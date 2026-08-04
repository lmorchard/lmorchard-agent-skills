#!/usr/bin/env python3
"""someday — mechanical triage operations for pages/someday.md."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

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
    tail: list[str] = field(default_factory=list)
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
    lines.extend(item.tail)
    return lines


def _close_section(section: Section | None) -> None:
    """Promote a trailing item's tail to the section footer, if it's more
    than blank padding. A footer describes the section, not the item it
    happened to follow, so it must not travel with that item if a later task
    moves the item elsewhere. Pure blank padding has nothing worth promoting
    and is left where it is.
    """
    if section is None or not section.items:
        return
    last = section.items[-1]
    if any(line != "" for line in last.tail):
        section.footer = last.tail
        last.tail = []


def parse(text: str) -> Document:
    doc = Document()
    lines = text.split("\n")
    # A trailing newline yields a final empty element; keep it for fidelity.
    trailing = lines.pop() if lines and lines[-1] == "" else None
    section: Section | None = None
    item: Item | None = None
    next_origin = 0

    for line in lines:
        heading = HEADING_RE.match(line)
        if heading:
            _close_section(section)
            section = Section(
                level=len(heading.group(1)),
                title=heading.group(2),
                raw_heading=line,
            )
            doc.sections.append(section)
            item = None
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
            continue

        if item is not None:
            if INDENTED_RE.match(line):
                item.raw.append(line)
                stripped = line.strip()
                if stripped.startswith("- "):
                    item.notes.append(stripped[2:])
            else:
                # Blank or plain unindented lines are positional: they sit
                # right after this item until the next item or heading says
                # otherwise. Keeping them in tail (not raw) preserves that
                # position even if this item is later regenerated dirty.
                item.tail.append(line)
            continue

        if section is None:
            doc.preamble.append(line)
        else:
            section.body.append(line)

    _close_section(section)
    doc.trailing_newline = trailing is not None
    return doc


def serialize(doc: Document) -> str:
    out: list[str] = list(doc.preamble)
    for section in doc.sections:
        out.append(section.raw_heading)
        out.extend(section.body)
        for item in section.items:
            if item.dirty:
                out.extend(render_item(item))
            else:
                out.extend(item.raw)
                out.extend(item.tail)
        out.extend(section.footer)
    text = "\n".join(out)
    if doc.trailing_newline:
        text += "\n"
    return text


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def assign_ids(doc: Document) -> None:
    seen: dict[str, int] = {}
    for section in doc.sections:
        for item in section.items:
            base = hashlib.sha1(normalize(item.text).encode()).hexdigest()[:8]
            seen[base] = seen.get(base, 0) + 1
            item.id = base if seen[base] == 1 else f"{base}-{seen[base]}"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def vault_root() -> Path:
    return Path(
        os.environ.get(
            "SOMEDAY_VAULT", str(Path.home() / "Documents" / "Obsidian" / "main")
        )
    )


def source_path() -> Path:
    return vault_root() / "pages" / "someday.md"


def archive_path() -> Path:
    return vault_root() / "pages" / "someday-done.md"


def load(path: Path) -> tuple[Document, str]:
    text = path.read_text()
    doc = parse(text)
    assign_ids(doc)
    return doc, text


FLAG_RE = re.compile(r"^needs-research \((\d{4}-\d{2}-\d{2})\): (.*)$")
INTAKE_TITLE = "intake"


def is_flagged(item: Item) -> bool:
    return any(FLAG_RE.match(note) for note in item.notes)


def open_items(doc: Document) -> list[Item]:
    return [i for s in doc.sections for i in s.items if i.checked is not True]


def cmd_status(args) -> int:
    doc, text = load(source_path())
    buckets: dict[str, int] = {}
    for section in doc.sections:
        if section.level == 1:
            buckets[section.title] = 0
    current = None
    for section in doc.sections:
        if section.level == 1:
            current = section.title
        if current is not None:
            buckets[current] += sum(1 for i in section.items if i.checked is not True)
    data = {
        "intake": buckets.get(INTAKE_TITLE, 0),
        "needs_research": sum(1 for i in open_items(doc) if is_flagged(i)),
        "open_total": len(open_items(doc)),
        "buckets": {k: v for k, v in buckets.items() if k != INTAKE_TITLE},
        "digest": digest(text),
    }
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"intake: {data['intake']}   needs-research: {data['needs_research']}")
        print(f"open total: {data['open_total']}")
        for name, count in data["buckets"].items():
            print(f"  {count:>4}  {name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="someday", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="counts for intake, queue, and buckets")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
