# Safe Code-Execution Agent: Demo Spec (Functional Requirements)

CLI command: `safebox`
Status: draft v1
Owner: Nathan

## 1. What this is

A small, runnable CLI demo that shows how to build an agent that safely executes
LLM-written code on the user's own machine, with permission boundaries that start
at zero and open up only when you explicitly grant them.

It is built in three phases that each ship something working:

1. An agent that executes code inside a sandbox with explicit filesystem and env var boundaries.
2. Helper functions the agent can call, including the GitHits CLI, plus selectively opening network access to GitHits only.
3. Snapshot logic so a session can be killed and resumed, including human-in-the-loop pauses.

The demo doubles as a real-world example of using GitHits to build against a brand
new library (Monty), which is the story we tell in the recorded walkthrough.

## 2. Goals and non-goals

Goals:
- Run entirely locally on the user's machine. No remote sandbox, no server to stand up.
- Beginner friendly. Someone should clone, set one API key, and run it in under five minutes.
- Make the safety model visible and obvious. The interesting moment is watching a denied action get denied, then granted.
- Keep the code small and readable. This is a teaching artifact, not a product.

Non-goals:
- Not a production sandbox or a hardened security boundary for hostile multi-tenant use.
- Not a general agent framework. One simple loop is enough.
- Not multi-language. Python only for executed code.
- No web UI. CLI only.

## 3. Audience and how it runs

Audience: developers trying the demo themselves, plus internal eng. Assume comfort
with a terminal and pip, but do not assume any prior knowledge of Monty, pydantic-ai,
or sandboxing.

Run model: `pip install` (or `uv`) into a fresh venv, set one model API key as an
env var, run `safebox` and start chatting with the agent. Everything else lives in a
local config file in the working directory.

## 4. Architecture overview

The whole design rests on one property of Monty: code running inside it has no access
to the host filesystem, environment variables, or network. Those are only reachable
through external functions that the host registers and Monty calls back into.

That inverts the usual sandbox model. Instead of running code and then trying to
restrict it, nothing exists inside the sandbox until we hand it in. Our permission
system is therefore just the decision of which host functions to register, and how to
gate them.

Three layers:

- Host process (Python): runs pydantic-ai, holds the model API key, owns the config and the gates. The model API key lives here and is never exposed to Monty.
- Monty interpreter: runs the Python the model writes. Pure computation by default. Reaches the outside world only via registered external functions.
- External functions (the gates): filesystem read/write, env read, GitHits CLI, and so on. Each one checks the config allowlist before doing anything.

Flow per turn: user message goes to the agent (pydantic-ai + model), the model writes
Python to accomplish the task, the host runs it in Monty, Monty calls back into gated
functions as needed, results return to the model, the model replies to the user.

## 5. Tech stack and key decisions

- Language: Python (host). Executed code: the Python subset Monty supports.
- Sandbox: Monty (`pydantic-monty`), pinned to `0.0.18` (it is pre-1.0 and moving fast, so we pin and note the version the demo was verified against).
- Agent: pydantic-ai. This is the only agent framework we use, and it pairs naturally with Monty since both are Pydantic projects.
- Model provider: provider-agnostic through pydantic-ai. Default is a local model via Ollama (`gemma4:e4b`), so the demo needs no API key and runs fully offline, which matches the "runs entirely on your machine" theme. A hosted provider keyed by env var is documented as a fallback for anyone who would rather not pull a local model.
- Config: a single local file (TOML), validated with Pydantic so a bad policy fails loudly with a clear message.

Local model sizing note: the default target is the 18GB M3 Pro, where Ollama sees roughly 12 GiB of GPU budget. `gemma4:e4b` (the GGUF/llama.cpp build, not the MLX build) runs at about 2.9 GiB resident with fast prefill and usable generation speed, and reliably makes GitHits tool calls. Larger Gemma 4 builds (12B and up) thrash on this hardware and are not viable. Sub-4B models are not recommended because tool-calling and code-writing reliability degrades at that size, which is exactly what the demo depends on. A small coder model (Qwen2.5-Coder 3B or Qwen3 4B class) is a reasonable alternative to A/B if snappier or cleaner tool calls are wanted.

Monty constraints to design around (as of the current pre-1.0 release): a subset of
Python only. No class definitions, match statements, context managers, or generators
yet, and only a small slice of the standard library (sys, os, typing, asyncio, re,
datetime, json). The agent's system prompt must steer the model to stay inside this
subset, and when the model writes something unsupported, the error is fed back so it
can rewrite. We treat that retry loop as expected behavior, not a failure, and the
demo should show it gracefully.

## 6. Phase 1: safe execution with filesystem and env boundaries

Goal: an agent that can execute model-written Python safely, where filesystem and env
var access are denied by default and granted only through config.

Functional requirements:

- F1.1 The CLI starts an interactive session: user types a request, agent responds, repeat.
- F1.2 The agent (pydantic-ai) produces Python that runs inside Monty. Pure computation (math, string work, JSON shaping) works with no special permission.
- F1.3 Filesystem access is mediated by gated host functions (read, write, list). Each call checks the requested path against an allowlist of paths from config. Paths outside the allowlist are refused with a clear message that surfaces to the user.
- F1.4 The filesystem allowlist is empty by default. A fresh run grants the agent zero filesystem access.
- F1.5 Env var access is mediated by a gated host function. Only names on the config allowlist return a value. Everything else returns refused, including the model provider API key.
- F1.6 The env var allowlist is empty by default, and can be added to programmatically and via config.
- F1.7 Network access is entirely off in phase 1. No network-capable external function is registered.
- F1.8 The policy lives in a config file (TOML), validated on load. An invalid policy stops startup with a readable error.
- F1.9 Every gated call (granted or denied) is visible in the session output, so the boundary is observable rather than hidden.

