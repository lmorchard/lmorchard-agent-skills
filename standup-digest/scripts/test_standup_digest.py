import json
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


def rev_parse(git_dir, toplevel=None):
    """Fake two-line `rev-parse --git-common-dir --show-toplevel` output.

    `toplevel` defaults to the git dir's parent -- a plain checkout, where the
    two coincide. Pass it explicitly to fake a linked worktree, whose common
    dir belongs to the main checkout while its toplevel is its own.
    """
    top = toplevel if toplevel is not None else str(Path(git_dir).parent)
    return f"{git_dir}\n{top}"


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
    w = sd.resolve_window(local(2026, 7, 29), since="2026-07-01", until="2026-07-05")
    assert w.since == local(2026, 7, 1)
    assert w.until == local(2026, 7, 5)
    assert w.rule == "explicit"


def test_date_combined_with_since_is_rejected():
    with pytest.raises(ValueError):
        sd.resolve_window(local(2026, 7, 29), date="2026-07-20", since="2026-07-01")


def test_dst_transitions_do_not_shift_window_boundaries():
    # Adding/subtracting whole days on an aware datetime keeps the old UTC
    # offset unless re-truncated to local midnight, silently dropping or
    # duplicating an hour across a DST transition. Verified against
    # America/New_York, where DST ends 2026-11-01 and begins 2026-03-08.
    old_tz = os.environ.get("TZ")
    os.environ["TZ"] = "America/New_York"
    time.tzset()
    try:
        # --date 2026-11-01 (the fall-back day) must cover the full local
        # day, not end an hour early at 23:00 on the 1st.
        w = sd.resolve_window(local(2026, 11, 1, 9, 16), date="2026-11-01")
        assert w.since == local(2026, 11, 1)
        assert w.until == local(2026, 11, 2)

        # Monday 2026-03-09 (after the spring-forward on the 8th) sweeps
        # back to Friday's local midnight, not an hour into Thursday.
        w2 = sd.resolve_window(local(2026, 3, 9, 9, 16))
        assert w2.since == local(2026, 3, 6)
        assert w2.until == local(2026, 3, 9)
    finally:
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz
        time.tzset()


HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"


def test_uuid_filenames_are_transcripts():
    assert sd.is_session_transcript(
        Path("/p/11111111-2222-3333-4444-555555555555.jsonl")
    )
    assert not sd.is_session_transcript(Path("/p/notes.jsonl"))
    assert not sd.is_session_transcript(Path("/p/11111111-2222.jsonl"))


def test_subagent_paths_are_excluded():
    p = Path("/p/abc/subagents/11111111-2222-3333-4444-555555555555.jsonl")
    assert not sd.is_session_transcript(p)


def test_read_transcript_counts_malformed_lines():
    t = sd.read_transcript(FIXTURES / "11111111-2222-3333-4444-555555555555.jsonl")
    assert t.malformed == 1  # the deliberate truncated final line
    assert len(t.records) == 10


def test_record_timestamp_parses_utc_z():
    rec = {"timestamp": "2026-07-28T14:00:00.000Z"}
    got = sd.record_timestamp(rec)
    assert got is not None
    assert got.year == 2026 and got.hour == 14


def test_record_timestamp_missing_returns_none():
    assert sd.record_timestamp({"type": "mode"}) is None


def test_record_timestamp_naive_is_treated_as_missing():
    # datetime.fromisoformat happily parses a timestamp with no offset/zone
    # into a naive datetime, which then can't be compared against the
    # window's aware bounds -- must be treated as absent, not raise.
    rec = {"timestamp": "2026-07-28 14:00:00"}
    assert sd.record_timestamp(rec) is None


def test_naive_timestamp_record_is_skipped_not_crashed():
    # A single naive timestamp mixed into an otherwise-normal session must
    # not abort the whole run with a TypeError; it's simply excluded, as if
    # it had no timestamp at all.
    session_id = "33333333-4444-5555-6666-777777777777"
    records = [
        {
            "type": "user",
            "isSidechain": False,
            "timestamp": "2026-07-28 14:00:00",  # naive
            "sessionId": session_id,
            "message": {"role": "user", "content": "naive timestamp prompt"},
        },
        {
            "type": "user",
            "isSidechain": False,
            "timestamp": "2026-07-28T15:00:00.000Z",
            "sessionId": session_id,
            "message": {"role": "user", "content": "valid prompt"},
        },
    ]
    t = sd.Transcript(
        path=Path(f"/tmp/{session_id}.jsonl"), records=records, malformed=0
    )
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")

    got = sd.distill_session(t, window, sd.NullVerifier())  # must not raise

    assert got["prompt_count"] == 1
    assert got["prompts"] == ["valid prompt"]


def test_touches_window_ignores_sidechain_records():
    window = sd.Window(local(2026, 7, 30, 8), local(2026, 7, 30, 10), "explicit")
    only_sidechain = [
        {"isSidechain": True, "timestamp": "2026-07-30T09:00:00.000Z"},
    ]
    assert not sd.touches_window(only_sidechain, window)


