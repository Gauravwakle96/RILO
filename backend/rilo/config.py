"""Local configuration, endpoint policy, and redaction."""

from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from dotenv import load_dotenv

from .pricing import ModelPricing, parse_model_pricing_json, validate_model_pricing


def service_url(value: str, *, hosted: bool = False) -> str:
    """Allow loopback services; hosted mode also permits explicit private IPs."""
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("The endpoint port is invalid.") from exc
    host = parsed.hostname or ""
    allowed = host in {"127.0.0.1", "localhost", "::1"}
    if hosted and host == "host.docker.internal":
        allowed = True
    if hosted and not allowed:
        import ipaddress

        try:
            address = ipaddress.ip_address(host)
            allowed = address.is_private and not address.is_unspecified and not address.is_link_local
        except ValueError:
            allowed = False
    if (
        parsed.scheme not in {"http", "https"}
        or not allowed
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or parsed.query
        or port is None
        or not 1024 <= port <= 65535
        or len(value) > 300
    ):
        raise ValueError(
            "Use an explicit loopback or private-network service endpoint."
            if hosted
            else "Use an explicit local endpoint, for example http://127.0.0.1:9000/run."
        )
    return value.rstrip("/")


def loopback_url(value: str) -> str:
    """Strict validator retained for local custom-agent endpoints."""
    return service_url(value)


_SECRET_KEYS = re.compile(
    r"^(?:api_?key|.*_api_?key|token|csrf_token|session_key|secret|password|authorization|cookie)$",
    re.I,
)
_SECRET_VALUE = re.compile(
    r"\b(?:tvly-|sk-|ghp_|github_pat_|AKIA|Bearer\s+)[A-Za-z0-9_\-\.]{8,}", re.I
)


