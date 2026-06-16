import subprocess
from types import SimpleNamespace

from safebox.githits_helpers import GitHitsHelperSet


def test_disabled_githits_search_refuses():
    helpers = GitHitsHelperSet(enabled=False)

    result = helpers.githits_search("query", "pypi:pydantic-monty")

    assert result["ok"] is False
    assert helpers.audit[-1].decision == "DENY"


def test_fetch_url_always_denies():
    helpers = GitHitsHelperSet(enabled=True)

    result = helpers.fetch_url("https://example.com")

    assert result["ok"] is False
    assert helpers.audit[-1].helper == "fetch_url"
    assert helpers.audit[-1].decision == "DENY"


def test_clear_audit_removes_previous_turn_records():
    helpers = GitHitsHelperSet(enabled=True)
    helpers.fetch_url("https://example.com")

    helpers.clear_audit()

    assert helpers.audit == []


def test_githits_search_builds_expected_argv(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"hits": []}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    helpers = GitHitsHelperSet(enabled=True)

    result = helpers.githits_search("run code", "pypi:pydantic-monty", source="code", limit=3)

    assert result == {"ok": True, "value": '{"hits": []}'}
    argv, kwargs = calls[0]
    assert argv == [
        "npx",
        "githits@latest",
        "search",
        "run code",
        "--in",
        "pypi:pydantic-monty",
        "--json",
        "--limit",
        "3",
        "--source",
        "code",
    ]
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == 30
    assert helpers.audit[-1].helper == "githits_search"


def test_githits_example_builds_expected_argv(monkeypatch):
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout='{"result": "ok"}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    helpers = GitHitsHelperSet(enabled=True)

    result = helpers.githits_example("sandbox python", lang="python")

    assert result["ok"] is True
    assert calls[0] == ["npx", "githits@latest", "example", "sandbox python", "--json", "--lang", "python"]


def test_githits_search_validates_source_and_limit():
    helpers = GitHitsHelperSet(enabled=True)

    assert helpers.githits_search("q", "target", source="web")["ok"] is False
    assert helpers.githits_search("q", "target", limit=11)["ok"] is False


def test_githits_nonzero_exit_returns_error(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr="no auth"),
    )
    helpers = GitHitsHelperSet(enabled=True)

    result = helpers.githits_search("q", "target")

    assert result == {"ok": False, "error": "GitHits command failed: no auth"}


def test_githits_timeout_returns_error(monkeypatch):
    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="githits", timeout=30)

    monkeypatch.setattr(subprocess, "run", fake_run)
    helpers = GitHitsHelperSet(enabled=True)

    assert helpers.githits_search("q", "target") == {"ok": False, "error": "GitHits command timed out"}
