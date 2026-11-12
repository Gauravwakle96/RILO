"""Retained snapshots, local retention, resumable batches and isolated continuations."""

import json

import pytest
from rilo.engine import RunContext
from rilo.local_product import history, manage_record
from rilo.worker import worker
from rilo.workspace_contracts import ConversationCreate, TurnCreate
from rilo.workspace_store import WorkspaceStore


@pytest.fixture
def completion(monkeypatch):
    async def respond(self, messages, **kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"summary": self.run["agent_id"] + " own answer", "findings": []}
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(RunContext, "completion", respond)


async def completed(store):
    workspace = WorkspaceStore(store)
    conv = workspace.create(
        ConversationCreate(
            title="Gap verification", slots=[{"agent_id": "scout"}, {"agent_id": "relay"}]
        )
    )
    exp = workspace.turn(
        conv["id"],
        TurnCreate(
            message="Describe this",
            inputs={"text": "Real captured test context."},
            checks=[{"id": "short", "name": "Short answer", "type": "max-length", "value": "100"}],
        ),
    )
    await worker(store, once=True)
    return conv, store.experiment(exp["id"])


async def test_candidate_keeps_snapshot_histories_checks_and_original(client, config, completion):
    from rilo.storage import Store

    store = Store(config)
    conv, exp = await completed(store)
    original = json.dumps(exp["manifest"], sort_keys=True)
    response = client.post(
        f"/api/v1/workspace/evaluations/{exp['id']}/retest",
        headers={"Authorization": "Bearer " + config.session_key},
        json={
            "slots": [
                {"agent_id": "scout", "instructions": "Candidate instructions"},
                {"agent_id": "relay"},
            ]
        },
    )
    assert response.status_code == 202, response.text
    candidate = response.json()
    assert candidate["manifest"]["workspace"]["snapshot_id"] == exp["manifest"]["snapshot"]["id"]
    assert (
        candidate["manifest"]["workspace"]["histories"] == exp["manifest"]["workspace"]["histories"]
    )
    assert candidate["manifest"]["workspace"]["checks"] == exp["manifest"]["workspace"]["checks"]
    assert (
        candidate["manifest"]["agent_versions"][0]["config"]["instructions"]
        == "Candidate instructions"
    )
    assert json.dumps(store.experiment(exp["id"])["manifest"], sort_keys=True) == original
    await worker(store, once=True)
    assert store.experiment(candidate["id"])["state"] == "completed"


async def test_retention_preserves_sources_and_protects_linked_evaluations(store, completion):
    conv, exp = await completed(store)
    assert history(store, "experiments")["total"] == 1
    manage_record(store, "experiments", exp["id"], "archive")
    assert history(store, "experiments")["total"] == 0
    assert history(store, "experiments", archived=True)["total"] == 1
    assert store.experiment(exp["id"])["state"] == "completed"
    manage_record(store, "experiments", exp["id"], "restore")
    with pytest.raises(ValueError, match="conversation"):
        manage_record(store, "experiments", exp["id"], "delete", exp["id"])
    with pytest.raises(ValueError, match="exact record"):
        manage_record(store, "conversations", conv["id"], "delete")
    manage_record(store, "conversations", conv["id"], "delete", conv["id"])
    with pytest.raises(KeyError):
        store.experiment(exp["id"])
    assert list((store.config.data_dir / "objects").iterdir())


async def test_continuation_is_isolated_and_original_history_unchanged(store, completion):
    conv, exp = await completed(store)
    workspace = WorkspaceStore(store)
    continuation = workspace.continue_conversation(conv["id"])
    histories = continuation["continuation"]["histories"]
    assert "slot_a own answer" in histories["slot_a"][0]["content"]
    assert "slot_b own answer" not in histories["slot_a"][0]["content"]
    assert "slot_a own answer" not in histories["slot_b"][0]["content"]
    next_exp = workspace.turn(
        continuation["id"],
        TurnCreate(message="Continue", snapshot_id=exp["manifest"]["snapshot"]["id"]),
    )
    assert next_exp["manifest"]["workspace"]["histories"] == histories
    assert len(workspace.get(conv["id"])["turns"]) == 1
    await worker(store, once=True)
    assert store.experiment(next_exp["id"])["state"] == "completed"


