---
name: laurels
description: Use when noticing work that landed genuinely well and worth remembering — nominate it as a laurel (calibration, surfaced at future session starts). Also the reference for how laurels are captured, adjudicated, and surfaced.
---

# Laurels

Laurels record work that turned out genuinely good, surfaced back at session start as
**calibration** ("this approach worked — reuse it"), not vibes. A laurel grants no task
and no priority; there is nothing to farm.

## Taxonomy / Canonical Tags

Tag entries to categorize the engineering instinct:

- `#test` — negative testing, mutation testing, proving guards fail before green
- `#spike` — cheap empirical experiments, measuring before designing/speccing
- `#diag` — root-cause isolation, dumping state at boundaries, diagnosing flakes/heisenbugs
- `#arch` — structural primitives, state machines, clean codecs, invariant preservation
- `#ui` — layouts, anti-jitter spacing, responsive interactions, terminal ergonomics
- `#protocol` — real paths over synthetic shortcuts, standards/RFC compliance, auth flows
- `#harness` — meta-verification, auditing evaluation tools/diffs/checklists for bias
- `#collab` — human-agent steering, pushback that mattered, redirecting away from red herrings

## Capture (during a session)

When you notice a genuinely good result — a satisfying fix, a non-obvious approach that
paid off — nominate it, **sparingly**:

    python3 ~/.claude/skills/laurels/scripts/laurels.py add "<what worked + why>" -t <tag> --cwd "$PWD"

You can pass `-t` multiple times, use `--tags "spike, perf"`, or write `#tag` inline in the text.
Issue numbers (like `#54`) are automatically distinguished from tags.

Not every passing test. Only work worth remembering weeks later. Over-nomination burns
Les's adjudication attention — that is the scarce resource, so err toward restraint.

## Adjudicate (at session-wrapup)

`session-wrapup` runs this as a shared-spine step; you rarely invoke it standalone.

    laurels.py pending --cwd "$PWD"      # this project's candidates, with indices
    laurels.py accept <index...>         # move blessed ones into the pool (can add -t tag)
    laurels.py drop <index...>           # discard the rest

## Surface (at session start)

A SessionStart hook runs `laurels.py show --cwd "$PWD"` and injects a project-relevant
laurel or two as calibration. Nothing to act on when you see them.

By default, `show` selects the latest project entry plus a diverse older entry (preferring
different tags) to prevent stale repetition, plus an occasional cross-project roll.

Options:
- `laurels.py show --tag <tag>` — focus calibration on a specific theme (e.g. `diag`)
- `laurels.py show --recent` — strictly sample the two newest entries

## Manage & Graduate

- `laurels.py tags [--all]` — inspect tag frequencies across the pool
- `laurels.py list [--tag <tag>] [--all]` — list accepted laurels with line indices
- `laurels.py archive <index...>` — move retired or graduated entries (e.g., lessons codified into permanent project docs) to `archive.md`

## Store

`~/.claude/laurels/`:
- `pending.md` (nominations)
- `laurels.md` (active accepted pool)
- `archive.md` (graduated/retired entries)

Runtime data, project-tagged, hand-editable. Override location with `LAURELS_DIR`.
