import asyncio
import copy
import json
import os
import shutil

import pytest
from pydantic import ValidationError
from rilo.engine import RunContext
from rilo.promptfoo_checks import RUNTIME, availability, compare_runs, grade_output
from rilo.readiness import PreflightInput, readiness
from rilo.reports import export, report_data
from rilo.task_checks import TaskCheck
from rilo.worker import worker
from rilo.workspace_contracts import ConversationCreate, TurnCreate
from rilo.workspace_evaluation import RegressionCreate, compare_workspace
from rilo.workspace_store import WorkspaceStore

RULE = {
    "id": "storage",
    "name": "Names the database",
    "type": "icontains",
    "value": "sqlite",
    "target": "summary",
}


@pytest.mark.parametrize(
    "patch",
    [
        {"type": "javascript", "value": "process.exit()"},
        {"type": "regex", "value": "(a+)+$"},
        {"value": "file:///private/key"},
        {"value": " package:malicious"},
        {"value": ""},
        {"value": " "},
        {"type": "is-json", "value": "file://schema"},
        {"provider": "https://example.com"},
        {"target": "file"},
    ],
)
def test_check_contract_rejects_executable_or_ambiguous_configuration(patch):
    with pytest.raises(ValidationError):
        TaskCheck.model_validate({**RULE, **patch})


def test_turn_checks_have_unique_ids():
    with pytest.raises(ValidationError, match="unique"):
        TurnCreate(message="A task", checks=[RULE, RULE])


async def test_actual_promptfoo_grading_and_literal_template_values(monkeypatch):
    assert availability()["available"], "Install the locked Promptfoo runtime for integration tests"
    monkeypatch.setenv("TEST_GRADER_SECRET", "private-sentinel")
    output = {"summary": "SQLite saves history. {{ env.TEST_GRADER_SECRET }}"}
    checks = [
        RULE,
        {**RULE, "id": "wrong", "type": "contains", "value": "PostgreSQL"},
        {**RULE, "id": "literal", "value": "{{ env.TEST_GRADER_SECRET }}"},
        {**RULE, "id": "valid", "type": "is-json", "value": None, "target": "response"},
        {**RULE, "id": "no_json", "type": "is-json", "value": None},
        {**RULE, "id": "no_mysql", "type": "not-icontains", "value": "mysql"},
    ]
    result = await grade_output(output, checks)
    assert result["version"] == "0.125.1"
    assert result["status"] == "fail"
    assert [row["passed"] for row in result["checks"]] == [True, False, True, True, False, True]
    assert result["score"] == 4 / 6
    assert "private-sentinel" not in json.dumps(result)
    assert output["summary"].startswith("SQLite")


async def test_empty_checks_are_ungraded_and_missing_runtime_is_evaluator_error(monkeypatch):
    monkeypatch.setattr(
        "rilo.promptfoo_checks.availability",
        lambda: {"available": False, "detail": "Runtime unavailable"},
    )
    assert (await grade_output({"summary": "text"}, []))["status"] == "ungraded"
    result = await grade_output({"summary": "text"}, [RULE])
    assert result["status"] == "error" and result["score"] is None
    assert result["reason"] == "Runtime unavailable"


async def test_promptfoo_timeout_and_empty_answer_are_not_success():
    result = await grade_output({"summary": "text"}, [RULE], timeout=0.001)
    assert result["status"] == "error" and "timed out" in result["reason"]
    result = await grade_output({"summary": ""}, [RULE])
    assert result["status"] == "fail"


