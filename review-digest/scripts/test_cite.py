import json

import cite


def item(id_, date, title="", url=None, path=None):
    meta = {"path": path} if path else {}
    return {"id": id_, "date": date, "title": title, "url": url, "meta": meta}


ITEMS = {
    i["id"]: i
    for i in [
        item("j:2026-08-14#rfc", "2026-08-14", "rfc", path="journals/2026/2026-08-14"),
        item(
            "j:2026-08-15#1-1-w-x",
            "2026-08-15",
            "1:1 w/ [[people/x|x]]",
            path="journals/2026/2026-08-15",
        ),
        item(
            "j:2026-08-16#notes", "2026-08-16", "notes", path="journals/2026/2026-08-16"
        ),
        item("t:2026-08-14", "2026-08-14", path="journals/2026/2026-08-14"),
        item("sd:2026-08-14", "2026-08-14", path="standup-digests/2026-08-14"),
        item(
            "gh:org/repo#12", "2026-08-14", "PR", "https://github.com/org/repo/pull/12"
        ),
        item("lin:ABC-1", "2026-08-14", "issue", "https://linear.app/x/issue/ABC-1"),
        item(
            "doc:AbC",
            "2026-08-14",
            "Design RFC",
            "https://docs.google.com/document/d/AbC",
        ),
    ]
}


def test_link_formats():
    out, missing = cite.link_ids(
        "a `j:2026-08-14#rfc` b `t:2026-08-14` c `sd:2026-08-14` "
        "d `gh:org/repo#12` e `lin:ABC-1` f `doc:AbC`",
        ITEMS,
    )
    assert missing == set()
    assert "[[journals/2026/2026-08-14#rfc|Aug 14]]" in out
    assert "[[journals/2026/2026-08-14|Aug 14 tasks]]" in out
    assert "[[standup-digests/2026-08-14|digest Aug 14]]" in out
    assert "[repo#12](https://github.com/org/repo/pull/12)" in out
    assert "[ABC-1](https://linear.app/x/issue/ABC-1)" in out
    assert "[Design RFC](https://docs.google.com/document/d/AbC)" in out


def test_headings_unsafe_as_anchors_link_to_the_day():
    out, _ = cite.link_ids("`j:2026-08-15#1-1-w-x` `j:2026-08-16#notes`", ITEMS)
    assert (
        out == "[[journals/2026/2026-08-15|Aug 15]] [[journals/2026/2026-08-16|Aug 16]]"
    )


def test_unresolved_ids_are_left_and_reported():
    out, missing = cite.link_ids("see `lin:ZZZ-9` and `make setup`", ITEMS)
    assert out == "see `lin:ZZZ-9` and `make setup`"
    assert missing == {"lin:ZZZ-9"}


def test_main_rewrites_files_and_exits_nonzero_on_unresolved(tmp_path, capsys):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "ledger.json").write_text(json.dumps({"items": list(ITEMS.values())}))
    good = tmp_path / "good.md"
    good.write_text("x `gh:org/repo#12`\n")
    bad = tmp_path / "bad.md"
    bad.write_text("y `lin:ZZZ-9` `doc:AbC`\n")

    assert cite.main(["--cache", str(cache), str(good)]) == 0
    assert good.read_text() == "x [repo#12](https://github.com/org/repo/pull/12)\n"

    assert cite.main(["--cache", str(cache), str(bad)]) == 1
    assert (
        bad.read_text()
        == "y `lin:ZZZ-9` [Design RFC](https://docs.google.com/document/d/AbC)\n"
    )
    assert "lin:ZZZ-9" in capsys.readouterr().err


def test_doc_titles_with_brackets_and_missing_urls():
    items = {
        "doc:B": item("doc:B", "2026-08-14", "[RFC] Fleet", "https://d/B"),
        "lin:ABC-2": item("lin:ABC-2", "2026-08-14", "issue", None),
    }
    out, _ = cite.link_ids("`doc:B` `lin:ABC-2`", items)
    assert out == r"[\[RFC\] Fleet](https://d/B) ABC-2"


def test_suffixed_duplicate_headings_link_to_the_day():
    items = {
        "j:2026-08-14#foo": item(
            "j:2026-08-14#foo", "2026-08-14", "foo", path="journals/2026/2026-08-14"
        ),
        "j:2026-08-14#foo-2": item(
            "j:2026-08-14#foo-2", "2026-08-14", "foo", path="journals/2026/2026-08-14"
        ),
    }
    out, _ = cite.link_ids("`j:2026-08-14#foo-2`", items)
    assert out == "[[journals/2026/2026-08-14|Aug 14]]"


def test_malformed_prefixed_ids_are_reported_not_ignored():
    out, missing = cite.link_ids(
        "`j:2026-08-14#RFC` `gh:org/repo#abc` `lin:5f2e-uuid`", ITEMS
    )
    assert missing == {"j:2026-08-14#RFC", "gh:org/repo#abc", "lin:5f2e-uuid"}


def test_links_inside_table_rows_escape_pipes():
    text = "| a | `j:2026-08-14#rfc` |\nplain `j:2026-08-14#rfc`\n"
    out, _ = cite.link_ids(text, ITEMS)
    row, plain = out.splitlines()
    assert row == r"| a | [[journals/2026/2026-08-14#rfc\|Aug 14]] |"
    assert plain == "plain [[journals/2026/2026-08-14#rfc|Aug 14]]"
