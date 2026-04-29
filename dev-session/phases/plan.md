# plan

Write an implementation plan from the spec.

## Inputs

- `spec.md`
- `research.md` (if it exists)
- The relevant source files

## Outputs

- `plan.md` — vertical-slice phases with mandatory automated and manual verification checkboxes

## Process

1. Read `spec.md` and `research.md`. Confirm the spec is ready for implementation against the brainstorm self-review criteria:
   - **No placeholders:** no "TBD" / "TODO" / vague requirements; "Open questions" only appear with default answers
   - **Internally consistent:** sections don't contradict each other
   - **Scope is bounded:** "What we're NOT doing" is present and concrete
   - **No load-bearing ambiguity:** any requirement that could be read two ways has been pinned

   If any criterion fails, stop and re-open `brainstorm` rather than guessing.

2. Read the relevant source files to understand the current codebase. Use the patterns and `file:line` refs from `research.md` as the starting point — extend the read only where the plan needs more detail.

3. **Vertical slices.** Break the spec into phases where each phase is a vertical slice — crossing all relevant layers (data, logic, interface, tests) for one piece of end-to-end functionality. NOT a horizontal layer of "all migrations, then all handlers, then all tests." Earlier slices should establish foundations that later slices build on. If slice N fails, slices 1 through N-1 should still be independently valuable.

4. **TDD by default** (see SKILL.md "Test-driven by default"). Each slice starts with a failing test for the behavior. Document opt-outs explicitly — pure refactoring, doc-only changes, infrastructure scaffolding without behavior.

5. **Write `plan.md`.** Use the structure in `references/plan-template.md`. One section per phase. Each phase MUST include:
   - **Files** — paths and what changes in each
   - **Key changes** — type signatures, new functions, or non-trivial code snippets
   - **Verification — automated** — `- [ ]` checkboxes for `make lint` / `make test` / `make check` / phase-specific commands (see `references/makefile-conventions.md`)
   - **Verification — manual** — `- [ ]` checkboxes for what the human should eyeball

   Checkboxes are mandatory. `execute` ticks them off as it progresses, and they are the resume mechanism if context resets mid-session.

6. **Scope discipline.** Only include changes described in `spec.md`. No drive-by refactoring, no "while we're here" cleanup, no improvements to adjacent code — even if it's obviously messy. Note worth-fixing items separately for a future session.

7. **No placeholders.** The following are plan failures — never write them:
   - "TBD", "TODO", "implement later", "fill in details"
   - "Add appropriate error handling" / "add validation" / "handle edge cases" without showing how
   - "Write tests for the above" without actual test code
   - "Similar to phase N" — repeat the relevant detail; phases may be read out of order
   - References to types, functions, or methods not defined in any phase

8. **Plan self-review:**
   - **Spec coverage:** skim each requirement in `spec.md`. Can you point to a phase that implements it? List gaps and fill them.
   - **Placeholder scan:** check the plan for the red flags in step 7.
   - **Type consistency:** do the types, signatures, and property names in later phases match what earlier phases defined? A function called `clearLayers()` in phase 3 but `clearFullLayers()` in phase 7 is a bug.

   Fix issues inline. Present findings before asking for human review — in interactive mode, wait for approval; in `express` mode, fix and continue.

## When to skip

- Trivial changes already covered fully by `spec.md` with one obvious implementation path. If `plan.md` would just restate the spec, skip to `execute`.
- Pure refactors where the diff IS the plan.

## When to go back

If writing the plan reveals the spec is missing a load-bearing decision, stop and re-open `brainstorm` rather than guessing. If a phase can't actually be implemented as a vertical slice (genuinely depends on infrastructure that doesn't exist yet), surface it before writing more.
