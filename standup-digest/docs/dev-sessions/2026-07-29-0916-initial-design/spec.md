# standup-digest — Design Spec

**Session:** 2026-07-29-0916-initial-design
**Status:** approved, ready for planning

## Problem

Les runs many Claude Code sessions a day across several repos. By the next morning's
standup, the details have evaporated. Claude Code already records everything in
`~/.claude/projects/**/*.jsonl`, but that record is unreadable: yesterday held 7
top-level sessions totalling 19 MB, most of it tool payloads and subagent chatter.

The scarce thing at standup is not information. It is three or four honest sentences.

## Goal

Produce a short spoken-aloud standup report of yesterday's work, backed by a fuller
digest to drill into when someone asks a follow-up.

A secondary goal shapes the architecture: the same extracted facts should later feed
`journal-note`, `daily-blog-post-composer`, and `weeknotes-composer` without a second
pipeline. The extractor therefore emits neutral structured data, and framing lives in a
rendering layer on top.

## Non-goals

Out of scope for this session, and easy to add later against the JSON contract:

- Cron scheduling or unattended runs
- Writing to Obsidian or any blog pipeline
- Multi-day or weekly rollups
- A TUI or any interactive browser

## Architecture

Two layers with a hard boundary between them:

```
~/.claude/projects/**/*.jsonl
        │
        ▼
  [ extractor ]   Python, stdlib-only, deterministic
        │         discover → filter → distill → verify
        ▼
   digest JSON    neutral facts, no editorial judgment
        │
        ▼
  [ renderer ]    SKILL.md, LLM composes framing
        │
        ├─► terminal: 3–5 headline bullets
        └─► ~/.claude/standup/YYYY-MM-DD.md
```

The extractor decides what is true. The renderer decides what is interesting. Neither
crosses into the other's job. That split is what lets one digest serve standup, journal,
and weeknotes.

## Component 1: Extractor

`standup-digest/scripts/standup_digest.py`, Python 3.11+, standard library only. It shells
out to `git` and `gh` but imports nothing outside stdlib, matching the portability stance
in `agent-sessions/driver/gate.py`.

### CLI

```
standup_digest.py [--date YYYY-MM-DD] [--since YYYY-MM-DD] [--until YYYY-MM-DD]
                  [--no-verify] [--root PATH] [--out PATH]
```

Writes JSON to stdout by default; `--out` writes to a file instead. All dates are
`YYYY-MM-DD` and resolve to local midnight. `--date` is shorthand for a single calendar
day and cannot be combined with `--since` or `--until`; `--until` is exclusive.
`--no-verify` skips all `git` and `gh` calls, for offline use and fast tests. `--root`
overrides the `~/.claude/projects` location, which exists so tests can point at a fixture
directory.

### Window

Default: **previous workday through today**, in local time.

| Run day | Window start |
|---|---|
| Monday | Friday 00:00 |
| Tuesday–Friday | yesterday 00:00 |
| Saturday, Sunday | yesterday 00:00 |

The window always ends at today 00:00. Monday therefore sweeps Friday, Saturday, and
Sunday, so weekend work appears rather than vanishing behind an empty Sunday.

Records store UTC timestamps. Convert at the boundary and compare in local time.

`window.rule` records which policy produced the bounds: `previous-workday` for the default,
`explicit` when `--date`, `--since`, or `--until` override it.

### Discovery

Glob `~/.claude/projects/*/*.jsonl`, then keep only filenames whose stem matches the UUID
pattern `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}`. Exclude any path
containing `/subagents/`. The glob is one level deep by design: subagent transcripts live
in a nested `<session-uuid>/subagents/` directory and are excluded by both rules.

Include a session when any record satisfies all of:

- `isSidechain` is not `true`
- `timestamp` falls inside the window

Select on record timestamps, not file mtime. A session file's mtime marks the last touch,
but sessions span days, so mtime both admits and omits the wrong ones.

### Distillation

Per surviving session, extract:

| Field | Source |
|---|---|
| `title` | last `type == "ai-title"` record's `aiTitle` |
| `project` | the `~/.claude/projects/` directory name, decoded back to a path and shortened relative to `~/devel` |
| `cwds`, `branches` | distinct `cwd` and `gitBranch` across records |
| `started_at`, `ended_at` | first and last **in-window** record timestamp |
| `prompts` | human prompt text (see below) |
| `launch` | inferred, see below |
| refs | `type == "pr-link"` records, plus regex over prompt text |

