# standup-digest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a skill that surveys Claude Code transcripts in `~/.claude/projects` and produces a 3–5 bullet standup report backed by a fuller digest.

**Architecture:** A stdlib-only Python extractor walks the JSONL transcripts, distills them to neutral structured facts, verifies every PR/issue/commit claim against `git` and `gh`, and emits JSON. A thin `SKILL.md` renderer reads that JSON and composes the prose. The extractor decides what is true; the renderer decides what is interesting.

**Tech Stack:** Python 3.11+ (standard library only), `pytest` for tests, `git` and `gh` shelled out via `subprocess`, Markdown for the skill.

## Global Constraints

- Python 3.11+ (`datetime.fromisoformat` must parse trailing `Z`).
- The extractor imports **only the standard library**. `subprocess` calls to `git`/`gh` are fine; third-party imports are not.
- Everything lives under `standup-digest/` in `~/devel/lmorchard-agent-skills`.
- No network access in any test. The `git`/`gh` layer sits behind a `Verifier` seam with a fake.
- Degradation is always partial and always announced via `warnings`. Exit non-zero only on bad arguments or an unwritable `--out`.
- Never truncate silently — every dropped character is counted and reported.
- Verification has exactly two states: `confirmed` and `unavailable`. An unreachable API means unknown, never false.
- Spec of record: `standup-digest/docs/dev-sessions/2026-07-29-0916-initial-design/spec.md`.

## File Structure

| File | Responsibility |
|---|---|
| `standup-digest/scripts/standup_digest.py` | The whole extractor: window, discovery, distillation, refs, verification seam, CLI. Single file, matching the stdlib-only single-file precedent of `agent-sessions/driver/gate.py`. |
| `standup-digest/scripts/test_standup_digest.py` | All unit and end-to-end tests. |
| `standup-digest/scripts/fixtures/sample-session.jsonl` | Hand-authored transcript with known values. |
| `standup-digest/scripts/fixtures/driver-session.jsonl` | Hand-authored transcript with a board-driver preamble. |
| `standup-digest/SKILL.md` | The renderer. Language rules and output shape. |
| `standup-digest/README.md` | Human-facing docs. |
| `Makefile` (repo root, new) | `test` and `standup` targets. |
| `.claude-plugin/plugin.json` (modify) | Register the skill. |

Tests live beside the module so pytest's default `prepend` import mode puts the module on `sys.path` with no packaging ceremony.

---

### Task 1: Scaffold and window calculation

**Files:**
- Create: `standup-digest/scripts/standup_digest.py`
- Create: `standup-digest/scripts/test_standup_digest.py`
- Create: `Makefile` (repo root)

**Interfaces:**
- Consumes: nothing.
- Produces: `Window` dataclass with fields `since: datetime`, `until: datetime`, `rule: str`; and `resolve_window(now: datetime, date: str | None = None, since: str | None = None, until: str | None = None) -> Window`.

- [ ] **Step 1: Write the failing tests**

Create `standup-digest/scripts/test_standup_digest.py`:

```python
from datetime import datetime, timedelta

import pytest

import standup_digest as sd


def local(y, m, d, hh=0, mm=0):
    """A tz-aware local datetime, matching what resolve_window returns."""
    naive = datetime(y, m, d, hh, mm)
    return naive.astimezone()


def test_monday_sweeps_friday_through_sunday():
    # 2026-08-03 is a Monday.
    w = sd.resolve_window(local(2026, 8, 3, 9, 16))
    assert w.since == local(2026, 7, 31)  # Friday
    assert w.until == local(2026, 8, 3)
    assert w.rule == "previous-workday"


def test_midweek_sweeps_yesterday():
    # 2026-07-29 is a Wednesday.
    w = sd.resolve_window(local(2026, 7, 29, 9, 16))
    assert w.since == local(2026, 7, 28)
    assert w.until == local(2026, 7, 29)
    assert w.rule == "previous-workday"


@pytest.mark.parametrize("day", [1, 2])  # Saturday 2026-08-01, Sunday 2026-08-02
def test_weekend_sweeps_yesterday(day):
    w = sd.resolve_window(local(2026, 8, day, 9, 16))
    assert w.since == local(2026, 8, day) - timedelta(days=1)


def test_explicit_date_is_one_calendar_day():
    w = sd.resolve_window(local(2026, 7, 29), date="2026-07-20")
    assert w.since == local(2026, 7, 20)
    assert w.until == local(2026, 7, 21)
    assert w.rule == "explicit"


def test_explicit_since_until_override():
    w = sd.resolve_window(
        local(2026, 7, 29), since="2026-07-01", until="2026-07-05"
    )
    assert w.since == local(2026, 7, 1)
    assert w.until == local(2026, 7, 5)
    assert w.rule == "explicit"


def test_date_combined_with_since_is_rejected():
    with pytest.raises(ValueError):
        sd.resolve_window(local(2026, 7, 29), date="2026-07-20", since="2026-07-01")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --with pytest pytest standup-digest/scripts -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'standup_digest'`

- [ ] **Step 3: Write the minimal implementation**

Create `standup-digest/scripts/standup_digest.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --with pytest pytest standup-digest/scripts -q`
Expected: PASS, 7 passed

- [ ] **Step 5: Add the repo-root Makefile**

The repo currently has none. Create `Makefile`:

```make
.PHONY: help test standup

help:
	@echo "test     - run the standup-digest test suite"
	@echo "standup  - print yesterday's digest JSON"

test:
	uv run --with pytest pytest standup-digest/scripts -q

standup:
	python3 standup-digest/scripts/standup_digest.py
```

- [ ] **Step 6: Verify the Makefile works**

Run: `make test`
Expected: PASS, 7 passed

- [ ] **Step 7: Commit**

```bash
git add standup-digest/scripts Makefile
git commit -m "standup-digest: window resolution and test scaffold"
```

---

### Task 2: Transcript discovery and record reading

**Files:**
- Modify: `standup-digest/scripts/standup_digest.py`
- Modify: `standup-digest/scripts/test_standup_digest.py`
- Create: `standup-digest/scripts/fixtures/sample-session.jsonl`

