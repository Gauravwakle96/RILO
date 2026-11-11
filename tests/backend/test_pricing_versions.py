import copy
import json
import math

import pytest
from rilo.catalog import SOURCES, TASKS, digest
from rilo.config import Config
from rilo.engine import InfrastructureError, RunContext
from rilo.evaluation import compare
from rilo.pricing import parse_model_pricing_json, response_matches_requested_model
from rilo.schemas import ExperimentCreate
from rilo.worker import execute_run, worker

MODEL = "ollama/qwen2.5-coder:7b"
ZERO = {"input_usd_per_million": 0, "output_usd_per_million": 0}


@pytest.mark.parametrize(
    "value",
    [
        "",
        "[]",
        "null",
        '{"bad model":{"input_usd_per_million":0,"output_usd_per_million":0}}',
        json.dumps({MODEL: {"input_usd_per_million": -1, "output_usd_per_million": 0}}),
        json.dumps({MODEL: {"input_usd_per_million": True, "output_usd_per_million": 0}}),
        json.dumps({MODEL: {"input_usd_per_million": "0", "output_usd_per_million": 0}}),
        json.dumps({MODEL: {"input_usd_per_million": math.nan, "output_usd_per_million": 0}}),
        json.dumps({MODEL: {"input_usd_per_million": 0, "output_usd_per_million": math.inf}}),
        json.dumps({MODEL: {"input_usd_per_million": 0}}),
        json.dumps({MODEL: {**ZERO, "surprise": 0}}),
    ],
)
def test_malformed_or_nonfinite_model_pricing_is_rejected(value):
    with pytest.raises(ValueError):
        parse_model_pricing_json(value)


def test_environment_pricing_is_explicit_and_invalid_configuration_fails(config, monkeypatch):
    monkeypatch.setenv("RILO_DATA_DIR", str(config.data_dir))
    monkeypatch.setenv("RILO_MODEL_PRICING_JSON", json.dumps({MODEL: ZERO}))
    loaded = Config.load(config.root)
    assert loaded.model_pricing[MODEL] == ZERO
    monkeypatch.setenv(
        "RILO_MODEL_PRICING_JSON", json.dumps({MODEL: {**ZERO, "input_usd_per_million": -1}})
    )
    with pytest.raises(ValueError, match="nonnegative"):
        Config.load(config.root)


def gateway_output(model: str, provider: str | None = None, usage=True) -> dict:
    result = {
        "model": model,
        "choices": [{"message": {"content": '{"summary":"Brief","facts":[]}'}}],
    }
    if usage:
        result["usage"] = {"prompt_tokens": 200, "completion_tokens": 50}
    if provider:
        result["extra_fields"] = {"provider": provider}
    return result


@pytest.mark.parametrize(
    "model,pricing,actual,provider,expected",
    [
        (MODEL, {MODEL: ZERO}, "qwen2.5-coder:7b", "ollama", 0),
        (MODEL, {}, "qwen2.5-coder:7b", "ollama", None),
        (
            "openai/cloud-model",
            {"openai/cloud-model": {"input_usd_per_million": 2, "output_usd_per_million": 8}},
            "cloud-model",
            "openai",
            0.0008,
        ),
        (MODEL, {MODEL: ZERO}, "qwen2.5-coder:7b", "different-provider", None),
        (MODEL, {MODEL: ZERO}, "qwen2.5-coder:7b", None, None),
        (MODEL, {MODEL: ZERO}, "ollama/different-model", "ollama", None),
        (MODEL, {MODEL: ZERO}, MODEL, None, 0),
    ],
)
async def test_pricing_requires_configured_rates_complete_usage_and_model_identity(
    store, monkeypatch, model, pricing, actual, provider, expected
):
    store.config.model_pricing = pricing
    spec = ExperimentCreate(
        name="Fee basis",
        agent_ids=["scout"],
        task_ids=["company_brief"],
        scenario_ids=["normal"],
        repetitions=1,
        engine="bifrost",
        model=model,
    )
    experiment = store.create_experiment(spec)
    basis = experiment["manifest"]["price_basis"]
    context = RunContext(store, experiment["runs"][0], spec, TASKS[0], SOURCES, price_basis=basis)

    async def response(*args, **kwargs):
        return gateway_output(actual, provider)

    monkeypatch.setattr("rilo.engine.bounded_json", response)
    await context.synthesize([], robust=False)
    recorded = store.run(context.run["id"])
    assert recorded["input_tokens"] == 200 and recorded["tokens_provenance"] == "reported"
    assert recorded["api_cost_usd"] == expected
    assert recorded["cost_provenance"] == ("estimated" if expected is not None else "unknown")
    assert recorded["cost_basis"] == basis


