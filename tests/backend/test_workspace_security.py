import asyncio
import json

import pytest
from rilo.network import fetch_public


def install_network(monkeypatch, responses):
    connected = []

    class Socket:
        def close(self):
            pass

    def connect(address, timeout):
        connected.append(address)
        return Socket()

    class Connection:
        def __init__(self, *args, **kwargs):
            self.sock = None

        def request(self, *args, **kwargs):
            pass

        def close(self):
            pass

        def getresponse(self):
            return responses.pop(0)

    monkeypatch.setattr("rilo.network.resolve_public", lambda host, port: "93.184.216.34")
    monkeypatch.setattr("socket.create_connection", connect)
    monkeypatch.setattr("http.client.HTTPConnection", Connection)
    return connected


class Response:
    def __init__(self, status=200, data=b"evidence", headers=None):
        self.status = status
        self.data = data
        self.headers = headers or {}

    def getheader(self, key, default=None):
        return self.headers.get(key, default)

    def getheaders(self):
        return list(self.headers.items())

    def read(self, n):
        value, self.data = self.data[:n], self.data[n:]
        return value


def test_fetch_connects_to_validated_ip_and_bounds_body(monkeypatch):
    connections = install_network(monkeypatch, [Response(data=b"source")])
    assert fetch_public("http://example.org")["body"] == b"source"
    assert connections == [("93.184.216.34", 80)]
    install_network(monkeypatch, [Response(data=b"too much")])
    with pytest.raises(ValueError, match="size"):
        fetch_public("http://example.org", limit=3)


def test_redirect_private_destination_and_robots_guard(monkeypatch):
    install_network(monkeypatch, [Response(302, headers={"Location": "http://127.0.0.1/private"})])
    with pytest.raises(ValueError, match="Private"):
        fetch_public("http://example.org")
    connections = install_network(monkeypatch, [Response(302, headers={"Location": "/blocked"})])
    with pytest.raises(ValueError, match="access rules"):
        fetch_public("http://example.org", url_guard=lambda url: not url.endswith("/blocked"))
    assert len(connections) == 1


def test_cross_host_redirect_does_not_forward_private_headers(monkeypatch):
    install_network(monkeypatch, [Response(302, headers={"Location": "http://other.example/"})])
    with pytest.raises(ValueError, match="permitted host"):
        fetch_public(
            "http://example.org", headers={"Authorization": "test"}, allowed_host="example.org"
        )


def test_compressed_response_rejected(monkeypatch):
    install_network(monkeypatch, [Response(headers={"Content-Encoding": "gzip"})])
    with pytest.raises(ValueError, match="Compressed"):
        fetch_public("http://example.org")


@pytest.mark.asyncio
async def test_sandbox_has_no_host_mounts_network_or_dependency_install(monkeypatch):
    from rilo.sandbox import run_tests

    calls = []

    class Input:
        def write(self, data):
            pass

        async def drain(self):
            pass

        def close(self):
            pass

    class Process:
        def __init__(self, args):
            self.returncode = 0
            self.stdin = Input()
            self.stdout = asyncio.StreamReader()
            self.stderr = asyncio.StreamReader()
            self.stdout.feed_data(b"0" if "inspect" in args else b"ran tests")
            self.stdout.feed_eof()
            self.stderr.feed_eof()

        async def wait(self):
            return 0

        def kill(self):
            self.returncode = -1

    async def spawn(*args, **kwargs):
        calls.append(args)
        return Process(args)

    monkeypatch.setenv("RILO_SANDBOX_IMAGE", "python@sha256:" + "a" * 64)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    result = await run_tests(
        [{"reference": "test_sample.py", "content": "import unittest"}], "python-unittest"
    )
    create = calls[0]
    assert "--network=none" in create and "--read-only" in create
    assert "--cap-drop=ALL" in create and "--memory=512m" in create
    assert not any(
        "mount" in arg or arg == "-v" for arg in create[: create.index("python@sha256:" + "a" * 64)]
    )
    assert result["executed"] and result["exit_code"] == 0
    assert calls[-1][1:3] == ("rm", "--force")


@pytest.mark.asyncio
async def test_advisory_evaluator_cannot_claim_verified(store, monkeypatch):
    from rilo.engine import InfrastructureError
    from rilo.semantic_review import review

    finding = {"id": "finding_1", "claim": "Claim", "verification": {"citations": []}}
    experiment = {
        "runs": [{"assessment": {"findings": [finding]}}],
        "manifest": {"bifrost_url": store.config.bifrost_url},
        "spec": {"model": store.config.model},
    }

    async def response(*args, **kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "judgments": [
                                    {
                                        "finding_id": "response_1:finding_1",
                                        "state": "VERIFIED",
                                        "explanation": "Trust me",
                                    }
                                ]
                            }
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr("rilo.semantic_review.bounded_json", response)
    with pytest.raises(InfrastructureError, match="schema"):
        await review(store, experiment)


@pytest.mark.asyncio
async def test_tavily_is_optional_and_captured_once_for_both_agents(store, monkeypatch):
    from rilo.workspace_contracts import ConversationCreate, TurnCreate
    from rilo.workspace_engine import prepare
    from rilo.workspace_store import WorkspaceStore

    calls = []

    async def response(*args, **kwargs):
        calls.append(kwargs["json"])
        return {
            "results": [
                {"title": "Source", "url": "https://example.org", "content": "Captured fact."}
            ],
            "usage": {"credits": 1},
        }

    monkeypatch.setattr("rilo.workspace_engine.bounded_json", response)
    store.config.tavily_key = "test-private-key"
    workspace = WorkspaceStore(store)
    conv = workspace.create(ConversationCreate(title="Search", search_provider="tavily"))
    exp = workspace.turn(conv["id"], TurnCreate(message="Research a fact"))
    manifest = await prepare(store, exp)
    assert len(calls) == 1 and calls[0]["search_depth"] == "basic"
    assert manifest["snapshot"]["metadata"]["search"]["requests"] == 1
    assert manifest["sources"][0]["content"] == "Captured fact."
