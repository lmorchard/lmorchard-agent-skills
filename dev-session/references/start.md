# Phase: Start

Look for an existing session directory to resume:

1. Check `.claude/dev-sessions/` first (most recent by timestamp prefix)
2. If nothing found there, check `docs/dev-sessions/` for older sessions

If a session is found, read all documents there for context and report the current state — which files exist, what the spec and plan say, and suggest the logical next phase.

If no session directory exists, create one under `.claude/dev-sessions/`:

1. Run `date +"%Y-%m-%d-%H%M"` to get the timestamp
2. Derive the slug from the current git branch name — strip prefixes like `feature/`, `fix/`, `chore/` etc. and convert to a readable short description. If not on a meaningful branch, ask for a short description.
3. Create the directory: `.claude/dev-sessions/{timestamp}-{slug}/`
4. Create these empty files: `spec.md`, `plan.md`, `notes.md`

Confirm what was created and suggest starting with the `brainstorm` phase to develop the spec.
