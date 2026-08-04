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
from datetime import date
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
    added_notes: list[str] = field(default_factory=list)
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
    """Regenerate only the item's own line; everything else is passed
    through verbatim. `item.raw` may hold content `parse` never modelled
    as a note or tail line (continuations, deeper-nested bullets), and
    reconstructing from the parsed fields alone would silently drop it.
    """
    box = "" if item.checked is None else ("[x] " if item.checked else "[ ] ")
    lines = [f"- {box}{item.text}"]
    lines.extend(item.raw[1:])
    lines.extend(f"\t- {note}" for note in item.added_notes)
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
    text = path.read_text(encoding="utf-8")
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


class PlanError(Exception):
    pass


def index_items(doc: Document) -> dict[str, Item]:
    return {i.id: i for s in doc.sections for i in s.items}


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    try:
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def live_origins(doc: Document) -> set[int]:
    return {i.origin for s in doc.sections for i in s.items}


def reconcile(
    before_origins: set[int], doc: Document, removed_origins: set[int]
) -> set[int]:
    """Origins present before but neither still present nor deliberately removed."""
    return before_origins - live_origins(doc) - removed_origins


def apply_annotate(item: Item, notes: list[str]) -> None:
    item.added_notes.extend(notes)
    item.dirty = True


def apply_retitle(item: Item, text: str) -> None:
    item.text = text
    item.dirty = True


def _note_text(line: str) -> str | None:
    """Extract note content from a raw line, mirroring the stripping `parse`
    does when it collects notes. Returns None for lines that aren't bullets
    (continuations, deeper structure `parse` doesn't otherwise model)."""
    stripped = line.strip()
    return stripped[2:] if stripped.startswith("- ") else None


def _is_flag_line(line: str) -> bool:
    text = _note_text(line)
    return text is not None and bool(FLAG_RE.match(text))


def apply_flag(item: Item, question: str, remove: bool, today: str) -> None:
    # flag is the only op allowed to remove an original line: it drops the
    # old flag note (if any) from raw, keeping `notes` in sync so
    # `is_flagged` stays honest, and appends the new flag via added_notes
    # like every other op. added_notes must be filtered too, not just raw
    # and notes -- a second flag op in the same plan only ever appends to
    # added_notes, so an unfiltered added_notes would let a prior flag from
    # earlier in the same plan survive alongside the new one.
    item.raw = [item.raw[0]] + [
        line for line in item.raw[1:] if not _is_flag_line(line)
    ]
    item.notes = [n for n in item.notes if not FLAG_RE.match(n)]
    item.added_notes = [n for n in item.added_notes if not FLAG_RE.match(n)]
    if not remove:
        item.added_notes.append(f"needs-research ({today}): {question}")
    item.dirty = True


def find_section(
    doc: Document, bucket: str, cluster: str | None, allow_new: bool
) -> Section:
    """Locate the tier bucket (level-1) named `bucket`, then within it the
    cluster (level-2) named `cluster`. Matching is by exact title string --
    no fuzzy matching, no case folding. A missing bucket is always an error;
    tiers are a fixed taxonomy. A missing cluster is an error unless
    `allow_new`, in which case one is created at the end of the bucket's
    cluster run (just before the next level-1 heading), so a new cluster
    never jumps ahead of existing ones.
    """
    bucket_idx = next(
        (n for n, s in enumerate(doc.sections) if s.level == 1 and s.title == bucket),
        None,
    )
    if bucket_idx is None:
        raise PlanError(f"unknown bucket: {bucket}")
    if cluster is None:
        return doc.sections[bucket_idx]

    for section in doc.sections[bucket_idx + 1 :]:
        if section.level == 1:
            break
        if section.title == cluster:
            return section

    if not allow_new:
        raise PlanError(
            f"unknown cluster: {cluster} (use --allow-new-clusters to create it)"
        )

    insert_at = bucket_idx + 1
    while insert_at < len(doc.sections) and doc.sections[insert_at].level != 1:
        insert_at += 1
    created = Section(level=2, title=cluster, raw_heading=f"## {cluster}", body=[""])
    doc.sections.insert(insert_at, created)
    return created


