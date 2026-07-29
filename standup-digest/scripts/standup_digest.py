#!/usr/bin/env python3
"""Survey Claude Code transcripts and emit a structured standup digest.

Standard library only. Shells out to `git` and `gh`, imports neither.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

MONDAY = 0


@dataclass(frozen=True)
class Window:
    since: datetime
    until: datetime
    rule: str


def _midnight(moment: datetime) -> datetime:
    """Local midnight beginning the day that `moment` falls in."""
    return moment.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)


def _parse_day(text: str) -> datetime:
    """Parse YYYY-MM-DD as local midnight."""
    return datetime.strptime(text, "%Y-%m-%d").astimezone()


def resolve_window(
    now: datetime,
    date: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> Window:
    if date and (since or until):
        raise ValueError("--date cannot be combined with --since or --until")

    if date:
        start = _parse_day(date)
        return Window(start, start + timedelta(days=1), "explicit")

    if since or until:
        today = _midnight(now)
        start = _parse_day(since) if since else today - timedelta(days=1)
        end = _parse_day(until) if until else today
        if end <= start:
            raise ValueError("--until must be after --since")
        return Window(start, end, "explicit")

    today = _midnight(now)
    back = 3 if today.weekday() == MONDAY else 1
    return Window(today - timedelta(days=back), today, "previous-workday")
