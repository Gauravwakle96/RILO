"""Persisted suite admission and summaries from original per-case executions."""

from __future__ import annotations

import json

from .storage import Store, identifier, now


def batch_summary(store: Store, batch_id: str) -> dict:
    store.require_access("batch", batch_id)
    with store.connection() as connection:
        row = connection.execute(
            "SELECT data FROM suite_batches WHERE id=?", (batch_id,)
        ).fetchone()
        if not row:
            raise KeyError(batch_id)
        batch = json.loads(row[0])
        records = connection.execute(
            "SELECT case_index,experiment_id FROM suite_batch_cases WHERE batch_id=? ORDER BY case_index",
            (batch_id,),
        ).fetchall()
    cases = []
    groups: dict[str, list[dict]] = {}
    for case in records:
        evaluation = store.experiment(case[1])
        cases.append(
            {
                "case": case[0],
                "id": case[1],
                "name": evaluation["name"],
                "state": evaluation["state"],
                "progress": evaluation["progress"],
            }
        )
        for entry in evaluation["runs"]:
            run = store.run(entry["id"])
            groups.setdefault(run["agent_id"], []).append(run)
    agents = []
    for agent, runs in groups.items():
        grading = [(r.get("assessment") or {}).get("task_checks", {}) for r in runs]
        assessable = [g for g in grading if g.get("status") in {"pass", "fail"}]
        passed = sum(g["status"] == "pass" for g in assessable)
        agents.append(
            {
                "agent_id": agent,
                "attempts": len(runs),
                "completed": sum(r["outcome"] == "completed" for r in runs),
                "assessed": len(assessable),
                "passed": passed,
                "task_success": passed / len(assessable) if assessable else None,
                "check_score": sum(g["score"] for g in assessable) / len(assessable)
                if assessable
                else None,
                "scope": "Declared checks across the recorded case mix; not general accuracy.",
            }
        )
    finished = len(cases) == batch["total_cases"] and all(
        c["state"] in {"completed", "failed", "partial", "cancelled"} for c in cases
    )
    return {
        **batch,
        "cases": cases,
        "agents": agents,
        "state": "finished"
        if finished
        else "incomplete_admission"
        if len(cases) < batch["total_cases"]
        else "running",
        "missing_cases": [
            index
            for index in range(batch["total_cases"])
            if index not in {c["case"] for c in cases}
        ],
        "limitations": [
            "Different cases can use different checks and agent configurations; totals describe this recorded suite mix.",
            "Missing, failed and ungraded attempts are shown separately.",
        ],
    }


def create_batch(store: Store, suite_id: str) -> dict:
    store.require_access("suite", suite_id)
    with store.transaction() as connection:
        row = connection.execute(
            "SELECT data FROM benchmark_suites WHERE id=?", (suite_id,)
        ).fetchone()
        if not row:
            raise KeyError(suite_id)
        suite = json.loads(row[0])
        value = {
            "id": identifier("batch"),
            "suite_id": suite_id,
            "name": suite["name"],
            "version": suite["version"],
            "created_at": now(),
            "total_cases": len(suite.get("cases", [suite])),
        }
        connection.execute(
            "INSERT INTO suite_batches VALUES(?,?,?,?)",
            (value["id"], suite_id, json.dumps(value), value["created_at"]),
        )
    store.claim_object("batch", value["id"])
    return value
