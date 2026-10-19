---
name: correct
description: "Prevent recurring agent mistakes in a repository by replacing repeated reminders with structural constraints, checks, or behavioral tests. Use when asked to stop a mistake recurring or improve how a repo guides agents; an ordinary bug fix alone does not call for this maintenance task."
license: MIT
---

# Correct

Change the repository so an evidenced, recurring mistake becomes harder to make or easier to detect. Focus on the correction the user named. A broad search for other mistake classes belongs only in a requested repository-wide pass.

## Establish the pattern

Read project instructions and the relevant code. Use supplied corrections, commits, reverts, review comments, or session records to identify what went wrong and why the existing feedback missed it. Keep the search within the selected project and supplied records.

Call a mistake recurring when there are at least two evidenced instances, including the current one, or the user identifies it as recurring. A single incident can justify a targeted fix, but does not establish a general pattern by itself. Distinguish a violated invariant from a changed requirement or a preference that still needs judgment.

Name the behavior to preserve and the mistake to prevent before choosing a mechanism. Preserve unrelated work and the intended result. For an assessment-only request, return the proposed correction and evidence without editing.

## Choose the smallest effective correction

Consider these options in order, choosing the least costly mechanism that actually addresses the cause:

1. **Structure.** Remove the wrong path, give state one owner, derive duplicated information from one source, or narrow an interface so callers cannot misuse it. Avoid a broad redesign when a local correction suffices.
2. **Types or boundary validation.** Express the invariant where values enter or are constructed. Check dynamic inputs at their boundary; do not scatter duplicate guards through consumers.
3. **Lint or a deterministic check.** Detect the mistake and report an actionable fix. Prefer an existing tool or project gate. When existing violations cannot be removed within scope, prevent new ones without hiding the old ones.
4. **Behavioral tests.** Exercise the actual interface and assert the observable result. The test should detect the mistake while allowing internal refactoring.
5. **Instructions.** Use prose for decisions that require judgment or cannot reasonably be enforced. Put it in the existing owning instruction or reference, with a concrete trigger and example. Avoid adding another copy of the rule.

Explain why a stronger structural option would not be appropriate when choosing a weaker one. A new framework or mandatory rule table is not a prerequisite.

## Prove the correction

For an automated check, show that it detects a representative known mistake and accepts the corrected behavior. Prefer a real past example when available; reproduce it in a temporary copy or fixture without disturbing the user's checkout. If only a synthetic case is available, label it and explain what it represents.

Run the relevant project checks. If a new check is intended as a standing guard, connect it to the existing local and CI gates within the authorized scope. A command that nobody runs does not enforce the rule. If CI wiring is outside scope, report that limit instead of claiming enforcement.

Keep useful existing tests and explain changed assertions. Remove an obsolete reminder only after inspecting its other purposes and confirming the replacement covers them. Instructions that still guide judgment can remain.

Return the mistake class and evidence, the mechanism chosen, the proof and checks actually run, and any remaining gaps. Make commits, publish changes, or widen the task only when the enclosing request authorizes those actions. When working within ghflow, preserve that operation's scope and handoff boundary.

## Source

Adapted from Lauren Tan's pstack [correct skill](https://github.com/cursor/plugins/blob/d457567332aa6989e753ea289f30ea2bfbc80bc0/pstack/skills/correct/SKILL.md) at revision `d457567332aa6989e753ea289f30ea2bfbc80bc0`. This adaptation bounds the investigation and edits to the request and replaces automatic commits and rule tables with existing project conventions. See [LICENSE](LICENSE).
