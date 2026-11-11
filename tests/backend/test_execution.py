import asyncio
import time

import httpx
import pytest
from rilo.catalog import SOURCES, TASKS
from rilo.engine import InfrastructureError, bounded_json
from rilo.evaluation import compare, grade
from rilo.schemas import AgentOutput, ExperimentCreate
from rilo.storage import Store
from rilo.worker import execute_run, worker


async def test_full_fixture_matrix_is_executed_and_traced(store):
    spec = ExperimentCreate(
        name="Full matrix",
        agent_ids=["scout", "relay"],
        task_ids=[task["id"] for task in TASKS],
        scenario_ids=["normal", "search_timeout", "model_outage", "prompt_injection"],
        repetitions=3,
    )
    experiment = store.create_experiment(spec)
    await worker(store, once=True)
    actual = store.experiment(experiment["id"])
    assert actual["state"] == "completed"
    assert actual["progress"] == {"completed": 120, "total": 120}
    assert actual["summary"]["infrastructure_errors"] == 0
    relay = next(item for item in actual["agent_metrics"] if item["agent_id"] == "relay")
    scout = next(item for item in actual["agent_metrics"] if item["agent_id"] == "scout")
    assert relay["passed"] == 60
    assert scout["failed"] > 0
    for result in actual["runs"]:
        run = store.run(result["id"])
        assert run["model_calls"] == 0
        assert run["input_tokens"] is None and run["tokens_provenance"] == "not_applicable"
        assert run["api_cost_usd"] == 0 and run["cost_provenance"] == "not_applicable"
        assert [event["sequence"] for event in run["events"]] == list(
            range(1, len(run["events"]) + 1)
        )
        assert run["steps"] == sum(event["type"] == "step" for event in run["events"])
        assert run["observation_coverage"] == "model_tool_boundaries"
        if run["scenario_id"] != "normal":
            assert run["scenario_activated"] is True
            assert any(event["type"] == "fault_injected" for event in run["events"])


async def test_tool_budget_failure_is_not_an_infrastructure_error(store):
    spec = ExperimentCreate(
        name="Bounded",
        agent_ids=["relay"],
        task_ids=["multi_step"],
        scenario_ids=["normal"],
        repetitions=1,
        limits={"max_tool_calls": 1},
    )
    experiment = store.create_experiment(spec)
    await worker(store, once=True)
    result = store.run(store.experiment(experiment["id"])["runs"][0]["id"])
    assert result["outcome"] == "limit_reached"
    assert result["assessment_status"] == "fail"
    assert result["tool_calls"] == 1


async def test_cancellation_preserves_partial_trace(store):
    spec = ExperimentCreate(
        name="Cancel",
        agent_ids=["relay"],
        task_ids=["multi_step"],
        scenario_ids=["normal"],
        repetitions=1,
    )
    experiment = store.create_experiment(spec)
    run = experiment["runs"][0]
    handle = asyncio.create_task(execute_run(store, run, spec, experiment["manifest"]))
    await asyncio.sleep(0.04)
    store.cancel(experiment["id"])
    await handle
    recorded = store.run(run["id"])
    assert recorded["outcome"] == "cancelled"
    assert recorded["events"]
    assert recorded["assessment_status"] == "inconclusive"


def test_restart_recovery_single_worker_claim_and_measured_usage(store, config, payload):
    experiment = store.create_experiment(ExperimentCreate.model_validate(payload))
    assert store.claim("worker-one") == experiment["id"]
    assert store.claim("worker-two") is None
    run_id = experiment["runs"][0]["id"]
    store.update_run(
        run_id,
        {
            "outcome": "running",
            "input_tokens": 123,
            "output_tokens": 45,
            "tokens_provenance": "reported",
        },
    )
    restarted = Store(config)
    assert restarted.run(run_id)["input_tokens"] == 123
    assert restarted.run(run_id)["output_tokens"] == 45
    with restarted.transaction() as connection:
        connection.execute(
            "UPDATE experiments SET lease_until=? WHERE id=?", (time.time() - 1, experiment["id"])
        )
    assert restarted.recover() == 1
    result = restarted.experiment(experiment["id"])
    assert result["state"] == "partial"
    assert result["summary"]["infrastructure_errors"] == len(result["runs"])
    assert restarted.run(run_id)["input_tokens"] == 123


