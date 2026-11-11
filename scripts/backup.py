"""Create or restore a verified Rilo data archive."""

from __future__ import annotations

import argparse
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
    for member in members:
        target = (destination / member.name).resolve()
        if not target.is_relative_to(root) or member.issym() or member.islnk():
            raise ValueError("Backup archive contains an unsafe path or link.")
    return members


def backup(data_dir: Path, output: Path) -> None:
    database = data_dir / "rilo.db"
    if not database.exists():
        raise ValueError("Rilo database was not found.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary) / "rilo-data"
        stage.mkdir()
        with closing(sqlite3.connect(database)) as source, closing(
            sqlite3.connect(stage / "rilo.db")
        ) as target:
            source.backup(target)
            target.commit()
        for name in ("uploads", "objects", "settings.json", "session.key"):
            source = data_dir / name
            if source.is_dir():
                shutil.copytree(source, stage / name)
            elif source.is_file():
                shutil.copy2(source, stage / name)
        manifest = {
            path.relative_to(stage).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in stage.rglob("*")
            if path.is_file()
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        with tarfile.open(output, "w:gz") as archive:
            archive.add(stage, arcname="rilo-data")


def restore(archive_path: Path, destination: Path) -> None:
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Restore destination must be empty.")
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary)
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(stage, members=safe_members(archive, stage), filter="data")
        root = stage / "rilo-data"
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        for relative, expected in manifest.items():
            path = root / relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Backup integrity verification failed.")
        for source in root.iterdir():
            if source.name != "manifest.json":
                shutil.move(str(source), destination / source.name)


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--data-dir", type=Path, default=Path(".rilo"))
    create.add_argument("--output", type=Path, required=True)
    recover = commands.add_parser("restore")
    recover.add_argument("--archive", type=Path, required=True)
    recover.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    backup(args.data_dir.resolve(), args.output.resolve()) if args.command == "create" else restore(
        args.archive.resolve(), args.destination.resolve()
    )


if __name__ == "__main__":
    main()
