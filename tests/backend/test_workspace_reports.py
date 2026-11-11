import io
import json

import pytest
from pypdf import PdfReader
from rilo.engine import RunContext
from rilo.reports import export, report_data
from rilo.worker import worker
from rilo.workspace_contracts import ConversationCreate, TurnCreate
from rilo.workspace_evaluation import RegressionCreate, compare_workspace, precision_recall, wilson
from rilo.workspace_store import WorkspaceStore


@pytest.mark.asyncio
async def test_persisted_reports_and_repeated_suite(store, client, config, monkeypatch):
    async def completion(self, messages, max_tokens=1100):
        source = self.evidence[0]
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "Actual saved response",
                                "findings": [
                                    {
                                        "title": "Storage",
                                        "claim": source["content"],
                                        "citations": [
                                            {
                                                "source_id": source["id"],
                                                "quote": source["content"],
                                                "start_line": source["start_line"],
                                                "end_line": source["end_line"],
                                            }
                                        ],
                                    }
                                ],
                            }
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(RunContext, "completion", completion)
    workspace = WorkspaceStore(store)
    conv = workspace.create(ConversationCreate(title="Report verification"))
    exp = workspace.turn(
        conv["id"],
        TurnCreate(message="Describe storage", inputs={"text": "SQLite stores history."}),
    )
    await worker(store, once=True)
    data = report_data(store, exp["id"])
    for format in ("json", "csv", "md", "pdf"):
        content, media = export(data, format)
        assert content and media
        if format == "pdf":
            assert export(data, "pdf")[0] == content
            text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(content)).pages)
            assert "Actual saved response" in text
            assert "SQLite stores history" in text
        else:
            assert exp["id"].encode() in content.replace(b"\\_", b"_")
    headers = {"Authorization": "Bearer " + config.session_key}
    suite = client.post(
        "/api/v1/workspace/suites",
        headers=headers,
        json={
            "name": "Storage suite",
            "version": "1.0",
            "source_experiment_id": exp["id"],
            "repetitions": 2,
            "labels": [
                {
                    "label_id": "storage",
                    "reference": "Attached context",
                    "expected_quote": "SQLite stores history.",
                }
            ],
        },
    ).json()
    assert suite["snapshot_id"] == data["manifest"]["snapshot"]["id"]
    rerun = client.post(f"/api/v1/workspace/suites/{suite['id']}/run", headers=headers).json()
    await worker(store, once=True)
    runs = report_data(store, rerun["id"])["runs"]
    assert len(runs) == 4
    assert all(run["assessment"]["label_metrics"]["recall"] == 1 for run in runs)
    regression = compare_workspace(
        data,
        report_data(store, rerun["id"]),
        RegressionCreate(baseline_id=exp["id"], candidate_id=rerun["id"]),
    )
    assert "repetitions" in regression["mismatches"]
    assert regression["gate"] == "inconclusive"


def test_metrics_handle_undefined_and_small_samples():
    assert precision_recall(0, 0, 0)["precision"] is None
    assert precision_recall(3, 1, 2)["recall"] == 0.6
    assert precision_recall(0, 2, 3)["f1"] == 0
    assert wilson(1, 2) is None
    assert wilson(5, 10)[0] < 0.5 < wilson(5, 10)[1]


def test_static_checks_record_exact_ast_lines_without_execution():
    from rilo.repository_checks import analyze

    result = analyze(
        [
            {
                "reference": "app.py",
                "content": "import os\n\ndef run(value):\n    return eval(value)\n",
            }
        ]
    )
    finding = result["observations"][0]
    assert finding["start_line"] == 4
    assert finding["quote"] == "    return eval(value)"
    assert result["executed_repository_code"] is False


@pytest.mark.asyncio
async def test_document_subprocess_extraction(store):
    from rilo.documents import extract_documents
    from rilo.ingestion import save_upload

    upload = save_upload(store, "notes.txt", b"Document subprocess evidence.")
    sources, _ = await extract_documents(store, [upload["id"]])
    assert sources[0]["content"] == "Document subprocess evidence."
