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


PLACEABLE = """# intake

- [ ] a fresh idea

# tier 1 — quick

## blog & site

- [ ] existing thing
"""


def test_place_moves_item_into_cluster(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, PLACEABLE)
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path,
        [
            {
                "op": "place",
                "item": target,
                "bucket": "tier 1 — quick",
                "cluster": "blog & site",
            }
        ],
    )
    assert someday.main(["apply", str(plan)]) == 0
    out = src.read_text()
    intake_body = out.split("# tier 1")[0]
    assert "a fresh idea" not in intake_body
    assert out.index("existing thing") < out.index("a fresh idea")


def test_place_rejects_unknown_cluster(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, PLACEABLE)
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path,
        [
            {
                "op": "place",
                "item": target,
                "bucket": "tier 1 — quick",
                "cluster": "nonexistent",
            }
        ],
    )
    before = src.read_text()
    assert someday.main(["apply", str(plan)]) != 0
    assert "nonexistent" in capsys.readouterr().err
    assert src.read_text() == before


def test_place_creates_cluster_when_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, PLACEABLE)
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path,
        [
            {
                "op": "place",
                "item": target,
                "bucket": "tier 1 — quick",
                "cluster": "brand new",
            }
        ],
    )
    assert someday.main(["apply", str(plan), "--allow-new-clusters"]) == 0
    out = src.read_text()
    assert "## brand new" in out
    assert out.index("## brand new") < out.index("a fresh idea")


def test_place_leaves_interstitial_tail_behind_in_source_section(tmp_path, monkeypatch):
    # The moved item ("a fresh idea with an aside") has a non-blank tail --
    # interstitial prose sitting between it and the next intake item. That
    # prose is section context, not part of the item, so a move must leave
    # it behind (appended to the preceding item's tail) rather than carrying
    # it along to the destination.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, (FIXTURES / "sample.md").read_text())
    doc, _ = someday.load(src)
    intake = doc.sections[0]
    target = next(i for i in intake.items if i.text == "a fresh idea with an aside").id
    plan = _plan(
        tmp_path,
        [
            {
                "op": "place",
                "item": target,
                "bucket": "tier 1 — small enough to finish in one sitting",
                "cluster": "blog & site",
            }
        ],
    )
    assert someday.main(["apply", str(plan)]) == 0
    out = src.read_text()
    intake_body = out.split("# tier 1")[0]
    aside = "an aside about scope that belongs to neither idea"
    assert "a fresh idea with an aside" not in intake_body
    assert aside in intake_body
    assert "another idea" in intake_body
    assert out.index("## blog & site") < out.index("a fresh idea with an aside")
    assert out.index("a fresh idea with an aside") < out.index("## lights")


def test_place_rejects_unknown_bucket_even_with_allow_new_clusters(
    tmp_path, monkeypatch, capsys
):
    # Ruling: a missing bucket is always an error, even with
    # --allow-new-clusters -- that flag creates clusters, not tiers. This is
    # a distinct branch from the cluster case (unconditional vs.
    # allow_new-gated), so it needs its own coverage.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, PLACEABLE)
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path,
        [
            {
                "op": "place",
                "item": target,
                "bucket": "nonexistent bucket",
                "cluster": "blog & site",
            }
        ],
    )
    before = src.read_text()
    rc = someday.main(["apply", str(plan), "--allow-new-clusters"])
    assert rc == 2
    assert "nonexistent bucket" in capsys.readouterr().err
    assert src.read_text() == before


MERGEABLE = """# intake

- [ ] dead on arrival thing

# tier 1 — quick

## lights

- [ ] Led strip for under bar
- [ ] led strip for UNDER bar
"""


def test_archive_moves_item_to_archive_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    _seed(
        tmp_path,
        "Completed items from [[someday]]\n\n- [x] old thing\n",
        "someday-done.md",
    )
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path,
        [
            {
                "op": "archive",
                "item": target,
                "reason": "closed",
                "note": "abandoned upstream, 358 open issues",
            }
        ],
    )
    assert someday.main(["apply", str(plan), "--today", "2026-08-04"]) == 0
    assert "dead on arrival thing" not in src.read_text()
    archive = (tmp_path / "pages" / "someday-done.md").read_text()
    assert "old thing" in archive
    assert "dead on arrival thing" in archive
    assert "abandoned upstream, 358 open issues" in archive
    assert "closed by research" in archive


