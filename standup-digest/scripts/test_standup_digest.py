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
