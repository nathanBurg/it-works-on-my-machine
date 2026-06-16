from __future__ import annotations

import argparse
import ast
from pathlib import Path
from time import monotonic
from typing import Any

from .agent import SafeboxAgent
from .config import ConfigError, SafeboxConfig, load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safebox Phase 1 local code-execution demo")
    parser.add_argument("--config", type=Path, help="Path to safebox.toml policy file")
    args = parser.parse_args(argv)

    logger = StepLogger()
    logger.session("Loading config")
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(exc)
        return 2

    if config.used_defaults:
        logger.session("Using secure defaults")
    else:
        logger.session(f"Using config: {config.source_path}")
    logger.session("Starting Safebox Phase 1 session")
    print_policy_summary(config)
    agent = SafeboxAgent(config, log_step=logger.turn)
    while True:
        try:
            user_message = input("safebox> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            return 0
        if user_message.lower() in {"exit", "quit"}:
            return 0
        if not user_message:
            continue
        logger.start_turn()
        logger.turn("Received user request")
        try:
            result = agent.run_turn(user_message)
        except KeyboardInterrupt:
            print("\nInterrupted.")
            return 0
        except Exception as exc:
            print(f"Agent error: {exc}")
            continue
        for record in result.execution.audit:
            logger.turn(f"Host gate call requested: {record.helper}")
            print(record.render())
        logger.turn("Returning result")
        rendered_stdout = render_stdout(result.execution.stdout, output=result.execution.output)
        if rendered_stdout:
            print(rendered_stdout, end="" if rendered_stdout.endswith("\n") else "\n")
        if result.execution.stderr:
            print(result.execution.stderr, end="")
        if result.execution.ok:
            rendered = render_execution_result(result.execution.output, result.execution.audit, had_stdout=bool(result.execution.stdout))
            if rendered:
                print(rendered)
        else:
            print(render_execution_failure(result))


def print_policy_summary(config: SafeboxConfig) -> None:
    print("Safebox Phase 1")
    if config.used_defaults:
        print(f"config: secure defaults (no config found at {config.source_path})")
    else:
        print(f"config: {config.source_path}")
    print(
        "grants: "
        f"read={len(config.filesystem.allow_read)} "
        f"write={len(config.filesystem.allow_write)} "
        f"env={len(config.env.allow)} "
        "network=disabled"
    )
    if config.model.provider == "ollama":
        print(f"model: ollama {config.model.model} {config.model.effective_base_url()}")
    else:
        print(f"model: {config.model.provider} {config.model.model}")


def render_output(output: Any, *, had_stdout: bool = False) -> str | None:
    if output is None:
        return None
    if isinstance(output, str):
        parsed = _parse_stringified_gate_result(output)
        if parsed is not None:
            return render_output(parsed, had_stdout=had_stdout)
    if isinstance(output, dict) and output.get("ok") is False and "error" in output:
        return f"refused: {_strip_refused_prefix(str(output['error']))}"
    if isinstance(output, dict) and output.get("ok") is True and "value" in output:
        return f"result: {output['value']}"
    parsed = _parse_stringified_gate_result(str(output))
    if parsed is not None:
        return render_output(parsed, had_stdout=had_stdout)
    if had_stdout:
        return f"result: {output}"
    return f"result: {output}"


def render_execution_result(output: Any, audit, *, had_stdout: bool = False) -> str | None:
    rendered = render_output(output, had_stdout=had_stdout)
    if rendered is not None:
        return rendered
    return render_completion_from_audit(audit)


def render_completion_from_audit(audit) -> str | None:
    if not audit:
        return None
    last = audit[-1]
    if last.decision != "ALLOW":
        return None
    return f"result: {last.helper} completed; see gate log above"


def render_execution_failure(result) -> str:
    return (
        f"Execution failed after {result.attempts} attempts: {result.execution.error}\n"
        "Generated code:\n"
        f"```python\n{result.code}\n```"
    )


def render_stdout(stdout: str, *, output: Any) -> str | None:
    if not stdout:
        return None
    if output is None:
        parsed = _parse_stringified_gate_result(stdout)
        if parsed is not None:
            return render_output(parsed)
    return stdout


def _parse_stringified_gate_result(output: str) -> dict[str, Any] | None:
    stripped = output.strip()
    if "'ok'" not in stripped and '"ok"' not in stripped:
        return None
    if not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        stripped = stripped[start : end + 1]
    try:
        parsed = ast.literal_eval(stripped)
    except (SyntaxError, ValueError):
        return None
    if isinstance(parsed, dict) and "ok" in parsed:
        return parsed
    return None


def _strip_refused_prefix(error: str) -> str:
    prefix = "Refused: "
    if error.startswith(prefix):
        return error[len(prefix) :]
    return error


class StepLogger:
    def __init__(self):
        self.session_start = monotonic()
        self.turn_start = self.session_start

    def start_turn(self) -> None:
        self.turn_start = monotonic()

    def session(self, message: str) -> None:
        print(f"[step +{monotonic() - self.session_start:.3f}s] {message}")

    def turn(self, message: str) -> None:
        print(f"[turn +{monotonic() - self.turn_start:.3f}s] {message}")
