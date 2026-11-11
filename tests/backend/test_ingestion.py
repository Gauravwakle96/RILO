import io
import json
import zipfile

import pytest
from rilo.documents import extract
from rilo.ingestion import (
    archive_files,
    github_repository,
    repository_sources,
    safe_path,
    save_upload,
)
from rilo.network import public_url, resolve_public
from rilo.websites import crawl


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://169.254.169.254",
        "http://10.0.0.1",
        "http://[::1]",
        "file:///etc/passwd",
        "http://localhost",
        "http://example.com:8080",
        "https://user:password@example.com",
        "http://example.local",
    ],
)
def test_public_url_blocks_private_and_unsafe_destinations(url):
    with pytest.raises(ValueError):
        public_url(url)


def test_dns_checks_every_address(monkeypatch):
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *args, **kwargs: [
            (2, 1, 6, "", ("93.184.216.34", 443)),
            (2, 1, 6, "", ("127.0.0.1", 443)),
        ],
    )
    with pytest.raises(ValueError, match="nonpublic"):
        resolve_public("example.org", 443)


def make_zip(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return output.getvalue()


@pytest.mark.parametrize(
    "name",
    ["../outside.py", "/absolute.py", "C:/Windows/file", "safe/../../escape", "safe\\escape.py"],
)
def test_archive_rejects_traversal(name):
    with pytest.raises(ValueError):
        safe_path(name)
    if "\\" in name:
        return  # Windows ZipInfo normalizes this separator when creating a fixture.
    with pytest.raises(ValueError):
        archive_files(make_zip({name: "data"}))


def test_zip_and_repository_capture_real_text(store):
    data = make_zip(
        {"src/main.py": "print('hello')\n", "node_modules/a.js": "skip", "image.png": b"\x00"}
    )
    upload = save_upload(store, "repository.zip", data)
    sources, metadata = repository_sources(archive_files(data))
    assert upload["size"] == len(data)
    assert sources == [
        {
            "reference": "src/main.py",
            "title": "src/main.py",
            "type": "repository",
            "content": "print('hello')\n",
        }
    ]
    assert metadata["files_captured"] == 1


def test_pdf_keeps_actual_page_numbers():
    from reportlab.pdfgen import canvas

    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.drawString(40, 700, "First page evidence.")
    pdf.showPage()
    pdf.drawString(40, 700, "Second page evidence.")
    pdf.save()
    sources = extract("two-pages.pdf", ".pdf", output.getvalue())
    assert [s["page"] for s in sources] == [1, 2]
    assert "Second page evidence" in sources[1]["content"]
    with pytest.raises(ValueError):
        extract("broken.pdf", ".pdf", b"%PDF-invalid")


def test_scanned_pdf_uses_bounded_ocr_and_keeps_page_number(monkeypatch):
    from reportlab.pdfgen import canvas

    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.rect(40, 650, 120, 30, fill=1)
    pdf.save()
    monkeypatch.setattr("rilo.documents._ocr_pdf", lambda data, pages, language: {1: "Scanned evidence"})
    sources = extract("scan.pdf", ".pdf", output.getvalue())
    assert sources[0]["page"] == 1
    assert sources[0]["content"] == "Scanned evidence"
    assert sources[0]["extraction_method"] == "ocr"


def test_docx_has_line_evidence_without_invented_pages():
    data = make_zip(
        {
            "word/document.xml": '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Contract clause.</w:t></w:r></w:p></w:body></w:document>'
        }
    )
    sources = extract("contract.docx", ".docx", data)
    assert sources[0]["page"] is None
    assert sources[0]["content"] == "Contract clause."


@pytest.mark.asyncio
async def test_github_pins_commit_and_blob_paths(monkeypatch):
    import base64

    called = []

    async def fetch(url, **kwargs):
        called.append(url)
        if "/git/blobs/" in url:
            body = {
                "encoding": "base64",
                "content": base64.b64encode(b"def app():\n    return 1\n").decode(),
            }
        elif "/git/trees/" in url:
            body = {
                "truncated": False,
                "tree": [
                    {
                        "type": "blob",
                        "mode": "100644",
                        "path": "src/app.py",
                        "size": 24,
                        "sha": "b" * 40,
                    }
                ],
            }
        elif "/commits/" in url:
            body = {"sha": "a" * 40}
        else:
            body = {"default_branch": "main"}
        return {"status": 200, "body": json.dumps(body).encode()}

    monkeypatch.setattr("rilo.ingestion.fetch", fetch)
    sources, metadata = await github_repository("https://github.com/test/project", "test-token")
    assert metadata["commit_sha"] == "a" * 40
    assert sources[0]["reference"] == "src/app.py"
    assert any("a" * 40 in url for url in called)


@pytest.mark.asyncio
async def test_github_large_capture_respects_file_and_byte_limits(monkeypatch):
    import base64

    async def fetch(url, **kwargs):
        if "/git/blobs/" in url:
            body = {"encoding": "base64", "content": base64.b64encode(b"12345").decode()}
        elif "/git/trees/" in url:
            body = {
                "truncated": False,
                "tree": [
                    {"type": "blob", "mode": "100644", "path": f"src/{index}.py", "size": 5, "sha": f"{index:040x}"}
                    for index in range(80)
                ],
            }
        elif "/commits/" in url:
            body = {"sha": "a" * 40}
        else:
            body = {"default_branch": "main"}
        return {"status": 200, "body": json.dumps(body).encode()}

    monkeypatch.setattr("rilo.ingestion.fetch", fetch)
    sources, metadata = await github_repository(
        "https://github.com/test/large", "test-token", file_limit=50, byte_limit=125
    )
    assert len(sources) == 25
    assert metadata["candidate_files"] == 80
    assert metadata["selected_bytes"] == 125
    assert metadata["omitted_candidate_files"] == 55


@pytest.mark.asyncio
async def test_website_respects_robots_and_bounds(monkeypatch):
    calls = []

    async def fetch(url, **kwargs):
        calls.append(url)
        if url.endswith("robots.txt"):
            return {"status": 200, "body": b"User-agent: *\nDisallow: /private"}
        return {
            "url": url,
            "status": 200,
            "headers": {"Content-Type": "text/html"},
            "body": b'<title>Example</title><p>Captured fact.</p><script>evil()</script><a href="/private">Private</a><a href="/about">About</a>',
        }

    monkeypatch.setattr("rilo.websites.fetch", fetch)
    sources, metadata = await crawl("https://example.org", 2, 1)
    assert len(sources) == 2
    assert "evil()" not in sources[0]["content"]
    assert "https://example.org/private" not in calls
    assert metadata["skipped"][0]["reason"].startswith("robots")
