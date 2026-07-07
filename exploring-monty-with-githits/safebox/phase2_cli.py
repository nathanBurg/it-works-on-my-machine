from __future__ import annotations

import argparse
from pathlib import Path

from .agent import SYSTEM_PROMPT, SafeboxAgent
from .cli import StepLogger, render_execution_failure, render_execution_result, render_stdout
from .config import ConfigError
from .githits_helpers import GitHitsHelperSet
from .monty_runner import MontyRunner
from .phase2_config import SafeboxPhase2Config, load_phase2_config


PHASE2_SYSTEM_PROMPT = f"""
{SYSTEM_PROMPT}

Phase 2 GitHits helpers are available only inside the generated Monty code:
githits_search(query, target, source=None, limit=5)
githits_example(query, lang=None)
githits_screen(package)
fetch_url(url) exists only to demonstrate refusal of general network access.
Do not call these as pydantic-ai tools. Put helper calls only inside the code string.
Network access is GitHits-only. General network fetches must use fetch_url(url), which will be refused.
githits_search, githits_example, and githits_screen return {{"ok": True, "value": "...json text..."}} on success.
They return {{"ok": False, "error": "..."}} on refusal or failure.
Always check response["ok"] before reading response["value"]. The value is JSON text,
so import json and use json.loads(response["value"]) before reading results. Do not treat the helper
response itself as a list.
If any helper returns {{"ok": False, "error": "..."}}, make that helper response the final result.
Do not wrap refusal dictionaries in prose strings.
If the user mentions pydantic-monty and does not provide a target, use "pypi:pydantic-monty".
Never call githits_search with an empty target.
The githits_screen helper returns vulnerability and license metadata for a specific package name.
Only call write_file if the user explicitly asks to write, save, create, or store a file.
If the user only asks to summarize, return a summary string as the final expression.

Summarize-only example:

import json

response = githits_search("pydantic-monty run code", "pypi:pydantic-monty")
if not response["ok"]:
    result = response
else:
    data = json.loads(response["value"])
    results = data.get("results", [])
    summary = "No GitHits results found."
    if results:
        first = results[0]
        summary = first.get("summary", first.get("title", "No summary found."))
    result = summary
result

Write-summary example:

import json

response = githits_search("pydantic-monty run code", "pypi:pydantic-monty")
if not response["ok"]:
    result = response
else:
    data = json.loads(response["value"])
    results = data.get("results", [])
    summary = "No GitHits results found."
    if results:
        first = results[0]
        summary = first.get("summary", first.get("title", "No summary found."))
    result = write_file("scratch/githits-summary.md", summary)
result
""".strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safebox Phase 2 GitHits helper demo")
    parser.add_argument("--config", type=Path, help="Path to safebox Phase 2 TOML policy file")
    args = parser.parse_args(argv)

    logger = StepLogger()
    logger.session("Loading config")
    try:
        config = load_phase2_config(args.config)
    except ConfigError as exc:
        print(exc)
        return 2

    if config.used_defaults:
        logger.session("Using secure defaults")
    else:
        logger.session(f"Using config: {config.source_path}")
    logger.session("Starting Safebox Phase 2 session")
    print_policy_summary(config)

    githits = GitHitsHelperSet(enabled=config.helpers.githits)
    runner = MontyRunner(
        config,
        extra_external_functions=githits.external_functions(),
        extra_audit_sources=[githits],
    )
    agent = SafeboxAgent(config, runner=runner, log_step=logger.turn, system_prompt=PHASE2_SYSTEM_PROMPT)
    return run_loop(agent, logger)


def run_loop(agent: SafeboxAgent, logger: StepLogger) -> int:
    while True:
        try:
            user_message = input("safebox-2> ").strip()
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
            rendered = render_execution_result(
                result.execution.output,
                result.execution.audit,
                had_stdout=bool(result.execution.stdout),
            )
            if rendered:
                print(rendered)
        else:
            print(render_execution_failure(result))


def print_policy_summary(config: SafeboxPhase2Config) -> None:
    print("Safebox Phase 2")
    if config.used_defaults:
        print(f"config: secure defaults (no config found at {config.source_path})")
    else:
        print(f"config: {config.source_path}")
    network = "githits-only" if config.network.enabled else "disabled"
    print(
        "grants: "
        f"read={len(config.filesystem.allow_read)} "
        f"write={len(config.filesystem.allow_write)} "
        f"env={len(config.env.allow)} "
        f"network={network}"
    )
    print(f"helpers: files={str(config.helpers.files).lower()} githits={str(config.helpers.githits).lower()}")
    if config.model.provider == "ollama":
        print(f"model: ollama {config.model.model} {config.model.effective_base_url()}")
    else:
        print(f"model: {config.model.provider} {config.model.model}")