`started_at` is the timestamp of the earliest record inside the window, so a session that
began the previous evening reports its first in-window activity rather than its true start.
Sessions are never excluded for starting early; only their records are bounded.

**Human prompts.** Keep records where `type == "user"` and `isMeta` is not `true`. Keep
string `content` and, for block-list content, only blocks with `type == "text"` — this
drops `tool_result` payloads, which carry the bulk of the volume. Strip
`<local-command-caveat>`, `<system-reminder>`, and `<command-name>` wrappers.

Measured on 2026-07-28: 19 MB of raw JSONL reduces to 75 KB across 711 lines, roughly 19k
tokens. Truncate each individual prompt at 1500 characters, appending an explicit
`… [truncated]` marker. Record the dropped count per session as
`session.prompt_chars_dropped` and summed across sessions as `stats.prompt_chars_dropped`.
Report truncation; never truncate silently.

**Launch inference.** Les's `agent-sessions` board-driver launches sessions with synthetic
prompts, so not every prompt is Les typing. This matters at standup: "I kicked off
autonomous runs on #100 and #101" is a different claim from "I hand-worked #446."

Set `launch` to `driver` when the first human prompt matches any of:

- `You are running unattended`
- `invoked by the ... board-driver`
- `There is no human watching`

Otherwise `human`. When a session has no human prompts at all, use `unknown`. Do not guess
past these three markers; a wrong attribution is worse than `unknown`.

### Verification

Transcripts record what an agent *claimed*. A digest that repeats an optimistic "done!" to
a standup is the exact failure `CLAUDE.md` warns about, so no claim reaches the report
unchecked.

**Refs.** Collect PR and issue references from `pr-link` records and from `#\d+` plus
GitHub URL patterns in prompt text. Resolve the repo from the `pr-link` record when
present, otherwise from the session's `cwd` remote. For each ref run `gh pr view` or
`gh issue view` with `--json state,title,url,mergedAt,closedAt`. Each ref records its
`source` as either `pr-link` or `prose`; prose-derived refs are the looser signal, since a
`#123` in a prompt may be something Les merely mentioned.

Deduplicate refs by `(repo, kind, number)` before calling `gh`, preferring `pr-link` as the
source when both produced the same ref. One `gh` call per unique ref per run.

**Commits.** For each distinct `cwd`, resolve worktree paths to their real repository via
`git rev-parse --path-format=absolute --git-common-dir`, then run `git log` bounded by the
window with `--author="$(git config user.email)"`. Collect at the top level of the digest
keyed by repo, since several sessions typically share one, and deduplicate by SHA.

**Verification states.** Every ref carries `verification`:

- `confirmed` — `gh` returned data, and `state` holds the truth
- `unavailable` — no `gh` binary, no auth, no network, or unknown repo

There is no third state. An unreachable API means unknown, never false, and never a silent
upgrade to success.

### Digest schema

```json
{
  "schema_version": 1,
  "generated_at": "2026-07-29T09:16:00-04:00",
  "window": {
    "since": "2026-07-28T00:00:00-04:00",
    "until": "2026-07-29T00:00:00-04:00",
    "rule": "previous-workday"
  },
  "stats": {
    "sessions": 7, "projects": 3,
    "malformed_lines": 3, "prompt_chars_dropped": 0,
    "gh_calls": 5
  },
  "warnings": ["gh unavailable: not authenticated"],
  "sessions": [
    {
      "session_id": "2588509f-dba9-463e-9df6-6c208cc1893c",
      "transcript": "/Users/lorchard/.claude/projects/.../2588509f-....jsonl",
      "title": "Evaluate and refresh stale PR 446",
      "project": "tabs-project/pilo",
      "cwds": ["/Users/lorchard/devel/tabs-project/pilo/.worktrees/page-exploration-tools"],
      "branches": ["fix/spa-snapshot-readiness-guard"],
      "launch": "human",
      "started_at": "2026-07-28T07:12:33-04:00",
      "ended_at": "2026-07-28T08:15:41-04:00",
      "prompt_count": 12,
      "prompt_chars_dropped": 0,
      "prompts": ["PR 446 has gotten quite stale — do you think..."],
      "refs": [
        {
          "kind": "pr", "repo": "mozilla/pilo", "number": 446,
          "source": "pr-link", "verification": "confirmed",
          "state": "MERGED", "merged_at": "2026-07-28T18:22:11Z",
          "title": "feat(core): add page exploration tools, structured extract",
          "url": "https://github.com/mozilla/pilo/pull/446"
        }
      ]
    }
  ],
  "commits": [
    {
      "repo": "mozilla/pilo",
      "path": "/Users/lorchard/devel/tabs-project/pilo",
      "sha": "abc1234",
      "subject": "fix(core): guard SPA snapshot readiness",
      "committed_at": "2026-07-28T14:02:11-04:00"
    }
  ]
}
```

