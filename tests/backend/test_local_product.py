"""Local product boundaries: independent candidates, real sources, privacy and checks."""

import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from rilo.config import Config, redact
from rilo.engine import InfrastructureError, RunContext, bounded_json
from rilo.local_product import dashboard, history, orphan_files, storage_file_sizes, storage_status
from rilo.promptfoo_checks import grade_output
from rilo.schemas import ExperimentCreate
from rilo.snapshots import Snapshots
from rilo.task_checks import TaskCheck
from rilo.worker import worker
from rilo.workspace_contracts import ConversationCreate, TurnCreate
from rilo.workspace_store import WorkspaceStore


def context(store, model):
    spec = ExperimentCreate(
        name="Provider test",
        agent_ids=["scout"],
        task_ids=["company_brief"],
        scenario_ids=["normal"],
        repetitions=1,
        engine="bifrost",
        model=model,
    )
    experiment = store.create_experiment(spec)
    return RunContext(
        store, experiment["runs"][0], spec, experiment["manifest"]["task_versions"][0], []
    )


async def test_agentrouter_has_fixed_endpoint_private_auth_and_unknown_usage(store, monkeypatch):
    store.config.agentrouter_key = "test-secret-for-private-provider"
    store.config.bifrost_key = "different-gateway-secret"
    received = []

    async def response(client, method, url, **kwargs):
        received.append((url, kwargs))
        return {"model": "example-model", "choices": [{"message": {"content": "{}"}}]}

    monkeypatch.setattr("rilo.engine.bounded_json", response)
    run = context(store, "agentrouter/example-model")
    await run.completion([{"role": "user", "content": "A small test"}])
    url, request = received[0]
    assert url == "https://agentrouter.org/v1/chat/completions"
    assert request["json"]["model"] == "example-model"
    assert request["headers"]["Authorization"] == "Bearer " + store.config.agentrouter_key
    assert "x-bf-vk" not in request["headers"]
    assert run.stats()["api_cost_usd"] is None
    assert run.stats()["tokens_provenance"] == "unknown"
    assert store.config.agentrouter_key not in json.dumps(redact(request, store.config.secrets))


@pytest.mark.parametrize("model", ["agentrouter/example", "openai/example"])
async def test_offline_refresh_blocks_remote_inference_before_dispatch(store, monkeypatch, model):
    run = context(store, model)
    separate_api_config = Config(
        root=store.config.root, data_dir=store.config.data_dir, offline=True
    )
    separate_api_config.save(separate_api_config.bifrost_url, separate_api_config.model)

    async def forbidden(*args, **kwargs):
        pytest.fail("Offline must not dispatch external inference")

    monkeypatch.setattr("rilo.engine.bounded_json", forbidden)
    with pytest.raises(InfrastructureError, match="Offline mode"):
        await run.completion([])


@pytest.mark.parametrize(
    "code,phrase", [(401, "Authentication"), (403, "Authentication"), (429, "credit limit")]
)
async def test_provider_failure_is_actionable_without_echoing_secrets(code, phrase):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(code, json={"error": "private credential"})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(InfrastructureError, match=phrase) as error:
            await bounded_json(client, "POST", "https://example.org/v1")
    assert "private credential" not in str(error.value)


async def test_same_profile_slots_models_and_histories_are_independent(store, monkeypatch):
    seen = []

    async def completion(self, messages, **kwargs):
        seen.append((self.run["agent_id"], self.spec.model, messages))
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"summary": self.run["agent_id"] + " private answer", "findings": []}
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(RunContext, "completion", completion)
    workspace = WorkspaceStore(store)
    conversation = workspace.create(
        ConversationCreate(
            title="Same agent distinct candidates",
            slots=[
                {"agent_id": "scout", "model": "ollama/model-a", "instructions": "Be concise"},
                {
                    "agent_id": "scout",
                    "model": "ollama/model-b",
                    "instructions": "Explain carefully",
                },
            ],
        )
    )
    first = workspace.turn(conversation["id"], TurnCreate(message="Say hello"))
    await worker(store, once=True)
    assert store.experiment(first["id"])["state"] == "completed"
    assert {model for _, model, _ in seen} == {"ollama/model-a", "ollama/model-b"}
    assert seen[0][2][-1] == seen[1][2][-1]
    workspace.turn(conversation["id"], TurnCreate(message="Continue"))
    await worker(store, once=True)
    for agent, _, messages in seen[2:]:
        other = "slot_b" if agent == "slot_a" else "slot_a"
        assert agent + " private answer" in str(messages)
        assert other + " private answer" not in str(messages)


