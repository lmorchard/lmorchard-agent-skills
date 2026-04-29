# start

Start or resume a dev session.

## Inputs

- Current git branch and working tree state
- Optional GitHub issue URL (passed as additional argument)
- Project `CLAUDE.md` (for session directory override)
- Existing session directory if one matches the current branch

## Outputs

- Feature branch created, worktree set up at `.worktrees/{branch-name}/`, dependencies installed, baseline tests green
- Session directory created at `{base}/{timestamp}-{slug}/` with empty `spec.md`, `research.md`, `plan.md`, `notes.md` — OR existing session identified and current state reported

## Process

1. **Determine the session base directory.** Check the project's `CLAUDE.md` for a "Dev Sessions" section or any non-default session directory. If specified, use it. Otherwise, default to `docs/dev-sessions/`.

2. **Look for an existing session to resume.** Search the base directory for the most recent timestamped session matching the current branch (or any in-progress session). If found, read `spec.md`, `research.md`, `plan.md`, and `notes.md` for context, report the current state, and ask whether to resume the existing session or start a fresh one. If resuming, suggest the appropriate next phase and stop here.

3. **Branch.** Check the current git branch. If on main, ask for a branch name or derive it from context (e.g., from a GitHub issue URL if provided as an extra argument). Strip prefixes like `feature/`, `fix/`, `chore/` when deriving a slug.

4. **Issue context.** If a GitHub issue URL is provided, fetch it for context and use it to derive the branch name. Check the issue body for the marker `<!-- dev-session:spec -->` and remember the result:
   - **Marker present:** the issue was filed by `/dev-session file` and embeds a complete spec. Capture the body (stripping the marker line and the trailing `_Filed by_` footer) for use in step 7. The marker state changes the After-section behavior.
   - **No marker:** capture the issue title + body as an initial spec sketch for use in step 7.

   If no issue URL was provided, skip this step entirely.

5. **Fetch and rebase from origin/main.**

6. **Set up an isolated worktree** (see SKILL.md "Worktrees" for the preferred path). If `superpowers:using-git-worktrees` is unavailable, fall back to:
   a. Verify `.worktrees/` is in `.gitignore`. If not, add it and commit (fix broken things immediately rather than working around them).
   b. `git worktree add .worktrees/{branch-name} -b {branch-name}`
   c. `cd` into the worktree.
   d. Run any project setup (venv / `npm install` / `cargo build` / `go mod download`) auto-detected from project files.
   e. Run the project's test suite (`make test`, or the native equivalent per `references/makefile-conventions.md`) to verify a clean baseline. Report failures rather than proceeding silently — ask the user whether to continue or investigate.

7. **Create the session directory** inside the worktree at `{base}/{timestamp}-{slug}/` with `research.md`, `plan.md`, and `notes.md` empty. For `spec.md`:
   - **Marker captured in step 4:** write the captured spec body to `spec.md`. Brainstorm is effectively done — refine mode applies if it runs.
   - **Sketch captured in step 4:** write the sketch to `spec.md` as a starting point for brainstorm.
   - **No issue URL:** leave `spec.md` empty.

   (Create inside the worktree, not the main checkout — untracked files don't transfer between worktrees.)

8. **Project board hook.** If working from an issue URL and a GitHub Project is configured (see `references/github-projects.md`), move the issue to the configured `in_progress` column. Skip silently if no issue URL or no project configured.

9. **Report** the session directory path and worktree path. This is the active dev session until another is started or this one is finished.

## After

Report the session directory path and the worktree path. Next step depends on how the session started:

- **Issue URL with `<!-- dev-session:spec -->` marker** (spec already exists): report that the spec was loaded from the issue, and ask whether to (a) jump into `plan`, (b) run `express` for autonomous execution, or (c) refine the spec via `brainstorm` first.
- **Issue URL without the marker** (intent is clear, spec needs work): load `phases/brainstorm.md` and proceed directly into the brainstorm flow, using the issue as the task source.
- **No issue URL** (intent is ambiguous): ask "Ready to brainstorm, or hold here?" If yes, load `phases/brainstorm.md` and proceed. If no, stop and let the user direct.

Don't auto-chain past brainstorm or past a spec-loaded issue. `plan`, `execute`, and `pr` each act on prior artifacts without re-confirming intent — those transitions stay explicit. (`express` exists for the full chain.)
