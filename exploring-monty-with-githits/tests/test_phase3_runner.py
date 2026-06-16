from pathlib import Path

from safebox.config import SafeboxConfig
from safebox.phase3_runner import Phase3Runner
from safebox.snapshots import SnapshotStore


PHASE3_CODE = '''
approval = request_approval("Write scratch/phase3-demo.md")
if not approval["ok"]:
    result = approval
else:
    result = write_file("scratch/phase3-demo.md", "Phase 3 resumed successfully.\\n")
result
'''


def _config(tmp_path: Path) -> SafeboxConfig:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    config = SafeboxConfig()
    config.filesystem.allow_read = [scratch.resolve()]
    config.filesystem.allow_write = [scratch.resolve()]
    config.source_path = tmp_path / "phase3.toml"
    return config


def test_phase3_start_saves_snapshot_on_approval(tmp_path: Path):
    store = SnapshotStore(tmp_path / ".safebox")
    runner = Phase3Runner(_config(tmp_path), cwd=tmp_path, store=store)

    result = runner.start(PHASE3_CODE)

    assert result.execution.ok is True
    assert result.metadata is not None
    assert store.snapshot_path.exists()
    assert store.metadata_path.exists()
    assert result.metadata.pending_helper == "request_approval"
    assert "snapshot saved" in result.execution.output["value"]
    assert "exit this session" in result.execution.output["value"]
    assert "safebox-3 resume --approve" in result.execution.output["value"]
    assert result.execution.audit[-1].helper == "request_approval"


def test_phase3_resume_approve_completes_write(tmp_path: Path):
    store = SnapshotStore(tmp_path / ".safebox")
    runner = Phase3Runner(_config(tmp_path), cwd=tmp_path, store=store)
    runner.start(PHASE3_CODE)

    result = runner.resume(approved=True)

    assert result.ok is True
    assert (tmp_path / "scratch" / "phase3-demo.md").read_text() == "Phase 3 resumed successfully.\n"
    assert result.output["ok"] is True
    assert [record.helper for record in result.audit] == ["request_approval", "write_file"]


def test_phase3_resume_deny_does_not_write(tmp_path: Path):
    store = SnapshotStore(tmp_path / ".safebox")
    runner = Phase3Runner(_config(tmp_path), cwd=tmp_path, store=store)
    runner.start(PHASE3_CODE)

    result = runner.resume(approved=False)

    assert result.ok is True
    assert result.output == {"ok": False, "error": "Refused: approval denied"}
    assert not (tmp_path / "scratch" / "phase3-demo.md").exists()
    assert [record.helper for record in result.audit] == ["request_approval"]


def test_phase3_resume_without_snapshot_fails_cleanly(tmp_path: Path):
    result = Phase3Runner(_config(tmp_path), cwd=tmp_path, store=SnapshotStore(tmp_path / ".safebox")).resume(approved=True)

    assert result.ok is False
    assert "No Safebox snapshot" in result.error
