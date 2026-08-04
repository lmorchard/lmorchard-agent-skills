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
