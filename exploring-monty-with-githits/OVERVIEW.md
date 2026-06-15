# Exploring Monty with GitHits

A hands-on walkthrough of using an AI coding assistant to learn and safely run code from a brand new library, with GitHits providing grounded, license-checked code examples.

We'll explore Monty ([pydantic/monty](https://github.com/pydantic/monty)), Pydantic's new microsecond-startup Python sandbox for running AI-generated code, using the GitHits CLI ([githits-com/githits-cli](https://github.com/githits-com/githits-cli)). Then we build a small agent that uses GitHits to write Monty code and test it end to end.

## Three parts

1. **Know your code.** Monty is brand new and changes often, so assistants tend to guess its API wrong. We use GitHits to check the license and dependencies, understand how we're allowed to use the code, screen for known exploits, and then explore how the project actually works. *Follow along.*

2. **Build it.** We have the assistant use GitHits to get correct context and make a plan, then build a small agent that runs code safely inside Monty's sandbox. *Follow along.*

3. **Where it goes.** Monty can snapshot a running program to a few kilobytes and resume it later, even in a different process. We'll pause an agent mid-task, save its state, and bring it back to life, then talk through what that makes possible. *Watch and discuss.*

## What you'll leave with

A clear way to use AI coding tools without shipping mystery code, and a working pattern for running untrusted code safely in pure Python, no Docker required.

## To follow along, bring

- A laptop with Python 3 and Node.js 20+
- Your AI coding assistant of choice (Claude Code, Cursor, or VS Code)
- Optional, to set up ahead of time: `pip install pydantic-monty`, and connect GitHits by running `npx githits@latest init`

---

## Prompts we'll use

Each prompt is written to be typed straight into your assistant, and each leans on GitHits. The tags note which GitHits skill the prompt exercises.

### Setup

Run `npx githits@latest init` to get started. It will ask how you want to connect:

- **Connect GitHits to my agent (Recommended)** runs the CLI onboarding flow and wires up your agent directly.
- **Use Agent Skills instead** installs the GitHits skills, including **githits-onboarding**. You then tell your agent to run **githits-onboarding** to sign up and configure your agents.

**This demo uses the Agent Skills**, so choose **Use Agent Skills instead** and make sure the skills are installed. The prompts below reference them by name (**githits-onboarding**, **githits-code**, **githits-package**), so you'll want them available to follow along. Do this before the demo starts so we begin in a clean, connected state.

**Prompt 0, verify the connection**

> Confirm GitHits is connected and the `search`, `search_language`, and `feedback` tools are available, then verify it's working by checking that you can reach the GitHits index.

### Section 1, Know your code (githits-code, githits-package)

This section is for understanding the project before we build on it: what we're legally clear to use, whether it's safe, and how the pieces we care about actually work.

**Prompt 1, license and dependencies first (githits-package)**

> Use the **githits-package** skill to look up `pydantic-monty`: its license, its dependencies, and the licenses of those dependencies. Lay out what we're working with before we touch the code.

**Prompt 2, how we can use it (githits-package)**

> Based on that license and the dependency licenses, explain how we're allowed to use this code: what's permitted, what's restricted, and anything to watch for if we build on it. GitHits filters out copyleft by default, so confirm whether anything here would have been flagged.

**Prompt 3, check for exploits (githits-package)**

> Using GitHits, check whether `pydantic-monty` or any of its dependencies have known vulnerabilities or security advisories. I want to know if there's anything risky before we run it.

#### Capability 1, running agent-generated code

We're building an agent that runs code in Monty, so first we get an overview of how that works.

**Prompt 4, how code goes in and runs (githits-code)**

> Using GitHits (**githits-code**), explore the `pydantic-monty` source to explain how a `pydantic_monty.Monty` instance is constructed and run: how code and `inputs` are passed, and how the result and stdout/stderr come back. Navigate the actual source and base your answer on what's in it, citing the files and lines you used.

**Prompt 5, host access through external functions (githits-code)**

> Using GitHits (**githits-code**), explore the source to explain how Monty gives sandboxed code access to host functions: how `external_functions` are passed in, and how the `start()` / `resume()` loop dispatches those calls one at a time so the host does the real work. Base your answer on the actual source and cite the files and lines.

> Then give me an overview of how running agent-generated code in Monty works, based on what you found in the source.

#### Capability 2, session snapshots

The other feature we care about is pausing and resuming a session.

**Prompt 6, snapshot and resume (githits-code)**

> Using GitHits (**githits-code**), dig through the source to explain how Monty's session snapshotting works: serializing parsed code with `dump()` / `load()`, pausing at an external call with `start()`, dumping live execution state and restoring it with `load_snapshot()`, then finishing with `resume()`, including resuming in a different process. Base your answer on the actual source and cite the files and lines.

> Then give me an overview of how snapshot and resume works and what state it captures, based on what you found in the source.

### Section 2, Build it (githits-code, githits-package)

We put the exploration to work:

- Use the GitHits context gathered in Section 1 to have the assistant create a plan for what we're building.
- Execute the plan, building a small agent that runs code safely inside Monty's sandbox.

### Section 3, Where it goes (githits-code)

We close on Monty's session snapshotting:

- Pause an agent mid-task, snapshot its state, and resume it, including across processes.
- Talk through what cheap, portable snapshots make possible.
