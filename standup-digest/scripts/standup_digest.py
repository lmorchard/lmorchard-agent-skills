#!/usr/bin/env python3
"""Survey Claude Code transcripts and emit a structured standup digest.

Standard library only. Shells out to `git` and `gh`, imports neither.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

MONDAY = 0

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


@dataclass(frozen=True)
class Window:
    since: datetime
    until: datetime
    rule: str


@dataclass
class Transcript:
    path: Path
    records: list[dict]
    malformed: int


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


def is_session_transcript(path: Path) -> bool:
    """A top-level session transcript, not a subagent's."""
    if "subagents" in path.parts:
        return False
    return bool(UUID_RE.match(path.stem))


def read_transcript(path: Path) -> Transcript:
    """Parse a JSONL transcript, tolerating partial trailing writes."""
    records: list[dict] = []
    malformed = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
            else:
                malformed += 1
    return Transcript(path=path, records=records, malformed=malformed)


def record_timestamp(rec: dict) -> datetime | None:
    raw = rec.get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _is_mainline(rec: dict) -> bool:
    return rec.get("isSidechain") is not True


def touches_window(records: list[dict], window: Window) -> bool:
    for rec in records:
        if not _is_mainline(rec):
            continue
        moment = record_timestamp(rec)
        if moment is not None and window.since <= moment < window.until:
            return True
    return False


def discover_transcripts(root: Path) -> list[Path]:
    """Every top-level session transcript under ~/.claude/projects."""
    return sorted(p for p in root.glob("*/*.jsonl") if is_session_transcript(p))
