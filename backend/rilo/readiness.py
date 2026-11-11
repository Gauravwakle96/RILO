"""Read-only dependency checks. Reachability never promises inference success."""

from __future__ import annotations

import asyncio
import time

import httpx

from .engine import InfrastructureError, bounded_json
from .promptfoo_checks import availability
from .schemas import StrictModel
from .workspace_contracts import ConversationCreate


class PreflightInput(StrictModel):
    configuration: ConversationCreate
    require_checks: bool = False


async def readiness(store, payload: PreflightInput) -> dict:
    async def gateway():
        try:
            async with httpx.AsyncClient(
                timeout=3, trust_env=False, follow_redirects=False
            ) as client:
                await bounded_json(client, "GET", store.config.bifrost_url + "/health")
            return {
                "name": "Model gateway",
                "ready": True,
                "detail": "Bifrost is reachable. Inference and credentials are validated during execution.",
            }
        except InfrastructureError as exc:
            return {
                "name": "Model gateway",
                "ready": False,
                "detail": f"Start the configured local Bifrost gateway. {exc}",
            }

    async def local_model():
        if not payload.configuration.model.startswith("ollama/"):
            return {
                "name": "Model availability",
                "ready": None,
                "detail": "External model availability will be checked by Bifrost during execution.",
            }
        try:
            async with httpx.AsyncClient(
                timeout=3, trust_env=False, follow_redirects=False
            ) as client:
                listing = await bounded_json(client, "GET", "http://127.0.0.1:11434/api/tags")
            expected = payload.configuration.model.removeprefix("ollama/")
            available = any(
                isinstance(item, dict) and expected in {item.get("name"), item.get("model")}
                for item in listing.get("models", [])
            )
            return {
                "name": "Local model",
                "ready": available,
                "detail": f"{expected} is installed."
                if available
                else f"The selected model {expected} is not listed by Ollama. Install it or select an installed model in Settings.",
            }
        except (InfrastructureError, TypeError):
            return {
                "name": "Local model",
                "ready": False,
                "detail": "Ollama is unavailable or its model list could not be read. Start Ollama and check Settings.",
            }

    checks = list(await asyncio.gather(gateway(), local_model()))
    with store.connection() as connection:
        lease = connection.execute("SELECT expires_at FROM worker_lock WHERE id=1").fetchone()
    worker_ready = bool(lease and lease[0] > time.time())
    checks.append(
        {
            "name": "Background worker",
            "ready": worker_ready,
            "detail": "Worker lease is active."
            if worker_ready
            else "No active worker heartbeat. Start Rilo using START_RILO.cmd before submitting.",
        }
    )
    if payload.require_checks:
        status = availability()
        checks.append(
            {"name": "Promptfoo checks", "ready": status["available"], "detail": status["detail"]}
        )
    if payload.configuration.search_provider == "tavily":
        checks.append(
            {
                "name": "Tavily",
                "ready": bool(store.config.tavily_key),
                "detail": "Key configured; live retrieval is validated during the run."
                if store.config.tavily_key
                else "Choose Search off or configure TAVILY_API_KEY privately.",
            }
        )
    return {
        "ready": all(check["ready"] is not False for check in checks),
        "checks": checks,
        "scope": "Dependency readiness only. Source size, permissions and inference can still fail during execution.",
    }
