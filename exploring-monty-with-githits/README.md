# Safebox Phase 1

Safebox is a local CLI demo for safely executing model-written Python with Monty. Phase 1 focuses on the safety boundary: filesystem and environment access start at zero and open only through local TOML policy.

## Smoke Tests

Run these from the `exploring-monty-with-githits/` directory. If your prompt already shows that directory, do not `cd exploring-monty-with-githits` again.

Passing checks:

```bash
uv run pytest
uv run safebox --config configs/deny-all.toml < /dev/null
uv run safebox --config configs/read-scratch.toml < /dev/null
uv run safebox --config configs/write-scratch.toml < /dev/null
DEMO_TOKEN=hello-demo uv run safebox --config configs/env-demo.toml < /dev/null
uv run safebox-2 --config configs/phase2-deny-all.toml < /dev/null
uv run safebox-2 --config configs/phase2-githits.toml < /dev/null
uv run safebox-3 --config configs/phase3-snapshot.toml < /dev/null
```

Expected failure checks:

```bash
uv run safebox --config configs/invalid-network.toml
uv run safebox --config configs/invalid-githits.toml
uv run safebox-2 --config configs/phase2-invalid-network.toml
```

The invalid-config checks should fail before the session starts with clear policy errors.

## Install

Requires Python 3.11+.

```bash
uv sync --dev
ollama serve
ollama pull gemma4:e4b
uv run safebox
```

The default model provider is Ollama with `gemma4:e4b` at `http://localhost:11434/v1`. Hosted providers can be configured later through `[model]`, but the provider API key remains host-only and is never exposed to Monty.

## Secure Defaults

If `safebox.toml` is missing, Safebox starts with secure defaults:

- no filesystem reads
- no filesystem writes
- no environment variable access
- no network access

## Example Config

```toml
[model]
provider = "ollama"
model = "gemma4:e4b"
base_url = "http://localhost:11434/v1"

[filesystem]
allow_read = ["README.md"]
allow_write = ["out"]

[env]
allow = ["DEMO_TOKEN"]

[network]
enabled = false

[helpers]
files = true
githits = false
```

Paths are resolved relative to the config file. Env vars are exact-name matches. `OPENAI_API_KEY` and other provider API keys are host-only and refused even if mistakenly allowlisted.

## What Phase 1 Can Do

- Run pure Python computation in Monty.
- Read, write, and list files only through allowlisted host helpers: `read_file`, `write_file`, and `list_files`.
- Read env vars only through the allowlisted `get_env` host helper.
- Show every granted or denied host access as a `[gate]` audit line.
- Print timed `[step +0.000s]` and `[turn +0.000s]` logs so the session is easy to narrate while the safety boundary is exercised.
- Render final output as `result: ...` or `refused: ...` instead of raw Python dictionaries.

## What Phase 1 Cannot Do

- No GitHits helper yet. That is Phase 2.
- No network access. That is Phase 2, scoped to GitHits only.
- No snapshot/resume. That is Phase 3.
- No shell helper.

## Phase 2: GitHits Helper Demo

Phase 2 is launched with `safebox-2`. The original `safebox` command remains the Phase 1 demo and keeps the same deny-by-default behavior.

Phase 2 adds GitHits-only network access through gated helpers. It still does not provide a shell helper or general HTTP access.

Prerequisites:

- Node.js 20+
- GitHits initialized and authenticated:
  ```bash
  npx githits@latest init
  ```
- Local Ollama running with `gemma4:e4b`

Run closed Phase 2 behavior:

```bash
uv run safebox-2 --config configs/phase2-deny-all.toml
```

Run GitHits-enabled Phase 2 behavior:

```bash
uv run safebox-2 --config configs/phase2-githits.toml
```

Try GitHits allow behavior:

```text
Use GitHits to search for how pydantic-monty runs code. Target pypi:pydantic-monty and summarize what you find.
```

Try general network deny behavior:

```text
Fetch https://example.com.
```

Try GitHits plus file write behavior:

```text
Use GitHits to search for how pydantic-monty runs code. Write the summary into scratch/githits-summary.md.
```

Expected behavior:

- GitHits calls are visible as `[gate] ALLOW githits_search ...` or `[gate] ALLOW githits_example ...`.
- General network attempts are visible as `[gate] DENY fetch_url ...`.
- File writes still go through `write_file` and remain scoped to `scratch`.

Expected gate examples:

```text
[gate] ALLOW githits_search ...
[gate] DENY fetch_url https://example.com - general network access is disabled
[gate] ALLOW write_file .../scratch/githits-summary.md - path is allowlisted for write
```

Clean up after Phase 2:

```bash
rm -f scratch/githits-search-summary.md scratch/githits-summary.md
```

Keep `scratch/notes.txt`; it is the committed seed file.

