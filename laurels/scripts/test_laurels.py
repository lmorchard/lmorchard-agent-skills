import subprocess

import laurels


def _seed_pending(tmp_path, *lines):
    (tmp_path / "pending.md").write_text("".join(line + "\n" for line in lines))


def test_pending_filters_by_project(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_pending(
        tmp_path,
        "- [2026-08-03] (obsidian/main) a",
        "- [2026-08-03] (tabs/pilo) b",
    )
    rc = laurels.main(["pending", "--project", "obsidian/main"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "0: [2026-08-03] (obsidian/main) a" in out
    assert "tabs/pilo" not in out


def test_accept_moves_to_laurels_with_accept_date(tmp_path, monkeypatch):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_pending(
        tmp_path,
        "- [2026-08-01] (p) keeper",
        "- [2026-08-01] (p) dropme",
    )
    rc = laurels.main(["accept", "0", "--date", "2026-08-03"])
    assert rc == 0
    assert (tmp_path / "laurels.md").read_text() == "- [2026-08-03] (p) keeper\n"
    assert (tmp_path / "pending.md").read_text() == "- [2026-08-01] (p) dropme\n"


def test_drop_removes_without_accepting(tmp_path, monkeypatch):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_pending(tmp_path, "- [2026-08-01] (p) x", "- [2026-08-01] (p) y")
    rc = laurels.main(["drop", "1"])
    assert rc == 0
    assert not (tmp_path / "laurels.md").exists()
    assert (tmp_path / "pending.md").read_text() == "- [2026-08-01] (p) x\n"


def test_accept_reports_stale_index(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_pending(tmp_path, "- [2026-08-01] (p) x")
    rc = laurels.main(["accept", "5", "--date", "2026-08-03"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "5" in err


def test_accept_dedupes_duplicate_indices(tmp_path, monkeypatch):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_pending(tmp_path, "- [2026-08-01] (p) keeper")
    rc = laurels.main(["accept", "0", "0", "--date", "2026-08-03"])
    assert rc == 0
    assert (tmp_path / "laurels.md").read_text() == "- [2026-08-03] (p) keeper\n"
    assert (tmp_path / "pending.md").read_text() == ""


def test_format_and_parse_round_trip():
    line = laurels.format_entry(
        "2026-08-03", "obsidian/main", "bidi-only check was the fix"
    )
    assert line == "- [2026-08-03] (obsidian/main) bidi-only check was the fix"
    parsed = laurels.parse_entry(line)
    assert parsed == {
        "date": "2026-08-03",
        "project": "obsidian/main",
        "text": "bidi-only check was the fix",
        "tags": [],
    }


def test_extract_tags():
    text = "#spike #TEST #spike fixed issue #54 and wideboi #72 after reading http://example.com#anchor #diag-fix"
    tags = laurels.extract_tags(text)
    # lowercase, deduped, order preserved, issue numbers and url anchors excluded
    assert tags == ["spike", "test", "diag-fix"]


def test_normalize_tag():
    assert laurels.normalize_tag("#spike") == "spike"
    assert laurels.normalize_tag("  #DIAG-test  ") == "diag-test"
    assert laurels.normalize_tag("ui") == "ui"
    try:
        laurels.normalize_tag("#54")
        assert False, "should have failed on leading digit"
    except ValueError:
        pass
    try:
        laurels.normalize_tag("bad tag")
        assert False, "should have failed on spaces"
    except ValueError:
        pass


def test_format_entry_with_tags():
    line = laurels.format_entry(
        "2026-09-20", "proj", "Ran experiments", tags=["spike", "perf"]
    )
    assert line == "- [2026-09-20] (proj) #spike #perf Ran experiments"

    # Does not duplicate if already present in text
    line2 = laurels.format_entry(
        "2026-09-20", "proj", "#spike Ran experiments", tags=["spike", "diag"]
    )
    assert line2 == "- [2026-09-20] (proj) #diag #spike Ran experiments"


def test_add_with_tags(tmp_path, monkeypatch):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    rc = laurels.main(
        [
            "add",
            "caught issue #123",
            "--project",
            "mine/proj",
            "--date",
            "2026-09-22",
            "-t",
            "diag",
            "--tags",
            "test, perf",
        ]
    )
    assert rc == 0
    text = (tmp_path / "pending.md").read_text()
    assert text == "- [2026-09-22] (mine/proj) #diag #test #perf caught issue #123\n"


def test_add_rejects_invalid_tag(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    rc = laurels.main(["add", "text", "--project", "p", "-t", "#123"])
    err = capsys.readouterr().err
    assert rc != 0
    assert "invalid tag" in err


def test_pending_filters_by_tag(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_pending(
        tmp_path,
        "- [2026-09-21] (p) #spike spike win",
        "- [2026-09-21] (p) #diag diag win",
    )
    rc = laurels.main(["pending", "--project", "p", "--tag", "spike"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "spike win" in out
    assert "diag win" not in out


def test_accept_adds_tags(tmp_path, monkeypatch):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_pending(tmp_path, "- [2026-09-21] (p) untagged win")
    rc = laurels.main(["accept", "0", "--date", "2026-09-22", "-t", "spike"])
    assert rc == 0
    assert (
        tmp_path / "laurels.md"
    ).read_text() == "- [2026-09-22] (p) #spike untagged win\n"


def test_list_and_filter(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_laurels(
        tmp_path,
        "- [2026-09-20] (p) #test test entry",
        "- [2026-09-21] (p) #spike spike entry",
        "- [2026-09-22] (other) #test other entry",
    )
    rc = laurels.main(["list", "--project", "p"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "0: [2026-09-20] (p) #test test entry" in out
    assert "1: [2026-09-21] (p) #spike spike entry" in out
    assert "other" not in out

    # filter by tag
    rc2 = laurels.main(["list", "--all", "--tag", "spike"])
    out2 = capsys.readouterr().out
    assert rc2 == 0
    assert "1: [2026-09-21] (p) #spike spike entry" in out2
    assert "test entry" not in out2


def test_tags_counts(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_laurels(
        tmp_path,
        "- [2026-09-20] (p) #test #diag item 1",
        "- [2026-09-21] (p) #test item 2",
        "- [2026-09-22] (p) untagged item 3",
    )
    rc = laurels.main(["tags", "--project", "p"])
    out = capsys.readouterr().out
    assert rc == 0
    lines = out.splitlines()
    assert lines == [
        "#test (2)",
        "#diag (1)",
        "untagged (1)",
    ]


def test_archive_moves_to_archive_md(tmp_path, monkeypatch):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_laurels(
        tmp_path,
        "- [2026-09-20] (p) first",
        "- [2026-09-21] (p) second",
        "- [2026-09-22] (p) third",
    )
    rc = laurels.main(["archive", "1"])
    assert rc == 0
    assert (tmp_path / "archive.md").read_text() == "- [2026-09-21] (p) second\n"
    assert (
        tmp_path / "laurels.md"
    ).read_text() == "- [2026-09-20] (p) first\n- [2026-09-22] (p) third\n"


def test_show_filters_by_tag(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_laurels(
        tmp_path,
        "- [2026-09-20] (p) #test test entry",
        "- [2026-09-21] (p) #spike spike entry",
    )
    rc = laurels.main(["show", "--project", "p", "--tag", "test", "--seed", "1"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Laurels [#test]" in out
    assert "test entry" in out
    assert "spike entry" not in out


def test_show_diverse_sampling_prefers_different_tags(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_laurels(
        tmp_path,
        "- [2026-09-18] (p) #diag diag entry",
        "- [2026-09-19] (p) #test test entry 1",
        "- [2026-09-20] (p) #test test entry 2",
    )
    # newest is test entry 2 (#test). older has test entry 1 (#test) and diag entry (#diag).
    # diverse sampling should choose diag entry (#diag) over test entry 1.
    rc = laurels.main(["show", "--project", "p", "--n", "3", "--seed", "0"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "test entry 2" in out
    assert "diag entry" in out
    assert "test entry 1" not in out


def test_show_recent_flag(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_laurels(
        tmp_path,
        "- [2026-09-18] (p) #diag diag entry",
        "- [2026-09-19] (p) #test test entry 1",
        "- [2026-09-20] (p) #test test entry 2",
    )
    rc = laurels.main(["show", "--project", "p", "--recent", "--n", "3"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "test entry 2" in out
    assert "test entry 1" in out
    assert "diag entry" not in out


def test_format_collapses_multiline_text():
    line = laurels.format_entry("2026-08-03", "p", "line one\n  line two")
    assert "\n" not in line
    assert line == "- [2026-08-03] (p) line one line two"


def test_parse_rejects_non_entry_lines():
    assert laurels.parse_entry("# a heading") is None
    assert laurels.parse_entry("") is None


def test_project_slug_non_repo_returns_basename(tmp_path):
    d = tmp_path / "someproj"
    d.mkdir()
    assert laurels.project_slug(str(d)) == "someproj"


def test_project_slug_resolves_git_worktree_to_repo_root(tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    assert laurels.project_slug(str(repo)) == "myrepo"


def test_add_appends_project_tagged_line(tmp_path, monkeypatch):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    rc = laurels.main(
        ["add", "the fix worked", "--project", "obsidian/main", "--date", "2026-08-03"]
    )
    assert rc == 0
    text = (tmp_path / "pending.md").read_text()
    assert text == "- [2026-08-03] (obsidian/main) the fix worked\n"


def test_add_rejects_malformed_date(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    rc = laurels.main(["add", "x", "--date", "bad", "--project", "p"])
    err = capsys.readouterr().err
    assert rc != 0
    assert err
    assert not (tmp_path / "pending.md").exists()


def test_add_creates_store_dir(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "laurels"
    monkeypatch.setenv("LAURELS_DIR", str(target))
    laurels.main(["add", "x", "--project", "p", "--date", "2026-08-03"])
    assert (target / "pending.md").exists()


def _seed_laurels(tmp_path, *lines):
    (tmp_path / "laurels.md").write_text("".join(ln + "\n" for ln in lines))


def test_show_project_matches_capped_at_two_newest_first(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_laurels(
        tmp_path,
        "- [2026-08-01] (p) oldest",
        "- [2026-08-02] (p) middle",
        "- [2026-08-03] (p) newest",
    )
    # seed chosen so the cross-project roll misses (no others exist anyway)
    rc = laurels.main(["show", "--project", "p", "--n", "3", "--seed", "1"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "oldest" not in out
    lines = [entry for entry in out.splitlines() if entry.startswith("- ")]
    assert lines == [
        "- [2026-08-03] (p) newest",
        "- [2026-08-02] (p) middle",
    ]


def test_show_orders_by_date_not_append_order(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_laurels(
        tmp_path,
        "- [2026-08-03] (p) later",
        "- [2026-08-01] (p) earlier-but-appended-after",
    )
    rc = laurels.main(["show", "--project", "p", "--n", "3", "--seed", "1"])
    out = capsys.readouterr().out
    assert rc == 0
    lines = [entry for entry in out.splitlines() if entry.startswith("- ")]
    assert lines == [
        "- [2026-08-03] (p) later",
        "- [2026-08-01] (p) earlier-but-appended-after",
    ]


def test_show_empty_store_is_silent(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    rc = laurels.main(["show", "--project", "p", "--seed", "1"])
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_show_can_include_cross_project_when_roll_hits(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_laurels(
        tmp_path,
        "- [2026-08-01] (p) mine",
        "- [2026-08-02] (other) theirs",
    )
    # find a seed where randint(1, n) == 1; --n 1 guarantees a hit
    rc = laurels.main(["show", "--project", "p", "--n", "1", "--seed", "0"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "- [2026-08-01] (p) mine" in out
    assert "(elsewhere)" in out
    assert "theirs" in out


def test_show_swallows_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    monkeypatch.setattr(
        laurels,
        "read_entries",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert laurels.main(["show", "--project", "p", "--seed", "1"]) == 0
