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

The JSON (`schema_version` 2) has: `schema_version`, `generated_at`, `window`
(`since`/`until`/`rule`),
`stats` (`sessions`/`projects`/`malformed_lines`/`prompt_chars_dropped`/`gh_calls`),
`warnings`, `sessions[]`, and `commits[]`.

Each session carries `session_id`, `transcript`, `title`, `project`, `cwds`, `repo`,
`branches`, `launch`, `started_at`, `ended_at`, `prompt_count`, `prompt_chars_dropped`,
`prompts`, `assistant_notes`, and `refs[]`. `assistant_notes` is a bounded, truncated
list of the closing prose of assistant turns — a sense of what was discussed, not a
transcript (see the conversation register-firewall rule below). Each ref carries `kind`,
`repo`, `number`, `source`, `url`, `verification`, `state`, `title`, `merged_at`,
`closed_at`. Each commit carries `repo`, `path`, `sha`, `subject`, `committed_at` —
`repo` is `null` for a local repo with no GitHub remote (use `path`'s directory name).

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

- Claims drawn from `prompts` alone — with no corroborating `commits[]` entry or a
  `confirmed` ref — license only intent language ("started on", "looked at", "picked
  up"). Outcome language ("landed", "shipped", "stood up", "cleared", "fixed") requires
  a commit or a confirmed ref behind it; a prompt records what someone said they meant
  to do, not that it happened. This is the same trap `prompts[]` created before the
  extractor learned to strip harness-injected completion claims out of it — the
  renderer is the layer that still has to enforce it for everything else in that array.
- **Conversation is topic signal, not proof.** `prompts` and `assistant_notes` say what
  was discussed, debated, and decided — render them in a *descriptive* register ("worked
  through", "went back and forth on", "landed on X in discussion", "explored"). They
  never, on their own, license outcome language ("shipped/landed/merged/fixed/closed"),
  which still requires a `commits[]` entry or a `confirmed` ref. `assistant_notes` is
  assistant prose and may carry aspirational completion claims ("now it works", "all
  green") — treat it as a record of what was said, never as evidence that it happened.
  This is the firewall that lets the narrative get vivid without the accomplishments
  getting loose.
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

Two artifacts: the terminal bullets (the tl;dr), and the full detail file — which now
*opens* with those same bullets.

### Terminal — the tl;dr

Three or four bullets ordered by significance, not chronology. Annotate each (in your
head, against the ref-state table above) before you print it:

```
## Tue Jul 28

- Refreshed PR #446 (pilo), still open, up for review     (confirmed, OPEN — not landed)
- Cleared a batch of evals-judge issues (#96, #97, #99, #101)   (confirmed, CLOSED)
- Started standing up a zoo eval sandbox; CDP flakiness still blocking clean runs   (no ref, no commit — from a prompt only, intent language)

_threads today: secret-management migration, eval date-robustness, a lot of triage_
_full digest: ~/Documents/Obsidian/main/standup-digests/2026-07-28.md_
```

The first bullet is the trap to avoid: PR #446 has genuinely been refreshed but is still
`OPEN` — "landed" or "merged" would be the fabrication this whole layer exists to prevent.
The second line's "cleared" is only honest because the issue refs are `confirmed` +
`CLOSED`; if any come back `unavailable`, drop to "worked on" for those numbers — one
confirmed closure doesn't license the whole batch. The third has no ref and no commit,
only a prompt describing intent, so it stays in intent language. The optional
`_threads today:_` line is conversational texture from `prompts`/`assistant_notes` —
descriptive only, never an accomplishment (see the register firewall).

### Detail file — `~/Documents/Obsidian/main/standup-digests/YYYY-MM-DD.md`

Create the directory if needed; name the file for the window's **start** date. Structure:

1. **`## tl;dr` at the very top** — the same significance-ranked bullets shown in the
   terminal (plus the one-line degraded-run note when `warnings` is non-empty). Someone
   should be able to get the day from these alone.
2. **One section per project**, each session under it (title, or the fallback label,
   plus branches) with two clearly separated parts:
   - **_what you worked through_** — a few descriptive bullets synthesizing `prompts` +
     `assistant_notes`: the questions asked, the debates, what got decided. Descriptive
     register only (see the firewall) — this is where the day gets its texture.
   - **_what shipped_** — only commit- or ref-backed items, phrased as the ref-state
     table permits. If nothing shipped, say so; never promote discussion into shipment.

Group `commits[]` by `repo`. A session's own `repo` says which project section it belongs
to, but a commit is never attributable to one session within that project — so list a
project's commits once at the section level, not split under individual sessions. Commits
with `repo: null` are a local repo with no GitHub remote: group them under a heading from
the `path`'s directory basename, e.g. `zoo-service (local, no remote)`.

Note once in the file that prompts/notes are truncated when `prompt_chars_dropped` is
nonzero (for a session or in `stats`) — the detail file is not a verbatim transcript.

## When the day was quiet

If `stats.sessions` is 0, say the window held no recorded sessions. Do not fill an empty
template, and do not pad with anything from the warnings.
