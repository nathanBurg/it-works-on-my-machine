# Safebox Phase 1

Safebox is a local CLI demo for safely executing model-written Python with Monty. Phase 1 focuses on the safety boundary: filesystem and environment access start at zero and open only through local TOML policy.

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

Try:

```text
Use GitHits to search for how pydantic-monty runs code. Target pypi:pydantic-monty and summarize what you find.
Fetch https://example.com.
Write the GitHits summary into scratch/githits-summary.md.
```

Expected behavior:

- GitHits calls are visible as `[gate] ALLOW githits_search ...` or `[gate] ALLOW githits_example ...`.
- General network attempts are visible as `[gate] DENY fetch_url ...`.
- File writes still go through `write_file` and remain scoped to `scratch`.

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

The scratch write should be allowed. The project-root write should be refused.
Expected gate labels are `write_file` for write attempts and `list_files` for directory listing.

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
