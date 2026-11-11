import json

import pytest
from rilo.engine import RunContext
from rilo.snapshots import Snapshots
from rilo.worker import worker
from rilo.workspace_contracts import ConversationCreate, TurnCreate, WorkspaceOutput
from rilo.workspace_store import WorkspaceStore


def response(text, evidence):
    findings = []
    if evidence:
        source = evidence[0]
        findings = [
            {
                "title": "Source observation",
                "claim": source["content"],
                "citations": [
                    {
                        "source_id": source["id"],
                        "quote": source["content"],
                        "start_line": source["start_line"],
                        "end_line": source["end_line"],
                        "page": source.get("page"),
                    }
                ],
            }
        ]
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps({"summary": text, "facts": [], "findings": findings})
                }
            }
        ]
    }


@pytest.mark.asyncio
async def test_paired_histories_snapshots_and_followups_are_independent(store, monkeypatch):
    seen = []

    async def completion(self, messages, max_tokens=1100):
        seen.append((self.run["agent_id"], messages))
        return response(self.run["agent_id"] + " private answer", self.evidence)

    monkeypatch.setattr(RunContext, "completion", completion)
    workspace = WorkspaceStore(store)
    conversation = workspace.create(ConversationCreate(title="Independent histories"))
    first = workspace.turn(
        conversation["id"],
        TurnCreate(
            message="Summarize the supplied statement", inputs={"text": "The package uses SQLite."}
        ),
    )
    with pytest.raises(ValueError, match="current turn"):
        workspace.turn(conversation["id"], TurnCreate(message="Too soon"))
    await worker(store, once=True)
    detail = workspace.get(conversation["id"])
    assert len(detail["turns"][0]["runs"]) == 2
    assert all(r["outcome"] == "completed" for r in detail["turns"][0]["runs"])
    assert all(r["assessment"]["metrics"]["accuracy"] is None for r in detail["turns"][0]["runs"])
    assert seen[0][1][-1] == seen[1][1][-1]
    assert all("private answer" not in str(messages) for _, messages in seen)
    second = workspace.turn(conversation["id"], TurnCreate(message="What was your conclusion?"))
    await worker(store, once=True)
    for agent_id, messages in seen[2:]:
        other = "relay" if agent_id == "scout" else "scout"
        assert agent_id + " private answer" in str(messages)
        assert other + " private answer" not in str(messages)
    assert (
        store.experiment(first["id"])["manifest"]["snapshot"]["id"]
        == store.experiment(second["id"])["manifest"]["snapshot"]["id"]
    )


def test_snapshot_integrity_and_reference_validation(store):
    from rilo.verification import verify

    snapshots = Snapshots(store)
    snapshot = snapshots.create(
        "repository",
        [{"reference": "src/auth.py", "type": "repository", "content": "first\nsecond\nthird"}],
    )
    evidence = snapshots.select(snapshot["id"], "auth")
    output = WorkspaceOutput.model_validate(
        {
            "summary": "Analysis",
            "facts": [],
            "findings": [
                {
                    "title": "Claim",
                    "claim": "An interpretation",
                    "citations": [
                        {
                            "source_id": evidence[0]["id"],
                            "quote": "second",
                            "start_line": 99,
                            "end_line": 100,
                        }
                    ],
                }
            ],
        }
    )
    result = verify(output, evidence)
    assert result["findings"][0]["verification"]["state"] == "UNSUPPORTED"
    output.findings[0].citations[0].start_line = 2
    output.findings[0].citations[0].end_line = 2
    assert verify(output, evidence)["findings"][0]["verification"]["state"] == "PARTIALLY VERIFIED"
    key = snapshot["sources"][0]["content_hash"]
    (snapshots.root / key).write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        snapshots.get(snapshot["id"], True)


def test_code_quote_dedent_preserves_relative_indentation():
    from rilo.verification import locate_quote

    source = {"content": "    if enabled:\n        run()\n    stop()", "start_line": 40}
    matched = locate_quote(source, "if enabled:\n    run()")
    assert matched[:2] == (40, 41)
    assert matched[2] == "    if enabled:\n        run()"
    assert locate_quote(source, "if enabled:\nrun()") is None
    assert locate_quote(source, "if disabled:\n    run()") is None


