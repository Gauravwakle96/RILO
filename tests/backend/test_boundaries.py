import json

import pytest
from pydantic import ValidationError
from rilo.api import create_app
from rilo.catalog import SOURCES, TASKS
from rilo.config import allowed_origins, redact
from rilo.engine import InfrastructureError, RunContext, reported_usage, tavily_evidence
from rilo.evaluation import grade
from rilo.schemas import AgentOutput, ExperimentCreate, TaskCreate
from rilo.worker import execute_run
from starlette.testclient import TestClient


@pytest.mark.parametrize(
    "usage",
    [
        None,
        [],
        {},
        {"prompt_tokens": True, "completion_tokens": 9},
        {"prompt_tokens": 12, "completion_tokens": False},
        {"prompt_tokens": -1, "completion_tokens": 9},
        {"prompt_tokens": 12, "completion_tokens": -9},
        {"prompt_tokens": "12", "completion_tokens": 9},
    ],
)
def test_untrusted_usage_cannot_establish_observed_token_totals(usage):
    assert reported_usage(usage) is None


@pytest.mark.parametrize("first_missing", ["usage", "failed_dispatch"])
async def test_later_measured_response_does_not_hide_an_unmeasured_dispatch(
    store, monkeypatch, first_missing
):
    spec = ExperimentCreate(
        name="Usage completeness",
        agent_ids=["scout"],
        task_ids=["company_brief"],
        scenario_ids=["normal"],
        repetitions=1,
        engine="bifrost",
    )
    experiment = store.create_experiment(spec)
    context = RunContext(store, experiment["runs"][0], spec, TASKS[0], SOURCES)
    calls = 0

    async def response(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1 and first_missing == "failed_dispatch":
            raise InfrastructureError("Model service did not report a response.")
        return {
            "model": spec.model,
            "choices": [{"message": {"content": json.dumps({"summary": "Brief", "facts": []})}}],
            **({"usage": {"prompt_tokens": 125, "completion_tokens": 12}} if calls > 1 else {}),
        }

    monkeypatch.setattr("rilo.engine.bounded_json", response)
    if first_missing == "failed_dispatch":
        with pytest.raises(InfrastructureError):
            await context.synthesize([], robust=False)
    else:
        await context.synthesize([], robust=False)
    await context.synthesize([], robust=False)
    stats = context.stats()
    assert stats["model_calls"] == 2
    assert stats["input_tokens"] is None and stats["output_tokens"] is None
    assert stats["tokens_provenance"] == "unknown"
    assert store.run(context.run["id"])["input_tokens"] is None


async def test_valid_reported_usage_is_preserved_without_invented_model_fees(store, monkeypatch):
    spec = ExperimentCreate(
        name="Observed response",
        agent_ids=["scout"],
        task_ids=["company_brief"],
        scenario_ids=["normal"],
        repetitions=1,
        engine="bifrost",
    )
    experiment = store.create_experiment(spec)
    context = RunContext(store, experiment["runs"][0], spec, TASKS[0], SOURCES)

    async def response(*args, **kwargs):
        assert kwargs["headers"]["x-bf-cache-no-store"] == "true"
        return {
            "model": spec.model,
            "choices": [{"message": {"content": '{"summary":"Brief","facts":[]}'}}],
            "usage": {"prompt_tokens": 125, "completion_tokens": 12},
        }

    monkeypatch.setattr("rilo.engine.bounded_json", response)
    await context.synthesize([], robust=False)
    stats = store.run(context.run["id"])
    assert stats["input_tokens"] == 125 and stats["output_tokens"] == 12
    assert stats["tokens_provenance"] == "reported"
    assert stats["api_cost_usd"] is None and stats["cost_provenance"] == "unknown"


@pytest.mark.parametrize("failure", [False, True])
async def test_http_adapter_keeps_internal_metrics_unknown_after_success_or_failure(
    store, monkeypatch, failure
):
    store.add_item(
        "agent",
        {
            "id": "http_boundary",
            "name": "Boundary adapter",
            "framework": "HTTP",
            "kind": "http",
            "version": "1",
            "config": {"endpoint": "http://127.0.0.1:9999/run"},
            "capabilities": ["final_output"],
        },
    )
    spec = ExperimentCreate(
        name="Opaque metrics",
        agent_ids=["http_boundary"],
        task_ids=["company_brief"],
        scenario_ids=["normal"],
        repetitions=1,
        engine="bifrost",
    )
    experiment = store.create_experiment(spec)

    async def response(*args, **kwargs):
        if failure:
            raise InfrastructureError("Adapter could not be reached.")
        return {"output": {"summary": "Brief", "facts": []}}

    monkeypatch.setattr("rilo.agents.bounded_json", response)
    await execute_run(store, experiment["runs"][0], spec, experiment["manifest"])
    actual = store.run(experiment["runs"][0]["id"])
    assert actual["outcome"] == ("infrastructure_error" if failure else "completed")
    assert all(
        actual[field] is None
        for field in (
            "steps",
            "model_calls",
            "tool_calls",
            "input_tokens",
            "output_tokens",
            "api_cost_usd",
        )
    )
    assert actual["tokens_provenance"] == actual["cost_provenance"] == "unknown"
    assert actual["observation_coverage"] == "final_output_only"


@pytest.mark.parametrize(
    "result",
    [
        {},
        {"results": None},
        {"results": "unexpected"},
        {"results": [None]},
        {"results": [{"title": 12, "url": "https://example.com", "content": "Evidence"}]},
        {"results": [{"title": "Title", "url": "javascript:alert(1)", "content": "Evidence"}]},
        {
            "results": [
                {"title": "Title", "url": "https://user:secret@example.com", "content": "Evidence"}
            ]
        },
        {"results": [{"title": "Title", "url": "https://example.com", "content": {}}]},
        {
            "results": [
                {
                    "title": "Title",
                    "url": "https://example.com",
                    "content": "Evidence",
                    "published_date": [],
                }
            ]
        },
    ],
)
def test_tavily_response_schema_and_urls_are_validated(result):
    with pytest.raises(InfrastructureError):
        tavily_evidence(result, 1)


def test_tavily_valid_results_retain_provenance_and_empty_results_are_allowed():
    result = tavily_evidence(
        {
            "results": [
                {
                    "title": "Company launch",
                    "url": "https://example.com/update",
                    "content": "Evidence",
                    "published_date": None,
                }
            ]
        },
        2,
    )
    assert result[0]["id"] == "live_2_0"
    assert result[0]["content"] == "Evidence"
    assert result[0]["published_at"] is None
    assert tavily_evidence({"results": []}, 1) == []


async def test_live_search_calls_only_the_fixed_tavily_endpoint_and_records_usage(
    store, monkeypatch
):
    store.config.tavily_key = "tvly-private-test-key"
    spec = ExperimentCreate(
        name="Live boundary",
        agent_ids=["scout"],
        task_ids=["company_brief"],
        scenario_ids=["normal"],
        repetitions=1,
        engine="bifrost",
        mode="live",
    )
    experiment = store.create_experiment(spec)
    context = RunContext(store, experiment["runs"][0], spec, TASKS[0], SOURCES)

    async def response(client, method, url, **kwargs):
        assert method == "POST" and url == "https://api.tavily.com/search"
        assert kwargs["headers"]["Authorization"] == "Bearer " + store.config.tavily_key
        assert kwargs["json"]["search_depth"] == "basic"
        assert kwargs["json"]["max_results"] == 5
        assert kwargs["json"]["include_usage"] is True
        assert kwargs["json"]["end_date"] == TASKS[0]["reference_time"][:10]
        return {
            "results": [
                {
                    "title": "Launch",
                    "url": "https://example.com/launch",
                    "content": "New product launched.",
                }
            ],
            "usage": {"credits": 1},
            "request_id": "retrieval-123",
        }

    monkeypatch.setattr("rilo.engine.bounded_json", response)
    evidence = await context.search("Aurora Labs launch")
    assert evidence[0]["id"] == "live_1_0"
    actual = store.run(context.run["id"])
    assert actual["tool_calls"] == 1
    usage = next(event for event in actual["events"] if event["type"] == "usage")
    assert usage["data"]["credit_usage"] == {"credits": 1}
    assert store.config.tavily_key not in json.dumps(actual)


def test_gateway_settings_separate_health_reachability_from_inference(client, config, monkeypatch):
    async def response(_client, method, url):
        assert method == "GET"
        return {"status": "ok"} if url.endswith("/health") else {"models": []}

    config.bifrost_key = "vk-private-test-key"
    monkeypatch.setattr("rilo.api.bounded_json", response)
    client.get("/api/v1/session")
    result = client.get("/api/v1/settings").json()
    gateway = result["integrations"]["bifrost"]
    assert gateway["status"] == "reachable" and gateway["credential_configured"] is True
    assert "authentication" in gateway["detail"]
    assert config.bifrost_key not in json.dumps(result)


def test_missing_custom_reference_rubric_cannot_pass_empty_content():
    task = {**TASKS[0], "required_facts": [], "rubric": "custom"}
    output = AgentOutput(summary="Brief", facts=[])
    assert grade(task, output, SOURCES, "controlled", False, "normal")["status"] == "inconclusive"
    with pytest.raises(ValidationError):
        TaskCreate(
            title="Empty reference",
            prompt="Research this organization.",
            reference_time=TASKS[0]["reference_time"],
            required_facts=[],
            source_ids=["aurora_launch"],
        )


def test_grading_exposes_unassessed_summary_grounding_without_false_fact_coverage():
    output = AgentOutput(
        summary="Aurora Labs has a secret funding round that the evidence does not establish.",
        facts=[
            {"text": SOURCES[0]["claims"][0], "source_ids": ["aurora_launch"]},
            {"text": SOURCES[1]["claims"][0], "source_ids": ["aurora_hire"]},
        ],
    )
    result = grade(TASKS[0], output, SOURCES, "controlled", False, "normal")
    assert result["coverage"]["summary_grounding"] == "unassessed"
    assert any("summary grounding is unassessed" in text for text in result["limitations"])


def test_configured_custom_server_port_is_allowed_and_invalid_ports_are_rejected(config):
    config.port = 9099
    with TestClient(create_app(config)) as client:
        response = client.get("/api/v1/session", headers={"Origin": "http://127.0.0.1:9099"})
        assert response.status_code == 200
    for port in (80, -1, 65536, True):
        with pytest.raises(ValueError):
            allowed_origins(port)


def test_early_deny_and_unexpected_errors_have_safe_headers(client, monkeypatch):
    denied = client.get("/api/v1/agents")
    assert denied.status_code == 401
    assert denied.headers["cache-control"] == "no-store"
    assert denied.headers["x-content-type-options"] == "nosniff"
    assert denied.headers["x-request-id"] == denied.json()["error"]["request_id"]
    client.get("/api/v1/session")

    def fail_catalog(*args, **kwargs):
        raise RuntimeError("private-secret-value")

    monkeypatch.setattr(client.app.state.store, "catalog", fail_catalog)
    error = client.get("/api/v1/agents")
    assert error.status_code == 500
    assert error.json()["error"]["code"] == "internal_error"
    assert "private-secret-value" not in error.text
    assert error.headers["cache-control"] == "no-store"


def test_json_report_retains_every_attempt_in_a_large_matrix(client):
    csrf = client.get("/api/v1/session").json()["csrf_token"]
    spec = {
        "name": "Full export",
        "agent_ids": ["scout", "relay"],
        "task_ids": [task["id"] for task in TASKS],
        "scenario_ids": ["normal", "search_timeout", "model_outage", "prompt_injection"],
        "repetitions": 3,
    }
    created = client.post("/api/v1/experiments", json=spec, headers={"X-CSRF-Token": csrf}).json()
    report = client.get(f"/api/v1/experiments/{created['id']}/report").json()
    assert len(report["runs"]) == report["progress"]["total"] == 120
    assert {run["id"] for run in report["runs"]} == {run["id"] for run in created["runs"]}
    assert len(redact(list(range(200)))) == 200
