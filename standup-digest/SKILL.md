---
name: standup-digest
description: Use when Les asks what he was up to yesterday, wants a standup report, or needs to reconstruct recent work from his Claude Code sessions — surveys transcripts in ~/.claude/projects and reports what actually shipped.
---

# Standup Digest

## Overview

Surveys Claude Code session transcripts and produces a short standup report: three or
four bullets to read aloud, backed by a fuller digest to drill into when someone asks a
follow-up.

A companion to `gws-workflow-standup-report`, which covers meetings and tasks from Google
Workspace. This skill covers the work itself — what got typed, committed, opened, and
merged — and does not touch Calendar or Tasks.

## Run the extractor

```bash
python3 ~/devel/lmorchard-agent-skills/standup-digest/scripts/standup_digest.py
```

Defaults to the previous workday through today, so a Monday run sweeps Friday through
Sunday. Add `--date YYYY-MM-DD` for one specific day, or `--since`/`--until` for a range.
Add `--no-verify` when offline.

The script writes JSON to stdout. Read it and compose from it; do not re-read the raw
transcripts yourself.

## The digest contract

The JSON has: `schema_version`, `generated_at`, `window` (`since`/`until`/`rule`),
`stats` (`sessions`/`projects`/`malformed_lines`/`prompt_chars_dropped`/`gh_calls`),
`warnings`, `sessions[]`, and `commits[]`.

Each session carries `session_id`, `transcript`, `title`, `project`, `cwds`, `repo`,
`branches`, `launch`, `started_at`, `ended_at`, `prompt_count`, `prompt_chars_dropped`,
`prompts`, and `refs[]`. Each ref carries `kind`, `repo`, `number`, `source`, `url`,
`verification`, `state`, `title`, `merged_at`, `closed_at`. Each commit carries `repo`,
`path`, `sha`, `subject`, `committed_at`.

Do not invent fields, and do not read anything from the digest beyond this list.

## Language rules

The digest separates what is true from what is interesting. You choose what is
interesting. You do **not** get to upgrade what is true.

| Digest state | Permitted phrasing |
|---|---|
| `verification: confirmed` + state `MERGED` or `CLOSED` | landed, merged, shipped, closed |
| `verification: confirmed` + state `OPEN` | opened, in flight, up for review |
| `verification: unavailable` | worked on, looked at |

`unavailable` means the claim could not be checked, not that it succeeded or failed.
Never describe an `unavailable` ref with success language ("shipped", "merged", "landed",
"closed") or failure language ("abandoned", "rejected") — "worked on" or "looked at" is
the ceiling regardless of what a prompt or commit subject implied.

Further binding rules:

- Anything absent from the digest never appears as an accomplishment.
- Sessions with `launch: "driver"` were kicked off or delegated, not hand-worked. Say so.
- Sessions with `launch: "unknown"` get neutral phrasing — describe what happened
  (the repos and branches involved, plus any refs and commits) without
  characterizing *how* the session started. Do not call it hand-worked and do not
  call it delegated; "unknown" means the transcript had no human prompts to judge
  from, not that the answer is ambiguous between the two.
- When `warnings` is non-empty, add one short line saying the run was degraded. A
  partial digest must never read as a clean one.
- `refs` with `source: "prose"` are the looser signal — Les may have only mentioned a
  number while working on something else. Weight them below `pr-link` refs and below
  commits. A session with a long list of prose refs (e.g. five or more) is usually one
  piece of work that happened to touch many issue numbers, not that many separate
  accomplishments — describe it as one item ("triaged a batch of evals-judge issues")
  rather than enumerating every number in the headline. The full list still belongs in
  the detail file.

## Missing titles

`title` is `null` when the transcript had no `ai-title` record — this happens. Never
print "None" or leave the line blank. Fall back to the first entry in `prompts`
(trimmed to a short phrase) for a working label, and use `project` plus `branches` to
give it context, e.g. "pilo (feat/retry-backoff): fix the flaky retry test — ...". If
`prompts` is also empty (pairs with `launch: "unknown"` — no human prompts recorded at
all), drop the prompt fragment and label the session from `project` and `branches`
alone, e.g. "pilo (feat/retry-backoff): session with no recorded prompts".

## Output

**To the terminal**, three or four bullets ordered by significance, not chronology:

Annotate each bullet's phrasing against its ref state — not literal output text, but a
check you can run against the table above before you print anything:

```
## Tue Jul 28

- Refreshed PR #446 (pilo), still open, up for review     (confirmed, OPEN — not landed)
- Cleared a batch of evals-judge issues (#97, #100, #101, ...)   (confirmed, CLOSED)
- Zoo eval sandbox stood up, CDP flakiness still blocking clean runs   (no ref — from commits/prompts)

_full digest: ~/.claude/standup/2026-07-28.md_
```

The first line is the trap to avoid: PR #446 has genuinely been refreshed but is still
`OPEN` — "landed" or "merged" would be the fabrication this whole layer exists to
prevent. The second line's "cleared" is only honest because the issue refs are
`confirmed` + `CLOSED`; if any of them come back `unavailable`, drop to "worked on" for
those numbers instead — do not let one confirmed closure license the whole batch.

**To `~/.claude/standup/YYYY-MM-DD.md`** (create the directory if needed), the full
detail: one section per project, sessions underneath with title (or the fallback above),
branches, refs with their verified state, and a one-line gloss of intent drawn from the
prompts. `commits[]` is keyed by `repo`, not by session — a session's own `repo` field
tells you which project section it belongs to, but a commit is never attributable to one
particular session within that project, so list a project's commits once at the section
level, not repeated or split under individual sessions. Note in the file, once, that
prompts are truncated when `prompt_chars_dropped` is nonzero for a session or nonzero in
`stats` overall — the detail file is not a verbatim transcript.

Name the file for the window's start date.

## When the day was quiet

If `stats.sessions` is 0, say the window held no recorded sessions. Do not fill an empty
template, and do not pad with anything from the warnings.
