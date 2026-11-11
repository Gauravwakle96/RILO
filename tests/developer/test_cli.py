"""Developer regression gates must expose distinct machine-readable exit statuses."""

import json

import httpx
import pytest
from rilo import cli
from rilo.client import RiloClient


@pytest.mark.parametrize("status,expected", [("pass", 0), ("fail", 1), ("inconclusive", 2)])
def test_cli_gate_exit_codes(monkeypatch, capsys, status: str, expected: int):
    def respond(request: httpx.Request):
        assert request.url.path == "/api/v1/comparisons"
        assert json.loads(request.content) == {
            "baseline_id": "exp_ref",
            "candidate_id": "exp_candidate",
        }
        return httpx.Response(
            200, json={"gate": {"status": status, "reasons": ["Measured result"]}}
        )

    monkeypatch.setattr(
        cli,
        "RiloClient",
        lambda *args: RiloClient(token="test", transport=httpx.MockTransport(respond)),
    )
    code = cli.main(
        ["compare", "--baseline", "exp_ref", "--candidate", "exp_candidate", "--require-pass"]
    )
    assert code == expected
    assert json.loads(capsys.readouterr().out)["gate"]["status"] == status


def test_cli_invalid_spec_does_not_queue_work(monkeypatch, capsys, tmp_path):
    calls = []
    monkeypatch.setattr(
        cli,
        "RiloClient",
        lambda *args: RiloClient(
            token="test",
            transport=httpx.MockTransport(
                lambda request: calls.append(request) or httpx.Response(200, json={})
            ),
        ),
    )
    path = tmp_path / "spec.json"
    path.write_text("[]")
    assert cli.main(["run", str(path)]) == 2
    assert not calls
    assert "JSON object" in capsys.readouterr().err


def test_cli_full_demo_is_explicit_fixture_with_full_matrix(monkeypatch, capsys):
    def respond(request: httpx.Request):
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": f"task_{i}"} for i in range(5)])
        spec = json.loads(request.content)
        assert spec["engine"] == "fixture" and spec["mode"] == "controlled"
        assert (
            len(spec["agent_ids"])
            * len(spec["task_ids"])
            * len(spec["scenario_ids"])
            * spec["repetitions"]
            == 120
        )
        return httpx.Response(202, json={"id": "exp_demo", "state": "queued"})

    monkeypatch.setattr(
        cli,
        "RiloClient",
        lambda *args: RiloClient(token="test", transport=httpx.MockTransport(respond)),
    )
    assert cli.main(["demo", "--full"]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "queued"
