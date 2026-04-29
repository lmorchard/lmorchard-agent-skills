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

[Anything the brainstorm couldn't resolve. Each one needs a default answer the
plan can proceed with, or a flag that this blocks planning.]
````

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
