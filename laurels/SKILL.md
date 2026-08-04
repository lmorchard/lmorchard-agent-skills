---
name: laurels
description: Use when noticing work that landed genuinely well and worth remembering — nominate it as a laurel (calibration, surfaced at future session starts). Also the reference for how laurels are captured, adjudicated, and surfaced.
---

# Laurels

Laurels record work that turned out genuinely good, surfaced back at session start as
**calibration** ("this approach worked — reuse it"), not vibes. A laurel grants no task
and no priority; there is nothing to farm.

## Capture (during a session)

When you notice a genuinely good result — a satisfying fix, a non-obvious approach that
paid off — nominate it, **sparingly**:

    python3 ~/.claude/skills/laurels/scripts/laurels.py add "<what worked + why>" --cwd "$PWD"

Not every passing test. Only work worth remembering weeks later. Over-nomination burns
Les's adjudication attention — that is the scarce resource, so err toward restraint.

## Adjudicate (at session-wrapup)

`session-wrapup` runs this as a shared-spine step; you rarely invoke it standalone.

    laurels.py pending --cwd "$PWD"      # this project's candidates, with indices
    laurels.py accept <index...>         # move blessed ones into the pool
    laurels.py drop <index...>           # discard the rest

## Surface (at session start)

A SessionStart hook runs `laurels.py show --cwd "$PWD"` and injects a project-relevant
laurel or two as calibration. Nothing to act on when you see them.

## Store

`~/.claude/laurels/pending.md` (nominations) and `laurels.md` (accepted pool). Runtime
data, project-tagged, hand-editable. Override location with `LAURELS_DIR`.