**Interfaces:**
- Consumes: `Window` from Task 1.
- Produces: `UUID_RE`, `is_session_transcript(path: Path) -> bool`, `Transcript` dataclass (`path: Path`, `records: list[dict]`, `malformed: int`), `read_transcript(path: Path) -> Transcript`, `record_timestamp(rec: dict) -> datetime | None`, `touches_window(records: list[dict], window: Window) -> bool`, `discover_transcripts(root: Path) -> list[Path]`.

- [ ] **Step 1: Create the fixture**

Create `standup-digest/scripts/fixtures/sample-session.jsonl`. Hand-authored with known values so assertions are exact. Note the deliberate malformed final line.

```jsonl
{"type":"mode","mode":"normal","sessionId":"11111111-2222-3333-4444-555555555555"}
{"type":"user","isSidechain":false,"timestamp":"2026-07-28T14:00:00.000Z","cwd":"/Users/lorchard/devel/tabs-project/pilo","gitBranch":"main","sessionId":"11111111-2222-3333-4444-555555555555","message":{"role":"user","content":"PR 446 has gotten quite stale - is it still worth merging? https://github.com/mozilla/pilo/pull/446"}}
{"type":"assistant","isSidechain":false,"timestamp":"2026-07-28T14:00:05.000Z","sessionId":"11111111-2222-3333-4444-555555555555","message":{"role":"assistant","content":[{"type":"text","text":"Let me check the PR state."}]}}
{"type":"user","isSidechain":false,"timestamp":"2026-07-28T14:00:09.000Z","sessionId":"11111111-2222-3333-4444-555555555555","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_01","content":"{\"state\":\"OPEN\"}"}]}}
{"type":"user","isSidechain":true,"timestamp":"2026-07-28T14:00:11.000Z","sessionId":"11111111-2222-3333-4444-555555555555","message":{"role":"user","content":"sidechain prompt that must be ignored"}}
{"type":"user","isMeta":true,"isSidechain":false,"timestamp":"2026-07-28T14:00:12.000Z","sessionId":"11111111-2222-3333-4444-555555555555","message":{"role":"user","content":"meta prompt that must be ignored"}}
{"type":"user","isSidechain":false,"timestamp":"2026-07-28T15:30:00.000Z","cwd":"/Users/lorchard/devel/tabs-project/pilo/.worktrees/pet","gitBranch":"feat/pet","sessionId":"11111111-2222-3333-4444-555555555555","message":{"role":"user","content":"<system-reminder>ignore me</system-reminder>Now resolve the conflicts and close out issue #97."}}
{"type":"pr-link","sessionId":"11111111-2222-3333-4444-555555555555","prNumber":446,"prUrl":"https://github.com/mozilla/pilo/pull/446","prRepository":"mozilla/pilo","timestamp":"2026-07-28T16:10:20.723Z"}
{"type":"user","isSidechain":false,"timestamp":"2026-07-30T09:00:00.000Z","sessionId":"11111111-2222-3333-4444-555555555555","message":{"role":"user","content":"a prompt outside the window"}}
{"type":"ai-title","aiTitle":"Evaluate and refresh stale PR 446","sessionId":"11111111-2222-3333-4444-555555555555"}
{"type":"user","isSidechain":false,"timestamp":"2026-07-28T
```

- [ ] **Step 2: Write the failing tests**

Append to `test_standup_digest.py`:

```python
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def test_uuid_filenames_are_transcripts():
    assert sd.is_session_transcript(Path("/p/11111111-2222-3333-4444-555555555555.jsonl"))
    assert not sd.is_session_transcript(Path("/p/notes.jsonl"))
    assert not sd.is_session_transcript(Path("/p/11111111-2222.jsonl"))


def test_subagent_paths_are_excluded():
    p = Path("/p/abc/subagents/11111111-2222-3333-4444-555555555555.jsonl")
    assert not sd.is_session_transcript(p)


def test_read_transcript_counts_malformed_lines():
    t = sd.read_transcript(FIXTURES / "sample-session.jsonl")
    assert t.malformed == 1          # the deliberate truncated final line
    assert len(t.records) == 10


def test_record_timestamp_parses_utc_z():
    rec = {"timestamp": "2026-07-28T14:00:00.000Z"}
    got = sd.record_timestamp(rec)
    assert got is not None
    assert got.year == 2026 and got.hour == 14


def test_record_timestamp_missing_returns_none():
    assert sd.record_timestamp({"type": "mode"}) is None


def test_touches_window_ignores_sidechain_records():
    window = sd.Window(local(2026, 7, 30, 8), local(2026, 7, 30, 10), "explicit")
    only_sidechain = [
        {"isSidechain": True, "timestamp": "2026-07-30T09:00:00.000Z"},
    ]
    assert not sd.touches_window(only_sidechain, window)


def test_touches_window_matches_in_window_record():
    t = sd.read_transcript(FIXTURES / "sample-session.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    assert sd.touches_window(t.records, window)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — `AttributeError: module 'standup_digest' has no attribute 'is_session_transcript'`

- [ ] **Step 4: Write the implementation**

Add to `standup_digest.py` (imports go at the top of the file):

```python
import json
import re
from pathlib import Path

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


@dataclass
class Transcript:
    path: Path
    records: list[dict]
    malformed: int


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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `make test`
Expected: PASS, 14 passed

- [ ] **Step 6: Commit**

```bash
git add standup-digest/scripts
git commit -m "standup-digest: transcript discovery and tolerant JSONL reading"
```

---

### Task 3: Prompt extraction, launch inference, session distillation

**Files:**
- Modify: `standup-digest/scripts/standup_digest.py`
- Modify: `standup-digest/scripts/test_standup_digest.py`
- Create: `standup-digest/scripts/fixtures/driver-session.jsonl`

**Interfaces:**
- Consumes: `Transcript`, `Window`, `record_timestamp`, `_is_mainline` from Task 2.
- Produces: `PROMPT_CHAR_LIMIT`, `strip_wrappers(text: str) -> str`, `extract_prompts(records, window) -> tuple[list[str], int]`, `infer_launch(prompts: list[str]) -> str`, `project_label(dirname: str) -> str`, `distill_session(transcript: Transcript, window: Window) -> dict`.

- [ ] **Step 1: Create the driver fixture**

Create `standup-digest/scripts/fixtures/driver-session.jsonl`:

