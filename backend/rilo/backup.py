"""Private, verified local backup and non-destructive restoration."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tarfile
import tempfile
from contextlib import closing
from pathlib import Path


def safe_members(archive: tarfile.TarFile, destination: Path) -> list[tarfile.TarInfo]:
    root = destination.resolve()
    members = archive.getmembers()
    if len(members) > 100000 or sum(member.size for member in members) > 2_000_000_000:
        raise ValueError("Backup exceeds restore limits.")
    names = set()
    for member in members:
        if (
            member.name in names
            or not (destination / member.name).resolve().is_relative_to(root / "rilo-data")
            or not (member.isfile() or member.isdir())
        ):
            raise ValueError("Backup archive contains an unsafe path or link.")
        names.add(member.name)
    return members


def backup(data_dir: Path, output: Path) -> None:
    database = data_dir / "rilo.db"
    if not database.exists():
        raise ValueError("Rilo database was not found.")
    if output.resolve().is_relative_to(data_dir.resolve()):
        raise ValueError("Save backups outside the active data folder.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary) / "rilo-data"
        stage.mkdir()
        with (
            closing(sqlite3.connect(database)) as source_connection,
            closing(sqlite3.connect(stage / "rilo.db")) as target,
        ):
            source_connection.backup(target)
            target.commit()
        for name in ("uploads", "objects", "settings.json", "session.key"):
            source = data_dir / name
            if source.is_symlink():
                raise ValueError("Backup sources cannot be symbolic links.")
            if source.is_dir():
                for item in source.rglob("*"):
                    if item.is_symlink():
                        raise ValueError("Backup sources cannot contain symbolic links.")
                shutil.copytree(source, stage / name)
            elif source.is_file():
                shutil.copy2(source, stage / name)
        manifest = {
            path.relative_to(stage).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in stage.rglob("*")
            if path.is_file()
        }
        (stage / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with tarfile.open(output, "w:gz") as archive:
            archive.add(stage, arcname="rilo-data")


def restore(archive_path: Path, destination: Path) -> None:
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Restore destination must be empty.")
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary)
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(stage, members=safe_members(archive, stage), filter="data")
        root = stage / "rilo-data"
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or "rilo.db" not in manifest:
            raise ValueError("Backup manifest is invalid or the database is missing.")
        for relative, expected in manifest.items():
            if not isinstance(relative, str) or not isinstance(expected, str):
                raise ValueError("Backup manifest entries are invalid.")
            path = (root / relative).resolve()
            if (
                not path.is_relative_to(root.resolve())
                or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected
            ):
                raise ValueError("Backup integrity verification failed.")
        actual = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file() and path != root / "manifest.json"
        }
        if actual != set(manifest):
            raise ValueError("Backup contains unverified files.")
        destination.mkdir(parents=True, exist_ok=True)
        for source in root.iterdir():
            if source.name != "manifest.json":
                shutil.move(str(source), destination / source.name)