def redact(value: Any, known_secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[redacted]" if _SECRET_KEYS.search(str(key)) else redact(item, known_secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, known_secrets) for item in value]
    if isinstance(value, str):
        result = value[:16000]
        for secret in known_secrets:
            if secret and len(secret) >= 8:
                result = result.replace(secret, "[redacted]")
        return _SECRET_VALUE.sub("[redacted]", result)
    return value


@dataclass
class Config:
    root: Path
    data_dir: Path
    bifrost_url: str = "http://127.0.0.1:8086"
    model: str = "ollama/qwen2.5-coder:7b"
    tavily_key: str = ""
    bifrost_key: str = ""
    github_key: str = ""
    tavily_credit_limit: int = 900
    port: int = 8018
    workspace_input_bytes: int = 6000
    storage_max_bytes: int = 512_000_000
    repository_file_limit: int = 200
    repository_byte_limit: int = 12_000_000
    ocr_language: str = "eng"
    hosted: bool = False
    bind_host: str = "127.0.0.1"
    public_url: str = ""
    allowed_hosts: tuple[str, ...] = ()
    allowed_origins_override: tuple[str, ...] = ()
    model_pricing: ModelPricing = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.model_pricing = validate_model_pricing(self.model_pricing)

    @classmethod
    def load(cls, root: Path | None = None) -> Config:
        project = (root or Path.cwd()).resolve()
        load_dotenv(project / ".env", override=False)
        data = Path(os.environ.get("RILO_DATA_DIR", ".rilo"))
        if not data.is_absolute():
            data = project / data
        data.mkdir(parents=True, exist_ok=True)
        config = cls(
            root=project,
            data_dir=data.resolve(),
            bifrost_url=service_url(
                os.environ.get("RILO_BIFROST_URL", "http://127.0.0.1:8086"),
                hosted=os.environ.get("RILO_HOSTED", "0").lower() in {"1", "true", "yes"},
            ),
            model=os.environ.get("RILO_MODEL", "ollama/qwen2.5-coder:7b"),
            tavily_key=os.environ.get("TAVILY_API_KEY", ""),
            bifrost_key=os.environ.get("BIFROST_API_KEY", ""),
            github_key=os.environ.get("GITHUB_TOKEN", ""),
            tavily_credit_limit=max(0, int(os.environ.get("RILO_TAVILY_CREDIT_LIMIT", "900"))),
            port=int(os.environ.get("RILO_PORT", "8018")),
            workspace_input_bytes=max(
                3000, min(100000, int(os.environ.get("RILO_WORKSPACE_INPUT_BYTES", "6000")))
            ),
            storage_max_bytes=max(
                8_000_000, int(os.environ.get("RILO_STORAGE_MAX_BYTES", "512000000"))
            ),
            repository_file_limit=max(
                40, min(500, int(os.environ.get("RILO_REPOSITORY_FILE_LIMIT", "200")))
            ),
            repository_byte_limit=max(
                2_000_000,
                min(40_000_000, int(os.environ.get("RILO_REPOSITORY_BYTE_LIMIT", "12000000"))),
            ),
            ocr_language=os.environ.get("RILO_OCR_LANGUAGE", "eng"),
            hosted=os.environ.get("RILO_HOSTED", "0").lower() in {"1", "true", "yes"},
            bind_host=os.environ.get("RILO_BIND_HOST", "127.0.0.1"),
            public_url=os.environ.get("RILO_PUBLIC_URL", "").rstrip("/"),
            allowed_hosts=tuple(
                value.strip().lower()
                for value in os.environ.get("RILO_ALLOWED_HOSTS", "").split(",")
                if value.strip()
            ),
            allowed_origins_override=tuple(
                value.strip().rstrip("/")
                for value in os.environ.get("RILO_ALLOWED_ORIGINS", "").split(",")
                if value.strip()
            ),
            model_pricing=parse_model_pricing_json(os.environ.get("RILO_MODEL_PRICING_JSON", "{}")),
        )
        if not re.fullmatch(r"[A-Za-z0-9_+-]{2,32}", config.ocr_language):
            raise ValueError("RILO_OCR_LANGUAGE must be a Tesseract language identifier.")
        if config.hosted:
            if config.bind_host not in {"0.0.0.0", "::"}:
                raise ValueError("Hosted mode requires RILO_BIND_HOST=0.0.0.0 or ::.")
            if not config.public_url.startswith("https://"):
                raise ValueError("Hosted mode requires an HTTPS RILO_PUBLIC_URL.")
            public = urlsplit(config.public_url)
            if not public.hostname or public.path not in {"", "/"} or public.query or public.fragment:
                raise ValueError("RILO_PUBLIC_URL must be an HTTPS origin without a path.")
            if not config.allowed_hosts:
                config.allowed_hosts = (public.hostname.lower(),)
            if not config.allowed_origins_override:
                config.allowed_origins_override = (config.public_url,)
        allowed_origins(config.port)
        saved = data / "settings.json"
        if saved.exists():
            values = json.loads(saved.read_text(encoding="utf-8"))
            config.bifrost_url = service_url(
                values.get("bifrost_url", config.bifrost_url), hosted=config.hosted
            )
            config.model = values.get("model", config.model)
        return config

    @property
    def secrets(self) -> tuple[str, ...]:
        return self.tavily_key, self.bifrost_key, self.github_key, self.session_key

    @property
    def session_key(self) -> str:
        path = self.data_dir / "session.key"
        if not path.exists():
            try:
                with path.open("x", encoding="utf-8") as handle:
                    handle.write(secrets.token_urlsafe(48))
                path.chmod(0o600)
            except FileExistsError:
                pass
        return path.read_text(encoding="utf-8").strip()

    def save(self, bifrost_url: str, model: str) -> None:
        self.bifrost_url = service_url(bifrost_url, hosted=self.hosted)
        self.model = model
        destination = self.data_dir / "settings.json"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"bifrost_url": self.bifrost_url, "model": model}), encoding="utf-8"
        )
        temporary.replace(destination)


def allowed_origins(port: int = 8018) -> set[str]:
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("RILO_PORT must be an integer between 1024 and 65535.")
    return {
        f"http://{host}:{service_port}"
        for host in ("127.0.0.1", "localhost", "[::1]")
        for service_port in (8018, 5187, port)
    }
