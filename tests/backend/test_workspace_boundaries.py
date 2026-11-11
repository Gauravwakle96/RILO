import io
import json
import zipfile

import pytest
from rilo.dependency_checks import check, resolved_dependencies
from rilo.ingestion import ingest, save_upload
from rilo.repository_checks import analyze


def test_private_blob_quota_and_integrity(store):
    from rilo.snapshots import Snapshots

    store.config.storage_max_bytes = 12
    first = save_upload(store, "a.txt", b"12345678")
    assert save_upload(store, "again.txt", b"12345678")["hash"] == first["hash"]
    with pytest.raises(ValueError, match="storage limit"):
        Snapshots(store).put_content("new bytes")
    (store.config.data_dir / "uploads" / first["hash"]).write_bytes(b"altered")
    with pytest.raises(ValueError, match="integrity"):
        save_upload(store, "again.txt", b"12345678")


def test_labeled_regression_has_defined_scope_and_rejects_changed_conditions():
    import copy

    from rilo.workspace_evaluation import RegressionCreate, compare_workspace

    baseline = {
        "spec": {
            "model": "local",
            "limits": {},
            "agent_ids": ["scout"],
            "repetitions": 5,
            "mode": "controlled",
            "engine": "bifrost",
        },
        "manifest": {
            "workspace": {
                "category": "repository",
                "suite_id": "suite_a",
                "suite_version": "1",
                "ground_truth": [{"reference": "a.py", "expected_quote": "x"}],
            }
        },
        "runs": [
            {
                "agent_id": "scout",
                "outcome": "completed",
                "assessment": {"label_metrics": {"f1": 1}},
            }
            for _ in range(5)
        ],
    }
    candidate = copy.deepcopy(baseline)
    candidate["runs"][0]["assessment"]["label_metrics"]["f1"] = 0
    spec = RegressionCreate(baseline_id="exp_a", candidate_id="exp_b")
    result = compare_workspace(baseline, candidate, spec)
    assert result["gate"] == "regression"
    assert result["agent_deltas"][0]["score_delta"] == pytest.approx(-0.2)
    assert result["agent_deltas"][0]["baseline_trials"]["completion_interval_95"]
    candidate["manifest"]["workspace"]["suite_version"] = "2"
    assert compare_workspace(baseline, candidate, spec)["gate"] == "inconclusive"


