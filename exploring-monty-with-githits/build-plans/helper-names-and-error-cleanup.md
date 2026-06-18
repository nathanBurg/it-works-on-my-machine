# Helper Naming And Model Error Cleanup Plan

## Objective

Make Safebox's external helper API unambiguous and improve model-generation error messages.

Fix:

- `list("scratch")` being interpreted as Python's built-in `list`.
- pydantic-ai/tool-call confusion around helper names.
- Misleading `Could not reach Ollama...` errors for non-connectivity model failures.

## 1. Rename Monty External Helpers

Change the helper names exposed to Monty from:

```python
read(path)
write(path, content)
list(path)
get_env(name)
```

to:

```python
read_file(path)
write_file(path, content)
list_files(path)
get_env(name)
```

Implementation notes:

- Keep Python method names in `GateSet` if desired, but expose only the new names from `external_functions()`.
- Update audit helper labels to use the new names:
  - `read_file`
  - `write_file`
  - `list_files`
  - `get_env`
- Do not expose `list` anymore.

Todo checks:

- [ ] `GateSet.external_functions()` exposes `read_file`, `write_file`, `list_files`, `get_env`.
- [ ] `GateSet.external_functions()` does not expose `read`, `write`, or `list`.
- [ ] Audit records use `read_file`, `write_file`, and `list_files`.
- [ ] `list_files("scratch")` lists directory contents.
- [ ] `list("scratch")` is no longer a Safebox helper and behaves only as Python built-in behavior if generated.

## 2. Update System Prompt

Update `SYSTEM_PROMPT` in `safebox/agent.py`.

Replace:

```text
Host access is only available through external functions: read(path), write(path, content),
list(path), and get_env(name).
```

with explicit wording:

```text
Host access is only available inside the Python code you write for Monty through these external functions:
read_file(path), write_file(path, content), list_files(path), and get_env(name).

These are not pydantic-ai tools. Do not try to call them directly as agent tools.
Return code that calls them inside Monty.
```

Also add an example snippet to steer the model:

```python
files = list_files("scratch")
files
```

Todo checks:

- [ ] Prompt mentions `read_file`, `write_file`, `list_files`, `get_env`.
- [ ] Prompt does not mention old `read`, `write`, or `list` helpers.
- [ ] Prompt explicitly says helpers are available only inside generated Monty code.
- [ ] Prompt includes a short `list_files("scratch")` example.

## 3. Update User-Facing Docs And Demo Prompts

Update README demo prompts and descriptions.

Change examples from generic `Read README.md` and `List files in scratch` only if needed to include clearer phrasing. The user can still type natural language, but docs should mention what the model should generate:

```python
list_files("scratch")
read_file("scratch/notes.txt")
write_file("scratch/README.md", "...")
```

Update any docs that list helpers.

Todo checks:

- [ ] README helper names are `read_file`, `write_file`, `list_files`, `get_env`.
- [ ] README no longer documents `list(path)`.
- [ ] Demo flow still uses natural-language prompts.
- [ ] README includes expected gate labels with new names.

## 4. Improve Model Error Classification

Current `_friendly_model_error()` wraps every Ollama provider/model exception as:

```text
Could not reach Ollama...
```

That is misleading when the model is reachable but returns invalid structured output or tries a tool call.

Refine behavior:

- Only return the `Could not reach Ollama...` message for likely connection/server availability errors.
- For non-connectivity errors, return:
  ```text
  Agent generation failed: the model did not return valid Monty code. Original error: ...
  ```
- If the error includes `Tool` and `exceeded max retries`, make it more specific:
  ```text
  Agent generation failed: the model tried to call a tool directly instead of returning Monty code. Original error: ...
  ```

Implementation option:

- Add helper functions:
  - `_is_ollama_connectivity_error(exc: Exception) -> bool`
  - `_is_tool_call_error(exc: Exception) -> bool`
- Keep matching conservative via error text and common exception class names. Do not over-engineer provider-specific exception trees yet.

Todo checks:

- [ ] Connectivity-like errors still produce Ollama startup guidance.
- [ ] Tool-call errors do not produce Ollama connectivity guidance.
- [ ] Structured-output/model-generation errors do not produce Ollama connectivity guidance.
- [ ] Error messages remain concise and do not expose secrets.