async def test_batch_has_combined_results_and_idempotent_resume(client, config, completion):
    from rilo.storage import Store

    store = Store(config)
    _, first = await completed(store)
    _, second = await completed(store)
    headers = {"Authorization": "Bearer " + config.session_key}
    suite = client.post(
        "/api/v1/workspace/suites",
        headers=headers,
        json={
            "name": "Two cases",
            "version": "1",
            "source_experiment_id": first["id"],
            "additional_experiment_ids": [second["id"]],
            "repetitions": 1,
        },
    ).json()
    response = client.post(
        f"/api/v1/workspace/suites/{suite['id']}/batches", headers=headers, json={}
    )
    assert response.status_code == 202, response.text
    batch = response.json()
    assert len(batch["cases"]) == 2
    same = client.post(
        f"/api/v1/workspace/batches/{batch['id']}/resume", headers=headers, json={}
    ).json()
    assert same["cases"] == batch["cases"]
    for _ in range(2):
        await worker(store, once=True)
    result = client.get(f"/api/v1/workspace/batches/{batch['id']}", headers=headers).json()
    assert result["state"] == "finished"
    assert all(a["assessed"] == 2 and a["passed"] == 2 for a in result["agents"])
    assert (
        client.get(f"/api/v1/workspace/batches/{batch['id']}/export", headers=headers).status_code
        == 200
    )
    with pytest.raises(ValueError, match="suite"):
        manage_record(
            store,
            "conversations",
            WorkspaceStore(store).get(first["manifest"]["workspace"]["conversation_id"])["id"],
            "delete",
            first["manifest"]["workspace"]["conversation_id"],
        )


def test_search_off_requires_evidence_before_queuing(store):
    workspace = WorkspaceStore(store)
    conv = workspace.create(ConversationCreate(title="Search", category="search"))
    with pytest.raises(ValueError, match="Paste a public website URL"):
        workspace.turn(conv["id"], TurnCreate(message="Find a person"))
    assert store.experiments() == []
    exp = workspace.turn(conv["id"], TurnCreate(message="Investigate https://example.com"))
    assert exp["manifest"]["workspace"]["inputs"]["url"] == "https://example.com"


def test_unicode_fonts_have_real_glyphs_and_missing_scripts_fail():
    from rilo.pdf_fonts import paragraph_text

    text = paragraph_text("café Ελληνικά Русский नमस्ते العربية")
    assert "RiloNotoSansDevanagari" in text and "RiloNotoSansArabic" in text
    assert "namaste" not in text
    with pytest.raises(ValueError, match="U\\+"):
        paragraph_text("😀")


def test_dns_fallback_still_rejects_private_addresses(monkeypatch):
    from rilo.network import resolve_public

    def fail(*args, **kwargs):
        raise OSError("DNS unavailable")

    monkeypatch.setattr("rilo.network.socket.getaddrinfo", fail)
    monkeypatch.setattr("rilo.network.fallback_addresses", lambda host: {"93.184.216.34"})
    assert resolve_public("example.org", 443) == "93.184.216.34"
    monkeypatch.setattr(
        "rilo.network.fallback_addresses", lambda host: {"93.184.216.34", "127.0.0.1"}
    )
    with pytest.raises(ValueError, match="private"):
        resolve_public("example.org", 443)


