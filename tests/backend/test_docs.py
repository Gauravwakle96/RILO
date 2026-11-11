from html.parser import HTMLParser

import pytest


class DocumentAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
        self.inline_scripts = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "script":
            if "src" in values:
                self.urls.append(values["src"])
            else:
                self.inline_scripts.append(values)
        if tag == "link" and values.get("rel") in {"stylesheet", "icon"}:
            self.urls.append(values["href"])


@pytest.mark.parametrize("path", ["/docs", "/redoc"])
def test_local_documentation_uses_only_explicit_self_hosted_assets(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert "Rilo API reference" in response.text
    assert response.headers["content-type"].startswith("text/html")
    policy = response.headers["content-security-policy"]
    assert "script-src 'self'" in policy and "unsafe-eval" not in policy
    parser = DocumentAssets()
    parser.feed(response.text)
    assert not parser.inline_scripts
    assert len(parser.urls) == 3
    for url in parser.urls:
        assert url.startswith("/docs-assets/")
        asset = client.get(url)
        assert asset.status_code == 200
        assert asset.headers["x-content-type-options"] == "nosniff"
        assert len(asset.content) <= 20_000
    script = client.get("/docs-assets/reference.js").text
    assert "textContent" in script and "innerHTML" not in script
    assert 'fetch("/api/v1/session"' in script
    assert 'fetch("/openapi.json"' in script


def test_openapi_schema_is_available_to_local_session_and_excludes_docs_assets(client, config):
    assert client.get("/openapi.json").status_code == 401
    client.get("/api/v1/session")
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    schema = response.json()
    assert "/api/v1/experiments" in schema["paths"]
    assert "/docs" not in schema["paths"] and "/docs-assets/{name}" not in schema["paths"]
    assert "ExperimentCreate" in schema["components"]["schemas"]
    client.cookies.clear()
    assert (
        client.get(
            "/openapi.json", headers={"Authorization": "Bearer " + config.session_key}
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "path",
    [
        "/docs-assets/not-found.js",
        "/docs-assets/private.env",
        "/docs-assets/nested/reference.js",
        "/api/v1/unknown",
    ],
)
def test_unknown_docs_assets_and_api_paths_return_safe_404(client, path):
    client.get("/api/v1/session")
    response = client.get(path)
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "request_error"


def test_documentation_and_schema_reject_untrusted_origins(client):
    for path in ("/docs", "/redoc", "/docs-assets/reference.js", "/openapi.json"):
        assert client.get(path, headers={"Origin": "https://attacker.example"}).status_code == 403
