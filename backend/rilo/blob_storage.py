"""Bounded private source storage; content hashes never name public assets."""

from pathlib import Path
from typing import TYPE_CHECKING

from .config import Config

if TYPE_CHECKING:
    from .storage import Store


def check_capacity(config: Config, additional_bytes: int) -> None:
    used = sum(
        item.stat().st_size
        for directory in ("uploads", "objects")
        for item in (config.data_dir / directory).glob("*")
        if item.is_file()
    )
    if used + additional_bytes > config.storage_max_bytes:
        raise ValueError(
            "Private source storage limit reached. Archive old workspace data or explicitly increase RILO_STORAGE_MAX_BYTES."
        )


def write_blob(store: "Store", path: Path, data: bytes) -> None:
    # Serialize quota admission across uploads and snapshots using the existing DB.
    with store.transaction():
        if path.exists():
            if path.read_bytes() != data:
                raise ValueError("Stored source integrity check failed.")
            return
        check_capacity(store.config, len(data))
        with path.open("xb") as handle:
            handle.write(data)
