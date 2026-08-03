# laurels + session-wrapup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture work that landed well as calibration (agent nominates in-session, Les adjudicates at wrap-up, accepted laurels surface project-relevant at next wake), and evolve `session-handoff` into `session-wrapup` that forks continuing/done with laurel adjudication in its shared spine.

**Architecture:** A stdlib Python CLI (`laurels.py`) owns all deterministic logic — format, project-slug derivation, store IO, adjudication moves, and the SessionStart selection. Skills (`laurels`, `session-wrapup`) carry only framing and judgment. A global project-tagged store lives at `~/.claude/laurels/{pending,laurels}.md` (runtime data, not committed).

**Tech Stack:** Python 3.11+ (standard library only), pytest, ruff (per PR #6), markdown SKILL.md files, Claude Code SessionStart hook in `settings.json`.

## Global Constraints

- Python 3.11+, **standard library only** — no third-party imports (matches `standup-digest`).
- Store location overridable via `LAURELS_DIR` env var; defaults to `~/.claude/laurels`. Every store-touching test sets `LAURELS_DIR` to a temp dir; no test writes the real store.
- Entry line format, verbatim: `- [YYYY-MM-DD] (project-slug) free text` (single line).
- Project slug: worktree resolves to real repo root, then path relative to `~/devel`, else relative to `~`, else basename.
- `laurels.md` = accepted pool (accept date); `pending.md` = nominations (capture date).
- Must pass `make lint` (ruff) once PR #6 (`chore/make-lint-ruff`) lands.
- The surface hook must **never** fail a session start: on any unexpected error, print nothing and exit 0.
- Ungameable properties are load-bearing: a laurel carries no task and no priority; surfaced retrospectively; gated by adjudication. Do not add prioritization or action to laurels.
- **Files that touch Les's global config (`~/.claude/CLAUDE.md`, `~/.claude/settings.json`, `~/.claude/skills/` symlinks) require Les's explicit approval before applying — Task 7 prepares them; it does not silently mutate them.**

---

### Task 1: `laurels.py` scaffold + pure helpers

**Files:**
- Create: `laurels/scripts/laurels.py`
- Test: `laurels/scripts/test_laurels.py`

**Interfaces:**
- Produces: `store_dir() -> Path`, `pending_path() -> Path`, `laurels_path() -> Path`, `project_slug(cwd) -> str`, `format_entry(when: str, project: str, text: str) -> str`, `parse_entry(line: str) -> dict | None`, `read_entries(path: Path) -> list[dict]`, `append_line(path: Path, line: str) -> None`. Each parsed entry is `{"date": str, "project": str, "text": str}`.

- [ ] **Step 1: Write the failing test**

```python
# laurels/scripts/test_laurels.py
import os
import subprocess
from pathlib import Path

import laurels


def test_format_and_parse_round_trip():
    line = laurels.format_entry("2026-08-03", "obsidian/main", "bidi-only check was the fix")
    assert line == "- [2026-08-03] (obsidian/main) bidi-only check was the fix"
    parsed = laurels.parse_entry(line)
    assert parsed == {"date": "2026-08-03", "project": "obsidian/main", "text": "bidi-only check was the fix"}


def test_format_collapses_multiline_text():
    line = laurels.format_entry("2026-08-03", "p", "line one\n  line two")
    assert "\n" not in line
    assert line == "- [2026-08-03] (p) line one line two"


def test_parse_rejects_non_entry_lines():
    assert laurels.parse_entry("# a heading") is None
    assert laurels.parse_entry("") is None


def test_project_slug_non_repo_returns_basename(tmp_path):
    d = tmp_path / "someproj"
    d.mkdir()
    assert laurels.project_slug(str(d)) == "someproj"


def test_project_slug_resolves_git_worktree_to_repo_root(tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    assert laurels.project_slug(str(repo)) == "myrepo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd laurels/scripts && python -m pytest test_laurels.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'laurels'` (or `AttributeError` once the file exists but functions don't).

- [ ] **Step 3: Write minimal implementation**

```python
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
            ["git", "-C", str(p), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, check=True,
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd laurels/scripts && python -m pytest test_laurels.py -v`
Expected: PASS (5 tests). If `git init` is unavailable in the sandbox, `test_project_slug_resolves_git_worktree_to_repo_root` may error — if so, confirm `git` is on PATH; it is a hard dependency of the repo.

- [ ] **Step 5: Commit**

```bash
git add laurels/scripts/laurels.py laurels/scripts/test_laurels.py
git commit -m "feat(laurels): script scaffold + format/parse/slug helpers"
```

---

### Task 2: `add` command

**Files:**
- Modify: `laurels/scripts/laurels.py` (add `cmd_add`, argparse dispatch, `main`)
- Test: `laurels/scripts/test_laurels.py`

**Interfaces:**
- Consumes: `format_entry`, `append_line`, `pending_path`, `project_slug` (Task 1).
- Produces: `cmd_add(args) -> int`; `build_parser() -> argparse.ArgumentParser`; `main(argv=None) -> int`. `add` accepts `text` (positional), `--cwd`, `--project`, `--date`.

- [ ] **Step 1: Write the failing test**

```python
def test_add_appends_project_tagged_line(tmp_path, monkeypatch):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    rc = laurels.main(["add", "the fix worked", "--project", "obsidian/main", "--date", "2026-08-03"])
    assert rc == 0
    text = (tmp_path / "pending.md").read_text()
    assert text == "- [2026-08-03] (obsidian/main) the fix worked\n"


def test_add_creates_store_dir(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "laurels"
    monkeypatch.setenv("LAURELS_DIR", str(target))
    laurels.main(["add", "x", "--project", "p", "--date", "2026-08-03"])
    assert (target / "pending.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd laurels/scripts && python -m pytest test_laurels.py -k add -v`
Expected: FAIL with `AttributeError: module 'laurels' has no attribute 'main'`.

- [ ] **Step 3: Write minimal implementation**

Append to `laurels.py`:

```python
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
    p_add.add_argument("--project", default="", help="explicit project slug (overrides --cwd)")
    p_add.add_argument("--date", default="", help="YYYY-MM-DD (defaults to today)")
    p_add.set_defaults(func=cmd_add)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd laurels/scripts && python -m pytest test_laurels.py -k add -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add laurels/scripts/laurels.py laurels/scripts/test_laurels.py
git commit -m "feat(laurels): add command appends project-tagged nominations"
```

---

### Task 3: `pending`, `accept`, `drop` commands

**Files:**
- Modify: `laurels/scripts/laurels.py`
- Test: `laurels/scripts/test_laurels.py`

**Interfaces:**
- Consumes: `parse_entry`, `format_entry`, `read entries via raw lines`, `pending_path`, `laurels_path`, `append_line`, `project_slug` (Tasks 1–2).
- Produces: `cmd_pending(args) -> int` (`--cwd`/`--project`/`--all`), `cmd_accept(args) -> int` (`index` nargs+, `--date`), `cmd_drop(args) -> int` (`index` nargs+). Indices are absolute line positions in `pending.md`.

- [ ] **Step 1: Write the failing test**

```python
def _seed_pending(tmp_path, *lines):
    (tmp_path / "pending.md").write_text("".join(l + "\n" for l in lines))


def test_pending_filters_by_project(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_pending(
        tmp_path,
        "- [2026-08-03] (obsidian/main) a",
        "- [2026-08-03] (tabs/pilo) b",
    )
    rc = laurels.main(["pending", "--project", "obsidian/main"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "0: [2026-08-03] (obsidian/main) a" in out
    assert "tabs/pilo" not in out


def test_accept_moves_to_laurels_with_accept_date(tmp_path, monkeypatch):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_pending(
        tmp_path,
        "- [2026-08-01] (p) keeper",
        "- [2026-08-01] (p) dropme",
    )
    rc = laurels.main(["accept", "0", "--date", "2026-08-03"])
    assert rc == 0
    assert (tmp_path / "laurels.md").read_text() == "- [2026-08-03] (p) keeper\n"
    assert (tmp_path / "pending.md").read_text() == "- [2026-08-01] (p) dropme\n"


def test_drop_removes_without_accepting(tmp_path, monkeypatch):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_pending(tmp_path, "- [2026-08-01] (p) x", "- [2026-08-01] (p) y")
    rc = laurels.main(["drop", "1"])
    assert rc == 0
    assert not (tmp_path / "laurels.md").exists()
    assert (tmp_path / "pending.md").read_text() == "- [2026-08-01] (p) x\n"


def test_accept_reports_stale_index(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_pending(tmp_path, "- [2026-08-01] (p) x")
    rc = laurels.main(["accept", "5", "--date", "2026-08-03"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "5" in err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd laurels/scripts && python -m pytest test_laurels.py -k "pending or accept or drop" -v`
Expected: FAIL — `argument cmd: invalid choice: 'pending'`.

- [ ] **Step 3: Write minimal implementation**

Add these functions and register the subparsers inside `build_parser()`:

```python
def _read_pending_lines() -> list[str]:
    path = pending_path()
    return path.read_text().splitlines() if path.exists() else []


def _write_pending_lines(lines: list[str]) -> None:
    path = pending_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(l + "\n" for l in lines))


def cmd_pending(args) -> int:
    lines = _read_pending_lines()
    project = None if args.all else (args.project or project_slug(args.cwd or os.getcwd()))
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
                append_line(laurels_path(), format_entry(when, parsed["project"], parsed["text"]))
    _write_pending_lines(keep)
    if missing:
        print(f"unresolved indices: {sorted(missing)}", file=sys.stderr)
        return 0 if picked else 1
    return 0


def cmd_accept(args) -> int:
    return _adjudicate(args.index, accept=True, when=args.date or date.today().isoformat())


def cmd_drop(args) -> int:
    return _adjudicate(args.index, accept=False, when="")
```

Inside `build_parser()`, before `return parser`, add:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd laurels/scripts && python -m pytest test_laurels.py -k "pending or accept or drop" -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add laurels/scripts/laurels.py laurels/scripts/test_laurels.py
git commit -m "feat(laurels): pending/accept/drop adjudication commands"
```

---

### Task 4: `show` command (SessionStart surface)

**Files:**
- Modify: `laurels/scripts/laurels.py`
- Test: `laurels/scripts/test_laurels.py`

**Interfaces:**
- Consumes: `read_entries`, `laurels_path`, `project_slug` (Task 1).
- Produces: `cmd_show(args) -> int` (`--cwd`, `--project`, `--n` default 3, `--seed`). Prints the surface block or nothing.

- [ ] **Step 1: Write the failing test**

```python
def _seed_laurels(tmp_path, *lines):
    (tmp_path / "laurels.md").write_text("".join(l + "\n" for l in lines))


def test_show_project_matches_capped_at_two_newest_first(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_laurels(
        tmp_path,
        "- [2026-08-01] (p) oldest",
        "- [2026-08-02] (p) middle",
        "- [2026-08-03] (p) newest",
    )
    # seed chosen so the cross-project roll misses (no others exist anyway)
    rc = laurels.main(["show", "--project", "p", "--n", "3", "--seed", "1"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "oldest" not in out
    lines = [l for l in out.splitlines() if l.startswith("- ")]
    assert lines == [
        "- [2026-08-03] (p) newest",
        "- [2026-08-02] (p) middle",
    ]


def test_show_empty_store_is_silent(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    rc = laurels.main(["show", "--project", "p", "--seed", "1"])
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_show_can_include_cross_project_when_roll_hits(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    _seed_laurels(
        tmp_path,
        "- [2026-08-01] (p) mine",
        "- [2026-08-02] (other) theirs",
    )
    # find a seed where randint(1, n) == 1; --n 1 guarantees a hit
    rc = laurels.main(["show", "--project", "p", "--n", "1", "--seed", "0"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "- [2026-08-01] (p) mine" in out
    assert "(elsewhere)" in out
    assert "theirs" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd laurels/scripts && python -m pytest test_laurels.py -k show -v`
Expected: FAIL — `argument cmd: invalid choice: 'show'`.

- [ ] **Step 3: Write minimal implementation**

Add the function and register the subparser:

```python
def cmd_show(args) -> int:
    project = args.project or project_slug(args.cwd or os.getcwd())
    entries = read_entries(laurels_path())
    matched = [e for e in entries if e["project"] == project]
    picked = matched[-2:][::-1]
    others = [e for e in entries if e["project"] != project]
    rng = random.Random(args.seed)
    cross = rng.choice(others) if others and rng.randint(1, args.n) == 1 else None
    if not picked and cross is None:
        return 0
    lines = ["Laurels — past work that landed well (calibration; nothing to act on):"]
    for e in picked:
        lines.append(f"- [{e['date']}] ({e['project']}) {e['text']}")
    if cross is not None:
        lines.append(f"- (elsewhere) [{cross['date']}] ({cross['project']}) {cross['text']}")
    lines.append("")
    lines.append('To nominate: laurels.py add "<what worked + why>" — sparingly.')
    print("\n".join(lines))
    return 0
```

Inside `build_parser()`, before `return parser`:

```python
    p_show = sub.add_parser("show", help="print the SessionStart surface block")
    p_show.add_argument("--cwd", default="")
    p_show.add_argument("--project", default="")
    p_show.add_argument("--n", type=int, default=3, help="1-in-N cross-project chance")
    p_show.add_argument("--seed", default=None, help="rng seed (testing/determinism)")
    p_show.set_defaults(func=cmd_show)
```

Note: `random.Random(None)` seeds from entropy in production; tests pass `--seed`. `randint(1, n)` with `--n 1` always returns 1 (guaranteed cross-project hit), which is why the cross-project test uses `--n 1`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd laurels/scripts && python -m pytest test_laurels.py -v`
Expected: PASS (all tests, ~13).

- [ ] **Step 5: Harden the hook entrypoint (never fail a session start)**

Wrap `show` dispatch so an unexpected error prints nothing and exits 0. Modify `main`:

```python
def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.func is cmd_show:
        try:
            return cmd_show(args)
        except Exception:
            return 0
    return args.func(args)
```

Add a test:

```python
def test_show_swallows_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("LAURELS_DIR", str(tmp_path))
    monkeypatch.setattr(laurels, "read_entries", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert laurels.main(["show", "--project", "p", "--seed", "1"]) == 0
```

Run: `cd laurels/scripts && python -m pytest test_laurels.py -k show -v` → PASS.

- [ ] **Step 6: Commit**

```bash
git add laurels/scripts/laurels.py laurels/scripts/test_laurels.py
git commit -m "feat(laurels): show command for SessionStart surfacing"
```

---

### Task 5: `laurels` skill docs

**Files:**
- Create: `laurels/SKILL.md`
- Create: `laurels/README.md`

**Interfaces:**
- Consumes: the CLI from Tasks 1–4 (documents `add`/`pending`/`accept`/`drop`/`show`).

- [ ] **Step 1: Write `laurels/SKILL.md`**

```markdown
---
name: laurels
description: Use when noticing work that landed genuinely well and worth remembering — nominate it as a laurel (calibration, surfaced at future session starts). Also the reference for how laurels are captured, adjudicated, and surfaced.
---

# Laurels

Laurels record work that turned out genuinely good, surfaced back at session start as
**calibration** ("this approach worked — reuse it"), not vibes. A laurel grants no task
and no priority; there is nothing to farm.

## Capture (during a session)

When you notice a genuinely good result — a satisfying fix, a non-obvious approach that
paid off — nominate it, **sparingly**:

    python3 ~/.claude/skills/laurels/scripts/laurels.py add "<what worked + why>" --cwd "$PWD"

Not every passing test. Only work worth remembering weeks later. Over-nomination burns
Les's adjudication attention — that is the scarce resource, so err toward restraint.

## Adjudicate (at session-wrapup)

`session-wrapup` runs this as a shared-spine step; you rarely invoke it standalone.

    laurels.py pending --cwd "$PWD"      # this project's candidates, with indices
    laurels.py accept <index...>         # move blessed ones into the pool
    laurels.py drop <index...>           # discard the rest

## Surface (at session start)

A SessionStart hook runs `laurels.py show --cwd "$PWD"` and injects a project-relevant
laurel or two as calibration. Nothing to act on when you see them.

## Store

`~/.claude/laurels/pending.md` (nominations) and `laurels.md` (accepted pool). Runtime
data, project-tagged, hand-editable. Override location with `LAURELS_DIR`.
```

- [ ] **Step 2: Write `laurels/README.md`**

```markdown
# laurels

Capture work that landed well as calibration signal, surfaced at future session starts.
Agent nominates in-session, Les adjudicates at `session-wrapup`, accepted laurels surface
project-relevant at the next wake. Ungameable by construction: no task or priority
attached, surfaced retrospectively, gated by adjudication.

- `scripts/laurels.py` — CLI: `add`, `pending`, `accept`, `drop`, `show`.
- Store: `~/.claude/laurels/{pending,laurels}.md` (override with `LAURELS_DIR`).
- Design: `docs/dev-sessions/2026-08-03-1631-laurels-session-wrapup/`.
```

- [ ] **Step 3: Verify the skill frontmatter parses**

Run: `python3 -c "import pathlib,re; t=pathlib.Path('laurels/SKILL.md').read_text(); assert t.startswith('---'); assert 'name: laurels' in t; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add laurels/SKILL.md laurels/README.md
git commit -m "docs(laurels): SKILL.md and README"
```

---

### Task 6: `session-handoff` → `session-wrapup` refactor

**Files:**
- Rename: `session-handoff/SKILL.md` → `session-wrapup/SKILL.md` (via `git mv`)
- Modify: `session-wrapup/SKILL.md`

**Interfaces:**
- Consumes: `laurels.py pending/accept/drop` (Tasks 1–4), the `journal-note` skill (existing).

- [ ] **Step 1: Rename the directory**

```bash
git mv session-handoff session-wrapup
```

Run: `git status -sb` → expect `renamed: session-handoff/SKILL.md -> session-wrapup/SKILL.md`.

- [ ] **Step 2: Rewrite `session-wrapup/SKILL.md`**

Fork the existing content: the handoff tail is the current skill nearly verbatim; the new surface is the mode fork, the adjudication spine step, and the closure tail. Full file:

```markdown
---
name: session-wrapup
description: Use when a session is ending — whether work continues (handoff) or the thread is done (closure). Forks on that question; shares a spine that gathers state, promotes durable lessons, and adjudicates laurels. Triggers: wrap up, hand off, close out, done for now, bank state, prime a new session.
---

# Session Wrap-up

Wrapping a session forks on one question: **is this work continuing, or is it done?**

- **continuing** — work is unfinished, a successor session is needed → **handoff tail**.
- **done** — the thread is finished or being put down, no successor → **closure tail**.

Ask when ambiguous; the invoking phrasing usually decides it.

Both modes run the shared spine first.

## Shared spine

### 1 — Gather from commands, not memory

Run them; paste no remembered values. Name the command beside each value.
Usually: `git status -sb`, `git log --oneline <base>..HEAD`, `gh pr list`, `gh issue
list`, `gh project item-list`, the project's run/state logs, the session directory.

### 2 — Promote, before drafting

For each thing this session learned, ask: **does it outlive the resume?**

- **Yes** → write it to its evergreen home now — findings/lessons doc, design doc, an
  issue, the project's instructions file — then link it.
- **No** → it belongs in the handoff (or, in closure, it is transient and dropped).

### 3 — Adjudicate laurels

List this project's in-session nominations and let Les judge them:

    laurels.py pending --cwd "$PWD"

Present the candidates. Les prunes / edits / blesses. Move survivors into the pool and
discard the rest:

    laurels.py accept <index...>
    laurels.py drop <index...>

If there are no pending candidates, this step is silent. Never nominate on Les's behalf
here — adjudication is his; capture happened live during the session.

---

## Handoff tail (work continues)

**The handoff is a router, not a container.** It is read once, at low context, then
thrown away. Anything worth keeping was promoted in spine step 2; the handoff carries a
link to it. Write to the OS temp directory and report the path. Never the workspace,
never committed.

Draft to this contract — each part one paragraph or a short list, in this order:

1. **Purpose** — what the next session is for, in one sentence.
2. **Corrections to inherit** — claims this session made that turned out wrong. Say what
   was claimed, what is true, and how it was established.
3. **State** — a pointer plus the command that prints it. Branch, tree, PRs, board, spend.
4. **The task** — what to do next, and what done looks like.
5. **Open decisions** — each with the default if nobody decides.
6. **Opening move** — the skill, mode, or command to start with, and files to read first.
7. **Launcher prompt** — a fenced block to paste into the fresh session.

Every part follows the same rule: if it already lives somewhere durable, link it. Redact
credentials and personal data.

### Example — a Corrections entry

    - I said `gh pr checks --watch` closed the review-waiting issue. It does not: that
      issue is about waiting for a *review*, and its own body already records `--watch`
      as the CI-only survivor. Established by reading the issue body.

---

## Closure tail (work is done)

No successor to prime — so no launcher doc. Instead:

1. **Journal the outcome** — invoke the `journal-note` skill to record what this session
   accomplished (composes it; does not reimplement journaling).
2. **Confirm promotion** — durable lessons were written to their evergreen homes in spine
   step 2. Verify nothing worth keeping is left only in this conversation.
3. **Stop.** Note the session is closed.

---

## Common mistakes

| Mistake | Instead |
|---|---|
| Transcribing state into prose | Name the command that prints it |
| Omitting Corrections because nothing "big" was wrong | The small wrong claims get inherited silently |
| Growing a handoff past ~100 lines | Something wants to be an evergreen doc — promote it |
| Writing a launcher doc in closure | Closure has no successor; skip it |
| Nominating laurels for Les in adjudication | Capture is the agent's; adjudication is Les's |
| Committing a handoff | Temp directory; the durable half was promoted in step 2 |
```

- [ ] **Step 3: Verify the rename and frontmatter**

Run:
```bash
test -f session-wrapup/SKILL.md && ! test -e session-handoff && echo "moved ok"
grep -q "name: session-wrapup" session-wrapup/SKILL.md && echo "name ok"
grep -q "Closure tail" session-wrapup/SKILL.md && echo "closure ok"
```
Expected: `moved ok`, `name ok`, `closure ok`.

- [ ] **Step 4: Commit**

```bash
git add -A session-wrapup session-handoff
git commit -m "refactor(session-wrapup): fork handoff/closure from session-handoff, add laurel adjudication"
```

---

### Task 7: Wiring — symlinks, marketplace, hook, CLAUDE.md

**Files:**
- Modify: `.claude-plugin/marketplace.json`
- Prepare (Les applies): `~/.claude/skills/` symlinks, `~/.claude/settings.json`, `~/.claude/CLAUDE.md`

**Interfaces:**
- Consumes: the two skill dirs (Tasks 5–6) and `laurels.py show` (Task 4).

> **Approval gate:** the symlink swap, `settings.json` hook, and `CLAUDE.md` edit touch Les's global config. Prepare exact commands/diffs and get his explicit go before applying each. Only `marketplace.json` (repo-local) is committed here.

- [ ] **Step 1: Update `marketplace.json`**

In `.claude-plugin/marketplace.json`, add `"./session-wrapup"` and `"./laurels"` to the
`plugins[0].skills` array (alongside the existing entries; `session-handoff` was never
listed, so nothing to remove there).

- [ ] **Step 2: Verify marketplace JSON is valid**

Run: `python3 -c "import json; d=json.load(open('.claude-plugin/marketplace.json')); s=d['plugins'][0]['skills']; assert './laurels' in s and './session-wrapup' in s; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit the repo-local change**

```bash
git add .claude-plugin/marketplace.json
git commit -m "chore(marketplace): register session-wrapup and laurels"
```

- [ ] **Step 4: Prepare the symlink swap (Les applies after review)**

```bash
rm ~/.claude/skills/session-handoff
ln -s ~/devel/lmorchard-agent-skills/session-wrapup ~/.claude/skills/session-wrapup
ln -s ~/devel/lmorchard-agent-skills/laurels ~/.claude/skills/laurels
```
Verify after: `readlink ~/.claude/skills/session-wrapup ~/.claude/skills/laurels`.

- [ ] **Step 5: Prepare the `settings.json` SessionStart hook (Les applies after review)**

Add to `~/.claude/settings.json` under `hooks` (merge, do not overwrite existing hooks):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/skills/laurels/scripts/laurels.py show --cwd \"$CLAUDE_PROJECT_DIR\""
          }
        ]
      }
    ]
  }
}
```
The `show` entrypoint swallows errors and exits 0 (Task 4 Step 5), so it cannot break a
session start. Verify by opening a fresh session in a project that has accepted laurels
and confirming the block appears in context.

- [ ] **Step 6: Prepare the `CLAUDE.md` capture pointer (Les applies after review)**

Propose adding this section to `~/.claude/CLAUDE.md`:

```markdown
# Laurels

- When you notice a genuinely good result during a session — a satisfying fix, a
  non-obvious approach that paid off — nominate it, sparingly:
  `python3 ~/.claude/skills/laurels/scripts/laurels.py add "<what worked + why>" --cwd "$PWD"`.
  Not every passing test; only work worth remembering.
- Nominations are adjudicated at session-wrapup and surface as calibration at future
  session starts. A laurel grants no task and no priority — there is nothing to farm.
```

- [ ] **Step 7: End-to-end smoke test (after Les applies Steps 4–6)**

```bash
export LAURELS_DIR=$(mktemp -d)
P=~/devel/lmorchard-agent-skills/laurels/scripts/laurels.py
python3 $P add "smoke: the wiring works end to end" --project demo --date 2026-08-03
python3 $P pending --project demo          # shows index 0
python3 $P accept 0 --date 2026-08-03
python3 $P show --project demo --seed 1    # prints the surface block
rm -rf "$LAURELS_DIR"; unset LAURELS_DIR
```
Expected: `add` silent, `pending` prints `0: ...`, `accept` silent, `show` prints the
calibration block containing "smoke: the wiring works end to end".

---

## Self-Review

**Spec coverage:**
- Laurels store / format / slug / pending-vs-accepted → Task 1 (+ used throughout). ✓
- Capture (`add`, sparingly, in-session) → Task 2 + Task 5 SKILL.md + Task 7 CLAUDE.md. ✓
- Adjudication (`pending`/`accept`/`drop`, at wrap-up) → Task 3 + Task 6 spine step 3. ✓
- Surface (`show`, project filter, cap 2, seeded cross-project, silence, never-fail) → Task 4. ✓
- `laurels.py` all five subcommands → Tasks 1–4. ✓
- session-wrapup refactor (mode fork, shared spine, handoff & closure tails) → Task 6. ✓
- Deliverables: skill dirs, symlinks, marketplace.json, settings.json hook, CLAUDE.md → Tasks 5–7. ✓
- Testing (pytest, temp store, seeded rng) → Tasks 1–4. ✓
- Error handling (missing files, malformed lines, stale indices, never-fail hook) → Tasks 1/3/4. ✓
- `make lint` (ruff) → Global Constraints; run before final commit once PR #6 lands.

**Placeholder scan:** none — every code and config step shows full content.

**Type consistency:** entry dict `{"date","project","text"}` and function signatures
(`format_entry`, `parse_entry`, `read_entries`, `cmd_*`, `build_parser`, `main`) are used
consistently across Tasks 1–4. `LAURELS_DIR`, `--cwd`, `--project`, `--date`, `--seed`,
`--n` names match between implementation, tests, SKILL.md, and the hook command.

**Gap note:** ruff may flag `l` as an ambiguous loop variable (E741) in the list
comprehensions; if so, rename `l` → `line`/`ln` when wiring `make lint`. Not fixed
pre-emptively to keep the plan's code readable.
```
