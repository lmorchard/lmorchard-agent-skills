---
name: create-verification-skill
description: "Create or repair a project-local skill for launching and exercising a real application, CLI, service, or library and capturing proof of its behavior. Use when asked to make a reusable verification or control recipe; ordinary test execution does not require generating a skill."
license: MIT
---

# Create a verification skill

Produce a project-local verification recipe that a future agent can execute from a cold start. Reuse the project's existing harnesses. Creating this skill is an optional project improvement, not a prerequisite for implementation or delivery.

## Discover the actual verification surface

Read project instructions, documented run commands, tests, routes or commands, and existing automation. Establish:

- What the user or caller actually interacts with, including multiple entry points when material.
- How to build and reach usable state, including configuration, migrations, seed data, and authentication prerequisites.
- Which available harness can drive that surface and observe its effects.
- How to isolate instances, ports, profiles, and data from the user's session and other workers.
- Which evidence proves the action happened and the intended result followed.

Inspect existing verification skills before creating another. Extend or repair the relevant one rather than duplicating it. Ask only for material choices or prerequisites that cannot be discovered. Do not change accounts, install system tools, or repair unrelated application problems merely to make the recipe work. Report such blockers and continue drafting what the evidence supports.

## Write the project skill

Use the project's established skill location. If none exists, use `.agents/skills/verify-APP/SKILL.md`, replacing `APP` with a short project-specific name. Use that same name in frontmatter and write a description that identifies the application, supported surface, and invocation conditions. Honor an explicitly requested destination.

Write real commands and selectors from this project, with no unresolved scaffold placeholders. Document runtime inputs, such as a chosen free port or temporary directory, and how the reader obtains them. Reference credential sources by name without embedding secrets. The generated skill needs these procedures:

- **Launch:** build or start the application with isolated scratch data. Establish usable readiness, including migrations and required seed state; a listening port alone may not suffice. For a short-lived CLI or library, describe the build/import setup and a fresh invocation rather than inventing a server.
- **Check the instance:** confirm the intended build, owned process or endpoint, and required access before driving it. After a surprising failure, recheck or reset to known state before retrying.
- **Drive:** exercise the real public interface with stable selectors or commands. Use existing test modes or boundary mocks where suitable, and state what they leave unverified. An internal setter or test-only endpoint is not proof that the user's path works.
- **Capture evidence:** record the action, observable result, and relevant side effects with exit statuses and failures. Name a durable evidence location outside scratch directories that cleanup removes. Avoid secrets and private payloads in logs.
- **Cleanup:** stop only processes the run started and remove only its scratch state, including residue from failed attempts. Preserve evidence. Never kill by process name or interfere with a shared instance without authorization.

Include a small set of representative feature journeys, each with prerequisites, entry point, drive steps, and observable success conditions. Keep them inline if short; use linked feature files only when that improves navigation. Name which surfaces are mapped and which remain outside coverage. An unavailable precondition is a gap, not permission to weaken the journey.

Add executable helpers only when they remove repeated or fragile work. Document their invocation and failure behavior, and verify them. Keep product code changes outside this task unless separately authorized.

## Execute the generated instructions

Follow the written launch, readiness, drive, capture, and cleanup procedures against at least one representative journey. Use only the environment and side effects authorized by the request. Check cleanup after failed attempts as well as success, and confirm the evidence survives it. Fix recipe or harness errors and rerun the affected journey.

Validate the skill with the available skill validator. Syntax checks do not establish that the application recipe works. If execution is blocked, deliver a clearly labeled draft with the exact blocker and untested steps. A stand-in environment establishes only what it actually exercised; name differences from the intended target.

Return the generated skill path, mapped coverage, journey executed, evidence location, cleanup outcome, and remaining limits. Do not claim that unexercised journeys are verified or publish changes merely because the recipe is complete.

## Source

Adapted from Lauren Tan's pstack [create-verification-skill](https://github.com/cursor/plugins/blob/d457567332aa6989e753ea289f30ea2bfbc80bc0/pstack/skills/create-verification-skill/SKILL.md) at revision `d457567332aa6989e753ea289f30ea2bfbc80bc0`. This adaptation follows project skill locations, permits compact feature maps, and bounds environment and product changes to the request. See [LICENSE](LICENSE).
