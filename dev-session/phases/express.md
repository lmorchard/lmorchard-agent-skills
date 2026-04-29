# express

Full express dev session — interactive brainstorm, then autonomous through PR with agent self-review substituting for human review at intermediate checkpoints (plan, per-phase execute). Brainstorm stays interactive because intent capture is human work; everything downstream trusts the spec.

## Inputs

- GitHub issue URL (passed as argument)
- Project context: `CLAUDE.md`, project board (if configured)

## Outputs

- All artifacts produced by the orchestrated phases: branch + worktree, session directory, `research.md`, `spec.md`, `plan.md`, code changes, commits, opened PR with Copilot review addressed
- PR URL — the primary consumable output, reported at the end
- Summary of what was fixed and what was skipped during the Copilot cycle

## Phase 0: Complexity check

Fetch the GitHub issue (URL provided as argument). Assess fit for express:

- **Good fit:** focused features, bug fixes, straightforward additions, well-defined scope (XS/S/M)
- **Bad fit:** architectural changes, many interaction effects, ambiguous requirements, large scope (L/XL), touching multiple subsystems in non-obvious ways

If too complex, **push back** — recommend the full interactive flow (`/dev-session start` then `/dev-session brainstorm`, etc.). Don't proceed just because express was requested.

## Phase 1: Setup (autonomous)

1. Fetch and read the GitHub issue thoroughly. If a project board is configured, also note priority/size from the board (the read-only check; the write-side board move happens via start.md step 8 in the next step).
2. **Run `phases/start.md` against the issue URL, autonomously.** Complete all of its steps — including marker detection (step 4), worktree setup (step 6), session directory (step 7), and the project-board hook to `in_progress` (step 8). Skip its After-section interactive prompts; we're chaining straight into Phase 2 regardless of what start would have asked.

## Phase 2: Brainstorm (interactive — usually)

Behavior depends on whether the issue already carries a spec:

- **Issue has the `<!-- dev-session:spec -->` marker** (spec was front-loaded via `/dev-session file`): `start` already copied the spec into `spec.md`. Skip the codebase research substep and the Q&A. Instead, run a brief confirmation: show the user the goal, design decisions, and "What we're NOT doing", and ask "Spec still good — proceed to autonomous execution?" If yes, continue. If they want changes, drop to `phases/brainstorm.md` — it will detect the populated `spec.md` and run in refine mode for targeted edits.
- **Issue has no marker** (raw issue, spec needs developing): run `phases/brainstorm.md` in full:
  1. Codebase research substep (documentarian subagent → `research.md`).
  2. Interactive Q&A grounded in research.
  3. Spec saved to `spec.md` (with "What we're NOT doing").
  4. Spec self-review (placeholder / consistency / scope / ambiguity).

When the spec is approved (or confirmed unchanged), **tell the user you're starting autonomous execution.** Then proceed through ALL remaining phases without stopping for input, unless hitting a genuinely unresolvable blocker.

## Phase 3: Autonomous execution

Print a brief status line at each transition. Run each phase file in sequence, with the express-mode overrides noted below:

| Step | Run | Express override |
|---|---|---|
| 3a. Plan | `phases/plan.md` | — |
| 3b. Plan self-review | self-review checklist from `phases/plan.md` step 8 | Replaces the human plan review — fix and continue |
| 3c. Execute | `phases/execute.md` | Skip per-phase manual pauses — they happen at 3d |
| 3d. Branch self-review | self-review checklist from `phases/pr.md` step 1 | Catches issues Copilot misses (and vice versa) |
| 3e. Squash and PR | `phases/pr.md` steps 3–6 | Use `references/pr-body-template.md` for the body; project-board hook runs here if configured |
| 3f. Copilot review cycle | `phases/pr.md` steps 7–12 | Always run — do not wait for user confirmation |

## When to break out of autonomous mode

Stop autonomous execution and surface the issue when:

- The plan self-review uncovers an issue that requires a design decision not covered in the spec.
- Execute hits a fundamental plan error (wrong API, missing dependency, structural mismatch).
- Branch self-review finds a bug whose fix would change the spec's intent.

Don't paper over fundamental issues with on-the-fly rewrites. Asking is cheap; rebuilding from a wrong foundation is expensive.
