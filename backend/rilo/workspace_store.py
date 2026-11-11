"""Conversation persistence layered on the existing experiment queue."""

from __future__ import annotations

import json

from .catalog import digest
from .provenance import implementation_hash
from .schemas import ExperimentCreate
from .storage import Store, identifier, now
from .workspace_contracts import ConversationCreate, TurnCreate


def _implementation_identity() -> str:
    return implementation_hash(
        "workspace_contracts.py",
        "workspace_store.py",
        "snapshots.py",
        "blob_storage.py",
        "workspace_engine.py",
        "verification.py",
        "ingestion.py",
        "documents.py",
        "document_worker.py",
        "websites.py",
        "network.py",
        "sandbox.py",
        "workspace_evaluation.py",
        "repository_checks.py",
        "dependency_checks.py",
        "semantic_review.py",
        "task_checks.py",
        "promptfoo_checks.py",
        "promptfoo_runtime/grade.mjs",
        "promptfoo_runtime/network_guard.mjs",
        "promptfoo_runtime/package.json",
        "promptfoo_runtime/package-lock.json",
    )


_WORKSPACE_RUNTIME_HASH = _implementation_identity()


def runtime_hash() -> str:
    """Loaded process identity; disk edits cannot relabel an older worker."""
    return _WORKSPACE_RUNTIME_HASH


def profiles(store: Store) -> list[dict]:
    values = []
    for item in store.catalog("agent"):
        builtin = item["kind"] != "http"
        tasks = (
            item["config"].get(
                "workspace_categories", ["chat", "repository", "documents", "website", "search"]
            )
            if builtin
            else []
        )
        formats = {
            "chat": ["text", "pdf", "docx", "txt", "markdown"],
            "repository": ["github", "zip"],
            "documents": ["pdf", "docx", "txt", "markdown"],
            "website": ["url"],
            "search": ["text"],
        }
        values.append(
            {
                **item,
                "category": tasks[0] if len(tasks) == 1 else "general" if builtin else "custom",
                "supported_tasks": tasks,
                "input_formats": sorted({format for task in tasks for format in formats[task]}),
                "model_requirements": "JSON-capable chat model via Bifrost"
                if builtin
                else "Existing research HTTP contract",
                "tools": ["snapshot_retrieval", "optional_tavily"] if builtin else [],
                "execution_configuration": {
                    "execution": "sequential",
                    "max_schema_retries": 1 if item["kind"] == "graph" else 0,
                    "input_byte_limit": store.config.workspace_input_bytes,
                },
                "limitations": [
                    "Interpretations require independent verification",
                    "No arbitrary host code execution",
                ]
                if builtin
                else ["Research benchmarks only; paired chat protocol unsupported"],
                "status": "requires_model" if builtin else "benchmark_only",
            }
        )
    return values


