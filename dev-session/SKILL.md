---
name: dev-session
description: "Use when working through a multi-phase feature, bugfix, or GitHub issue that warrants tracked spec/plan/notes artifacts. Triggers: /dev-session command, /dev-session phase names (start/brainstorm/plan/execute/pr/retro/express), starting a new feature branch, picking up a GitHub issue."
---

# Dev Session

Structured workflow for development sessions. Each session moves through phases that produce inspectable artifacts (`spec.md`, `research.md`, `plan.md`, `notes.md`) so context survives across sessions and can be reviewed independently of the code.

## Dispatcher

Parse the first argument and read ONLY the matching phase file. Ignore the others.

| Argument | Phase file | Purpose |
|---|---|---|
| `start` | `phases/start.md` | Start or resume a session: branch + worktree + session dir |
| `brainstorm` | `phases/brainstorm.md` | Brainstorm a spec interactively (with codebase research substep) |
| `plan` | `phases/plan.md` | Write an implementation plan from the spec |
| `execute` | `phases/execute.md` | Execute the plan phase-by-phase with verification |
| `pr` | `phases/pr.md` | Self-review, squash, push, open PR, run Copilot review |
| `file` | `phases/file.md` | File the spec as a GitHub issue and stop (queue for later or parallel express) |
| `retro` | `phases/retro.md` | End the session with a learning-focused retrospective |
| `express` | `phases/express.md` | Interactive brainstorm → autonomous execution through PR |

If no argument is given, find the most recent session directory, read `spec.md`/`plan.md`/`notes.md` to assess current state, and suggest the most appropriate next phase.

## Producer / consumer pattern

Front-loading the high-attention work (research + brainstorm) and parallelizing the autonomous work later is the key workflow this skill supports:

1. **Producer:** `start` → `brainstorm` → `file` files a well-specified issue, then stops. Repeat across several sessions in one focused work block.
2. **Consumer:** later, run `/dev-session express <issue-url>` against any of those filed issues — possibly several in parallel. Express detects the embedded spec via the `<!-- dev-session:spec -->` marker and skips brainstorm, going straight to plan + execute + PR.

This separates "thinking" (you, focused) from "doing" (agent, autonomous).

## Shared conventions

**Session directory.** Session docs live in `docs/dev-sessions/{timestamp}-{slug}/` with `spec.md`, `research.md`, `plan.md`, and `notes.md`. `{timestamp}` is `$(date +"%Y-%m-%d-%H%M")`. Derive `{slug}` from the current git branch name (strip prefixes like `feature/`, `fix/`, `chore/`); otherwise ask for a short description.

**CLAUDE.md override.** Before creating session artifacts, check the project's `CLAUDE.md` for a "Dev Sessions" section or any mention of a non-default session directory. Some projects override the location — respect it if specified.

**Worktrees.** Prefer doing session work in a git worktree at `.worktrees/{branch-name}/` (relative to the project root) rather than switching branches in-place. Worktrees isolate the session from the main checkout, enabling concurrent agents and uninterrupted dev servers in other branches.

- **Preferred:** if `superpowers:using-git-worktrees` is available, invoke it. It handles directory priority, gitignore verification, dependency install auto-detection, and a baseline test run.
- **Fallback:** see the inline procedure in `phases/start.md`.
- Fall back to in-place branch switching only if the project can't support a worktree (uncommitted changes that must stay visible, tooling that requires a fixed path) or the user asks for it.

**Worktree gotcha.** Untracked files in the main checkout are NOT visible from worktrees. Always create the session directory inside the active worktree, not in the main checkout, and verify it's there before writing artifacts.

**Always rebase first.** Fetch and rebase from origin/main before creating new branches.

**Documentarian agent dispatch.** When dispatching a subagent (`Explore` or `general-purpose`) for codebase research, use the negation rules in `references/documentarian-prompt.md`. This keeps research factual and prevents the agent from rationalizing toward a chosen solution.

**Makefile-first.** Verification commands (`make lint`, `make test`, `make check`) assume a project Makefile per `references/makefile-conventions.md`. If a project lacks one, run native tooling and offer to scaffold the targets the skill expects. If a target the skill names is missing, add it before relying on it.

**GitHub Project board (optional).** If the project's `CLAUDE.md` declares a Projects v2 board (see `references/github-projects.md`), `file` / `start` / `pr` move issues across the board at phase boundaries (Ready → In Progress → In Review). Skipped silently when not configured.

**Test-driven by default.** In `execute`, write a failing test first, watch it fail, write minimal code to pass, watch it pass, refactor. The user may opt out for specific phases (pure refactoring, doc changes, infrastructure scaffolding without behavior), but the default is TDD.

**Subagent-driven execution.** When `superpowers:subagent-driven-development` is available, prefer it for `execute` — fresh subagent per phase, two-stage review (spec compliance + code quality), no context pollution. Fall back to inline only when the skill is unavailable or the user explicitly asks for it.

**Verification before completion.** Never claim a phase is done, tests pass, or a build succeeds without having run the verification command in the current message and read the output. Evidence before claims, always. No "should pass" / "I'm confident" / "looks correct" without fresh evidence. This applies in `execute` (per-phase) and `pr` (before opening).

## When NOT to use

- One-line tweaks, doc fixes, single-grep sed-replacements — overhead exceeds value.
- Exploratory or research-only work without an implementation goal.
- Work where the user has explicitly opted out of the structured flow.