async def test_chat_url_captures_shared_website_evidence(store, monkeypatch):
    seen = []

    async def crawl(url, max_pages, max_depth):
        return [
            {
                "type": "website",
                "reference": url,
                "title": "Documentation",
                "content": "The project stores results in SQLite.",
            }
        ], {"url": url}

    async def completion(self, messages, **kwargs):
        source = self.evidence[0]
        seen.append(source)
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "Results use SQLite.",
                                "findings": [
                                    {
                                        "title": "Storage",
                                        "claim": "Results use SQLite.",
                                        "citations": [
                                            {
                                                "source_id": source["id"],
                                                "quote": "The project stores results in SQLite.",
                                            }
                                        ],
                                    }
                                ],
                            }
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr("rilo.websites.crawl", crawl)
    monkeypatch.setattr(RunContext, "completion", completion)
    workspace = WorkspaceStore(store)
    conversation = workspace.create(ConversationCreate(title="Website in chat"))
    experiment = workspace.turn(
        conversation["id"],
        TurnCreate(message="How are results stored?", inputs={"url": "https://example.org/docs"}),
    )
    await worker(store, once=True)
    assert seen[0] == seen[1]
    for run in store.experiment(experiment["id"])["runs"]:
        run = store.run(run["id"])
        assert run["outcome"] == "completed"
        assert run["assessment"]["findings"][0]["verification"]["citations"][0]["valid"]


async def test_offline_blocks_uncaptured_url_before_inference(store, monkeypatch):
    store.config.offline = True
    workspace = WorkspaceStore(store)
    conversation = workspace.create(ConversationCreate(title="Offline URL"))
    experiment = workspace.turn(
        conversation["id"],
        TurnCreate(message="Summarize", inputs={"url": "https://example.org/docs"}),
    )
    await worker(store, once=True)
    assert store.experiment(experiment["id"])["state"] == "failed"
    for run in store.experiment(experiment["id"])["runs"]:
        run = store.run(run["id"])
        assert "Offline mode" in run["assessment"]["checks"][0]["evidence"]


async def test_native_checks_preserve_undefined_accuracy_and_reference_integrity():
    checks = [
        {
            "id": "field",
            "name": "Typed JSON value",
            "type": "json-field-equals",
            "value": '{"path":"flag","value":true}',
        },
        {"id": "length", "name": "Short answer", "type": "max-length", "value": "40"},
        {"id": "citations", "name": "Valid references", "type": "citations-valid"},
    ]
    result = await grade_output(
        {"summary": '{"flag":1}', "findings": []}, checks, assessment={"findings": []}
    )
    assert [check["passed"] for check in result["checks"]] == [False, True, False]
    assert result["score"] == 1 / 3


@pytest.mark.parametrize(
    "value", ["[]", "null", '"text"', '{"path":"","value":1}', '{"path":"flag"}']
)
def test_invalid_json_rules_are_validation_errors(value):
    with pytest.raises(ValidationError):
        TaskCheck(id="rule", name="Invalid rule", type="json-field-equals", value=value)


