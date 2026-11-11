"""Workspace routes use the existing session, CSRF and local host boundary."""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import Response

from .promptfoo_checks import availability
from .readiness import PreflightInput, readiness
from .snapshots import Snapshots
from .storage import Store
from .workspace_contracts import ConversationCreate, TurnCreate
from .workspace_evaluation import RegressionCreate, SuiteCreate, compare_workspace
from .workspace_store import WorkspaceStore, profiles


def workspace_router(store: Store) -> APIRouter:
    router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])
    workspace = WorkspaceStore(store)

    @router.post("/preflight")
    async def preflight(payload: PreflightInput):
        return await readiness(store, payload)

    @router.get("/profiles")
    def agent_profiles():
        return profiles(store)

    @router.get("/capabilities")
    def capabilities():
        import os

        with store.connection() as connection:
            reserved = connection.execute(
                "SELECT coalesce(sum(reserved_credits),0) FROM experiments"
            ).fetchone()[0]
        return {
            "task_checks": availability(),
            "deployment": "local_single_user",
            "tavily": {
                "configured": bool(store.config.tavily_key),
                "default": "off",
                "search_depth": "basic",
                "local_credit_limit": store.config.tavily_credit_limit,
                "reserved": reserved,
                "remaining_local_allowance": max(0, store.config.tavily_credit_limit - reserved),
                "provider_balance": None,
                "scope": "Lifetime conservative local reservation; not monthly Tavily billing",
            },
            "github": {"private_access_configured": bool(store.config.github_key)},
            "sandbox": {
                "image_configured": bool(os.environ.get("RILO_SANDBOX_IMAGE")),
                "health": "validated when requested; configuration alone does not prove availability",
            },
            "documents": {
                "formats": ["pdf", "docx", "txt", "md"],
                "ocr": False,
                "max_upload_bytes": 8_000_000,
            },
        }

    @router.get("/dashboard")
    def dashboard():
        with store.connection() as connection:
            total = connection.execute("SELECT count(*) FROM experiments").fetchone()[0]
            aggregate = connection.execute("""
                SELECT count(*) AS attempts,
                coalesce(sum(state='completed'),0) AS successful_executions,
                coalesce(sum(state NOT IN ('completed','queued','running')),0) AS failed_executions,
                avg(CASE WHEN state NOT IN ('queued','running') THEN json_extract(data,'$.duration_ms') END) AS average_latency_ms,
                sum(json_extract(data,'$.input_tokens')) AS observed_input_tokens,
                sum(json_extract(data,'$.output_tokens')) AS observed_output_tokens,
                sum(json_extract(data,'$.input_tokens') IS NOT NULL) AS token_observed_runs
                FROM runs
            """).fetchone()
            agents = [
                dict(row)
                for row in connection.execute("""
                SELECT json_extract(data,'$.agent_name') AS name, count(*) AS attempts,
                sum(state='completed') AS completed,
                avg(CASE WHEN state='completed' THEN json_extract(data,'$.duration_ms') END) AS latency_ms
                FROM runs GROUP BY json_extract(data,'$.agent_name')
            """)
            ]
            regressions = [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT data FROM workspace_artifacts WHERE kind='regression' ORDER BY created_at DESC LIMIT 5"
                )
            ]
        return {
            "evaluations": total,
            **dict(aggregate),
            "agents": agents,
            "regressions": regressions,
            "scope": "All persisted executions, including explicitly labeled fixture benchmarks. Completion is not verified accuracy.",
        }

    @router.get("/conversations")
    def conversations():
        return workspace.list()

    @router.post("/conversations", status_code=201)
    def create_conversation(payload: ConversationCreate):
        return workspace.create(payload)

    @router.get("/conversations/{conversation_id}")
    def conversation(conversation_id: str):
        return workspace.get(conversation_id)

    @router.get("/conversations/{conversation_id}/export")
    def export_conversation(conversation_id: str):
        value = workspace.get(conversation_id)
        return Response(
            json.dumps(value, ensure_ascii=False, indent=2).encode(),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="rilo-{value["id"]}.json"'},
        )

    @router.post("/conversations/{conversation_id}/turns", status_code=202)
    def turn(conversation_id: str, payload: TurnCreate, request: Request):
        key = request.headers.get("idempotency-key")
        if key and (len(key) > 100 or not key.isascii()):
            raise ValueError("Idempotency-Key must be ASCII and at most 100 characters.")
        return workspace.turn(conversation_id, payload, key)

    @router.get("/snapshots/{snapshot_id}")
    def snapshot(snapshot_id: str):
        return Snapshots(store).get(snapshot_id, True)

    @router.post("/runs/{run_id}/retry", status_code=202)
    def retry_response(run_id: str):
        return workspace.retry(run_id)

    @router.get("/evaluations/{experiment_id}")
    def evaluation(experiment_id: str):
        value = store.experiment(experiment_id)
        if not value["manifest"].get("workspace"):
            raise ValueError("This is a research benchmark; use its existing experiment report.")
        value["runs"] = [store.run(run["id"]) for run in value["runs"]]
        with store.connection() as connection:
            value["artifacts"] = [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT data FROM workspace_artifacts WHERE experiment_id=? ORDER BY rowid",
                    (experiment_id,),
                )
            ]
        return value

    @router.post("/uploads", status_code=201)
    async def upload(request: Request):
        import asyncio

        from .ingestion import save_upload

        return await asyncio.to_thread(
            save_upload, store, request.headers.get("x-filename", ""), await request.body()
        )

    @router.get("/evaluations/{experiment_id}/report")
    def report(experiment_id: str, format: Literal["pdf", "md", "json", "csv"] = "json"):
        from .reports import export, report_data

        data = report_data(store, experiment_id)
        content, media = export(data, format)
        import hashlib

        workspace.artifact(
            experiment_id,
            "report",
            {
                "format": format,
                "content_hash": hashlib.sha256(content).hexdigest(),
                "size": len(content),
                "source_updated_at": data["updated_at"],
            },
        )
        return Response(
            content,
            media_type=media,
            headers={
                "Content-Disposition": f'attachment; filename="rilo-{experiment_id}.{format}"'
            },
        )

    @router.get("/reports")
    def reports():
        with store.connection() as connection:
            return [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT data FROM workspace_artifacts WHERE kind='report' ORDER BY created_at DESC LIMIT 100"
                )
            ]

    @router.get("/suites")
    def suites():
        with store.connection() as connection:
            return [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT data FROM benchmark_suites ORDER BY created_at DESC"
                )
            ]

    @router.post("/suites", status_code=201)
    def create_suite(payload: SuiteCreate):
        from .storage import identifier, now

        source = store.experiment(payload.source_experiment_id)
        if not source["manifest"].get("snapshot") or source["state"] != "completed":
            raise ValueError("Choose a completed workspace evaluation with a captured snapshot.")
        snapshot_sources = Snapshots(store).get(source["manifest"]["snapshot"]["id"], True)[
            "sources"
        ]
        for label in payload.labels:
            if not any(
                s["reference"] == label.reference and label.expected_quote in s["content"]
                for s in snapshot_sources
            ):
                raise ValueError("Each ground-truth reference must match the captured source.")
        record = {
            "id": identifier("suite"),
            "created_at": now(),
            **payload.model_dump(),
            "snapshot_id": source["manifest"]["snapshot"]["id"],
            "source_manifest": source["manifest"],
            "spec": source["spec"],
            "label_scope": "Expected source quotation coverage; not semantic vulnerability truth",
            "checks": [check.model_dump() for check in payload.checks]
            if payload.checks is not None
            else source["manifest"]["workspace"].get("checks", []),
        }
        with store.transaction() as connection:
            if connection.execute(
                "SELECT 1 FROM benchmark_suites WHERE json_extract(data,'$.name')=? AND json_extract(data,'$.version')=?",
                (payload.name, payload.version),
            ).fetchone():
                raise ValueError("This suite name and version already exist. Choose a new version.")
            connection.execute(
                "INSERT INTO benchmark_suites(id,data,created_at) VALUES(?,?,?)",
                (record["id"], json.dumps(record), record["created_at"]),
            )
        return record

    @router.post("/suites/{suite_id}/run", status_code=202)
    def run_suite(suite_id: str):
        from .schemas import ExperimentCreate
        from .storage import identifier
        from .workspace_store import runtime_hash

        with store.connection() as connection:
            row = connection.execute(
                "SELECT data FROM benchmark_suites WHERE id=?", (suite_id,)
            ).fetchone()
        if not row:
            raise KeyError(suite_id)
        suite = json.loads(row[0])
        original = suite["source_manifest"]["workspace"]
        conv = workspace.create(
            ConversationCreate(
                title=suite["name"],
                category=original["category"],
                agent_ids=suite["spec"]["agent_ids"],
                model=suite["spec"]["model"],
                search_provider="off",
                limits=suite["spec"]["limits"],
            )
        )
        task = {
            **original,
            "conversation_id": conv["id"],
            "turn_id": identifier("turn"),
            "snapshot_id": suite["snapshot_id"],
            "previous_turns": 0,
            "runtime_hash": runtime_hash(),
            "suite_id": suite_id,
            "suite_version": suite["version"],
            "ground_truth": suite["labels"],
            "checks": suite.get("checks", original.get("checks", [])),
            "search_provider": "off",
        }
        spec = ExperimentCreate.model_validate(
            {
                **suite["spec"],
                "name": suite["name"][:100] + " · benchmark",
                "mode": "controlled",
                "repetitions": suite["repetitions"],
            }
        )
        return store.create_experiment(spec, workspace=task)

    @router.post("/regressions")
    def regression(payload: RegressionCreate):
        from .reports import report_data

        result = compare_workspace(
            report_data(store, payload.baseline_id),
            report_data(store, payload.candidate_id),
            payload,
        )
        workspace.artifact(
            payload.candidate_id,
            "regression",
            {"baseline_id": payload.baseline_id, "candidate_id": payload.candidate_id, **result},
        )
        return result

    @router.post("/evaluations/{experiment_id}/retest", status_code=202)
    def retest(experiment_id: str):
        source = store.experiment(experiment_id)
        task = source["manifest"].get("workspace")
        if not task or source["state"] not in {"completed", "partial", "failed", "cancelled"}:
            raise ValueError("Choose a finished workspace evaluation to retest.")
        snapshot = source["manifest"].get("snapshot")
        search_provider: Literal["off", "tavily"] = (
            "tavily" if not snapshot and task.get("search_provider") == "tavily" else "off"
        )
        conv = workspace.create(
            ConversationCreate(
                title=source["name"][:90] + " retest",
                category=task["category"],
                agent_ids=source["spec"]["agent_ids"],
                model=source["spec"]["model"],
                limits=source["spec"]["limits"],
                search_provider=search_provider,
                semantic_review=task.get("semantic_review", False),
            )
        )
        from .schemas import ExperimentCreate
        from .storage import identifier
        from .workspace_store import runtime_hash

        pinned_task = {
            **task,
            "conversation_id": conv["id"],
            "turn_id": identifier("turn"),
            "snapshot_id": snapshot["id"] if snapshot else None,
            "previous_turns": 0,
            "runtime_hash": runtime_hash(),
            "search_provider": search_provider,
            "retest_of": source["id"],
            "source_capture": "reused_snapshot" if snapshot else "retry_input_capture",
        }
        spec = ExperimentCreate.model_validate(
            {
                **source["spec"],
                "name": conv["title"],
                "mode": "live" if search_provider == "tavily" else "controlled",
            }
        )
        return store.create_experiment(spec, workspace=pinned_task)

    return router
