#!/usr/bin/env python3
"""Turn backticked evidence ids in review drafts into links, in place.

Standard library only. Resolves each id against the cycle's ledger.json and
rewrites it as an Obsidian link (journal, task, digest) or a markdown URL link
(GitHub, Linear, Docs). An id the ledger doesn't know is left as-is and
reported, and the exit status is 1, so this doubles as a grounding check.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

CACHE_ROOT = Path.home() / ".cache" / "review-digest"
# Anything backticked with an evidence prefix is treated as a citation; the ledger,
# not this pattern, decides whether it's valid, so malformed ids get reported.
_ID_RE = re.compile(r"`((?:j|t|sd|gh|lin|doc):[^`\s]+)`")
_UNSAFE_ANCHOR = set("[]|#^")


def _day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}"


def _escape(text: str) -> str:
    return text.replace("[", r"\[").replace("]", r"\]")


def _url_link(label: str, url: str | None) -> str:
    return f"[{_escape(label)}]({url})" if url else label


def link(item: dict, duplicate_heading: bool = False) -> str:
    """`duplicate_heading`: another section that day has the same heading, so an
    anchor would land on the first one; link the day instead."""
    kind = item["id"].split(":", 1)[0]
    path = item["meta"].get("path")
    if kind == "j":
        heading = item["title"]
        whole_day = item["id"].endswith(("#notes", "#til"))
        if whole_day or duplicate_heading or _UNSAFE_ANCHOR & set(heading):
            return f"[[{path}|{_day(item['date'])}]]"
        return f"[[{path}#{heading}|{_day(item['date'])}]]"
    if kind == "t":
        return f"[[{path}|{_day(item['date'])} tasks]]"
    if kind == "sd":
        return f"[[{path}|digest {_day(item['date'])}]]"
    if kind == "gh":
        repo, number = item["id"][3:].split("#")
        return _url_link(f"{repo.split('/')[1]}#{number}", item["url"])
    if kind == "lin":
        return _url_link(item["id"][4:], item["url"])
    return _url_link(item["title"], item["url"])


def link_ids(text: str, items: dict[str, dict]) -> tuple[str, set[str]]:
    """Rewrite backticked ids into links. Inside a markdown table row, the `|` in an
    Obsidian alias would split the cell, so it is escaped there."""
    headings: dict[tuple, int] = {}
    for item in items.values():
        if item["id"].startswith("j:"):
            key = (item["meta"].get("path"), item["title"])
            headings[key] = headings.get(key, 0) + 1
    missing: set[str] = set()

    def linked_line(line: str) -> str:
        in_table = line.lstrip().startswith("|")

        def sub(m: re.Match) -> str:
            item = items.get(m.group(1))
            if item is None:
                missing.add(m.group(1))
                return m.group(0)
            dup = (
                headings[(item["meta"].get("path"), item["title"])] > 1
                if (item["id"].startswith("j:"))
                else False
            )
            linked = link(item, duplicate_heading=dup)
            return linked.replace("|", r"\|") if in_table else linked

        return _ID_RE.sub(sub, line)

    return "\n".join(linked_line(line) for line in text.split("\n")), missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "files", nargs="+", type=Path, help="drafts to rewrite in place"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--cycle", help="e.g. 2026-H2 (cache: ~/.cache/review-digest/<cycle>)"
    )
    group.add_argument("--cache", type=Path, help="cache directory holding ledger.json")
    args = parser.parse_args(argv)

    cache = args.cache or CACHE_ROOT / args.cycle
    ledger = json.loads((cache / "ledger.json").read_text())
    items = {i["id"]: i for i in ledger["items"]}

    missing: set[str] = set()
    for path in args.files:
        text, file_missing = link_ids(path.read_text(), items)
        path.write_text(text)
        missing |= file_missing
    for item_id in sorted(missing):
        print(f"unresolved: {item_id}", file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
