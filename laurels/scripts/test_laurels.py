import subprocess

import laurels


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