async def test_bynara_uses_fixed_endpoint_private_key_and_offline_policy(store, monkeypatch):
    from rilo.schemas import ExperimentCreate

    store.config.bynara_key = "private-test-bynara-credential"
    store.config.bifrost_key = "different-local-gateway-key"
    spec = ExperimentCreate(
        name="Bynara contract",
        agent_ids=["scout"],
        task_ids=["company_brief"],
        scenario_ids=["normal"],
        repetitions=1,
        engine="bifrost",
        model="bynara/agnes-2.5-flash",
    )
    exp = store.create_experiment(spec)
    seen = []

    async def response(client, method, url, **kwargs):
        seen.append((url, kwargs))
        return {"model": "agnes-2.5-flash", "choices": [{"message": {"content": "{}"}}]}

    monkeypatch.setattr("rilo.engine.bounded_json", response)
    context = RunContext(store, exp["runs"][0], spec, exp["manifest"]["task_versions"][0], [])
    await context.completion([{"role": "user", "content": "Small test"}])
    url, request = seen[0]
    assert url == "https://router.bynara.id/v1/chat/completions"
    assert request["json"]["model"] == "agnes-2.5-flash"
    assert request["headers"]["Authorization"] == "Bearer " + store.config.bynara_key
    assert "x-bf-vk" not in request["headers"]
    assert context.stats()["input_tokens"] is None
    store.config.offline = True
    from rilo.engine import InfrastructureError

    with pytest.raises(InfrastructureError, match="Offline"):
        await context.completion([{"role": "user", "content": "Blocked"}])
    assert len(seen) == 1


@pytest.mark.parametrize(
    "status,message", [(402, "credits are insufficient"), (404, "model or endpoint was not found")]
)
async def test_provider_errors_are_actionable_without_response_secret(status, message):
    import httpx
    from rilo.engine import InfrastructureError, bounded_json

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, json={"error": "secret-provider-body"})
        )
    ) as client:
        with pytest.raises(InfrastructureError, match=message) as error:
            await bounded_json(client, "POST", "https://router.bynara.id/v1/chat/completions")
    assert "secret-provider-body" not in str(error.value)


async def test_human_review_does_not_overwrite_automated_evidence(client, config, monkeypatch):
    from rilo.storage import Store

    store = Store(config)

    async def response(self, messages, **kwargs):
        source = self.evidence[0]
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "Context",
                                "findings": [
                                    {
                                        "title": "Source",
                                        "claim": source["content"],
                                        "citations": [
                                            {"source_id": source["id"], "quote": source["content"]}
                                        ],
                                    }
                                ],
                            }
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(RunContext, "completion", response)
    _, exp = await completed(store)
    run = store.run(exp["runs"][0]["id"])
    before = json.dumps(run["assessment"], sort_keys=True)
    finding = run["assessment"]["findings"][0]
    headers = {"Authorization": "Bearer " + config.session_key}
    result = client.post(
        f"/api/v1/workspace/runs/{run['id']}/reviews",
        headers=headers,
        json={
            "finding_id": finding["id"],
            "state": "NEEDS MANUAL REVIEW",
            "rationale": "Interpretation needs reproduction.",
        },
    )
    assert result.status_code == 201, result.text
    assert result.json()["data"]["method"] == "human-reviewed"
    assert json.dumps(store.run(run["id"])["assessment"], sort_keys=True) == before
    result = client.post(
        f"/api/v1/workspace/runs/{run['id']}/reviews",
        headers=headers,
        json={"finding_id": "unknown", "state": "VERIFIED", "rationale": "invalid"},
    )
    assert result.status_code == 409


async def test_restart_preserves_completed_agent_and_marks_interrupted_agent(
    store, config, completion
):
    import time

    from rilo.schemas import ExperimentCreate
    from rilo.storage import Store
    from rilo.worker import execute_run
    from rilo.workspace_engine import prepare

    workspace = WorkspaceStore(store)
    conv = workspace.create(ConversationCreate(title="Restart checkpoint"))
    exp = workspace.turn(
        conv["id"], TurnCreate(message="Summarize", inputs={"text": "Captured before restart."})
    )
    assert store.claim("restart-check") == exp["id"]
    exp = store.experiment(exp["id"])
    manifest = await prepare(store, exp)
    await execute_run(store, exp["runs"][0], ExperimentCreate.model_validate(exp["spec"]), manifest)
    saved = store.run(exp["runs"][0]["id"])
    store.update_run(exp["runs"][1]["id"], {"outcome": "running"})
    with store.transaction() as c:
        c.execute("UPDATE experiments SET lease_until=? WHERE id=?", (time.time() - 1, exp["id"]))
    restarted = Store(config)
    assert restarted.recover() == 1
    assert restarted.run(saved["id"])["output"] == saved["output"]
    assert restarted.run(exp["runs"][1]["id"])["outcome"] == "interrupted"
    assert restarted.experiment(exp["id"])["state"] == "partial"
