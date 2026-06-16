# Demo Build Retrospective

## Demo Thesis

We used GitHits to avoid guessing a brand-new library's API, then used an agentic plan-review-execute loop to build and harden a local Monty demo in small working phases.

Presenter note: the goal is not to live-code the whole project. The goal is to show the loop, then jump to working phase demos that came out of that loop.

## The Loop

```text
Explore with GitHits -> Make a plan -> Review the plan -> Execute -> Test the demo path -> Feed failures back in
```

The important part is the feedback loop. Manual demo failures were useful because they showed where prompts, gates, and output rendering needed to become more explicit.

## Loop 1: Explore Before Building

Inputs:

- License and dependency checks for `pydantic-monty`.
- Vulnerability checks before running new code locally.
- Source exploration for `Monty.run(...)`, external functions, `start()`, `resume()`, `dump()`, and `load_snapshot()`.

Outputs:

- `PRODUCT_SPECS.md`
- `build-plans/phase-1-safebox.md`
- `build-plans/phase-2-githits-helper.md`
- `build-plans/phase-3-snapshot-resume.md`

Presenter note: this is the part that prevents the assistant from inventing APIs. GitHits grounds the plan in indexed source and docs.

## Loop 2: Phase 1, Safety Boundary

Plan:

- Build `safebox` as the Phase 1 CLI.
- Run model-written Python inside Monty.
- Expose host file/env access only through audited helpers.
- Keep network unavailable.

Review findings:

- Helper names needed to be unambiguous: `read_file`, `write_file`, `list_files`, `get_env`.
- The model needed to return Monty code, not call tools directly.
- Local model output needed stricter examples for safe multiline file writes.

Demo outcome:

- Writing to `scratch/README.md` is allowed.
- Writing to the project root is refused.
- Every host access prints a `[gate]` line.

Presenter note: this is the safety story. The sandbox starts with nothing, and the host chooses exactly which callbacks exist.

## Loop 3: Phase 2, GitHits Helper

Plan:

- Add `safebox-2` so Phase 1 remains stable.
- Add GitHits helpers as Monty external functions.
- Keep general network access refused.

Review findings:

- Phase 2 must preserve Phase 1 behavior.
- GitHits helper audit needed to reset per turn.
- Helper responses are gate dictionaries, not raw lists.
- The model needed an explicit default target: `pypi:pydantic-monty`.
- The prompt needed separate examples for summarize-only and write-to-file behavior.

Demo outcome:

- GitHits calls are allowed and audited.
- `Fetch https://example.com.` is denied and rendered as `refused: ...`.
- GitHits summaries can be written only to `scratch`.

Presenter note: this is the scoped-capability story. We open one useful network-backed capability without opening general network access.

## Loop 4: Phase 3, Snapshot And Resume

Plan:

- Add `safebox-3` so earlier phase demos stay intact.
- Use Monty's real iterative APIs: `start()`, `FunctionSnapshot.dump()`, `load_snapshot()`, and `resume()`.
- Pause on `request_approval(...)`, save a local snapshot, then resume with approve or deny.

Review findings:

- `MontyRunner.run()` was the wrong abstraction for snapshots because it runs to completion.
- Phase 3 needed a dedicated iterative runner.
- Snapshot metadata must avoid provider secrets and env values.
- The CLI needed to print the exact resume command so the user does not type `proceed` into the active session.

Demo outcome:

- The first run saves `.safebox/latest.snapshot`.
- `resume --approve` continues execution and writes `scratch/phase3-demo.md`.
- `resume --deny` continues execution and refuses without writing.

Presenter note: this is the future-looking story. A Monty execution can pause at a host boundary, become bytes on disk, and resume in another process.

## What The Audience Should Copy

- Explore source with GitHits before asking an agent to build against a new library.
- Ask for a plan before implementation.
- Review the plan before executing it.
- Build in small, working phases.
- Preserve previous phase behavior while adding new capability.
- Test the live demo path, not only unit tests.
- Treat model failures as feedback for prompts, gates, tests, and output rendering.

## What We Do Live

1. Run the GitHits Q&A prompts to understand Monty.
2. Show one plan-review-execute loop on screen.
3. Explain that the full build happened by repeating that loop.
4. Jump to the prebuilt phase demos:
   - Phase 1: filesystem safety boundary.
   - Phase 2: GitHits-only network helper.
   - Phase 3: snapshot, kill, and resume.

Presenter note: this keeps the demo honest. We show the process without pretending a polished multi-phase build should happen live in a few minutes.