## 5. Update Rendering And Gate Output Expectations

Current rendering is already mostly good:

- Gate refusal dicts render as `refused: ...`.
- `None` is suppressed.

Update expectations for renamed gate helpers:

- `[gate] ALLOW list_files ...`
- `[gate] DENY write_file ...`
- `[turn +...] Host gate call requested: list_files`

Todo checks:

- [ ] Gate audit lines show new helper names.
- [ ] Turn step logs show new helper names.
- [ ] Result rendering still suppresses `None`.
- [ ] Gate dicts still render as `refused: ...` or `result: ...`.

## 6. Tests

Add/update deterministic tests.

Gate tests:

- [ ] `external_functions()` includes `read_file`, `write_file`, `list_files`, `get_env`.
- [ ] `external_functions()` excludes `read`, `write`, `list`.
- [ ] `list_files` allowed path returns expected entries.
- [ ] `list_files` denied path returns a refusal.
- [ ] `read_file` and `write_file` preserve existing allow/deny behavior.

Monty runner tests:

- [ ] `list_files("scratch")` returns `{"ok": True, "value": [...]}` when scratch is allowlisted.
- [ ] `read_file("README.md")` is denied by default.
- [ ] `write_file("scratch/README.md", "...")` succeeds when scratch is allowlisted.
- [ ] `list("scratch")` does not hit a Safebox gate. It should either return Python built-in behavior or fail as normal Python, but no `[gate]` audit should appear.

Agent tests:

- [ ] `SYSTEM_PROMPT` contains `list_files`.
- [ ] `SYSTEM_PROMPT` does not contain `list(path)`.
- [ ] `_friendly_model_error()` maps `Tool 'list' exceeded max retries count of 1` to a tool-call/model-generation message.
- [ ] `_friendly_model_error()` keeps Ollama guidance for a representative connection error string.

CLI tests:

- [ ] Fake agent result with `list_files` audit renders `[gate] ALLOW list_files ...`.
- [ ] Step log says `Host gate call requested: list_files`.

Docs/config tests:

- [ ] Existing demo configs still load unchanged.
- [ ] README mentions new helper names.

## 7. Manual Acceptance Checks

After implementation:

1. Read-only config:
   ```bash
   uv run safebox --config configs/read-scratch.toml
   ```

2. Prompt:
   ```text
   List files in scratch.
   ```

Expected:

```text
[gate] ALLOW list_files .../scratch - path is allowlisted for read
result: ['notes.txt']
```

3. Prompt:

```text
Create a README.md file in scratch.
```

Expected:

```text
[gate] DENY write_file .../scratch/README.md - path is not allowlisted for write
refused: path is not allowlisted for write: ...
```

4. Write config:

```bash
uv run safebox --config configs/write-scratch.toml
```

5. Prompt:

```text
Create a README.md file in scratch with a short hello-world demo description.
```

Expected:

```text
[gate] ALLOW write_file .../scratch/README.md - path is allowlisted for write
result: .../scratch/README.md
```

6. Prompt:

```text
Write Python code that calls list("scratch") and returns the result.
```

Expected:

- It may return `['s', 'c', 'r', ...]` if the model follows that exact user instruction.
- No Safebox gate should be called.
- The README/demo prompts should steer away from this.

## Required Assessments

Security:

- No new capabilities are added.
- Renaming helpers reduces accidental host access confusion.
- Removing old names is safer than aliasing them because it narrows the exposed API.

Performance:

- No meaningful performance impact.
- Error classification is string/class-name based and negligible.

Quality:

- Explicit helper names improve model reliability and demo clarity.
- Tests should cover both helper exposure and user-visible audit names.

Documentation:

- Required because demo instructions currently imply ambiguous helper behavior.
- README should document `list_files`, not `list`.

Breaking changes:

- This breaks any existing generated code or tests using `read`, `write`, or `list`.
- Since Safebox is an in-progress demo and not a shipped API, this is acceptable.
- Do not add compatibility aliases unless you want to preserve old prompts; for the clean demo, remove them.
