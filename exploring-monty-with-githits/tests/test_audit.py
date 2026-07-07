import subprocess
from pathlib import Path

from safebox.audit import run_security_audit


def test_run_security_audit_fails_if_command_fails(monkeypatch):
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        return type("CompletedProcess", (), {"returncode": 1, "stdout": "", "stderr": "error: unknown command 'audit'"})()

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_security_audit("print('hello')")

    assert result["ok"] is False
    assert "error: unknown command 'audit'" in result["error"]
    assert calls[0][:3] == ["npx", "githits@latest", "audit"]
    assert "print('hello')" in Path(calls[0][3]).read_text()


def test_run_security_audit_succeeds_if_command_succeeds(monkeypatch):
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        return type("CompletedProcess", (), {"returncode": 0, "stdout": "clean", "stderr": ""})()

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_security_audit("print('hello')")

    assert result["ok"] is True
    assert result["value"] == "Audit passed"
