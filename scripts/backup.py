"""Create or restore a verified Rilo archive using the shared backup engine."""

from __future__ import annotations

import argparse
from pathlib import Path

from rilo.backup import backup, restore, safe_members  # noqa: F401


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
    if args.command == "create":
        backup(args.data_dir.resolve(), args.output.resolve())
    else:
        restore(args.archive.resolve(), args.destination.resolve())


if __name__ == "__main__":
    main()