Acceptance criteria:

- Ask the agent to compute something with no IO. It succeeds without any grant.
- Ask it to read a path that is not allowlisted. It is refused, and the refusal is shown.
- Add that path to the config allowlist, restart, ask again. It now succeeds.
- Ask it to read an env var that is not allowlisted (including the provider API key). It is refused.
- Confirm no network call can be made by the executed code in this phase.

## 7. Phase 2: helper functions and scoped network access

Goal: give the agent useful capabilities as registered helper functions, with the
GitHits CLI as the headline, and use it to demonstrate opening network access to a
single destination.

Functional requirements:

- F2.1 Helper functions are registered as external functions Monty can call, each with a typed signature so the model knows how to call them.
- F2.2 The GitHits CLI is exposed as a helper. The agent can run GitHits searches and code lookups and receive results back into the session.
- F2.3 The GitHits helper is the first capability that needs network. Network is opened for it specifically, scoped to the GitHits destination only. This is the moment the demo uses to show controllable network access.
- F2.4 Network is strictly GitHits-only. Any attempt to reach any other destination is refused. The single-destination grant does not become general network access. The demo ships a small script (or set of agent prompts) that tries a non-GitHits fetch or web search and shows it being refused, making the boundary explicit.
- F2.5 Helpers respect the same config-driven gating as phase 1. A helper that is not enabled in config is not registered, and the agent cannot call it.
- F2.6 Helper calls and their results are visible in the session output, consistent with F1.9.

Helper set (locked, kept minimal):

- `githits_search` / `githits_code`: wrap the GitHits CLI commands. Headline capability, and the only network-gated helper (GitHits destination only).
- Scoped file helpers (`read`, `write`, `list`): the phase 1 gated functions, reused here as real task tools so the agent can, for example, write a result file into the working dir as part of a task.

No general `http_get` and no shell helper. Keeping network to GitHits only is deliberate, so the network story stays crisp and the refusal demo in F2.4 is unambiguous.

Acceptance criteria:

- With the GitHits helper enabled, ask the agent a question that requires looking something up through GitHits. It calls the helper and uses the result.
- Run the refusal script: an attempt to reach a non-GitHits destination is refused, and the refusal is shown.
- Have the agent complete a task that uses a file helper (for example, write its answer to a file in the working dir) and confirm the file lands only inside an allowlisted path.
- Disable the GitHits helper in config. The agent can no longer call it, and says so cleanly.

## 8. Phase 3: snapshot, kill, and resume

Goal: a session can be paused (including waiting on human approval), the process can be
killed, and a later run can rehydrate and continue from exactly where it left off.

What state must survive a snapshot:

- Monty interpreter state (serialized, small, single-digit kilobytes by design).
- Session context: the message history and the record of helper and tool calls.
- The working-directory filesystem (the jail), so files the agent created are still there on resume.

Resume model: rehydrate from serialized state, not bit-exact process resume. We
reconstruct the session and Monty state from disk and continue.

Functional requirements:

- F3.1 The agent can pause and wait for human approval before performing a flagged action (human in the loop).
- F3.2 While paused, the session can be killed entirely. No process or server stays running. The user can walk away for any length of time.
- F3.3 On kill, the snapshot is written: Monty state, session context, and the jail filesystem.
- F3.4 A resume command rehydrates from the snapshot and continues the session, including any pending approval that was outstanding at kill time.
- F3.5 After resume, granted permissions and registered helpers match what they were before, driven by the same config.
- F3.6 Snapshots are local files. No external storage.

Acceptance criteria:

- Start a session, have the agent create a file and accumulate some message history, then trigger an action that pauses for approval.
- Kill the process while paused. Confirm nothing is left running.
- Resume in a new run. Confirm the message history, the created file, and the pending approval are all intact, and the session continues correctly.
- Approve the pending action after resume and confirm it completes.

## 9. Config file shape (illustrative)

```toml
[model]
# Default: local model via Ollama, no API key needed.
provider = "ollama"
model = "gemma4:e4b"

# Hosted fallback (uncomment to use instead of local):
# provider = "openai"
# model = "gpt-..."
# api_key_env = "OPENAI_API_KEY"  # read by the host only, never exposed to Monty

[filesystem]
# empty by default: zero filesystem access
allow_read = []
allow_write = []

[env]
# empty by default: zero env var access
allow = []

[network]
enabled = false              # phase 1 default; in phase 2, opened for GitHits only

[helpers]
githits = false              # enabled in the phase 2 walkthrough; also scopes network to GitHits only
files = true                 # scoped read/write/list, bounded by the [filesystem] allowlists
```

## 10. CLI surface (initial)

- `safebox` : start or continue an interactive session in the current working dir.
- `safebox resume` : rehydrate the most recent snapshot and continue.
- `safebox --config PATH` : use a specific policy file.

Kept intentionally small. We can add flags later, but the demo should be runnable with
no flags at all.

## 11. Resolved decisions

- Default model provider: local model via Ollama (`gemma4:e4b`), no API key. Hosted provider documented as a fallback. See section 5 for the sizing rationale.
- Name and CLI command: `safebox`.
- Phase 2 helper set: the GitHits CLI plus the reused phase 1 scoped file read/write/list. No general `http_get`, no shell helper.
- Network: strictly GitHits-only, with a refusal demo proving other destinations fail.
- Monty version: pinned to `0.0.18`.

## 12. Out of scope (for this demo)

- Hardened isolation against actively hostile code.
- Multiple languages for executed code.
- Remote or shared execution.
- Web UI.
- Persistence beyond local snapshot files.