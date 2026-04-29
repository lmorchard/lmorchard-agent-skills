# brainstorm

Brainstorm a spec for the current dev session. Reads from `spec.md` (already populated by `start` if an issue URL was given) and produces a finalized spec ready for `plan` or `file`.

## Inputs

- `spec.md` — preexisting content from `start` (sketch from raw issue, full spec from marker-tagged issue, or empty for free-form sessions)
- The task source as context (issue body, user prompt) — usually already captured in `spec.md`

## Outputs

- `spec.md` — the finalized spec
- `research.md` — codebase findings from the documentarian substep (blank-slate mode only; refine mode skips research)

## Process

1. **Read `spec.md`.** Two modes depending on what you find:
   - **`spec.md` is empty or has only sketch-level content** → blank-slate brainstorm. Continue to step 2.
   - **`spec.md` is already populated** (typically from `start` loading a marker-tagged issue, or a prior session): switch to **refine mode**. Skip the codebase research substep and the open-ended Q&A. Read the existing spec, then ask the user "What specifically about this spec needs to change?" Make the requested edits, run the self-review (step 6), and stop. Don't redo research or ask the original brainstorm questions — the spec was deliberately filed in this state.

   Read the task source thoroughly in either mode.

2. **Codebase research substep** (blank-slate only). Dispatch a documentarian-mode subagent (typically `Explore` or `general-purpose`) to answer 3-5 neutral questions about how the relevant areas of the codebase currently work. Frame the questions in terms of existing components and flows, not the desired feature — the subagent should describe what exists, not propose how to change it.
   - Use the negation rules in `references/documentarian-prompt.md` when dispatching.
   - Save findings to `research.md` (~300 lines max, prefer `file:line` references over prose).
   - Skip this step only if the change is so localized that codebase context is obvious (one-line tweaks, doc fixes).

3. **Interactive Q&A** (blank-slate only). Ask one question at a time to develop the spec, grounded in `research.md`. Each question should build on previous answers. Propose your best judgment with the trade-offs from research, and ask to confirm or adjust — don't ask open-ended questions when you have a clear recommendation. Multiple choice preferred when feasible.

4. **Keep proportional to complexity.** For small, well-defined issues, 2-4 questions covering key design decisions is enough. For larger or ambiguous issues, go deeper. If the design is obvious after a couple of questions, say so and offer to move to the spec.

5. **Save the spec to `spec.md`.** Use the structure in `references/spec-template.md`. At minimum: goal, current state, desired end state, design decisions (with reasoning), patterns to follow (with `file:line` refs from research), and an explicit "What we're NOT doing" section to lock scope.

6. **Spec self-review** (run in both modes after edits). Apply the **Readiness checklist** in `references/spec-template.md`. Fix any failures inline, then ask the user to review the written spec before moving to `plan`.

## When to go back

- **Blank-slate mode:** if research uncovers a constraint that invalidates the framing of the task, surface it and re-anchor the brainstorm before writing the spec.
- **Either mode:** if the spec, on self-review, reveals it's actually two specs that need to be split, say so and offer to decompose into sub-project specs — each gets its own session.
