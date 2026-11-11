"""Install an official, pinned Bifrost binary in this project's private data folder.

Local Ollama needs no paid provider credentials. The gateway still authenticates
inference and administrative access using project-local secrets. The recorded
SHA256 identifies the downloaded artifact; HTTPS is its distribution trust basis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import secrets
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "v2.5.0"


def local_environment(root: Path) -> dict[str, str]:
    """Read simple .env assignments without evaluating code or expanding variables."""
    local_values: dict[str, str] = {}
    path = root / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            name = name.removeprefix("export ").strip()
            if name.isidentifier():
                local_values[name] = value.strip().strip("\"'")
    return {**local_values, **os.environ}


def ensure_gateway_config(root: Path, directory: Path) -> dict[str, str]:
    """Provision a restricted inference key and authenticated bootstrap, preserving settings."""
    environment = local_environment(root)
    model = environment.get("RILO_MODEL", "ollama/qwen2.5-coder:7b")
    if not model.startswith("ollama/"):
        raise ValueError(
            "The gateway helper provisions only local Ollama models. Configure other providers directly."
        )
    assignments = []
    for name, prefix in (("BIFROST_API_KEY", "sk-bf-"), ("BIFROST_SETUP_TOKEN", "")):
        if not environment.get(name):
            environment[name] = prefix + secrets.token_urlsafe(48)
            assignments.append(f"{name}={environment[name]}\n")
    if assignments:
        private_env = root / ".env"
        with private_env.open("a", encoding="utf-8") as handle:
            handle.write("\n# Generated Rilo-local gateway credentials. Keep this file private.\n")
            handle.writelines(assignments)
        private_env.chmod(0o600)
    model_name = model.removeprefix("ollama/")
    config_path = directory / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    config.setdefault("$schema", "https://www.getbifrost.ai/schema")
    config.setdefault("version", 2)
    config.setdefault("setup_token", "env.BIFROST_SETUP_TOKEN")
    client = config.setdefault("client", {})
    client.setdefault("enforce_auth_on_inference", True)
    client.setdefault("disable_content_logging", True)
    providers = config.setdefault("providers", {})
    providers.setdefault(
        "ollama",
        {
            "network_config": {"base_url": "http://127.0.0.1:11434"},
            "keys": [
                {
                    "name": "local-ollama",
                    "value": "local-no-secret",
                    "models": [model_name],
                    "weight": 1.0,
                    "ollama_key_config": {"url": "http://127.0.0.1:11434"},
                }
            ],
        },
    )
    for key in providers["ollama"].get("keys", []):
        if key.get("name") == "local-ollama":
            key.setdefault("ollama_key_config", {"url": "http://127.0.0.1:11434"})
    governance = config.setdefault("governance", {})
    virtual_keys = governance.setdefault("virtual_keys", [])
    if not any(key.get("id") == "rilo-local" for key in virtual_keys):
        virtual_keys.append(
            {
                "id": "rilo-local",
                "name": "Rilo local inference",
                "value": "env.BIFROST_API_KEY",
                "is_active": True,
                "allow_all_providers": False,
                "disable_content_logging": True,
                "provider_configs": [
                    {"provider": "ollama", "allowed_models": [model_name], "key_ids": ["*"]}
                ],
            }
        )
    temporary = config_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, indent=2), encoding="utf-8")
    temporary.replace(config_path)
    print(
        "Local gateway configured with a restricted inference key; credentials stay in the private .env."
    )
    return environment


def download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Rilo-local-setup/0.1"})
    temporary = target.with_suffix(".download")
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(request, timeout=45) as response, temporary.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    temporary.replace(target)
    target.chmod(0o755)
    target.with_suffix(".artifact.json").write_text(
        json.dumps({"url": url, "sha256": digest.hexdigest(), "bytes": size}, indent=2),
        encoding="utf-8",
    )
    print(f"Installed official Bifrost {VERSION}: {size:,} bytes.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", action="store_true", help="Run the local gateway in foreground")
    parser.add_argument("--port", type=int, default=8086)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use a port between 1024 and 65535.")
    machine = platform.machine().lower()
    arch = "arm64" if machine in {"arm64", "aarch64"} else "amd64"
    os_name = {"win32": "windows", "darwin": "darwin", "linux": "linux"}.get(sys.platform)
    if os_name is None:
        print("This operating system is not supported by the setup helper.", file=sys.stderr)
        return 1
    filename = "bifrost-http.exe" if os_name == "windows" else "bifrost-http"
    directory = ROOT / ".rilo" / "bifrost"
    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / filename
    url = f"https://downloads.getmaxim.ai/bifrost/{VERSION}/{os_name}/{arch}/{filename}"
    if not binary.exists():
        try:
            download(url, binary)
        except (OSError, urllib.error.URLError) as exc:
            print(
                f"Bifrost download failed: {type(exc).__name__}. Retry when online.",
                file=sys.stderr,
            )
            return 1
    try:
        environment = ensure_gateway_config(ROOT, directory)
    except (OSError, ValueError, TypeError) as exc:
        print(
            f"Gateway configuration failed ({type(exc).__name__}); review private configuration.",
            file=sys.stderr,
        )
        return 1
    if args.start:
        return subprocess.call(
            [
                str(binary),
                "-host",
                "127.0.0.1",
                "-port",
                str(args.port),
                "-app-dir",
                str(directory),
            ],
            cwd=ROOT,
            env=environment,
        )
    print(f"Gateway ready. Run: python scripts/setup_gateway.py --start --port {args.port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
