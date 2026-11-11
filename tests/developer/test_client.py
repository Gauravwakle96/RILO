"""SDK trust boundaries and real API orchestration contracts."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from rilo.api import create_app
from rilo.client import RiloClient, RiloError
from rilo.config import Config
from rilo.storage import Store
from rilo.worker import worker


def sdk(handler) -> RiloClient:
    return RiloClient(token="local-test-key", transport=httpx.MockTransport(handler))


def test_sdk_requires_private_key_and_local_endpoint(tmp_path: Path):
    with pytest.raises(RiloError, match="Start the local"):
        RiloClient(data_dir=tmp_path)
    with pytest.raises(ValueError, match="explicit local"):
        RiloClient("https://external.example:8018", token="test")
    with pytest.raises(RiloError, match="empty"):
        RiloClient(token="")


@pytest.mark.parametrize(
    "path",
    [
        "https://external.example",
        "//external.example",
        "../health",
        "agents/../../health",
        "%2e%2e/health",
        "agents?key=secret",
        "agents#fragment",
        "\\external.example",
        "",
    ],
)
def test_sdk_does_not_send_auth_outside_relative_api_routes(path: str):
    calls = []
    with sdk(lambda request: calls.append(request) or httpx.Response(200, json={})) as client:
        with pytest.raises(RiloError, match="relative API routes"):
            client.request("GET", path)
    assert not calls


def test_sdk_applies_local_auth_and_preserves_unknown_metrics():
    def respond(request: httpx.Request):
        assert str(request.url) == "http://127.0.0.1:8018/api/v1/experiments"
        assert request.headers["authorization"] == "Bearer local-test-key"
        assert request.headers["idempotency-key"] == "same-work"
        assert json.loads(request.content)["name"] == "SDK check"
        return httpx.Response(
            202, json={"id": "exp_test", "input_tokens": None, "api_cost_usd": None}
        )

    with sdk(respond) as client:
        result = client.run({"name": "SDK check"}, idempotency_key="same-work")
    assert result["input_tokens"] is None and result["api_cost_usd"] is None


def test_sdk_redirect_and_malformed_success_are_errors():
    with sdk(
        lambda _: httpx.Response(302, headers={"location": "https://external.example"})
    ) as client:
        with pytest.raises(RiloError, match="HTTP 302"):
            client.agents()
    for content in (b"invalid json", b"42"):
        with sdk(lambda _, content=content: httpx.Response(200, content=content)) as client:
            with pytest.raises(RiloError, match="invalid"):
                client.agents()


def test_sdk_wait_handles_terminal_states_and_timeout(monkeypatch):
    responses = iter([{"state": "queued"}, {"state": "running"}, {"state": "partial"}])
    with sdk(lambda _: httpx.Response(200, json=next(responses))) as client:
        monkeypatch.setattr("rilo.client.time.sleep", lambda _: None)
        assert client.wait("exp_test")["state"] == "partial"
    moments = iter([0, 1])
    with sdk(lambda _: httpx.Response(200, json={"state": "running"})) as client:
        monkeypatch.setattr("rilo.client.time.monotonic", lambda: next(moments))
        with pytest.raises(RiloError, match="remains visible"):
            client.wait("exp_test", timeout=0.5)


@pytest.mark.parametrize("timeout,interval", [(0, 1), (1, 0), (float("nan"), 1), (1, float("inf"))])
def test_sdk_wait_rejects_unbounded_or_invalid_timing(timeout: float, interval: float):
    with sdk(lambda _: httpx.Response(200, json={})) as client:
        with pytest.raises(ValueError):
            client.wait("exp_test", timeout=timeout, interval=interval)


def test_sdk_export_preserves_full_api_report_and_rejects_bad_id(tmp_path: Path):
    report = {"runs": [{"id": f"run_{i}"} for i in range(120)]}
    destination = tmp_path / "reports" / "all.json"
    with sdk(lambda _: httpx.Response(200, json=report)) as client:
        client.export("exp_test", destination)
        with pytest.raises(RiloError):
            client.export("../session", destination)
        with pytest.raises(ValueError):
            client.export("exp_test", destination, format="html")
    assert len(json.loads(destination.read_bytes())["runs"]) == 120


def test_sdk_real_api_run_report_baseline_compare_cancel(tmp_path: Path):
    data = tmp_path / ".rilo"
    data.mkdir()
    config = Config(root=tmp_path, data_dir=data)
    store = Store(config)
    with TestClient(create_app(config)) as server:

        def forward(request: httpx.Request) -> httpx.Response:
            response = server.request(
                request.method,
                str(request.url),
                headers=dict(request.headers),
                content=request.content,
            )
            return httpx.Response(
                response.status_code, headers=dict(response.headers), content=response.content
            )

        with RiloClient(data_dir=data, transport=httpx.MockTransport(forward)) as client:
            spec = {
                "name": "SDK integration",
                "agent_ids": ["relay"],
                "task_ids": ["company_brief"],
                "scenario_ids": ["normal", "search_timeout"],
                "repetitions": 3,
                "engine": "fixture",
                "mode": "controlled",
            }
            reference = client.run(spec, idempotency_key="sdk-reference")
            assert client.run(spec, idempotency_key="sdk-reference")["id"] == reference["id"]
            asyncio.run(worker(store, once=True))
            reference = client.wait(reference["id"])
            assert reference["state"] == "completed"
            assert reference["summary"]["passes"] == 6
            baseline = client.baseline(reference["id"], "SDK baseline")
            assert baseline["experiment_id"] == reference["id"]
            candidate = client.run({**spec, "name": "SDK candidate"})
            asyncio.run(worker(store, once=True))
            assert client.compare(reference["id"], candidate["id"])["gate"]["status"] == "pass"
            destination = tmp_path / "report.json"
            client.export(reference["id"], destination)
            exported = json.loads(destination.read_bytes())
            assert len(exported["runs"]) == 6
            assert all(run["events"] for run in exported["runs"])
            assert config.session_key not in destination.read_text()
            pending = client.run({**spec, "name": "Cancel check"})
            assert client.cancel(pending["id"])["state"] == "cancelled"
            assert (
                client.compare(reference["id"], pending["id"])["gate"]["status"] == "inconclusive"
            )
