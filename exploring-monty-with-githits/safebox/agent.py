from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from .config import SafeboxConfig
from .monty_runner import ExecutionResult, MontyRunner


class AgentCode(BaseModel):
    code: str
    explanation: str


@dataclass(frozen=True)
class AgentTurnResult:
    explanation: str
    code: str
    execution: ExecutionResult
    attempts: int


SYSTEM_PROMPT = """
You are writing Python for Safebox Phase 1. Return structured output with code and explanation.
The code runs inside pydantic-monty, so keep it simple: no classes, no context managers,
no generators, and no match statements. Use ordinary functions, conditionals, loops,
lists, dicts, strings, numbers, json, re, datetime, sys, os, and typing when needed.
Host access is only available inside the Python code you write for Monty through these
external functions: read_file(path), write_file(path, content), list_files(path), and
get_env(name). These are not pydantic-ai tools. Do not try to call them directly as
agent tools. You must return only the structured AgentCode output requested by the host.
Put helper calls only inside the code string. Return code that calls them inside Monty.
For example:

files = list_files("scratch")
files

result = write_file("scratch/README.md", "Hello from Safebox.")
result

Network access is unavailable in Phase 1. Do not try to use sockets, requests, urllib,
shell commands, subprocess, or general HTTP fetches.
Make the final expression the value that should be returned to the user.
""".strip()


class SafeboxAgent:
    def __init__(self, config: SafeboxConfig, cwd=None, runner: MontyRunner | None = None, log_step=None):
        self.config = config
        self.runner = runner or MontyRunner(config, cwd=cwd)
        self.log_step = log_step or (lambda _message: None)

    def run_turn(self, user_message: str, max_retries: int = 2) -> AgentTurnResult:
        prompt = user_message
        last_code = ""
        last_explanation = ""
        last_execution: ExecutionResult | None = None
        for attempt in range(1, max_retries + 2):
            self.log_step("Asking model to write Monty-compatible Python")
            generated = self._generate_code(prompt)
            last_code = generated.code
            last_explanation = generated.explanation
            self.log_step("Running generated code in Monty")
            last_execution = self.runner.run(generated.code)
            if last_execution.ok:
                self.log_step("Execution complete")
                return AgentTurnResult(last_explanation, last_code, last_execution, attempt)
            self.log_step("Generated code failed; asking model to rewrite")
            prompt = (
                f"The previous code failed inside Monty with this error:\n{last_execution.error}\n"
                "Rewrite it to satisfy the original request while staying inside Monty's supported subset.\n"
                f"Original request: {user_message}"
            )
        assert last_execution is not None
        return AgentTurnResult(last_explanation, last_code, last_execution, max_retries + 1)

    def _generate_code(self, prompt: str) -> AgentCode:
        try:
            from pydantic_ai import Agent
        except ImportError as exc:  # pragma: no cover - exercised in real CLI environments
            raise RuntimeError("pydantic-ai is not installed; install the project dependencies") from exc

        agent = Agent(_build_model(self.config), output_type=_build_output_type(self.config), system_prompt=SYSTEM_PROMPT)
        try:
            result = agent.run_sync(prompt)
        except Exception as exc:
            if _is_tool_call_error(exc):
                self.log_step("Model tried a tool call; retrying structured code generation")
                retry_prompt = (
                    "You tried to call a tool directly. Do not call tools. Return structured AgentCode only. "
                    "The code field must contain Python code that calls write_file, read_file, list_files, "
                    "or get_env inside Monty. "
                    f"Original request: {prompt}"
                )
                try:
                    result = agent.run_sync(retry_prompt)
                except Exception as retry_exc:
                    message = _friendly_model_error(self.config, retry_exc)
                    raise RuntimeError(message) from retry_exc
                return result.output
            message = _friendly_model_error(self.config, exc)
            raise RuntimeError(message) from exc
        return result.output


def _build_model(config: SafeboxConfig):
    if config.model.provider == "ollama":
        from pydantic_ai.models.ollama import OllamaModel
        from pydantic_ai.providers.ollama import OllamaProvider

        return OllamaModel(
            config.model.model,
            provider=OllamaProvider(base_url=config.model.effective_base_url()),
        )
    return f"{config.model.provider}:{config.model.model}"


def _build_output_type(config: SafeboxConfig):
    if _is_self_hosted_ollama(config):
        from pydantic_ai.output import NativeOutput

        return NativeOutput(AgentCode)
    return AgentCode


def _is_self_hosted_ollama(config: SafeboxConfig) -> bool:
    base_url = config.model.effective_base_url() or ""
    return config.model.provider == "ollama" and "ollama.com" not in base_url


def _friendly_model_error(config: SafeboxConfig, exc: Exception) -> str:
    if _is_tool_call_error(exc):
        return (
            "Agent generation failed: the model tried to call a tool directly instead of returning Monty code. "
            f"Original error: {exc}"
        )
    if config.model.provider == "ollama":
        if not _is_ollama_connectivity_error(exc):
            return f"Agent generation failed: the model did not return valid Monty code. Original error: {exc}"
        base_url = config.model.effective_base_url()
        return (
            f"Could not reach Ollama at {base_url}. Start Ollama with `ollama serve` "
            f"and pull the model with `ollama pull {config.model.model}`. Original error: {exc}"
        )
    return str(exc)


def _is_tool_call_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "tool" in message and "exceeded max retries" in message


def _is_ollama_connectivity_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    indicators = (
        "connect",
        "connection",
        "connection refused",
        "could not connect",
        "server disconnected",
        "readerror",
        "connecterror",
        "timeout",
        "timed out",
        "network is unreachable",
        "name or service not known",
        "nodename nor servname provided",
    )
    return any(indicator in text for indicator in indicators)
