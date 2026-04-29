# Spec template

Skeleton for `spec.md`. Goal is enough detail that `plan` can produce a vertical-slice implementation plan without re-asking design questions.

````markdown
# [Feature Name] Spec

**Goal:** [One sentence. What does this enable, and for whom?]

**Source:** [Issue URL, ticket, or "user request from {date}"]

## Current state

[How does the relevant area work today? Reference `research.md` with `file:line`
pointers — don't duplicate research findings, summarize the load-bearing facts.]

## Desired end state

[What does "done" look like? User-visible behavior, API surface, data shape.
Concrete enough that the plan author knows what to build.]

## Design decisions

[Each decision: what was chosen, what was rejected, and why. Reasoning matters
more than conclusion — future readers need to know if a constraint changes.]

- **Decision:** [chosen approach]
  - **Why:** [the constraint or trade-off that drove it]
  - **Rejected:** [alternative considered and why not]

## Patterns to follow

[Existing patterns from `research.md` to mirror, with `file:line` refs.
"Follow the pattern at `internal/foo/bar.go:42-58`" beats "use the standard
pattern."]

## What we're NOT doing

[Explicit non-goals to lock scope. Anything tempting that this spec rules out:
adjacent refactors, related features, optimizations, error-handling polish that
isn't load-bearing. List by name so `plan` and `execute` can refuse them.]

## Open questions

[Anything the brainstorm couldn't resolve. Each entry must either pair with a
default answer (so plan/execute can proceed under that assumption) OR escalate
explicitly as "blocks planning — needs decision before proceeding". Don't leave
bare questions; they fail the readiness checklist.]
````

## Readiness checklist

Run this checklist whenever a downstream phase depends on the spec being complete (`brainstorm` self-review, `plan` step 1, `file` pre-check). The spec is ready iff:

1. **Placeholder scan:** no "TBD" / "TODO" / vague requirements anywhere. The "Open questions" section is allowed iff every entry has a default answer paired with it; un-answered questions are placeholders.
2. **Internal consistency:** sections don't contradict each other. The architecture matches the feature description; the "Patterns to follow" align with the design decisions.
3. **Scope bounded:** "What we're NOT doing" is present and concrete. The spec is focused enough for a single implementation plan, not two specs in a trench coat.
4. **No load-bearing ambiguity:** any requirement that could be read two ways has been pinned to one reading.

If any criterion fails, the appropriate response is: re-open `brainstorm` (for `plan` and `file`) or fix inline (within `brainstorm` itself).

## Notes on use

- **"What we're NOT doing" is mandatory.** Without it, `plan` and `execute` quietly absorb adjacent improvements and the session bloats.
- **Cite `research.md` with `file:line` refs.** "Patterns to follow" without paths leaves the plan author guessing.
- **Decisions need reasoning, not just conclusions.** The "why" is what survives when constraints change.
- **Keep it scannable.** If the spec is longer than ~150 lines, it probably needs decomposition into sub-project specs.

## Filing as a GitHub issue

`/dev-session file` lifts this spec into a GitHub issue body and prepends the marker `<!-- dev-session:spec -->`. The marker is how `start` and `express` later recognize that the issue carries a complete spec (not just a raw bug report) and skip brainstorm. Don't strip the marker if you edit the issue manually — it's the resume-detection signal.

A few sections drop or transform during filing:
- **Source** is dropped (the issue *is* the source).
- **Open questions** is kept only if questions remain with their default answers; fully resolved questions get dropped.
- **`file:line` refs** are kept verbatim, even though they may drift over time. They reflect the codebase at filing time; the resumer can re-research if a reference no longer exists.

After loading via `start`, the in-session `spec.md` won't have a Source line — that's expected, not a bug.
