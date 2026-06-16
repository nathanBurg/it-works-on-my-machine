from pathlib import Path

import safebox.phase2_cli as phase2_cli
from safebox.monty_runner import ExecutionResult
from safebox.monty_runner import MontyRunner
from safebox.phase2_cli import PHASE2_SYSTEM_PROMPT
from safebox.phase2_config import load_phase2_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_phase2_prompt_mentions_githits_helpers():
    assert "githits_search" in PHASE2_SYSTEM_PROMPT
    assert "githits_example" in PHASE2_SYSTEM_PROMPT
    assert "fetch_url" in PHASE2_SYSTEM_PROMPT
    assert "code string" in PHASE2_SYSTEM_PROMPT
    assert "Never put literal line breaks inside quoted strings" in PHASE2_SYSTEM_PROMPT
    assert 'response["ok"]' in PHASE2_SYSTEM_PROMPT
    assert "import json" in PHASE2_SYSTEM_PROMPT
    assert 'json.loads(response["value"])' in PHASE2_SYSTEM_PROMPT
    assert "Do not treat the helper" in PHASE2_SYSTEM_PROMPT
    assert "Only call write_file if the user explicitly asks" in PHASE2_SYSTEM_PROMPT
    assert "If the user only asks to summarize" in PHASE2_SYSTEM_PROMPT
    assert "pypi:pydantic-monty" in PHASE2_SYSTEM_PROMPT
    assert "Never call githits_search with an empty target" in PHASE2_SYSTEM_PROMPT
    assert "Do not wrap refusal dictionaries in prose strings" in PHASE2_SYSTEM_PROMPT
    assert 'result = write_file("scratch/githits-summary.md", summary)' in PHASE2_SYSTEM_PROMPT
    assert "result" in PHASE2_SYSTEM_PROMPT


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


def test_phase2_cli_prints_generated_code_on_final_execution_failure(monkeypatch, capsys):
    class FakeAgent:
        def run_turn(self, _message):
            return type(
                "Result",
                (),
                {
                    "attempts": 3,
                    "code": "githits_search(\"pydantic monty\", \"pypi:pydantic-monty\"",
                    "execution": ExecutionResult(
                        ok=False,
                        output=None,
                        stdout="",
                        stderr="",
                        error="missing closing parenthesis",
                        audit=[],
                    ),
                },
            )()

    inputs = iter(["Search GitHits.", "exit"])
    logger = phase2_cli.StepLogger()
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))

    assert phase2_cli.run_loop(FakeAgent(), logger) == 0

    out = capsys.readouterr().out
    assert "Execution failed after 3 attempts: missing closing parenthesis" in out
    assert "Generated code:" in out
    assert 'githits_search("pydantic monty", "pypi:pydantic-monty"' in out
