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
