# retro

End the current dev session with a retrospective. The goal is captured learning, not metrics.

## Inputs

- Session artifacts: `spec.md`, `research.md`, `plan.md`
- Git history for the branch
- The conversation itself (what actually happened vs. what was planned)

## Outputs

- `notes.md` populated with the retrospective
- Optionally: new auto-memory entries, CLAUDE.md updates, or sketched skill changes — acted on now, not just listed

## Process

1. Think carefully about the session and **append** to `notes.md` in the session directory under a `## Retrospective` section — don't overwrite. `notes.md` may already contain a `## Filed` section from a prior `file` invocation, or other content. Cover:
   - **Brief recap** of what was actually built (or filed, if the session ended at `file`).
   - **Scope drift:** what changed between spec and ship, and why. (For file-terminated sessions: how the spec evolved during brainstorm.)
   - **Surprises:** things in the codebase or task that didn't match expectations.
   - **Workflow friction:** which phases were too thin, too thick, or produced something we didn't end up using.
   - **Misses:** questions we didn't ask that bit us, or answers we got that turned out not to matter.
   - **Memory candidates:** facts about the user, project, or codebase worth saving to auto-memory or CLAUDE.md.
   - **Skill candidates:** patterns from this session worth lifting into a skill or into this dev-session workflow itself.

   For file-terminated sessions, focus on spec/brainstorm quality rather than implementation: was the spec specific enough that an autonomous express run would succeed without re-asking? If not, what's missing from the brainstorm process?

2. Ask the user one or two open-ended questions worth recording — pick what feels most relevant given the session, don't survey.

## Landing the retro commit

`retro` normally runs before `pr`, so the retrospective rides along in the PR
squash. When it runs *after* the branch has merged — the user merged early, or
the session resumed post-merge — the session directory is already on `main` and
the branch is gone.

In that case don't commit to `main` directly and don't reopen the merged
branch. Cut a fresh `docs/<slug>-retro` branch from the updated `origin/main`,
append there, and open a small docs-only PR. Same review gate as any other
change; the retro is often where the most transferable findings are written
down, so it's worth the same visibility.

## What to skip

- Wall-clock time, token count, conversation turns — not actionable.
- "Efficiency insights" as an abstract category — too vague to act on.
- Generic "lessons learned" without a concrete next-time application.

## After writing

If `Memory candidates` or `Skill candidates` came up, offer to act on them — save the memory now, or sketch a skill update for review. Don't let learnings rot in `notes.md`.
