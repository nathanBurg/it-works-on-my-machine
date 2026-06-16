from pathlib import Path

from safebox.gates import AuditRecord
from safebox.snapshots import SnapshotStore


def test_snapshot_store_writes_metadata_without_secret_values(tmp_path: Path):
    store = SnapshotStore(tmp_path / ".safebox")

    metadata = store.save(
        snapshot_bytes=b"monty-state",
        config_path=tmp_path / "phase3.toml",
        code='request_approval("write")',
        pending_helper="request_approval",
        pending_args=("write",),
        pending_kwargs={},
        audit=[AuditRecord("request_approval", "ALLOW", "write", "human approval required")],
    )

    assert store.snapshot_path.read_bytes() == b"monty-state"
    assert metadata.pending_helper == "request_approval"
    text = store.metadata_path.read_text()
    assert "OPENAI_API_KEY" not in text
    assert "secret-token" not in text
    loaded = store.load_metadata()
    assert loaded.pending_args == ["write"]


def test_snapshot_store_missing_snapshot_is_readable(tmp_path: Path):
    store = SnapshotStore(tmp_path / ".safebox")

    try:
        store.load_snapshot_bytes()
    except FileNotFoundError as exc:
        assert "No Safebox snapshot" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected missing snapshot error")
