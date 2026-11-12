"""SQLite persistence with explicit migrations, atomic claims, and bounded traces."""

from __future__ import annotations

import itertools
import json
import random
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from .catalog import AGENTS, SCENARIOS, SOURCES, TASKS, digest
from .config import Config, redact
from .identity import (
    current_owner,
    normalize_email,
    password_hash,
    session_expiry,
    token_hash,
    verify_password,
)
from .pricing import price_basis
from .provenance import builtin_metadata, loaded_identity
from .schemas import ExperimentCreate

TERMINAL = {"completed", "cancelled", "failed", "partial"}


def now() -> str:
    return datetime.now(UTC).isoformat()


def identifier(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class Store:
    def __init__(self, config: Config):
        self.config = config
        self.path = config.data_dir / "rilo.db"
        self.initialize()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS schema_versions(version INTEGER PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS catalog(kind TEXT NOT NULL,id TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(kind,id));
                CREATE TABLE IF NOT EXISTS agent_versions(agent_id TEXT NOT NULL,version TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(agent_id,version));
                CREATE TABLE IF NOT EXISTS experiments(
                    id TEXT PRIMARY KEY,name TEXT NOT NULL,state TEXT NOT NULL,spec TEXT NOT NULL,manifest TEXT NOT NULL,
                    created_at TEXT NOT NULL,updated_at TEXT NOT NULL,total INTEGER NOT NULL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,idempotency_key TEXT UNIQUE,lease_until REAL,worker_id TEXT,
                    reserved_credits INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS runs(
                    id TEXT PRIMARY KEY,experiment_id TEXT NOT NULL REFERENCES experiments(id),position INTEGER NOT NULL,
                    data TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'queued',UNIQUE(experiment_id,position));
                CREATE TABLE IF NOT EXISTS events(
                    run_id TEXT NOT NULL REFERENCES runs(id),sequence INTEGER NOT NULL,data TEXT NOT NULL,
                    PRIMARY KEY(run_id,sequence));
                CREATE TABLE IF NOT EXISTS baselines(id TEXT PRIMARY KEY,name TEXT NOT NULL,
                    experiment_id TEXT NOT NULL REFERENCES experiments(id),created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS worker_lock(id INTEGER PRIMARY KEY CHECK(id=1),owner TEXT NOT NULL,expires_at REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS experiments_queue ON experiments(state,created_at);
                CREATE INDEX IF NOT EXISTS run_experiment ON runs(experiment_id,position);
                INSERT OR IGNORE INTO schema_versions(version) VALUES(1);
                INSERT OR IGNORE INTO schema_versions(version) VALUES(2);
                CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,data TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS workspace_turns(id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL REFERENCES conversations(id),experiment_id TEXT NOT NULL UNIQUE REFERENCES experiments(id),message TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS turns_conversation ON workspace_turns(conversation_id,created_at);
                CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY,data TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS uploads(id TEXT PRIMARY KEY,data TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS workspace_artifacts(id TEXT PRIMARY KEY,experiment_id TEXT NOT NULL REFERENCES experiments(id),kind TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS benchmark_suites(id TEXT PRIMARY KEY,data TEXT NOT NULL,created_at TEXT NOT NULL);
                INSERT OR IGNORE INTO schema_versions(version) VALUES(3);
                CREATE TABLE IF NOT EXISTS workspace_retries(experiment_id TEXT PRIMARY KEY REFERENCES experiments(id),original_id TEXT NOT NULL REFERENCES experiments(id),run_id TEXT NOT NULL REFERENCES runs(id),created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS retries_original ON workspace_retries(original_id,created_at);
                CREATE UNIQUE INDEX IF NOT EXISTS retries_once ON workspace_retries(run_id);
                INSERT OR IGNORE INTO schema_versions(version) VALUES(4);
                CREATE TABLE IF NOT EXISTS users(
                    id TEXT PRIMARY KEY,email TEXT NOT NULL UNIQUE,name TEXT NOT NULL,password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin','member')),disabled INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS auth_sessions(
                    id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),token_hash TEXT NOT NULL UNIQUE,
                    csrf_hash TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL,last_seen_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS auth_sessions_expiry ON auth_sessions(expires_at);
                CREATE TABLE IF NOT EXISTS object_owners(
                    object_type TEXT NOT NULL,object_id TEXT NOT NULL,owner_id TEXT NOT NULL REFERENCES users(id),
                    created_at TEXT NOT NULL,PRIMARY KEY(object_type,object_id));
                CREATE INDEX IF NOT EXISTS object_owner_lookup ON object_owners(owner_id,object_type,created_at);
                INSERT OR IGNORE INTO schema_versions(version) VALUES(5);
                CREATE INDEX IF NOT EXISTS experiments_history ON experiments(created_at DESC,id);
                CREATE INDEX IF NOT EXISTS conversations_history ON conversations(created_at DESC,id);
                CREATE INDEX IF NOT EXISTS artifacts_history ON workspace_artifacts(kind,created_at DESC);
                INSERT OR IGNORE INTO schema_versions(version) VALUES(6);
                CREATE TABLE IF NOT EXISTS record_visibility(kind TEXT NOT NULL,id TEXT NOT NULL,archived_at TEXT NOT NULL,PRIMARY KEY(kind,id));
                CREATE TABLE IF NOT EXISTS local_audit(id TEXT PRIMARY KEY,action TEXT NOT NULL,kind TEXT NOT NULL,object_id TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS suite_batches(id TEXT PRIMARY KEY,suite_id TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS suite_batch_cases(batch_id TEXT NOT NULL REFERENCES suite_batches(id),case_index INTEGER NOT NULL,experiment_id TEXT NOT NULL UNIQUE REFERENCES experiments(id),PRIMARY KEY(batch_id,case_index));
                INSERT OR IGNORE INTO schema_versions(version) VALUES(7);
            """)
        with self.transaction() as connection:
            for kind, values in (
                ("agent", AGENTS),
                ("task", TASKS),
                ("source", SOURCES),
                ("scenario", SCENARIOS),
            ):
                for item in values:
                    connection.execute(
                        "INSERT OR IGNORE INTO catalog(kind,id,data) VALUES(?,?,?)",
                        (kind, item["id"], json.dumps(item)),
                    )
            for row in connection.execute("SELECT data FROM catalog WHERE kind='agent'"):
                item = json.loads(row["data"])
                connection.execute(
                    "INSERT OR IGNORE INTO agent_versions(agent_id,version,data,created_at) VALUES(?,?,?,?)",
                    (item["id"], item["version"], json.dumps(item), now()),
                )

    def create_user(self, email: str, name: str, password: str, role: str = "member") -> dict:
        email = normalize_email(email)
        name = name.strip()
        if not 1 <= len(name) <= 100 or role not in {"admin", "member"}:
            raise ValueError("User name or role is invalid.")
        value = {
            "id": identifier("user"),
            "email": email,
            "name": name,
            "role": role,
            "created_at": now(),
        }
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO users(id,email,name,password_hash,role,created_at) VALUES(?,?,?,?,?,?)",
                (value["id"], email, name, password_hash(password), role, value["created_at"]),
            )
        return value

    def users(self) -> list[dict]:
        with self.connection() as connection:
            return [
                {key: row[key] for key in ("id", "email", "name", "role", "disabled", "created_at")}
                for row in connection.execute(
                    "SELECT id,email,name,role,disabled,created_at FROM users ORDER BY created_at"
                )
            ]

    def user_count(self) -> int:
        with self.connection() as connection:
            return int(connection.execute("SELECT count(*) FROM users").fetchone()[0])

    def authenticate_user(self, email: str, password: str) -> dict | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id,email,name,password_hash,role,disabled,created_at FROM users WHERE email=?",
                (normalize_email(email),),
            ).fetchone()
        if not row or row["disabled"] or not verify_password(password, row["password_hash"]):
            return None
        return {key: row[key] for key in ("id", "email", "name", "role", "created_at")}

    def create_auth_session(self, user_id: str, token: str, csrf: str) -> None:
        timestamp = now()
        with self.transaction() as connection:
            connection.execute("DELETE FROM auth_sessions WHERE expires_at<?", (timestamp,))
            connection.execute(
                "INSERT INTO auth_sessions(id,user_id,token_hash,csrf_hash,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?,?,?)",
                (
                    identifier("auth"),
                    user_id,
                    token_hash(token),
                    token_hash(csrf),
                    session_expiry(),
                    timestamp,
                    timestamp,
                ),
            )

    def auth_session(self, token: str) -> tuple[dict, str] | None:
        if not token:
            return None
        timestamp = now()
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT s.id,s.csrf_hash,u.id AS user_id,u.email,u.name,u.role,u.created_at "
                "FROM auth_sessions s JOIN users u ON u.id=s.user_id "
                "WHERE s.token_hash=? AND s.expires_at>? AND u.disabled=0",
                (token_hash(token), timestamp),
            ).fetchone()
            if row:
                connection.execute(
                    "UPDATE auth_sessions SET last_seen_at=? WHERE id=?", (timestamp, row["id"])
                )
        if not row:
            return None
        user = {
            "id": row["user_id"],
            **{key: row[key] for key in ("email", "name", "role", "created_at")},
        }
        return user, row["csrf_hash"]

    def revoke_auth_session(self, token: str) -> None:
        with self.transaction() as connection:
            connection.execute("DELETE FROM auth_sessions WHERE token_hash=?", (token_hash(token),))

    def claim_object(self, object_type: str, object_id: str, owner_id: str | None = None) -> None:
        owner = owner_id or current_owner()
        if not self.config.hosted or not owner:
            return
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO object_owners(object_type,object_id,owner_id,created_at) VALUES(?,?,?,?)",
                (object_type, object_id, owner, now()),
            )

    def can_access(self, object_type: str, object_id: str, owner_id: str | None = None) -> bool:
        if not self.config.hosted:
            return True
        owner = owner_id or current_owner()
        if not owner:
            return True
        with self.connection() as connection:
            row = connection.execute(
                "SELECT owner_id FROM object_owners WHERE object_type=? AND object_id=?",
                (object_type, object_id),
            ).fetchone()
        return bool(row and row["owner_id"] == owner)

    def require_access(self, object_type: str, object_id: str) -> None:
        if not self.can_access(object_type, object_id):
            raise KeyError(object_id)

    def owned_ids(self, object_type: str) -> list[str] | None:
        owner = current_owner()
        if not self.config.hosted or not owner:
            return None
        with self.connection() as connection:
            return [
                row[0]
                for row in connection.execute(
                    "SELECT object_id FROM object_owners WHERE object_type=? AND owner_id=? ORDER BY created_at DESC",
                    (object_type, owner),
                )
            ]

    def object_owner(self, object_type: str, object_id: str) -> str | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT owner_id FROM object_owners WHERE object_type=? AND object_id=?",
                (object_type, object_id),
            ).fetchone()
        return row[0] if row else None

    def scoped_key(self, value: str | None) -> str | None:
        owner = current_owner()
        return owner + ":" + value if self.config.hosted and value and owner else value

    def catalog(self, kind: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            values = [
                builtin_metadata(json.loads(row["data"]))
                if kind == "agent"
                else json.loads(row["data"])
                for row in connection.execute(
                    "SELECT data FROM catalog WHERE kind=? ORDER BY rowid", (kind,)
                )
            ]
        if self.config.hosted and kind in {"agent", "task"} and current_owner():
            builtins = {item["id"] for item in AGENTS if kind == "agent"} | {
                item["id"] for item in TASKS if kind == "task"
            }
            values = [
                item
                for item in values
                if item["id"] in builtins or self.can_access("catalog_" + kind, item["id"])
            ]
        return values

    def item(self, kind: str, item_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT data FROM catalog WHERE kind=? AND id=?", (kind, item_id)
            ).fetchone()
        if row is None:
            raise KeyError(item_id)
        builtins = {item["id"] for item in AGENTS if kind == "agent"} | {
            item["id"] for item in TASKS if kind == "task"
        }
        if kind in {"agent", "task"} and item_id not in builtins:
            self.require_access("catalog_" + kind, item_id)
        item = json.loads(row["data"])
        return builtin_metadata(item) if kind == "agent" else item

    def add_item(self, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO catalog(kind,id,data) VALUES(?,?,?)",
                (kind, data["id"], json.dumps(data)),
            )
            if kind == "agent":
                connection.execute(
                    "INSERT INTO agent_versions(agent_id,version,data,created_at) VALUES(?,?,?,?)",
                    (data["id"], data["version"], json.dumps(data), now()),
                )
        if kind in {"agent", "task"}:
            self.claim_object("catalog_" + kind, data["id"])
        return builtin_metadata(data) if kind == "agent" else data

    def revise_agent(self, agent_id: str, update: dict[str, Any]) -> dict:
        """Archive an explicitly new HTTP version without mutating experiment snapshots."""
        self.require_access("catalog_agent", agent_id)
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT data FROM catalog WHERE kind='agent' AND id=?", (agent_id,)
            ).fetchone()
            if row is None:
                raise KeyError(agent_id)
            current = json.loads(row["data"])
            if current["kind"] != "http":
                raise ValueError(
                    "Built-in workflows are versioned by installed implementation; only HTTP versions can be registered."
                )
            if connection.execute(
                "SELECT 1 FROM agent_versions WHERE agent_id=? AND version=?",
                (agent_id, update["version"]),
            ).fetchone():
                raise ValueError(
                    "Choose a new agent version; existing version labels cannot be reused."
                )
            revised = {
                **current,
                "version": update["version"],
                "config": {**current["config"], "endpoint": update["endpoint"]},
                **{
                    field: update[field]
                    for field in ("name", "description")
                    if update.get(field) is not None
                },
            }
            connection.execute(
                "INSERT INTO agent_versions(agent_id,version,data,created_at) VALUES(?,?,?,?)",
                (agent_id, revised["version"], json.dumps(revised), now()),
            )
            connection.execute(
                "UPDATE catalog SET data=? WHERE kind='agent' AND id=?",
                (json.dumps(revised), agent_id),
            )
        return builtin_metadata(revised)

    def agent_versions(self, agent_id: str) -> list[dict]:
        self.item("agent", agent_id)
        with self.connection() as connection:
            return [
                json.loads(row["data"])
                for row in connection.execute(
                    "SELECT data FROM agent_versions WHERE agent_id=? ORDER BY created_at",
                    (agent_id,),
                )
            ]

    def create_experiment(
        self,
        spec: ExperimentCreate,
        idempotency_key: str | None = None,
        *,
        workspace: dict | None = None,
    ) -> dict[str, Any]:
        idempotency_key = self.scoped_key(idempotency_key)
        pinned = {agent["id"]: agent for agent in (workspace or {}).get("execution_agents", [])}
        agents = [
            pinned[value] if value in pinned else self.item("agent", value)
            for value in spec.agent_ids
        ]
        if not workspace and any(agent["config"].get("workspace_categories") for agent in agents):
            raise ValueError(
                "Task-specific analyst profiles run in their supported workspaces; select Scout, Relay or a research HTTP agent for this benchmark."
            )
        tasks = (
            [
                {
                    "id": spec.task_ids[0],
                    "title": workspace["category"].title(),
                    "prompt": workspace["prompt"],
                    "company": "",
                    "reference_time": now(),
                    "source_ids": [],
                }
            ]
            if workspace
            else [self.item("task", value) for value in spec.task_ids]
        )
        scenarios = [self.item("scenario", value) for value in spec.scenario_ids]
        if any(agent["kind"] == "http" for agent in agents):
            if spec.mode == "live" and not workspace:
                raise ValueError(
                    "HTTP adapters receive controlled evidence only; live search coverage is unsupported."
                )
            if spec.scenario_ids != ["normal"]:
                raise ValueError(
                    "HTTP adapters expose final output only; injected faults are unsupported."
                )
            if spec.engine == "fixture":
                raise ValueError(
                    "HTTP adapters require the Bifrost engine selection; their own model usage remains unknown."
                )
        sources = self.catalog("source")
        timestamp = now()
        experiment_id = identifier("exp")
        combinations = list(
            itertools.product(agents, tasks, scenarios, range(1, spec.repetitions + 1))
        )
        seed = random.SystemRandom().randrange(1 << 32)
        random.Random(seed).shuffle(combinations)
        manifest = {
            "version": "1.1",
            "grader_version": "research-evidence-v2",
            "engine": spec.engine,
            "mode": spec.mode,
            "model": spec.model,
            "bifrost_url": self.config.bifrost_url,
            "agent_versions": agents,
            "task_versions": tasks,
            "scenario_versions": scenarios,
            **loaded_identity(),
            "price_basis": price_basis(
                spec.model, self.config.model_pricing, fixture=spec.engine == "fixture"
            ),
            "evidence_hash": digest(sources),
            "agent_hash": digest(agents),
            "task_hash": digest(tasks),
            "scenario_hash": digest(scenarios),
            "order_seed": seed,
            "cache_policy": "request-no-store; provider cache configuration is external",
            "fixture_notice": "Deterministic executable demonstration; no model inference"
            if spec.engine == "fixture"
            else None,
            "sources": [
                item
                for item in sources
                if item["id"] in {s for task in tasks for s in task["source_ids"]}
            ],
        }
        if workspace:
            manifest["agent_price_basis"] = {
                agent["id"]: price_basis(
                    agent["config"].get("model") or spec.model,
                    self.config.model_pricing,
                    fixture=spec.engine == "fixture",
                )
                for agent in agents
            }
            manifest["workspace"] = workspace
            manifest["sources"] = []
            manifest["grader_version"] = "workspace-evidence-v1"
            manifest["workspace_runtime_hash"] = workspace["runtime_hash"]
            manifest["task_versions"] = [
                {
                    "id": spec.task_ids[0],
                    "title": workspace["category"].title(),
                    "prompt": workspace["prompt"],
                    "source_ids": [],
                    "company": "",
                    "reference_time": timestamp,
                }
            ]
            manifest["task_hash"] = digest(
                {
                    "category": workspace["category"],
                    "prompt": workspace["prompt"],
                    "histories": workspace["histories"],
                }
            )
        credits = len(combinations) * spec.limits.max_tool_calls if spec.mode == "live" else 0
        with self.transaction() as connection:
            if workspace and idempotency_key:
                existing_workspace = connection.execute(
                    "SELECT id,manifest FROM experiments WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if existing_workspace:
                    if json.loads(existing_workspace["manifest"]).get("workspace", {}).get(
                        "request_hash"
                    ) != workspace.get("request_hash"):
                        raise ValueError("Idempotency key belongs to a different turn.")
                    return self.experiment(existing_workspace["id"])
            if workspace:
                if (
                    workspace.get("retry_run_id")
                    and connection.execute(
                        "SELECT 1 FROM workspace_retries WHERE run_id=?",
                        (workspace["retry_run_id"],),
                    ).fetchone()
                ):
                    raise ValueError(
                        "This failed attempt already has a retry; reload the conversation."
                    )
                pending = connection.execute(
                    "SELECT 1 FROM workspace_turns t JOIN experiments e ON e.id=t.experiment_id WHERE t.conversation_id=? AND e.state IN ('queued','running')",
                    (workspace["conversation_id"],),
                ).fetchone()
                if pending:
                    raise ValueError(
                        "Wait for the current turn to finish or cancel it before continuing."
                    )
                retry_pending = connection.execute(
                    "SELECT 1 FROM workspace_retries r JOIN experiments e ON e.id=r.experiment_id JOIN workspace_turns t ON t.experiment_id=r.original_id WHERE t.conversation_id=? AND e.state IN ('queued','running')",
                    (workspace["conversation_id"],),
                ).fetchone()
                if retry_pending:
                    raise ValueError("Wait for the failed response retry to finish.")
                count = connection.execute(
                    "SELECT count(*) FROM workspace_turns WHERE conversation_id=?",
                    (workspace["conversation_id"],),
                ).fetchone()[0]
                if count != workspace["previous_turns"]:
                    raise ValueError(
                        "Conversation changed; reload it before sending the next turn."
                    )
            if idempotency_key:
                existing = connection.execute(
                    "SELECT id,spec FROM experiments WHERE idempotency_key=?", (idempotency_key,)
                ).fetchone()
                if existing:
                    if json.loads(existing["spec"]) != spec.model_dump():
                        raise ValueError(
                            "Idempotency key belongs to a different experiment request."
                        )
                    return self.experiment(existing["id"])
            active = connection.execute(
                "SELECT count(*) FROM experiments WHERE state IN ('queued','running')"
            ).fetchone()[0]
            if active >= 10:
                raise ValueError("At most ten experiments can be queued or running.")
            reserved = connection.execute(
                "SELECT coalesce(sum(reserved_credits),0) FROM experiments"
            ).fetchone()[0]
            if credits + reserved > self.config.tavily_credit_limit:
                raise ValueError(
                    "The live-search upper bound exceeds the remaining configured credit allowance."
                )
            connection.execute(
                "INSERT INTO experiments(id,name,state,spec,manifest,created_at,updated_at,total,idempotency_key,reserved_credits) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    experiment_id,
                    spec.name,
                    "queued",
                    spec.model_dump_json(),
                    json.dumps(manifest),
                    timestamp,
                    timestamp,
                    len(combinations),
                    idempotency_key,
                    credits,
                ),
            )
            if workspace:
                if workspace.get("batch_id"):
                    connection.execute(
                        "INSERT INTO suite_batch_cases(batch_id,case_index,experiment_id) VALUES(?,?,?)",
                        (workspace["batch_id"], workspace["suite_case"], experiment_id),
                    )
                if workspace.get("retry_of"):
                    connection.execute(
                        "INSERT INTO workspace_retries(experiment_id,original_id,run_id,created_at) VALUES(?,?,?,?)",
                        (
                            experiment_id,
                            workspace["retry_of"],
                            workspace["retry_run_id"],
                            timestamp,
                        ),
                    )
                else:
                    connection.execute(
                        "INSERT INTO workspace_turns(id,conversation_id,experiment_id,message,created_at) VALUES(?,?,?,?,?)",
                        (
                            workspace["turn_id"],
                            workspace["conversation_id"],
                            experiment_id,
                            workspace["prompt"],
                            timestamp,
                        ),
                    )
            for position, (agent, task, scenario, repetition) in enumerate(combinations):
                run = {
                    "id": identifier("run"),
                    "experiment_id": experiment_id,
                    "agent_id": agent["id"],
                    "agent_name": agent["name"],
                    "model": agent["config"].get("model") or spec.model,
                    "task_id": task["id"],
                    "task_name": task["title"],
                    "scenario_id": scenario["id"],
                    "scenario_name": scenario["name"],
                    "scenario_activated": False,
                    "repetition": repetition,
                    "outcome": "queued",
                    "assessment_status": "inconclusive",
                    "duration_ms": 0,
                    "tool_calls": None if agent["kind"] == "http" else 0,
                    "model_calls": None if agent["kind"] == "http" else 0,
                    "steps": None if agent["kind"] == "http" else 0,
                    "observation_coverage": "final_output_only"
                    if agent["kind"] == "http"
                    else "model_tool_boundaries",
                    "input_tokens": None,
                    "output_tokens": None,
                    "api_cost_usd": 0.0 if spec.engine == "fixture" else None,
                    "tokens_provenance": "not_applicable"
                    if spec.engine == "fixture"
                    else "unknown",
                    "cost_provenance": "not_applicable" if spec.engine == "fixture" else "unknown",
                    "cost_basis": manifest["price_basis"] if agent["kind"] != "http" else None,
                    "output": None,
                    "assessment": {"status": "inconclusive", "checks": []},
                }
                connection.execute(
                    "INSERT INTO runs(id,experiment_id,position,data) VALUES(?,?,?,?)",
                    (run["id"], experiment_id, position, json.dumps(run)),
                )
        self.claim_object("experiment", experiment_id)
        return self.experiment(experiment_id)

    def update_manifest(self, experiment_id: str, manifest: dict) -> None:
        """Worker preparation records a snapshot once, before any agent starts."""
        with self.transaction() as connection:
            current = connection.execute(
                "SELECT manifest FROM experiments WHERE id=?", (experiment_id,)
            ).fetchone()
            if current is None:
                raise KeyError(experiment_id)
            if json.loads(current[0]).get("snapshot"):
                raise ValueError("A prepared snapshot cannot be replaced.")
            if connection.execute(
                "SELECT 1 FROM runs WHERE experiment_id=? AND state!='queued'", (experiment_id,)
            ).fetchone():
                raise ValueError("Snapshot must be prepared before agent execution.")
            connection.execute(
                "UPDATE experiments SET manifest=? WHERE id=?",
                (json.dumps(manifest), experiment_id),
            )

    def experiments(self) -> list[dict[str, Any]]:
        owned = self.owned_ids("experiment")
        if owned is not None:
            return [self.experiment(value, detail=False) for value in owned[:200]]
        with self.connection() as connection:
            ids = [
                row["id"]
                for row in connection.execute(
                    "SELECT id FROM experiments WHERE id NOT IN (SELECT id FROM record_visibility WHERE kind='experiments') ORDER BY created_at DESC LIMIT 200"
                )
            ]
        return [self.experiment(value, detail=False) for value in ids]

    def experiment(self, experiment_id: str, detail: bool = True) -> dict[str, Any]:
        self.require_access("experiment", experiment_id)
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM experiments WHERE id=?", (experiment_id,)
            ).fetchone()
            if row is None:
                raise KeyError(experiment_id)
            runs = [
                json.loads(item["data"])
                for item in connection.execute(
                    "SELECT data FROM runs WHERE experiment_id=? ORDER BY position",
                    (experiment_id,),
                )
            ]
        complete = [item for item in runs if item["outcome"] not in {"queued", "running"}]
        summary = {"passes": 0, "failures": 0, "inconclusive": 0, "infrastructure_errors": 0}
        for item in complete:
            if item["outcome"] in {"infrastructure_error", "interrupted", "adapter_error"}:
                summary["infrastructure_errors"] += 1
            elif item["assessment_status"] == "pass":
                summary["passes"] += 1
            elif item["assessment_status"] == "fail":
                summary["failures"] += 1
            else:
                summary["inconclusive"] += 1
        metrics = []
        manifest = json.loads(row["manifest"])
        for agent in manifest["agent_versions"]:
            attempts = [item for item in complete if item["agent_id"] == agent["id"]]
            assessable = [
                item for item in attempts if item["assessment_status"] in {"pass", "fail"}
            ]
            passed = sum(item["assessment_status"] == "pass" for item in assessable)

            def total(field: str, attempts: list[dict] = attempts) -> int | float | None:
                return (
                    sum(item[field] for item in attempts)
                    if attempts and all(item.get(field) is not None for item in attempts)
                    else None
                )

            metrics.append(
                {
                    "agent_id": agent["id"],
                    "agent_name": agent["name"],
                    "total": len(attempts),
                    "passed": passed,
                    "failed": sum(item["assessment_status"] == "fail" for item in attempts),
                    "inconclusive": sum(
                        item["assessment_status"] == "inconclusive" for item in attempts
                    ),
                    "infrastructure_errors": sum(
                        item["outcome"] in {"infrastructure_error", "interrupted", "adapter_error"}
                        for item in attempts
                    ),
                    "success_rate": passed / len(assessable) if assessable else None,
                    "avg_duration_ms": sum(item["duration_ms"] for item in attempts) / len(attempts)
                    if attempts
                    else 0,
                    "total_tool_calls": total("tool_calls"),
                    "total_model_calls": total("model_calls"),
                    "total_steps": total("steps"),
                    "observation_coverage": "final_output_only"
                    if agent["kind"] == "http"
                    else "model_tool_boundaries",
                    "input_tokens": total("input_tokens"),
                    "output_tokens": total("output_tokens"),
                    "api_cost_usd": total("api_cost_usd"),
                    "tokens_provenance": self._provenance(attempts, "tokens_provenance"),
                    "cost_provenance": self._provenance(attempts, "cost_provenance"),
                    "scenario_exposures": sum(item["scenario_activated"] for item in attempts),
                }
            )
        result = {
            "id": row["id"],
            "name": row["name"],
            "state": row["state"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "spec": json.loads(row["spec"]),
            "progress": {"completed": len(complete), "total": row["total"]},
            "summary": summary,
            "agent_metrics": metrics,
        }
        if manifest.get("workspace") and not manifest.get("snapshot") and complete:
            reason = next(
                (
                    check.get("evidence")
                    for run in complete
                    for check in (run.get("assessment") or {}).get("checks", [])
                    if check.get("name") == "Input preparation"
                ),
                None,
            )
            if reason:
                result["preparation_error"] = reason
        if detail:
            result["manifest"] = manifest
            result["runs"] = [
                {key: value for key, value in item.items() if key not in {"output", "assessment"}}
                for item in runs
            ]
        return result

    @staticmethod
    def _provenance(attempts: list[dict], field: str) -> str:
        values = {item[field] for item in attempts}
        return next(iter(values)) if len(values) == 1 else "unknown"

    def run(self, run_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute("SELECT data FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            result = json.loads(row["data"])
            self.require_access("experiment", result["experiment_id"])
            result["events"] = [
                json.loads(event["data"])
                for event in connection.execute(
                    "SELECT data FROM events WHERE run_id=? ORDER BY sequence", (run_id,)
                )
            ]
        return result

    def update_run(self, run_id: str, values: dict[str, Any]) -> None:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT data,experiment_id FROM runs WHERE id=?", (run_id,)
            ).fetchone()
            data = json.loads(row["data"])
            data.update(redact(values, self.config.secrets))
            connection.execute(
                "UPDATE runs SET data=?,state=? WHERE id=?",
                (json.dumps(data), data["outcome"], run_id),
            )
            connection.execute(
                "UPDATE experiments SET updated_at=? WHERE id=?", (now(), row["experiment_id"])
            )

    def event(
        self,
        run_id: str,
        event_type: str,
        title: str,
        data: dict | None = None,
        duration_ms: float | None = None,
    ) -> None:
        with self.transaction() as connection:
            sequence = connection.execute(
                "SELECT coalesce(max(sequence),0)+1 FROM events WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            event = {
                "sequence": sequence,
                "type": event_type,
                "timestamp": now(),
                "title": title,
                "data": redact(data or {}, self.config.secrets),
                "duration_ms": duration_ms,
            }
            connection.execute(
                "INSERT INTO events(run_id,sequence,data) VALUES(?,?,?)",
                (run_id, sequence, json.dumps(event)),
            )

    def cancelled(self, experiment_id: str) -> bool:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT cancel_requested FROM experiments WHERE id=?", (experiment_id,)
            ).fetchone()
        return bool(row and row[0])

    def cancel(self, experiment_id: str) -> dict:
        self.require_access("experiment", experiment_id)
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT state FROM experiments WHERE id=?", (experiment_id,)
            ).fetchone()
            if not row:
                raise KeyError(experiment_id)
            if row["state"] not in TERMINAL:
                state = "cancelled" if row["state"] == "queued" else row["state"]
                connection.execute(
                    "UPDATE experiments SET cancel_requested=1,state=?,updated_at=? WHERE id=?",
                    (state, now(), experiment_id),
                )
        if row["state"] == "queued":
            self.finish_pending(experiment_id, "cancelled")
        return self.experiment(experiment_id)

    def finish_pending(self, experiment_id: str, outcome: str) -> None:
        with self.connection() as connection:
            ids = [
                row[0]
                for row in connection.execute(
                    "SELECT id FROM runs WHERE experiment_id=? AND state IN ('queued','running')",
                    (experiment_id,),
                )
            ]
        for run_id in ids:
            self.update_run(
                run_id,
                {
                    "outcome": outcome,
                    "assessment_status": "inconclusive",
                    "assessment": {
                        "status": "inconclusive",
                        "checks": [
                            {
                                "name": "Execution coverage",
                                "passed": False,
                                "evidence": f"Attempt {outcome}; no quality claim.",
                            }
                        ],
                    },
                },
            )

    def claim(self, worker_id: str) -> str | None:
        with self.transaction() as connection:
            lock = connection.execute("SELECT * FROM worker_lock WHERE id=1").fetchone()
            if lock and lock["owner"] != worker_id and lock["expires_at"] > time.time():
                return None
            connection.execute(
                "INSERT INTO worker_lock(id,owner,expires_at) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET owner=excluded.owner,expires_at=excluded.expires_at",
                (worker_id, time.time() + 20),
            )
            row = connection.execute(
                "SELECT id FROM experiments WHERE state='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if not row:
                return None
            connection.execute(
                "UPDATE experiments SET state='running',worker_id=?,lease_until=?,updated_at=? WHERE id=?",
                (worker_id, time.time() + 20, now(), row["id"]),
            )
        return row["id"]

    def heartbeat(self, worker_id: str, experiment_id: str | None = None) -> None:
        with self.transaction() as connection:
            connection.execute(
                "UPDATE worker_lock SET expires_at=? WHERE id=1 AND owner=?",
                (time.time() + 20, worker_id),
            )
            if experiment_id:
                connection.execute(
                    "UPDATE experiments SET lease_until=? WHERE id=? AND worker_id=?",
                    (time.time() + 20, experiment_id, worker_id),
                )

    def recover(self) -> int:
        with self.connection() as connection:
            stale = [
                row[0]
                for row in connection.execute(
                    "SELECT id FROM experiments WHERE state='running' AND coalesce(lease_until,0)<?",
                    (time.time(),),
                )
            ]
        for experiment_id in stale:
            self.finish_pending(experiment_id, "interrupted")
            self.finish_experiment(experiment_id, "partial")
        return len(stale)

    def finish_experiment(self, experiment_id: str, state: str) -> None:
        with self.transaction() as connection:
            connection.execute(
                "UPDATE experiments SET state=?,updated_at=?,lease_until=NULL WHERE id=?",
                (state, now(), experiment_id),
            )

    def baselines(self) -> list[dict]:
        with self.connection() as connection:
            return [
                dict(row)
                for row in connection.execute("SELECT * FROM baselines ORDER BY created_at DESC")
                if self.can_access("experiment", row["experiment_id"])
            ]

    def add_baseline(self, experiment_id: str, name: str) -> dict:
        experiment = self.experiment(experiment_id)
        if experiment["state"] != "completed":
            raise ValueError("A baseline must refer to a completed experiment.")
        record = {
            "id": identifier("base"),
            "name": name,
            "experiment_id": experiment_id,
            "created_at": now(),
        }
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO baselines(id,name,experiment_id,created_at) VALUES(?,?,?,?)",
                tuple(record.values()),
            )
        return record

    def experiment_events(self, experiment_id: str, after: int = 0) -> list[dict]:
        self.require_access("experiment", experiment_id)
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT events.rowid AS cursor,events.data,runs.id AS run_id FROM events JOIN runs ON runs.id=events.run_id WHERE runs.experiment_id=? AND events.rowid>? ORDER BY events.rowid LIMIT 500",
                (experiment_id, after),
            )
            return [
                {"cursor": row["cursor"], "run_id": row["run_id"], **json.loads(row["data"])}
                for row in rows
            ]