```jsonl
{"type":"user","isSidechain":false,"timestamp":"2026-07-28T10:00:00.000Z","cwd":"/Users/lorchard/devel/agent-sessions","gitBranch":"main","sessionId":"99999999-8888-7777-6666-555555555555","message":{"role":"user","content":"You are running unattended, invoked by the agent-session board-driver.\nWork issue https://github.com/lmorchard/agent-sessions/issues/4"}}
{"type":"ai-title","aiTitle":"Tackle GitHub issue 4","sessionId":"99999999-8888-7777-6666-555555555555"}
```

- [ ] **Step 2: Write the failing tests**

Append to `test_standup_digest.py`:

```python
def test_strip_wrappers_removes_system_noise():
    text = (
        "<local-command-caveat>blah</local-command-caveat>"
        "<system-reminder>nope</system-reminder>"
        "<command-name>/clear</command-name>"
        "real content"
    )
    assert sd.strip_wrappers(text) == "real content"


def test_extract_prompts_keeps_only_human_mainline_text():
    t = sd.read_transcript(FIXTURES / "sample-session.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    prompts, dropped = sd.extract_prompts(t.records, window)

    assert dropped == 0
    assert len(prompts) == 2
    assert prompts[0].startswith("PR 446 has gotten quite stale")
    assert prompts[1] == "Now resolve the conflicts and close out issue #97."
    joined = " ".join(prompts)
    assert "sidechain prompt" not in joined      # isSidechain
    assert "meta prompt" not in joined           # isMeta
    assert "tool_result" not in joined           # block-list tool payloads
    assert "outside the window" not in joined    # out of window
    assert "ignore me" not in joined             # stripped wrapper


def test_extract_prompts_truncates_and_counts():
    long_text = "x" * (sd.PROMPT_CHAR_LIMIT + 250)
    records = [
        {
            "type": "user",
            "isSidechain": False,
            "timestamp": "2026-07-28T14:00:00.000Z",
            "message": {"role": "user", "content": long_text},
        }
    ]
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    prompts, dropped = sd.extract_prompts(records, window)

    assert dropped == 250
    assert prompts[0].endswith("… [truncated]")
    assert len(prompts[0]) == sd.PROMPT_CHAR_LIMIT + len("… [truncated]")


def test_infer_launch_detects_driver_preamble():
    assert sd.infer_launch(["You are running unattended, invoked by..."]) == "driver"
    assert sd.infer_launch(["There is no human watching this run."]) == "driver"


def test_infer_launch_defaults_to_human():
    assert sd.infer_launch(["please fix the flaky test"]) == "human"


def test_infer_launch_unknown_when_no_prompts():
    assert sd.infer_launch([]) == "unknown"


def test_project_label_decodes_and_shortens():
    assert sd.project_label("-Users-lorchard-devel-tabs-project-pilo") == "tabs-project/pilo"


def test_distill_session_collects_metadata():
    t = sd.read_transcript(FIXTURES / "sample-session.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    got = sd.distill_session(t, window)

    assert got["title"] == "Evaluate and refresh stale PR 446"
    assert got["session_id"] == "11111111-2222-3333-4444-555555555555"
    assert got["launch"] == "human"
    assert got["prompt_count"] == 2
    assert got["branches"] == ["feat/pet", "main"]
    assert got["started_at"].startswith("2026-07-28T")
    # ended_at must be the last in-window record, not the 07-30 one
    assert got["ended_at"].startswith("2026-07-28T")


def test_distill_session_marks_driver_launch():
    t = sd.read_transcript(FIXTURES / "driver-session.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    assert sd.distill_session(t, window)["launch"] == "driver"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — `AttributeError: module 'standup_digest' has no attribute 'strip_wrappers'`

- [ ] **Step 4: Write the implementation**

Add to `standup_digest.py`:

```python
PROMPT_CHAR_LIMIT = 1500
TRUNCATION_MARKER = "… [truncated]"

_WRAPPER_RE = re.compile(
    r"<(local-command-caveat|system-reminder|command-name|command-message|command-args)>"
    r".*?</\1>",
    re.DOTALL,
)

_DRIVER_MARKERS = (
    re.compile(r"You are running unattended", re.IGNORECASE),
    re.compile(r"invoked by the .{0,40}driver", re.IGNORECASE),
    re.compile(r"There is no human watching", re.IGNORECASE),
)


def strip_wrappers(text: str) -> str:
    """Remove harness-injected wrapper blocks from a prompt."""
    return _WRAPPER_RE.sub("", text).strip()


def _prompt_text(rec: dict) -> str:
    """Human-authored text from a user record, excluding tool payloads."""
    content = rec.get("message", {}).get("content")
    if isinstance(content, str):
        return strip_wrappers(content)
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return strip_wrappers("\n".join(parts))
    return ""


def extract_prompts(records: list[dict], window: Window) -> tuple[list[str], int]:
    """In-window human prompts, truncated, with dropped chars counted."""
    prompts: list[str] = []
    dropped = 0
    for rec in records:
        if rec.get("type") != "user" or rec.get("isMeta") is True:
            continue
        if not _is_mainline(rec):
            continue
        moment = record_timestamp(rec)
        if moment is None or not (window.since <= moment < window.until):
            continue
        text = _prompt_text(rec)
        if not text:
            continue
        if len(text) > PROMPT_CHAR_LIMIT:
            dropped += len(text) - PROMPT_CHAR_LIMIT
            text = text[:PROMPT_CHAR_LIMIT] + TRUNCATION_MARKER
        prompts.append(text)
    return prompts, dropped


def infer_launch(prompts: list[str]) -> str:
    """Whether Les typed this session's first prompt or the board-driver did."""
    if not prompts:
        return "unknown"
    first = prompts[0]
    if any(marker.search(first) for marker in _DRIVER_MARKERS):
        return "driver"
    return "human"


def project_label(dirname: str) -> str:
    """Decode a ~/.claude/projects directory name to a short project label."""
    path = dirname.replace("-", "/")
    home = str(Path.home())
    for prefix in (f"{home}/devel/", f"{home}/"):
        marker = prefix.replace("-", "/")
        if path.startswith(marker):
            return path[len(marker):]
    return path.lstrip("/")


def _distinct(values) -> list[str]:
    return sorted({v for v in values if v})


