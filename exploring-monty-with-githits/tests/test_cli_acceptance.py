from pathlib import Path
from types import SimpleNamespace

import safebox.cli as cli
from safebox.cli import (
    main,
    print_policy_summary,
    render_completion_from_audit,
    render_execution_failure,
    render_execution_result,
    render_output,
    render_stdout,
)
from safebox.config import SafeboxConfig, load_config
from safebox.gates import AuditRecord


def test_help_works(capsys):
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    assert "Safebox Phase 1" in capsys.readouterr().out


def test_policy_summary_hides_secret_names(capsys):
    config = SafeboxConfig()
    config.env.allow = ["DEMO_TOKEN"]

    print_policy_summary(config)

    out = capsys.readouterr().out
    assert "grants: read=0 write=0 env=1 network=disabled" in out
    assert "model: ollama gemma4:e4b http://localhost:11434/v1" in out
    assert "DEMO_TOKEN" not in out


def test_config_path_loads(tmp_path: Path):
    config_path = tmp_path / "custom.toml"
    config_path.write_text('[env]\nallow = ["DEMO_TOKEN"]\n')

    config = load_config(config_path, cwd=tmp_path)

    assert config.env.allow == ["DEMO_TOKEN"]


def test_prompt_keyboard_interrupt_exits_cleanly(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _prompt: (_ for _ in ()).throw(KeyboardInterrupt()))

    assert main([]) == 0

    out = capsys.readouterr().out
    assert "[step +" in out
    assert "Loading config" in out


def test_runtime_keyboard_interrupt_exits_cleanly(monkeypatch, capsys):
    class InterruptingAgent:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_turn(self, _message):
            raise KeyboardInterrupt

    inputs = iter(["Compute 17 * 23."])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr(cli, "SafeboxAgent", InterruptingAgent)

    assert main([]) == 0

    assert "Interrupted." in capsys.readouterr().out


def test_step_logs_are_printed_for_successful_turn(monkeypatch, capsys):
    class Execution:
        audit = []
        stdout = ""
        stderr = ""
        ok = True
        output = 391
        error = None

    class Result:
        execution = Execution()

    class FakeAgent:
        def __init__(self, *_args, **kwargs):
            self.log_step = kwargs["log_step"]

        def run_turn(self, _message):
            self.log_step("Asking model to write Monty-compatible Python")
            self.log_step("Running generated code in Monty")
            self.log_step("Execution complete")
            return Result()

    inputs = iter(["Compute 17 * 23.", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr(cli, "SafeboxAgent", FakeAgent)

    assert main([]) == 0

    out = capsys.readouterr().out
    assert "[turn +" in out
    assert "Received user request" in out
    assert "Asking model to write Monty-compatible Python" in out
    assert "Running generated code in Monty" in out
    assert "Returning result" in out
    assert "result: 391" in out
    assert "Generated code:" not in out


def test_gate_audit_uses_new_helper_name_in_cli(monkeypatch, capsys):
    class Execution:
        audit = [AuditRecord("list_files", "ALLOW", "/tmp/scratch", "path is allowlisted for read")]
        stdout = ""
        stderr = ""
        ok = True
        output = {"ok": True, "value": ["notes.txt"]}
        error = None

    class Result:
        execution = Execution()

    class FakeAgent:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_turn(self, _message):
            return Result()

    inputs = iter(["List files in scratch.", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr(cli, "SafeboxAgent", FakeAgent)

    assert main([]) == 0

    out = capsys.readouterr().out
    assert "Host gate call requested: list_files" in out
    assert "[gate] ALLOW list_files /tmp/scratch - path is allowlisted for read" in out
    assert "result: ['notes.txt']" in out


def test_successful_gate_with_no_output_gets_completion_message():
    audit = [AuditRecord("write_file", "ALLOW", "/tmp/scratch/README.md", "path is allowlisted for write")]

    assert render_execution_result(None, audit) == "result: write_file completed; see gate log above"


def test_phase2_successful_gate_with_no_output_gets_completion_message():
    audit = [AuditRecord("githits_search", "ALLOW", "pypi:pydantic-monty", "GitHits helper is enabled")]

    assert render_execution_result(None, audit) == "result: githits_search completed; see gate log above"


def test_denied_gate_does_not_get_completion_message():
    audit = [AuditRecord("write_file", "DENY", "/tmp/README.md", "path is not allowlisted for write")]

    assert render_completion_from_audit(audit) is None


def test_no_audit_no_output_still_renders_nothing():
    assert render_execution_result(None, []) is None


def test_execution_failure_renders_attempt_count_and_code():
    result = SimpleNamespace(
        attempts=3,
        code='write_file("scratch/README.md", "# Demo',
        execution=SimpleNamespace(error="missing closing quote in string literal"),
    )

    rendered = render_execution_failure(result)

    assert "Execution failed after 3 attempts: missing closing quote in string literal" in rendered
    assert "Generated code:" in rendered
    assert '```python\nwrite_file("scratch/README.md", "# Demo\n```' in rendered


def test_phase1_cli_prints_generated_code_on_final_execution_failure(monkeypatch, capsys):
    class Execution:
        audit = []
        stdout = ""
        stderr = ""
        ok = False
        output = None
        error = "missing closing quote in string literal"

    class Result:
        execution = Execution()
        attempts = 3
        code = 'write_file("scratch/README.md", "# Demo'

    class FakeAgent:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_turn(self, _message):
            return Result()

    inputs = iter(["Create a README.md file in scratch.", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr(cli, "SafeboxAgent", FakeAgent)

    assert main([]) == 0

    out = capsys.readouterr().out
    assert "Execution failed after 3 attempts: missing closing quote in string literal" in out
    assert "Generated code:" in out
    assert 'write_file("scratch/README.md", "# Demo' in out


def test_ollama_model_builder_does_not_require_env(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    from safebox.agent import _build_model

    model = _build_model(SafeboxConfig())

    assert model is not None


def test_render_output_suppresses_none():
    assert render_output(None) is None
    assert render_output(None, had_stdout=True) is None


def test_render_output_formats_gate_refusal():
    assert render_output({"ok": False, "error": "Refused: path is not allowlisted"}) == (
        "refused: path is not allowlisted"
    )


def test_render_output_formats_stringified_gate_refusal():
    output = "{'ok': False, 'error': 'Refused: path is not allowlisted'}"

    assert render_output(output) == "refused: path is not allowlisted"


def test_render_output_formats_gate_success():
    assert render_output({"ok": True, "value": "hello"}) == "result: hello"


def test_render_output_formats_stringified_gate_success():
    output = "{'ok': True, 'value': 'scratch/README.md'}"

    assert render_output(output) == "result: scratch/README.md"


def test_render_output_formats_normal_value():
    assert render_output(8760) == "result: 8760"


def test_render_stdout_formats_printed_gate_result_when_output_is_none():
    stdout = "{'ok': False, 'error': 'Refused: env var is host-only: OPENAI_API_KEY'}\n"

    assert render_stdout(stdout, output=None) == "refused: env var is host-only: OPENAI_API_KEY"


def test_render_stdout_preserves_normal_stdout():
    assert render_stdout("hello\n", output=None) == "hello\n"
