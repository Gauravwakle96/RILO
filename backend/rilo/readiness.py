"""Read-only dependency checks. Reachability never promises inference success."""

from __future__ import annotations

import asyncio
import time

import httpx

from .engine import InfrastructureError, bounded_json
from .model_providers import connection as provider_connection
from .model_providers import remote_provider
from .promptfoo_checks import availability
from .schemas import StrictModel
from .workspace_contracts import ConversationCreate


class PreflightInput(StrictModel):
    configuration: ConversationCreate
    require_checks: bool = False
    test_inference: bool = False


async def readiness(store, payload: PreflightInput) -> dict:
    store.config.refresh_settings()
    ids = (
        [slot.agent_id for slot in payload.configuration.slots]
        if payload.configuration.slots
        else payload.configuration.agent_ids
    )
    selected = [store.item("agent", agent_id) for agent_id in ids]
    models = [
        (
            (payload.configuration.slots[index].model if payload.configuration.slots else None)
            or payload.configuration.model
        )
        for index, agent in enumerate(selected)
        if agent["kind"] != "http"
    ]
    model_required = bool(models)
    remote_only = bool(models) and all(remote_provider(model) for model in models)

    async def gateway():
        if not model_required:
            return {
                "name": "Model gateway",
                "ready": None,
                "detail": "Selected HTTP agents run their own inference. Rilo model services are not required.",
            }
        if remote_only:
            return {
                "name": "External model provider",
                "ready": all(
                    bool(getattr(store.config, remote_provider(model)[1])) for model in models
                )
                and not store.config.offline,
                "detail": "Credential configured; use Test inference to validate authentication."
                if all(bool(getattr(store.config, remote_provider(model)[1])) for model in models)
                and not store.config.offline
                else "Configure the private key or turn off Offline mode.",
            }
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
        if not any(model.startswith("ollama/") for model in models):
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
            expected_models = [
                model.removeprefix("ollama/") for model in models if model.startswith("ollama/")
            ]
            expected = ", ".join(expected_models)
            available = all(
                any(
                    isinstance(item, dict) and name in {item.get("name"), item.get("model")}
                    for item in listing.get("models", [])
                )
                for name in expected_models
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
    for agent in selected:
        if agent["kind"] == "http":
            checks.append(
                {
                    "name": agent["name"] + " adapter",
                    "ready": False if store.config.offline else None,
                    "detail": "Offline mode disables adapters whose external tool access is unobserved."
                    if store.config.offline
                    else "The loopback endpoint must implement workspace-v1. Its response schema is validated during the actual task; reachability is not proof of protocol support.",
                }
            )
    if not remote_only and any(remote_provider(model) for model in models):
        checks.append(
            {
                "name": "External model provider",
                "ready": all(
                    bool(getattr(store.config, remote_provider(model)[1]))
                    for model in models
                    if remote_provider(model)
                )
                and not store.config.offline,
                "detail": "Credential configured; Test inference validates authentication."
                if all(
                    bool(getattr(store.config, remote_provider(model)[1]))
                    for model in models
                    if remote_provider(model)
                )
                else "Set the selected provider API key privately before selecting this model.",
            }
        )
    if store.config.offline and any(not model.startswith("ollama/") for model in models):
        checks.append(
            {
                "name": "Offline policy",
                "ready": False,
                "detail": "Offline mode permits only local Ollama inference.",
            }
        )
    if payload.test_inference:
        for model in sorted(set(models)):
            ready = False
            detail = ""
            try:
                store.config.require_model(model)
                endpoint, headers, requested_model = provider_connection(
                    store.config, model, store.config.bifrost_url
                )
                async with httpx.AsyncClient(
                    timeout=45, trust_env=False, follow_redirects=False
                ) as client:
                    result = await bounded_json(
                        client,
                        "POST",
                        endpoint,
                        headers=headers,
                        json={
                            "model": requested_model,
                            "messages": [
                                {"role": "user", "content": 'Return JSON {"status":"ok"}.'}
                            ],
                            "max_tokens": 100,
                            "temperature": 0,
                        },
                    )
                ready = bool(result.get("choices"))
                detail = (
                    "Actual inference returned a response."
                    if ready
                    else "No response choices were returned."
                )
            except (InfrastructureError, ValueError) as exc:
                detail = str(exc)
            checks.append({"name": "Inference · " + model, "ready": ready, "detail": detail})
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
                "ready": bool(store.config.tavily_key) and not store.config.offline,
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
