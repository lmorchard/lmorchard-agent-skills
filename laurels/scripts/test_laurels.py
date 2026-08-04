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
    }


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
