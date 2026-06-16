from pathlib import Path

from safebox.config import SafeboxConfig
from safebox.gates import GateSet


def config_for(tmp_path: Path, *, read=(), write=(), env=()) -> SafeboxConfig:
    config = SafeboxConfig()
    config.filesystem.allow_read = [Path(p).resolve() for p in read]
    config.filesystem.allow_write = [Path(p).resolve() for p in write]
    config.env.allow = list(env)
    return config


def test_read_outside_allowlist_denied(tmp_path: Path):
    target = tmp_path / "secret.txt"
    target.write_text("secret")
    gates = GateSet(config_for(tmp_path), cwd=tmp_path)

    result = gates.read_file("secret.txt")

    assert result["ok"] is False
    assert gates.audit[-1].decision == "DENY"
    assert gates.audit[-1].helper == "read_file"


def test_read_inside_allowlist_allowed(tmp_path: Path):
    target = tmp_path / "data.txt"
    target.write_text("hello")
    gates = GateSet(config_for(tmp_path, read=[target]), cwd=tmp_path)

    result = gates.read_file("data.txt")

    assert result == {"ok": True, "value": "hello"}
    assert gates.audit[-1].decision == "ALLOW"
    assert gates.audit[-1].helper == "read_file"


def test_list_inside_allowlist_allowed(tmp_path: Path):
    directory = tmp_path / "data"
    directory.mkdir()
    (directory / "a.txt").write_text("a")
    gates = GateSet(config_for(tmp_path, read=[directory]), cwd=tmp_path)

    result = gates.list_files("data")

    assert result == {"ok": True, "value": ["a.txt"]}
    assert gates.audit[-1].helper == "list_files"


def test_external_functions_expose_unambiguous_names(tmp_path: Path):
    gates = GateSet(config_for(tmp_path), cwd=tmp_path)

    functions = gates.external_functions()

    assert set(functions) == {"read_file", "write_file", "list_files", "get_env"}
    assert "read" not in functions
    assert "write" not in functions
    assert "list" not in functions


def test_write_outside_allowlist_denied(tmp_path: Path):
    gates = GateSet(config_for(tmp_path), cwd=tmp_path)

    result = gates.write_file("out.txt", "hello")

    assert result["ok"] is False
    assert not (tmp_path / "out.txt").exists()


def test_write_inside_allowlist_allowed(tmp_path: Path):
    out_dir = tmp_path / "out"
    gates = GateSet(config_for(tmp_path, write=[out_dir]), cwd=tmp_path)

    result = gates.write_file("out/result.txt", "hello")

    assert result["ok"] is True
    assert (out_dir / "result.txt").read_text() == "hello"
    assert gates.audit[-1].helper == "write_file"


def test_traversal_cannot_escape_allowlist(tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("secret")
    gates = GateSet(config_for(tmp_path, read=[allowed]), cwd=allowed)

    result = gates.read_file("../secret.txt")

    assert result["ok"] is False


def test_symlink_escape_denied(tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("secret")
    (allowed / "link.txt").symlink_to(secret)
    gates = GateSet(config_for(tmp_path, read=[allowed]), cwd=tmp_path)

    result = gates.read_file("allowed/link.txt")

    assert result["ok"] is False


def test_env_allow_deny_and_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DEMO_TOKEN", "token")
    gates = GateSet(config_for(tmp_path, env=["DEMO_TOKEN", "MISSING"]), cwd=tmp_path)

    assert gates.get_env("NOPE")["ok"] is False
    assert gates.get_env("DEMO_TOKEN") == {"ok": True, "value": "token"}
    assert gates.get_env("MISSING") == {"ok": True, "value": None}


def test_provider_api_key_denied_even_if_allowlisted(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    gates = GateSet(config_for(tmp_path, env=["OPENAI_API_KEY"]), cwd=tmp_path)

    result = gates.get_env("OPENAI_API_KEY")

    assert result["ok"] is False
    assert "secret" not in gates.audit[-1].render()