`schema_version` exists so the journal and weeknotes consumers can detect drift later.

## Component 2: Renderer

`standup-digest/SKILL.md`. Runs the script, reads the JSON, writes the detail file, prints
the headline.

**Output shape.** Three or four bullets, each one line, ordered by significance rather
than chronology, with a footer pointing at the detail file:

```
## Tue Jul 28

- Refreshed + landed stale PR #446 (pilo)
- Cleared 3 evals-judge issues (#97/100/101)
- Zoo eval sandbox stood up, CDP flakiness still blocking clean runs

_full digest: ~/.claude/standup/2026-07-28.md_
```

**Language rules**, binding on the renderer:

| Digest state | Permitted phrasing |
|---|---|
| `confirmed` + `MERGED`/`CLOSED` | landed, merged, shipped, closed |
| `confirmed` + `OPEN` | opened, in flight, up for review |
| `unavailable` | worked on, looked at |

Anything absent from the digest never appears as an accomplishment. Sessions with
`launch: driver` are described as kicked off or delegated, not hand-worked. When
`warnings` is non-empty, the headline says so in one short line, so a degraded run never
passes as a clean one.

**Detail file.** `~/.claude/standup/YYYY-MM-DD.md`, one section per project, sessions
underneath with their titles, branches, refs and verified state, and a one-line gloss of
intent drawn from the prompts.

## Error handling

- **Malformed JSONL** — skip the line, count it in `stats.malformed_lines`. These files are
  appended live, so a trailing partial write is normal, not a fault.
- **Missing `gh` or auth** — mark affected refs `unavailable`, append to `warnings`, exit 0.
- **Missing `git` or a non-repo `cwd`** — omit those commits, append to `warnings`.
- **Empty window** — emit a valid digest with zero sessions. The renderer says the day was
  quiet rather than filling an empty template.
- **Unreadable transcript** — skip it, append to `warnings`.

Degradation is always partial and always announced. The script exits non-zero only on bad
arguments or an unwritable `--out`.

## Testing

`pytest`, following the `agent-sessions` precedent, against a trimmed fixture transcript
with paths and secrets scrubbed.

Pure functions, tested directly:

- window calculation, especially the Monday rule and the local/UTC boundary
- record filtering: sidechain, `isMeta`, subagent paths, tool-result blocks
- prompt extraction and the 1500-character truncation accounting
- ref extraction from both `pr-link` records and prose, including dedup by
  `(repo, kind, number)` with `pr-link` winning over `prose`
- launch inference across all three outcomes

The `git`/`gh` layer sits behind a `Verifier` seam with a real implementation and a fake,
so no test touches the network. One end-to-end test runs the extractor over the fixture
with `--no-verify` and asserts the digest validates against the schema.

## Deliverables

```
standup-digest/
  SKILL.md
  README.md
  scripts/
    standup_digest.py
    test_standup_digest.py
    fixtures/sample-session.jsonl
```

Register the skill in `.claude-plugin/plugin.json`. Add a repo-root `Makefile` with `test`
and `standup` targets; the repo currently has none.

## Open decisions, already made

- **Name.** `standup-digest`, distinct from the existing `gws-workflow-standup-report`,
  which reads Google Workspace meetings and tasks. The two are complementary: that one
  holds the calendar, this one holds the work.
- **Home.** `~/devel/lmorchard-agent-skills`, beside `journal-note` and
  `weeknotes-composer`, rather than `agent-sessions`. This tool reads transcripts from
  every project; it is not part of the board-driver loop.
