from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from rilo.api import create_app
from rilo.config import Config
from rilo.storage import Store


@pytest.fixture
def config(tmp_path: Path) -> Config:
    data = tmp_path / ".rilo"
    data.mkdir()
    return Config(root=tmp_path, data_dir=data)


@pytest.fixture
def store(config: Config) -> Store:
    return Store(config)


@pytest.fixture
def client(config: Config):
    with TestClient(create_app(config)) as test_client:
        yield test_client


@pytest.fixture
def payload() -> dict:
    return {
        "name": "Test recovery",
        "agent_ids": ["scout", "relay"],
        "task_ids": ["company_brief"],
        "scenario_ids": ["normal"],
        "repetitions": 3,
        "engine": "fixture",
        "mode": "controlled",
    }
