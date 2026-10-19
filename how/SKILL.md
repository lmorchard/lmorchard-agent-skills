---
name: how
description: "Explain how a codebase or subsystem works, including execution flow, data, ownership, and boundaries. Use for code walkthroughs, onboarding, and questions about where behavior lives. Produces an explanation without changing the implementation."
license: MIT
---

# How

Build a working mental model of the requested code, grounded in the current source. Match the depth to why the user is asking: learning, reviewing, debugging, or preparing a change. This is an explanation task; it does not start an implementation or delivery workflow.

## Trace the behavior

Identify the question and relevant checkout. If the target is ambiguous, state a reasonable interpretation and investigate it; ask only when different interpretations would materially change the work.

Start at a real entry point and trace the path that answers the question. Follow the data as well as the calls: where it originates, how it changes, who owns it, where it persists, and what leaves the subsystem. Inspect relevant callers, tests, configuration, generated code, and dependency versions when they affect the explanation. A test's name alone does not establish its behavior.

For ownership questions, distinguish where code currently lives from where it might belong. Explain the existing boundary before proposing a different one. For historical motivation, consult relevant commits or discussions when available; label an inferred reason as an inference.

Handle a narrow question directly. For a large subsystem, split the investigation into distinct questions when that improves coverage. Use available subagents only when authorized and useful; give each a bounded question and require source locations, traced flow, and unresolved gaps. Reconcile conflicting findings against the source before presenting them. The skill works without delegation or a particular model.

## Explain the model

Lead with what the subsystem does and the few concepts needed to understand it. Then walk through a concrete path from input to observable result. Include error paths or lifecycle details when they change that model.

Link the files and symbols that support material claims. Add a short file map or a diagram when it makes the relationships clearer. Include surprising constraints and unanswered questions. Keep a small answer small; use sections only when the explanation needs them.

Separate what the source establishes from behavior observed by running commands. Run a focused check when a material claim depends on runtime or library behavior that source inspection does not settle. Keep checks within the request's permissions and isolate any scratch state. Report an unverified claim as a gap.

Return enough understanding for the user to navigate the code and make their next decision. Do not turn a walkthrough into an unsolicited audit or redesign.

## Source

Adapted from Lauren Tan's pstack [how skill](https://github.com/cursor/plugins/blob/d457567332aa6989e753ea289f30ea2bfbc80bc0/pstack/skills/how/SKILL.md) and its explorer/explainer prompts at revision `d457567332aa6989e753ea289f30ea2bfbc80bc0`. This adaptation removes Cursor-specific orchestration and handles narrow questions directly. See [LICENSE](LICENSE).
