"""Optional fixed-endpoint inference providers. Credentials never enter manifests."""

PROVIDERS = {
    "agentrouter": (
        "https://agentrouter.org/v1/chat/completions",
        "agentrouter_key",
        "AgentRouter",
        "AGENTROUTER_API_KEY",
    ),
    "bynara": (
        "https://router.bynara.id/v1/chat/completions",
        "bynara_key",
        "Bynara",
        "BYNARA_API_KEY",
    ),
}


def remote_provider(model: str):
    return PROVIDERS.get(model.split("/", 1)[0])


def connection(config, model: str, gateway: str) -> tuple[str, dict, str]:
    config.require_model(model)
    provider = remote_provider(model)
    if provider:
        endpoint, key_field, label, env_name = provider
        key = getattr(config, key_field)
        if not key:
            raise ValueError(f"Configure {env_name} privately before selecting {label}.")
        return endpoint, {"Authorization": "Bearer " + key}, model.split("/", 1)[1]
    return (
        gateway + "/v1/chat/completions",
        {"x-bf-vk": config.bifrost_key} if config.bifrost_key else {},
        model,
    )