async def test_actual_worker_grading_persistence_suites_reports_and_regressions(
    store, client, config, monkeypatch
):
    improved = False
    messages = []

    async def completion(self, prompt, max_tokens=1100):
        messages.append((self.run["agent_id"], str(prompt)))
        summary = (
            "SQLite saves history."
            if self.run["agent_id"] == "relay" or improved
            else "Records are stored."
        )
        return {
            "choices": [{"message": {"content": json.dumps({"summary": summary, "findings": []})}}]
        }

    monkeypatch.setattr(RunContext, "completion", completion)
    workspace = WorkspaceStore(store)
    conv = workspace.create(ConversationCreate(title="Explicit database requirement"))
    source = workspace.turn(
        conv["id"],
        TurnCreate(
            message="Name the database used by this project",
            inputs={"text": "The project stores records in SQLite."},
            checks=[RULE],
        ),
    )
    await worker(store, once=True)
    first = report_data(store, source["id"])
    assert {run["agent_id"]: run["assessment_status"] for run in first["runs"]} == {"scout": "fail", "relay": "pass"}
    assert all(run["outcome"] == "completed" for run in first["runs"])
    comparison = next(a["data"] for a in first["artifacts"] if a["kind"] == "comparison")
    assert comparison["winner"] == "relay"
    assert not any("Names the database" in prompt for _, prompt in messages), (
        "Expected test labels must not leak to agents"
    )
    for fmt in ("json", "csv", "md", "pdf"):
        data, _ = export(first, fmt)
        assert data
        if fmt in {"json", "csv", "md"}:
            assert b"Names the database" in data
    headers = {"Authorization": "Bearer " + config.session_key}
    suite_response = client.post(
        "/api/v1/workspace/suites",
        headers=headers,
        json={
            "name": "Database checks",
            "version": "1",
            "source_experiment_id": source["id"],
            "repetitions": 1,
        },
    )
    assert suite_response.status_code == 201, suite_response.text
    suite = suite_response.json()
    assert suite["checks"] == [RULE]
    repeated = client.post(f"/api/v1/workspace/suites/{suite['id']}/run", headers=headers).json()
    await worker(store, once=True)
    baseline = report_data(store, repeated["id"])
    improved = True
    candidate = client.post(f"/api/v1/workspace/suites/{suite['id']}/run", headers=headers).json()
    await worker(store, once=True)
    after = report_data(store, candidate["id"])
    assert (
        next(a["data"] for a in after["artifacts"] if a["kind"] == "comparison")["verdict"] == "tie"
    )
    spec = RegressionCreate(baseline_id=repeated["id"], candidate_id=candidate["id"])
    delta = compare_workspace(baseline, after, spec)
    assert delta["compatible"] and delta["gate"] == "no_observed_regression"
    assert delta["agent_deltas"][0]["check_score_delta"] == 1
    assert delta["agent_deltas"][0]["now_passing_checks"] == ["Names the database"]
    # Reverse direction actually detects a regression.
    assert compare_workspace(after, baseline, spec)["gate"] == "regression"
    changed = copy.deepcopy(after)
    changed["manifest"]["workspace"]["checks"][0]["value"] = "other"
    assert not compare_workspace(baseline, changed, spec)["compatible"]


async def test_grader_failure_preserves_agent_output(store, monkeypatch):
    async def completion(*args, **kwargs):
        return {"choices": [{"message": {"content": '{"summary":"saved response","findings":[]}'}}]}

    monkeypatch.setattr(RunContext, "completion", completion)
    monkeypatch.setattr(
        "rilo.promptfoo_checks.availability",
        lambda: {"available": False, "detail": "Runtime unavailable"},
    )
    workspace = WorkspaceStore(store)
    conv = workspace.create(ConversationCreate(title="Evaluator unavailable"))
    exp = workspace.turn(conv["id"], TurnCreate(message="Answer this", checks=[RULE]))
    await worker(store, once=True)
    data = report_data(store, exp["id"])
    for run in data["runs"]:
        assert run["outcome"] == "completed" and run["output"]["summary"] == "saved response"
        assert run["assessment_status"] == "inconclusive"
        assert run["assessment"]["task_checks"]["status"] == "error"
    assert compare_runs(data["runs"])["winner"] is None


async def test_readiness_checks_actual_configuration_and_worker_lease(store, monkeypatch):
    async def listing(client, method, url):
        return (
            {"models": [{"name": "qwen2.5-coder:7b"}]} if url.endswith("tags") else {"status": "ok"}
        )

    monkeypatch.setattr("rilo.readiness.bounded_json", listing)
    payload = PreflightInput(
        configuration=ConversationCreate(title="Readiness"), require_checks=True
    )
    result = await readiness(store, payload)
    assert not result["ready"]
    assert next(c for c in result["checks"] if c["name"] == "Background worker")["ready"] is False
    store.claim("preflight-test")
    assert (await readiness(store, payload))["ready"]
    payload.configuration.model = "ollama/missing:latest"
    assert not (await readiness(store, payload))["ready"]


async def test_node_guard_denies_network_host_files_and_child_processes(tmp_path):
    script = """
import './network_guard.mjs';
import fs from 'node:fs';
import net from 'node:net';
import http from 'node:http';
import { execFileSync } from 'node:child_process';
const blocked = [];
for (const call of [() => net.connect(9, '127.0.0.1'), () => http.get('http://127.0.0.1:9'), () => fetch('https://example.com'), () => fs.readFileSync(process.argv[1]), () => execFileSync('node', ['--version'])]) {
  try { await call(); blocked.push(false); } catch { blocked.push(true); }
}
console.log(JSON.stringify(blocked));
"""
    secret = tmp_path / "private.txt"
    secret.write_text("not-readable")
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}
    }
    process = await asyncio.create_subprocess_exec(
        shutil.which("node") or "node",
        "--permission",
        f"--allow-fs-read={RUNTIME}",
        "--input-type=module",
        "-e",
        script,
        str(secret),
        cwd=RUNTIME,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    raw, error = await asyncio.wait_for(process.communicate(), timeout=10)
    assert process.returncode == 0, error.decode()
    assert json.loads(raw) == [True] * 5


def test_preflight_requires_authentication(client):
    assert (
        client.post(
            "/api/v1/workspace/preflight", json={"configuration": {"title": "secret"}}
        ).status_code
        == 401
    )
