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
    assert "always make the helper result the final expression" in SYSTEM_PROMPT
    assert "result = write_file" in SYSTEM_PROMPT
    assert '"\\n".join(lines) + "\\n"' in SYSTEM_PROMPT
    assert "Never put literal line breaks inside quoted strings" in SYSTEM_PROMPT
    assert 'If the user says "in scratch"' in SYSTEM_PROMPT
    assert '"scratch/README.md"' in SYSTEM_PROMPT


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
            return ExecutionResult(ok=True, output=391, stdout="", stderr="", error=None, audit=[SimpleNamespace(helper="write_file")])

    agent = SafeboxAgent(SafeboxConfig(), runner=FakeRunner(), log_step=logs.append)
    result = agent.run_turn("Create a README.md file in scratch.")

    assert result.execution.output == 391
    assert len(prompts) == 2
    assert "Do not call tools" in prompts[1]
    assert "code field" in prompts[1]
    assert "Model tried a tool call; retrying structured code generation" in logs


def test_failed_code_is_included_in_retry_prompt(monkeypatch):
    prompts: list[str] = []
    generated_codes = iter(
        [
            AgentCode(code='write_file("scratch/README.md", "# Demo', explanation="bad quote"),
            AgentCode(code='result = write_file("scratch/README.md", "# Demo\\n")\nresult', explanation="fixed"),
        ]
    )

    class FakeAgent:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_sync(self, prompt: str):
            prompts.append(prompt)
            return SimpleNamespace(output=next(generated_codes))

    monkeypatch.setattr("pydantic_ai.Agent", FakeAgent)

    class FakeRunner:
        def __init__(self):
            self.calls = 0

        def run(self, code: str):
            self.calls += 1
            if self.calls == 1:
                return ExecutionResult(
                    ok=False,
                    output=None,
                    stdout="",
                    stderr="",
                    error="missing closing quote in string literal",
                    audit=[],
                )
            return ExecutionResult(
                ok=True,
                output="scratch/README.md",
                stdout="",
                stderr="",
                error=None,
                audit=[SimpleNamespace(helper="write_file")],
            )

    logs: list[str] = []
    agent = SafeboxAgent(SafeboxConfig(), runner=FakeRunner(), log_step=logs.append)

    result = agent.run_turn("Create a README.md file in scratch.")

    assert result.execution.ok is True
    assert result.attempts == 2
    assert len(prompts) == 2
    assert "missing closing quote in string literal" in prompts[1]
    assert 'write_file("scratch/README.md", "# Demo' in prompts[1]
    assert "Return only structured AgentCode" in prompts[1]
    assert "Keep helper results as the final expression" in prompts[1]
    assert "helpers return gate dictionaries" in prompts[1]
    assert "missing closing quote" in prompts[1]
    assert "join([...])" in prompts[1]
    assert "escaped" in prompts[1]
    assert "Preserve the requested path" in prompts[1]
    assert "scratch/<filename>" in prompts[1]
    assert "call the matching host helper" in prompts[1]
    assert "Asking model to write Monty-compatible Python (attempt 1/3)" in logs
    assert "Generated code failed; asking model to rewrite (attempt 2/3)" in logs
    assert "Asking model to write Monty-compatible Python (attempt 2/3)" in logs


def test_final_failed_attempt_does_not_log_another_retry(monkeypatch):
    class FakeAgent:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_sync(self, _prompt: str):
            return SimpleNamespace(output=AgentCode(code="1 / 0", explanation="fail"))

    monkeypatch.setattr("pydantic_ai.Agent", FakeAgent)

    class FakeRunner:
        def run(self, _code: str):
            return ExecutionResult(ok=False, output=None, stdout="", stderr="", error="division by zero", audit=[])

    logs: list[str] = []
    agent = SafeboxAgent(SafeboxConfig(), runner=FakeRunner(), log_step=logs.append)

    result = agent.run_turn("Divide by zero.", max_retries=1)

    assert result.attempts == 2
    assert logs.count("Generated code failed; asking model to rewrite (attempt 2/2)") == 1
    assert not any("attempt 3/2" in log for log in logs)


def test_file_request_retries_when_code_calls_no_helper(monkeypatch):
    prompts: list[str] = []
    generated_codes = iter(
        [
            AgentCode(code='content = "hello"\ncontent', explanation="forgot helper"),
            AgentCode(code='result = write_file("scratch/README.md", "hello")\nresult', explanation="uses helper"),
        ]
    )

    class FakeAgent:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_sync(self, prompt: str):
            prompts.append(prompt)
            return SimpleNamespace(output=next(generated_codes))

    monkeypatch.setattr("pydantic_ai.Agent", FakeAgent)

    class FakeRunner:
        def __init__(self):
            self.calls = 0

        def run(self, _code: str):
            self.calls += 1
            if self.calls == 1:
                return ExecutionResult(ok=True, output="hello", stdout="", stderr="", error=None, audit=[])
            return ExecutionResult(
                ok=True,
                output={"ok": True, "value": "scratch/README.md"},
                stdout="",
                stderr="",
                error=None,
                audit=[SimpleNamespace(helper="write_file")],
            )

    logs: list[str] = []
    agent = SafeboxAgent(SafeboxConfig(), runner=FakeRunner(), log_step=logs.append)

    result = agent.run_turn("Create a README.md file in scratch.")

    assert result.execution.output == {"ok": True, "value": "scratch/README.md"}
    assert result.attempts == 2
    assert "completed without calling the required host helper" in prompts[1]
    assert "write_file" in prompts[1]
    assert "Generated code skipped required helper; asking model to rewrite (attempt 2/3)" in logs