def test_pagination_totals_and_cleanup_protect_saved_sources(store):
    for index in range(203):
        store.create_experiment(
            ExperimentCreate(
                name=f"Record {index}",
                agent_ids=["scout"],
                task_ids=["company_brief"],
                scenario_ids=["normal"],
                repetitions=1,
                engine="fixture",
            )
        )
        with store.transaction() as connection:
            connection.execute("UPDATE experiments SET state='completed' WHERE state='queued'")
    assert history(store, "experiments", page=9)["total"] == 203
    assert len(history(store, "experiments", page=9)["items"]) == 3
    assert dashboard(store)["evaluations"] == 203
    snapshot = Snapshots(store).create(
        "chat", [{"reference": "Context", "type": "text", "content": "Keep this source."}]
    )
    retained = store.config.data_dir / "objects" / snapshot["sources"][0]["content_hash"]
    orphan = store.config.data_dir / "objects" / "orphan"
    orphan.write_text("unreferenced")
    assert orphan in orphan_files(store)
    assert retained not in orphan_files(store)


def test_message_url_auto_capture_and_invalid_focus_are_explicit(store):
    workspace = WorkspaceStore(store)
    conversation = workspace.create(ConversationCreate(title="URL detection"))
    experiment = workspace.turn(
        conversation["id"], TurnCreate(message="Please inspect https://example.org/docs.")
    )
    assert experiment["manifest"]["workspace"]["inputs"]["url"] == "https://example.org/docs"
    snapshot = Snapshots(store).create(
        "repository",
        [{"reference": "src/app.py", "type": "repository", "content": "print('hello')"}],
    )
    with pytest.raises(ValueError, match="not present"):
        Snapshots(store).select(snapshot["id"], "hello", references=["missing.py"])


async def test_http_only_readiness_does_not_require_local_model_services(store, monkeypatch):
    from rilo.readiness import PreflightInput, readiness

    store.add_item(
        "agent",
        {
            "id": "test_adapter",
            "name": "Adapter",
            "description": "Test adapter",
            "kind": "http",
            "version": "1",
            "framework": "HTTP",
            "capabilities": ["final_output"],
            "config": {
                "endpoint": "http://127.0.0.1:9999/run",
                "protocol": "workspace-v1",
                "workspace_categories": ["chat"],
            },
        },
    )
    store.claim("readiness_test")

    async def forbidden(*args, **kwargs):
        pytest.fail("HTTP-only readiness must not call model services")

    monkeypatch.setattr("rilo.readiness.bounded_json", forbidden)
    result = await readiness(
        store,
        PreflightInput(
            configuration=ConversationCreate(
                title="Custom pair",
                slots=[{"agent_id": "test_adapter"}, {"agent_id": "test_adapter"}],
            ),
            test_inference=True,
        ),
    )
    assert result["ready"]
    assert any("workspace-v1" in check["detail"] for check in result["checks"])
    store.config.offline = True
    assert not (
        await readiness(
            store,
            PreflightInput(
                configuration=ConversationCreate(
                    title="Custom pair",
                    slots=[{"agent_id": "test_adapter"}, {"agent_id": "test_adapter"}],
                )
            ),
        )
    )["ready"]


async def test_workspace_adapter_receives_only_own_history_and_has_unknown_metrics(
    store, monkeypatch
):
    store.add_item(
        "agent",
        {
            "id": "test_adapter",
            "name": "Adapter",
            "description": "Test adapter",
            "kind": "http",
            "version": "1",
            "framework": "HTTP",
            "capabilities": ["final_output"],
            "config": {
                "endpoint": "http://127.0.0.1:9999/run",
                "protocol": "workspace-v1",
                "workspace_categories": ["chat"],
            },
        },
    )
    seen = []

    async def response(client, method, url, **kwargs):
        seen.append(kwargs["json"])
        return {"output": {"summary": f"Private answer {len(seen)}", "findings": []}}

    monkeypatch.setattr("rilo.workspace_engine.bounded_json", response)
    workspace = WorkspaceStore(store)
    conversation = workspace.create(
        ConversationCreate(
            title="Adapter pair", slots=[{"agent_id": "test_adapter"}, {"agent_id": "test_adapter"}]
        )
    )
    experiment = workspace.turn(conversation["id"], TurnCreate(message="Hello"))
    await worker(store, once=True)
    assert len(seen) == 2 and all(not request["history"] for request in seen)
    for run in store.experiment(experiment["id"])["runs"]:
        run = store.run(run["id"])
        assert run["outcome"] == "completed"
        assert run["tool_calls"] is None and run["input_tokens"] is None
        assert run["api_cost_usd"] is None


