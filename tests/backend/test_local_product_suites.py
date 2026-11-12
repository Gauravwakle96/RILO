"""Suite cases retain their own assertions, labels and immutable candidate settings."""

import json

import pytest
from rilo.backup import restore, safe_members
from rilo.engine import RunContext
from rilo.worker import worker
from rilo.workspace_contracts import ConversationCreate, TurnCreate
from rilo.workspace_store import WorkspaceStore


async def test_multicase_suite_preserves_own_checks_and_labels(client, config, monkeypatch):
    from rilo.storage import Store

    store = Store(config)

    async def completion(self, messages, **kwargs):
        return {"choices": [{"message": {"content": '{"summary":"Response","findings":[]}'}}]}

    monkeypatch.setattr(RunContext, "completion", completion)
    workspace = WorkspaceStore(store)
    experiments = []
    for index in range(2):
        conversation = workspace.create(
            ConversationCreate(
                title=f"Case {index}", slots=[{"agent_id": "scout"}, {"agent_id": "scout"}]
            )
        )
        experiments.append(
            workspace.turn(
                conversation["id"],
                TurnCreate(
                    message=f"Task {index}",
                    inputs={"text": f"Case {index} context"},
                    checks=[
                        {
                            "id": f"rule_{index}",
                            "name": f"Rule {index}",
                            "type": "max-length",
                            "value": str(30 + index),
                        }
                    ],
                ),
            )
        )
        await worker(store, once=True)
    csrf = client.get("/api/v1/session").json()["csrf_token"]
    response = client.post(
        "/api/v1/workspace/suites",
        json={
            "name": "Multiple cases",
            "version": "1",
            "source_experiment_id": experiments[0]["id"],
            "additional_experiment_ids": [experiments[1]["id"]],
            "repetitions": 1,
            "labels": [
                {
                    "label_id": "first_label",
                    "reference": "Attached context",
                    "expected_quote": "Case 0 context",
                }
            ],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 201, response.text
    suite = response.json()
    assert suite["cases"][0]["labels"][0]["label_id"] == "first_label"
    assert suite["cases"][1]["labels"] == []
    for case in range(2):
        response = client.post(
            f"/api/v1/workspace/suites/{suite['id']}/run?case={case}",
            json={},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 202, response.text
        task = response.json()["manifest"]["workspace"]
        assert task["checks"][0]["id"] == f"rule_{case}"
        assert task["suite_case"] == case
        assert (
            task["execution_agents"]
            == suite["cases"][case]["source_manifest"]["workspace"]["execution_agents"]
        )


def test_backup_rejects_extra_unmanifested_files_and_links(tmp_path):
    import io
    import tarfile

    archive_path = tmp_path / "extra.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for name, content in [
            ("rilo-data/rilo.db", b"db"),
            ("rilo-data/extra", b"unverified"),
            (
                "rilo-data/manifest.json",
                json.dumps({"rilo.db": __import__("hashlib").sha256(b"db").hexdigest()}).encode(),
            ),
        ]:
            item = tarfile.TarInfo(name)
            item.size = len(content)
            archive.addfile(item, io.BytesIO(content))
    with pytest.raises(ValueError, match="unverified"):
        restore(archive_path, tmp_path / "restore")
    assert not (tmp_path / "restore").exists()
    with tarfile.open(tmp_path / "link.tar.gz", "w:gz") as archive:
        item = tarfile.TarInfo("rilo-data/link")
        item.type = tarfile.SYMTYPE
        item.linkname = "../../outside"
        archive.addfile(item)
    with (
        tarfile.open(tmp_path / "link.tar.gz") as archive,
        pytest.raises(ValueError, match="unsafe"),
    ):
        safe_members(archive, tmp_path / "stage")
