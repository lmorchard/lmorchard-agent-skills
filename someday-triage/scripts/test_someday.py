import json
import os
from pathlib import Path

import pytest
import someday

FIXTURES = Path(__file__).parent / "fixtures"


def test_round_trip_is_byte_exact():
    text = (FIXTURES / "sample.md").read_text()
    assert someday.serialize(someday.parse(text)) == text


def test_parse_captures_structure():
    doc = someday.parse((FIXTURES / "sample.md").read_text())
    titles = [s.title for s in doc.sections]
    assert titles[0] == "intake"
    assert "tier 1 — small enough to finish in one sitting" in titles
    assert doc.preamble[0].startswith("A less aspirational cousin")


def test_parse_handles_non_checkbox_and_checked_items():
    doc = someday.parse((FIXTURES / "sample.md").read_text())
    items = {i.text: i for s in doc.sections for i in s.items}
    assert items["batteries?"].checked is None
    assert items["already done thing"].checked is True
    assert items["Led strip for under bar"].checked is False


def test_notes_are_collected_regardless_of_indent_style():
    doc = someday.parse((FIXTURES / "sample.md").read_text())
    items = {i.text: i for s in doc.sections for i in s.items}
    handwriting = items[
        "Work on [[blog/drafts/adventures in handwriting recognition|adventures in handwriting recognition]]"
    ]
    assert handwriting.notes == ["a note indented with spaces, not a tab"]


def test_section_footer_is_not_absorbed_by_preceding_item():
    doc = someday.parse((FIXTURES / "sample.md").read_text())
    section = next(s for s in doc.sections if s.title == "outings & visits")
    footer_text = (
        "*If any of these acquires a date, move it off this list — "
        "see the LeGuin exhibit in [[someday-done]].*"
    )
    # The whole trailing run (including its surrounding blanks) is promoted
    # to the section footer, so it round-trips byte-exact; only the text
    # itself is asserted here, not the exact blank padding around it.
    assert footer_text in section.footer
    item = next(iter(section.items))
    assert footer_text not in item.raw
    assert footer_text not in item.tail
    assert footer_text not in item.notes


def test_dirty_item_still_leaves_section_footer_intact():
    doc = someday.parse((FIXTURES / "sample.md").read_text())
    section = next(s for s in doc.sections if s.title == "outings & visits")
    item = next(iter(section.items))
    item.dirty = True
    item.text = "Take the girl to Really Good Stuff sometime, ideally on a weekend"
    out = someday.serialize(doc)
    footer_text = (
        "*If any of these acquires a date, move it off this list — "
        "see the LeGuin exhibit in [[someday-done]].*"
    )
    assert footer_text in out


def test_interstitial_prose_stays_between_its_items():
    doc = someday.parse((FIXTURES / "sample.md").read_text())
    section = next(s for s in doc.sections if s.title == "workshop notes")
    items = {i.text: i for i in section.items}
    prose = "an aside about dust collection that belongs to neither item"
    assert prose in items["tune the belt sander"].tail
    assert prose not in items["order more sanding belts"].tail
    assert prose not in section.footer


def test_interstitial_prose_survives_preceding_item_going_dirty():
    doc = someday.parse((FIXTURES / "sample.md").read_text())
    section = next(s for s in doc.sections if s.title == "workshop notes")
    first = section.items[0]
    first.dirty = True
    first.text = "tune and wax the belt sander"
    out = someday.serialize(doc)
    prose_index = out.index(
        "an aside about dust collection that belongs to neither item"
    )
    belt_index = out.index("tune and wax the belt sander")
    belts_index = out.index("order more sanding belts")
    assert belt_index < prose_index < belts_index


def test_malformed_link_survives_round_trip():
    text = (FIXTURES / "sample.md").read_text()
    assert (
        "[spec kit]((https://github.com/github/spec-kit from github"
        in someday.serialize(someday.parse(text))
    )


REAL = (
    Path(
        os.environ.get(
            "SOMEDAY_VAULT", str(Path.home() / "Documents" / "Obsidian" / "main")
        )
    )
    / "pages"
    / "someday.md"
)


