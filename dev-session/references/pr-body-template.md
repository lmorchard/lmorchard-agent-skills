# PR body template

```markdown
## Summary
- [What this PR does, drawn from spec.md]
- [Why, drawn from spec.md]

## Design Decisions
[Key decisions from spec.md that reviewers should understand. Sourced from the
"Design Decisions" or "Patterns to follow" section of spec.md, or paraphrased
from the brainstorm. Reviewer shouldn't have to read the spec to get the gist.]

## Changes
[Brief description of what changed, organized by component if multi-component.]

## Test Plan
- [ ] [Automated verification command — e.g., `make test`]
- [ ] [Manual verification step — e.g., "run `tabstack research foo` and confirm SSE stream"]

## References
- Spec: `docs/dev-sessions/{session-dir}/spec.md`
- Plan: `docs/dev-sessions/{session-dir}/plan.md`
- Closes #N
```

## Notes on use

- **Title under 70 chars.** Use the body for details.
- **Summary explains WHY, not just WHAT.** The diff shows what changed; the PR description should explain reasoning. If you find yourself summarizing the diff, ask "why was this needed?" and write that instead.
- **Reference the spec and plan docs** so reviewers can find the full context without having to be present at the brainstorm.
- **`Closes #N`** auto-closes the linked issue when the PR merges. Use one per related issue.
