"""Process-start hashes of fixed, nonsecret application implementation files."""

from __future__ import annotations

import copy
import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path

HASH_FIELDS = ("agent_runtime_hash", "grader_hash", "runtime_hash")
PACKAGE_DIR = Path(__file__).resolve().parent


def implementation_hash(*names: str) -> str:
    content = {
        name: hashlib.sha256((PACKAGE_DIR / name).read_bytes()).hexdigest() for name in names
    }
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


_DEPENDENCIES = {name: version(name) for name in ("httpx", "pydantic", "langgraph")}
_DEPENDENCIES["python"] = platform.python_version()
_IDENTITY = {
    "agent_runtime_hash": implementation_hash("agents.py"),
    "grader_hash": implementation_hash("evaluation.py"),
    "runtime_hash": hashlib.sha256(
        json.dumps(
            {
                "files": implementation_hash(
                    "engine.py",
                    "worker.py",
                    "config.py",
                    "schemas.py",
                    "storage.py",
                    "pricing.py",
                    "provenance.py",
                ),
                "dependencies": _DEPENDENCIES,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest(),
    "runtime_dependencies": _DEPENDENCIES,
}


def loaded_identity() -> dict:
    """Captured once for this process; later disk edits cannot relabel loaded code."""
    return copy.deepcopy(_IDENTITY)


def builtin_metadata(agent: dict) -> dict:
    result = dict(agent)
    if agent.get("id") in {"scout", "relay"} and agent.get("kind") in {"plain", "graph"}:
        result["implementation_hash"] = _IDENTITY["agent_runtime_hash"]
        result["implementation_hash_scope"] = "builtin agents.py source at process start"
    elif agent.get("kind") == "http":
        result["implementation_hash"] = None
        result["implementation_hash_scope"] = (
            "unobserved HTTP implementation; version is user declared"
        )
    elif agent.get("config", {}).get("workspace_categories"):
        result["implementation_hash"] = implementation_hash("workspace_engine.py")
        result["implementation_hash_scope"] = (
            "workspace profile engine; pinned workspace runtime identity at admission"
        )
    return result
