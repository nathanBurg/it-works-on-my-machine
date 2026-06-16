from __future__ import annotations

import argparse
from pathlib import Path

from .agent import SYSTEM_PROMPT, SafeboxAgent
from .cli import StepLogger, render_execution_failure, render_execution_result, render_stdout
from .config import ConfigError, SafeboxConfig, load_config
from .phase3_runner import Phase3Runner


PHASE3_SYSTEM_PROMPT = f"""
{SYSTEM_PROMPT}

Phase 3 approval helper is available only inside generated Monty code:
request_approval(reason)
Call request_approval before any write that asks for approval. It returns a gate dictionary.
If approval["ok"] is false, make that refusal the result. If approval["ok"] is true,
continue with the approved action. Assign result inside branches, then make result the
final expression after the branch.
For example:

approval = request_approval("Write scratch/phase3-demo.md")
if not approval["ok"]:
    result = approval
else:
    lines = ["Phase 3 resumed successfully."]
    content = "\\n".join(lines) + "\\n"
    result = write_file("scratch/phase3-demo.md", content)
result
""".strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safebox Phase 3 snapshot/resume demo")
    subparsers = parser.add_subparsers(dest="command")
    parser.add_argument("--config", type=Path, help="Path to safebox Phase 3 TOML policy file")

    resume_parser = subparsers.add_parser("resume", help="Resume the latest Safebox snapshot")
    approval = resume_parser.add_mutually_exclusive_group(required=True)
    approval.add_argument("--approve", action="store_true", help="Approve the pending action")
    approval.add_argument("--deny", action="store_true", help="Deny the pending action")
    resume_parser.add_argument("--config", type=Path, help="Path to safebox Phase 3 TOML policy file")

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

    if args.command == "resume":
        logger.session("Resuming Safebox Phase 3 snapshot")
        print_policy_summary(config)
        result = Phase3Runner(config).resume(approved=args.approve)
        render_turn_result(result, attempts=1, code="resume", logger=logger)
        return 0 if result.ok else 1

    logger.session("Starting Safebox Phase 3 session")
    print_policy_summary(config)
    agent = SafeboxAgent(config, runner=Phase3Runner(config), log_step=logger.turn, system_prompt=PHASE3_SYSTEM_PROMPT)
    return run_loop(agent, logger)


def run_loop(agent: SafeboxAgent, logger: StepLogger) -> int:
    while True:
        try:
            user_message = input("safebox-3> ").strip()
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
        render_turn_result(result.execution, attempts=result.attempts, code=result.code, logger=logger)


def render_turn_result(result, *, attempts: int, code: str, logger: StepLogger) -> None:
    for record in result.audit:
        logger.turn(f"Host gate call requested: {record.helper}")
        print(record.render())
    logger.turn("Returning result")
    rendered_stdout = render_stdout(result.stdout, output=result.output)
    if rendered_stdout:
        print(rendered_stdout, end="" if rendered_stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="")
    if result.ok:
        rendered = render_execution_result(result.output, result.audit, had_stdout=bool(result.stdout))
        if rendered:
            print(rendered)
    else:
        failure = type("Result", (), {"attempts": attempts, "code": code, "execution": result})()
        print(render_execution_failure(failure))


def print_policy_summary(config: SafeboxConfig) -> None:
    print("Safebox Phase 3")
    if config.used_defaults:
        print(f"config: secure defaults (no config found at {config.source_path})")
    else:
        print(f"config: {config.source_path}")
    print(
        "grants: "
        f"read={len(config.filesystem.allow_read)} "
        f"write={len(config.filesystem.allow_write)} "
        f"env={len(config.env.allow)} "
        "network=disabled snapshot=enabled"
    )
    if config.model.provider == "ollama":
        print(f"model: ollama {config.model.model} {config.model.effective_base_url()}")
    else:
        print(f"model: {config.model.provider} {config.model.model}")
