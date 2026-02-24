---
name: dev-session
description: "Manage structured development sessions with phases for starting, brainstorming specs, planning implementation, executing plans, and retrospectives. Use when starting a new dev session, brainstorming a feature spec, creating an implementation plan, executing a plan, or wrapping up a session. Invoke as /dev-session with an optional phase: start, brainstorm, plan, execute, or retro. Without a phase argument, assess current session state and suggest the appropriate next action."
---

# Dev Session

A dev session is a structured unit of development work focused on building a specific feature or a discrete phase of a larger feature. Each session is documented in its own directory and follows a lifecycle of phases.

## Session Directory

New sessions live at `.claude/dev-sessions/{timestamp}-{slug}` within the current project, where `{timestamp}` is `YYYY-MM-DDHHMM` and `{slug}` is a short description derived from the current git branch name (or provided by the user).

Older sessions may exist at `docs/dev-sessions/{timestamp}-{slug}` — check there when looking for prior session context, but always create new sessions under `.claude/dev-sessions/`.

The directory contains:
- `spec.md` — specification for the session
- `plan.md` — implementation plan
- `notes.md` — running notes and final retrospective

Use the built-in todo tools (TodoWrite/TodoRead) to track task progress during execution rather than a static `todo.md` file.

## Usage

Invoke as `/dev-session [phase]` where phase is one of: `start`, `brainstorm`, `plan`, `execute`, `retro`.

Without a phase argument: find the most recent session directory under `.claude/dev-sessions/` (falling back to `docs/dev-sessions/` for older sessions), read its files to assess current state, and suggest the most appropriate next action.

## Phases

Load the relevant reference file for the active phase:

- **start** — [references/start.md](references/start.md): Find or create the session directory and scaffold files
- **brainstorm** — [references/brainstorm.md](references/brainstorm.md): Iteratively develop the spec via Q&A
- **plan** — [references/plan.md](references/plan.md): Draft the step-by-step implementation plan
- **execute** — [references/execute.md](references/execute.md): Execute the plan with git commits per phase
- **retro** — [references/retro.md](references/retro.md): Write the session retrospective
