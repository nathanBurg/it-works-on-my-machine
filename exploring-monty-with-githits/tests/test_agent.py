from types import SimpleNamespace

from safebox.agent import AgentCode, SafeboxAgent, SYSTEM_PROMPT, _build_output_type, _friendly_model_error
from safebox.config import SafeboxConfig
from safebox.monty_runner import ExecutionResult


def test_system_prompt_uses_unambiguous_helper_names():
    assert "read_file(path)" in SYSTEM_PROMPT
    assert "write_file(path, content)" in SYSTEM_PROMPT
    assert "list_files(path)" in SYSTEM_PROMPT
    assert "get_env(name)" in SYSTEM_PROMPT
    assert "list(path)" not in SYSTEM_PROMPT
    assert "not pydantic-ai tools" in SYSTEM_PROMPT
    assert 'list_files("scratch")' in SYSTEM_PROMPT
    assert 'write_file("scratch/README.md"' in SYSTEM_PROMPT
    assert "code string" in SYSTEM_PROMPT


def test_default_ollama_uses_native_output():
    output_type = _build_output_type(SafeboxConfig())

    assert type(output_type).__name__ == "NativeOutput"


def test_ollama_cloud_does_not_use_native_output():
    config = SafeboxConfig()
    config.model.base_url = "https://ollama.com/v1"

    assert _build_output_type(config) is AgentCode


def test_non_ollama_does_not_use_native_output():
    config = SafeboxConfig()
    config.model.provider = "openai"
    config.model.model = "gpt-test"

    assert _build_output_type(config) is AgentCode


def test_tool_call_error_is_not_reported_as_ollama_connectivity():
    message = _friendly_model_error(SafeboxConfig(), RuntimeError("Tool 'list' exceeded max retries count of 1"))

    assert "tried to call a tool directly" in message
    assert "Could not reach Ollama" not in message


def test_non_connectivity_model_error_is_not_reported_as_ollama_connectivity():
    message = _friendly_model_error(SafeboxConfig(), RuntimeError("invalid structured output"))

    assert "did not return valid Monty code" in message
    assert "Could not reach Ollama" not in message


def test_connectivity_error_keeps_ollama_guidance():
    message = _friendly_model_error(SafeboxConfig(), RuntimeError("connection refused"))

    assert "Could not reach Ollama" in message
    assert "ollama serve" in message


def test_tool_call_generation_error_gets_corrective_retry(monkeypatch):
    prompts: list[str] = []

    class FakeAgent:
        def __init__(self, *_args, **_kwargs):
            self.calls = 0

        def run_sync(self, prompt: str):
            prompts.append(prompt)
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("Tool 'write_file' exceeded max retries count of 1")
            return SimpleNamespace(output=AgentCode(code="17 * 23", explanation="compute"))

    monkeypatch.setattr("pydantic_ai.Agent", FakeAgent)

    logs: list[str] = []

    class FakeRunner:
        def run(self, _code: str):
            return ExecutionResult(ok=True, output=391, stdout="", stderr="", error=None, audit=[])

    agent = SafeboxAgent(SafeboxConfig(), runner=FakeRunner(), log_step=logs.append)
    result = agent.run_turn("Create a README.md file in scratch.")

    assert result.execution.output == 391
    assert len(prompts) == 2
    assert "Do not call tools" in prompts[1]
    assert "code field" in prompts[1]
    assert "Model tried a tool call; retrying structured code generation" in logs