def archive(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as value:
        for path, content in files.items():
            value.writestr(path, content)
    return output.getvalue()


@pytest.mark.asyncio
async def test_osv_exact_versions_and_independent_failure(monkeypatch):
    sources = [
        {"reference": "requirements.txt", "content": "Flask==0.12.2\nhttpx>=0.20\nFlask==0.12.2"},
        {
            "reference": "package-lock.json",
            "content": json.dumps(
                {"packages": {"node_modules/a": {"version": "1.2.3"}, "": {"version": "1"}}}
            ),
        },
    ]
    assert len(resolved_dependencies(sources)) == 2
    assert resolved_dependencies([{"reference": "package-lock.json", "content": "broken"}]) == []
    assert (await check([]))["status"] == "not_applicable"

    async def provider(*args, **kwargs):
        assert kwargs["json"]["queries"][0]["package"]["name"] == "Flask"
        assert "content" not in str(kwargs["json"])
        return {"results": [{"vulns": [{"id": "TEST-ADVISORY", "modified": "2026-01-01"}]}, {}]}

    monkeypatch.setattr("rilo.dependency_checks.bounded_json", provider)
    result = await check(sources)
    assert result["packages_checked"] == 2
    assert result["results"][0]["advisories"][0]["id"] == "TEST-ADVISORY"

    async def invalid(*args, **kwargs):
        return {"results": []}

    monkeypatch.setattr("rilo.dependency_checks.bounded_json", invalid)
    with pytest.raises(ValueError, match="invalid"):
        await check(sources)


@pytest.mark.asyncio
async def test_zip_ingestion_keeps_static_and_failed_external_checks_separate(store, monkeypatch):
    upload = save_upload(
        store,
        "repo.zip",
        archive(
            {
                "app.py": "def run(value):\n    return eval(value)\n",
                "requirements.txt": "Flask==0.12.2",
            }
        ),
    )

    async def unavailable(*args):
        raise ConnectionError("Provider unavailable")

    async def isolated(sources, profile):
        assert profile == "python-unittest"
        return {"status": "unavailable", "executed": False, "reason": "Runner not installed"}

    monkeypatch.setattr("rilo.dependency_checks.check", unavailable)
    monkeypatch.setattr("rilo.sandbox.run_tests", isolated)
    sources, metadata = await ingest(
        store,
        {
            "category": "repository",
            "inputs": {
                "upload_ids": [upload["id"]],
                "dependency_advisories": True,
                "run_tests": True,
                "test_profile": "python-unittest",
            },
        },
    )
    assert metadata["commit_sha"] is None
    assert metadata["static_analysis"]["observations"][0]["start_line"] == 2
    assert metadata["dependency_advisories"]["status"] == "unavailable"
    assert metadata["runtime_tests"]["executed"] is False
    assert sources[0]["reference"] == "app.py"


def test_ast_and_manifest_inventory_distinguishes_patterns_from_vulnerabilities():
    result = analyze(
        [
            {
                "reference": "app.py",
                "content": "import subprocess\nfrom lib import db\n@app.get('/items')\ndef items():\n    subprocess.run('x', shell=True)\n    db.execute(f'SELECT {user}')\n",
            },
            {"reference": "test_bad.py", "content": "def !!!"},
            {"reference": "package.json", "content": '{"dependencies":{"a":"^1.0"}}'},
            {"reference": "nested/package.json", "content": "broken"},
            {"reference": "pyproject.toml", "content": '[project]\ndependencies=["httpx>=0.28"]'},
            {"reference": "nested/pyproject.toml", "content": "["},
        ]
    )
    assert result["modules"][0]["routes"][0]["path"] == "/items"
    assert result["modules"][1]["parse_status"] == "unsupported_or_invalid_syntax"
    assert {o["rule"] for o in result["observations"]} == {
        "shell-true-call",
        "dynamic-sql-expression",
        "invalid-dependency-manifest",
    }
    assert len(result["dependencies"]) == 2
    assert result["executed_repository_code"] is False


@pytest.mark.asyncio
async def test_advisory_review_returns_observed_usage_and_rejects_unknown_ids(store, monkeypatch):
    from rilo.engine import InfrastructureError
    from rilo.semantic_review import review

    experiment = {
        "runs": [
            {
                "assessment": {
                    "findings": [
                        {
                            "id": "finding_1",
                            "claim": "SQLite is safe",
                            "verification": {
                                "citations": [
                                    {
                                        "quote": "SQLite stores records",
                                        "valid": True,
                                        "source_reference": "notes",
                                    }
                                ]
                            },
                        }
                    ]
                }
            }
        ],
        "manifest": {"bifrost_url": store.config.bifrost_url},
        "spec": {"model": store.config.model},
    }
    finding_id = "response_1:finding_1"

    async def provider(*args, **kwargs):
        return {
            "model": store.config.model,
            "usage": {"prompt_tokens": 120, "completion_tokens": 40},
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "judgments": [
                                    {
                                        "finding_id": finding_id,
                                        "state": "UNSUPPORTED",
                                        "explanation": "Storage choice does not establish safety.",
                                    }
                                ]
                            }
                        )
                    }
                }
            ],
        }

    monkeypatch.setattr("rilo.semantic_review.bounded_json", provider)
    result = await review(store, experiment)
    assert result["model_graded"] and result["input_tokens"] == 120
    assert result["judgments"][0]["state"] == "UNSUPPORTED"
    finding_id = "invented"
    with pytest.raises(InfrastructureError, match="references"):
        await review(store, experiment)


@pytest.mark.asyncio
async def test_real_api_report_retest_and_regression(store, client, config, monkeypatch):
    from rilo.engine import RunContext
    from rilo.worker import worker
    from rilo.workspace_contracts import ConversationCreate, TurnCreate
    from rilo.workspace_store import WorkspaceStore

    async def provider(self, messages, max_tokens=1100):
        return {
            "choices": [{"message": {"content": '{"summary":"Recorded answer","findings":[]}'}}]
        }

    monkeypatch.setattr(RunContext, "completion", provider)
    headers = {"Authorization": "Bearer " + config.session_key}
    workspace = WorkspaceStore(store)
    conv = workspace.create(ConversationCreate(title="Routes"))
    exp = workspace.turn(conv["id"], TurnCreate(message="Explain this", inputs={"text": "Text"}))
    await worker(store, once=True)
    base = "/api/v1/workspace"
    for route in [
        "profiles",
        "dashboard",
        "capabilities",
        "conversations",
        "conversations/" + conv["id"],
        "conversations/" + conv["id"] + "/export",
        "evaluations/" + exp["id"],
        "reports",
        "suites",
    ]:
        assert client.get(base + "/" + route, headers=headers).status_code == 200
    for format in ["pdf", "json", "csv", "md"]:
        report = client.get(
            base + f"/evaluations/{exp['id']}/report?format={format}", headers=headers
        )
        assert report.status_code == 200 and report.content
    rerun = client.post(base + f"/evaluations/{exp['id']}/retest", headers=headers)
    assert rerun.status_code == 202
    await worker(store, once=True)
    regression = client.post(
        base + "/regressions",
        json={"baseline_id": exp["id"], "candidate_id": rerun.json()["id"]},
        headers=headers,
    )
    assert regression.json()["compatible"]
    assert regression.json()["gate"] == "inconclusive"
