from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .gates import AuditRecord

SNAPSHOT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SnapshotMetadata:
    schema_version: int
    config_path: str | None
    code: str
    pending_helper: str
    pending_args: list[Any]
    pending_kwargs: dict[str, Any]
    audit: list[dict[str, str]]


class SnapshotStore:
    def __init__(self, root: Path | None = None):
        self.root = (root or Path.cwd() / ".safebox").resolve()
        self.metadata_path = self.root / "latest.json"
        self.snapshot_path = self.root / "latest.snapshot"

    def save(
        self,
        *,
        snapshot_bytes: bytes,
        config_path: Path | None,
        code: str,
        pending_helper: str,
        pending_args: tuple[Any, ...],
        pending_kwargs: dict[str, Any],
        audit: list[AuditRecord],
    ) -> SnapshotMetadata:
        self.root.mkdir(parents=True, exist_ok=True)
        metadata = SnapshotMetadata(
            schema_version=SNAPSHOT_SCHEMA_VERSION,
            config_path=str(config_path) if config_path is not None else None,
            code=code,
            pending_helper=pending_helper,
            pending_args=list(pending_args),
            pending_kwargs=pending_kwargs,
            audit=[asdict(record) for record in audit],
        )
        self.snapshot_path.write_bytes(snapshot_bytes)
        self.metadata_path.write_text(json.dumps(asdict(metadata), indent=2, sort_keys=True))
        return metadata

    def load_metadata(self) -> SnapshotMetadata:
        if not self.metadata_path.exists():
            raise FileNotFoundError(f"No Safebox snapshot metadata found at {self.metadata_path}")
        data = json.loads(self.metadata_path.read_text())
        if data.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(f"Unsupported Safebox snapshot schema: {data.get('schema_version')}")
        return SnapshotMetadata(**data)

    def load_snapshot_bytes(self) -> bytes:
        if not self.snapshot_path.exists():
            raise FileNotFoundError(f"No Safebox snapshot found at {self.snapshot_path}")
        return self.snapshot_path.read_bytes()
