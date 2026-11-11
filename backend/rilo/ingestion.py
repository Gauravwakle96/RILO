"""Bounded source ingestion; repository and document contents are data, never code."""

from __future__ import annotations

import base64
import io
import json
import re
import stat
import zipfile
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from .network import fetch, public_url
from .storage import Store, identifier, now

TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".md",
    ".txt",
    ".rs",
    ".go",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".cs",
    ".rb",
    ".php",
    ".sql",
    ".sh",
    ".html",
    ".css",
    ".xml",
    ".ini",
    ".cfg",
    ".example",
    ".lock",
}
SKIP_PARTS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".next",
    "vendor",
}


def safe_path(name: str) -> str:
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or ":" in name
        or "\x00" in name
        or path.is_absolute()
        or any(part in {"..", "."} for part in name.split("/"))
        or len(name) > 300
    ):
        raise ValueError("Archive contains an unsafe file path.")
    return str(path)


def archive_files(data: bytes) -> dict[str, bytes]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        entries = archive.infolist()
        if len(entries) > 2000 or sum(e.file_size for e in entries) > 30_000_000:
            raise ValueError("Archive exceeds file count or expanded size limits.")
        files = {}
        for entry in entries:
            path = safe_path(entry.filename.rstrip("/"))
            mode = entry.external_attr >> 16
            if (
                stat.S_ISLNK(mode)
                or entry.flag_bits & 1
                or entry.file_size > 2_000_000
                or entry.file_size / max(1, entry.compress_size) > 200
            ):
                raise ValueError(
                    "Archive contains a link, encrypted file or excessive compression."
                )
            if entry.is_dir():
                continue
            if path in files:
                raise ValueError("Archive contains duplicate paths.")
            files[path] = archive.read(entry)
        return files
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise ValueError("Invalid or unsupported ZIP archive.") from exc


def save_upload(store: Store, filename: str, data: bytes) -> dict:
    filename = unquote(filename)
    if (
        not filename
        or PurePosixPath(filename).name != filename
        or "\\" in filename
        or ":" in filename
        or len(filename) > 180
    ):
        raise ValueError("Use a simple filename without path components.")
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix not in {".zip", ".pdf", ".docx", ".txt", ".md"} or not data or len(data) > 8_000_000:
        raise ValueError("Upload a nonempty ZIP, PDF, DOCX, TXT or Markdown file up to 8 MB.")
    if suffix in {".zip", ".docx"}:
        archive_files(data)
    if suffix == ".pdf" and not data.startswith(b"%PDF-"):
        raise ValueError("The file does not contain a PDF header.")
    import hashlib

    key = hashlib.sha256(data).hexdigest()
    root = store.config.data_dir / "uploads"
    root.mkdir(exist_ok=True)
    path = root / key
    from .blob_storage import write_blob

    write_blob(store, path, data)
    value = {
        "id": identifier("upload"),
        "name": filename,
        "hash": key,
        "size": len(data),
        "type": suffix,
        "created_at": now(),
    }
    with store.transaction() as connection:
        connection.execute(
            "INSERT INTO uploads(id,data,created_at) VALUES(?,?,?)",
            (value["id"], json.dumps(value), value["created_at"]),
        )
    return value


