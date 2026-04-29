# pr

Self-review, squash, push, open a PR, and run the Copilot review cycle.

## Inputs

- Branch state (commits ahead of origin/main, current diff)
- `spec.md` — for the PR body's "Design Decisions" section
- `plan.md` — referenced from the PR body

## Outputs

- Squashed branch pushed to remote
- Open PR with structured body, `Closes #N` references, and links to spec/plan
- Copilot review requested and worthwhile comments addressed
- Final squashed commit force-pushed (`--force-with-lease`)
- PR URL reported, with summary of what was fixed and what was skipped

## Process

1. **Branch self-review.** Review `git diff origin/main..HEAD` for:
   - **Bugs introduced:** wrong logic, missing imports, changed behavior unintentionally
   - **Incomplete changes:** renamed something in one place but missed another, removed a function but left callers
   - **Edge cases:** hidden files/dirs not filtered, path traversal, off-by-one, empty inputs
   - **Test gaps:** new behavior without tests, changed behavior that existing tests don't cover
   - **Convention violations:** bare error strings, imports inside functions, undeclared attributes
   - **Doc gaps:** new config options not documented, CLAUDE.md key files list stale

   Fix anything found before proceeding. This catches issues Copilot often misses (and vice versa).

2. **Verification before completion:** before opening the PR, run `make lint`, `make test`, and `make check` and confirm green (see SKILL.md "Verification before completion" and "Makefile-first"). Do not open a PR with red checks.

3. **Squash all commits** on the branch into one with a comprehensive message.

4. **Push the branch** to remote.

5. **Open the PR** using `references/pr-body-template.md` for the body structure. Title under 70 chars; details in the body. Include `Closes #N` references and pointers to `spec.md` and `plan.md`.

6. **Project board hook.** If a GitHub Project is configured (see `references/github-projects.md`), move each issue referenced via `Closes #N` to the configured `in_review` column. Skip silently if not configured.

7. **Request a Copilot review:**
   ```
   gh pr edit <number> --add-reviewer copilot-pull-request-reviewer
   ```

8. **Poll for new review comments.** Use:
   ```
   gh api repos/{owner}/{repo}/pulls/{number}/comments --jq 'length'
   ```
   Poll every 30s for up to 10 minutes. Stop early once the count goes above the pre-request baseline. Give up if none arrive in that window and report the timeout.

9. **Assess each Copilot comment:**
   - **Fix:** real bugs, valid edge cases, missing error handling, doc/code mismatches, missing test coverage
   - **Skip:** over-engineering, theoretical concerns without real risk, style nitpicks

10. **Fix worthwhile comments.** Lint, test, commit.

11. **Squash again and force-push** with `--force-with-lease` (refuses if remote has commits you haven't fetched, preventing silent overwrites of work pushed from another machine).

12. **Report** the PR URL, what was fixed, and what was skipped (with brief reasoning).

## When to skip

- The branch is unfinished or has failing checks. Fix first; don't open a half-baked PR.
- Work that won't go to PR at all (direct-to-main, throwaway, keep-local) — use the alternative paths below.

## Alternative paths

If the work shouldn't end in a PR — e.g., merge directly to main, keep as branch, or discard — see `superpowers:finishing-a-development-branch` for the 4-option pattern (merge / PR / keep / discard) with appropriate worktree cleanup for each.
