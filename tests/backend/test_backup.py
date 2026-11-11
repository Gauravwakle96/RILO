import importlib.util
import io
import json
import sqlite3
import tarfile
from contextlib import closing
from pathlib import Path

import pytest


def backup_module():
    path = Path(__file__).parents[2] / "scripts" / "backup.py"
    spec = importlib.util.spec_from_file_location("rilo_backup", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backup_restore_round_trip_and_rejections(tmp_path: Path):
    module = backup_module()
    source = tmp_path / "source"
    source.mkdir()
    with closing(sqlite3.connect(source / "rilo.db")) as connection:
        connection.execute("CREATE TABLE proof(value TEXT NOT NULL)")
        connection.execute("INSERT INTO proof(value) VALUES(?)", ("persisted",))
        connection.commit()
    (source / "uploads").mkdir()
    (source / "uploads" / "blob").write_bytes(b"private upload")
    (source / "session.key").write_text("private-session-key", encoding="utf-8")

    archive = tmp_path / "rilo.tar.gz"
    module.backup(source, archive)
    restored = tmp_path / "restored"
    module.restore(archive, restored)

    with closing(sqlite3.connect(restored / "rilo.db")) as connection:
        assert connection.execute("SELECT value FROM proof").fetchone()[0] == "persisted"
    assert (restored / "uploads" / "blob").read_bytes() == b"private upload"
    assert (restored / "session.key").read_text(encoding="utf-8") == "private-session-key"

    with pytest.raises(ValueError, match="empty"):
        module.restore(archive, restored)

    unsafe = tmp_path / "unsafe.tar.gz"
    with tarfile.open(unsafe, "w:gz") as value:
        entry = tarfile.TarInfo("../escape")
        entry.size = 1
        value.addfile(entry, io.BytesIO(b"x"))
    with pytest.raises(ValueError, match="unsafe"):
        module.restore(unsafe, tmp_path / "unsafe-restore")


def test_backup_restore_detects_modified_payload(tmp_path: Path):
    module = backup_module()
    source = tmp_path / "source"
    source.mkdir()
    with closing(sqlite3.connect(source / "rilo.db")) as connection:
        connection.execute("CREATE TABLE proof(value TEXT NOT NULL)")
        connection.commit()
    archive = tmp_path / "rilo.tar.gz"
    module.backup(source, archive)

    unpacked = tmp_path / "unpacked"
    with tarfile.open(archive, "r:gz") as value:
        value.extractall(unpacked, filter="data")
    (unpacked / "rilo-data" / "rilo.db").write_bytes(b"tampered")
    manifest = json.loads((unpacked / "rilo-data" / "manifest.json").read_text())
    assert "rilo.db" in manifest
    tampered = tmp_path / "tampered.tar.gz"
    with tarfile.open(tampered, "w:gz") as value:
        value.add(unpacked / "rilo-data", arcname="rilo-data")
    with pytest.raises(ValueError, match="integrity"):
        module.restore(tampered, tmp_path / "tampered-restore")
