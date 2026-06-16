# Phase 2 GitHits Helper Demo Plan

## Objective

Add a working Phase 2 demo build that exposes GitHits as a gated helper inside Monty while preserving Phase 1 behavior exactly.

## 1. Preserve Phase 1

Todo checks:

- [x] `safebox` remains Phase 1.
- [x] Phase 1 rejects `network.enabled = true`.
- [x] Phase 1 rejects `helpers.githits = true`.
- [x] Existing Phase 1 tests pass.

## 2. Add Phase 2 Entrypoint

Todo checks:

- [x] Add `safebox-2 = "safebox.phase2_cli:main"`.
- [x] `safebox-2 --help` works.
- [x] Startup prints `Safebox Phase 2`.
- [x] Startup prints helper and network state.

## 3. Add Phase 2 Config Model

Todo checks:

- [x] Phase 2 accepts `network.enabled = true` only with `allow = ["githits"]`.
- [x] Phase 2 rejects non-GitHits network allowlists.
- [x] Phase 2 requires GitHits network when `helpers.githits = true`.
- [x] Phase 1 config model remains strict.

## 4. Add Demo Configs

Todo checks:

- [x] Add `configs/phase2-deny-all.toml`.
- [x] Add `configs/phase2-githits.toml`.
- [x] Add `configs/phase2-invalid-network.toml`.
- [x] Tests cover each config.

## 5. Add GitHits Helpers

Todo checks:

- [x] Add `githits_search(query, target, source=None, limit=5)`.
- [x] Add `githits_example(query, lang=None)`.
- [x] Use fixed `subprocess.run([...], shell=False)` argv.
- [x] Validate search source.
- [x] Validate search limit.
- [x] Bound subprocess timeout.
- [x] Return structured `ok/value/error` results.

## 6. Add Refusal-Only Network Helper

Todo checks:

- [x] Add `fetch_url(url)`.
- [x] Always deny general network.
- [x] Do not perform network access.
- [x] Audit as `[gate] DENY fetch_url ...`.

## 7. Extend Runner And Agent

Todo checks:

- [x] `MontyRunner` accepts extra helpers.
- [x] `MontyRunner` surfaces extra helper audit records.
- [x] `SafeboxAgent` accepts phase-specific system prompt.
- [x] Phase 2 prompt documents GitHits helpers.

## 8. Tests

Todo checks:

- [x] Config tests cover Phase 2.
- [x] Helper tests mock subprocess.
- [x] Runner tests cover extra helpers.
- [x] CLI tests cover Phase 2 startup.
- [x] Phase 1 tests still pass.

## 9. Verification

Run:

```bash
uv run pytest
uv run safebox --config configs/deny-all.toml < /dev/null
uv run safebox --config configs/read-scratch.toml < /dev/null
uv run safebox --config configs/write-scratch.toml < /dev/null
uv run safebox-2 --config configs/phase2-deny-all.toml < /dev/null
uv run safebox-2 --config configs/phase2-githits.toml < /dev/null
uv run safebox-2 --config configs/phase2-invalid-network.toml
```

Manual GitHits prompt:

```text
Use GitHits to search for how pydantic-monty runs code. Target pypi:pydantic-monty and summarize what you find.
```

Manual network refusal prompt:

```text
Fetch https://example.com.
```

## Assessments

Security: Phase 2 adds fixed GitHits command wrappers, not shell access. General network is refusal-only.

Performance: GitHits subprocess calls are bounded by timeout and demo limits.

Quality: Phase 2 is additive via `safebox-2`; Phase 1 remains stable.

Documentation: README includes prerequisites and copy-paste commands.

Breaking changes: None for `safebox`; Phase 2 is additive.
