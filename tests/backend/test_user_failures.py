"""Regressions for source-free chat, title-only pages, and input retries."""

import json

import pytest
from rilo.engine import RunContext
from rilo.ingestion import github_repository
from rilo.promptfoo_checks import compare_runs, grade_output
from rilo.websites import crawl
from rilo.worker import worker
from rilo.workspace_contracts import ConversationCreate, TurnCreate
from rilo.workspace_store import WorkspaceStore


def test_repository_overview_keeps_readme_and_exact_lines_when_twenty_lines_exceed_budget(store):
    from rilo.snapshots import Snapshots

    text = "# Example\n" + "\n".join(["A useful project description with exact evidence." * 4] * 25)
    snapshots = Snapshots(store)
    snapshot = snapshots.create(
        "repository",
        [
            {"reference": "README.md", "type": "repository", "content": text},
            {
                "reference": "backend/app/engine.py",
                "type": "repository",
                "content": "import os\n" * 20,
            },
        ],
    )
    selection = snapshots.select(snapshot["id"], "tell me about the git hub repo", budget=2000)
    assert selection[0]["reference"] == "README.md"
    assert selection[0]["start_line"] == 1
    assert selection[0]["content"] == "\n".join(text.splitlines()[: selection[0]["end_line"]])
    assert len(selection[0]["content"]) <= 1600


async def test_conversation_identity_and_unverifiable_notes_preserve_original(store, monkeypatch):
    seen = []

    async def completion(self, messages, **kwargs):
        seen.append((self.run["agent_name"], messages))
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "I can help with questions.",
                                "findings": [
                                    {"title": "Language", "claim": "I understand language"}
                                ],
                            }
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(RunContext, "completion", completion)
    workspace = WorkspaceStore(store)
    conv = workspace.create(ConversationCreate(title="Capabilities"))
    exp = workspace.turn(conv["id"], TurnCreate(message="what are ur specialities"))
    await worker(store, once=True)
    for run in store.experiment(exp["id"])["runs"]:
        saved = store.run(run["id"])
        assert saved["outcome"] == "completed"
        assert saved["output"]["findings"][0]["claim"] == "I understand language"
        assert saved["assessment"]["findings"] == []
        assert saved["assessment"]["observations"][0]["title"] == "Language"
        assert saved["assessment"]["evidence_assessment"] == "not_applicable"
        assert saved["assessment"]["metrics"]["accuracy"] is None
    for name, messages in seen:
        assert f"You are {name}" in messages[0]["content"]
        assert "Search for this task is off" in messages[0]["content"]
        assert "findings:[]" in messages[-1]["content"]
    assert seen[0][1][-1] == seen[1][1][-1]


async def test_title_only_javascript_page_never_becomes_evidence(monkeypatch):
    async def fetch(url, **kwargs):
        return {
            "status": 200,
            "url": url,
            "headers": {"Content-Type": "text/html"},
            "body": b"User-agent: *\nAllow: /"
            if url.endswith("robots.txt")
            else b'<html><head><title>Upcoming Hackathons</title></head><body><div id="root"></div><script>renderEverything()</script></body></html>',
        }

    monkeypatch.setattr("rilo.websites.fetch", fetch)
    with pytest.raises(ValueError, match="No readable page body.*JavaScript"):
        await crawl("https://example.org/hackathons")


async def test_robust_agent_retries_missing_citations_once_and_preserves_original(
    store, monkeypatch
):
    calls: dict[str, int] = {}

    async def completion(self, messages, **kwargs):
        agent = self.run["agent_id"]
        calls[agent] = calls.get(agent, 0) + 1
        source = self.evidence[0]
        citations = (
            [{"source_id": source["id"], "quote": "SQLite saves records."}]
            if calls[agent] == 2
            else []
        )
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "SQLite stores data.",
                                "findings": [
                                    {
                                        "title": "Storage",
                                        "claim": "SQLite saves records.",
                                        "citations": citations,
                                    }
                                ],
                            }
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(RunContext, "completion", completion)
    workspace = WorkspaceStore(store)
    conv = workspace.create(ConversationCreate(title="Citation repair"))
    exp = workspace.turn(
        conv["id"], TurnCreate(message="Describe storage", inputs={"text": "SQLite saves records."})
    )
    await worker(store, once=True)
    assert calls == {"scout": 1, "relay": 2}
    runs = [store.run(r["id"]) for r in store.experiment(exp["id"])["runs"]]
    relay = next(r for r in runs if r["agent_id"] == "relay")
    scout = next(r for r in runs if r["agent_id"] == "scout")
    assert relay["assessment"]["metrics"]["citation_validity"] == 1
    assert scout["assessment"]["findings"][0]["verification"]["state"] == "UNSUPPORTED"
    original = next(e for e in relay["events"] if e["type"] == "citation_warning")
    assert original["data"]["output"]["findings"][0]["citations"] == []