@pytest.mark.skipif(not REAL.exists(), reason="vault not present")
def test_round_trip_on_real_file():
    text = REAL.read_text()
    assert someday.serialize(someday.parse(text)) == text


def test_ids_are_stable_and_collision_suffixed():
    doc = someday.parse("# intake\n- [ ] Same Thing\n- [ ] same   thing\n- [ ] other\n")
    someday.assign_ids(doc)
    ids = [i.id for i in doc.sections[0].items]
    assert ids[0] != ids[2]
    assert ids[1] == ids[0] + "-2"


def test_digest_changes_with_content():
    assert someday.digest("a") != someday.digest("b")
    assert someday.digest("a") == someday.digest("a")
    assert len(someday.digest("a")) == 12


SAMPLE_WITH_FLAG = """# intake

- [ ] new idea one
- [ ] new idea two

# tier 1 — quick

- [ ] existing thing
	- needs-research (2026-08-01): is it maintained?
- [ ] another thing
"""


def _seed(tmp_path, text, name="someday.md"):
    pages = tmp_path / "pages"
    pages.mkdir(exist_ok=True)
    (pages / name).write_text(text)
    return pages / name


def test_status_json_reports_counts(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, SAMPLE_WITH_FLAG)
    rc = someday.main(["status", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["intake"] == 2
    assert data["needs_research"] == 1
    assert data["open_total"] == 4
    assert data["buckets"]["tier 1 — quick"] == 2
    assert len(data["digest"]) == 12


def test_status_reports_empty_intake(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, "# intake\n\n# tier 1 — quick\n\n- [ ] a thing\n")
    rc = someday.main(["status", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["intake"] == 0
    assert data["needs_research"] == 0


BASIC = """# intake

- [ ] a fresh idea

# tier 1 — quick

- [ ] existing thing
"""


def _plan(tmp_path, ops, digest_override=None):
    src = tmp_path / "pages" / "someday.md"
    text = src.read_text()
    plan = {
        "digest": digest_override or someday.digest(text),
        "ops": ops,
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    return path


def test_apply_rejects_stale_plan(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, BASIC)
    plan = _plan(tmp_path, [], digest_override="000000000000")
    before = src.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc == 2
    assert "stale" in capsys.readouterr().err.lower()
    assert src.read_text() == before


def test_apply_rejects_unknown_item_id(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, BASIC)
    plan = _plan(tmp_path, [{"op": "retitle", "item": "deadbeef", "text": "nope"}])
    before = src.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc == 2
    assert "deadbeef" in capsys.readouterr().err
    assert src.read_text() == before


def test_apply_rejects_unsupported_op(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, BASIC)
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(tmp_path, [{"op": "defer", "item": target}])
    before = src.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc == 2
    assert "defer" in capsys.readouterr().err
    assert src.read_text() == before


def test_apply_rejects_malformed_op(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, BASIC)
    # A model-authored plan is exactly the input most likely to omit a
    # required key; this should refuse cleanly, not crash with a KeyError
    # traceback and exit 1.
    plan = _plan(tmp_path, [{"op": "retitle"}])
    before = src.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc == 2
    assert "malformed plan" in capsys.readouterr().err.lower()
    assert src.read_text() == before


def test_apply_rejects_reconciliation_failure_from_broken_serializer(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, BASIC)
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(tmp_path, [{"op": "annotate", "item": target, "notes": ["x"]}])
    before = src.read_text()

    # The in-memory reconcile() check can't catch a bug in serialize()
    # itself, so this simulates one directly: a serializer that silently
    # drops every item. reconcile() sees an untouched `doc` and passes; the
    # re-parse-and-count check is the only thing that can catch this.
    monkeypatch.setattr(someday, "serialize", lambda doc: "# intake\n")

    rc = someday.main(["apply", str(plan)])
    assert rc == 3
    assert "serializer check failed" in capsys.readouterr().err.lower()
    assert src.read_text() == before


def test_dry_run_leaves_file_untouched(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, BASIC)
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path, [{"op": "annotate", "item": target, "notes": ["first step: x"]}]
    )
    before = src.read_text()
    mtime = src.stat().st_mtime_ns
    rc = someday.main(["apply", str(plan), "--dry-run"])
    assert rc == 0
    assert src.read_text() == before
    assert src.stat().st_mtime_ns == mtime
    assert "first step: x" in capsys.readouterr().out


def test_atomic_write_leaves_original_intact_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "f.md"
    target.write_text("original\n")

    def boom(src, dst):
        raise OSError("simulated failure")

    monkeypatch.setattr(someday.os, "replace", boom)
    with pytest.raises(OSError):
        someday.atomic_write(target, "replacement\n")
    assert target.read_text() == "original\n"
    assert list(tmp_path.glob("*.tmp*")) == []


def test_annotate_preserves_continuation_lines_and_nested_bullets():
    # render_item must regenerate only the item's own line. `parse` only
    # models two line classes under an item ("- " bullets as notes, blank
    # lines as tail); a continuation line and a deeper-nested bullet exist
    # solely in `raw`. Before the fix, going dirty regenerated from `notes`
    # + `tail` alone, which silently dropped the continuation line and
    # flattened the nested bullet to a single tab — and both safety checks
    # (reconcile on origin, reparse-and-count) are blind to this, since the
    # item count and origin are unaffected.
    doc = someday.parse((FIXTURES / "sample.md").read_text())
    section = next(s for s in doc.sections if s.title == "continuation lines")
    item = section.items[0]
    someday.apply_annotate(item, ["a fresh note"])
    out = someday.serialize(doc)
    assert "\t  continued on the next line" in out
    assert "\t\t- a deeper sub-bullet" in out
    assert "\t- a fresh note" in out


def test_annotate_and_retitle_are_written(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, BASIC)
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path,
        [
            {"op": "retitle", "item": target, "text": "a sharpened idea"},
            {"op": "annotate", "item": target, "notes": ["first step: read the docs"]},
        ],
    )
    assert someday.main(["apply", str(plan)]) == 0
    out = src.read_text()
    assert "- [ ] a sharpened idea" in out
    assert "\t- first step: read the docs" in out
    assert "a fresh idea" not in out


def test_flag_replaces_existing_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, SAMPLE_WITH_FLAG)
    doc, _ = someday.load(src)
    flagged = next(i for i in someday.open_items(doc) if someday.is_flagged(i))
    plan = _plan(
        tmp_path,
        [{"op": "flag", "item": flagged.id, "question": "newer question?"}],
    )
    assert someday.main(["apply", str(plan), "--today", "2026-08-04"]) == 0
    out = src.read_text()
    assert "needs-research (2026-08-04): newer question?" in out
    assert "is it maintained?" not in out


def test_two_flag_ops_in_one_plan_leave_exactly_one_flag_line(tmp_path, monkeypatch):
    # apply_flag filters raw and notes before appending the new flag to
    # added_notes, but a second flag op in the same plan only ever sees
    # added_notes growing, never filtered -- so two flags on one item
    # should not both survive to the written file.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, BASIC)
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path,
        [
            {"op": "flag", "item": target, "question": "q1?"},
            {"op": "flag", "item": target, "question": "q2?"},
        ],
    )
    assert someday.main(["apply", str(plan), "--today", "2026-08-04"]) == 0
    out = src.read_text()
    assert out.count("needs-research (2026-08-04):") == 1
    assert "q2?" in out
    assert "q1?" not in out


def test_flag_then_remove_in_one_plan_leaves_no_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, BASIC)
    doc, _ = someday.load(src)
    origin = doc.sections[0].items[0].origin
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path,
        [
            {"op": "flag", "item": target, "question": "q?"},
            {"op": "flag", "item": target, "remove": True},
        ],
    )
    assert someday.main(["apply", str(plan), "--today", "2026-08-04"]) == 0
    out = src.read_text()
    assert "needs-research" not in out

    # Re-load rather than trust the in-memory item, so this proves the file
    # and the model agree, not just that the object in hand looks right.
    doc2, _ = someday.load(src)
    item2 = next(i for s in doc2.sections for i in s.items if i.origin == origin)
    assert someday.is_flagged(item2) is False
