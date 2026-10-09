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

1. **Rebase onto `origin/main` before anything else.** `git fetch origin && git rebase origin/main`. Long sessions are common; main advances. Self-review and squash both depend on a meaningful diff vs. `origin/main` — pre-rebase, `git diff origin/main..HEAD` may show dozens of unrelated files from commits you haven't picked up yet, drowning out your actual changes. Re-run the full verification (`make test`, `make check`) after the rebase even if you ran it minutes ago — origin/main may have introduced fixture or behavior changes that affect your code. If conflicts surface, resolve them now, not after the PR is open.

2. **Branch self-review.** Review `git diff origin/main..HEAD` for:
   - **Bugs introduced:** wrong logic, missing imports, changed behavior unintentionally
   - **Incomplete changes:** renamed something in one place but missed another, removed a function but left callers
   - **Edge cases:** hidden files/dirs not filtered, path traversal, off-by-one, empty inputs
   - **Test gaps:** new behavior without tests, changed behavior that existing tests don't cover
   - **Convention violations:** bare error strings, imports inside functions, undeclared attributes
   - **Doc gaps:** new config options not documented, CLAUDE.md key files list stale
   - **Premise corrections:** if self-review, or later a review comment, overturns a premise from `spec.md` or `research.md`, grep all the session docs (`spec.md`, `research.md`, `plan.md`, `notes.md`) for every restatement of it. Correct each one and mark it as revised. Fixing only the spec leaves stale copies for reviewers to find.

   Then an **adversarial pass, by a fresh subagent, by default.** A correctness read by the author misses what an outside reviewer finds. The author wrote the tests around their own assumptions, so their pass inherits the same blind spots. Dispatch a `general-purpose` subagent that has none of the session's context:
   - **Isolate it.** Tell it to `cd` to the worktree as its literal first action and to confirm with `git rev-parse --show-toplevel`. It must be read-only: no edits, commits, pushes, or anything that reaches a network, cloud or cluster. Running local unit tests is fine.
   - **Point it at the source of truth:** `spec.md` first, then `git diff origin/main..HEAD`. Name the components and the flow in a paragraph so it doesn't have to rediscover the architecture.
   - **Ask for real defects only**, each with `file:line`, a concrete failure scenario, severity and confidence. Tell it to say plainly if it finds nothing serious. Have it hunt for:
     - **Breaks of each spec invariant.** For every "only", "never", bound, or permission rule in `spec.md`, try to violate it in the diff. Look for preexisting state, unnormalised input, unbounded rate, a near-miss mapping ("clicked" taken as any mouse event), and an item already in flight when a setting flips.
     - **Negative tests that don't prove their trigger ran.** A "does not happen" test needs evidence the triggering action ran: a sentinel, a counter, a positive control. Waiting for quiet is not evidence.
     - **Tests that can't fail.** For each new test, name the broken implementation it would miss. Watch for test doubles friendlier than the real thing: an in-process channel that drops where a socket would block, or an injected object where production *aliases* a shared one, such as `env` being `process.env`.
     - **Widened failure windows.** A new remote step inserted between existing ones changes what each later failure leaves behind.
   - **Run it in the background** while you do step 3's verification, and don't duplicate its files.

   **Verify every finding first-hand before acting on it.** Read the code it cites. Reviewer output is usually right, which is exactly why a wrong claim slips through. Fix the real ones test-first (the test must fail before the fix). Mark wrong claims as such with the evidence. Record each finding and its outcome (fixed, tested, documented limitation, or not a defect) in `notes.md`. A finding you choose not to fix also goes in the PR body's known limitations.

   Skip the subagent only for docs-only or trivially mechanical diffs, and say so. Then do the same three checks inline yourself. This catches issues Copilot often misses (and vice versa).

3. **Verification before completion:** before opening the PR, run `make lint`, `make test`, and `make check` and confirm green (see SKILL.md "Verification before completion" and "Makefile-first"). Do not open a PR with red checks.

4. **Re-check `origin/main` immediately before squashing.** `git fetch origin && git log --oneline main..origin/main`. Even if step 1 ran a few minutes ago, main may have advanced again — and a soft-reset-then-commit squash performed against a stale `origin/main` will silently include deletions of files that landed in between (e.g., a sibling PR merged). If new commits appear, redo the rebase + verification before squashing.

   **Then read the full diffstat and account for every file.** `git diff origin/main..HEAD --stat` — not the tail, the whole list. A file you don't recognise is the finding, and large deletion counts on a feature branch are the tell: insertions are usually yours, deletions usually aren't. Generated and vendored artifacts (lockfiles, bundles, `*.generated.*`) are the usual culprits, because build and check steps rewrite them as a side effect and a broad `git add -A <dir>` sweeps them in. Note `git add <dir>` stages tracked modifications regardless of `-A`, so the narrower habit doesn't save you — prefer staging named paths. Restore anything unintended with `git checkout origin/main -- <path>` and amend before pushing.

5. **Squash all commits** on the branch into one with a comprehensive message.

6. **Push the branch** to remote.

7. **Open the PR** using `references/pr-body-template.md` for the body structure. Title under 70 chars; details in the body. Include `Closes #N` references and pointers to `spec.md` and `plan.md`.

8. **Project board hook.** If a GitHub Project is configured (see `references/github-projects.md`), move each issue referenced via `Closes #N` to the configured `in_review` column. Skip silently if not configured.

9. **Request a Copilot review:**
   ```
   gh pr edit <number> --add-reviewer copilot-pull-request-reviewer
   ```
   The `copilot-pull-request-reviewer` slug is the current GitHub-published bot identity — if it's renamed or your install uses a different one, this command will silently no-op. Confirm with `gh api repos/{owner}/{repo}/assignees | jq '.[] | select(.type=="Bot")'` if you're unsure.

10. **Poll for new review comments.** Use:
    ```
    gh api repos/{owner}/{repo}/pulls/{number}/comments --jq 'length'
    ```
    Poll every 30s for up to 10 minutes. Stop early once the count goes above the pre-request baseline. Give up if none arrive in that window and report the timeout.

11. **Assess each Copilot comment:**
    - **Fix:** real bugs, valid edge cases, missing error handling, doc/code mismatches, missing test coverage
    - **Skip:** over-engineering, theoretical concerns without real risk, style nitpicks
    - **Defer:** real correctness issues that are pre-existing and outside this PR's spec scope. File as a follow-up issue, link from a PR comment, and explicitly note the deferral in the PR description's "References" section so reviewers and future-you see the trail. Don't silently skip a real-but-out-of-scope issue.

12. **Fix worthwhile comments.** Lint, test, commit.

13. **Squash again and force-push** with `--force-with-lease` (refuses if remote has commits you haven't fetched, preventing silent overwrites of work pushed from another machine). Before squashing, re-run step 4's origin/main check — main may have advanced during the Copilot poll-and-fix cycle too. Record the current squash commit's SHA *before* `git reset --soft origin/main`, then reuse its message with `git commit -C <sha>`. A reflog shorthand like `ORIG_HEAD@{0}` can fail after the reset and leave you on `origin/main` with everything staged.

14. **Report** the PR URL, what was fixed, and what was skipped (with brief reasoning).

## When to skip

- Work that won't end in a PR at all (direct-to-main, throwaway, keep-local). Use the alternative paths below.

(Unfinished branches or failing checks are preconditions, not skip conditions: fix them first, then run `pr`.)

## Alternative paths

If the work shouldn't end in a PR — e.g., merge directly to main, keep as branch, or discard — see `superpowers:finishing-a-development-branch` for the 4-option pattern (merge / PR / keep / discard) with appropriate worktree cleanup for each.