def test_turn_idempotency_does_not_duplicate_work(store):
    workspace = WorkspaceStore(store)
    conv = workspace.create(ConversationCreate(title="Idempotency"))
    payload = TurnCreate(message="A repeated client request")
    first = workspace.turn(conv["id"], payload, "turn-request-1")
    second = workspace.turn(conv["id"], payload, "turn-request-1")
    assert first["id"] == second["id"]
    assert len(workspace.get(conv["id"])["turns"]) == 1
    with pytest.raises(ValueError, match="different turn"):
        workspace.turn(conv["id"], TurnCreate(message="Another request"), "turn-request-1")


@pytest.mark.asyncio
async def test_retry_preserves_original_and_sibling_then_uses_own_history(store, monkeypatch):
    from rilo.engine import InfrastructureError

    seen = []
    failed = True

    async def completion(self, messages, max_tokens=1100):
        seen.append((self.run["agent_id"], str(messages)))
        if failed and self.run["agent_id"] == "scout":
            raise InfrastructureError("Provider failed once")
        return response(self.run["agent_id"] + " private reply", self.evidence)

    monkeypatch.setattr(RunContext, "completion", completion)
    workspace = WorkspaceStore(store)
    conv = workspace.create(ConversationCreate(title="Retry"))
    original = workspace.turn(
        conv["id"],
        TurnCreate(message="Give one observation", inputs={"text": "SQLite stores records."}),
    )
    await worker(store, once=True)
    first = workspace.get(conv["id"])["turns"][0]
    bad = next(r for r in first["runs"] if r["agent_id"] == "scout")
    good = next(r for r in first["runs"] if r["agent_id"] == "relay")
    with pytest.raises(ValueError, match="failed or cancelled"):
        workspace.retry(good["id"])
    failed = False
    retried = workspace.retry(bad["id"])
    assert retried["spec"]["agent_ids"] == ["scout"]
    with pytest.raises(ValueError):
        workspace.turn(conv["id"], TurnCreate(message="Too early"))
    await worker(store, once=True)
    after = workspace.get(conv["id"])["turns"][0]
    assert len(after["attempts"]) == 3
    assert store.run(bad["id"])["outcome"] == "infrastructure_error"
    assert store.run(good["id"])["output"] == good["output"]
    assert all(r["outcome"] == "completed" for r in after["runs"])
    assert "relay private reply" not in seen[-1][1]
    assert (
        store.experiment(original["id"])["manifest"]["snapshot"]["id"]
        == store.experiment(retried["id"])["manifest"]["snapshot"]["id"]
    )
    workspace.turn(conv["id"], TurnCreate(message="Recall your answer"))
    await worker(store, once=True)
    for agent, messages in seen[-2:]:
        assert agent + " private reply" in messages
        assert ("relay" if agent == "scout" else "scout") + " private reply" not in messages


@pytest.mark.asyncio
async def test_context_budget_rejects_without_dispatch(store, monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("Over-budget requests must not reach inference")

    monkeypatch.setattr(RunContext, "completion", forbidden)
    workspace = WorkspaceStore(store)
    conv = workspace.create(ConversationCreate(title="Budget"))
    exp = workspace.turn(conv["id"], TurnCreate(message="x" * 6000))
    await worker(store, once=True)
    detail = store.experiment(exp["id"])
    assert detail["state"] == "failed"
    assert detail["summary"]["infrastructure_errors"] == 2


def test_workspace_auth_capability_and_search_availability(client, config):
    assert client.get("/api/v1/workspace/conversations").status_code == 401
    headers = {"Authorization": "Bearer " + config.session_key}
    assert (
        client.post(
            "/api/v1/workspace/conversations", headers=headers, json={"title": "Private local chat"}
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/workspace/conversations",
            headers=headers,
            json={"title": "Unavailable search", "search_provider": "tavily"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/workspace/conversations",
            headers=headers,
            json={"title": "Unsupported", "agent_ids": ["unknown", "relay"]},
        ).status_code
        == 409
    )


@pytest.mark.asyncio
async def test_workspace_provider_failure_is_recorded_without_fixture_fallback(store, monkeypatch):
    from rilo.engine import InfrastructureError

    async def unavailable(*args, **kwargs):
        raise InfrastructureError("Model unavailable.")

    monkeypatch.setattr(RunContext, "completion", unavailable)
    workspace = WorkspaceStore(store)
    conv = workspace.create(ConversationCreate(title="Failure"))
    exp = workspace.turn(conv["id"], TurnCreate(message="Explain something"))
    await worker(store, once=True)
    results = store.experiment(exp["id"])
    assert results["summary"]["infrastructure_errors"] == 2
    assert all(store.run(r["id"])["output"] is None for r in results["runs"])
