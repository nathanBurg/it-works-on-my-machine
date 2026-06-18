from pathlib import Path

import safebox.phase3_cli as phase3_cli
from safebox.phase3_cli import PHASE3_SYSTEM_PROMPT


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_phase3_prompt_mentions_approval_helper():
    assert "request_approval" in PHASE3_SYSTEM_PROMPT
    assert 'approval["ok"]' in PHASE3_SYSTEM_PROMPT
    assert '"\\n".join(lines) + "\\n"' in PHASE3_SYSTEM_PROMPT
    assert 'write_file("scratch/phase3-demo.md", content)' in PHASE3_SYSTEM_PROMPT
    assert 'successfully.\n")' not in PHASE3_SYSTEM_PROMPT
    assert "result" in PHASE3_SYSTEM_PROMPT


def test_phase3_cli_starts_with_snapshot_config(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _prompt: (_ for _ in ()).throw(EOFError()))

    assert phase3_cli.main(["--config", str(PROJECT_ROOT / "configs" / "phase3-snapshot.toml")]) == 0

    out = capsys.readouterr().out
    assert "Safebox Phase 3" in out
    assert "snapshot=enabled" in out


def test_phase3_resume_without_snapshot_fails_cleanly(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert phase3_cli.main(["resume", "--approve"]) == 1

    out = capsys.readouterr().out
    assert "No Safebox snapshot" in out


def test_phase3_resume_uses_config_before_subcommand(monkeypatch, tmp_path: Path):
    seen = []

    class FakeRunner:
        def __init__(self, config):
            seen.append(config.source_path)

        def resume(self, *, approved: bool):
            assert approved is True
            return type("Result", (), {"ok": True, "output": 1, "stdout": "", "stderr": "", "audit": []})()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(phase3_cli, "Phase3Runner", FakeRunner)

    config_path = PROJECT_ROOT / "configs" / "phase3-snapshot.toml"
    assert phase3_cli.main(["--config", str(config_path), "resume", "--approve"]) == 0

    assert seen == [config_path.resolve()]


def test_phase3_resume_uses_config_after_subcommand(monkeypatch, tmp_path: Path):
    seen = []

    class FakeRunner:
        def __init__(self, config):
            seen.append(config.source_path)

        def resume(self, *, approved: bool):
            assert approved is True
            return type("Result", (), {"ok": True, "output": 1, "stdout": "", "stderr": "", "audit": []})()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(phase3_cli, "Phase3Runner", FakeRunner)

    config_path = PROJECT_ROOT / "configs" / "phase3-snapshot.toml"
    assert phase3_cli.main(["resume", "--approve", "--config", str(config_path)]) == 0

    assert seen == [config_path.resolve()]
