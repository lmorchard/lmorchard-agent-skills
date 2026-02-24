# Phase: Execute

Confirm that `plan.md`, `spec.md`, and `notes.md` exist in the current session directory. If any are missing, flag the issue before proceeding.

Read `plan.md` and `spec.md`. Assess whether the plan is detailed and actionable. If the plan is too vague or incomplete, say so and ask for clarification rather than guessing.

## Execution

Use the built-in todo tools (TodoWrite/TodoRead) to track progress through the plan steps. Load the plan steps as todos at the start.

While executing:
- Update `notes.md` as you go — record progress, decisions made, and any deviations from the plan along with the reason
- After each phase or major batch of changes, commit to git with a message summarizing what was done in that phase
- **Do NOT push to remote** — the user will review changes in git, and may revise or squash commits before pushing

## Git Commit Guidelines

- Commit after each logical phase of work, not after every small change
- Write commit messages that summarize the *purpose* of the phase, not just a list of files changed
- Stage specific files by name rather than `git add -A` to avoid accidentally including unintended files
