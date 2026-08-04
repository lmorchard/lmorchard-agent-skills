#!/usr/bin/env python3
"""laurels — capture and surface work that landed well, as calibration."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ENTRY_RE = re.compile(r"^- \[(\d{4}-\d{2}-\d{2})\] \(([^)]*)\) (.*)$")


def store_dir() -> Path:
    return Path(os.environ.get("LAURELS_DIR", str(Path.home() / ".claude" / "laurels")))


def pending_path() -> Path:
    return store_dir() / "pending.md"


def laurels_path() -> Path:
    return store_dir() / "laurels.md"


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


def format_entry(when: str, project: str, text: str) -> str:
    text = " ".join(text.split())
    return f"- [{when}] ({project}) {text}"


def parse_entry(line: str) -> dict | None:
    m = ENTRY_RE.match(line.rstrip("\n"))
    if not m:
        return None
    return {"date": m.group(1), "project": m.group(2), "text": m.group(3)}


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
    when = args.date or date.today().isoformat()
    project = args.project or project_slug(args.cwd or os.getcwd())
    append_line(pending_path(), format_entry(when, project, args.text))
    return 0


def _read_pending_lines() -> list[str]:
    path = pending_path()
    return path.read_text().splitlines() if path.exists() else []


def _write_pending_lines(lines: list[str]) -> None:
    path = pending_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(line + "\n" for line in lines))


def cmd_pending(args) -> int:
    lines = _read_pending_lines()
    project = (
        None if args.all else (args.project or project_slug(args.cwd or os.getcwd()))
    )
    for i, line in enumerate(lines):
        parsed = parse_entry(line)
        if parsed is None:
            continue
        if project is None or parsed["project"] == project:
            print(f"{i}: [{parsed['date']}] ({parsed['project']}) {parsed['text']}")
    return 0


def _adjudicate(indices: list[int], accept: bool, when: str) -> int:
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
                    format_entry(when, parsed["project"], parsed["text"]),
                )
    _write_pending_lines(keep)
    if missing:
        print(f"unresolved indices: {sorted(missing)}", file=sys.stderr)
        return 0 if picked else 1
    return 0


def cmd_accept(args) -> int:
    return _adjudicate(
        args.index, accept=True, when=args.date or date.today().isoformat()
    )


def cmd_drop(args) -> int:
    return _adjudicate(args.index, accept=False, when="")


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
    p_add.set_defaults(func=cmd_add)

    p_pending = sub.add_parser("pending", help="list pending nominations")
    p_pending.add_argument("--cwd", default="")
    p_pending.add_argument("--project", default="")
    p_pending.add_argument("--all", action="store_true", help="ignore project filter")
    p_pending.set_defaults(func=cmd_pending)

    p_accept = sub.add_parser("accept", help="move pending entries into the pool")
    p_accept.add_argument("index", type=int, nargs="+")
    p_accept.add_argument("--date", default="")
    p_accept.set_defaults(func=cmd_accept)

    p_drop = sub.add_parser("drop", help="discard pending entries")
    p_drop.add_argument("index", type=int, nargs="+")
    p_drop.set_defaults(func=cmd_drop)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
