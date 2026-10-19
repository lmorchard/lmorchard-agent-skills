---
name: why
description: "Investigate why existing code or a design decision took its current shape, using commits, PRs, issues, and other relevant records. Use for design rationale, unusual constraints, and historical tradeoffs; use how for present execution flow."
license: MIT
---

# Why

Reconstruct the reasons behind the requested code or decision. Keep recorded intent separate from present behavior and your interpretation. An explanation task does not authorize changing the implementation or publishing findings.

## Anchor the question

Identify the target, checkout, and question. State a reasonable interpretation of a vague target and proceed when the surrounding conversation supplies enough context.

Read the current code and relevant tests to locate the behavior, symbols, and boundaries. Record the revision inspected. Current code establishes what exists; it does not establish the author's original intent.

## Follow the evidence

Start with the closest records: comments, blame for the relevant lines, file history through renames, and the commits that introduced or changed the behavior. Read patches and full commit messages rather than relying on titles. Resolve substantive commits to PR descriptions, reviews, linked issues, and design documents when available. A last-touch commit can be formatting; trace back to the behavioral change.

Use existing Git and GitHub tools. Other connected sources, such as team chat or incident records, are useful when the question or nearby evidence points to them. Search only the requested project and relevant time range; do not mine unrelated private conversations. Record unavailable sources when they materially limit the answer. Missing access is not evidence that no rationale exists.

Follow concrete leads until the rationale is established or the relevant searches stop producing new evidence. A narrow question may need one PR. A broad investigation may benefit from authorized delegation by evidence source; neither parallelism nor a particular model is required.

Treat a hypothesis supplied by the user as one candidate to investigate. Preserve contradictory evidence, including reversions and later changes that invalidate earlier reasoning. Distinguish why a decision was made then from whether its constraints still apply now. Do not infer that a proposed fix succeeded from its description alone.

## Return the answer with its limits

Lead with the best-supported answer and cite the sources adjacent to the claims they support. Distinguish:

- **Recorded rationale:** a source explicitly states the reason. Attribute it to the author and time rather than treating every historical statement as current truth.
- **Supported inference:** several observations support an interpretation; state the reasoning and plausible alternatives.
- **Unknown:** the searched records do not establish the reason. Name the relevant searches and remaining gaps instead of filling them with a tidy story.

Summarize the important tradeoffs and rejected alternatives when documented. Link detailed evidence instead of reproducing whole discussions. If a present-day change is worth considering, label it as a recommendation separate from the historical finding; do not implement it as part of the investigation.

## Source

Adapted from Lauren Tan's pstack [why skill](https://github.com/cursor/plugins/blob/d457567332aa6989e753ea289f30ea2bfbc80bc0/pstack/skills/why/SKILL.md) and its confidence guidance at revision `d457567332aa6989e753ea289f30ea2bfbc80bc0`. This adaptation starts with nearby evidence and expands by relevance, without mandatory multi-model investigation or Cursor-specific configuration. See [LICENSE](LICENSE).
