#!/usr/bin/env python3
"""laurels — capture and surface work that landed well, as calibration."""

from __future__ import annotations

import argparse
import os
import random
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ENTRY_RE = re.compile(r"^- \[(\d{4}-\d{2}-\d{2})\] \(([^)]*)\) (.*)$")
TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z][a-zA-Z0-9_-]*)")


def store_dir() -> Path:
    return Path(os.environ.get("LAURELS_DIR", str(Path.home() / ".claude" / "laurels")))


def pending_path() -> Path:
    return store_dir() / "pending.md"


def laurels_path() -> Path:
    return store_dir() / "laurels.md"


def archive_path() -> Path:
    return store_dir() / "archive.md"


def extract_tags(text: str) -> list[str]:
    seen: set[str] = set()
    tags: list[str] = []
    for m in TAG_RE.finditer(text):
        tag = m.group(1).lower()
        if tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def normalize_tag(tag: str) -> str:
    cleaned = tag.strip().lstrip("#").lower()
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", cleaned):
        raise ValueError(f"invalid tag '{tag}' (must match ^[a-z][a-z0-9_-]*$)")
    return cleaned


def parse_tag_args(
    tags_arg: list[str] | None, tags_str: str | None = None
) -> list[str]:
    raw_tags: list[str] = []
    if tags_arg:
        raw_tags.extend(tags_arg)
    if tags_str:
        raw_tags.extend(re.split(r"[,\s]+", tags_str))
    res: list[str] = []
    seen: set[str] = set()
    for t in raw_tags:
        t = t.strip()
        if not t:
            continue
        norm = normalize_tag(t)
        if norm not in seen:
            seen.add(norm)
            res.append(norm)
    return res


