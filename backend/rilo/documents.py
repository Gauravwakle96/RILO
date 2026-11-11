"""Text-based PDF and bounded OOXML/plaintext extraction with honest page metadata."""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys

from defusedxml import ElementTree
from pypdf import PdfReader

from .ingestion import archive_files, load_upload
from .storage import Store


def extract(filename: str, kind: str, data: bytes) -> list[dict]:
    pages: list[tuple[int | None, str]] = []
    if kind == ".pdf":
        try:
            pdf = PdfReader(io.BytesIO(data), strict=True)
            if pdf.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported.")
            if len(pdf.pages) > 200:
                raise ValueError("PDF exceeds the 200-page limit.")
            total = 0
            for index, page in enumerate(pdf.pages):
                content = page.get_contents()
                if content is not None and len(content.get_data()) > 4_000_000:
                    raise ValueError("PDF page content exceeds the extraction limit.")
                text = page.extract_text() or ""
                total += len(text)
                if total > 2_000_000:
                    raise ValueError("Document exceeds the extracted text limit.")
                if text.strip():
                    pages.append((index + 1, text))
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"PDF extraction failed ({type(exc).__name__}).") from exc
        if not pages:
            raise ValueError(
                "PDF has no extractable text. Scanned pages require OCR, which is not supported yet."
            )
    elif kind == ".docx":
        files = archive_files(data)
        if "word/document.xml" not in files:
            raise ValueError("DOCX is missing word/document.xml.")
        try:
            root = ElementTree.fromstring(files["word/document.xml"])
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            paragraphs = ["".join(node.itertext()) for node in root.findall(".//w:p", ns)]
            pages = [(None, "\n".join(paragraphs))]
        except Exception as exc:
            raise ValueError("DOCX XML is invalid or unsafe.") from exc
    else:
        try:
            pages = [(None, data.decode("utf-8-sig"))]
        except UnicodeDecodeError as exc:
            raise ValueError("Text documents must use UTF-8 encoding.") from exc
    if sum(len(text) for _, text in pages) > 2_000_000 or not any(
        text.strip() for _, text in pages
    ):
        raise ValueError("Document is empty or exceeds the text limit.")
    return [
        {
            "reference": filename,
            "title": filename + (f" · page {page}" if page else ""),
            "type": "document",
            "page": page,
            "content": text,
        }
        for page, text in pages
    ]


async def extract_documents(store: Store, ids: list[str]) -> tuple[list[dict], dict]:
    if not ids:
        raise ValueError("Upload at least one document.")
    sources = []
    files = []
    for upload_id in ids:
        item, data = load_upload(store, upload_id)
        if item["type"] not in {".pdf", ".docx", ".txt", ".md"}:
            raise ValueError("Choose PDF, DOCX, TXT or Markdown documents.")
        path = store.config.data_dir / "uploads" / item["hash"]
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-m",
            "rilo.document_worker",
            str(path),
            item["name"],
            item["type"],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env={
                key: value
                for key, value in os.environ.items()
                if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "LANG", "LC_ALL"}
            },
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), timeout=30)
            if process.returncode != 0 or len(output) > 12_000_000:
                raise ValueError("Document parser exceeded its resource limit or failed.")
            parsed = json.loads(output)
            if parsed.get("error"):
                raise ValueError(parsed["error"])
            sources.extend(parsed["sources"])
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        files.append(item)
    return sources, {
        "documents": files,
        "limitations": [
            "PDF page numbers come from the captured file.",
            "DOCX, TXT and Markdown have no reliable rendered page numbers; citations use lines.",
            "No OCR; scanned content may be missing.",
        ],
    }
