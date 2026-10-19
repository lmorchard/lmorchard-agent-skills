---
name: blast-radius
description: "Assess what a proposed code change could break beyond its diff. Use for change-impact investigations and questions such as what could this break; trace indirect consumers and verify the assumptions that make the change safe. Returns findings without implementing repairs."
license: MIT
---

# Blast radius

Find the effects of a proposed change outside the edited lines. Focus on concrete paths and the assumptions that determine safety, rather than producing a list of imaginable problems. This assessment does not authorize repairs, publication, or merge.

## Establish the change

Identify the proposed behavior, exact base and head when there is a diff, and relevant uncommitted changes. Use the project's actual base rather than assuming a branch name. Preserve the implementation checkout.

Explain what changes observably, including removals, defaults, side effects, and behavior implied by configuration or generated artifacts. If the change has not been implemented, assess the supplied proposal and label which conclusions depend on its eventual implementation.

## Trace beyond symbol references

Find callers and follow the paths that can carry the change elsewhere. Consider the boundaries the code actually crosses: persisted data, wire formats, dynamically registered handlers, generated clients, feature flags, dependency versions or patches, and lifecycle ordering. Inspect success, empty, error, and retry behavior where the change affects them. Do not invent consumers or demand a universal checklist unrelated to the change.

State the key assumptions that make the change safe. For example, a cache eviction may be harmless only if entries have no cleanup side effects. Test that assumption rather than treating a function name or comment as proof. There may be several independent assumptions; do not force every change into a single explanation.

## Verify the decisive assumptions

Read the actual implementation, including the pinned dependency when relevant. Use a focused test or reproduction that runs the real path and observes the result. Confirm that the check can detect the suspected failure rather than only exercising a neighboring path. For timing or lifecycle questions, exercise the relevant ordering.

Keep scratch checks in an isolated temporary copy or test instance when they mutate state. Respect a read-only request: source inspection can proceed, while execution requiring prohibited writes remains an explicit evidence gap. Do not exercise production side effects or change the reviewed implementation to obtain a favorable result.

Distinguish source-backed reasoning, an executed test, and a reproduction in the running app. None establishes safety for paths it did not cover. If a decisive assumption cannot be checked, mark it unproven and name the cheapest useful next check.

## Return the assessment

Lead with the observable change and the most consequential finding. Include:

- The decisive safety assumptions, supporting sources, and checks actually run.
- Concrete risks, each with a triggering condition, affected consumer, failure mechanism, and practical impact. Use qualitative likelihood only when evidence supports it; do not invent probabilities.
- Suspected risks that were checked and cleared, with the reason.
- Coverage limits and remaining checks before the change can be relied on.

Keep demonstrated defects separate from hypotheses and missing evidence. A favorable result means no problem found within the assessed paths, not a blanket guarantee.

## Source

Adapted from Lauren Tan's pstack [blast-radius skill](https://github.com/cursor/plugins/blob/d457567332aa6989e753ea289f30ea2bfbc80bc0/pstack/skills/blast-radius/SKILL.md) at revision `d457567332aa6989e753ea289f30ea2bfbc80bc0`. This adaptation is self-contained, permits multiple safety assumptions, and preserves assessment and execution boundaries without mandatory multi-model review. See [LICENSE](LICENSE).
