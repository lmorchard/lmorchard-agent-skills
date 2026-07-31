# Digest fuller capture — Spec

**Goal:** Make the standup digest reflect the *whole* of a day's work — commits made in
directories the session `cd`'d into (not just its launch cwd), work in local repos with
no GitHub remote, and a descriptive sense of what was discussed/debated/decided — without
loosening the tool's anti-overclaim discipline.

**Source:** Les, user request 2026-07-30 (motivating case: the `zoo-service` build on
2026-07-29 was nearly invisible — commits uncounted and the design conversation flattened
to one line).

## Current state

See `research.md`. Load-bearing facts:

- Commits are collected only from `session["cwds"]`, which is the transcript's structured
  `cwd` field = the session **launch** dir (`standup-digest/scripts/standup_digest.py:574-583`,
  `:513`). Work reached via `cd`/`git -C` inside a Bash command is invisible.
- `GhVerifier.commits` warns `"not a git repository, commits skipped"` for any scanned
  non-repo dir (`:372`) and attributes `repo` via `repo_from_cwd`, which is `None` with no
  origin remote (`:402`, `:434-440`). Commits already carry `path` (`:409-417`).
- Only human prompt text is captured (`extract_prompts` `:185-210`); assistant text is
  never captured. The renderer is forbidden from re-reading transcripts (`SKILL.md:28`).
- `SCHEMA_VERSION = 1` (`:536`); schema-conformance test at
  `scripts/test_standup_digest.py:859` / documented key list `:844`.

## Desired end state

1. **Relocated output (DONE, carried on this branch):** the detail file is written to
   `~/Documents/Obsidian/main/standup-digests/YYYY-MM-DD.md`, not `~/.claude/standup/`.
2. **Harvested dirs:** the extractor scans additional directories discovered from Bash
   tool-use inputs in each transcript (absolute `cd <path>` and `git -C <path>` targets)
   for in-window commits, merged into `commits[]` with the same email/window filters and
   sha dedup. A harvested dir that is not a git repo does **not** emit a warning (a plain
   `cd /tmp` is not degradation).
3. **Repo-less projects count:** commits in a git repo with no origin remote are included
   with `repo: null` and a usable `path`. The renderer groups such commits under a
   directory-basename heading (e.g. `zoo-service (local, no remote)`).
4. **Assistant-side narrative signal:** the extractor captures a bounded, truncated
   digest of assistant prose per session (the final `text` block of each assistant turn,
   with a per-session character budget — NOT a transcript dump), so the renderer can
   describe what was discussed/debated/decided.
5. **Renderer changes (`SKILL.md`):**
   - Detail file opens with a **tl;dr overview** (the same significance-ranked bullets
     shown in the terminal), then per-project/per-session detail.
   - Each session gains a short **descriptive narrative** ("what you worked through")
     synthesized from prompts + the assistant-prose signal, kept in a descriptive
     register and visually separate from the commit/ref-backed "what shipped".
   - Terminal output carries more conversational texture (the day's themes) alongside the
     confirmed accomplishments, and the same bullets are what lead the detail file.
   - A new **register-firewall language rule**: conversation-sourced text (prompts and
     assistant prose) is topic/discussion signal only and licenses descriptive language;
     outcome language ("shipped/landed/fixed/closed") still requires a commit or a
     `confirmed` ref. Assistant prose may contain aspirational completion claims and must
     never, on its own, license an accomplishment.
6. **Schema bump to v2:** new session field(s) documented in `SKILL.md`'s contract and in
   the conformance test; `SCHEMA_VERSION = 2`.

## Design decisions

- **Decision:** Discover extra dirs from the transcript's Bash inputs (absolute paths
  only), config-free.
  - **Why:** Les requires the skill stay configuration-free and discover work dynamically
    from transcripts. Absolute `cd`/`git -C` targets are the real-world dominant form (98×
    absolute vs 1× relative for `zoo-service`).
  - **Rejected:** sweeping configured roots (needs a config knob); resolving relative
    `cd`s (requires simulating shell cwd state across `&&`/`;` chains — fiddly and
    error-prone, and redundant here since the same dir also appears absolute).

- **Decision:** The commit scan is the noise filter; harvested non-repo dirs are silently
  skipped.
  - **Why:** a harvested dir yields commits only if it is a git repo *and* has in-window
    commits by *that repo's own* `user.email`. Non-repos / others' repos / out-of-window
    naturally produce nothing. Suppressing the non-repo warning for harvested (vs. real
    cwd) dirs keeps a stray `cd` from marking the run degraded.
  - **Rejected:** pre-filtering candidate paths with extra `git` calls (redundant with
    the rev-parse the scan already does).

- **Decision:** Capture assistant narrative as the final `text` block per assistant turn,
  truncated, under a per-session character budget.
  - **Why:** the closing prose of a turn is where conclusions/summaries/questions land —
    high signal for "what was discussed and how it resolved" — while a per-turn + total
    cap keeps a 4.8 MB transcript from bloating the JSON. Les explicitly wants a general
    sense, not a transcript dump.
  - **Rejected:** all assistant text blocks (bloat, noise); the renderer reading
    transcripts directly (violates `SKILL.md:28`, unbounded cost).

- **Decision:** Strict register firewall in the language rules; schema bump to v2.
  - **Why:** the tool's whole point is not overclaiming (`SKILL.md:63-69`, and the
    existing "strip harness completion claims from prompts" work). Assistant prose is the
    single richest source of *aspirational* claims, so the firewall must be explicit. A
    version bump signals the contract changed for anything parsing the JSON.
  - **Rejected:** surfacing assistant text without a firewall rule (reintroduces exactly
    the overclaim failure mode the tool was built to prevent).

## Patterns to follow

- Commit scanning, warning, and email-scoping: mirror `GhVerifier.commits`
  (`scripts/standup_digest.py:360-419`); add a `warn_non_repo: bool = True` param and pass
  `False` for harvested dirs.
- Dir harvesting: a pure function over `records` (like `extract_prompts`
  `:185-210`), unit-testable with plain-dict records; wire results into the commit loop in
  `build_digest` (`:574-583`) after the `cwds` pass, sharing `seen_paths`/`seen_shas`.
- Assistant capture: a pure function paralleling `_prompt_text`/`extract_prompts`
  (`:170-210`), added as a session field in `distill_session` (`:503-533`).
- Tests: mirror `test_commits_*` (`test_standup_digest.py:657-745`) for scanning,
  `test_extract_prompts_*` (`:242-286`) for the pure extractors, and update
  `test_digest_matches_documented_schema` (`:859`) + the documented key list (`:844`).

## What we're NOT doing

- **No config** — no roots list, no email list, no flags for discovery. Everything from
  the transcript.
- **No relative-`cd` resolution** — absolute `cd`/`git -C` targets only.
- **No transcript dump** — assistant capture is bounded and truncated; the renderer still
  never reads raw transcripts.
- **No re-labeling of a session's `repo`/`project`** from harvested dirs — the session's
  identity stays as recorded; harvested commits are attributed by their own `path`/`repo`.
- **No change to ref (PR/issue) extraction or gh verification.**
- **No new external dependencies.**

## Open questions

- **Per-session assistant-prose budget + per-turn truncation limits (char counts).**
  Default: reuse the spirit of `PROMPT_CHAR_LIMIT` for per-turn truncation, and set a
  per-session total budget in the low-thousands of characters (tune during execute so a
  busy session stays a paragraph or two, not pages). Non-blocking — plan proceeds under
  this default and the exact numbers are settled by eyeballing real output in `execute`.
