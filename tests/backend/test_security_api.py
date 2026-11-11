import json

import pytest
from pydantic import ValidationError
from rilo.config import loopback_url, redact
from rilo.schemas import AgentCreate, ExperimentCreate


def test_auth_cookie_csrf_and_bearer(client, config, payload):
    assert client.get("/api/v1/agents").status_code == 401
    session = client.get("/api/v1/session")
    assert session.status_code == 200
    cookie = session.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert client.get("/api/v1/agents").status_code == 200
    assert client.post("/api/v1/experiments", json=payload).status_code == 403
    headers = {"X-CSRF-Token": session.json()["csrf_token"]}
    assert client.post("/api/v1/experiments", json=payload, headers=headers).status_code == 202
    client.cookies.clear()
    assert (
        client.get(
            "/api/v1/agents", headers={"Authorization": "Bearer " + config.session_key}
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/agents", headers={"Authorization": "Bearer invalid"}).status_code == 401
    )


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://attacker.example"},
        {"Host": "attacker.example"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_session_bootstrap_rejects_untrusted_browser(client, headers):
    assert client.get("/api/v1/session", headers=headers).status_code == 403


def test_payload_size_validation_and_private_settings(client, config, payload):
    session = client.get("/api/v1/session").json()
    headers = {"X-CSRF-Token": session["csrf_token"]}
    assert client.post("/api/v1/tasks", content="x" * 65000, headers=headers).status_code == 413
    payload["name"] = ""
    response = client.post("/api/v1/experiments", json=payload, headers=headers)
    assert response.status_code == 422
    assert "input" not in json.dumps(response.json())
    config.tavily_key = "tvly-secret-private-value"
    config.bifrost_key = "vk-private-test-value"
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    assert config.tavily_key not in response.text
    assert config.bifrost_key not in response.text


@pytest.mark.parametrize(
    "value",
    [
        "http://169.254.169.254:8080",
        "http://192.168.1.1:9000/run",
        "http://localhost:80",
        "http://127.0.0.1:9000/run?secret=1",
        "http://user:password@localhost:9000",
        "file:///tmp/evil",
        "http://localhost.attacker.example:9000",
    ],
)
def test_endpoints_are_explicit_loopback_only(value):
    with pytest.raises(ValueError):
        loopback_url(value)
    with pytest.raises(ValidationError):
        AgentCreate(name="Invalid", endpoint=value)


def test_redaction_preserves_real_usage_counts():
    result = redact(
        {
            "input_tokens": 125,
            "output_tokens": 12,
            "api_cost_usd": 0.1,
            "api_key": "bad",
            "authorization": "bad",
            "text": "token tvly-secret123456",
        }
    )
    assert result["input_tokens"] == 125 and result["output_tokens"] == 12
    assert result["api_key"] == "[redacted]" and result["authorization"] == "[redacted]"
    assert "tvly-secret" not in result["text"]


def test_experiment_limits_and_duplicate_ids(payload):
    payload["agent_ids"] = ["scout", "scout"]
    with pytest.raises(ValidationError):
        ExperimentCreate.model_validate(payload)
    payload["agent_ids"] = ["scout"]
    payload["mode"] = "live"
    with pytest.raises(ValidationError):
        ExperimentCreate.model_validate(payload)


def test_idempotent_creation_and_missing_item(client, payload):
    csrf = client.get("/api/v1/session").json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "repeat-me"}
    first = client.post("/api/v1/experiments", json=payload, headers=headers)
    second = client.post("/api/v1/experiments", json=payload, headers=headers)
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    payload["name"] = "Different payload"
    assert client.post("/api/v1/experiments", json=payload, headers=headers).status_code == 409
    assert client.get("/api/v1/runs/no-such-run").status_code == 404