def load_upload(store: Store, upload_id: str) -> tuple[dict, bytes]:
    import hashlib

    with store.connection() as connection:
        row = connection.execute("SELECT data FROM uploads WHERE id=?", (upload_id,)).fetchone()
    if not row:
        raise KeyError(upload_id)
    item = json.loads(row[0])
    data = (store.config.data_dir / "uploads" / item["hash"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != item["hash"]:
        raise ValueError("Uploaded content integrity check failed.")
    return item, data


def repository_sources(files: dict[str, bytes]) -> tuple[list[dict], dict]:
    sources: list[dict] = []
    skipped: list[str] = []
    total = 0
    for path, data in sorted(files.items()):
        parts = PurePosixPath(path).parts
        if any(part in SKIP_PARTS for part in parts) or (
            PurePosixPath(path).suffix.lower() not in TEXT_SUFFIXES
            and PurePosixPath(path).name not in {"Dockerfile", "Makefile", "LICENSE"}
        ):
            skipped.append(path)
            continue
        if len(data) > 200000 or len(sources) >= 300 or total + len(data) > 6_000_000:
            skipped.append(path)
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            skipped.append(path)
            continue
        if "\x00" in text:
            skipped.append(path)
            continue
        from .config import _SECRET_VALUE

        original_hash = __import__("hashlib").sha256(data).hexdigest()
        clean = _SECRET_VALUE.sub("[credential withheld]", text)
        clean = re.sub(
            r"""(?im)((?:api[_-]?key|secret[_-]?key|password|access[_-]?token)\s*["']?\s*[:=]\s*)["']([^"'\r\n]{8,})["']""",
            r'\1"[credential withheld]"',
            clean,
        )
        source: dict = {"reference": path, "title": path, "type": "repository", "content": clean}
        if clean != text:
            source.update(original_content_hash=original_hash, redacted=True)
        sources.append(source)
        total += len(data)
    if not sources:
        raise ValueError("No supported text source files were found.")
    metadata = {
        "files_seen": len(files),
        "files_captured": len(sources),
        "skipped_files": skipped[:300],
        "languages": sorted({PurePosixPath(s["reference"]).suffix for s in sources}),
        "manifests": [
            s["reference"]
            for s in sources
            if PurePosixPath(s["reference"]).name
            in {
                "package.json",
                "pyproject.toml",
                "requirements.txt",
                "Cargo.toml",
                "go.mod",
                "Gemfile",
            }
        ],
        "limitations": [
            "Analysis covers captured and selected text only.",
            "Static observations are not proof of a vulnerability.",
            "Repository code and dependencies are never executed on the host.",
        ],
    }
    metadata["redacted_files"] = [s["reference"] for s in sources if s.get("redacted")]
    return sources, metadata


async def github_repository(url: str, token: str = "") -> tuple[list[dict], dict]:
    public_url(url)
    parsed = urlsplit(url)
    if parsed.hostname != "github.com" or parsed.query or parsed.fragment:
        raise ValueError("Use a GitHub repository URL: https://github.com/owner/repository.")
    match = re.fullmatch(r"/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", parsed.path)
    if not match:
        raise ValueError("Use the repository root URL without a branch or file path.")
    owner, name = match.groups()
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token

    async def request(path):
        result = await fetch(
            "https://api.github.com/repos/" + owner + "/" + name + path,
            headers=headers,
            allowed_host="api.github.com",
            limit=8_000_000,
        )
        if result["status"] in {401, 403, 404}:
            raise ValueError(
                "GitHub repository is unavailable, rate limited or requires authorized GITHUB_TOKEN access."
            )
        if result["status"] != 200:
            raise ValueError(f"GitHub returned HTTP {result['status']}.")
        return json.loads(result["body"])

    try:
        repo = await request("")
    except ValueError:
        if token:
            raise
        return await public_git_archive(owner, name)
    branch = repo.get("default_branch")
    if not isinstance(branch, str):
        raise ValueError("GitHub did not return a default branch.")
    from urllib.parse import quote

    commit = await request("/commits/" + quote(branch, safe=""))
    sha = commit.get("sha", "")
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("GitHub did not return a valid commit SHA.")
    tree = await request(f"/git/trees/{sha}?recursive=1")
    if tree.get("truncated"):
        raise ValueError(
            "Repository tree exceeds GitHub's complete-tree limit. Upload a bounded ZIP instead."
        )
    entries = tree.get("tree", [])
    if not isinstance(entries, list) or len(entries) > 10000:
        raise ValueError("Repository exceeds the tree limit.")
    files = {}
    selected = [
        e
        for e in entries
        if e.get("type") == "blob"
        and e.get("mode") != "120000"
        and e.get("size", 0) <= 200000
        and PurePosixPath(e.get("path", "")).suffix.lower() in TEXT_SUFFIXES
        and not any(p in SKIP_PARTS for p in PurePosixPath(e.get("path", "")).parts)
    ]
    # Capture useful source files, not large binary assets from a full archive.
    selected.sort(
        key=lambda e: (
            0
            if PurePosixPath(e["path"]).name.lower()
            in {"readme.md", "pyproject.toml", "package.json", "cargo.toml", "requirements.txt"}
            else 1
            if e["path"].startswith(("src/", "app/", "lib/", "backend/", "tests/"))
            else 2,
            e["path"].count("/"),
            e["path"],
        )
    )
    import asyncio

    concurrency = asyncio.Semaphore(4)

    async def capture(entry: dict) -> tuple[str, bytes]:
        path = safe_path(entry["path"])
        if not re.fullmatch(r"[a-f0-9]{40}", entry.get("sha", "")):
            raise ValueError("GitHub returned an invalid blob identifier.")
        async with concurrency:
            if token:
                # Private credentials stay on the fixed API host.
                blob = await request("/git/blobs/" + entry["sha"])
                if blob.get("encoding") != "base64":
                    raise ValueError("Unsupported GitHub blob encoding.")
                data = base64.b64decode(blob["content"], validate=False)
            else:
                response = await fetch(
                    f"https://raw.githubusercontent.com/{owner}/{name}/{sha}/{quote(path, safe='/')}",
                    allowed_host="raw.githubusercontent.com",
                    limit=200000,
                )
                if response["status"] != 200:
                    raise ValueError(
                        f"GitHub source file retrieval returned HTTP {response['status']}. Retry source capture."
                    )
                data = response["body"]
            if len(data) > 200000:
                raise ValueError("GitHub source file exceeds the 200,000-byte limit.")
            return path, data

    captured = await asyncio.gather(
        *(capture(entry) for entry in selected[:40]), return_exceptions=True
    )
    for item in captured:
        if isinstance(item, BaseException):
            raise item
        files[item[0]] = item[1]
    sources, metadata = repository_sources(files)
    metadata.update(
        repository=url,
        commit_sha=sha,
        default_branch=branch,
        files_in_tree=len(entries),
        retrieval_limit=40,
        omitted_candidate_files=max(0, len(selected) - 40),
        retrieval="commit-pinned bounded source files",
    )
    return sources, metadata


async def public_git_archive(owner: str, name: str) -> tuple[list[dict], dict]:
    """Read-only public ref lookup and pinned ZIP fallback when REST is rate limited."""
    import asyncio
    import os

    import certifi

    url = f"https://github.com/{owner}/{name}.git"
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ASKPASS": "",
        "GIT_CONFIG_COUNT": "0",
    }
    try:
        process = await asyncio.create_subprocess_exec(
            "git",
            "-c",
            "credential.helper=",
            "-c",
            "http.followRedirects=false",
            "-c",
            "http.sslCAInfo=" + certifi.where(),
            "-c",
            "protocol.allow=never",
            "-c",
            "protocol.https.allow=always",
            "ls-remote",
            "--symref",
            url,
            "HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
            cwd=os.environ.get("TEMP", os.curdir),
        )
    except FileNotFoundError as exc:
        raise ValueError(
            "GitHub API quota is exhausted. Install Git for public archive retrieval, configure GITHUB_TOKEN, or upload a ZIP."
        ) from exc
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=25)
        if process.returncode != 0 or len(output) > 8000:
            raise ValueError(
                "Public repository ref lookup failed. Check repository access or upload a ZIP."
            )
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    text = output.decode("utf-8")
    sha_match = re.search(r"^([a-f0-9]{40})\s+HEAD$", text, re.M)
    branch_match = re.search(r"^ref: refs/heads/(.+)\s+HEAD$", text, re.M)
    if not sha_match:
        raise ValueError("Could not determine the public repository HEAD commit.")
    sha = sha_match.group(1)
    response = await fetch(
        f"https://codeload.github.com/{owner}/{name}/zip/{sha}",
        allowed_host="codeload.github.com",
        limit=8_000_000,
    )
    if response["status"] != 200:
        raise ValueError(f"GitHub archive returned HTTP {response['status']}.")
    files = archive_files(response["body"])
    prefix = next(iter(files)).split("/")[0] + "/" if files else ""
    if not prefix or not all(path.startswith(prefix) for path in files):
        raise ValueError("GitHub archive has an unexpected source root.")
    sources, metadata = repository_sources(
        {path[len(prefix) :]: data for path, data in files.items()}
    )
    metadata.update(
        repository=f"https://github.com/{owner}/{name}",
        commit_sha=sha,
        default_branch=branch_match.group(1).strip() if branch_match else None,
        retrieval="public git ref plus commit-pinned archive",
        fallback_reason="Unauthenticated REST request unavailable",
    )
    return sources, metadata


