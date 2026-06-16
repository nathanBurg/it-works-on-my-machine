from pathlib import Path

import safebox.phase2_cli as phase2_cli
from safebox.monty_runner import MontyRunner
from safebox.phase2_cli import PHASE2_SYSTEM_PROMPT
from safebox.phase2_config import load_phase2_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_phase2_prompt_mentions_githits_helpers():
    assert "githits_search" in PHASE2_SYSTEM_PROMPT
    assert "githits_example" in PHASE2_SYSTEM_PROMPT
    assert "fetch_url" in PHASE2_SYSTEM_PROMPT
    assert "code string" in PHASE2_SYSTEM_PROMPT


def test_phase2_cli_starts_with_githits_config(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _prompt: (_ for _ in ()).throw(EOFError()))

    assert phase2_cli.main(["--config", str(PROJECT_ROOT / "configs" / "phase2-githits.toml")]) == 0

    out = capsys.readouterr().out
    assert "Safebox Phase 2" in out
    assert "network=githits-only" in out
    assert "helpers: files=true githits=true" in out


def test_monty_runner_executes_extra_helper():
    config = load_phase2_config(PROJECT_ROOT / "configs" / "phase2-deny-all.toml", cwd=PROJECT_ROOT)

    def extra():
        return {"ok": True, "value": "extra"}

    result = MontyRunner(config, extra_external_functions={"extra_helper": extra}).run("extra_helper()")

    assert result.ok is True
    assert result.output == {"ok": True, "value": "extra"}
