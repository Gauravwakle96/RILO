"""Workspace routes use the existing session, CSRF and local host boundary."""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask

from .promptfoo_checks import availability
from .readiness import PreflightInput, readiness
from .snapshots import Snapshots
from .storage import Store
from .workspace_contracts import (
    CandidateCreate,
    ConversationCreate,
    HumanReview,
    RecordAction,
    TurnCreate,
)
from .workspace_evaluation import RegressionCreate, SuiteCreate, compare_workspace
from .workspace_store import WorkspaceStore, profiles


def reports_for_owner(store: Store, kind: str) -> list[dict]:
    with store.connection() as connection:
        values = [
            json.loads(row[0])
            for row in connection.execute(
                "SELECT data FROM workspace_artifacts WHERE kind=? ORDER BY created_at DESC",
                (kind,),
            )
        ]
    return [value for value in values if store.can_access("experiment", value["experiment_id"])]


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
            "deployment": "hosted_multi_user" if store.config.hosted else "local_single_user",
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
                "ocr": True,
                "ocr_engine": "local Tesseract when installed",
                "max_upload_bytes": 8_000_000,
            },
        }

    @router.get("/dashboard")
    def dashboard():
        from .local_product import dashboard as local_dashboard

        result = local_dashboard(store)
        result["regressions"] = reports_for_owner(store, "regression")[:5]
        return result

    @router.get("/history")
    def history(
        kind: Literal["experiments", "conversations"] = "experiments",
        query: str = "",
        page: int = 1,
        size: int = 25,
        category: str | None = None,
        archived: bool = False,
    ):
        from .local_product import history as records

        return records(store, kind, query[:200], page, size, category, archived)

    @router.post("/records/{kind}/{record_id}")
    def record_action(
        kind: Literal["experiments", "conversations"], record_id: str, payload: RecordAction
    ):
        from .local_product import manage_record

        return manage_record(store, kind, record_id, payload.action, payload.confirmation)

    @router.get("/storage")
    def storage():
        from .local_product import orphan_files, storage_file_sizes, storage_status

        files = storage_file_sizes(orphan_files(store))
        return {
            **storage_status(store),
            "orphan_files": len(files),
            "reclaimable_bytes": sum(files.values()),
        }

    @router.get("/backup")
    def download_backup():
        import shutil
        import tempfile
        from pathlib import Path

        from .backup import backup

        if store.config.hosted:
            raise ValueError("Backup downloads are local-only.")
        with store.transaction() as connection:
            if connection.execute(
                "SELECT 1 FROM experiments WHERE state IN ('queued','running')"
            ).fetchone():
                raise ValueError("Wait for queued/running work before taking a consistent backup.")
            temporary = tempfile.mkdtemp(prefix="rilo-backup-")
            try:
                path = Path(temporary) / "rilo-backup.tar.gz"
                backup(store.config.data_dir, path)
            except Exception:
                shutil.rmtree(temporary)
                raise
        return FileResponse(
            path,
            media_type="application/gzip",
            filename="rilo-private-backup.tar.gz",
            background=BackgroundTask(shutil.rmtree, temporary),
        )

    @router.post("/storage/cleanup")
    def cleanup():
        from .local_product import orphan_files

        removed = 0
        with store.transaction() as connection:
            if connection.execute(
                "SELECT 1 FROM experiments WHERE state IN ('queued','running')"
            ).fetchone():
                raise ValueError("Wait for queued/running work before cleaning storage.")
            files = orphan_files(store)
            for path in files:
                if not path.resolve().is_relative_to(store.config.data_dir):
                    raise ValueError("Unexpected storage path.")
                try:
                    path.unlink()
                except FileNotFoundError:
                    continue
                removed += 1
        return {
            "removed_files": removed,
            "scope": "Only blobs without persisted source references removed.",
        }

    @router.patch("/conversations/{conversation_id}")
    def rename(conversation_id: str, payload: dict):
        store.require_access("conversation", conversation_id)
        if (
            set(payload) != {"title"}
            or not isinstance(payload["title"], str)
            or not 1 <= len(payload["title"].strip()) <= 120
        ):
            raise ValueError("Provide a title of 1–120 characters.")
        with store.transaction() as connection:
            row = connection.execute(
                "SELECT data FROM conversations WHERE id=?", (conversation_id,)
            ).fetchone()
            if not row:
                raise KeyError(conversation_id)
            data = json.loads(row[0])
            data["title"] = payload["title"].strip()
            connection.execute(
                "UPDATE conversations SET data=? WHERE id=?", (json.dumps(data), conversation_id)
            )
        return data

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

    @router.post("/conversations/{conversation_id}/continue", status_code=201)
    def continue_conversation(conversation_id: str):
        return workspace.continue_conversation(conversation_id)

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

    @router.post("/runs/{run_id}/reviews", status_code=201)
    def human_review(run_id: str, payload: HumanReview):
        run = store.run(run_id)
        finding = next(
            (
                f
                for f in (run.get("assessment") or {}).get("findings", [])
                if f["id"] == payload.finding_id
            ),
            None,
        )
        if finding is None:
            raise ValueError("Finding does not belong to this recorded run.")
        return workspace.artifact(
            run["experiment_id"],
            "human_review",
            {
                "run_id": run_id,
                **payload.model_dump(),
                "method": "human-reviewed",
                "scope": "User judgment; stored separately from automated evidence integrity and original findings.",
            },
        )

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
        return reports_for_owner(store, "report")[:100]

    @router.get("/suites")
    def suites():
        with store.connection() as connection:
            return [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT data FROM benchmark_suites ORDER BY created_at DESC"
                )
                if store.can_access("suite", json.loads(row[0])["id"])
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
        record["cases"] = []
        for value in [source["id"], *payload.additional_experiment_ids]:
            captured = store.experiment(value)
            if captured["state"] != "completed" or not captured["manifest"].get("snapshot"):
                raise ValueError(
                    "Every suite case requires a completed captured workspace evaluation."
                )
            record["cases"].append(
                {
                    "spec": captured["spec"],
                    "source_manifest": captured["manifest"],
                    "snapshot_id": captured["manifest"]["snapshot"]["id"],
                    "checks": record["checks"]
                    if value == source["id"]
                    else captured["manifest"]["workspace"].get("checks", []),
                    "labels": record["labels"]
                    if value == source["id"]
                    else captured["manifest"]["workspace"].get("ground_truth", []),
                }
            )
        with store.transaction() as connection:
            duplicate = next(
                (
                    json.loads(row[0])
                    for row in connection.execute(
                        "SELECT data FROM benchmark_suites WHERE json_extract(data,'$.name')=? AND json_extract(data,'$.version')=?",
                        (payload.name, payload.version),
                    )
                    if store.can_access("suite", json.loads(row[0])["id"])
                ),
                None,
            )
            if duplicate:
                raise ValueError("This suite name and version already exist. Choose a new version.")
            connection.execute(
                "INSERT INTO benchmark_suites(id,data,created_at) VALUES(?,?,?)",
                (record["id"], json.dumps(record), record["created_at"]),
            )
        store.claim_object("suite", record["id"])
        return record

    @router.post("/suites/{suite_id}/run", status_code=202)
    def run_suite(suite_id: str, case: int = 0, batch_id: str | None = None):
        from .schemas import ExperimentCreate
        from .storage import identifier
        from .workspace_store import runtime_hash

        store.require_access("suite", suite_id)
        with store.connection() as connection:
            row = connection.execute(
                "SELECT data FROM benchmark_suites WHERE id=?", (suite_id,)
            ).fetchone()
        if not row:
            raise KeyError(suite_id)
        suite = json.loads(row[0])
        if batch_id:
            store.require_access("batch", batch_id)
            with store.connection() as connection:
                batch = connection.execute(
                    "SELECT suite_id FROM suite_batches WHERE id=?", (batch_id,)
                ).fetchone()
                if not batch or batch[0] != suite_id:
                    raise ValueError("Batch does not belong to this suite.")
                existing = connection.execute(
                    "SELECT experiment_id FROM suite_batch_cases WHERE batch_id=? AND case_index=?",
                    (batch_id, case),
                ).fetchone()
            if existing:
                return store.experiment(existing[0])
        if not 0 <= case < len(suite.get("cases", [suite])):
            raise ValueError("Suite case was not found.")
        suite = {**suite, **suite.get("cases", [suite])[case]}
        original = suite["source_manifest"]["workspace"]
        conv = workspace.create(
            ConversationCreate(
                title=suite["name"],
                category=original["category"],
                agent_ids=suite["spec"]["agent_ids"],
                slots=suite["source_manifest"]["workspace"].get("slots"),
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
            "suite_case": case,
            "ground_truth": suite["labels"],
            "checks": suite.get("checks", original.get("checks", [])),
            "search_provider": "off",
            **({"batch_id": batch_id} if batch_id else {}),
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

    @router.get("/batches")
    def batches():
        from .suite_batches import batch_summary

        with store.connection() as connection:
            ids = [
                r[0]
                for r in connection.execute(
                    "SELECT id FROM suite_batches ORDER BY created_at DESC LIMIT 100"
                )
            ]
        return [batch_summary(store, value) for value in ids if store.can_access("batch", value)]

    @router.get("/batches/{batch_id}")
    def batch(batch_id: str):
        from .suite_batches import batch_summary

        return batch_summary(store, batch_id)

    @router.post("/suites/{suite_id}/batches", status_code=202)
    def start_batch(suite_id: str):
        from .suite_batches import create_batch

        record = create_batch(store, suite_id)
        return resume_batch(record["id"])

    @router.post("/batches/{batch_id}/resume", status_code=202)
    def resume_batch(batch_id: str):
        from .suite_batches import batch_summary

        record = batch_summary(store, batch_id)
        admission_error = None
        for case in record["missing_cases"]:
            try:
                run_suite(record["suite_id"], case, batch_id)
            except ValueError as exc:
                admission_error = str(exc)
                break
        return {**batch_summary(store, batch_id), "admission_error": admission_error}

    @router.get("/batches/{batch_id}/export")
    def export_batch(batch_id: str):
        from .suite_batches import batch_summary

        value = batch_summary(store, batch_id)
        return Response(
            json.dumps(value, ensure_ascii=False, indent=2).encode(),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="rilo-{value["id"]}.json"'},
        )

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
    def retest(experiment_id: str, payload: CandidateCreate | None = None):
        if payload and not payload.slots:
            payload = None
        source = store.experiment(experiment_id)
        task = source["manifest"].get("workspace")
        if not task or source["state"] not in {"completed", "partial", "failed", "cancelled"}:
            raise ValueError("Choose a finished workspace evaluation to retest.")
        snapshot = source["manifest"].get("snapshot")
        if payload and not task.get("slots"):
            raise ValueError("Editable reruns require an evaluation with independent A/B slots.")
        search_provider: Literal["off", "tavily"] = (
            "tavily" if not snapshot and task.get("search_provider") == "tavily" else "off"
        )
        conv = workspace.create(
            ConversationCreate(
                title=source["name"][:90] + " retest",
                category=task["category"],
                agent_ids=source["spec"]["agent_ids"],
                slots=payload.slots if payload else task.get("slots"),
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
        if payload:
            pinned_task.update(
                slots=conv["slots"],
                execution_agents=conv["execution_agents"],
                declared_agent_changes=True,
            )
        spec = ExperimentCreate.model_validate(
            {
                **source["spec"],
                "name": conv["title"],
                "mode": "live" if search_provider == "tavily" else "controlled",
            }
        )
        return store.create_experiment(spec, workspace=pinned_task)

    return router
