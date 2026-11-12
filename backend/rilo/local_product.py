"""Local history, diagnostics and data management on the existing store."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .storage import Store, identifier, now


def manage_record(
    store: Store, kind: str, record_id: str, action: str, confirmation: str = ""
) -> dict:
    """Local-only retention changes; never detach a benchmark or regression reference."""
    if store.config.hosted or kind not in {"experiments", "conversations"}:
        raise ValueError("Saved data management is local-only.")
    store.require_access("experiment" if kind == "experiments" else "conversation", record_id)
    with store.transaction() as connection:
        if not connection.execute(f"SELECT id FROM {kind} WHERE id=?", (record_id,)).fetchone():
            raise KeyError(record_id)
        if action in {"archive", "restore"}:
            if action == "archive":
                connection.execute(
                    "INSERT OR IGNORE INTO record_visibility VALUES(?,?,?)",
                    (kind, record_id, now()),
                )
            else:
                connection.execute(
                    "DELETE FROM record_visibility WHERE kind=? AND id=?", (kind, record_id)
                )
        elif action == "delete":
            if confirmation != record_id:
                raise ValueError("Type the exact record ID to permanently delete it.")
            if connection.execute(
                "SELECT 1 FROM experiments WHERE state IN ('queued','running')"
            ).fetchone():
                raise ValueError("Finish or cancel queued/running work before deleting saved data.")
            if (
                kind == "conversations"
                and connection.execute(
                    "SELECT 1 FROM conversations WHERE json_extract(data,'$.continuation.source_conversation_id')=?",
                    (record_id,),
                ).fetchone()
            ):
                raise ValueError(
                    "A saved continuation depends on this conversation. Archive it instead."
                )
            ids = (
                [record_id]
                if kind == "experiments"
                else [
                    r[0]
                    for r in connection.execute(
                        "SELECT experiment_id FROM workspace_turns WHERE conversation_id=?",
                        (record_id,),
                    )
                ]
            )
            if (
                kind == "experiments"
                and connection.execute(
                    "SELECT 1 FROM workspace_turns WHERE experiment_id=?", (record_id,)
                ).fetchone()
            ):
                raise ValueError(
                    "This evaluation belongs to a conversation. Delete the conversation as a unit or archive this evaluation."
                )
            ids += [
                r[0]
                for r in connection.execute(
                    "SELECT experiment_id,original_id FROM workspace_retries"
                )
                if r[1] in ids
            ]
            for exp_id in ids:
                if (
                    connection.execute(
                        "SELECT 1 FROM baselines WHERE experiment_id=?", (exp_id,)
                    ).fetchone()
                    or connection.execute(
                        "SELECT 1 FROM suite_batch_cases WHERE experiment_id=?", (exp_id,)
                    ).fetchone()
                ):
                    raise ValueError(
                        "Saved baselines or suite batches depend on this record. Archive it instead."
                    )
                for row in connection.execute("SELECT data FROM benchmark_suites"):
                    if exp_id in row[0]:
                        raise ValueError(
                            "A versioned suite depends on this record. Archive it instead."
                        )
                for row in connection.execute("SELECT id,manifest FROM experiments"):
                    if row[0] not in ids and exp_id in row[1]:
                        raise ValueError(
                            "A retest or another evaluation depends on this record. Archive it instead."
                        )
                for row in connection.execute(
                    "SELECT experiment_id,data FROM workspace_artifacts WHERE kind='regression'"
                ):
                    if row[0] not in ids and exp_id in row[1]:
                        raise ValueError(
                            "A saved regression depends on this record. Archive it instead."
                        )
            for exp_id in ids:
                run_ids = [
                    r[0]
                    for r in connection.execute(
                        "SELECT id FROM runs WHERE experiment_id=?", (exp_id,)
                    )
                ]
                for run_id in run_ids:
                    connection.execute("DELETE FROM events WHERE run_id=?", (run_id,))
                connection.execute(
                    "DELETE FROM workspace_retries WHERE experiment_id=? OR original_id=?",
                    (exp_id, exp_id),
                )
                connection.execute(
                    "DELETE FROM workspace_artifacts WHERE experiment_id=?", (exp_id,)
                )
                connection.execute("DELETE FROM workspace_turns WHERE experiment_id=?", (exp_id,))
                connection.execute("DELETE FROM runs WHERE experiment_id=?", (exp_id,))
                connection.execute("DELETE FROM experiments WHERE id=?", (exp_id,))
                connection.execute(
                    "DELETE FROM record_visibility WHERE kind='experiments' AND id=?", (exp_id,)
                )
            if kind == "conversations":
                connection.execute("DELETE FROM conversations WHERE id=?", (record_id,))
            connection.execute(
                "DELETE FROM record_visibility WHERE kind=? AND id=?", (kind, record_id)
            )
        else:
            raise ValueError("Choose archive, restore or delete.")
        connection.execute(
            "INSERT INTO local_audit VALUES(?,?,?,?,?)",
            (identifier("audit"), action, kind, record_id, now()),
        )
    return {
        "action": action,
        "id": record_id,
        "scope": "Saved records and their execution history. Shared captured sources and uploaded files are retained.",
    }


def history(
    store: Store,
    kind: str,
    query: str = "",
    page: int = 1,
    size: int = 25,
    category: str | None = None,
    archived: bool = False,
) -> dict:
    if kind not in {"experiments", "conversations"}:
        raise ValueError("Invalid history type.")
    page = max(1, page)
    size = max(1, min(100, size))
    field = "name" if kind == "experiments" else "json_extract(data,'$.title')"
    where = f"{field} LIKE ? ESCAPE '\\'"
    where += (
        f" AND id {'IN' if archived else 'NOT IN'} (SELECT id FROM record_visibility WHERE kind=?)"
    )
    params: list = ["%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"]
    params.append(kind)
    if category:
        if kind != "conversations" or category not in {
            "chat",
            "repository",
            "documents",
            "website",
            "search",
        }:
            raise ValueError("Category filtering requires a supported conversation category.")
        where += " AND json_extract(data,'$.category')=?"
        params.append(category)
    owned = store.owned_ids("experiment" if kind == "experiments" else "conversation")
    if owned is not None:
        where += (
            " AND id IN (SELECT object_id FROM object_owners WHERE object_type=? AND owner_id=?)"
        )
        from .identity import current_owner

        params += ["experiment" if kind == "experiments" else "conversation", current_owner()]
    with store.connection() as connection:
        total = connection.execute(f"SELECT count(*) FROM {kind} WHERE {where}", params).fetchone()[
            0
        ]
        rows = connection.execute(
            f"SELECT * FROM {kind} WHERE {where} ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
            [*params, size, (page - 1) * size],
        ).fetchall()
    items = [
        store.experiment(row["id"], detail=False)
        if kind == "experiments"
        else json.loads(row["data"])
        for row in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, (total + size - 1) // size),
    }


def dashboard(store: Store) -> dict:
    from .identity import current_owner

    owner = current_owner() if store.config.hosted else None
    where = (
        "WHERE e.id IN (SELECT object_id FROM object_owners WHERE object_type='experiment' AND owner_id=?)"
        if owner
        else ""
    )
    params = [owner] if owner else []
    # JSON counters stay in the existing run records; SQL aggregates avoid N+1 reads.
    terminal = "r.state NOT IN ('queued','running')"
    with store.connection() as connection:
        evaluations = connection.execute(
            f"SELECT count(*) FROM experiments e {where}", params
        ).fetchone()[0]
        conversation_where = (
            "WHERE id IN (SELECT object_id FROM object_owners WHERE object_type='conversation' AND owner_id=?)"
            if owner
            else ""
        )
        conversations = connection.execute(
            f"SELECT count(*) FROM conversations {conversation_where}", params
        ).fetchone()[0]
        rows = connection.execute(
            f"SELECT json_extract(r.data,'$.agent_name') AS name,count(*) AS attempts, sum(r.state='completed') AS completed,avg(json_extract(r.data,'$.duration_ms')) AS latency_ms FROM runs r JOIN experiments e ON e.id=r.experiment_id {where} {'AND' if where else 'WHERE'} {terminal} GROUP BY name",
            params,
        ).fetchall()
        totals = connection.execute(
            f"SELECT count(*) AS attempts,sum(r.state='completed') AS successful_executions,sum({terminal} AND r.state!='completed') AS failed_executions,avg(CASE WHEN {terminal} THEN json_extract(r.data,'$.duration_ms') END) AS average_latency_ms,sum(json_extract(r.data,'$.input_tokens')) AS observed_input_tokens,sum(json_extract(r.data,'$.output_tokens')) AS observed_output_tokens,sum(json_extract(r.data,'$.input_tokens') IS NOT NULL) AS token_observed_runs FROM runs r JOIN experiments e ON e.id=r.experiment_id {where}",
            params,
        ).fetchone()
    result = dict(totals)
    for name in ("attempts", "successful_executions", "failed_executions", "token_observed_runs"):
        result[name] = result[name] or 0
    return {
        **result,
        "evaluations": evaluations,
        "conversations": conversations,
        "agents": [dict(row) for row in rows],
        "regressions": [],
        "scope": "All accessible stored evaluations; completion is not accuracy.",
    }


def storage_status(store: Store) -> dict:
    if store.config.hosted:
        raise ValueError("Data management is available in local mode only.")
    sizes: dict = {
        name: sum(p.stat().st_size for p in (store.config.data_dir / name).glob("*") if p.is_file())
        for name in ("uploads", "objects", "backups")
    }
    sizes["database"] = sum(
        p.stat().st_size for p in store.config.data_dir.glob("rilo.db*") if p.is_file()
    )
    sizes["limit"] = store.config.storage_max_bytes
    sizes["free_disk"] = shutil.disk_usage(store.config.data_dir).free
    sizes["data_directory"] = str(store.config.data_dir)
    return sizes


def orphan_files(store: Store) -> list[Path]:
    storage_status(store)
    with store.connection() as connection:
        upload_names = {
            json.loads(row[0])["hash"] for row in connection.execute("SELECT data FROM uploads")
        }
        objects = {
            source["content_hash"]
            for row in connection.execute("SELECT data FROM snapshots")
            for source in json.loads(row[0])["sources"]
        }
    return [
        p
        for folder, names in (("uploads", upload_names), ("objects", objects))
        for p in (store.config.data_dir / folder).glob("*")
        if p.is_file() and p.name not in names
    ]
