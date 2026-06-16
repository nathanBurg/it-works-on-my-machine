from pathlib import Path

from safebox.config import SafeboxConfig
from safebox.monty_runner import MontyRunner


def test_pure_computation_returns_last_expression(tmp_path: Path):
    result = MontyRunner(SafeboxConfig(), cwd=tmp_path).run("17 * 23")

    assert result.ok is True
    assert result.output == 391
    assert result.audit == []


def test_print_output_is_captured(tmp_path: Path):
    result = MontyRunner(SafeboxConfig(), cwd=tmp_path).run('print("hello")')

    assert result.ok is True
    assert result.stdout == "hello\n"


def test_file_gate_denied_by_default(tmp_path: Path):
    (tmp_path / "README.md").write_text("readme")
    result = MontyRunner(SafeboxConfig(), cwd=tmp_path).run('read_file("README.md")')

    assert result.ok is True
    assert result.output["ok"] is False
    assert result.audit[-1].decision == "DENY"
    assert result.audit[-1].helper == "read_file"


def test_file_gate_allowed_when_configured(tmp_path: Path):
    target = tmp_path / "README.md"
    target.write_text("readme")
    config = SafeboxConfig()
    config.filesystem.allow_read = [target.resolve()]

    result = MontyRunner(config, cwd=tmp_path).run('read_file("README.md")')

    assert result.ok is True
    assert result.output == {"ok": True, "value": "readme"}
    assert result.audit[-1].decision == "ALLOW"
    assert result.audit[-1].helper == "read_file"


def test_list_files_gate_allowed_when_configured(tmp_path: Path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "notes.txt").write_text("notes")
    config = SafeboxConfig()
    config.filesystem.allow_read = [scratch.resolve()]

    result = MontyRunner(config, cwd=tmp_path).run('list_files("scratch")')

    assert result.ok is True
    assert result.output == {"ok": True, "value": ["notes.txt"]}
    assert result.audit[-1].helper == "list_files"


def test_write_file_gate_allowed_when_configured(tmp_path: Path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    config = SafeboxConfig()
    config.filesystem.allow_write = [scratch.resolve()]

    result = MontyRunner(config, cwd=tmp_path).run('write_file("scratch/README.md", "hello")')

    assert result.ok is True
    assert (scratch / "README.md").read_text() == "hello"
    assert result.audit[-1].helper == "write_file"


def test_python_builtin_list_does_not_hit_gate(tmp_path: Path):
    result = MontyRunner(SafeboxConfig(), cwd=tmp_path).run('list("scratch")')

    assert result.ok is True
    assert result.output == ["s", "c", "r", "a", "t", "c", "h"]
    assert result.audit == []


def test_env_gate_denied_by_default(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DEMO_TOKEN", "token")
    result = MontyRunner(SafeboxConfig(), cwd=tmp_path).run('get_env("DEMO_TOKEN")')

    assert result.ok is True
    assert result.output["ok"] is False
    assert result.audit[-1].helper == "get_env"


def test_monty_error_is_readable(tmp_path: Path):
    result = MontyRunner(SafeboxConfig(), cwd=tmp_path).run("x +")

    assert result.ok is False
    assert result.error
