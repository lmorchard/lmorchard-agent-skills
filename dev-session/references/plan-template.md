# Plan template

Skeleton for `plan.md`. Each phase is a vertical slice with mandatory automated and manual verification checkboxes.

````markdown
# [Feature Name] Implementation Plan

**Goal:** [One sentence describing what this builds]

**Approach:** [2-3 sentences from spec.md's Design Decisions]

**Tech stack:** [Key technologies/libraries]

---

## Phase 1: [Slice name]

[1-2 sentences: what this phase delivers end-to-end]

**Files:**
- Create: `exact/path/to/file.ext`
- Modify: `exact/path/to/existing.ext` — [what changes]
- Test: `tests/exact/path/to/test.ext`

**Key changes:**
- `functionName(param: Type): ReturnType` — new
- `NewType { field: Type }` — new type

```language
// Code snippet for any non-trivial new logic
```

**Verification — automated** (see `references/makefile-conventions.md`):
- [ ] `make lint` passes
- [ ] `make test` passes
- [ ] `make check` passes
- [ ] [any phase-specific command, e.g., `go test ./internal/foo -run TestNewBehavior -v`]

**Verification — manual:**
- [ ] [What to check, expected behavior]

---

## Phase 2: [Slice name]

[...]
````

## Notes on use

- **Checkboxes are mandatory.** `execute` ticks them off as it progresses; manual items only get checked when the user confirms. They are also the resume mechanism if context resets — read the plan, find the first unchecked item, pick up there.
- **Three states, not two.** `- [ ]` pending, `- [x]` verified (with the evidence recorded inline — `— **3420 passed**`, not a bare tick), `- [!]` the assertion turned out false. Use `[!]` when the *plan* was wrong rather than the work: a check written from a stale snapshot, a number that isn't stable, a claim the codebase doesn't support. Say what actually happened and whether it's a real failure. Silently deleting the box hides the bad plan; ticking it anyway is faking success.
- **Don't write single-observation facts as checkable assertions.** "The N known failures are the only ones", "this takes under X seconds", "only these three files match" — if the number came from one run, verify it repeats *before* it becomes a checkbox, or phrase the check as "record which failures appear" instead. This is the most common source of `[!]`.
- **Code blocks for any non-trivial new code.** Don't write "implement validation logic" — show the validation. The plan should be self-contained enough that an agent reading only `plan.md` could implement the feature.
- **Repeat shared context across phases.** Phases may be read out of order or after a context reset. "Similar to phase 2" is not adequate.
- **One commit per phase** keeps phases independently revertable. Commit message format: `Phase N: <name>`.
- **Test-first by default.** Each phase should start with a failing test, unless explicitly opted out (pure refactoring, doc changes, infrastructure scaffolding without behavior).
- **Aim for proportionality.** Roughly 1 line of plan per 1-2 lines of code expected. If the plan is much longer than that, you're writing the implementation; if much shorter, you're missing detail.