async def ingest(store: Store, task: dict) -> tuple[list[dict], dict]:
    inputs = task["inputs"]
    if task["category"] == "repository":
        if inputs.get("url"):
            sources, metadata = await github_repository(inputs["url"], store.config.github_key)
        elif len(inputs["upload_ids"]) == 1:
            item, data = load_upload(store, inputs["upload_ids"][0])
            if item["type"] != ".zip":
                raise ValueError("Repository upload must be a ZIP archive.")
            sources, metadata = repository_sources(archive_files(data))
            metadata.update(archive_hash=item["hash"], filename=item["name"], commit_sha=None)
        else:
            raise ValueError("Provide a repository URL or one ZIP archive.")
        from .repository_checks import analyze

        metadata["static_analysis"] = analyze(sources)
        if inputs.get("dependency_advisories"):
            from .dependency_checks import check

            try:
                metadata["dependency_advisories"] = await check(sources)
            except Exception as exc:
                metadata["dependency_advisories"] = {
                    "status": "unavailable",
                    "reason": f"Advisory lookup failed ({type(exc).__name__}).",
                }
        if inputs.get("run_tests"):
            from .sandbox import run_tests

            metadata["runtime_tests"] = await run_tests(sources, inputs["test_profile"])
        return sources, metadata
    if task["category"] == "documents" or inputs["upload_ids"]:
        from .documents import extract_documents

        return await extract_documents(store, inputs["upload_ids"])
    if task["category"] == "website":
        from .websites import crawl

        return await crawl(inputs["url"], inputs["max_pages"], inputs["max_depth"])
    raise ValueError("This input type is not supported in the selected workspace.")
