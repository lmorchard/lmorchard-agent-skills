"""Pins the macOS persona the recorded fixtures were captured under.

The fixture transcripts record cwds like `/Users/lorchard/devel/tabs-project/pilo`,
and the digest consults the real filesystem in two places: `commits` skips a cwd
that no longer exists, and `project_label` shortens a path by stripping the home
prefix. Both make the result depend on the machine running the suite, so several
tests only ever passed on the laptop that captured the fixtures.

Rather than rewrite every fixture, pin the persona: `HOME` is that laptop's home,
and any path under it reports as existing. Everything else still hits the real
filesystem, so `tmp_path` and the scripts directory behave normally.
"""

from pathlib import Path

import pytest

PERSONA_HOME = "/Users/lorchard"

_real_exists = Path.exists


@pytest.fixture(autouse=True)
def persona(monkeypatch):
    monkeypatch.setenv("HOME", PERSONA_HOME)
    monkeypatch.setattr(
        Path,
        "exists",
        lambda self: str(self).startswith(PERSONA_HOME) or _real_exists(self),
    )