@pytest.mark.parametrize("first_result", ["missing_usage", "failed", "fallback"])
async def test_later_priced_response_cannot_hide_missing_usage_or_prior_fallback(
    store, monkeypatch, first_result
):
    store.config.model_pricing = {MODEL: ZERO}
    spec = ExperimentCreate(
        name="Partial fees",
        agent_ids=["scout"],
        task_ids=["company_brief"],
        scenario_ids=["normal"],
        repetitions=1,
        engine="bifrost",
    )
    experiment = store.create_experiment(spec)
    context = RunContext(
        store,
        experiment["runs"][0],
        spec,
        TASKS[0],
        SOURCES,
        price_basis=experiment["manifest"]["price_basis"],
    )
    calls = 0

    async def response(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1 and first_result == "failed":
            raise InfrastructureError("No gateway response.")
        return gateway_output(
            "other" if calls == 1 and first_result == "fallback" else "qwen2.5-coder:7b",
            "ollama",
            usage=not (calls == 1 and first_result == "missing_usage"),
        )

    monkeypatch.setattr("rilo.engine.bounded_json", response)
    if first_result == "failed":
        with pytest.raises(InfrastructureError):
            await context.synthesize([], robust=False)
    else:
        await context.synthesize([], robust=False)
    await context.synthesize([], robust=False)
    assert context.stats()["api_cost_usd"] is None
    assert context.stats()["cost_provenance"] == "unknown"


async def test_experiment_pinned_prices_survive_later_configuration_changes(store, monkeypatch):
    store.config.model_pricing = {MODEL: {"input_usd_per_million": 2, "output_usd_per_million": 8}}
    spec = ExperimentCreate(
        name="Pinned fees",
        agent_ids=["scout"],
        task_ids=["company_brief"],
        scenario_ids=["normal"],
        repetitions=1,
        engine="bifrost",
    )
    experiment = store.create_experiment(spec)
    store.config.model_pricing = {MODEL: ZERO}

    async def response(*args, **kwargs):
        return gateway_output("qwen2.5-coder:7b", "ollama")

    monkeypatch.setattr("rilo.engine.bounded_json", response)
    await execute_run(store, experiment["runs"][0], spec, experiment["manifest"])
    result = store.run(experiment["runs"][0]["id"])
    assert result["api_cost_usd"] == 0.0008 and result["cost_provenance"] == "estimated"
    assert result["cost_basis"]["rates"]["input_usd_per_million"] == 2


def test_contradictory_gateway_routing_cannot_use_requested_model_price():
    response = gateway_output("qwen2.5-coder:7b", "ollama")
    response["extra_fields"]["routing_info"] = {"provider": "openai", "model": "other"}
    assert response_matches_requested_model(response, MODEL) is False
    response["extra_fields"]["routing_info"] = {
        "provider": "ollama",
        "model": "qwen2.5-coder:7b",
        "requested_provider": "ollama",
        "requested_model": "qwen2.5-coder:7b",
    }
    assert response_matches_requested_model(response, MODEL) is True


def test_builtin_implementation_and_separate_grader_runtime_hashes_are_pinned(store, payload):
    manifest = store.create_experiment(ExperimentCreate.model_validate(payload))["manifest"]
    assert all(
        len(manifest[field]) == 64
        for field in ("agent_runtime_hash", "grader_hash", "runtime_hash")
    )
    assert all(
        agent["implementation_hash"] == manifest["agent_runtime_hash"]
        for agent in manifest["agent_versions"]
    )
    assert "langgraph" in manifest["runtime_dependencies"]


async def test_worker_cannot_execute_different_pinned_implementation(store, payload):
    spec = ExperimentCreate.model_validate(payload)
    experiment = store.create_experiment(spec)
    manifest = copy.deepcopy(experiment["manifest"])
    manifest["runtime_hash"] = "different"
    await execute_run(store, experiment["runs"][0], spec, manifest)
    result = store.run(experiment["runs"][0]["id"])
    assert result["outcome"] == "infrastructure_error"
    assert result["assessment_status"] == "inconclusive"
    assert not any(event["type"] in {"model_request", "tool_request"} for event in result["events"])


async def test_agent_changes_need_declaration_but_grader_runtime_and_price_remain_strict(store):
    spec = ExperimentCreate(
        name="Strict protocol",
        agent_ids=["relay"],
        task_ids=["company_brief"],
        scenario_ids=["normal"],
        repetitions=3,
    )
    experiment = store.create_experiment(spec)
    await worker(store, once=True)
    baseline = store.experiment(experiment["id"])
    candidate = copy.deepcopy(baseline)
    candidate["manifest"]["agent_versions"][0]["version"] = "2.0.0"
    candidate["manifest"]["agent_hash"] = digest(candidate["manifest"]["agent_versions"])
    candidate["manifest"]["agent_runtime_hash"] = "changed-agent-implementation"
    assert compare(baseline, candidate)["gate"]["status"] == "inconclusive"
    result = compare(baseline, candidate, allow_agent_changes=True)
    assert result["gate"]["status"] == "pass"
    assert {item["field"] for item in result["declared_changes"]} == {
        "agent_hash",
        "agent_runtime_hash",
    }
    for field in ("grader_hash", "runtime_hash", "price_basis"):
        incompatible = copy.deepcopy(candidate)
        incompatible["manifest"][field] = "changed"
        assert (
            compare(baseline, incompatible, allow_agent_changes=True)["gate"]["status"]
            == "inconclusive"
        )
    incompatible = copy.deepcopy(candidate)
    incompatible["manifest"]["agent_versions"][0]["framework"] = "Different framework"
    assert (
        compare(baseline, incompatible, allow_agent_changes=True)["gate"]["status"]
        == "inconclusive"
    )


def test_http_version_registration_preserves_old_manifests_and_rejects_reused_versions(client):
    csrf = client.get("/api/v1/session").json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    agent = client.post(
        "/api/v1/agents",
        headers=headers,
        json={"name": "Developer agent", "endpoint": "http://127.0.0.1:9001/run", "version": "v1"},
    ).json()
    spec = ExperimentCreate(
        name="HTTP v1",
        agent_ids=[agent["id"]],
        task_ids=["company_brief"],
        scenario_ids=["normal"],
        repetitions=1,
        engine="bifrost",
    )
    store = client.app.state.store
    original = store.create_experiment(spec)
    update = client.post(
        f"/api/v1/agents/{agent['id']}/versions",
        headers=headers,
        json={"version": "v2", "endpoint": "http://127.0.0.1:9002/run"},
    )
    assert update.status_code == 201
    assert store.item("agent", agent["id"])["version"] == "v2"
    previous = store.experiment(original["id"])["manifest"]["agent_versions"][0]
    assert previous["version"] == "v1" and previous["config"]["endpoint"].endswith(":9001/run")
    history = client.get(f"/api/v1/agents/{agent['id']}/versions").json()
    assert [item["version"] for item in history] == ["v1", "v2"]
    live = client.post(
        "/api/v1/experiments",
        headers=headers,
        json={**spec.model_dump(), "mode": "live"},
    )
    assert live.status_code == 409 and "live search coverage is unsupported" in live.text
    assert (
        client.post(
            f"/api/v1/agents/{agent['id']}/versions",
            headers=headers,
            json={"version": "v1", "endpoint": "http://127.0.0.1:9001/run"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/agents/relay/versions",
            headers=headers,
            json={"version": "v2", "endpoint": "http://127.0.0.1:9002/run"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/agents/{agent['id']}/versions",
            headers=headers,
            json={"version": "v3", "endpoint": "https://attacker.example:9000/run"},
        ).status_code
        == 422
    )