def project_slug(cwd: str) -> str:
    p = Path(cwd).resolve()
    try:
        out = subprocess.run(
            [
                "git",
                "-C",
                str(p),
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if out:
            common = Path(out)
            p = common.parent if common.name == ".git" else p
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    home = Path.home()
    devel = home / "devel"
    if p.is_relative_to(devel):
        return str(p.relative_to(devel))
    if p.is_relative_to(home):
        return str(p.relative_to(home))
    return p.name


def format_entry(
    when: str, project: str, text: str, tags: list[str] | None = None
) -> str:
    text = " ".join(text.split())
    if tags:
        existing = set(extract_tags(text))
        new_tags = [f"#{t}" for t in tags if t.lower() not in existing]
        if new_tags:
            text = f"{' '.join(new_tags)} {text}"
    return f"- [{when}] ({project}) {text}"


def parse_entry(line: str) -> dict | None:
    m = ENTRY_RE.match(line.rstrip("\n"))
    if not m:
        return None
    text = m.group(3)
    return {
        "date": m.group(1),
        "project": m.group(2),
        "text": text,
        "tags": extract_tags(text),
    }


def read_entries(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text().splitlines():
        parsed = parse_entry(line)
        if parsed:
            entries.append(parsed)
    return entries


def append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(line + "\n")


def cmd_add(args) -> int:
    if args.date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        print(f"invalid --date (expected YYYY-MM-DD): {args.date}", file=sys.stderr)
        return 1
    try:
        tags = parse_tag_args(args.tag, args.tags)
    except ValueError as e:
        print(f"invalid tag: {e}", file=sys.stderr)
        return 1
    when = args.date or date.today().isoformat()
    project = args.project or project_slug(args.cwd or os.getcwd())
    append_line(pending_path(), format_entry(when, project, args.text, tags=tags))
    return 0


def _read_pending_lines() -> list[str]:
    path = pending_path()
    return path.read_text().splitlines() if path.exists() else []


def _write_pending_lines(lines: list[str]) -> None:
    path = pending_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(line + "\n" for line in lines))


def _read_laurels_lines() -> list[str]:
    path = laurels_path()
    return path.read_text().splitlines() if path.exists() else []


def _write_laurels_lines(lines: list[str]) -> None:
    path = laurels_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(line + "\n" for line in lines))


def cmd_pending(args) -> int:
    lines = _read_pending_lines()
    project = (
        None if args.all else (args.project or project_slug(args.cwd or os.getcwd()))
    )
    filter_tag = args.tag.lstrip("#").lower() if args.tag else None
    for i, line in enumerate(lines):
        parsed = parse_entry(line)
        if parsed is None:
            continue
        if project is not None and parsed["project"] != project:
            continue
        if filter_tag is not None and filter_tag not in parsed.get("tags", []):
            continue
        print(f"{i}: [{parsed['date']}] ({parsed['project']}) {parsed['text']}")
    return 0


def _adjudicate(
    indices: list[int],
    accept: bool,
    when: str,
    tags: list[str] | None = None,
) -> int:
    indices = list(dict.fromkeys(indices))
    lines = _read_pending_lines()
    picked = [lines[i] for i in indices if 0 <= i < len(lines)]
    missing = [i for i in indices if not (0 <= i < len(lines))]
    keep = [line for i, line in enumerate(lines) if i not in set(indices)]
    if accept:
        for line in picked:
            parsed = parse_entry(line)
            if parsed:
                append_line(
                    laurels_path(),
                    format_entry(when, parsed["project"], parsed["text"], tags=tags),
                )
    _write_pending_lines(keep)
    if missing:
        print(f"unresolved indices: {sorted(missing)}", file=sys.stderr)
        return 0 if picked else 1
    return 0


def cmd_accept(args) -> int:
    try:
        tags = parse_tag_args(args.tag, args.tags)
    except ValueError as e:
        print(f"invalid tag: {e}", file=sys.stderr)
        return 1
    return _adjudicate(
        args.index,
        accept=True,
        when=args.date or date.today().isoformat(),
        tags=tags,
    )


def cmd_drop(args) -> int:
    return _adjudicate(args.index, accept=False, when="")


def cmd_list(args) -> int:
    lines = _read_laurels_lines()
    project = (
        None if args.all else (args.project or project_slug(args.cwd or os.getcwd()))
    )
    filter_tag = args.tag.lstrip("#").lower() if args.tag else None
    for i, line in enumerate(lines):
        parsed = parse_entry(line)
        if parsed is None:
            continue
        if project is not None and parsed["project"] != project:
            continue
        if filter_tag is not None and filter_tag not in parsed.get("tags", []):
            continue
        print(f"{i}: [{parsed['date']}] ({parsed['project']}) {parsed['text']}")
    return 0


def cmd_tags(args) -> int:
    entries = read_entries(laurels_path())
    project = (
        None if args.all else (args.project or project_slug(args.cwd or os.getcwd()))
    )
    if project is not None:
        entries = [e for e in entries if e["project"] == project]
    counts: dict[str, int] = {}
    untagged = 0
    for e in entries:
        tags = e.get("tags", [])
        if not tags:
            untagged += 1
        for t in tags:
            counts[t] = counts.get(t, 0) + 1
    if not counts and untagged == 0:
        return 0
    sorted_tags = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    for tag, count in sorted_tags:
        print(f"#{tag} ({count})")
    if untagged:
        print(f"untagged ({untagged})")
    return 0


def _archive_entries(indices: list[int]) -> int:
    indices = list(dict.fromkeys(indices))
    lines = _read_laurels_lines()
    picked = [lines[i] for i in indices if 0 <= i < len(lines)]
    missing = [i for i in indices if not (0 <= i < len(lines))]
    keep = [line for i, line in enumerate(lines) if i not in set(indices)]
    for line in picked:
        append_line(archive_path(), line)
    _write_laurels_lines(keep)
    if missing:
        print(f"unresolved indices: {sorted(missing)}", file=sys.stderr)
        return 0 if picked else 1
    return 0


def cmd_archive(args) -> int:
    return _archive_entries(args.index)


def cmd_show(args) -> int:
    project = args.project or project_slug(args.cwd or os.getcwd())
    entries = read_entries(laurels_path())
    matched = [e for e in entries if e["project"] == project]
    others = [e for e in entries if e["project"] != project]

    filter_tag = args.tag.lstrip("#").lower() if args.tag else None
    if filter_tag:
        matched = [e for e in matched if filter_tag in e.get("tags", [])]
        others = [e for e in others if filter_tag in e.get("tags", [])]

    matched.sort(key=lambda e: e["date"])
    rng = random.Random(args.seed)

    if not args.recent and len(matched) > 2:
        newest = matched[-1]
        older = matched[:-1]
        newest_tags = set(newest.get("tags", []))
        diff_tag_older = [
            e
            for e in older
            if not (newest_tags and set(e.get("tags", [])) & newest_tags)
        ]
        pool = diff_tag_older if diff_tag_older else older
        second = rng.choice(pool)
        picked = [newest, second]
    else:
        picked = matched[-2:][::-1]

    cross = rng.choice(others) if others and rng.randint(1, args.n) == 1 else None
    if not picked and cross is None:
        return 0

    tag_str = f" [#{filter_tag}]" if filter_tag else ""
    lines = [
        f"Laurels{tag_str} — past work that landed well (calibration; nothing to act on):"
    ]
    for e in picked:
        lines.append(f"- [{e['date']}] ({e['project']}) {e['text']}")
    if cross is not None:
        lines.append(
            f"- (elsewhere) [{cross['date']}] ({cross['project']}) {cross['text']}"
        )
    lines.append("")
    lines.append('To nominate: laurels.py add "<what worked + why>" — sparingly.')
    print("\n".join(lines))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="laurels", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="nominate a laurel (append to pending)")
    p_add.add_argument("text", help="one line: what worked + why")
    p_add.add_argument("--cwd", default="", help="working dir to derive project slug")
    p_add.add_argument(
        "--project", default="", help="explicit project slug (overrides --cwd)"
    )
    p_add.add_argument("--date", default="", help="YYYY-MM-DD (defaults to today)")
    p_add.add_argument(
        "-t",
        "--tag",
        action="append",
        default=[],
        help="tag to associate (repeatable)",
    )
    p_add.add_argument(
        "--tags", default="", help="comma- or space-separated list of tags"
    )
    p_add.set_defaults(func=cmd_add)

    p_pending = sub.add_parser("pending", help="list pending nominations")
    p_pending.add_argument("--cwd", default="")
    p_pending.add_argument("--project", default="")
    p_pending.add_argument("--all", action="store_true", help="ignore project filter")
    p_pending.add_argument("-t", "--tag", default="", help="filter pending by tag")
    p_pending.set_defaults(func=cmd_pending)

    p_accept = sub.add_parser("accept", help="move pending entries into the pool")
    p_accept.add_argument("index", type=int, nargs="+")
    p_accept.add_argument("--date", default="")
    p_accept.add_argument(
        "-t",
        "--tag",
        action="append",
        default=[],
        help="tag(s) to add upon accept (repeatable)",
    )
    p_accept.add_argument(
        "--tags", default="", help="comma- or space-separated list of tags to add"
    )
    p_accept.set_defaults(func=cmd_accept)

    p_drop = sub.add_parser("drop", help="discard pending entries")
    p_drop.add_argument("index", type=int, nargs="+")
    p_drop.set_defaults(func=cmd_drop)

    p_list = sub.add_parser("list", help="list accepted laurels with stable indices")
    p_list.add_argument("--cwd", default="")
    p_list.add_argument("--project", default="")
    p_list.add_argument("--all", action="store_true", help="ignore project filter")
    p_list.add_argument("-t", "--tag", default="", help="filter by tag")
    p_list.set_defaults(func=cmd_list)

    p_tags = sub.add_parser("tags", help="show tag counts across accepted laurels")
    p_tags.add_argument("--cwd", default="")
    p_tags.add_argument("--project", default="")
    p_tags.add_argument("--all", action="store_true", help="ignore project filter")
    p_tags.set_defaults(func=cmd_tags)

    p_archive = sub.add_parser("archive", help="move accepted entries to archive.md")
    p_archive.add_argument(
        "index", type=int, nargs="+", help="indices from laurels list"
    )
    p_archive.set_defaults(func=cmd_archive)

    p_show = sub.add_parser("show", help="print the SessionStart surface block")
    p_show.add_argument("--cwd", default="")
    p_show.add_argument("--project", default="")
    p_show.add_argument("--n", type=int, default=3, help="1-in-N cross-project chance")
    p_show.add_argument("--seed", default=None, help="rng seed (testing/determinism)")
    p_show.add_argument(
        "-t", "--tag", default="", help="filter surfaced laurels by tag"
    )
    p_show.add_argument(
        "--recent",
        action="store_true",
        help="sample strictly the most recent entries",
    )
    p_show.set_defaults(func=cmd_show)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.func is cmd_show:
        try:
            return cmd_show(args)
        except Exception:
            return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
