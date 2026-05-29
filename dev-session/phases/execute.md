# execute

Execute the plan for the current dev session.

## Inputs

- `plan.md` — primary working document
- `spec.md` — for grounding
- Files referenced in each phase of the plan

## Outputs

- Code changes implemented per phase
- `plan.md` updated with ticked `- [x]` checkboxes for each verified item
- One git commit per phase (`Phase N: <name>`)

## Preferred mode: subagent-driven

If `superpowers:subagent-driven-development` is available, invoke it. It dispatches a fresh subagent per phase with two-stage review (spec compliance, then code quality) and isolates context per task. Fall back to inline execution only when the skill is unavailable or the user explicitly asks for inline.

## Process

1. **Load and review.** Read `plan.md` and `spec.md`. Check existing checkboxes — if some are already ticked, resume from the first unchecked phase. Critically review the plan: any concerns, missing pieces, ordering problems? If yes, raise them before starting. If not, proceed.

2. **For each phase:**
   - Read all files referenced in the phase before making changes.
   - **Test-first** (default): write the failing test (or tests) for the phase's behavior. Run them to confirm they fail with the expected error.
   - Implement the changes (via subagent per the preference above, or inline). Follow the plan's intent; if the codebase has diverged in a way the plan didn't anticipate, stop and surface the mismatch rather than silently improvising.
   - Run automated verification: `make lint`, `make test`, `make check` plus any phase-specific commands (see SKILL.md "Makefile-first" for fallbacks). Fix failures before proceeding.
   - **Verification before completion:** read the actual output before ticking any checkbox (see SKILL.md "Verification before completion").
   - Tick `- [ ]` → `- [x]` for each automated checkbox in `plan.md` as it passes.
   - **Pre-commit `git status` check.** Before committing, run `git status` and confirm: every file the phase intended to edit is staged; nothing unexpected is included. Catches the "subagent did `git mv` then edited but forgot `git add`" failure mode where a commit lands a renamed-but-stale file and tests still pass in the working tree.
   - Commit the phase as one commit with a descriptive message (`Phase N: <name>`). One commit per phase keeps phases independently revertable.
   - Present manual verification items to the user. In interactive mode, wait for confirmation before ticking manual checkboxes and proceeding to the next phase. In `express` mode, skip manual pauses (they happen at the branch self-review instead).

3. **Scope discipline.** Only make changes described in the plan. Do not refactor or clean up adjacent code, even if it's obviously messy. If you spot something worth fixing, note it for the user after the phase is done — don't fix it now.

4. **TDD opt-outs.** If a phase is genuinely not test-driven (pure docs, scaffolding without behavior, dependency bumps), state it explicitly when starting the phase rather than silently skipping the test-first step.

5. Do not push to remote — `pr` handles that.

## When to skip

- No `plan.md` exists. Run `plan` first; don't improvise.
- The "plan" is a single trivial edit. Make the edit and skip straight to `pr`.

## Resuming after context reset

If you're starting fresh in a new context window:
- **Verify working directory.** Run `pwd` and confirm you're inside the session's worktree (`.worktrees/{branch-name}/`). If not, `cd` there before doing anything else — running tests or commits from the main checkout will hit the wrong branch.
- Read `plan.md` — checked boxes show what's done.
- Verify by running the automated verification commands for the last completed phase. Trust completed work only after fresh evidence confirms it.
- Pick up from the first unchecked item.

## When to go back

For small mismatches between plan and codebase, adapt and continue (and note the adaptation). For fundamental issues — wrong API, missing dependency, structurally incorrect approach — stop and re-open `plan` or `brainstorm` rather than building on a broken foundation.