class WorkspaceStore:
    def __init__(self, store: Store):
        self.store = store

    def create(self, spec: ConversationCreate) -> dict:
        supported = {p["id"] for p in profiles(self.store) if spec.category in p["supported_tasks"]}
        if any(agent not in supported for agent in spec.agent_ids):
            raise ValueError("Selected agent does not support this workspace task.")
        if spec.search_provider == "tavily" and not self.store.config.tavily_key:
            raise ValueError(
                "Tavily is unavailable. Configure TAVILY_API_KEY privately or choose Search off."
            )
        item = {"id": identifier("conv"), "created_at": now(), **spec.model_dump()}
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT INTO conversations(id,data,created_at) VALUES(?,?,?)",
                (item["id"], json.dumps(item), item["created_at"]),
            )
        self.store.claim_object("conversation", item["id"])
        return item

    def list(self) -> list[dict]:
        owned = self.store.owned_ids("conversation")
        if owned is not None:
            return [self.get(value) for value in owned[:100]]
        with self.store.connection() as connection:
            return [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT data FROM conversations ORDER BY created_at DESC LIMIT 100"
                )
            ]

    def get(self, conversation_id: str) -> dict:
        self.store.require_access("conversation", conversation_id)
        with self.store.connection() as connection:
            row = connection.execute(
                "SELECT data FROM conversations WHERE id=?", (conversation_id,)
            ).fetchone()
            if row is None:
                raise KeyError(conversation_id)
            value = json.loads(row[0])
            turns = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM workspace_turns WHERE conversation_id=? ORDER BY rowid",
                    (conversation_id,),
                )
            ]
        for turn in turns:
            experiment = self.store.experiment(turn["experiment_id"])
            turn["experiment"] = experiment
            turn["runs"] = [self.store.run(run["id"]) for run in experiment["runs"]]
            with self.store.connection() as connection:
                retry_ids = [
                    row[0]
                    for row in connection.execute(
                        "SELECT experiment_id FROM workspace_retries WHERE original_id=? ORDER BY rowid",
                        (experiment["id"],),
                    )
                ]
                turn["artifacts"] = [
                    json.loads(row[0])
                    for row in connection.execute(
                        "SELECT data FROM workspace_artifacts WHERE experiment_id=? AND kind!='report' ORDER BY rowid",
                        (experiment["id"],),
                    )
                ]
            turn["retry_experiments"] = [self.store.experiment(value) for value in retry_ids]
            turn["attempts"] = list(turn["runs"])
            for retry in turn["retry_experiments"]:
                for item in retry["runs"]:
                    replacement = self.store.run(item["id"])
                    turn["attempts"].append(replacement)
                    turn["runs"] = [
                        replacement if r["agent_id"] == replacement["agent_id"] else r
                        for r in turn["runs"]
                    ]
        value["turns"] = turns
        return value

    def retry(self, run_id: str) -> dict:
        """Append a bounded attempt without rewriting a run or exposing its sibling."""
        run = self.store.run(run_id)
        source = self.store.experiment(run["experiment_id"])
        task = source["manifest"].get("workspace")
        if not task or not source["manifest"].get("snapshot"):
            raise ValueError("Retry requires a prepared workspace snapshot; retest input failures.")
        conversation = self.get(task["conversation_id"])
        original_id = task.get("retry_of", source["id"])
        latest = conversation["turns"][-1]
        effective = next((r for r in latest["runs"] if r["id"] == run_id), None)
        if latest["experiment_id"] != original_id or not effective:
            raise ValueError("Only the latest response can be retried before another follow-up.")
        if source["state"] not in {"completed", "partial", "failed", "cancelled"} or run[
            "outcome"
        ] in {"completed", "queued", "running"}:
            raise ValueError("Only a failed or cancelled response can be retried.")
        attempts = [r for r in latest["attempts"] if r["agent_id"] == run["agent_id"]]
        if len(attempts) >= 3:
            raise ValueError("Two response retries allowed; start a new evaluation to continue.")
        if task["runtime_hash"] != runtime_hash():
            raise ValueError("Implementation changed; retest the pair with current conditions.")
        retry_task = {
            **task,
            "retry_of": original_id,
            "retry_run_id": run_id,
            "snapshot_id": source["manifest"]["snapshot"]["id"],
            "previous_turns": len(conversation["turns"]),
            "search_provider": "off",
            "semantic_review": False,
        }
        spec = ExperimentCreate.model_validate(
            {
                **source["spec"],
                "name": source["name"] + " · retry",
                "agent_ids": [run["agent_id"]],
                "mode": "controlled",
                "repetitions": 1,
            }
        )
        return self.store.create_experiment(spec, workspace=retry_task)

    def turn(
        self, conversation_id: str, payload: TurnCreate, idempotency_key: str | None = None
    ) -> dict:
        conversation = self.get(conversation_id)
        request_hash = digest({"conversation_id": conversation_id, **payload.model_dump()})
        if idempotency_key:
            scoped_key = self.store.scoped_key(idempotency_key)
            with self.store.connection() as connection:
                existing = connection.execute(
                    "SELECT id,manifest FROM experiments WHERE idempotency_key=?",
                    (scoped_key,),
                ).fetchone()
            if existing:
                if (
                    json.loads(existing["manifest"]).get("workspace", {}).get("request_hash")
                    != request_hash
                ):
                    raise ValueError("Idempotency key belongs to a different turn.")
                return self.store.experiment(existing["id"])
        if any(len(turn["runs"]) != 2 for turn in conversation["turns"]):
            raise ValueError(
                "Repeated benchmark trials cannot become a chat follow-up. Start a new conversation."
            )
        if len(conversation["turns"]) >= 20:
            raise ValueError("Conversation limit reached; start another conversation.")
        histories: dict[str, list[dict]] = {agent: [] for agent in conversation["agent_ids"]}
        for turn in conversation["turns"]:
            if any(r["state"] in {"queued", "running"} for r in turn["retry_experiments"]):
                raise ValueError("Wait for the failed response retry to finish.")
            if turn["experiment"]["state"] not in {"completed", "partial", "cancelled", "failed"}:
                raise ValueError("Wait for the current turn to finish or cancel it.")
            for agent in histories:
                histories[agent].append({"role": "user", "content": turn["message"]})
                run = next((r for r in turn["runs"] if r["agent_id"] == agent), None)
                if run and run.get("output"):
                    histories[agent].append(
                        {"role": "assistant", "content": json.dumps(run["output"])}
                    )
        if any(
            sum(len(message["content"].encode()) for message in history)
            > self.store.config.workspace_input_bytes - 2500
            for history in histories.values()
        ):
            raise ValueError("Conversation context limit reached; start another conversation.")
        snapshot_id = payload.snapshot_id
        if (
            not snapshot_id
            and conversation["turns"]
            and not (payload.inputs.url or payload.inputs.upload_ids or payload.inputs.text)
        ):
            snapshot_id = (
                conversation["turns"][-1]["experiment"]["manifest"].get("snapshot", {}).get("id")
            )
        if snapshot_id:
            from .snapshots import Snapshots

            Snapshots(self.store).get(snapshot_id)
        elif conversation["category"] == "repository" and not (
            payload.inputs.url or payload.inputs.upload_ids
        ):
            raise ValueError("Repository analysis requires a GitHub URL or a repository ZIP.")
        elif conversation["category"] == "documents" and not payload.inputs.upload_ids:
            raise ValueError("Document analysis requires an uploaded document.")
        elif conversation["category"] == "website" and not payload.inputs.url:
            raise ValueError("Website analysis requires a public website URL.")
        workspace = {
            "checks": [check.model_dump() for check in payload.checks],
            "request_hash": request_hash,
            "semantic_review": conversation.get("semantic_review", False),
            "category": conversation["category"],
            "prompt": payload.message,
            "inputs": payload.inputs.model_dump(),
            "snapshot_id": snapshot_id,
            "conversation_id": conversation_id,
            "turn_id": identifier("turn"),
            "histories": histories,
            "search_provider": conversation["search_provider"],
            "runtime_hash": runtime_hash(),
            "previous_turns": len(conversation["turns"]),
        }
        spec = ExperimentCreate(
            name=f"{conversation['title'][:110]} · {len(conversation['turns']) + 1}",
            agent_ids=conversation["agent_ids"],
            task_ids=[
                "workspace_"
                + digest({"category": conversation["category"], "prompt": payload.message})[:16]
            ],
            scenario_ids=["normal"],
            repetitions=1,
            engine="bifrost",
            mode="live" if conversation["search_provider"] == "tavily" else "controlled",
            model=conversation["model"],
            limits=conversation["limits"],
        )
        return self.store.create_experiment(spec, idempotency_key, workspace=workspace)

    def artifact(self, experiment_id: str, kind: str, data: dict) -> dict:
        self.store.require_access("experiment", experiment_id)
        value = {
            "id": identifier("artifact"),
            "experiment_id": experiment_id,
            "kind": kind,
            "created_at": now(),
            "data": data,
            "hash": digest(data),
        }
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT INTO workspace_artifacts(id,experiment_id,kind,data,created_at) VALUES(?,?,?,?,?)",
                (value["id"], experiment_id, kind, json.dumps(value), value["created_at"]),
            )
        self.store.claim_object("artifact", str(value["id"]))
        return value