def _detach(doc: Document, item: Item) -> None:
    """Remove `item` from whichever section holds it. `item.tail` is
    section context (interstitial prose or blank padding) that happens to
    sit after this item, not part of the item, so it does not travel: it is
    left behind, appended to the preceding item's tail, or -- if the item
    was first in its section -- to the section's body. `Section.footer` is
    never touched here; it belongs to the section, not any item. Shared by
    every op that takes an item out of its section outright (place,
    archive, merge) so this transfer rule lives in exactly one place.
    """
    for section in doc.sections:
        if item in section.items:
            idx = section.items.index(item)
            if item.tail:
                if idx > 0:
                    section.items[idx - 1].tail.extend(item.tail)
                else:
                    section.body.extend(item.tail)
                item.tail = []
            section.items.remove(item)
            return


def apply_place(
    doc: Document, item: Item, bucket: str, cluster: str | None, allow_new: bool
) -> None:
    """Move `item` out of its current section into the bucket/cluster named.
    The item keeps its `origin` (identity) and `dirty` stays False, so its
    original lines are emitted verbatim in the new location -- moving must
    not rewrite text. The destination gets the item with an empty tail of
    its own; see `_detach` for what happens to the tail it leaves behind.
    """
    # Resolve the destination before touching the source. find_section can
    # raise PlanError (unknown bucket, or unknown cluster without
    # allow_new); if that happens after the item was already detached from
    # its source section, it would be orphaned -- present in no section at
    # all. Doing this lookup first means a failure here leaves `doc`
    # untouched except, possibly, for a newly created empty cluster (when
    # allow_new is true) -- a far milder side effect than losing an item,
    # so don't "fix" this back to removing the item first.
    destination = find_section(doc, bucket, cluster, allow_new)
    _detach(doc, item)
    destination.items.append(item)


ARCHIVE_SECTIONS = {
    "done": "done",
    "missed": "missed",
    "closed": "closed by research",
    "routed": "routed elsewhere",
    "merged": "collapsed duplicates",
}
APPROVAL_REASONS = frozenset({"done", "closed", "missed"})


def archive_entry(item: Item, note: str) -> list[str]:
    """Render `item` as archive lines: its text, then its original notes
    (excluding needs-research flag lines -- a stale research question is
    noise in an archive), then any added_notes it picked up earlier in the
    same plan, then the op's `note` if present. This never touches
    `item.tail`; tail is section context handled by `_detach`, not archive
    content.
    """
    lines = [f"- {item.text}"]
    lines.extend(f"\t- {n}" for n in item.notes if not FLAG_RE.match(n))
    lines.extend(f"\t- {n}" for n in item.added_notes)
    if note:
        lines.append(f"\t- {note}")
    return lines


def append_archive(path: Path, groups: dict[str, list[list[str]]], today: str) -> None:
    """Append a dated `# triage <today>` section to the archive file, with
    one `## <heading>` subsection per reason. Reads existing content and
    writes once via `atomic_write` -- the archive holds years of history,
    so this must never clobber it.
    """
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    parts = [existing.rstrip("\n"), "", f"# triage {today}", ""]
    for reason, entries in groups.items():
        parts.append(f"## {ARCHIVE_SECTIONS[reason]}")
        parts.append("")
        for entry in entries:
            parts.extend(entry)
        parts.append("")
    atomic_write(path, "\n".join(parts).lstrip("\n") + "\n")


IN_PLACE_OPS = {"annotate", "retitle", "flag"}
MOVE_OPS = {"place", "archive", "merge"}