def test_pure_compute_does_not_require_host_helper(monkeypatch):
    class FakeAgent:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_sync(self, _prompt: str):
            return SimpleNamespace(output=AgentCode(code="17 * 23", explanation="compute"))

    monkeypatch.setattr("pydantic_ai.Agent", FakeAgent)

    class FakeRunner:
        def run(self, _code: str):
            return ExecutionResult(ok=True, output=391, stdout="", stderr="", error=None, audit=[])

    agent = SafeboxAgent(SafeboxConfig(), runner=FakeRunner())

    assert agent.run_turn("Compute 17 * 23.").execution.output == 391


def test_pure_write_prompt_does_not_require_host_helper(monkeypatch):
    class FakeAgent:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_sync(self, _prompt: str):
            return SimpleNamespace(output=AgentCode(code='"Autumn rain on glass"', explanation="haiku"))

    monkeypatch.setattr("pydantic_ai.Agent", FakeAgent)

    class FakeRunner:
        def run(self, _code: str):
            return ExecutionResult(ok=True, output="Autumn rain on glass", stdout="", stderr="", error=None, audit=[])

    agent = SafeboxAgent(SafeboxConfig(), runner=FakeRunner())

    result = agent.run_turn("Write a haiku.")

    assert result.execution.output == "Autumn rain on glass"
    assert result.attempts == 1


def test_pure_list_prompt_does_not_require_host_helper(monkeypatch):
    class FakeAgent:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_sync(self, _prompt: str):
            return SimpleNamespace(output=AgentCode(code="[2, 3, 5, 7, 11]", explanation="primes"))

    monkeypatch.setattr("pydantic_ai.Agent", FakeAgent)

    class FakeRunner:
        def run(self, _code: str):
            return ExecutionResult(ok=True, output=[2, 3, 5, 7, 11], stdout="", stderr="", error=None, audit=[])

    agent = SafeboxAgent(SafeboxConfig(), runner=FakeRunner())

    result = agent.run_turn("List the first five primes.")

    assert result.execution.output == [2, 3, 5, 7, 11]
    assert result.attempts == 1


def test_arithmetic_slash_does_not_require_host_helper(monkeypatch):
    class FakeAgent:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_sync(self, _prompt: str):
            return SimpleNamespace(output=AgentCode(code="10 / 2", explanation="divide"))

    monkeypatch.setattr("pydantic_ai.Agent", FakeAgent)

    class FakeRunner:
        def run(self, _code: str):
            return ExecutionResult(ok=True, output=5, stdout="", stderr="", error=None, audit=[])

    agent = SafeboxAgent(SafeboxConfig(), runner=FakeRunner())
    result = agent.run_turn("Compute 10/2.")

    assert result.execution.output == 5
    assert result.attempts == 1


def test_profile_substring_does_not_require_host_helper(monkeypatch):
    class FakeAgent:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_sync(self, _prompt: str):
            return SimpleNamespace(output=AgentCode(code='"A concise profile."', explanation="describe"))

    monkeypatch.setattr("pydantic_ai.Agent", FakeAgent)

    class FakeRunner:
        def run(self, _code: str):
            return ExecutionResult(ok=True, output="A concise profile.", stdout="", stderr="", error=None, audit=[])

    agent = SafeboxAgent(SafeboxConfig(), runner=FakeRunner())
    result = agent.run_turn("Describe a profile.")

    assert result.execution.output == "A concise profile."
    assert result.attempts == 1


def test_envelope_substring_does_not_require_host_helper(monkeypatch):
    class FakeAgent:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_sync(self, _prompt: str):
            return SimpleNamespace(output=AgentCode(code='"Fold the envelope neatly."', explanation="instructions"))

    monkeypatch.setattr("pydantic_ai.Agent", FakeAgent)

    class FakeRunner:
        def run(self, _code: str):
            return ExecutionResult(ok=True, output="Fold the envelope neatly.", stdout="", stderr="", error=None, audit=[])

    agent = SafeboxAgent(SafeboxConfig(), runner=FakeRunner())
    result = agent.run_turn("Fold an envelope.")

    assert result.execution.output == "Fold the envelope neatly."
    assert result.attempts == 1
