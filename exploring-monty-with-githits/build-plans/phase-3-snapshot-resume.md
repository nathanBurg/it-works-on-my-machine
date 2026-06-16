# Phase 3: Snapshot, Kill, And Resume

## Goal

Add a separate Phase 3 demo that uses Monty's real iterative execution and snapshot APIs to pause on a human approval helper, save local state, exit, and resume later.

## Scope

- Add `safebox-3`; keep `safebox` and `safebox-2` behavior unchanged.
- Use `pydantic_monty.Monty.start(...)`, `FunctionSnapshot.dump()`, `pydantic_monty.load_snapshot(...)`, and `FunctionSnapshot.resume(...)`.
- Store local snapshot state in `.safebox/`.
- Demonstrate approving or denying a pending write after process restart.

## CLI

```bash
uv run safebox-3 --config configs/phase3-snapshot.toml
uv run safebox-3 resume --approve
uv run safebox-3 resume --deny
```

## Demo Prompt

```text
Create scratch/phase3-demo.md, but pause for approval before writing it.
```

## Acceptance Criteria

- Initial run pauses at `request_approval(...)`, writes `.safebox/latest.snapshot` and `.safebox/latest.json`, and prints a clear snapshot-saved result.
- `resume --approve` reloads the Monty snapshot, resumes approval, dispatches `write_file(...)`, and writes only inside `scratch`.
- `resume --deny` reloads the snapshot, resumes approval with a refusal dictionary, and does not write the target file.
- Snapshot metadata contains no provider secret names or env values.
- Phase 1 and Phase 2 startup checks still pass.

## Verification

```bash
uv run pytest
uv run safebox --config configs/write-scratch.toml < /dev/null
uv run safebox-2 --config configs/phase2-githits.toml < /dev/null
uv run safebox-3 --config configs/phase3-snapshot.toml < /dev/null
```

## Assessments

Security: snapshots are local only; metadata excludes env values and provider secrets. Monty snapshot bytes may contain generated code and in-sandbox values, so `.safebox/` is treated as local runtime state.

Performance: snapshot files are small for the demo and add no overhead to Phase 1 or Phase 2.

Quality: Phase 3 uses a dedicated runner so earlier phase demos remain stable.

Documentation: README must document Phase 3 commands, prompt, expected behavior, and cleanup.

Breaking changes: none to existing commands or configs; Phase 3 adds `safebox-3`.
