"""Private content-addressed source storage and immutable bounded snapshots."""

from __future__ import annotations

import hashlib
import json
import re

from .blob_storage import write_blob
from .catalog import digest
from .storage import Store, identifier, now


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class Snapshots:
    def __init__(self, store: Store):
        self.store = store
        self.root = store.config.data_dir / "objects"
        self.root.mkdir(parents=True, exist_ok=True)

    def put_content(self, content: str) -> str:
        encoded = content.encode("utf-8")
        if len(encoded) > 2_000_000:
            raise ValueError("A source exceeds the 2 MB text limit.")
        key = content_hash(content)
        path = self.root / key
        write_blob(self.store, path, encoded)
        return key

    def content(self, key: str) -> str:
        if not re.fullmatch(r"[a-f0-9]{64}", key):
            raise ValueError("Invalid content identifier.")
        value = (self.root / key).read_bytes().decode("utf-8")
        if content_hash(value) != key:
            raise ValueError("Stored source integrity check failed.")
        return value

    def create(self, category: str, sources: list[dict], metadata: dict | None = None) -> dict:
        if len(sources) > 500 or sum(len(item["content"].encode()) for item in sources) > 8_000_000:
            raise ValueError("Snapshot exceeds the source count or total size limit.")
        records = []
        timestamp = now()
        for source in sources:
            record = {key: value for key, value in source.items() if key != "content"}
            record.update(
                id=source.get("id", identifier("src")),
                content_hash=self.put_content(source["content"]),
                retrieved_at=source.get("retrieved_at", timestamp),
            )
            records.append(record)
        value = {
            "id": identifier("snap"),
            "category": category,
            "created_at": timestamp,
            "sources": records,
            "metadata": metadata or {},
            "version": 1,
        }
        value["hash"] = digest(
            {
                "category": category,
                "sources": [
                    {k: v for k, v in s.items() if k not in {"retrieved_at", "id"}} for s in records
                ],
                "metadata": value["metadata"],
            }
        )
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT INTO snapshots(id,data,created_at) VALUES(?,?,?)",
                (value["id"], json.dumps(value), timestamp),
            )
        if self.store.config.hosted:
            from .identity import current_owner

            if current_owner():
                self.store.claim_object("snapshot", str(value["id"]))
        return value

    def get(self, snapshot_id: str, include_content: bool = False) -> dict:
        self.store.require_access("snapshot", snapshot_id)
        with self.store.connection() as connection:
            row = connection.execute(
                "SELECT data FROM snapshots WHERE id=?", (snapshot_id,)
            ).fetchone()
        if row is None:
            raise KeyError(snapshot_id)
        value = json.loads(row[0])
        if include_content:
            for source in value["sources"]:
                source["content"] = self.content(source["content_hash"])
        return value

    def select(self, snapshot_id: str, prompt: str, budget: int = 3000) -> list[dict]:
        """One deterministic selection shared by both agents; absolute lines retained."""
        snapshot = self.get(snapshot_id, True)
        terms = set(re.findall(r"[a-zA-Z_]{3,}", prompt.lower()))
        overview = bool(
            terms
            & {"about", "overview", "summarize", "summary", "explain", "purpose", "architecture"}
        )
        chunks = []
        for source in snapshot["sources"]:
            lines = source["content"].splitlines()
            offset = 0
            while offset < len(lines):
                start = offset
                block: list[str] = []
                while offset < len(lines) and len(block) < 20:
                    line = lines[offset]
                    if len("\n".join([*block, line])) > 1600:
                        break
                    block.append(line)
                    offset += 1
                if not block:
                    offset += 1  # An individual oversized line cannot fit this context.
                    continue
                text = "\n".join(block)
                score = sum(
                    term in (source.get("reference", "") + " " + text).lower() for term in terms
                )
                if source.get("type") == "repository":
                    path = source.get("reference", "")
                    if path.startswith(("src/", "app/", "lib/", "backend/")):
                        score += 4
                    if path.endswith(("pyproject.toml", "package.json", "Cargo.toml")):
                        score += 3
                    if overview and path.lower() in {"readme.md", "readme.txt", "readme"}:
                        score += 12 if start == 0 else 5
                chunks.append((score, source, start, text))
        chunks.sort(key=lambda x: (-x[0], x[1]["id"], x[2]))
        selected: list[dict] = []
        used = 0
        chosen_per_source: dict[str, int] = {}
        for _, source, offset, text in chunks:
            if used + len(text) > budget or len(selected) >= 20:
                continue
            if chosen_per_source.get(source["id"], 0) >= 2:
                continue
            selected.append(
                {
                    **source,
                    "id": f"{source['id']}_{offset + 1}",
                    "source_id": source["id"],
                    "content": text,
                    "start_line": offset + 1,
                    "end_line": offset + len(text.splitlines()),
                    "snapshot_id": snapshot_id,
                }
            )
            used += len(text)
            chosen_per_source[source["id"]] = chosen_per_source.get(source["id"], 0) + 1
        return selected
