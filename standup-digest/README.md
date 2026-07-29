# standup-digest

Surveys Claude Code transcripts in `~/.claude/projects` and reports what you actually did.

## Why

Claude Code records everything, but the record is unreadable: a single day can hold
19 MB of JSONL across a dozen sessions, most of it tool payloads and subagent chatter.
The scarce thing at standup is not information. It is three or four honest sentences.

## How it works

Two layers with a hard boundary:

- `scripts/standup_digest.py` — a stdlib-only extractor. Discovers transcripts, filters
  to a time window, distills the human prompts, and verifies every PR, issue, and commit
  claim against `git` and `gh`. Emits JSON.
- `SKILL.md` — the renderer. Reads that JSON and composes the prose.

The extractor decides what is true; the renderer decides what is interesting. That split
is what lets the same digest also feed `journal-note` and `weeknotes-composer`.

## Verification

Transcripts record what an agent *claimed*. A PR is reported as landed only when `gh`
confirms it merged. When `gh` is unreachable, refs are marked `unavailable` and the
renderer downgrades its language — never the reverse.

## Usage

```bash
make standup                                   # previous workday, verified (run from repo root)
python3 scripts/standup_digest.py --date 2026-07-28
python3 scripts/standup_digest.py --no-verify  # offline
```

## Window

Defaults to the previous workday through today. Monday sweeps Friday, Saturday, and
Sunday, so weekend work appears rather than vanishing.

## Tests

```bash
make test
```

No test touches the network; `git` and `gh` sit behind a `Verifier` seam with a fake.

## Files

- `SKILL.md` — the renderer: language rules and output format Claude follows
- `scripts/standup_digest.py` — the extractor
- `scripts/test_standup_digest.py` — test suite
- `docs/dev-sessions/` — design history (spec, plan, notes)
