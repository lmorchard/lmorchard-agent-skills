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
