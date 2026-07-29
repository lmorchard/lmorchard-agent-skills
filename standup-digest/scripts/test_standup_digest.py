import os
import time

os.environ["TZ"] = "UTC"
time.tzset()

from datetime import datetime, timedelta
from pathlib import Path

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


def test_discover_transcripts_filters_by_depth_and_uuid(tmp_path):
    # Valid UUID transcript one level deep: should be found
    valid_uuid = "11111111-2222-3333-4444-555555555555"
    (tmp_path / "project1" / f"{valid_uuid}.jsonl").parent.mkdir(exist_ok=True)
    (tmp_path / "project1" / f"{valid_uuid}.jsonl").touch()

    # Non-UUID filename: should be excluded
    (tmp_path / "project2").mkdir(exist_ok=True)
    (tmp_path / "project2" / "notes.jsonl").touch()

    # Nested subagents path: should be excluded
    (tmp_path / "project3" / "subagents").mkdir(parents=True, exist_ok=True)
    (tmp_path / "project3" / "subagents" / f"{valid_uuid}.jsonl").touch()

    # Two levels deep (not one): should be excluded by glob
    (tmp_path / "deep" / "nested" / "more").mkdir(parents=True, exist_ok=True)
    (tmp_path / "deep" / "nested" / "more" / f"{valid_uuid}.jsonl").touch()

    found = sd.discover_transcripts(tmp_path)
    assert len(found) == 1
    assert found[0].name == f"{valid_uuid}.jsonl"
    assert found[0].parent.name == "project1"


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
    assert "LEAKED_TOOL_PAYLOAD" not in joined   # tool_result block's own "text" key
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


def test_project_label_prefers_recorded_cwd():
    label = sd.project_label(
        "-Users-lorchard-devel-tabs-project-pilo",
        ["/Users/lorchard/devel/tabs-project/pilo/.worktrees/pet"],
    )
    assert label == "tabs-project/pilo"


def test_project_label_falls_back_to_dirname():
    assert sd.project_label("-Users-lorchard-devel-foo", []) == "Users/lorchard/devel/foo"


def test_distill_session_collects_metadata():
    t = sd.read_transcript(FIXTURES / "sample-session.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    got = sd.distill_session(t, window)

    assert got["title"] == "Evaluate and refresh stale PR 446"
    assert got["session_id"] == "11111111-2222-3333-4444-555555555555"
    assert got["launch"] == "human"
    assert got["prompt_count"] == 2
    assert got["branches"] == ["main", "feat/pet"]
    assert got["started_at"].startswith("2026-07-28T")
    # ended_at must be the last in-window record, not the 07-30 one
    assert got["ended_at"].startswith("2026-07-28T")


def test_distill_session_marks_driver_launch():
    t = sd.read_transcript(FIXTURES / "driver-session.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    assert sd.distill_session(t, window)["launch"] == "driver"


def test_distill_session_attributes_launch_from_whole_transcript():
    # The driver preamble lands the day before the report window (this session
    # spans multiple days). Launch attribution must look at the whole
    # transcript, not just the window being reported on, or a later window
    # would misattribute a driver-launched session as human-launched.
    session_id = "22222222-3333-4444-5555-666666666666"
    records = [
        {
            "type": "user",
            "isSidechain": False,
            "timestamp": "2026-07-27T09:00:00.000Z",
            "sessionId": session_id,
            "message": {
                "role": "user",
                "content": "You are running unattended, invoked by the board-driver.",
            },
        },
        {
            "type": "user",
            "isSidechain": False,
            "timestamp": "2026-07-28T14:00:00.000Z",
            "sessionId": session_id,
            "message": {"role": "user", "content": "continue the work"},
        },
    ]
    t = sd.Transcript(path=Path(f"/tmp/{session_id}.jsonl"), records=records, malformed=0)
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    got = sd.distill_session(t, window)

    assert got["launch"] == "driver"
    assert got["prompt_count"] == 1  # the windowed prompt list is unaffected


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


def test_repo_from_cwd_parses_ssh_remote(monkeypatch):
    monkeypatch.setattr(
        sd, "_run", lambda cmd, timeout=20: "git@github.com:mozilla/pilo.git\n"
    )
    assert sd.repo_from_cwd("/anywhere") == "mozilla/pilo"


def test_repo_from_cwd_parses_https_remote_with_git_suffix(monkeypatch):
    monkeypatch.setattr(
        sd, "_run", lambda cmd, timeout=20: "https://github.com/mozilla/pilo.git"
    )
    assert sd.repo_from_cwd("/anywhere") == "mozilla/pilo"


def test_repo_from_cwd_parses_https_remote_without_git_suffix(monkeypatch):
    monkeypatch.setattr(
        sd, "_run", lambda cmd, timeout=20: "https://github.com/mozilla/pilo\n"
    )
    assert sd.repo_from_cwd("/anywhere") == "mozilla/pilo"


def test_repo_from_cwd_returns_none_for_non_github_remote(monkeypatch):
    monkeypatch.setattr(
        sd, "_run", lambda cmd, timeout=20: "git@gitlab.com:foo/bar.git\n"
    )
    assert sd.repo_from_cwd("/anywhere") is None


def test_repo_from_cwd_returns_none_when_run_fails(monkeypatch):
    monkeypatch.setattr(sd, "_run", lambda cmd, timeout=20: None)
    assert sd.repo_from_cwd("/anywhere") is None


def test_distill_session_includes_pr_link_ref_and_drops_ambiguous_bare_hash(
    monkeypatch,
):
    # No resolvable origin remote: default_repo is None, so the fixture's
    # bare "#97" prose reference is ambiguous and must be dropped, while the
    # pr-link record (which carries its own repo) survives.
    monkeypatch.setattr(sd, "_run", lambda cmd, timeout=20: None)
    t = sd.read_transcript(FIXTURES / "sample-session.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    refs = sd.distill_session(t, window)["refs"]
    assert any(r["number"] == 446 and r["source"] == "pr-link" for r in refs)
    assert not any(r["number"] == 97 for r in refs)


def test_distill_session_attaches_bare_hash_to_resolved_repo(monkeypatch):
    # With an origin remote resolvable, the bare "#97" is no longer
    # ambiguous and is attached to that repo as an issue.
    monkeypatch.setattr(
        sd, "_run", lambda cmd, timeout=20: "git@github.com:mozilla/pilo.git\n"
    )
    t = sd.read_transcript(FIXTURES / "sample-session.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    refs = sd.distill_session(t, window)["refs"]
    assert any(
        r["number"] == 97 and r["kind"] == "issue"
        and r["repo"] == "mozilla/pilo" and r["source"] == "prose"
        for r in refs
    )