def cmd_apply(args) -> int:
    src = source_path()
    doc, text = load(src)
    items = index_items(doc)

    # A model-authored plan is exactly the input most likely to be
    # malformed: invalid JSON, a missing "op"/"item" key, a non-dict op, an
    # op missing "notes"/"text". None of that is a data-loss path (nothing
    # has been written yet), but it should still refuse cleanly with exit 2
    # rather than crash with a traceback and exit 1.
    try:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        if plan.get("digest") != digest(text):
            print(
                f"stale plan: source digest is {digest(text)}, plan expects "
                f"{plan.get('digest')}. Re-snapshot and rebuild the plan.",
                file=sys.stderr,
            )
            return 2

        ops = plan.get("ops", [])

        def refs(op: dict) -> list[str]:
            # merge names its ids via "into"/"from" rather than "item"; this
            # has to cover all three or a merge naming a nonexistent id
            # slips past this check and KeyErrors in the op loop instead of
            # returning exit 2.
            out = []
            if op.get("item"):
                out.append(op["item"])
            if op.get("into"):
                out.append(op["into"])
            out.extend(op.get("from", []))
            return out

        unknown = sorted({r for op in ops for r in refs(op) if r not in items})
        if unknown:
            print(f"unknown item ids: {', '.join(unknown)}", file=sys.stderr)
            return 2

        today = args.today or date.today().isoformat()
        before_origins = live_origins(doc)
        removed_origins: set[int] = set()
        archived: dict[str, list[list[str]]] = {}

        def drop(item: Item) -> None:
            _detach(doc, item)

        for op in ops:
            kind = op["op"]
            if kind not in IN_PLACE_OPS and kind not in MOVE_OPS:
                print(f"unsupported op: {kind}", file=sys.stderr)
                return 2
            if kind == "place":
                item = items[op["item"]]
                apply_place(
                    doc, item, op["bucket"], op.get("cluster"), args.allow_new_clusters
                )
            elif kind == "annotate":
                item = items[op["item"]]
                apply_annotate(item, op["notes"])
            elif kind == "retitle":
                item = items[op["item"]]
                apply_retitle(item, op["text"])
            elif kind == "flag":
                item = items[op["item"]]
                apply_flag(item, op.get("question", ""), op.get("remove", False), today)
            elif kind == "archive":
                item = items[op["item"]]
                reason = op["reason"]
                if reason not in ARCHIVE_SECTIONS:
                    raise PlanError(f"unknown archive reason: {reason}")
                archived.setdefault(reason, []).append(
                    archive_entry(item, op.get("note", ""))
                )
                removed_origins.add(item.origin)
                drop(item)
            elif kind == "merge":
                # The winner stays in place, untouched apart from the
                # optional note. Each loser is archived under "merged" and
                # removed_origins records its origin -- never its id, which
                # is a content hash that would change under retitle.
                winner = items[op["into"]]
                note = op.get("note", "")
                for ref in op["from"]:
                    loser = items[ref]
                    archived.setdefault("merged", []).append(
                        archive_entry(loser, f"merged into: {winner.text}")
                    )
                    removed_origins.add(loser.origin)
                    drop(loser)
                if note:
                    apply_annotate(winner, [note])
    except json.JSONDecodeError as e:
        print(f"invalid plan JSON: {e}", file=sys.stderr)
        return 2
    except PlanError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (KeyError, TypeError, AttributeError) as e:
        print(f"malformed plan: {e}", file=sys.stderr)
        return 2

    # Two independent checks. The first is a set difference on `origin`
    # (deliberately: it must catch an origin present before but neither
    # still present nor deliberately removed, which a count alone could
    # mask). The second proves the serializer emitted something that parses
    # back to the same population, compared by item *count*, not set
    # cardinality, so a bug that leaves one `Item` reachable from two places
    # can't cancel out against a serializer bug that drops one.
    surviving = live_origins(doc)
    lost = reconcile(before_origins, doc, removed_origins)
    if lost:
        print(
            f"reconciliation failed: {len(lost)} item(s) vanished "
            f"(origins: {sorted(lost)})",
            file=sys.stderr,
        )
        return 3

    out = serialize(doc)
    reparsed = parse(out)
    reparsed_count = sum(len(s.items) for s in reparsed.sections)
    live_count = sum(len(s.items) for s in doc.sections)
    if reparsed_count != live_count:
        print(
            f"serializer check failed: {live_count} items in memory but "
            f"{reparsed_count} after re-parsing the output",
            file=sys.stderr,
        )
        return 3

    print(
        f"reconciled: {len(before_origins)} in, {len(surviving)} remaining, "
        f"{len(removed_origins)} archived, 0 unaccounted"
    )
    if args.dry_run:
        print("--- dry run, no write ---")
        print(out)
        return 0

    # Archive FIRST, then the source. If the second write fails, the item
    # exists in BOTH files -- visible and trivially fixable. The reverse
    # order would leave it in NEITHER, which is the exact failure this
    # design exists to prevent. Never reorder these two calls.
    if archived:
        append_archive(archive_path(), archived, today)
        print(f"appended {len(removed_origins)} to {archive_path()}")
    atomic_write(src, out)
    print(f"wrote {src}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="someday", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="counts for intake, queue, and buckets")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    p_apply = sub.add_parser(
        "apply", help="apply a JSON plan (the only mutating command)"
    )
    p_apply.add_argument("plan")
    p_apply.add_argument("--dry-run", action="store_true")
    p_apply.add_argument("--today", default="", help="override date (testing)")
    p_apply.add_argument("--allow-new-clusters", action="store_true")
    p_apply.set_defaults(func=cmd_apply)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