def test_merge_keeps_winner_and_archives_loser(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    _seed(tmp_path, "Completed items from [[someday]]\n", "someday-done.md")
    doc, _ = someday.load(src)
    items = {i.text: i for s in doc.sections for i in s.items}
    winner = items["Led strip for under bar"].id
    loser = items["led strip for UNDER bar"].id
    plan = _plan(
        tmp_path,
        [
            {
                "op": "merge",
                "into": winner,
                "from": [loser],
                "note": "duplicate wording",
            }
        ],
    )
    assert someday.main(["apply", str(plan), "--today", "2026-08-04"]) == 0
    out = src.read_text()
    assert out.count("nder bar") == 1
    # The count assertion above is vacuous on its own: winner and loser
    # differ only in case ("under bar" vs "UNDER bar"), so "nder bar"
    # (lowercase) matches the winner's line regardless of whether the loser
    # was actually removed. This asserts removal directly.
    assert "led strip for UNDER bar" not in out
    # The op's note is annotated onto the winner, not just recorded in the
    # archive.
    assert "duplicate wording" in out
    archive = (tmp_path / "pages" / "someday-done.md").read_text()
    assert "led strip for UNDER bar" in archive
    assert "collapsed duplicates" in archive


def test_reconcile_reports_an_item_lost_without_being_recorded():
    doc = someday.parse("# tier 1 — quick\n\n- [ ] a\n- [ ] b\n- [ ] c\n")
    before = someday.live_origins(doc)
    vanished = doc.sections[0].items.pop(1)
    # Removed but NOT recorded in removed_origins — the exact bug this catches.
    assert someday.reconcile(before, doc, set()) == {vanished.origin}
    # Recorded deliberately, so not a loss.
    assert someday.reconcile(before, doc, {vanished.origin}) == set()


def test_serializer_check_blocks_a_write_that_would_lose_items(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    monkeypatch.setattr(someday, "serialize", lambda doc: "broken\n")
    plan = _plan(tmp_path, [])
    before = src.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc == 3
    assert "serializer check failed" in capsys.readouterr().err
    assert src.read_text() == before


def test_archive_is_written_before_source(tmp_path, monkeypatch):
    """Ordering is load-bearing: a failure must duplicate, never lose."""
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    _seed(tmp_path, "Completed items from [[someday]]\n", "someday-done.md")
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path, [{"op": "archive", "item": target, "reason": "closed", "note": "x"}]
    )
    order = []
    real = someday.atomic_write

    def spy(path, text):
        order.append(path.name)
        real(path, text)

    monkeypatch.setattr(someday, "atomic_write", spy)
    assert someday.main(["apply", str(plan), "--today", "2026-08-04"]) == 0
    assert order == ["someday-done.md", "someday.md"]


def test_archive_preserves_continuation_lines_and_nested_bullets(tmp_path, monkeypatch):
    # archive_entry must build from item.raw, not item.notes: notes is a
    # lossy projection that only keeps indented "- " bullets, so building
    # from it silently drops continuation lines and flattens nesting depth
    # -- permanently, since the source line is gone and nothing reaches the
    # archive either. Both safety nets are blind to this (origin and item
    # counts are unaffected), so this has to be caught by a direct
    # assertion on the archive's content.
    #
    # The fixture's "continuation lines" item also carries a needs-research
    # flag line specifically so the flag-exclusion branch has coverage: no
    # other archive/merge test's fixture contains one, so without this the
    # filter could regress (or be deleted outright) with all tests staying
    # green while stale research questions leak permanently into the real,
    # 337+-line archive a human reads.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, (FIXTURES / "sample.md").read_text())
    _seed(tmp_path, "Completed items from [[someday]]\n", "someday-done.md")
    doc, _ = someday.load(src)
    section = next(s for s in doc.sections if s.title == "continuation lines")
    target = section.items[0].id
    plan = _plan(
        tmp_path,
        [{"op": "archive", "item": target, "reason": "closed", "note": "op note"}],
    )
    assert someday.main(["apply", str(plan), "--today", "2026-08-04"]) == 0
    archive = (tmp_path / "pages" / "someday-done.md").read_text()
    assert "\t- a note" in archive
    assert "\t  continued on the next line" in archive
    assert "\t\t- a deeper sub-bullet" in archive
    assert "\t- op note" in archive
    assert "needs-research" not in archive


COMPLETED_WITH_CONTENT = """# tier 1 — quick

- [x] finished multi-part thing
	- a note
	  continued on the next line
		- a deeper sub-bullet
	- needs-research (2026-08-01): stale question?
- [ ] still open thing
"""


def test_sweep_archives_completed_item_with_all_its_indented_content(
    tmp_path, monkeypatch, capsys
):
    # A ticked box is the ordinary case a completed-item sweep exists to
    # handle: the item, its note, a continuation line and a nested bullet
    # must all travel to the archive, and the flag line must not (see
    # test_archive_preserves_continuation_lines_and_nested_bullets for why
    # that exclusion exists). The id comes from `status --json`'s
    # `completed_items`, exactly the way intake work reads ids from
    # `intake_items`.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, COMPLETED_WITH_CONTENT)
    _seed(tmp_path, "Completed items from [[someday]]\n", "someday-done.md")
    someday.main(["status", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert data["completed"] == 1
    target = data["completed_items"][0]["id"]
    plan = _plan(tmp_path, [{"op": "archive", "item": target, "reason": "done"}])
    assert someday.main(["apply", str(plan), "--today", "2026-08-04"]) == 0
    out = src.read_text()
    assert "finished multi-part thing" not in out
    assert "still open thing" in out
    archive = (tmp_path / "pages" / "someday-done.md").read_text()
    assert "- [x] finished multi-part thing" in archive
    assert "\t- a note" in archive
    assert "\t  continued on the next line" in archive
    assert "\t\t- a deeper sub-bullet" in archive
    assert "needs-research" not in archive


def test_archive_of_item_still_open_carries_unchecked_box(tmp_path, monkeypatch):
    # Retiring an item while it is still open (closed/missed/routed/merged)
    # must record that it was open when retired -- `- [ ] `, not the old
    # bare `- ` that dropped the state entirely.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    _seed(tmp_path, "Completed items from [[someday]]\n", "someday-done.md")
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id  # "dead on arrival thing", checked False
    plan = _plan(
        tmp_path, [{"op": "archive", "item": target, "reason": "closed", "note": "x"}]
    )
    assert someday.main(["apply", str(plan), "--today", "2026-08-04"]) == 0
    archive = (tmp_path / "pages" / "someday-done.md").read_text()
    assert "- [ ] dead on arrival thing" in archive


def test_archive_of_non_checkbox_fragment_carries_bare_dash(tmp_path, monkeypatch):
    # A fragment (no checkbox at all) has no state to record; archiving it
    # must not invent one.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, "# unclear\n\n- batteries?\n")
    _seed(tmp_path, "Completed items from [[someday]]\n", "someday-done.md")
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path, [{"op": "archive", "item": target, "reason": "closed", "note": "x"}]
    )
    assert someday.main(["apply", str(plan), "--today", "2026-08-04"]) == 0
    archive = (tmp_path / "pages" / "someday-done.md").read_text()
    assert "- batteries?" in archive
    assert "- [ ] batteries?" not in archive
    assert "- [x] batteries?" not in archive


def test_archive_leaves_interstitial_tail_behind_in_source_section(
    tmp_path, monkeypatch
):
    # Coverage was previously inherited from `place` only by shared
    # implementation (_detach); MERGEABLE's archived items all have
    # blank-only tails, so the non-blank branch never actually ran under
    # `archive`. This exercises it directly.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, (FIXTURES / "sample.md").read_text())
    _seed(tmp_path, "Completed items from [[someday]]\n", "someday-done.md")
    doc, _ = someday.load(src)
    intake = doc.sections[0]
    target = next(i for i in intake.items if i.text == "a fresh idea with an aside").id
    plan = _plan(
        tmp_path,
        [{"op": "archive", "item": target, "reason": "closed", "note": "x"}],
    )
    assert someday.main(["apply", str(plan), "--today", "2026-08-04"]) == 0
    out = src.read_text()
    intake_body = out.split("# tier 1")[0]
    aside = "an aside about scope that belongs to neither idea"
    assert "a fresh idea with an aside" not in intake_body
    assert aside in intake_body
    archive = (tmp_path / "pages" / "someday-done.md").read_text()
    assert aside not in archive


def test_archive_rejects_unknown_reason(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(tmp_path, [{"op": "archive", "item": target, "reason": "bogus"}])
    before = src.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc == 2
    assert "bogus" in capsys.readouterr().err
    assert src.read_text() == before


def test_merge_rejects_unknown_id_in_into(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    doc, _ = someday.load(src)
    items = {i.text: i for s in doc.sections for i in s.items}
    loser = items["led strip for UNDER bar"].id
    plan = _plan(tmp_path, [{"op": "merge", "into": "deadbeef", "from": [loser]}])
    before = src.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc == 2
    assert "deadbeef" in capsys.readouterr().err
    assert src.read_text() == before


def test_merge_rejects_unknown_id_in_from(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    doc, _ = someday.load(src)
    items = {i.text: i for s in doc.sections for i in s.items}
    winner = items["Led strip for under bar"].id
    plan = _plan(tmp_path, [{"op": "merge", "into": winner, "from": ["deadbeef"]}])
    before = src.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc == 2
    assert "deadbeef" in capsys.readouterr().err
    assert src.read_text() == before


def test_merge_rejects_winner_named_in_its_own_from_list(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    doc, _ = someday.load(src)
    items = {i.text: i for s in doc.sections for i in s.items}
    winner = items["Led strip for under bar"].id
    plan = _plan(tmp_path, [{"op": "merge", "into": winner, "from": [winner]}])
    before = src.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc == 2
    assert src.read_text() == before


def test_merge_rejects_duplicate_id_in_from(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    doc, _ = someday.load(src)
    items = {i.text: i for s in doc.sections for i in s.items}
    winner = items["Led strip for under bar"].id
    loser = items["led strip for UNDER bar"].id
    plan = _plan(tmp_path, [{"op": "merge", "into": winner, "from": [loser, loser]}])
    before = src.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc == 2
    assert src.read_text() == before


def test_apply_with_no_archived_items_leaves_archive_file_untouched(
    tmp_path, monkeypatch
):
    # The `if archived:` guard must not append an empty dated section when
    # nothing was actually archived -- the real archive holds years of
    # history, and a stub section on every no-op run would silently pile up.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, BASIC)
    archive = _seed(
        tmp_path,
        "Completed items from [[someday]]\n\n- [x] old thing\n",
        "someday-done.md",
    )
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(tmp_path, [{"op": "annotate", "item": target, "notes": ["x"]}])
    before = archive.read_text()
    assert someday.main(["apply", str(plan)]) == 0
    assert archive.read_text() == before


def test_reconciliation_catches_an_item_recorded_removed_but_still_present(
    tmp_path, monkeypatch, capsys
):
    # The dual of test_reconcile_reports_an_item_lost_without_being_recorded:
    # reconcile()'s set subtraction (before - live - removed) can't catch an
    # origin that is BOTH still live AND recorded as removed -- subtracting
    # a live origin from a live-origins set is a no-op. Simulate the bug by
    # making _detach a no-op, so archive records the item as removed and
    # writes it to the archive file, but it never actually leaves the
    # source. Both writes must be blocked.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    archive = _seed(tmp_path, "Completed items from [[someday]]\n", "someday-done.md")
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path, [{"op": "archive", "item": target, "reason": "closed", "note": "x"}]
    )
    monkeypatch.setattr(someday, "_detach", lambda doc, item: None)
    before_src = src.read_text()
    before_archive = archive.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc == 3
    assert "still present" in capsys.readouterr().err
    assert src.read_text() == before_src
    assert archive.read_text() == before_archive


def test_place_leaves_first_item_tail_in_section_body(tmp_path, monkeypatch):
    # The other half of the tail-transfer rule: when the moved item is
    # first in its section, its tail has no preceding item to fold into,
    # so it goes to the section's body instead.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    text = """# intake

- [ ] a fresh idea with an aside

an aside about scope that belongs to neither idea

- [ ] another idea

# tier 1 — quick

## blog & site

- [ ] existing thing
"""
    src = _seed(tmp_path, text)
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path,
        [
            {
                "op": "place",
                "item": target,
                "bucket": "tier 1 — quick",
                "cluster": "blog & site",
            }
        ],
    )
    assert someday.main(["apply", str(plan)]) == 0
    out = src.read_text()
    intake_body = out.split("# tier 1")[0]
    destination_body = out.split("## blog & site")[1]
    aside = "an aside about scope that belongs to neither idea"
    assert "a fresh idea with an aside" not in intake_body
    assert aside in intake_body
    assert "another idea" in intake_body
    assert aside not in destination_body
    assert "a fresh idea with an aside" in destination_body
    assert out.index("existing thing") < out.index("a fresh idea with an aside")


DUPES = """# tier 1 — quick

## lights

- [ ] Led strip for under bar
- [ ] Led strip for above sink
- [ ] led strip for UNDER bar

## infra

- [ ] Get logotron working again with docker-in-docker?
- [ ] get [[logotron]] working again and persistently - docker in docker?
- [ ] get [[pages/logotron|logotron]] dockerized
- [ ] Build a tool to export spotify playlist as markdown?
- [ ] tool to export my playlists from Spotify API (to plex?)?
"""


def test_dupes_does_not_group_under_bar_with_above_sink(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, DUPES)
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    groups = someday.find_dupes(doc, 0.75)
    for group in groups:
        texts = {i.text for i in group}
        assert not (
            "Led strip for under bar" in texts and "Led strip for above sink" in texts
        )


def test_dupes_groups_case_variant_of_same_item(tmp_path, monkeypatch):
    # A genuine duplicate pulled from the real vault: same item, re-typed
    # with different capitalization. `normalize` lowercases before either
    # half of `similarity` runs, so this is the near-verbatim case `dupes`
    # is meant to catch -- distinct from the under-bar/above-sink pair
    # above, which is surface-similar but semantically different.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, DUPES)
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    groups = someday.find_dupes(doc, 0.75)
    group = next(
        g for g in groups if any(i.text == "Led strip for under bar" for i in g)
    )
    texts = {i.text for i in group}
    assert "led strip for UNDER bar" in texts
    assert "Led strip for above sink" not in texts


def test_dupes_groups_byte_identical_items(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(
        tmp_path,
        "# tier 1 — quick\n\n## misc\n\n- [ ] Buy new hiking boots\n"
        "- [ ] Buy new hiking boots\n",
    )
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    groups = someday.find_dupes(doc, 0.75)
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_dupes_does_not_group_paraphrased_logotron_items(tmp_path, monkeypatch):
    # Documented limitation, not a bug. `similarity` blends SequenceMatcher's
    # surface-form ratio with a Jaccard overlap of content words -- that
    # combination is what lets the under-bar/above-sink test above tell a
    # false positive apart from a real one, but it has no way to recognize
    # a genuine paraphrase that shares few literal words: measured directly,
    # ("Get logotron working again with docker-in-docker?",
    # "get [[pages/logotron|logotron]] dockerized") scores ~0.43, *below*
    # the ~0.49 the under-bar/above-sink false-positive pair scores. No
    # threshold groups this trio without also risking that false positive,
    # so `dupes` is a near-verbatim detector by design: it finds re-typed
    # and case/punctuation-variant repeats, not reworded duplicates. Reading
    # intake items for paraphrased duplicates is the model's job (see
    # SKILL.md), not this command's. If a future metric change makes this
    # assertion start failing, that's a signal to update this comment and
    # the docs describing the limitation -- not proof of a bug fixed.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, DUPES)
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    groups = someday.find_dupes(doc, 0.75)
    logotron = [g for g in groups if any("logotron" in i.text for i in g)]
    assert logotron == []


def test_dupes_json_output(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, DUPES)
    rc = someday.main(["dupes", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["groups"]

    # A model authors `merge` ops against the ids in this payload, so it's
    # not enough that "items" is present -- each item's id must actually be
    # the same id `load` assigns that item, not just a non-empty string.
    doc, _ = someday.load(src)
    expected_ids = {i.text: i.id for s in doc.sections for i in s.items}
    for group in data["groups"]:
        assert group["items"]
        for item in group["items"]:
            assert item["id"]
            assert item["text"]
            assert item["id"] == expected_ids[item["text"]]


LINTABLE = """A preamble line

# intake

- [ ] go to the show on 2026-09-14
- [ ] check out [thing](https://example.com)
- [ ] plain idea with no link

# tier 1 — quick

- [ ] researched thing
	- alive and maintained (verified 2025-01-01)
- [ ] fresh thing
	- alive and maintained (verified 2026-08-01)

# unclear

- batteries?
"""


def test_lint_flags_dated_items(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, LINTABLE)
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    assert any("2026-09-14" in f["text"] for f in report["dated"])


def test_lint_flags_non_checkbox_fragments(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, LINTABLE)
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    assert [f["text"] for f in report["fragments"]] == ["batteries?"]


def test_lint_nominates_only_provable_research_candidates(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, LINTABLE)
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    texts = [f["text"] for f in report["research_candidates"]]
    assert "check out [thing](https://example.com)" in texts
    assert "plain idea with no link" not in texts


def test_lint_flags_stale_verified_annotations(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, LINTABLE)
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    stale = [f["text"] for f in report["stale"]]
    assert "researched thing" in stale
    assert "fresh thing" not in stale


def test_lint_does_not_flag_items_without_dates(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, LINTABLE)
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    dated_texts = [f["text"] for f in report["dated"]]
    assert "plain idea with no link" not in dated_texts


# Regression cases for DATE_IN_TEXT_RE: the month-name alternative used to
# allow a greedy `[a-z]*` suffix after the three-letter abbreviation, so it
# matched into the middle of an unrelated word before landing on a trailing
# number ("mar" + "io" in "mario", "may" + "be" in "maybe", etc). None of
# these five phrases contain an actual date and must never be flagged.
DATE_FALSE_POSITIVES = [
    "play mario 5",
    "maybe 5 minutes",
    "julia 5.0",
    "octopus 5-pack",
    "deck 5 boards",
]


def test_lint_date_regex_rejects_month_prefix_false_positives(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    body = "\n".join(f"- [ ] {phrase}" for phrase in DATE_FALSE_POSITIVES)
    _seed(tmp_path, f"# intake\n\n{body}\n")
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    dated_texts = [f["text"] for f in report["dated"]]
    for phrase in DATE_FALSE_POSITIVES:
        assert phrase not in dated_texts


def test_lint_flags_untiered_items_before_any_level_one_heading(tmp_path, monkeypatch):
    # A level-2 heading before any level-1 heading is legal markdown; the
    # item it introduces has no enclosing level-1 title, so bucket stays
    # None for it.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, "## some cluster\n\n- [ ] orphan item\n")
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    assert [f["text"] for f in report["untiered"]] == ["orphan item"]
    assert report["untiered"][0]["bucket"] is None


def test_lint_stale_reports_item_once_despite_two_stale_notes(tmp_path, monkeypatch):
    # Multiple stale (verified ...) notes on one item must still yield a
    # single stale report entry -- the count-of-one guarantee holds because
    # "stale" is decided from the max verified date across all notes, not
    # by stopping at the first note found.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(
        tmp_path,
        "# tier 1 — quick\n\n"
        "- [ ] double stale thing\n"
        "\t- alive (verified 2020-01-01)\n"
        "\t- also alive (verified 2019-01-01)\n",
    )
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    stale_texts = [f["text"] for f in report["stale"]]
    assert stale_texts.count("double stale thing") == 1


def test_lint_stale_uses_most_recent_verified_date_not_the_first(tmp_path, monkeypatch):
    # This is the regression case that makes audit mode actually work: no
    # operation can edit or remove an existing note, so the only way to
    # re-verify an item during an audit is to append a fresh
    # (verified ...) note. If staleness were decided by the first note
    # found (or the oldest), an item with an old stale note and a new
    # in-window note would stay stuck under `lint --stale` forever, with no
    # in-band way to clear it. Staleness must be decided by the *most
    # recent* verified date.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(
        tmp_path,
        "# tier 1 — quick\n\n"
        "- [ ] re-verified thing\n"
        "\t- alive (verified 2020-01-01)\n"
        "\t- still alive (verified 2026-08-01)\n",
    )
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    stale_texts = [f["text"] for f in report["stale"]]
    assert "re-verified thing" not in stale_texts


def test_lint_stale_still_flags_item_whose_only_note_is_old(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(
        tmp_path,
        "# tier 1 — quick\n\n- [ ] old thing\n\t- alive (verified 2020-01-01)\n",
    )
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    stale_texts = [f["text"] for f in report["stale"]]
    assert "old thing" in stale_texts


def test_lint_stale_does_not_flag_item_with_no_verified_note(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, "# tier 1 — quick\n\n- [ ] never checked thing\n")
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    stale_texts = [f["text"] for f in report["stale"]]
    assert "never checked thing" not in stale_texts


def test_lint_malformed_verified_date_does_not_crash_and_is_reported(
    tmp_path, monkeypatch
):
    # VERIFIED_RE validates digit shape only, so "2026-13-45" matches it
    # even though it isn't a real calendar date. Before the fix,
    # date.fromisoformat raised ValueError here and took down the whole
    # (read-only) lint command over one typo'd marker.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(
        tmp_path,
        "# tier 1 — quick\n\n- [ ] bad date thing\n\t- alive (verified 2026-13-45)\n",
    )
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    assert "bad date thing" in [f["text"] for f in report["malformed_dates"]]


def test_lint_malformed_only_date_is_not_stale(tmp_path, monkeypatch):
    # An item whose *only* verified note is malformed has no usable
    # verification date, so it must not be reported stale -- we genuinely
    # don't know when it was verified, same as an item with no note at all.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(
        tmp_path,
        "# tier 1 — quick\n\n- [ ] bad date thing\n\t- alive (verified 2026-13-45)\n",
    )
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    assert "bad date thing" not in [f["text"] for f in report["stale"]]


def test_lint_malformed_plus_fresh_date_is_not_stale_but_still_flagged(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(
        tmp_path,
        "# tier 1 — quick\n\n"
        "- [ ] mixed dates thing\n"
        "\t- bad note (verified 2026-13-45)\n"
        "\t- good note (verified 2026-08-01)\n",
    )
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    assert "mixed dates thing" not in [f["text"] for f in report["stale"]]
    assert "mixed dates thing" in [f["text"] for f in report["malformed_dates"]]


def test_lint_malformed_plus_stale_date_is_stale(tmp_path, monkeypatch):
    # The malformed note must be ignored, not treated as a fresh
    # verification that would mask a genuinely stale valid date.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(
        tmp_path,
        "# tier 1 — quick\n\n"
        "- [ ] mixed stale thing\n"
        "\t- bad note (verified 2026-13-45)\n"
        "\t- old note (verified 2020-01-01)\n",
    )
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    assert "mixed stale thing" in [f["text"] for f in report["stale"]]


def test_lint_existing_categories_unchanged_by_malformed_dates_addition(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, LINTABLE)
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    assert any("2026-09-14" in f["text"] for f in report["dated"])
    assert [f["text"] for f in report["fragments"]] == ["batteries?"]
    texts = [f["text"] for f in report["research_candidates"]]
    assert "check out [thing](https://example.com)" in texts
    assert "plain idea with no link" not in texts
    stale = [f["text"] for f in report["stale"]]
    assert "researched thing" in stale
    assert "fresh thing" not in stale
    assert report["malformed_dates"] == []


def test_lint_skips_closed_items_entirely(tmp_path, monkeypatch):
    # A checked item that would otherwise trip research_candidates (it has
    # a link) must not appear in any report list -- closed items are not
    # lint subjects.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(
        tmp_path,
        "# tier 1 — quick\n\n- [x] check out [thing](https://example.com)\n",
    )
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    for entries in report.values():
        assert entries == []


def test_lint_nominates_flagged_items_with_no_link(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(
        tmp_path,
        "# tier 1 — quick\n\n"
        "- [ ] plain flagged idea\n"
        "\t- needs-research (2026-08-01): is this real?\n",
    )
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    texts = [f["text"] for f in report["research_candidates"]]
    assert "plain flagged idea" in texts


def test_lint_cli_json_output(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, LINTABLE)
    rc = someday.main(
        ["lint", "--json", "--today", "2026-08-04", "--stale-days", "180"]
    )
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert set(data.keys()) == {
        "dated",
        "fragments",
        "untiered",
        "research_candidates",
        "stale",
        "malformed_dates",
    }
    assert any("2026-09-14" in f["text"] for f in data["dated"])


def test_distinctive_terms_breaks_ties_alphabetically():
    # Regression test for a hash-randomization bug: content_words returns a
    # set, so without a tie-break on the word text itself, ties on
    # (corpus_count, -len(word)) resolved via Python's hash-randomized set
    # iteration order -- the same input produced a different top-3 (and thus
    # a different done-check result) from one process to the next, measured
    # as 20/19/19 candidates across three runs on an unchanged real vault.
    # All four words below tie on count (absent from corpus_counts, so 0)
    # and length (5), so only alphabetical order can decide the top three --
    # this fails if the tie-break key is ever removed, regardless of which
    # process or hash seed runs it.
    item = someday.Item(text="zebra olive mango grape")
    assert someday.distinctive_terms(item, {}) == ["grape", "mango", "olive"]


def test_done_check_finds_item_present_in_archive(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(
        tmp_path,
        "# tier 1 — quick\n\n- [ ] build a mermaid rendering web component for my blog\n- [ ] something entirely unrelated to anything\n",
    )
    _seed(
        tmp_path,
        "- [x] Wrapping Mermaid Diagrams in a Web Component\n",
        "someday-done.md",
    )
    rc = someday.main(["done-check", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    texts = [c["text"] for c in data["candidates"]]
    assert "build a mermaid rendering web component for my blog" in texts
    assert "something entirely unrelated to anything" not in texts
    hit = next(c for c in data["candidates"] if "mermaid" in c["text"])
    assert set(hit["matched"]) >= {"mermaid", "component"}
    assert "mermaid" in hit["evidence"]["line"].lower()
    assert "component" in hit["evidence"]["line"].lower()


def test_done_check_does_not_nominate_terms_split_across_lines(
    tmp_path, monkeypatch, capsys
):
    # distinctive_terms for this item are ["rendering", "component", "mermaid"]
    # (verified above). Each appears somewhere in the archive, but no single
    # line ever has two of them together -- the co-occurrence requirement
    # must reject this, where the old blob-matching approach would have
    # nominated it.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(
        tmp_path,
        "# tier 1 — quick\n\n- [ ] build a mermaid rendering web component for my blog\n",
    )
    _seed(
        tmp_path,
        "- [x] finished the mermaid diagram thing\n"
        "- [x] separately built a nice web component elsewhere\n"
        "- [x] rendering pipeline notes for something else\n",
        "someday-done.md",
    )
    rc = someday.main(["done-check", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    texts = [c["text"] for c in data["candidates"]]
    assert "build a mermaid rendering web component for my blog" not in texts


def test_done_check_searches_extra_dirs(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, "# tier 1 — quick\n\n- [ ] wayback machine link fixer\n")
    _seed(tmp_path, "nothing here\n", "someday-done.md")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "notes.md").write_text(
        "finished the wayback machine link fixer last week\n"
    )
    rc = someday.main(["done-check", "--repos", str(repo), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert any("wayback" in c["text"] for c in data["candidates"])


def test_done_check_excludes_the_skills_own_directory(tmp_path, monkeypatch, capsys):
    # SKILL.md and README.md quote real item text as examples, and
    # fixtures/sample.md is real item text -- so a `--repos ~/devel` audit
    # (the documented path, and this repo lives under ~/devel) let the tool
    # "confirm" an item against the skill's own prose. Same self-confirmation
    # failure mode DONE_CHECK_SKIP_DIRS exists to close, reopened by the
    # skill's own docs. Measured before the fix: 4 self-matches in this repo
    # alone, 2 from SKILL.md and 2 from fixtures/sample.md.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, "# tier 1 — quick\n\n- [ ] get a vectrex flash card\n")
    _seed(tmp_path, "nothing here\n", "someday-done.md")
    skill_root = Path(someday.__file__).resolve().parents[1]
    # Guard the premise: if SKILL.md stops quoting this item the test would
    # pass for the wrong reason.
    assert "flash card" in (skill_root / "SKILL.md").read_text(encoding="utf-8")
    rc = someday.main(["done-check", "--repos", str(skill_root), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["candidates"] == []


@pytest.mark.parametrize(
    "skipped_relpath",
    [
        ".git/README.md",
        "node_modules/pkg/README.md",
        ".superpowers/sdd/plan/notes.md",
        ".venv/lib/site-packages/pkg/README.md",
        "venv/lib/site-packages/pkg/README.md",
        "dist/README.md",
        "build/README.md",
        "__pycache__/README.md",
        ".tox/py313/README.md",
        "docs/dev-sessions/2026-01-01-thing/notes.md",
    ],
)
def test_done_check_skips_self_confirmation_dirs(
    tmp_path, monkeypatch, capsys, skipped_relpath
):
    # A prior real-vault run found the tool matching its own dev-session
    # reports living inside the scanned tree -- pure self-confirmation, not
    # evidence. This pins that each of the excluded directories is actually
    # excluded, not merely documented.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, "# tier 1 — quick\n\n- [ ] wayback machine link fixer\n")
    _seed(tmp_path, "nothing here\n", "someday-done.md")
    repo = tmp_path / "repo"
    skipped_file = repo / skipped_relpath
    skipped_file.parent.mkdir(parents=True)
    skipped_file.write_text("finished the wayback machine link fixer last week\n")
    rc = someday.main(["done-check", "--repos", str(repo), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["candidates"] == []


def test_status_json_lists_open_intake_items_with_ids(tmp_path, monkeypatch, capsys):
    # The documented intake flow is "read the intake items, then emit
    # place/retitle/annotate ops against them" -- which needs ids for
    # *ordinary* items. lint/dupes/done-check only ever emit ids for items
    # that trip a category or match something, so a plain checkbox line with
    # no URL, no date and no duplicate had an id nothing printed, and the
    # skill's main mode could not be completed at all.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, SAMPLE_WITH_FLAG)
    rc = someday.main(["status", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    doc, _ = someday.load(src)
    expected = [
        {"id": i.id, "text": i.text}
        for i in doc.sections[0].items
        if i.checked is not True
    ]
    assert data["intake_items"] == expected
    assert [i["text"] for i in data["intake_items"]] == ["new idea one", "new idea two"]
    assert data["intake"] == len(data["intake_items"])


def test_status_intake_items_skip_closed_items(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, "# intake\n\n- [ ] still open\n- [x] already handled\n")
    rc = someday.main(["status", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert [i["text"] for i in data["intake_items"]] == ["still open"]


def test_status_intake_ids_are_the_ids_apply_accepts(tmp_path, monkeypatch, capsys):
    # End-to-end proof that the primary workflow closes: take an id straight
    # from `status --json`, file a `place` op against it, and have `apply`
    # accept it. Ids are content hashes and must never be guessed by hand --
    # this item's mixed case and doubled space are exactly what a naive guess
    # gets wrong.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(
        tmp_path,
        "# intake\n\n- [ ] A  Plain Intake Item\n\n# tier 1 — quick\n\n## misc\n\n"
        "- [ ] existing thing\n",
    )
    assert someday.main(["status", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    target = data["intake_items"][0]["id"]
    plan = _plan(
        tmp_path,
        [
            {
                "op": "place",
                "item": target,
                "bucket": "tier 1 — quick",
                "cluster": "misc",
            }
        ],
    )
    assert someday.main(["apply", str(plan)]) == 0
    out = src.read_text()
    assert out.index("existing thing") < out.index("A  Plain Intake Item")


def test_status_json_lists_completed_items_with_ids(tmp_path, monkeypatch, capsys):
    # Mirrors test_status_json_lists_open_intake_items_with_ids: a checked
    # item needs a published id too, or a sweep step has nothing to file an
    # `archive` op against. Collected across the whole file, not just
    # intake, and in document order.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(
        tmp_path,
        "# intake\n\n- [ ] still open\n\n"
        "# tier 1 — quick\n\n"
        "- [x] finished thing one\n- [ ] not finished\n- [x] finished thing two\n",
    )
    rc = someday.main(["status", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    doc, _ = someday.load(src)
    expected = [
        {"id": i.id, "text": i.text}
        for s in doc.sections
        for i in s.items
        if i.checked is True
    ]
    assert data["completed_items"] == expected
    assert [i["text"] for i in data["completed_items"]] == [
        "finished thing one",
        "finished thing two",
    ]
    assert data["completed"] == len(data["completed_items"])


def test_status_completed_items_empty_when_nothing_checked(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, BASIC)
    rc = someday.main(["status", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["completed_items"] == []
    assert data["completed"] == 0
    assert data["open_total"] == 2


def test_status_human_readable_reports_completed(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, "# tier 1 — quick\n\n- [x] finished thing\n- [ ] open thing\n")
    rc = someday.main(["status"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "completed: 1" in out


def test_apply_rejects_op_sequenced_after_its_item_was_archived(
    tmp_path, monkeypatch, capsys
):
    # The note went to NEITHER file before this check: archive_entry had
    # already snapshotted the item's lines, and the item was detached from
    # doc, so serialize never rendered its added_notes. Exit 0, "1 archived,
    # 0 unaccounted" -- all three existing guards are blind to it, because
    # nothing about item identity is wrong; the plan simply asked for
    # something in an order that cannot be honoured.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    archive = _seed(tmp_path, "Completed items from [[someday]]\n", "someday-done.md")
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path,
        [
            {"op": "archive", "item": target, "reason": "closed"},
            {"op": "annotate", "item": target, "notes": ["THIS SHOULD NOT VANISH"]},
        ],
    )
    before_src = src.read_text()
    before_archive = archive.read_text()
    rc = someday.main(["apply", str(plan)])
    err = capsys.readouterr().err
    assert rc == 2
    assert target in err
    assert "op 0" in err and "op 1" in err
    assert src.read_text() == before_src
    assert archive.read_text() == before_archive


def test_apply_rejects_op_referencing_an_item_a_merge_removed(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    _seed(tmp_path, "Completed items from [[someday]]\n", "someday-done.md")
    doc, _ = someday.load(src)
    items = {i.text: i for s in doc.sections for i in s.items}
    winner = items["Led strip for under bar"].id
    loser = items["led strip for UNDER bar"].id
    plan = _plan(
        tmp_path,
        [
            {"op": "merge", "into": winner, "from": [loser]},
            {"op": "annotate", "item": loser, "notes": ["THIS SHOULD NOT VANISH"]},
        ],
    )
    before = src.read_text()
    rc = someday.main(["apply", str(plan)])
    err = capsys.readouterr().err
    assert rc == 2
    assert loser in err
    assert src.read_text() == before


def test_apply_rejects_the_same_item_archived_twice(tmp_path, monkeypatch, capsys):
    # Two archive ops on one item wrote TWO entries to someday-done.md under
    # two contradictory reason headings while reporting "1 archived, 0
    # unaccounted": the origin is gone from doc and recorded removed, so
    # reconcile passes; it isn't live, so the duplication check passes; the
    # source file is correct, so the serializer check passes.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    archive = _seed(tmp_path, "Completed items from [[someday]]\n", "someday-done.md")
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path,
        [
            {"op": "archive", "item": target, "reason": "closed"},
            {"op": "archive", "item": target, "reason": "done"},
        ],
    )
    before_archive = archive.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc == 2
    assert target in capsys.readouterr().err
    assert archive.read_text() == before_archive
    assert "dead on arrival thing" in src.read_text()


def test_archive_entry_count_must_match_removed_origins(tmp_path, monkeypatch, capsys):
    # Deliberately independent of the pre-flight ordering check above. The
    # pre-flight refuses a malformed *plan*; this invariant catches a future
    # *code* bug that produces the same corruption (two archive entries, one
    # removed origin) from a plan the pre-flight considers fine. Neutering
    # _validate_op_ordering simulates exactly that: the bug is now inside the
    # tool, not in the plan, and the count invariant is the only guard left.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    archive = _seed(tmp_path, "Completed items from [[someday]]\n", "someday-done.md")
    doc, _ = someday.load(src)
    target = doc.sections[0].items[0].id
    plan = _plan(
        tmp_path,
        [
            {"op": "archive", "item": target, "reason": "closed"},
            {"op": "archive", "item": target, "reason": "done"},
        ],
    )
    monkeypatch.setattr(someday, "_validate_op_ordering", lambda ops: None)
    before_src = src.read_text()
    before_archive = archive.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc == 3
    assert "archive entr" in capsys.readouterr().err
    assert src.read_text() == before_src
    assert archive.read_text() == before_archive


@pytest.mark.parametrize(
    "build_ops",
    [
        lambda ids: [
            {"op": "flag", "item": ids["dead on arrival thing"], "question": "still?"},
            {"op": "archive", "item": ids["dead on arrival thing"], "reason": "closed"},
        ],
        lambda ids: [
            {"op": "annotate", "item": ids["led strip for UNDER bar"], "notes": ["n"]},
            {
                "op": "merge",
                "into": ids["Led strip for under bar"],
                "from": [ids["led strip for UNDER bar"]],
            },
        ],
        lambda ids: [
            {
                "op": "merge",
                "into": ids["Led strip for under bar"],
                "from": [ids["led strip for UNDER bar"]],
            },
            {"op": "annotate", "item": ids["Led strip for under bar"], "notes": ["n"]},
        ],
    ],
    ids=["flag-then-archive", "annotate-then-merge", "merge-then-annotate-winner"],
)
def test_apply_allows_legitimate_orderings_around_a_removing_op(
    tmp_path, monkeypatch, build_ops
):
    # The ordering check must reject only what cannot be honoured. Touching
    # an item *before* it is removed is fine (the edit reaches the archive
    # entry), and so is touching the surviving winner of a merge either side
    # of the merge itself.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    _seed(tmp_path, "Completed items from [[someday]]\n", "someday-done.md")
    doc, _ = someday.load(src)
    ids = {i.text: i.id for s in doc.sections for i in s.items}
    plan = _plan(tmp_path, build_ops(ids))
    assert someday.main(["apply", str(plan), "--today", "2026-08-04"]) == 0


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"op": "annotate", "notes": "first step: buy it"}, "notes"),
        ({"op": "annotate", "notes": ["fine", 7]}, "notes"),
        ({"op": "retitle", "text": 42}, "text"),
        ({"op": "flag", "question": ["a", "b"]}, "question"),
        ({"op": "place", "bucket": 3}, "bucket"),
        ({"op": "place", "bucket": "tier 1 — quick", "cluster": 3}, "cluster"),
        ({"op": "archive", "reason": ["closed"]}, "reason"),
        ({"op": "archive", "reason": "closed", "note": 9}, "note"),
    ],
    ids=[
        "notes-string",
        "notes-non-string-member",
        "text-int",
        "question-list",
        "bucket-int",
        "cluster-int",
        "reason-list",
        "note-int",
    ],
)
def test_apply_rejects_wrong_payload_types(
    tmp_path, monkeypatch, capsys, payload, field
):
    # A bare string where a list belongs is a plausible model slip and the
    # most dangerous of these: list.extend spreads it one character per
    # bullet, so `"notes": "first step: buy it"` wrote 18 one-character
    # bullets, exit 0, 0 unaccounted -- a corrupt write that reconciles
    # clean, because item identity is untouched. `"text": 42` writes
    # `- [ ] 42`. Refuse, don't write.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    doc, _ = someday.load(src)
    op = dict(payload)
    op["item"] = doc.sections[0].items[0].id
    plan = _plan(tmp_path, [op])
    before = src.read_text()
    rc = someday.main(["apply", str(plan)])
    err = capsys.readouterr().err
    assert rc == 2
    assert field in err
    assert src.read_text() == before


def test_apply_rejects_merge_from_that_is_not_a_list(tmp_path, monkeypatch, capsys):
    # Worse than a wrong type: `refs()` iterates a string character by
    # character, so the unknown-id check would report single letters and a
    # one-element "from" spelled as a bare id would silently archive nothing.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    doc, _ = someday.load(src)
    items = {i.text: i for s in doc.sections for i in s.items}
    plan = _plan(
        tmp_path,
        [
            {
                "op": "merge",
                "into": items["Led strip for under bar"].id,
                "from": items["led strip for UNDER bar"].id,
            }
        ],
    )
    before = src.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc == 2
    assert "from" in capsys.readouterr().err
    assert src.read_text() == before


@pytest.mark.parametrize(
    "remove, expected_rc",
    [("false", 2), (1, 2), (True, 0), (False, 0)],
    ids=["string-false", "int-one", "real-true", "real-false"],
)
def test_apply_validates_the_remove_flag_as_a_bool(
    tmp_path, monkeypatch, capsys, remove, expected_rc
):
    # `remove` was the one field cmd_apply reads that nothing type-checked,
    # and it is consumed as bare truthiness: `"remove": "false"` (or `1`) is
    # truthy, so apply_flag took the removal branch -- deleting the item's
    # existing needs-research note, writing no replacement, exit 0, "0
    # unaccounted". Same class as the notes-as-a-string corruption: a write
    # that reconciles clean because item identity is untouched. isinstance
    # against bool is what separates these from a real true/false, since
    # isinstance(1, bool) is False while isinstance(True, int) is True.
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, SAMPLE_WITH_FLAG)
    doc, _ = someday.load(src)
    flagged = next(i for i in someday.open_items(doc) if someday.is_flagged(i))
    plan = _plan(
        tmp_path,
        [
            {
                "op": "flag",
                "item": flagged.id,
                "remove": remove,
                "question": "newer question?",
            }
        ],
    )
    before = src.read_text()
    rc = someday.main(["apply", str(plan), "--today", "2026-08-04"])
    assert rc == expected_rc
    if expected_rc == 2:
        assert "remove" in capsys.readouterr().err
        assert src.read_text() == before
        assert "is it maintained?" in src.read_text()
    elif remove:
        assert "needs-research" not in src.read_text()
    else:
        assert "needs-research (2026-08-04): newer question?" in src.read_text()


def test_apply_rejects_a_non_object_op(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, MERGEABLE)
    plan = _plan(tmp_path, ["archive that thing"])
    before = src.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc == 2
    assert src.read_text() == before
