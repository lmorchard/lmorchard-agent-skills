# file

Terminal phase. File the current spec as a GitHub issue and stop. Use this when you've front-loaded the high-attention work (research + brainstorm) and want to queue the work for later — yourself or someone else can pick it up via `/dev-session start <issue-url>` or `/dev-session express <issue-url>`.

## Inputs

- `spec.md` — must be complete and self-reviewed (run `brainstorm` first if not)
- `research.md` — referenced from the issue body if it contains useful context
- Repo context (current working directory must be inside a GitHub-backed repo)

## Outputs

- New GitHub issue containing the spec, marked with `<!-- dev-session:spec -->` so future `start` / `express` runs recognize it
- Issue URL appended to `notes.md` for traceability
- Optional: labels/assignees applied per project convention

## Process

1. **Confirm spec is ready.** Verify `spec.md` against the **Readiness checklist** in `references/spec-template.md`. If any criterion fails, refuse and recommend `brainstorm` first — a filed spec that's incomplete defeats the purpose.

2. **Confirm gh CLI access.** Run `gh repo view --json nameWithOwner` to confirm the working directory maps to a GitHub repo and `gh` is authenticated. If not, surface the error rather than guessing.

3. **Build the issue body.** Format:
   ```markdown
   <!-- dev-session:spec -->

   [contents of spec.md, lightly adapted]

   ---

   _Filed by `/dev-session file` from session `{session-dir}`. To resume:_
   _`/dev-session start <this-issue-url>` (interactive) or `/dev-session express <this-issue-url>` (autonomous)._
   ```

   Adaptations to the spec body:
   - Drop the "Source" line (the issue IS the source).
   - Drop "Open questions" entirely if all questions were resolved during self-review; otherwise leave them with their default answers so the resumer knows what was assumed.
   - Keep `file:line` references as-is, even though they'll drift over time — they're a snapshot of the codebase at filing time and the resumer can re-research if needed.

4. **Title.** Derive from `spec.md` "Goal" line, under 70 chars. Reviewer-readable, not just a slug.

5. **Create the issue.** Use a single-quoted HEREDOC (`<<'EOF'`) to preserve formatting and prevent shell expansion of `$variable`-looking strings in the spec body:
   ```
   gh issue create --title "<title>" --body "$(cat <<'EOF'
   <body>
   EOF
   )"
   ```

6. **Project conventions.** Check `CLAUDE.md` for default labels and assignees. If specified, apply them (`--label`, `--assignee`). Don't guess. (Project-board membership is handled by step 8 — don't pass `--project` here.)

7. **Append to `notes.md`** under a `## Filed` section:
   ```
   ## Filed
   - Issue: <url>
   - Date: <today>
   - Resume command: `/dev-session express <url>`
   ```

8. **Project board hook.** If a GitHub Project is configured (see `references/github-projects.md`), add the new issue to the board and set its status to the configured `ready` column. Skip silently if not configured.

9. **Report** the issue URL, the resume command, and any labels/project assignments applied.

## When to skip

- No `spec.md` or it's empty — run `brainstorm` first.
- The spec is for work you're about to do yourself in the same session — go straight to `plan`.
- The repo isn't on GitHub or `gh` isn't available — fall back to whatever the project uses (file in Linear, etc.) and skip this phase.

## After

Don't auto-chain into anything. `file` is terminal — the session ends here. The user may run `retro` separately to capture learnings, but typically the work has been queued, not finished.