async def test_public_repository_uses_pinned_bounded_files_without_archive(monkeypatch):
    calls = []

    async def fetch(url, **kwargs):
        calls.append((url, kwargs))
        if "raw.githubusercontent.com" in url:
            assert "headers" not in kwargs
            assert kwargs["limit"] == 200000
            assert "/" + "a" * 40 + "/" in url
            return {"status": 200, "body": b"# Real repository\n"}
        if "/git/trees/" in url:
            body = {
                "tree": [
                    {"type": "blob", "path": "README.md", "size": 18, "sha": "b" * 40},
                    {"type": "blob", "path": "large.mp4", "size": 20_000_000},
                    {"type": "blob", "path": "node_modules/a.js", "size": 10},
                    {"type": "blob", "path": "linked.py", "mode": "120000", "size": 10},
                ]
            }
        elif "/commits/" in url:
            body = {"sha": "a" * 40}
        else:
            body = {"default_branch": "main"}
        assert "Authorization" not in kwargs["headers"]
        return {"status": 200, "body": json.dumps(body).encode()}

    monkeypatch.setattr("rilo.ingestion.fetch", fetch)
    sources, metadata = await github_repository("https://github.com/owner/repo")
    assert [s["reference"] for s in sources] == ["README.md"]
    assert metadata["commit_sha"] == "a" * 40
    assert len(calls) == 4
    assert not any("codeload" in url for url, _ in calls)


async def test_failed_source_capture_can_retry_pair_without_overwriting_history(
    store, client, config, monkeypatch
):
    workspace = WorkspaceStore(store)
    conv = workspace.create(ConversationCreate(title="Input failure", category="repository"))
    exp = workspace.turn(
        conv["id"],
        TurnCreate(message="Explain repo", inputs={"url": "https://github.com/test/repo"}),
    )
    headers = {"Authorization": "Bearer " + config.session_key}
    assert (
        client.post(
            f"/api/v1/workspace/evaluations/{exp['id']}/retest", headers=headers
        ).status_code
        == 409
    )

    async def broken(*args):
        raise ValueError("Source exceeds size limit")

    monkeypatch.setattr("rilo.ingestion.ingest", broken)
    await worker(store, once=True)
    failed = store.experiment(exp["id"])
    assert failed["state"] == "failed" and "snapshot" not in failed["manifest"]
    retried = client.post(f"/api/v1/workspace/evaluations/{exp['id']}/retest", headers=headers)
    assert retried.status_code == 202, retried.text
    retry = retried.json()
    assert retry["manifest"]["workspace"]["inputs"] == failed["manifest"]["workspace"]["inputs"]
    assert retry["manifest"]["workspace"]["source_capture"] == "retry_input_capture"
    assert retry["spec"]["agent_ids"] == failed["spec"]["agent_ids"]

    async def captured(*args):
        return [{"reference": "README.md", "type": "repository", "content": "A project."}], {}

    async def completion(*args, **kwargs):
        return {"choices": [{"message": {"content": '{"summary":"A project","findings":[]}'}}]}

    monkeypatch.setattr("rilo.ingestion.ingest", captured)
    monkeypatch.setattr(RunContext, "completion", completion)
    await worker(store, once=True)
    assert store.experiment(retry["id"])["state"] == "completed"
    assert store.experiment(exp["id"])["state"] == "failed"


async def test_literal_typo_remains_failed_without_quality_winner():
    check = {
        "id": "title",
        "name": "Title",
        "type": "icontains",
        "value": "global ai hakathon",
        "target": "summary",
    }
    grade = await grade_output({"summary": "Global AI Hackathon"}, [check])
    assert grade["status"] == "fail" and grade["score"] == 0
    runs = [
        {
            "id": agent,
            "agent_id": agent,
            "agent_name": agent,
            "outcome": "completed",
            "assessment": {"task_checks": grade},
        }
        for agent in ["scout", "relay"]
    ]
    comparison = compare_runs(runs)
    assert comparison["verdict"] == "neither_met_checks"
    assert comparison["winner"] is None
