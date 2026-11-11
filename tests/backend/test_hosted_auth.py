from pathlib import Path

from fastapi.testclient import TestClient
from rilo.api import create_app
from rilo.config import Config
from rilo.identity import owner_context
from rilo.ingestion import load_upload, save_upload
from rilo.schemas import ExperimentCreate
from rilo.snapshots import Snapshots
from rilo.storage import Store
from rilo.workspace_contracts import ConversationCreate
from rilo.workspace_store import WorkspaceStore


def hosted_config(tmp_path: Path) -> Config:
    data = tmp_path / ".rilo-hosted"
    data.mkdir()
    return Config(
        root=tmp_path,
        data_dir=data,
        hosted=True,
        bind_host="0.0.0.0",
        public_url="https://rilo.example",
        allowed_hosts=("rilo.example",),
        allowed_origins_override=("https://rilo.example",),
    )


def login(client: TestClient, email: str, password: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "https://rilo.example"},
    )
    assert response.status_code == 200
    return response.json()


def test_hosted_login_admin_and_per_user_object_isolation(tmp_path: Path, payload: dict):
    config = hosted_config(tmp_path)
    store = Store(config)
    first = store.create_user("first@example.com", "First", "correct-horse-one", "admin")
    second = store.create_user("second@example.com", "Second", "correct-horse-two")
    with owner_context(first["id"]):
        first_experiment = store.create_experiment(ExperimentCreate.model_validate(payload))
    with owner_context(second["id"]):
        second_experiment = store.create_experiment(
            ExperimentCreate.model_validate({**payload, "name": "Second user"})
        )

    with TestClient(create_app(config), base_url="https://rilo.example") as client:
        assert client.get("/api/v1/session").status_code == 401
        first_session = login(client, "first@example.com", "correct-horse-one")
        assert "max-age=31536000" in client.get("/health").headers["strict-transport-security"]
        listed = client.get("/api/v1/experiments").json()
        assert [item["id"] for item in listed] == [first_experiment["id"]]
        assert client.get(f"/api/v1/experiments/{second_experiment['id']}").status_code == 404
        assert client.post(
            f"/api/v1/experiments/{second_experiment['id']}/cancel",
            headers={"X-CSRF-Token": first_session["csrf_token"]},
        ).status_code == 404
        users = client.get("/api/v1/users")
        assert users.status_code == 200 and len(users.json()) == 2
        created = client.post(
            "/api/v1/users",
            json={
                "email": "third@example.com",
                "name": "Third",
                "password": "correct-horse-three",
                "role": "member",
            },
            headers={"X-CSRF-Token": first_session["csrf_token"]},
        )
        assert created.status_code == 201
        client.cookies.clear()
        second_session = login(client, "second@example.com", "correct-horse-two")
        assert client.get("/api/v1/users").status_code == 403
        assert client.get(f"/api/v1/experiments/{first_experiment['id']}").status_code == 404
        assert client.post(
            "/api/v1/auth/logout", headers={"X-CSRF-Token": second_session["csrf_token"]}
        ).status_code == 204
        assert client.get("/api/v1/experiments").status_code == 401


def test_hosted_mode_requires_an_initial_user(tmp_path: Path):
    config = hosted_config(tmp_path)
    try:
        with TestClient(create_app(config), base_url="https://rilo.example"):
            pass
    except RuntimeError as exc:
        assert "rilo user add --admin" in str(exc)
    else:
        raise AssertionError("Hosted mode started without an administrator")


def test_hosted_workspace_objects_catalog_and_artifacts_are_isolated(
    tmp_path: Path, payload: dict
):
    config = hosted_config(tmp_path)
    store = Store(config)
    first = store.create_user("first@example.com", "First", "correct-horse-one", "admin")
    second = store.create_user("second@example.com", "Second", "correct-horse-two")

    with owner_context(first["id"]):
        workspace = WorkspaceStore(store)
        conversation = workspace.create(ConversationCreate(title="First private chat"))
        upload = save_upload(store, "private.txt", b"first private upload")
        snapshot = Snapshots(store).create(
            "chat",
            [{"reference": "private.txt", "type": "document", "content": "first evidence"}],
        )
        agent = store.add_item(
            "agent",
            {
                "id": "agent_first_private",
                "name": "First private agent",
                "description": "Private",
                "framework": "HTTP endpoint",
                "kind": "http",
                "version": "1",
                "capabilities": ["final_output"],
                "config": {"endpoint": "http://127.0.0.1:9001/run"},
            },
        )
        task = store.add_item(
            "task",
            {
                "id": "task_first_private",
                "title": "First private task",
                "description": "Private",
                "prompt": "Summarize the supplied private source.",
                "company": "",
                "reference_time": "2026-11-11T00:00:00+00:00",
                "required_facts": ["first evidence"],
                "source_ids": ["company_source"],
            },
        )
        experiment = store.create_experiment(ExperimentCreate.model_validate(payload))
        store.finish_experiment(experiment["id"], "completed")
        report = workspace.artifact(experiment["id"], "report", {"format": "json"})
        suite_id = "suite_first_private"
        with store.transaction() as connection:
            connection.execute(
                "INSERT INTO benchmark_suites(id,data,created_at) VALUES(?,?,?)",
                (
                    suite_id,
                    '{"id":"suite_first_private","name":"Private","version":"1"}',
                    "2026-11-11T00:00:00+00:00",
                ),
            )
        store.claim_object("suite", suite_id)

    with owner_context(second["id"]):
        assert WorkspaceStore(store).list() == []
        assert agent["id"] not in {item["id"] for item in store.catalog("agent")}
        assert task["id"] not in {item["id"] for item in store.catalog("task")}
        for action in (
            lambda: WorkspaceStore(store).get(conversation["id"]),
            lambda: load_upload(store, upload["id"]),
            lambda: Snapshots(store).get(snapshot["id"]),
            lambda: WorkspaceStore(store).artifact(experiment["id"], "report", {}),
            lambda: store.require_access("artifact", report["id"]),
            lambda: store.require_access("suite", suite_id),
            lambda: store.item("agent", agent["id"]),
            lambda: store.item("task", task["id"]),
        ):
            try:
                action()
            except KeyError:
                pass
            else:
                raise AssertionError("Cross-user object access was not rejected")