def test_touches_window_matches_in_window_record():
    t = sd.read_transcript(FIXTURES / "11111111-2222-3333-4444-555555555555.jsonl")
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
        "<task-notification><status>completed</status></task-notification>"
        "<local-command-stdout>ok</local-command-stdout>"
        "real content"
    )
    assert sd.strip_wrappers(text) == "real content"


def test_task_notification_record_yields_no_prompt():
    # A record whose content is purely a harness-injected task-notification
    # (e.g. "Background command ... completed") is a machine's completion
    # claim, not a human prompt. It must strip to empty and be dropped
    # entirely -- not counted in prompt_count -- rather than leaking an
    # unverified "completed" claim into the one channel with no
    # verification gate.
    records = [
        {
            "type": "user",
            "isSidechain": False,
            "timestamp": "2026-07-28T14:00:00.000Z",
            "message": {
                "role": "user",
                "content": (
                    "<task-notification><status>completed</status>"
                    '<summary>Background command "foo" completed</summary>'
                    "</task-notification>"
                ),
            },
        }
    ]
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")

    prompts, dropped = sd.extract_prompts(records, window)

    assert prompts == []
    assert dropped == 0


def test_extract_prompts_keeps_only_human_mainline_text():
    t = sd.read_transcript(FIXTURES / "11111111-2222-3333-4444-555555555555.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    prompts, dropped = sd.extract_prompts(t.records, window)

    assert dropped == 0
    assert len(prompts) == 2
    assert prompts[0].startswith("PR 446 has gotten quite stale")
    assert prompts[1] == "Now resolve the conflicts and close out issue #97."
    joined = " ".join(prompts)
    assert "sidechain prompt" not in joined  # isSidechain
    assert "meta prompt" not in joined  # isMeta
    assert "tool_result" not in joined  # block-list tool payloads
    assert "LEAKED_TOOL_PAYLOAD" not in joined  # tool_result block's own "text" key
    assert "outside the window" not in joined  # out of window
    assert "ignore me" not in joined  # stripped wrapper


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
    assert (
        sd.project_label("-Users-lorchard-devel-foo", []) == "Users/lorchard/devel/foo"
    )


def test_distill_session_collects_metadata():
    t = sd.read_transcript(FIXTURES / "11111111-2222-3333-4444-555555555555.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    got = sd.distill_session(t, window, sd.NullVerifier())

    assert got["title"] == "Evaluate and refresh stale PR 446"
    assert got["session_id"] == "11111111-2222-3333-4444-555555555555"
    assert got["launch"] == "human"
    assert got["prompt_count"] == 2
    assert got["branches"] == ["main", "feat/pet"]
    assert got["started_at"].startswith("2026-07-28T")
    # ended_at must be the last in-window record, not the 07-30 one
    assert got["ended_at"].startswith("2026-07-28T")


def test_distill_session_marks_driver_launch():
    t = sd.read_transcript(FIXTURES / "99999999-8888-7777-6666-555555555555.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    assert sd.distill_session(t, window, sd.NullVerifier())["launch"] == "driver"


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
    t = sd.Transcript(
        path=Path(f"/tmp/{session_id}.jsonl"), records=records, malformed=0
    )
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    got = sd.distill_session(t, window, sd.NullVerifier())

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
    assert refs[0].kind == "issue"  # bare #N is ambiguous; assume issue
    assert refs[0].source == "prose"


def test_bare_hash_without_default_repo_is_dropped():
    assert sd.extract_refs([], ["close out issue #97"], default_repo=None) == []


def test_dedupe_prefers_pr_link_over_prose():
    refs = [
        sd.Ref(kind="pr", repo="mozilla/pilo", number=446, source="prose", url=None),
        sd.Ref(
            kind="pr",
            repo="mozilla/pilo",
            number=446,
            source="pr-link",
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


def test_bare_hash_preceded_by_word_char_or_slash_is_dropped():
    # The (?<![\w/#]) lookbehind exists to reject a "#123" that's actually
    # part of something else -- immediately glued to a word character (a
    # build tag like "build123#45") or a path/URL fragment separator
    # ("path/#46") -- not a standalone issue reference. Without the
    # lookbehind, #(\d+)\b alone would happily match both.
    refs = sd.extract_refs([], ["build123#45 and path/#46"], default_repo="a/b")
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
    t = sd.read_transcript(FIXTURES / "11111111-2222-3333-4444-555555555555.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    refs = sd.distill_session(t, window, sd.GhVerifier())["refs"]
    assert any(r["number"] == 446 and r["source"] == "pr-link" for r in refs)
    assert not any(r["number"] == 97 for r in refs)


def test_distill_session_attaches_bare_hash_to_resolved_repo(monkeypatch):
    # With an origin remote resolvable, the bare "#97" is no longer
    # ambiguous and is attached to that repo as an issue.
    monkeypatch.setattr(
        sd, "_run", lambda cmd, timeout=20: "git@github.com:mozilla/pilo.git\n"
    )
    t = sd.read_transcript(FIXTURES / "11111111-2222-3333-4444-555555555555.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    refs = sd.distill_session(t, window, sd.GhVerifier())["refs"]
    assert any(
        r["number"] == 97
        and r["kind"] == "issue"
        and r["repo"] == "mozilla/pilo"
        and r["source"] == "prose"
        for r in refs
    )


def test_distill_session_carries_resolved_repo(monkeypatch):
    # commits[] is keyed by the session's cwd's resolved origin remote
    # (owner/name); a session must carry that same value as `repo` so a
    # renderer can actually join commits to the project they belong to.
    monkeypatch.setattr(
        sd, "_run", lambda cmd, timeout=20: "git@github.com:mozilla/pilo.git\n"
    )
    t = sd.read_transcript(FIXTURES / "11111111-2222-3333-4444-555555555555.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")

    got = sd.distill_session(t, window, sd.GhVerifier())

    assert got["repo"] == "mozilla/pilo"


def test_distill_session_repo_is_none_without_resolvable_remote():
    t = sd.read_transcript(FIXTURES / "11111111-2222-3333-4444-555555555555.jsonl")
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")

    got = sd.distill_session(t, window, sd.NullVerifier())

    assert got["repo"] is None


def test_null_verifier_marks_everything_unavailable():
    v = sd.NullVerifier()
    ref = sd.Ref(kind="pr", repo="a/b", number=1, source="prose", url=None)
    got = v.verify_ref(ref)
    assert got["verification"] == "unavailable"
    assert got["state"] is None
    assert v.commits("/tmp", None) == []


def test_null_verifier_warns_that_verification_was_skipped():
    # --no-verify must not look indistinguishable from a clean verified run:
    # every ref comes back unavailable and zero commits are collected, so
    # the degradation has to be announced through warnings or it's silent.
    v = sd.NullVerifier()
    assert v.warnings != []
    assert "no-verify" in v.warnings[0]


def test_null_verifier_repo_for_calls_nothing(monkeypatch):
    def boom(cmd, timeout=20):
        raise AssertionError(f"_run must not be called: {cmd}")

    monkeypatch.setattr(sd, "_run", boom)
    assert sd.NullVerifier().repo_for("/anywhere") is None


def test_gh_verifier_repo_for_delegates_and_caches(monkeypatch):
    calls = []

    def fake_run(cmd, timeout=20):
        calls.append(cmd)
        return "git@github.com:mozilla/pilo.git\n"

    monkeypatch.setattr(sd, "_run", fake_run)
    v = sd.GhVerifier()
    assert v.repo_for("/repo") == "mozilla/pilo"
    assert v.repo_for("/repo") == "mozilla/pilo"
    assert len(calls) == 1  # cached by cwd on repeat lookups


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


def test_gh_verifier_requests_pr_and_issue_field_lists_separately(monkeypatch):
    calls = []

    def fake_run(cmd, timeout=20):
        calls.append(cmd)
        return json.dumps({"state": "OPEN", "title": "t", "url": "u"})

    monkeypatch.setattr(sd, "_run", fake_run)
    v = sd.GhVerifier()

    pr_ref = sd.Ref(
        kind="pr", repo="mozilla/pilo", number=446, source="pr-link", url=None
    )
    v.verify_ref(pr_ref)
    issue_ref = sd.Ref(
        kind="issue",
        repo="Mozilla-Ocho/pilo-evals-judge",
        number=97,
        source="prose",
        url=None,
    )
    v.verify_ref(issue_ref)

    assert len(calls) == 2
    pr_cmd, issue_cmd = calls
    pr_fields = pr_cmd[pr_cmd.index("--json") + 1]
    issue_fields = issue_cmd[issue_cmd.index("--json") + 1]
    assert "mergedAt" in pr_fields
    assert "mergedAt" not in issue_fields
    # gh rejects mergedAt for issue view entirely, so the issue field list
    # must not merely reorder the PR list -- it must actually omit the field.
    assert issue_fields != pr_fields


def test_gh_verifier_confirms_closed_issue(monkeypatch):
    payload = {
        "state": "CLOSED",
        "title": "Move cloud-eval secret management off the laptop",
        "url": "https://github.com/Mozilla-Ocho/pilo-evals-judge/issues/97",
        "closedAt": "2026-07-28T23:59:30Z",
    }
    monkeypatch.setattr(sd, "_run", lambda cmd, timeout=20: json.dumps(payload))
    v = sd.GhVerifier()
    ref = sd.Ref(
        kind="issue",
        repo="Mozilla-Ocho/pilo-evals-judge",
        number=97,
        source="prose",
        url=None,
    )
    got = v.verify_ref(ref)

    assert got["verification"] == "confirmed"
    assert got["state"] == "CLOSED"
    assert got["merged_at"] is None
    assert got["closed_at"] == "2026-07-28T23:59:30Z"
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
    assert v.gh_calls == 1  # surfaced as stats.gh_calls in the digest


def test_commits_parses_git_log(monkeypatch):
    log = (
        "abc1234\x1ffix(core): guard SPA snapshot\x1f2026-07-28T14:02:11-04:00\n"
        "def5678\x1fchore: bump deps\x1f2026-07-28T15:10:00-04:00"
    )

    def fake_run(cmd, timeout=20):
        if cmd[:2] == ["git", "-C"] and "rev-parse" in cmd:
            return rev_parse("/Users/lorchard/devel/tabs-project/pilo/.git")
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


def test_commits_scopes_author_email_per_repo(tmp_path, monkeypatch):
    # Transcripts span both work and personal repos, each with its own
    # locally-configured user.email. The lookup must be scoped to the repo
    # being scanned, not read from ambient cwd and reused for every repo.
    # Real directories: `commits` now checks cwd existence before shelling
    # out, so a fake path would short-circuit before ever calling fake_run.
    work = tmp_path / "work"
    personal = tmp_path / "personal"
    work.mkdir()
    personal.mkdir()

    config_calls = []
    log_cmds = []

    def fake_run(cmd, timeout=20):
        if "rev-parse" in cmd:
            repo_dir = cmd[cmd.index("-C") + 1]
            return rev_parse(f"{repo_dir}/.git")
        if "config" in cmd:
            config_calls.append(cmd)
            repo_dir = cmd[cmd.index("-C") + 1]
            return (
                "work@mozilla.com" if repo_dir == str(work) else "personal@example.com"
            )
        if "log" in cmd:
            log_cmds.append(cmd)
            return ""
        return None

    monkeypatch.setattr(sd, "_run", fake_run)
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    v = sd.GhVerifier()

    v.commits(str(work), window)
    v.commits(str(personal), window)
    v.commits(str(work), window)  # repeat: must hit the full per-repo commits cache

    assert len(config_calls) == 2  # one lookup per distinct repo, not per call
    assert len(log_cmds) == 2  # git log deduped by repo_root, not re-run on repeat
    assert "--author=work@mozilla.com" in log_cmds[0]
    assert "--author=personal@example.com" in log_cmds[1]


def test_commits_warns_when_git_log_fails(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()

    def fake_run(cmd, timeout=20):
        if "rev-parse" in cmd:
            return rev_parse(f"{repo}/.git")
        if "config" in cmd:
            return "lorchard@mozilla.com"
        if "log" in cmd:
            return None
        return None

    monkeypatch.setattr(sd, "_run", fake_run)
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    v = sd.GhVerifier()
    got = v.commits(str(repo), window)

    assert got == []
    assert len(v.warnings) == 1
    assert "git log failed" in v.warnings[0]


def test_commits_empty_log_is_not_a_warning(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()

    def fake_run(cmd, timeout=20):
        if "rev-parse" in cmd:
            return rev_parse(f"{repo}/.git")
        if "config" in cmd:
            return "lorchard@mozilla.com"
        if "log" in cmd:
            return ""
        return None

    monkeypatch.setattr(sd, "_run", fake_run)
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    v = sd.GhVerifier()
    got = v.commits(str(repo), window)

    assert got == []
    assert v.warnings == []


def test_commits_returns_empty_for_nonexistent_cwd(tmp_path, monkeypatch):
    # A cleaned-up worktree cwd is not degradation: no warning, and no
    # subprocess should even be attempted.
    def boom(cmd, timeout=20):
        raise AssertionError(f"_run must not be called for a nonexistent cwd: {cmd}")

    monkeypatch.setattr(sd, "_run", boom)
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    v = sd.GhVerifier()
    missing = tmp_path / "gone"

    got = v.commits(str(missing), window)

    assert got == []
    assert v.warnings == []


def test_commits_dedupes_git_log_by_resolved_repo_root(tmp_path, monkeypatch):
    # Two different cwds (e.g. two worktrees of the same repo) resolving to
    # the same repo_root must trigger exactly one `git log` invocation, not
    # one per cwd.
    worktree_a = tmp_path / "worktree-a"
    worktree_b = tmp_path / "worktree-b"
    worktree_a.mkdir()
    worktree_b.mkdir()
    shared_repo_root = tmp_path / "shared-repo"

    log_calls = []

    def fake_run(cmd, timeout=20):
        if "rev-parse" in cmd:
            # Shared common dir, per-worktree toplevel: what git really reports
            # from inside two linked worktrees of one repository.
            return rev_parse(f"{shared_repo_root}/.git", cmd[cmd.index("-C") + 1])
        if "config" in cmd:
            return "lorchard@mozilla.com"
        if "log" in cmd:
            log_calls.append(cmd)
            return ""
        return None

    monkeypatch.setattr(sd, "_run", fake_run)
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    v = sd.GhVerifier()

    v.commits(str(worktree_a), window)
    v.commits(str(worktree_b), window)

    assert len(log_calls) == 1
    # ...but working state is per-worktree, so both are tracked: each has its
    # own branch and its own uncommitted changes.
    assert list(v.worktrees) == [str(worktree_a), str(worktree_b)]


def test_build_digest_over_fixtures_no_verify():
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    digest = sd.build_digest(FIXTURES.parent, window, sd.NullVerifier())

    assert digest["schema_version"] == sd.SCHEMA_VERSION
    assert digest["window"]["rule"] == "explicit"
    assert digest["stats"]["malformed_lines"] == 1
    assert digest["stats"]["gh_calls"] == 0  # --no-verify makes no calls
    assert digest["warnings"], "a --no-verify run must announce degradation"
    assert digest["commits"] == []  # NullVerifier never collects commits


def test_build_digest_applies_verification_to_refs(monkeypatch):
    payload = {
        "state": "MERGED",
        "title": "t",
        "url": "u",
        "mergedAt": "2026-07-28T18:22:11Z",
    }
    monkeypatch.setattr(sd, "_run", lambda cmd, timeout=20: json.dumps(payload))
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    digest = sd.build_digest(FIXTURES.parent, window, sd.GhVerifier())

    refs = [r for s in digest["sessions"] for r in s["refs"]]
    assert refs, "fixture should yield at least one ref"
    assert all(r["verification"] == "confirmed" for r in refs)
    assert any(r["state"] == "MERGED" for r in refs)


DIGEST_TOP_LEVEL_KEYS = {
    "schema_version",
    "generated_at",
    "window",
    "stats",
    "warnings",
    "notes",
    "sessions",
    "commits",
    "working_state",
}
WORKING_STATE_KEYS = {"repo", "path", "branch", "dirty_files", "last_commit"}
SESSION_KEYS = {
    "session_id",
    "transcript",
    "title",
    "project",
    "cwds",
    "repo",
    "branches",
    "launch",
    "started_at",
    "ended_at",
    "prompt_count",
    "prompt_chars_dropped",
    "prompts",
    "assistant_notes",
    "refs",
}
REF_KEYS = {
    "kind",
    "repo",
    "number",
    "source",
    "url",
    "verification",
    "state",
    "title",
    "merged_at",
    "closed_at",
}
COMMIT_KEYS = {"repo", "path", "sha", "subject", "committed_at"}


def test_digest_matches_documented_schema(monkeypatch):
    """Locks the exact key sets SKILL.md enumerates as the digest contract.

    spec.md promises a test that "asserts the digest validates against the
    schema"; nothing did. Renaming a key (e.g. merged_at -> mergedAt) would
    silently break the renderer while every other test kept passing.
    """

    def fake_run(cmd, timeout=20):
        if cmd[0] == "gh":
            return json.dumps(
                {
                    "state": "MERGED",
                    "title": "t",
                    "url": "https://github.com/mozilla/pilo/pull/446",
                    "mergedAt": "2026-07-28T18:22:11Z",
                    "closedAt": "2026-07-28T18:22:11Z",
                }
            )
        if "rev-parse" in cmd:
            # A real directory: `working_state` skips a toplevel that no longer
            # exists, and this test needs an entry to check the shape of.
            return rev_parse(f"{HERE}/.git")
        if "remote" in cmd:
            return "git@github.com:mozilla/pilo.git"
        if "config" in cmd:
            return "lorchard@mozilla.com"
        if "symbolic-ref" in cmd:
            return "feat/thing"
        if "status" in cmd:
            return " M src/a.py\n?? src/b.py"
        if "log" in cmd:
            return "abc1234\x1ffix: something\x1f2026-07-28T14:02:11-04:00"
        return None

    monkeypatch.setattr(sd, "_run", fake_run)
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    digest = sd.build_digest(FIXTURES.parent, window, sd.GhVerifier())

    assert set(digest.keys()) == DIGEST_TOP_LEVEL_KEYS

    assert digest["working_state"], "a resolved worktree should report its state"
    for state in digest["working_state"]:
        assert set(state.keys()) == WORKING_STATE_KEYS
        assert set(state["last_commit"].keys()) == {"sha", "subject", "committed_at"}

    assert digest["sessions"], "fixtures should yield at least one session"
    for session in digest["sessions"]:
        assert set(session.keys()) == SESSION_KEYS
        for ref in session["refs"]:
            assert set(ref.keys()) == REF_KEYS
            assert ref["verification"] in {"confirmed", "unavailable"}

    assert digest["commits"], "fixtures should yield at least one commit"
    for commit in digest["commits"]:
        assert set(commit.keys()) == COMMIT_KEYS


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
            "--date",
            "2026-07-28",
            "--no-verify",
            "--root",
            str(FIXTURES.parent),
            "--out",
            str(out),
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


def test_no_verify_never_touches_subprocess(monkeypatch):
    """--no-verify must make zero subprocess calls, full stop.

    This is the whole point of routing all repo/commit/ref resolution
    through the verifier: NullVerifier must never let a `git`/`gh` call
    escape, even indirectly via a helper distill_session calls itself.
    """

    def boom(cmd, timeout=20):
        raise AssertionError(f"_run must not be called under --no-verify: {cmd}")

    monkeypatch.setattr(sd, "_run", boom)
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    digest = sd.build_digest(FIXTURES.parent, window, sd.NullVerifier())
    assert digest["schema_version"] == sd.SCHEMA_VERSION


# --- Phase 1: harvest cd/git -C dirs so their commits count -------------------


def _asst_bash(command):
    """One assistant record carrying a single Bash tool_use with `command`."""
    return {
        "type": "assistant",
        "isSidechain": False,
        "message": {
            "content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": command}},
            ]
        },
    }


def test_harvest_dirs_finds_absolute_cd_and_git_C():
    recs = [
        _asst_bash("cd /Users/me/devel/zoo-service && git add -A"),
        _asst_bash("git -c x=y -C /Users/me/devel/other status"),
    ]
    assert sd.harvest_dirs(recs) == [
        "/Users/me/devel/zoo-service",
        "/Users/me/devel/other",
    ]


def test_harvest_dirs_dedupes_preserving_order():
    recs = [
        _asst_bash("cd /a/one && ls"),
        _asst_bash("cd /a/two && ls"),
        _asst_bash("cd /a/one && git commit"),
    ]
    assert sd.harvest_dirs(recs) == ["/a/one", "/a/two"]


def test_harvest_dirs_ignores_relative_vars_and_node_modules():
    recs = [
        _asst_bash('cd zoo-service; cd "$WT/x"; cd /a/node_modules/pkg'),
        _asst_bash("git -C ../rel status"),
    ]
    assert sd.harvest_dirs(recs) == []


def test_harvest_dirs_expands_tilde():
    recs = [_asst_bash("cd ~/devel/thing && ls")]
    assert sd.harvest_dirs(recs) == [str(Path("~/devel/thing").expanduser())]


def test_harvest_dirs_rejects_subcommand_dash_C_and_trailing_deps():
    recs = [
        # `-C` as a subcommand option (reuse a commit message), not the dir flag:
        _asst_bash("git commit -C HEAD~1"),
        _asst_bash("git commit -C /Users/me/abs/ref -m x"),
        # node_modules / .git as the final path segment (no trailing slash):
        _asst_bash("cd /Users/me/proj/node_modules"),
        _asst_bash("cd /Users/me/proj/.git"),
    ]
    assert sd.harvest_dirs(recs) == []


def test_harvest_dirs_finds_git_C_after_config_flag():
    recs = [_asst_bash("git -c user.name=X -C /Users/me/devel/proj status")]
    assert sd.harvest_dirs(recs) == ["/Users/me/devel/proj"]


def test_non_checkout_cwd_is_a_note_not_a_warning(tmp_path, monkeypatch):
    # A cwd that isn't a checkout is routine, not run degradation: a stray `cd`
    # into a plain directory, or a launch dir that merely holds checkouts. It
    # used to land in `warnings`, which made every such run render as degraded.
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setattr(sd, "_run", lambda cmd, timeout=20: None)
    window = sd.resolve_window(local(2026, 7, 30), date="2026-07-29")

    v = sd.GhVerifier()
    assert v.commits(str(plain), window) == []
    assert v.warnings == []
    assert len(v.notes) == 1
    assert "no commits to collect" in v.notes[0]


def test_container_cwd_expands_to_its_checkouts(tmp_path, monkeypatch):
    # `~/firefox` holds `firefox/` plus its worktrees and is not itself a
    # checkout. Launching a session there used to yield one warning and zero
    # commits; the checkouts beneath it must be scanned instead.
    container = tmp_path / "firefox"
    (container / "firefox").mkdir(parents=True)
    (container / "wt-bidi").mkdir()
    (container / "docs").mkdir()  # a plain directory, not a checkout
    (container / ".cache").mkdir()  # hidden: never scanned

    scanned = []
    # Matched by exact path, not basename: the container is itself named
    # `firefox`, so a basename match would resolve it as a checkout and never
    # expand -- which is the whole behavior under test.
    checkouts = {str(container / "firefox"), str(container / "wt-bidi")}

    def fake_run(cmd, timeout=20):
        target = cmd[cmd.index("-C") + 1] if "-C" in cmd else ""
        if "rev-parse" in cmd:
            if target in checkouts:
                return rev_parse(f"{target}/.git")
            return None
        if "config" in cmd:
            return "lorchard@mozilla.com"
        if "log" in cmd:
            scanned.append(target)
            return f"abc{len(scanned)}\x1fwork\x1f2026-07-29T10:00:00-07:00"
        return None

    monkeypatch.setattr(sd, "_run", fake_run)
    window = sd.resolve_window(local(2026, 7, 30), date="2026-07-29")
    v = sd.GhVerifier()
    got = v.commits(str(container), window)

    assert sorted(Path(p).name for p in scanned) == ["firefox", "wt-bidi"]
    assert len(got) == 2
    assert v.warnings == []
    assert any("scanned one level down" in note for note in v.notes)


def test_harvested_path_contributes_commits_but_not_working_state(
    tmp_path, monkeypatch
):
    # A `cd /Users/lorchard/devel` is navigation, not a claim about where work
    # happened. Expanding it pulled in every checkout underneath -- unrelated
    # repos with week-old uncommitted dirt, which then read as "worked on".
    # Harvested paths contribute commits only: no expansion, no working state,
    # no note.
    container = tmp_path / "devel"
    unrelated = container / "some-other-repo"
    unrelated.mkdir(parents=True)

    def fake_run(cmd, timeout=20):
        target = cmd[cmd.index("-C") + 1] if "-C" in cmd else ""
        if "rev-parse" in cmd:
            return rev_parse(f"{target}/.git") if target == str(unrelated) else None
        if "config" in cmd:
            return "lorchard@mozilla.com"
        if "log" in cmd:
            return "aaa1111\x1fstale\x1f2026-07-29T10:00:00-07:00"
        return None

    monkeypatch.setattr(sd, "_run", fake_run)
    window = sd.resolve_window(local(2026, 7, 30), date="2026-07-29")
    v = sd.GhVerifier()

    assert v.commits(str(container), window, session_cwd=False) == []
    assert v.worktrees == {}
    assert v.notes == []

    # A checkout reached by `cd` still yields its commits -- that path predates
    # this flag and stays. It just doesn't earn a working_state entry.
    got = v.commits(str(unrelated), window, session_cwd=False)
    assert len(got) == 1
    assert v.worktrees == {}


def test_child_scan_stops_at_one_level(tmp_path, monkeypatch):
    # Expansion must not walk a whole tree: only checkouts that are immediate
    # children count, so a checkout nested two deep under a plain directory is
    # out of reach rather than triggering an unbounded descent.
    container = tmp_path / "top"
    buried = container / "middle" / "repo"
    buried.mkdir(parents=True)

    def fake_run(cmd, timeout=20):
        target = cmd[cmd.index("-C") + 1] if "-C" in cmd else ""
        if "rev-parse" in cmd and Path(target).name == "repo":
            return rev_parse(f"{target}/.git")
        return None

    monkeypatch.setattr(sd, "_run", fake_run)
    window = sd.resolve_window(local(2026, 7, 30), date="2026-07-29")
    v = sd.GhVerifier()

    assert v.commits(str(container), window) == []
    assert v.worktrees == {}


def test_child_scan_skips_a_directory_with_too_many_children(tmp_path, monkeypatch):
    # A session launched from `~` shouldn't fan out into a rev-parse per entry.
    home = tmp_path / "home"
    home.mkdir()
    for i in range(sd.CHILD_SCAN_LIMIT + 1):
        (home / f"dir{i:02d}").mkdir()

    calls = []

    def fake_run(cmd, timeout=20):
        calls.append(cmd)
        return None

    monkeypatch.setattr(sd, "_run", fake_run)
    window = sd.resolve_window(local(2026, 7, 30), date="2026-07-29")
    v = sd.GhVerifier()

    assert v.commits(str(home), window) == []
    # Exactly one rev-parse: the cwd itself. No per-child probing.
    assert len(calls) == 1


def test_working_state_reports_unlanded_work(tmp_path, monkeypatch):
    # The case that motivated this: a full session in a checkout that produced
    # no commit inside the window. `commits[]` is empty and correct; without
    # working_state there is nothing at all to hang "worked on" from.
    tree = tmp_path / "wt-bidi"
    tree.mkdir()

    def fake_run(cmd, timeout=20):
        if "rev-parse" in cmd:
            return rev_parse(f"{tree}/.git")
        if "remote" in cmd:
            return "git@github.com:mozilla/gecko-dev.git"
        if "config" in cmd:
            return "lorchard@mozilla.com"
        if "symbolic-ref" in cmd:
            return "bidi-webext-commands\n"
        if "status" in cmd:
            return " M remote/shared/Foo.sys.mjs\n?? notes.md\n"
        if "log" in cmd:
            # Windowed log is empty; the unwindowed -1 lookup still answers.
            return (
                ""
                if "--since=" in " ".join(cmd)
                else ("27318fe\x1fDocument the registry\x1f2026-08-01T14:17:23-07:00")
            )
        return None

    monkeypatch.setattr(sd, "_run", fake_run)
    window = sd.resolve_window(local(2026, 8, 4), date="2026-08-03")
    v = sd.GhVerifier()

    assert v.commits(str(tree), window) == []  # nothing landed in the window
    state = v.working_state(str(tree))

    assert state["repo"] == "mozilla/gecko-dev"
    assert state["branch"] == "bidi-webext-commands"
    assert state["dirty_files"] == 2
    assert state["last_commit"]["sha"] == "27318fe"
    # Dated before the window opened: parked work, not work done today.
    assert state["last_commit"]["committed_at"] < window.since.isoformat()
    assert v.warnings == []


def test_working_state_skips_a_removed_worktree(tmp_path, monkeypatch):
    monkeypatch.setattr(sd, "_run", lambda cmd, timeout=20: "whatever")
    assert sd.GhVerifier().working_state(str(tmp_path / "gone")) is None


def test_build_digest_counts_harvested_remoteless_commit(tmp_path, monkeypatch):
    # A session launched in /launch (which doesn't exist, so its own cwd scan is a
    # silent no-op) whose Bash `cd`s into a real, remote-less repo where the commit
    # actually landed. That commit must show up with repo=None and no degraded warning.
    root = tmp_path / "projects"
    proj = root / "proj-x"
    proj.mkdir(parents=True)
    work = tmp_path / "work"
    work.mkdir()

    tid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    recs = [
        {
            "type": "user",
            "isSidechain": False,
            "sessionId": "s1",
            "gitBranch": "main",
            "cwd": "/launch",
            "timestamp": "2026-07-29T12:00:00+00:00",
            "message": {"role": "user", "content": "build it"},
        },
        {
            "type": "assistant",
            "isSidechain": False,
            "cwd": "/launch",
            "timestamp": "2026-07-29T12:01:00+00:00",
            "message": {
                "content": [
                    {"type": "text", "text": "on it"},
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {
                            "command": f"cd {work} && git add -A && git commit -m x"
                        },
                    },
                ]
            },
        },
    ]
    (proj / f"{tid}.jsonl").write_text(
        "\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8"
    )

    def fake_run(cmd, timeout=20):
        if "rev-parse" in cmd:
            return rev_parse(f"{cmd[cmd.index('-C') + 1]}/.git")
        if "remote" in cmd:
            return None  # no origin -> repo None
        if "config" in cmd:
            return "me@example.com"
        if "log" in cmd:
            if cmd[cmd.index("-C") + 1] == str(work):
                return "abc1234\x1ffeat: thing\x1f2026-07-29T12:00:00-07:00"
            return ""
        return None

    monkeypatch.setattr(sd, "_run", fake_run)
    window = sd.resolve_window(local(2026, 7, 30), date="2026-07-29")
    digest = sd.build_digest(root, window, sd.GhVerifier())

    hits = [c for c in digest["commits"] if c["sha"] == "abc1234"]
    assert len(hits) == 1
    assert hits[0]["repo"] is None
    assert hits[0]["path"] == str(work)
    assert digest["warnings"] == []


# --- Phase 2: bounded assistant-prose narrative signal ------------------------


def _asst_text(*blocks, ts="2026-07-28T14:00:00+00:00"):
    """One assistant record carrying the given content blocks."""
    return {
        "type": "assistant",
        "isSidechain": False,
        "timestamp": ts,
        "message": {"content": list(blocks)},
    }


def test_extract_assistant_notes_takes_final_text_block_per_turn():
    recs = [
        _asst_text(
            {"type": "thinking", "thinking": "ignore me"},
            {"type": "text", "text": "first"},
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
            {"type": "text", "text": "the conclusion"},
        )
    ]
    assert sd.extract_assistant_notes(recs) == ["the conclusion"]


def test_extract_assistant_notes_skips_turns_without_text():
    recs = [
        _asst_text({"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}),
        _asst_text({"type": "thinking", "thinking": "hmm"}),
        _asst_text({"type": "text", "text": "kept"}),
    ]
    assert sd.extract_assistant_notes(recs) == ["kept"]


def test_extract_assistant_notes_truncates_and_respects_budget():
    big = "x" * 5000
    recs = [_asst_text({"type": "text", "text": big}) for _ in range(3)]
    notes = sd.extract_assistant_notes(recs, turn_limit=600, budget=1000)
    assert notes  # at least one captured
    assert all(n.endswith(sd.TRUNCATION_MARKER) for n in notes)
    body = sum(len(n) - len(sd.TRUNCATION_MARKER) for n in notes)
    assert body <= 1000


def test_extract_assistant_notes_filters_by_window():
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    recs = [
        _asst_text({"type": "text", "text": "in"}, ts="2026-07-28T14:00:00+00:00"),
        _asst_text({"type": "text", "text": "out"}, ts="2026-07-30T14:00:00+00:00"),
    ]
    assert sd.extract_assistant_notes(recs, window) == ["in"]


def test_distill_session_includes_assistant_notes():
    session_id = "abababab-cdcd-efef-0101-232323232323"
    records = [
        {
            "type": "user",
            "isSidechain": False,
            "timestamp": "2026-07-28T14:00:00+00:00",
            "sessionId": session_id,
            "message": {"role": "user", "content": "do it"},
        },
        _asst_text({"type": "text", "text": "here is what I concluded"}),
    ]
    t = sd.Transcript(
        path=Path(f"/tmp/{session_id}.jsonl"), records=records, malformed=0
    )
    window = sd.resolve_window(local(2026, 7, 29), date="2026-07-28")
    got = sd.distill_session(t, window, sd.NullVerifier())
    assert got["assistant_notes"] == ["here is what I concluded"]