## Phase 3: Snapshot And Resume Demo

Phase 3 is launched with `safebox-3`. It uses Monty's iterative `start()` / `resume()` flow and `FunctionSnapshot.dump()` / `load_snapshot()` so a paused program can be resumed in a later process.

Run the Phase 3 session:

```bash
uv run safebox-3 --config configs/phase3-snapshot.toml
```

Try:

```text
Create scratch/phase3-demo.md, but pause for approval before writing it.
```

Expected first run behavior:

```text
[gate] ALLOW request_approval Write scratch/phase3-demo.md - human approval required
result: snapshot saved: .../.safebox/latest.snapshot
next: exit this session, then run:
uv run safebox-3 resume --approve --config configs/phase3-snapshot.toml
```

Do not type `proceed` inside the active `safebox-3` session. Exit or press Ctrl-C, then approve the pending action from a new run:

```bash
uv run safebox-3 resume --approve --config configs/phase3-snapshot.toml
```

Expected approval behavior:

```text
[gate] ALLOW request_approval Write scratch/phase3-demo.md - human approved pending action
[gate] ALLOW write_file .../scratch/phase3-demo.md - path is allowlisted for write
result: .../scratch/phase3-demo.md
```

To test denial, recreate the snapshot with the same prompt and then run:

```bash
uv run safebox-3 resume --deny --config configs/phase3-snapshot.toml
```

Expected denial behavior:

```text
[gate] DENY request_approval Write scratch/phase3-demo.md - human denied pending action
refused: approval denied
```

Clean up after Phase 3:

```bash
rm -rf .safebox
rm -f scratch/phase3-demo.md
```

Show invalid non-GitHits network config failing at startup:

```bash
uv run safebox-2 --config configs/phase2-invalid-network.toml
```

## Demo Configs

The `configs/` directory contains ready-to-run policies for showing the boundary changing live.

Start with explicit deny-all behavior:

```bash
uv run safebox --config configs/deny-all.toml
```

Try:

```text
Read README.md.
Create a README.md file in scratch.
```

Both should be refused.

Show read-only access to the safe scratch workspace:

```bash
uv run safebox --config configs/read-scratch.toml
```

Try:

```text
List files in scratch.
Create a README.md file in scratch.
```

Listing should be allowed, writing should be refused.
The generated Monty code should use `list_files("scratch")` for the allowed list operation and `write_file(...)` for the refused write.

Show narrow read/write access to scratch:

```bash
uv run safebox --config configs/write-scratch.toml
```

Try:

```text
Create a README.md file in scratch with a short hello-world demo description.
Create a README.md file in the project root.
```

The scratch write should be allowed. It may show one failed generation followed by a successful rewrite, especially with local models. The project-root write should be refused.
Expected gate labels are `write_file` for write attempts and `list_files` for directory listing.

Expected successful scratch write:

```text
[gate] ALLOW write_file .../scratch/README.md - path is allowlisted for write
result: .../scratch/README.md
```

Expected refused project-root write:

```text
[gate] DENY write_file .../README.md - path is not allowlisted for write
refused: path is not allowlisted for write: .../README.md
```

Clean up after the scratch write demo:

```bash
rm -f scratch/README.md
```

Generated code retry demo:

```text
Asking model to write Monty-compatible Python (attempt 1/3)
Generated code failed; asking model to rewrite (attempt 2/3)
Asking model to write Monty-compatible Python (attempt 2/3)
Execution complete
```

If all retries fail, Safebox prints the final error and the generated code so the failure is still narratable:

````text
Execution failed after 3 attempts: ...
Generated code:
```python
...
```
````

Show exact-name env access:

```bash
DEMO_TOKEN=hello-demo uv run safebox --config configs/env-demo.toml
```

Try:

```text
Read DEMO_TOKEN from the environment.
Read OPENAI_API_KEY from the environment.
```

`DEMO_TOKEN` should be allowed. Provider API keys remain refused.

Show invalid Phase 2 config failing at startup:

```bash
uv run safebox --config configs/invalid-network.toml
uv run safebox --config configs/invalid-githits.toml
```

Both should fail before the session starts with clear Phase 2-only messages.

## Manual Acceptance Checklist

- With no config, ask: `Compute 17 * 23.` It succeeds.
- With no config, ask: `Read README.md.` It is refused and the refusal is visible.
- Add `README.md` or the repo root to `allow_read`, restart, and ask again. It succeeds.
- Ask for `OPENAI_API_KEY` or a configured provider key. It is refused.
- Ask it to fetch a URL. It says network is unavailable or fails because no network helper exists.
- Confirm every granted or denied host access prints a `[gate]` line.
- Confirm no file is written outside `allow_write`.

## Tests

```bash
uv run pytest
```
