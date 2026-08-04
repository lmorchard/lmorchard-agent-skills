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

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
