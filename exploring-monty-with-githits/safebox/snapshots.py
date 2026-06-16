from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import SafeboxConfig
from .gates import AuditRecord

SNAPSHOT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SnapshotMetadata:
    schema_version: int
    config_path: str | None
    policy_fingerprint: str
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
        config: SafeboxConfig,
        code: str,
        pending_helper: str,
        pending_args: tuple[Any, ...],
        pending_kwargs: dict[str, Any],
        audit: list[AuditRecord],
    ) -> SnapshotMetadata:
        self.root.mkdir(parents=True, exist_ok=True)
        metadata = SnapshotMetadata(
            schema_version=SNAPSHOT_SCHEMA_VERSION,
            config_path=str(config.source_path) if config.source_path is not None else None,
            policy_fingerprint=policy_fingerprint(config),
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

    def clear(self) -> None:
        self.metadata_path.unlink(missing_ok=True)
        self.snapshot_path.unlink(missing_ok=True)


def policy_fingerprint(config: SafeboxConfig) -> str:
    payload = {
        "used_defaults": config.used_defaults,
        "source_path": str(config.source_path.resolve()) if config.source_path is not None else None,
        "model": {
            "provider": config.model.provider,
            "model": config.model.model,
            "api_key_env": config.model.api_key_env,
            "base_url": config.model.base_url,
        },
        "filesystem": {
            "allow_read": sorted(str(path.resolve()) for path in config.filesystem.allow_read),
            "allow_write": sorted(str(path.resolve()) for path in config.filesystem.allow_write),
        },
        "env": {"allow": sorted(config.env.allow)},
        "network": {"enabled": config.network.enabled},
        "helpers": {"files": config.helpers.files, "githits": config.helpers.githits},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