def distill_session(transcript: Transcript, window: Window) -> dict:
    """Neutral facts about one session. No editorial judgment."""
    records = transcript.records
    in_window = [
        rec
        for rec in records
        if _is_mainline(rec)
        and (moment := record_timestamp(rec)) is not None
        and window.since <= moment < window.until
    ]
    moments = sorted(m for rec in in_window if (m := record_timestamp(rec)))
    prompts, dropped = extract_prompts(records, window)

    titles = [r.get("aiTitle") for r in records if r.get("type") == "ai-title"]
    session_ids = [r.get("sessionId") for r in records if r.get("sessionId")]

    return {
        "session_id": session_ids[-1] if session_ids else transcript.path.stem,
        "transcript": str(transcript.path),
        "title": titles[-1] if titles else None,
        "project": project_label(transcript.path.parent.name),
        "cwds": _distinct(r.get("cwd") for r in records),
        "branches": _distinct(r.get("gitBranch") for r in records),
        "launch": infer_launch(prompts),
        "started_at": moments[0].astimezone().isoformat() if moments else None,
        "ended_at": moments[-1].astimezone().isoformat() if moments else None,
        "prompt_count": len(prompts),
        "prompt_chars_dropped": dropped,
        "prompts": prompts,
        "refs": [],  # populated in Task 4
    }
```

Note the `project_label` implementation detail: Claude Code encodes `/` as `-`, which is
lossy for paths that legitimately contain `-`. `tabs-project` round-trips as
`tabs/project`. Task 4 does not depend on this being perfect; the renderer treats
`project` as a display label only, and `cwds` carries the authoritative path.

- [ ] **Step 5: Run tests to verify they pass**

Run: `make test`
Expected: FAIL on `test_project_label_decodes_and_shortens` — the naive replace yields `tabs/project/pilo`, not `tabs-project/pilo`.

- [ ] **Step 6: Fix project_label using the real cwd**

The directory name is lossy, so prefer the authoritative `cwd` recorded inside the
transcript and fall back to the decoded name. Replace `project_label` and adjust its call:

```python
def project_label(dirname: str, cwds: list[str] | None = None) -> str:
    """Short project label. Prefers a recorded cwd; the dirname is lossy."""
    home = str(Path.home())
    if cwds:
        base = cwds[0]
        # A worktree lives at <repo>/.worktrees/<name>; report the repo.
        if "/.worktrees/" in base:
            base = base.split("/.worktrees/")[0]
        for prefix in (f"{home}/devel/", f"{home}/"):
            if base.startswith(prefix):
                return base[len(prefix):]
        return base
    return dirname.replace("-", "/").lstrip("/")
```

Update the test to match the real contract, and update the call in `distill_session`:

```python
def test_project_label_prefers_recorded_cwd():
    label = sd.project_label(
        "-Users-lorchard-devel-tabs-project-pilo",
        ["/Users/lorchard/devel/tabs-project/pilo/.worktrees/pet"],
    )
    assert label == "tabs-project/pilo"


def test_project_label_falls_back_to_dirname():
    assert sd.project_label("-Users-lorchard-devel-foo", []) == "Users/lorchard/devel/foo"
```

Delete `test_project_label_decodes_and_shortens`. In `distill_session`, compute `cwds`
first and pass it:

```python
    cwds = _distinct(r.get("cwd") for r in records)
    ...
        "project": project_label(transcript.path.parent.name, cwds),
        "cwds": cwds,
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `make test`
Expected: PASS, 24 passed (23 after Step 2, then −1 deleted and +2 added in Step 6)

- [ ] **Step 8: Commit**

```bash
git add standup-digest/scripts
git commit -m "standup-digest: prompt extraction, launch inference, session distillation"
```

---

### Task 4: Reference extraction and dedup

**Files:**
- Modify: `standup-digest/scripts/standup_digest.py`
- Modify: `standup-digest/scripts/test_standup_digest.py`

**Interfaces:**
- Consumes: `distill_session` from Task 3.
- Produces: `Ref` dataclass (fields `kind: str`, `repo: str | None`, `number: int`, `source: str`, `url: str | None`), `extract_refs(records: list[dict], prompts: list[str], default_repo: str | None) -> list[Ref]`, `dedupe_refs(refs: list[Ref]) -> list[Ref]`, `repo_from_cwd(cwd: str) -> str | None`.

- [ ] **Step 1: Write the failing tests**

Append to `test_standup_digest.py`:

```python
def test_extract_refs_from_pr_link_records():
    records = [
        {
            "type": "pr-link",
            "prNumber": 446,
            "prRepository": "mozilla/pilo",
            "prUrl": "https://github.com/mozilla/pilo/pull/446",
        }
    ]
    refs = sd.extract_refs(records, [], default_repo=None)
    assert len(refs) == 1
    assert refs[0].kind == "pr"
    assert refs[0].number == 446
    assert refs[0].repo == "mozilla/pilo"
    assert refs[0].source == "pr-link"


def test_extract_refs_from_prose_urls():
    prompts = ["look at https://github.com/lmorchard/agent-sessions/issues/4 please"]
    refs = sd.extract_refs([], prompts, default_repo=None)
    assert refs[0].kind == "issue"
    assert refs[0].repo == "lmorchard/agent-sessions"
    assert refs[0].number == 4
    assert refs[0].source == "prose"


def test_extract_refs_from_bare_hash_uses_default_repo():
    refs = sd.extract_refs([], ["close out issue #97"], default_repo="mozilla/pilo")
    assert refs[0].repo == "mozilla/pilo"
    assert refs[0].number == 97
    assert refs[0].kind == "issue"      # bare #N is ambiguous; assume issue
    assert refs[0].source == "prose"


def test_bare_hash_without_default_repo_is_dropped():
    assert sd.extract_refs([], ["close out issue #97"], default_repo=None) == []


def test_dedupe_prefers_pr_link_over_prose():
    refs = [
        sd.Ref(kind="pr", repo="mozilla/pilo", number=446, source="prose", url=None),
        sd.Ref(
            kind="pr", repo="mozilla/pilo", number=446, source="pr-link",
            url="https://github.com/mozilla/pilo/pull/446",
        ),
    ]
    got = sd.dedupe_refs(refs)
    assert len(got) == 1
    assert got[0].source == "pr-link"
    assert got[0].url is not None


def test_dedupe_keeps_distinct_repos_and_kinds():
    refs = [
        sd.Ref(kind="pr", repo="a/b", number=1, source="prose", url=None),
        sd.Ref(kind="issue", repo="a/b", number=1, source="prose", url=None),
        sd.Ref(kind="pr", repo="c/d", number=1, source="prose", url=None),
    ]
    assert len(sd.dedupe_refs(refs)) == 3


def test_version_numbers_are_not_mistaken_for_refs():
    refs = sd.extract_refs([], ["bump to v2.1.220 and #  spaced"], default_repo="a/b")
    assert refs == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — `AttributeError: module 'standup_digest' has no attribute 'extract_refs'`

- [ ] **Step 3: Write the implementation**

Add to `standup_digest.py`:

```python
import subprocess

