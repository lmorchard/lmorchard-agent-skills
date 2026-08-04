#!/usr/bin/env python3
"""someday — mechanical triage operations for pages/someday.md."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

HEADING_RE = re.compile(r"^(#{1,6}) +(.*)$")
ITEM_RE = re.compile(r"^- (?:\[([ xX])\] )?(.*)$")
INDENTED_RE = re.compile(r"^[ \t]+\S")


@dataclass
class Item:
    id: str = ""
    origin: int = -1
    checked: bool | None = None
    text: str = ""
    notes: list[str] = field(default_factory=list)
    raw: list[str] = field(default_factory=list)
    dirty: bool = False


@dataclass
class Section:
    level: int
    title: str
    raw_heading: str
    body: list[str] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    footer: list[str] = field(default_factory=list)


@dataclass
class Document:
    preamble: list[str] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    trailing_newline: bool = False


def render_item(item: Item) -> list[str]:
    box = "" if item.checked is None else ("[x] " if item.checked else "[ ] ")
    lines = [f"- {box}{item.text}"]
    lines.extend(f"\t- {note}" for note in item.notes)
    return lines


def parse(text: str) -> Document:
    doc = Document()
    lines = text.split("\n")
    # A trailing newline yields a final empty element; keep it for fidelity.
    trailing = lines.pop() if lines and lines[-1] == "" else None
    section: Section | None = None
    item: Item | None = None
    # Once a section's footer has started (a plain line after an item), later
    # lines keep appending to that same footer run — including blank lines —
    # rather than snapping back to the item. This is not lookahead: it only
    # continues a run already in progress, mirroring how an item keeps
    # absorbing its own trailing blank/indented lines.
    in_footer = False
    next_origin = 0

    for line in lines:
        heading = HEADING_RE.match(line)
        if heading:
            section = Section(
                level=len(heading.group(1)),
                title=heading.group(2),
                raw_heading=line,
            )
            doc.sections.append(section)
            item = None
            in_footer = False
            continue

        item_match = ITEM_RE.match(line)
        if item_match and section is not None:
            flag = item_match.group(1)
            item = Item(
                origin=next_origin,
                checked=None if flag is None else flag.lower() == "x",
                text=item_match.group(2),
                raw=[line],
            )
            next_origin += 1
            section.items.append(item)
            in_footer = False
            continue

        if item is not None:
            if not in_footer and (line == "" or INDENTED_RE.match(line)):
                item.raw.append(line)
                stripped = line.strip()
                if stripped.startswith("- "):
                    item.notes.append(stripped[2:])
            else:
                section.footer.append(line)
                in_footer = True
            continue

        if section is None:
            doc.preamble.append(line)
        else:
            section.body.append(line)

    doc.trailing_newline = trailing is not None
    return doc


def serialize(doc: Document) -> str:
    out: list[str] = list(doc.preamble)
    for section in doc.sections:
        out.append(section.raw_heading)
        out.extend(section.body)
        for item in section.items:
            out.extend(render_item(item) if item.dirty else item.raw)
        out.extend(section.footer)
    text = "\n".join(out)
    if doc.trailing_newline:
        text += "\n"
    return text
