"""Independent durable worker: uv run python -m rilo.worker."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import uuid

from pydantic import ValidationError

from .agents import http_agent, relay, scout
from .config import Config
from .engine import (
    CancelledRun,
    InfrastructureError,
    InjectedFault,
    InvalidOutput,
    LimitReached,
    RunContext,
)
from .evaluation import grade
from .provenance import HASH_FIELDS, loaded_identity
from .schemas import ExperimentCreate
from .storage import Store


async def execute_run(store: Store, run: dict, spec: ExperimentCreate, manifest: dict) -> None:
    task = next(item for item in manifest["task_versions"] if item["id"] == run["task_id"])
    agent = next(item for item in manifest["agent_versions"] if item["id"] == run["agent_id"])
    context = RunContext(
        store,
        run,
        spec,
        task,
        manifest["sources"],
        manifest["bifrost_url"],
        manifest.get("price_basis"),
    )
    context.opaque = agent["kind"] == "http"
    store.update_run(run["id"], {"outcome": "running"})
    context.event(
        "run_start",
        "Attempt started",
        {
            "agent": agent["name"],
            "framework": agent["framework"],
            "engine": spec.engine,
            "mode": spec.mode,
            "scenario": run["scenario_id"],
            "repetition": run["repetition"],
        },
    )
    try:
        identity = loaded_identity()
        changed = [field for field in HASH_FIELDS if manifest.get(field) != identity[field]]
        if changed:
            raise InfrastructureError(
                "Loaded worker implementation does not match the pinned manifest: "
                + ", ".join(changed)
            )

        async def invocation():
            if manifest.get("workspace"):
                from .workspace_engine import invoke

                return await invoke(context, manifest, agent)
            if agent["kind"] == "http":
                return await http_agent(context, agent)
            return await (relay(context) if agent["kind"] == "graph" else scout(context))

        task_handle = asyncio.create_task(invocation())
        try:
            deadline = asyncio.get_running_loop().time() + spec.limits.timeout_seconds
            while not task_handle.done():
                context.check()
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError
                await asyncio.wait({task_handle}, timeout=min(0.25, remaining))
            output = await task_handle
        finally:
            if not task_handle.done():
                task_handle.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task_handle
        if manifest.get("workspace"):
            from .promptfoo_checks import grade_output
            from .workspace_engine import assess

            assessment = assess(output, manifest)
            # Finish inference timing before the independent evaluator runs.
            observed_stats = context.stats()
            store.update_run(run["id"], {**observed_stats, "output": output.model_dump()})
            grading = asyncio.create_task(
                grade_output(output.model_dump(), manifest["workspace"].get("checks", []))
            )
            try:
                while not grading.done():
                    if store.cancelled(run["experiment_id"]):
                        raise CancelledRun
                    await asyncio.wait({grading}, timeout=0.25)
                task_checks = await grading
            finally:
                if not grading.done():
                    grading.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await grading
            assessment["task_checks"] = task_checks
            assessment["status"] = (
                task_checks["status"]
                if task_checks["status"] in {"pass", "fail"}
                else "inconclusive"
            )
            assessment["checks"].extend(
                {"name": row["name"], "passed": row["passed"], "evidence": row["reason"]}
                for row in task_checks["checks"]
            )
            if task_checks["status"] == "error":
                assessment["checks"].append(
                    {"name": "Task evaluator", "passed": None, "evidence": task_checks["reason"]}
                )
            context.event("task_checks", "Promptfoo task checks recorded", task_checks)
        else:
            assessment = grade(
                task,
                output,
                context.evidence if agent["kind"] != "http" else manifest["sources"],
                spec.mode,
                context.activated,
                run["scenario_id"],
            )
            observed_stats = context.stats()
        context.event("assessment", "Evidence checks completed", assessment)
        store.update_run(
            run["id"],
            {
                **observed_stats,
                "outcome": "completed",
                "output": output.model_dump(),
                "assessment": assessment,
                "assessment_status": assessment["status"],
            },
        )
        if agent["kind"] == "http":
            store.update_run(
                run["id"],
                {
                    "tool_calls": None,
                    "model_calls": None,
                    "input_tokens": None,
                    "output_tokens": None,
                    "api_cost_usd": None,
                    "tokens_provenance": "unknown",
                    "cost_provenance": "unknown",
                    "observation_coverage": "final_output_only",
                },
            )
    except (InjectedFault, InvalidOutput, ValidationError) as exc:
        assessment = {
            "status": "fail",
            "checks": [
                {
                    "name": "Task completion",
                    "passed": False,
                    "evidence": "The agent did not recover from the controlled fault."
                    if isinstance(exc, InjectedFault)
                    else "The final output did not satisfy the required JSON schema.",
                }
            ],
        }
        store.update_run(
            run["id"],
            {
                **context.stats(),
                "outcome": "agent_error",
                "assessment_status": "fail",
                "assessment": assessment,
            },
        )
        context.event(
            "agent_error",
            "Agent could not complete task",
            {"reason": assessment["checks"][0]["evidence"]},
        )
    except LimitReached as exc:
        assessment = {
            "status": "fail",
            "checks": [{"name": "Resource limit", "passed": False, "evidence": str(exc)}],
        }
        store.update_run(
            run["id"],
            {
                **context.stats(),
                "outcome": "limit_reached",
                "assessment_status": "fail",
                "assessment": assessment,
            },
        )
    except TimeoutError:
        assessment = {
            "status": "fail",
            "checks": [
                {
                    "name": "Task timeout",
                    "passed": False,
                    "evidence": f"Attempt exceeded {spec.limits.timeout_seconds} seconds.",
                }
            ],
        }
        store.update_run(
            run["id"],
            {
                **context.stats(),
                "outcome": "timed_out",
                "assessment_status": "fail",
                "assessment": assessment,
            },
        )
        context.event("limit_reached", "Attempt timeout reached")
    except CancelledRun:
        store.update_run(
            run["id"],
            {
                **context.stats(),
                "outcome": "cancelled",
                "assessment_status": "inconclusive",
                "assessment": {
                    "status": "inconclusive",
                    "checks": [
                        {
                            "name": "Execution coverage",
                            "passed": False,
                            "evidence": "User cancelled before completion.",
                        }
                    ],
                },
            },
        )
        context.event("cancelled", "Attempt cancelled")
    except InfrastructureError as exc:
        store.update_run(
            run["id"],
            {
                **context.stats(),
                "outcome": "infrastructure_error",
                "assessment_status": "inconclusive",
                "assessment": {
                    "status": "inconclusive",
                    "checks": [
                        {"name": "Dependency availability", "passed": False, "evidence": str(exc)}
                    ],
                },
            },
        )
        context.event("infrastructure_error", "Dependency unavailable", {"reason": str(exc)})
    except Exception as exc:
        store.update_run(
            run["id"],
            {
                **context.stats(),
                "outcome": "infrastructure_error",
                "assessment_status": "inconclusive",
                "assessment": {
                    "status": "inconclusive",
                    "checks": [
                        {
                            "name": "Runner availability",
                            "passed": False,
                            "evidence": f"Unexpected runner failure ({type(exc).__name__}); no quality claim.",
                        }
                    ],
                },
            },
        )
        context.event(
            "infrastructure_error",
            "Runner could not complete attempt",
            {"error_type": type(exc).__name__, "diagnostic": str(exc)[:500]},
        )
    context.event("run_end", "Attempt recorded", context.stats())


async def run_experiment(store: Store, experiment_id: str, worker_id: str) -> None:
    experiment = store.experiment(experiment_id)
    spec = ExperimentCreate.model_validate(experiment["spec"])

    async def heartbeat():
        while True:
            store.heartbeat(worker_id, experiment_id)
            await asyncio.sleep(4)

    pulse = asyncio.create_task(heartbeat())
    try:
        if experiment["manifest"].get("workspace"):
            from .workspace_engine import prepare

            try:
                preparation = asyncio.create_task(prepare(store, experiment))
                try:
                    deadline = asyncio.get_running_loop().time() + 180
                    while not preparation.done():
                        if store.cancelled(experiment_id):
                            raise CancelledRun
                        if asyncio.get_running_loop().time() >= deadline:
                            raise TimeoutError
                        await asyncio.wait({preparation}, timeout=0.25)
                    experiment["manifest"] = await preparation
                finally:
                    if not preparation.done():
                        preparation.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await preparation
            except CancelledRun:
                store.finish_pending(experiment_id, "cancelled")
                store.finish_experiment(experiment_id, "cancelled")
                return
            except Exception as exc:
                reason = (
                    str(exc)
                    if isinstance(exc, (ValueError, InfrastructureError))
                    else f"Input preparation failed ({type(exc).__name__})."
                )
                for run in experiment["runs"]:
                    store.event(
                        run["id"],
                        "input_error",
                        "Could not prepare shared sources",
                        {"reason": reason},
                    )
                    store.update_run(
                        run["id"],
                        {
                            "outcome": "infrastructure_error",
                            "assessment_status": "inconclusive",
                            "assessment": {
                                "status": "inconclusive",
                                "checks": [
                                    {
                                        "name": "Input preparation",
                                        "passed": False,
                                        "evidence": reason,
                                    }
                                ],
                            },
                        },
                    )
                store.finish_experiment(experiment_id, "failed")
                return
        for run in experiment["runs"]:
            if store.cancelled(experiment_id):
                store.finish_pending(experiment_id, "cancelled")
                store.finish_experiment(experiment_id, "cancelled")
                return
            await execute_run(store, run, spec, experiment["manifest"])
        if experiment["manifest"].get("workspace"):
            from .promptfoo_checks import compare_runs
            from .reports import report_data
            from .semantic_review import review
            from .verification import compare_findings
            from .workspace_store import WorkspaceStore

            if experiment["manifest"]["workspace"].get("semantic_review"):
                try:
                    review_task = asyncio.create_task(
                        review(store, report_data(store, experiment_id))
                    )
                    try:
                        while not review_task.done():
                            if store.cancelled(experiment_id):
                                raise CancelledRun
                            await asyncio.wait({review_task}, timeout=0.25)
                        reviewed = await review_task
                    finally:
                        if not review_task.done():
                            review_task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await review_task
                except CancelledRun:
                    store.finish_experiment(experiment_id, "cancelled")
                    return
                except Exception as exc:
                    reviewed = {
                        "status": "unavailable",
                        "model_graded": True,
                        "reason": str(exc)
                        if isinstance(exc, InfrastructureError)
                        else f"Evaluator failed ({type(exc).__name__}).",
                    }
                WorkspaceStore(store).artifact(experiment_id, "semantic_review", reviewed)

            WorkspaceStore(store).artifact(
                experiment_id,
                "comparison",
                {
                    **compare_runs([store.run(r["id"]) for r in experiment["runs"]]),
                    "findings": compare_findings([store.run(r["id"]) for r in experiment["runs"]]),
                },
            )
        final_state = "completed"
        if experiment["manifest"].get("workspace"):
            outcomes = [store.run(r["id"])["outcome"] for r in experiment["runs"]]
            if not any(outcome == "completed" for outcome in outcomes):
                final_state = "failed"
            elif not all(outcome == "completed" for outcome in outcomes):
                final_state = "partial"
        store.finish_experiment(experiment_id, final_state)
    finally:
        pulse.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pulse


async def worker(store: Store, once: bool = False) -> None:
    worker_id = "worker_" + uuid.uuid4().hex
    try:
        while True:
            store.recover()
            experiment_id = store.claim(worker_id)
            if experiment_id:
                await run_experiment(store, experiment_id, worker_id)
            elif once:
                break
            else:
                await asyncio.sleep(0.4)
            if once:
                break
    finally:
        with store.transaction() as connection:
            connection.execute("DELETE FROM worker_lock WHERE owner=?", (worker_id,))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Rilo's durable experiment worker")
    parser.add_argument("--once", action="store_true", help="Process at most one queued experiment")
    args = parser.parse_args()
    asyncio.run(worker(Store(Config.load()), args.once))


if __name__ == "__main__":
    main()
