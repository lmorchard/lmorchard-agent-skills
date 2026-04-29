# GitHub Projects integration

Optional. The skill moves issues across a GitHub Projects v2 board at phase boundaries (file → Ready, start → In Progress, pr → In Review). It only runs when the project's `CLAUDE.md` declares the board — otherwise every phase skips this silently.

## CLAUDE.md schema

Add a section like this to the project's `CLAUDE.md`:

```markdown
## GitHub Project

- **Owner:** `lmorchard` (user or org login)
- **Number:** `5` (project number from the board URL)
- **Status field:** `Status` (the single-select field used for column tracking)
- **Columns:**
  - `ready: Ready`
  - `in_progress: In Progress`
  - `in_review: In Review`
  - `done: Done`
```

The skill reads these as declarative names. The agent resolves the underlying GraphQL IDs at runtime — don't hand-write IDs into `CLAUDE.md`, they're noisy and tied to the field schema.

If any of `Owner`, `Number`, `Status field`, or the four `Columns` entries are missing, treat the integration as not configured and skip all transitions.

## ID resolution (once per phase)

GitHub Projects v2 needs four IDs to move an item: project ID, item ID, field ID, single-select option ID. Resolve them once, hold in memory:

```bash
# Project ID + status field + option IDs (one shot per session)
gh project field-list <number> --owner <owner> --format json

# Item ID for a specific issue (resolves the project-item ID, not the issue number)
gh project item-list <number> --owner <owner> --format json \
  | jq '.items[] | select(.content.url == "<issue-url>")'
```

If the issue isn't on the board yet (common after `file`), add it first:

```bash
gh project item-add <number> --owner <owner> --url <issue-url>
```

## Transition command

Single edit, one option at a time:

```bash
gh project item-edit \
  --project-id <project-id> \
  --id <item-id> \
  --field-id <status-field-id> \
  --single-select-option-id <target-option-id>
```

## When each phase transitions

| Phase | Transition | Notes |
|---|---|---|
| `file` | → `ready` | After issue creation. Add to project first if missing. |
| `start` (with issue URL) | → `in_progress` | After worktree setup, before brainstorm. Skip if no issue URL. |
| `pr` | → `in_review` | After the PR is opened (step 5 of pr.md). The linked issue is the one referenced via `Closes #N`. |
| (merge) | → `done` | Out of scope — `Closes #N` auto-closes the issue and most boards auto-move to Done on close. |

## When to skip

- No `## GitHub Project` section in `CLAUDE.md` — silent skip, no warning.
- `gh` CLI lacks the `project` scope — surface once with the fix (`gh auth refresh -s project`), then skip subsequent transitions in the session rather than re-prompting.
- Issue is already at the target column — no-op (don't transition to the same state).
- The phase ran without an issue URL (e.g., `start` with a free-form branch) — nothing to transition.

## Failure handling

Project transitions are non-load-bearing. If a transition fails (network error, permissions, board structure changed), report the failure and continue. Don't block the phase — the skill's primary job is the dev workflow, not board hygiene.

## Notes on use

- **Declarative names, not IDs.** The CLAUDE.md schema uses human names so it survives schema changes. The agent re-resolves IDs each session.
- **Resolve once, reuse.** ID resolution is the slow part of GitHub Projects API work. Cache for the session in memory; don't hit the API per transition.
- **One-time setup helper.** First-time CLAUDE.md authoring: have the agent run `gh project list --owner <owner>` to find the number and `gh project field-list` to confirm the column names. Paste the resolved names into `CLAUDE.md`.
