# Phase: Plan

Read `spec.md` from the current session directory.

Draft a detailed, step-by-step blueprint for building the feature:

1. Break the work into small, iterative chunks that build on each other
2. Review those chunks and break them down further — steps should be small enough to implement safely but large enough to move the project meaningfully forward
3. Iterate until the steps feel right-sized for the project

From these steps, write a series of implementation prompts suitable for a code-generation LLM. Each prompt should:
- Build on all previous prompts
- End with wiring things together into the larger whole
- Leave no orphaned code — everything integrates into a prior step
- Prioritize best practices and incremental progress
- Avoid big jumps in complexity between steps

Separate each prompt section clearly with markdown headers. Include brief context alongside each prompt explaining what it builds on and what state the codebase will be in after completion.

Save the finished plan to `plan.md`.
