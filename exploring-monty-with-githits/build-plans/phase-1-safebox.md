# Phase 1 Safebox Build Plan

## Objective

Build `safebox`, a small local CLI demo that uses pydantic-ai to generate Python, executes that Python inside `pydantic-monty==0.0.18`, and exposes host filesystem/env access only through explicit, audited, config-gated external functions.

## Phase 1 Deliverable

A user can run:

```bash
safebox
```

Then:

- Ask for pure computation and get a successful answer.
- Ask to read a non-allowlisted file and see a refusal.
- Add the file/path to TOML config, restart, and read it successfully.
- Ask for an env var such as `OPENAI_API_KEY` and see a refusal.
- Ask for network access and see that no network helper exists in Phase 1.

## 1. Package Skeleton

Create a small Python package inside `exploring-monty-with-githits/`.

Planned structure:

```text
exploring-monty-with-githits/
  pyproject.toml
  README.md
  safebox/
    __init__.py
    __main__.py
    cli.py
    config.py
    gates.py
    monty_runner.py
    agent.py
  tests/
    test_config.py
    test_gates.py
    test_monty_runner.py
    test_cli_acceptance.py
```

Todo checks:

- [ ] `pyproject.toml` defines package metadata and `safebox` console script.
- [ ] `python -m safebox` works.
- [ ] `safebox --help` works.
- [ ] No Phase 2 or Phase 3 files are introduced prematurely.
- [ ] No generated/cache files are committed.

## 2. Dependencies And Version Pins

Use explicit pins for demo stability.

Dependencies:

- `pydantic-monty==0.0.18`
- `pydantic`
- `pydantic-ai==1.107.0`
- `pytest`

Todo checks:

- [ ] `pydantic-monty` is pinned to `0.0.18`.
- [ ] `pydantic-ai` is pinned, not floating.
- [ ] Install docs mention Python version requirement.
- [ ] Dependency install succeeds in a fresh venv.
- [ ] Dependency sanity check passes.

## 3. Config Loading And Validation

Implement `safebox/config.py`.

Default config behavior:

- Load `safebox.toml` from current working directory.
- Accept `--config PATH`.
- If no config exists, use secure defaults and print a clear message.
- Invalid config stops startup with a readable error.

Config shape:

```toml
[model]
provider = "ollama"
model = "gemma4:e4b"

[filesystem]
allow_read = []
allow_write = []

[env]
allow = []

[network]
enabled = false

[helpers]
files = true
githits = false
```

Validation:

- `allow_read` and `allow_write` must be lists of paths.
- Paths are resolved relative to the config file directory.
- Env allowlist must be exact env var names.
- `network.enabled` must be `false` in Phase 1.
- `helpers.githits = true` fails with a Phase 2-only message.

Todo checks:

- [ ] Missing config produces secure defaults.
- [ ] Invalid TOML fails with a readable error.
- [ ] Invalid field types fail with readable Pydantic errors.
- [ ] Relative paths resolve from config file directory.
- [ ] Empty allowlists are valid and default.
- [ ] `network.enabled = true` fails in Phase 1.
- [ ] `helpers.githits = true` fails clearly.

## 4. Audit Model

Implement a structured audit record in `gates.py`.

Fields:

- `helper`: `read`, `write`, `list`, `get_env`
- `decision`: `ALLOW` or `DENY`
- `target`: path or env var name
- `reason`: short human-readable reason

CLI rendering:

```text
[gate] DENY read /path/to/file - path is not allowlisted for read
[gate] ALLOW get_env DEMO_TOKEN - env var is allowlisted
```

Todo checks:

- [ ] Every gate call creates one audit record.
- [ ] Allowed calls are audited.
- [ ] Denied calls are audited.
- [ ] Audit records are testable as structured data.
- [ ] CLI output includes audit lines for every gate call.

## 5. Filesystem Gates

Implement host functions:

- `read(path: str) -> dict`
- `write(path: str, content: str) -> dict`
- `list(path: str) -> dict`

Return format:

```python
{"ok": True, "value": "..."}
{"ok": False, "error": "Refused: path is not allowlisted for read: ..."}
```

Path policy:

- Resolve requested paths before checking.
- Prevent `../` traversal escape.
- Prevent symlink escape.
- Allow exact path match.
- Allow descendants of allowlisted directories.
- `read` and `list` use `allow_read`.
- `write` uses `allow_write`.

Todo checks:

- [ ] Read outside allowlist is denied.
- [ ] Read inside allowlist succeeds.
- [ ] List outside allowlist is denied.
- [ ] List inside allowlist succeeds.
- [ ] Write outside allowlist is denied.
- [ ] Write inside allowlist succeeds.
- [ ] `../` traversal cannot escape an allowlisted directory.
- [ ] Symlink escape is denied.
- [ ] Denial messages are clear enough to show in the demo.

## 6. Env Gate

Implement:

- `get_env(name: str) -> dict`

Policy:

- Only exact names in `[env].allow` return values.
- Everything else denied.
- Provider API key env var is host-only and denied even if accidentally allowlisted.

Todo checks:

- [ ] Env var outside allowlist is denied.
- [ ] Env var inside allowlist succeeds.
- [ ] Missing env var inside allowlist returns a clear not-set result.
- [ ] Provider API key env var is denied.
- [ ] Env denials are audited.

## 7. Monty Runner

Implement `safebox/monty_runner.py`.

Responsibilities:

- Accept model-generated Python code.
- Register external functions.
- Capture stdout/stderr.
- Return structured result.
- Catch Monty errors and return readable failure data.

Todo checks:

- [ ] Pure computation works without helpers.
- [ ] Last expression result is returned.
- [ ] Printed output is captured.
- [ ] Gated helper calls work through `external_functions`.
- [ ] Monty syntax/runtime errors are returned cleanly.
- [ ] No network-capable function is registered.

## 8. Agent Wrapper

Implement `safebox/agent.py`.

Model contract:

- Agent returns structured output with `code` and `explanation`.
- Retry at most 2 times when Monty reports execution errors.
- Model provider config is read by the host only.

Todo checks:

- [ ] Agent returns structured code, not Markdown.
- [ ] System prompt includes Monty subset constraints.
- [ ] System prompt states network is unavailable.
- [ ] Retry loop is bounded.
- [ ] Retry failures are readable to the user.
- [ ] Model provider config is read by host only, never exposed to Monty.

## 9. CLI Loop

Implement `safebox/cli.py`.

Todo checks:

- [ ] CLI starts with no config.
- [ ] CLI starts with explicit config path.
- [ ] CLI prints policy summary.
- [ ] CLI repeats until exit/Ctrl-D.
- [ ] CLI displays gate audit lines.
- [ ] CLI displays final answer or clear failure.
- [ ] CLI does not print secret env values in audit logs.

## 10. Tests

Todo checks:

- [ ] Config tests cover missing, valid, invalid, and relative-path config.
- [ ] Gate tests cover allow, deny, traversal, and symlink behavior.
- [ ] Env tests cover allowed, denied, missing, and provider-key behavior.
- [ ] Monty tests cover pure compute, print capture, file gate, env gate, and errors.
- [ ] CLI tests avoid depending on live model access.
- [ ] Full test suite passes.

## 11. Manual Acceptance Checklist

Todo checks:

- [ ] With no config, ask: “Compute 17 * 23.” It succeeds.
- [ ] With no config, ask: “Read README.md.” It is refused and the refusal is visible.
- [ ] Add README or repo root to `allow_read`, restart, ask again. It succeeds.
- [ ] Ask for `OPENAI_API_KEY` or configured provider key. It is refused.
- [ ] Ask it to fetch a URL. It says network is unavailable or fails because no network helper exists.
- [ ] Confirm every granted/denied host access prints a `[gate]` line.
- [ ] Confirm no file is written outside `allow_write`.

## 12. Documentation

Todo checks:

- [ ] README explains secure default deny behavior.
- [ ] README includes example config.
- [ ] README explains local Ollama default.
- [ ] README explains hosted-provider fallback if supported.
- [ ] README explicitly says network/GitHits/snapshot are later phases.
- [ ] README includes manual acceptance checklist.

## Assessments

Security: Phase 1 defaults to no filesystem/env/network access. All host access is mediated by allowlisted functions. This is not a hardened multi-tenant sandbox.

Performance: CLI is single-user and synchronous. Local model latency is the main runtime cost. No optimization is needed in Phase 1.

Quality: Keep modules small and testable. Use structured result types instead of string parsing. Mock agent behavior for deterministic tests.

Documentation: Required because this is a teaching artifact. Demo commands should be copy-pasteable.

Breaking changes: No existing app code or public API exists. Adding the package and CLI is additive.
