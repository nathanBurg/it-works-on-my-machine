from pathlib import Path

from safebox.config import SafeboxConfig
from safebox.gates import AuditRecord
from safebox.snapshots import SnapshotStore, policy_fingerprint


def _config(tmp_path: Path) -> SafeboxConfig:
    config = SafeboxConfig()
    config.source_path = tmp_path / "phase3.toml"
    config.filesystem.allow_write = [(tmp_path / "scratch").resolve()]
    return config


def test_snapshot_store_writes_metadata_without_secret_values(tmp_path: Path):
    store = SnapshotStore(tmp_path / ".safebox")

    metadata = store.save(
        snapshot_bytes=b"monty-state",
        config=_config(tmp_path),
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
    assert loaded.policy_fingerprint == metadata.policy_fingerprint


def test_snapshot_store_missing_snapshot_is_readable(tmp_path: Path):
    store = SnapshotStore(tmp_path / ".safebox")

    try:
        store.load_snapshot_bytes()
    except FileNotFoundError as exc:
        assert "No Safebox snapshot" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected missing snapshot error")


def test_policy_fingerprint_changes_when_policy_changes(tmp_path: Path):
    original = _config(tmp_path)
    broader = _config(tmp_path)
    broader.filesystem.allow_write = [tmp_path.resolve()]

    assert policy_fingerprint(original) != policy_fingerprint(broader)


def test_policy_fingerprint_changes_when_defaults_status_changes(tmp_path: Path):
    defaults = _config(tmp_path)
    defaults.used_defaults = True
    loaded = _config(tmp_path)
    loaded.used_defaults = False

    assert policy_fingerprint(defaults) != policy_fingerprint(loaded)