def test_local_backup_download_and_cleanup_require_no_active_work(client, config):
    from rilo.storage import Store

    csrf = client.get("/api/v1/session").json()["csrf_token"]
    result = client.get("/api/v1/workspace/backup")
    assert result.status_code == 200 and result.content[:2] == b"\x1f\x8b"
    store = Store(config)
    store.create_experiment(
        ExperimentCreate(
            name="Pending",
            agent_ids=["scout"],
            task_ids=["company_brief"],
            scenario_ids=["normal"],
            repetitions=1,
        )
    )
    assert client.get("/api/v1/workspace/backup").status_code == 409
    assert (
        client.post(
            "/api/v1/workspace/storage/cleanup", json={}, headers={"X-CSRF-Token": csrf}
        ).status_code
        == 409
    )


@pytest.mark.parametrize("relative", ["uploads/disappearing", "rilo.db-shm"])
def test_storage_status_survives_files_removed_during_size_read(store, monkeypatch, relative):
    vanished = store.config.data_dir / relative
    vanished.parent.mkdir(exist_ok=True)
    vanished.write_bytes(b"transient")
    retained = store.config.data_dir / "uploads" / "retained"
    retained.parent.mkdir(exist_ok=True)
    retained.write_bytes(b"saved upload")
    original_stat = Path.stat

    def remove_during_read(path, *args, **kwargs):
        if path == vanished:
            vanished.unlink(missing_ok=True)
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", remove_during_read)
    result = storage_status(store)
    assert result["uploads"] == len(b"saved upload")
    assert result["database"] > 0
    assert retained.read_bytes() == b"saved upload"


def test_storage_size_read_preserves_permission_errors(tmp_path, monkeypatch):
    denied = tmp_path / "denied"
    original_stat = Path.stat

    def deny_read(path, *args, **kwargs):
        if path == denied:
            raise PermissionError("Storage read denied")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", deny_read)
    with pytest.raises(PermissionError, match="Storage read denied"):
        storage_file_sizes([denied])


@pytest.mark.parametrize("route", ["status", "cleanup"])
def test_storage_routes_survive_orphan_removed_after_listing(client, config, monkeypatch, route):
    from rilo.storage import Store

    store = Store(config)
    snapshot = Snapshots(store).create(
        "chat", [{"reference": "Context", "type": "text", "content": "Keep this source."}]
    )
    retained = config.data_dir / "objects" / snapshot["sources"][0]["content_hash"]
    vanished = config.data_dir / "objects" / "transient-orphan"
    remaining = config.data_dir / "objects" / "remaining-orphan"
    vanished.write_bytes(b"removed elsewhere")
    remaining.write_bytes(b"reclaimable")

    def disappear_after_listing(store):
        files = orphan_files(store)
        vanished.unlink()
        return files

    monkeypatch.setattr("rilo.local_product.orphan_files", disappear_after_listing)
    csrf = client.get("/api/v1/session").json()["csrf_token"]
    if route == "status":
        response = client.get("/api/v1/workspace/storage")
        assert response.status_code == 200
        assert response.json()["orphan_files"] == 1
        assert response.json()["reclaimable_bytes"] == len(b"reclaimable")
        assert remaining.exists()
    else:
        response = client.post(
            "/api/v1/workspace/storage/cleanup", json={}, headers={"X-CSRF-Token": csrf}
        )
        assert response.status_code == 200
        assert response.json()["removed_files"] == 1
        assert not remaining.exists()
    assert retained.read_text() == "Keep this source."