_GH_URL_RE = re.compile(
    r"https?://github\.com/([\w.-]+/[\w.-]+)/(pull|issues)/(\d+)"
)


def _run(cmd: list[str], timeout: int = 20) -> str | None:
    """Run a command, returning stdout, or None on any failure."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout
_BARE_REF_RE = re.compile(r"(?<![\w/#])#(\d+)\b")


@dataclass(frozen=True)
class Ref:
    kind: str            # "pr" | "issue"
    repo: str | None
    number: int
    source: str          # "pr-link" | "prose"
    url: str | None


def repo_from_cwd(cwd: str) -> str | None:
    """owner/name for a checkout's origin remote, or None."""
    out = _run(["git", "-C", cwd, "remote", "get-url", "origin"])
    if out is None:
        return None
    match = re.search(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?$", out.strip())
    return match.group(1) if match else None


def extract_refs(
    records: list[dict], prompts: list[str], default_repo: str | None
) -> list[Ref]:
    refs: list[Ref] = []

    for rec in records:
        if rec.get("type") != "pr-link":
            continue
        number = rec.get("prNumber")
        if not isinstance(number, int):
            continue
        refs.append(
            Ref(
                kind="pr",
                repo=rec.get("prRepository"),
                number=number,
                source="pr-link",
                url=rec.get("prUrl"),
            )
        )

    for text in prompts:
        for repo, kind_word, number in _GH_URL_RE.findall(text):
            refs.append(
                Ref(
                    kind="pr" if kind_word == "pull" else "issue",
                    repo=repo,
                    number=int(number),
                    source="prose",
                    url=f"https://github.com/{repo}/{kind_word}/{number}",
                )
            )
        if default_repo:
            for number in _BARE_REF_RE.findall(text):
                refs.append(
                    Ref(
                        kind="issue",
                        repo=default_repo,
                        number=int(number),
                        source="prose",
                        url=None,
                    )
                )

    return dedupe_refs(refs)


def dedupe_refs(refs: list[Ref]) -> list[Ref]:
    """One ref per (repo, kind, number). pr-link beats prose."""
    best: dict[tuple, Ref] = {}
    for ref in refs:
        key = (ref.repo, ref.kind, ref.number)
        current = best.get(key)
        if current is None or (
            current.source == "prose" and ref.source == "pr-link"
        ):
            best[key] = ref
    return sorted(best.values(), key=lambda r: (r.repo or "", r.kind, r.number))
```

`_run` is the single seam every `git`/`gh` call goes through. Tests monkeypatch it rather
than the subprocess module, which is why it is a module-level function and not a method.

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test`
Expected: PASS, 31 passed

- [ ] **Step 5: Wire refs into distill_session**

In `distill_session`, replace the `"refs": []` placeholder:

```python
    default_repo = repo_from_cwd(cwds[0]) if cwds else None
    refs = extract_refs(records, prompts, default_repo)
    ...
        "refs": [vars(r) for r in refs],
```

- [ ] **Step 6: Add a test for the wiring**

```python
def test_distill_session_includes_pr_link_ref():
    t = sd.read_transcript(FIXTURES / "sample-session.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    refs = sd.distill_session(t, window)["refs"]
    assert any(r["number"] == 446 and r["source"] == "pr-link" for r in refs)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `make test`
Expected: PASS, 32 passed

- [ ] **Step 8: Commit**

```bash
git add standup-digest/scripts
git commit -m "standup-digest: PR and issue reference extraction with dedup"
```

---

### Task 5: Verification seam — git and gh

**Files:**
- Modify: `standup-digest/scripts/standup_digest.py`
- Modify: `standup-digest/scripts/test_standup_digest.py`

**Interfaces:**
- Consumes: `Ref`, `Window`, `_run`, `repo_from_cwd` from Task 4.
- Produces: `NullVerifier`, `GhVerifier`, both exposing `verify_ref(ref: Ref) -> dict` and `commits(cwd: str, window: Window) -> list[dict]` and carrying `warnings: list[str]` and `gh_calls: int` attributes.

`verify_ref` returns a dict merged onto the serialized ref: `{"verification": "confirmed"|"unavailable", "state": str|None, "title": str|None, "url": str|None, "merged_at": str|None, "closed_at": str|None}`.

- [ ] **Step 1: Write the failing tests**

Append to `test_standup_digest.py`:

```python
def test_null_verifier_marks_everything_unavailable():
    v = sd.NullVerifier()
    ref = sd.Ref(kind="pr", repo="a/b", number=1, source="prose", url=None)
    got = v.verify_ref(ref)
    assert got["verification"] == "unavailable"
    assert got["state"] is None
    assert v.commits("/tmp", None) == []


def test_gh_verifier_confirms_merged_pr(monkeypatch):
    payload = {
        "state": "MERGED",
        "title": "feat(core): page exploration tools",
        "url": "https://github.com/mozilla/pilo/pull/446",
        "mergedAt": "2026-07-28T18:22:11Z",
        "closedAt": "2026-07-28T18:22:11Z",
    }
    monkeypatch.setattr(sd, "_run", lambda cmd, timeout=20: json.dumps(payload))
    v = sd.GhVerifier()
    ref = sd.Ref(kind="pr", repo="mozilla/pilo", number=446, source="pr-link", url=None)
    got = v.verify_ref(ref)

    assert got["verification"] == "confirmed"
    assert got["state"] == "MERGED"
    assert got["merged_at"] == "2026-07-28T18:22:11Z"
    assert v.warnings == []


def test_gh_verifier_degrades_to_unavailable(monkeypatch):
    monkeypatch.setattr(sd, "_run", lambda cmd, timeout=20: None)
    v = sd.GhVerifier()
    ref = sd.Ref(kind="pr", repo="mozilla/pilo", number=446, source="pr-link", url=None)
    got = v.verify_ref(ref)

    assert got["verification"] == "unavailable"
    assert got["state"] is None
    assert len(v.warnings) == 1
    assert "mozilla/pilo#446" in v.warnings[0]


def test_gh_verifier_skips_refs_without_a_repo():
    v = sd.GhVerifier()
    ref = sd.Ref(kind="pr", repo=None, number=1, source="prose", url=None)
    assert v.verify_ref(ref)["verification"] == "unavailable"


def test_gh_verifier_caches_repeat_lookups(monkeypatch):
    calls = []

    def fake_run(cmd, timeout=20):
        calls.append(cmd)
        return json.dumps({"state": "OPEN", "title": "t", "url": "u"})

    monkeypatch.setattr(sd, "_run", fake_run)
    v = sd.GhVerifier()
    ref = sd.Ref(kind="pr", repo="a/b", number=1, source="prose", url=None)
    v.verify_ref(ref)
    v.verify_ref(ref)
    assert len(calls) == 1
    assert v.gh_calls == 1      # surfaced as stats.gh_calls in the digest


def test_commits_parses_git_log(monkeypatch):
    log = (
        "abc1234\x1ffix(core): guard SPA snapshot\x1f2026-07-28T14:02:11-04:00\n"
        "def5678\x1fchore: bump deps\x1f2026-07-28T15:10:00-04:00"
    )

    def fake_run(cmd, timeout=20):
        if cmd[:2] == ["git", "-C"] and "rev-parse" in cmd:
            return "/Users/lorchard/devel/tabs-project/pilo/.git"
        if "log" in cmd:
            return log
        if "remote" in cmd:
            return "git@github.com:mozilla/pilo.git"
        if "config" in cmd:
            return "lorchard@mozilla.com"
        return None

    monkeypatch.setattr(sd, "_run", fake_run)
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    got = sd.GhVerifier().commits("/Users/lorchard/devel/tabs-project/pilo", window)

    assert len(got) == 2
    assert got[0]["sha"] == "abc1234"
    assert got[0]["subject"] == "fix(core): guard SPA snapshot"
    assert got[0]["repo"] == "mozilla/pilo"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — `AttributeError: module 'standup_digest' has no attribute 'NullVerifier'`

- [ ] **Step 3: Add the verifiers**

`_run` already exists from Task 4. Add below it:

```python
GIT_LOG_SEP = "\x1f"

_UNVERIFIED = {
    "verification": "unavailable",
    "state": None,
    "title": None,
    "merged_at": None,
    "closed_at": None,
}


class NullVerifier:
    """Used by --no-verify and by tests. Touches nothing."""

    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.gh_calls = 0

    def verify_ref(self, ref: Ref) -> dict:
        return dict(_UNVERIFIED)

    def commits(self, cwd: str, window) -> list[dict]:
        return []


class GhVerifier:
    """Checks claims against real git and gh state."""

    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.gh_calls = 0
        self._ref_cache: dict[tuple, dict] = {}
        self._email: str | None = None

    def verify_ref(self, ref: Ref) -> dict:
        if not ref.repo:
            return dict(_UNVERIFIED)

        key = (ref.repo, ref.kind, ref.number)
        if key in self._ref_cache:
            return dict(self._ref_cache[key])

        noun = "pr" if ref.kind == "pr" else "issue"
        self.gh_calls += 1
        raw = _run(
            [
                "gh", noun, "view", str(ref.number),
                "--repo", ref.repo,
                "--json", "state,title,url,mergedAt,closedAt",
            ]
        )
        if raw is None:
            self.warnings.append(
                f"gh unavailable for {ref.repo}#{ref.number}; reported as unverified"
            )
            result = dict(_UNVERIFIED)
        else:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                self.warnings.append(f"gh returned unparseable JSON for {ref.repo}#{ref.number}")
                result = dict(_UNVERIFIED)
            else:
                result = {
                    "verification": "confirmed",
                    "state": data.get("state"),
                    "title": data.get("title"),
                    "merged_at": data.get("mergedAt"),
                    "closed_at": data.get("closedAt"),
                }
                if data.get("url"):
                    result["url"] = data["url"]

        self._ref_cache[key] = result
        return dict(result)

    def _author_email(self) -> str | None:
        if self._email is None:
            out = _run(["git", "config", "user.email"])
            self._email = out.strip() if out else ""
        return self._email or None

    def commits(self, cwd: str, window) -> list[dict]:
        """Les's commits in `cwd`'s repository inside the window."""
        common = _run(
            ["git", "-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"]
        )
        if common is None:
            self.warnings.append(f"not a git repository, commits skipped: {cwd}")
            return []
        repo_root = str(Path(common.strip()).parent)

        email = self._author_email()
        if not email:
            self.warnings.append("git user.email unset; commit authorship not filtered")

        cmd = [
            "git", "-C", repo_root, "log",
            f"--since={window.since.isoformat()}",
            f"--until={window.until.isoformat()}",
            f"--pretty=format:%h{GIT_LOG_SEP}%s{GIT_LOG_SEP}%cI",
            "--all", "--no-merges",
        ]
        if email:
            cmd.append(f"--author={email}")

        out = _run(cmd)
        if not out:
            return []

        repo = repo_from_cwd(repo_root)
        commits = []
        for line in out.strip().splitlines():
            parts = line.split(GIT_LOG_SEP)
            if len(parts) != 3:
                continue
            sha, subject, committed = parts
            commits.append(
                {
                    "repo": repo,
                    "path": repo_root,
                    "sha": sha,
                    "subject": subject,
                    "committed_at": committed,
                }
            )
        return commits
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test`
Expected: PASS, 38 passed

- [ ] **Step 5: Commit**

```bash
git add standup-digest/scripts
git commit -m "standup-digest: git and gh verification behind a testable seam"
```

---

### Task 6: Digest assembly, CLI, end-to-end

**Files:**
- Modify: `standup-digest/scripts/standup_digest.py`
- Modify: `standup-digest/scripts/test_standup_digest.py`

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces: `SCHEMA_VERSION = 1`, `build_digest(root: Path, window: Window, verifier) -> dict`, `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write the failing tests**

Append to `test_standup_digest.py`:

```python
def test_build_digest_over_fixtures_no_verify():
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    digest = sd.build_digest(FIXTURES.parent, window, sd.NullVerifier())

    assert digest["schema_version"] == sd.SCHEMA_VERSION
    assert digest["window"]["rule"] == "explicit"
    assert digest["stats"]["malformed_lines"] == 1
    assert digest["stats"]["gh_calls"] == 0      # --no-verify makes no calls
    assert isinstance(digest["warnings"], list)
    assert isinstance(digest["commits"], list)


def test_build_digest_applies_verification_to_refs(monkeypatch):
    payload = {"state": "MERGED", "title": "t", "url": "u", "mergedAt": "2026-07-28T18:22:11Z"}
    monkeypatch.setattr(sd, "_run", lambda cmd, timeout=20: json.dumps(payload))
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    digest = sd.build_digest(FIXTURES.parent, window, sd.GhVerifier())

    refs = [r for s in digest["sessions"] for r in s["refs"]]
    assert refs, "fixture should yield at least one ref"
    assert all(r["verification"] == "confirmed" for r in refs)
    assert any(r["state"] == "MERGED" for r in refs)


def test_empty_window_yields_valid_digest():
    window = sd.resolve_window(local(2026, 7, 29), date="1999-01-01")
    digest = sd.build_digest(FIXTURES.parent, window, sd.NullVerifier())
    assert digest["sessions"] == []
    assert digest["stats"]["sessions"] == 0


def test_main_writes_json_to_out(tmp_path, monkeypatch):
    out = tmp_path / "digest.json"
    monkeypatch.setattr(sd, "_run", lambda cmd, timeout=20: None)
    code = sd.main(
        [
            "--date", "2026-07-28",
            "--no-verify",
            "--root", str(FIXTURES.parent),
            "--out", str(out),
        ]
    )
    assert code == 0
    loaded = json.loads(out.read_text())
    assert loaded["schema_version"] == sd.SCHEMA_VERSION


def test_main_rejects_conflicting_window_flags(capsys):
    code = sd.main(["--date", "2026-07-28", "--since", "2026-07-01", "--no-verify"])
    assert code == 2


def test_main_reports_unwritable_out(tmp_path):
    bad = tmp_path / "missing-dir" / "digest.json"
    code = sd.main(["--no-verify", "--root", str(FIXTURES.parent), "--out", str(bad)])
    assert code == 1
```

The fixtures live in `scripts/fixtures/`, so `FIXTURES.parent` is `scripts/`, and
`discover_transcripts` globs `*/*.jsonl` beneath it — which finds `fixtures/*.jsonl`.
That is deliberate: it makes `scripts/` stand in for `~/.claude/projects/` with
`fixtures/` as the single project directory.

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — `AttributeError: module 'standup_digest' has no attribute 'build_digest'`

- [ ] **Step 3: Write the implementation**

Add to `standup_digest.py`:

```python
import argparse
import sys

SCHEMA_VERSION = 1
DEFAULT_ROOT = Path.home() / ".claude" / "projects"


def build_digest(root: Path, window: Window, verifier) -> dict:
    sessions: list[dict] = []
    malformed = 0
    dropped = 0
    warnings: list[str] = []

    for path in discover_transcripts(root):
        try:
            transcript = read_transcript(path)
        except OSError as err:
            warnings.append(f"unreadable transcript {path}: {err}")
            continue

        malformed += transcript.malformed
        if not touches_window(transcript.records, window):
            continue

        session = distill_session(transcript, window)
        dropped += session["prompt_chars_dropped"]

        for ref in session["refs"]:
            ref.update(
                verifier.verify_ref(
                    Ref(
                        kind=ref["kind"], repo=ref["repo"], number=ref["number"],
                        source=ref["source"], url=ref["url"],
                    )
                )
            )
        sessions.append(session)

    commits: list[dict] = []
    seen_paths: set[str] = set()
    seen_shas: set[str] = set()
    for session in sessions:
        for cwd in session["cwds"]:
            if cwd in seen_paths:
                continue
            seen_paths.add(cwd)
            for commit in verifier.commits(cwd, window):
                if commit["sha"] in seen_shas:
                    continue
                seen_shas.add(commit["sha"])
                commits.append(commit)

    warnings.extend(verifier.warnings)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(),
        "window": {
            "since": window.since.isoformat(),
            "until": window.until.isoformat(),
            "rule": window.rule,
        },
        "stats": {
            "sessions": len(sessions),
            "projects": len({s["project"] for s in sessions}),
            "malformed_lines": malformed,
            "prompt_chars_dropped": dropped,
            "gh_calls": verifier.gh_calls,
        },
        "warnings": warnings,
        "sessions": sessions,
        "commits": commits,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit a structured digest of recent Claude Code sessions."
    )
    parser.add_argument("--date", help="a single calendar day, YYYY-MM-DD")
    parser.add_argument("--since", help="window start, YYYY-MM-DD")
    parser.add_argument("--until", help="window end (exclusive), YYYY-MM-DD")
    parser.add_argument("--no-verify", action="store_true", help="skip git and gh")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="projects directory")
    parser.add_argument("--out", help="write JSON here instead of stdout")
    args = parser.parse_args(argv)

    try:
        window = resolve_window(
            datetime.now().astimezone(), args.date, args.since, args.until
        )
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    verifier = NullVerifier() if args.no_verify else GhVerifier()
    digest = build_digest(Path(args.root), window, verifier)
    payload = json.dumps(digest, indent=2, ensure_ascii=False)

    if args.out:
        try:
            Path(args.out).write_text(payload, encoding="utf-8")
        except OSError as err:
            print(f"error: cannot write {args.out}: {err}", file=sys.stderr)
            return 1
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test`
Expected: PASS, 44 passed

- [ ] **Step 5: Verify against real data**

The fixtures are synthetic, so confirm the extractor survives real transcripts:

```bash
python3 standup-digest/scripts/standup_digest.py --date 2026-07-28 --no-verify \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["stats"]); [print("-", s["title"], "|", s["launch"], "|", s["project"]) for s in d["sessions"]]'
```

Expected: 7 sessions across 3 projects, titles including "Evaluate and refresh stale
PR 446" and "Tackle GitHub issue 101". If the count or titles disagree with the spec's
recorded observations, stop and investigate before continuing — a silent mismatch here
means the filters are wrong.

- [ ] **Step 6: Verify the verification path against real data**

```bash
python3 standup-digest/scripts/standup_digest.py --date 2026-07-28 \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print("warnings:", d["warnings"]); [print(r["repo"], r["number"], r["verification"], r["state"]) for s in d["sessions"] for r in s["refs"]]'
```

Expected: refs reported `confirmed` with real states when `gh` is authenticated;
`unavailable` with a warning otherwise. Either outcome is a pass — a silent absence of
both is not.

- [ ] **Step 7: Commit**

```bash
git add standup-digest/scripts
git commit -m "standup-digest: digest assembly and CLI"
```

---

### Task 7: The renderer — SKILL.md, README, plugin registration

**Files:**
- Create: `standup-digest/SKILL.md`
- Create: `standup-digest/README.md`
- Modify: `.claude-plugin/plugin.json`
- Modify: `Makefile` (repo root)

**Interfaces:**
- Consumes: the digest JSON contract from Task 6.
- Produces: the user-facing skill.

- [ ] **Step 1: Write SKILL.md**

Create `standup-digest/SKILL.md`:

````markdown
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
Workspace. This one covers the work itself.

## Run the extractor

```bash
python3 ~/devel/lmorchard-agent-skills/standup-digest/scripts/standup_digest.py
```

Defaults to the previous workday through today, so a Monday run sweeps Friday through
Sunday. Add `--date YYYY-MM-DD` for one specific day, or `--since`/`--until` for a range.
Add `--no-verify` when offline.

The script writes JSON to stdout. Read it and compose from it; do not re-read the raw
transcripts yourself.

## Language rules

The digest separates what is true from what is interesting. You choose what is
interesting. You do **not** get to upgrade what is true.

| Digest state | Permitted phrasing |
|---|---|
| `verification: confirmed` + state `MERGED` or `CLOSED` | landed, merged, shipped, closed |
| `verification: confirmed` + state `OPEN` | opened, in flight, up for review |
| `verification: unavailable` | worked on, looked at |

Further binding rules:

- Anything absent from the digest never appears as an accomplishment.
- Sessions with `launch: "driver"` were kicked off or delegated, not hand-worked. Say so.
- Sessions with `launch: "unknown"` get neutral phrasing; do not guess.
- When `warnings` is non-empty, add one short line saying the run was degraded. A
  partial digest must never read as a clean one.
- `refs` with `source: "prose"` are the looser signal — Les may have only mentioned them.
  Weight them below `pr-link` refs and below commits.

## Output

**To the terminal**, three or four bullets ordered by significance, not chronology:

```
## Tue Jul 28

- Refreshed + landed stale PR #446 (pilo)
- Cleared 3 evals-judge issues (#97/100/101)
- Zoo eval sandbox stood up, CDP flakiness still blocking clean runs

_full digest: ~/.claude/standup/2026-07-28.md_
```

**To `~/.claude/standup/YYYY-MM-DD.md`** (create the directory if needed), the full
detail: one section per project, sessions underneath with title, branches, refs with
their verified state, commits, and a one-line gloss of intent drawn from the prompts.
Name the file for the window's start date.

## When the day was quiet

If `stats.sessions` is 0, say the window held no recorded sessions. Do not fill an empty
template, and do not pad with anything from the warnings.
````

- [ ] **Step 2: Write README.md**

Create `standup-digest/README.md`:

```markdown
# standup-digest

Surveys Claude Code transcripts in `~/.claude/projects` and reports what you actually did.

## Why

Claude Code records everything, but the record is unreadable: a single day can hold 19 MB
of JSONL across a dozen sessions, most of it tool payloads and subagent chatter. The
scarce thing at standup is not information. It is three or four honest sentences.

## How it works

Two layers with a hard boundary:

- `scripts/standup_digest.py` — a stdlib-only extractor. Discovers transcripts, filters to
  a time window, distills the human prompts, and verifies every PR, issue, and commit
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
make standup                                   # previous workday, verified
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
```

- [ ] **Step 3: Register the skill**

In `.claude-plugin/plugin.json`, add `"./standup-digest"` to the `skills` array:

```json
      "skills": [
        "./go-cli-builder",
        "./weeknotes-composer",
        "./daily-blog-post-composer",
        "./dev-session",
        "./send-notification",
        "./journal-note",
        "./television-companion",
        "./standup-digest"
      ]
```

- [ ] **Step 4: Verify the JSON stays valid**

Run: `python3 -c "import json; d=json.load(open('.claude-plugin/plugin.json')); print(d['plugins'][0]['skills'])"`
Expected: the list prints with `./standup-digest` last.

- [ ] **Step 5: Run the full suite**

Run: `make test`
Expected: PASS, 44 passed

- [ ] **Step 6: Commit**

```bash
git add standup-digest .claude-plugin/plugin.json Makefile
git commit -m "standup-digest: renderer skill, docs, and plugin registration"
```

---

### Task 8: End-to-end rehearsal

**Files:**
- Create: `standup-digest/docs/dev-sessions/2026-07-29-0916-initial-design/notes.md`

**Interfaces:**
- Consumes: the finished skill.
- Produces: session notes.

- [ ] **Step 1: Run the real thing**

Invoke the skill as Les would — ask for yesterday's standup — and confirm the output
obeys every language rule in `SKILL.md`. Specifically check:

- No `unavailable` ref is described with shipped/landed/merged phrasing.
- Driver-launched sessions are described as kicked off, not hand-worked.
- The detail file exists at `~/.claude/standup/YYYY-MM-DD.md`.
- Warnings, if any, appear in the headline.

- [ ] **Step 2: Write notes.md**

Record what worked, what surprised you about the real transcript shape, and anything the
spec got wrong. Include the actual first-run output verbatim.

- [ ] **Step 3: Commit**

```bash
git add standup-digest/docs
git commit -m "standup-digest: session notes"
```

---

## Deferred

Named here so they are not silently dropped. Each is easy against the JSON contract:

- Cron scheduling for an unattended morning run.
- Writing into the Obsidian journal via `journal-note`.
- Multi-day and weekly rollups for `weeknotes-composer`.
- Assistant-prose distillation. The current digest reads only human prompts, which
  carry intent but not outcome; outcomes come from `git`/`gh` instead. If the reports
  turn out thin, this is the first lever to pull.