@pytest.mark.parametrize("body", [[], "not an object", 3])
async def test_external_json_shape_is_validated(body):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(InfrastructureError):
            await bounded_json(client, "GET", "http://127.0.0.1:9000")


async def test_external_redirect_and_response_size_are_rejected():
    for response in (
        httpx.Response(302, headers={"Location": "http://attacker.example"}),
        httpx.Response(200, content=b"x" * 256001),
    ):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request, response=response: response)
        ) as client:
            with pytest.raises(InfrastructureError):
                await bounded_json(client, "GET", "http://127.0.0.1:9000")


def test_evidence_grading_rejects_hallucinated_support_and_stale_claims():
    task = TASKS[0]
    unsupported = AgentOutput.model_validate(
        {
            "summary": "Briefing",
            "facts": [
                {"text": "Aurora Labs raised ten million dollars.", "source_ids": ["aurora_launch"]}
            ],
        }
    )
    assert grade(task, unsupported, SOURCES, "controlled", False, "normal")["status"] == "fail"
    unknown = AgentOutput.model_validate(
        {
            "summary": "Briefing",
            "facts": [{"text": "Unsupported", "source_ids": ["does_not_exist"]}],
        }
    )
    assert grade(task, unknown, SOURCES, "controlled", False, "normal")["status"] == "fail"
    stale = AgentOutput.model_validate(
        {
            "summary": "Briefing",
            "facts": [{"text": SOURCES[2]["claims"][0], "source_ids": ["aurora_old"]}],
        }
    )
    checks = grade(task, stale, SOURCES, "controlled", False, "normal")["checks"]
    assert not next(
        check for check in checks if check["name"] == "Evidence within reference window"
    )["passed"]


def test_live_evidence_checks_cannot_claim_full_correctness():
    output = AgentOutput.model_validate(
        {
            "summary": "Some current information",
            "facts": [{"text": SOURCES[0]["claims"][0], "source_ids": ["aurora_launch"]}],
        }
    )
    assert grade(TASKS[0], output, SOURCES, "live", False, "normal")["status"] == "inconclusive"


async def test_comparison_gate_requires_full_compatible_repeated_evidence(store, payload):
    first = store.create_experiment(ExperimentCreate.model_validate(payload))
    await worker(store, once=True)
    second = store.create_experiment(
        ExperimentCreate.model_validate({**payload, "name": "Candidate"})
    )
    await worker(store, once=True)
    baseline, candidate = store.experiment(first["id"]), store.experiment(second["id"])
    assert compare(baseline, candidate)["gate"]["status"] == "pass"
    candidate["manifest"]["evidence_hash"] = "changed"
    assert compare(baseline, candidate)["gate"]["status"] == "inconclusive"
    candidate["manifest"] = baseline["manifest"]
    candidate["summary"]["inconclusive"] = 1
    assert compare(baseline, candidate)["gate"]["status"] == "inconclusive"


def test_http_adapter_cannot_claim_injection_capability(store):
    store.add_item(
        "agent",
        {
            "id": "http_test",
            "name": "External",
            "framework": "HTTP",
            "kind": "http",
            "version": "1",
            "config": {"endpoint": "http://127.0.0.1:9999/run"},
            "capabilities": ["final_output"],
        },
    )
    spec = ExperimentCreate(
        name="Opaque",
        agent_ids=["http_test"],
        task_ids=["company_brief"],
        scenario_ids=["search_timeout"],
        engine="bifrost",
    )
    with pytest.raises(ValueError, match="unsupported"):
        store.create_experiment(spec)
    with pytest.raises(ValueError, match="live search coverage is unsupported"):
        store.create_experiment(
            spec.model_copy(update={"mode": "live", "scenario_ids": ["normal"]})
        )


def test_global_live_credit_reservations_are_enforced(store):
    store.config.tavily_credit_limit = 10
    spec = ExperimentCreate(
        name="Credits",
        agent_ids=["scout"],
        task_ids=["company_brief"],
        scenario_ids=["normal"],
        repetitions=1,
        engine="bifrost",
        mode="live",
    )
    store.create_experiment(spec)
    with pytest.raises(ValueError, match="credit allowance"):
        store.create_experiment(spec)
