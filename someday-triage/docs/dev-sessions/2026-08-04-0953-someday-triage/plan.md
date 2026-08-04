# someday-triage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `someday-triage` skill that safely triages `pages/someday.md` in the Obsidian vault — filing, sharpening, deduping, researching, and archiving items — where all mechanical work is done by a tested script and all judgment is done by the model.

**Architecture:** The model never edits the markdown. It emits a plan as JSON; `someday.py apply` validates and applies it. Round-trip fidelity (`serialize(parse(x)) == x`) is a tested invariant, so any diff after applying a plan is exactly the plan. A source digest makes stale plans fail loudly, reconciliation makes lost items impossible, and no operation ever deletes a line — retiring an item moves it to `someday-done.md`.

**Tech Stack:** Python 3 standard library only (argparse, re, hashlib, difflib, dataclasses, pathlib, json). pytest for tests, ruff for lint/format. No third-party runtime dependencies — matches the existing `laurels` skill in this repo.

## Global Constraints

- **Python standard library only** at runtime. `laurels.py` sets this precedent; do not add dependencies. `difflib.SequenceMatcher` covers similarity, `hashlib` covers digests.
- **Follow `laurels/scripts/laurels.py` structure exactly:** `#!/usr/bin/env python3`, module docstring, `from __future__ import annotations`, module-level compiled regexes, `cmd_*(args) -> int` handlers, `build_parser() -> argparse.ArgumentParser`, `main(argv=None) -> int`.
- **Path override via environment variable** for testability: `SOMEDAY_VAULT`, defaulting to `~/Documents/Obsidian/main`. Tests set it with `monkeypatch.setenv`.
- **Tests import the module directly** (`import someday`), call `someday.main([...])`, and use `tmp_path`, `monkeypatch`, `capsys`. No package, no conftest needed.
- **Never invoke git against the vault.** `/Users/lorchard/Documents/Obsidian/main/.git` is an empty directory — Syncthing carries files but not git internals. There is no local git data. Code that shells out to git there will find nothing; do not add such code.
- **`apply` never deletes a line.** Retiring an item appends it to `someday-done.md`.
- **Default file paths:** source `pages/someday.md`, archive `pages/someday-done.md`, both relative to the vault root.
- Indentation for generated note bullets is a **single tab**, matching the existing file.
- Run the full gate with `make check` from the repo root (ruff check + ruff format --check + pytest).

---

## File Structure

| File | Responsibility |
|---|---|
| `someday-triage/SKILL.md` | The procedure: intake and audit modes, research budget, brief template. Judgment only — no mechanics. |
| `someday-triage/README.md` | Short human-facing overview and CLI reference. |
| `someday-triage/scripts/someday.py` | All mechanical work: parse, serialize, ids, status, dupes, lint, done-check, apply. |
| `someday-triage/scripts/test_someday.py` | Test suite, including the four safety tests that justify the approach. |
| `someday-triage/scripts/fixtures/sample.md` | Hand-built fixture carrying every real edge case. |
| `Makefile` (repo root) | Add `someday-triage/scripts` to the `test` target. |

Single script file is deliberate: `laurels.py` is 228 lines and does five commands in one file. This will be larger but splitting a stdlib-only CLI into modules would break the import-the-module-directly test pattern the repo uses.

---

## Task 1: Parser, serializer, round-trip fidelity

**Files:**
- Create: `someday-triage/scripts/someday.py`
- Create: `someday-triage/scripts/test_someday.py`
- Create: `someday-triage/scripts/fixtures/sample.md`
- Modify: `Makefile` (repo root) — add `someday-triage/scripts` to the `test` target

**Interfaces:**
- Consumes: nothing (first task)
- Produces:
  - `Item` dataclass: `id: str`, `origin: int`, `checked: bool | None`, `text: str`, `notes: list[str]`, `raw: list[str]`, `dirty: bool`
  - `Section` dataclass: `level: int`, `title: str`, `raw_heading: str`, `body: list[str]`, `items: list[Item]`
  - `Document` dataclass: `preamble: list[str]`, `sections: list[Section]`, `trailing_newline: bool`

`origin` is a 0-based sequence number stamped at parse time, in document order. It is **immutable identity**: unlike `id` (a content hash), it survives a `retitle`, which is what makes exact reconciliation possible in Task 3. Nothing else may write it.

### As built (amended after Task 1 review — this is the shape later tasks code against)

Task 1's step-by-step code below is the starting draft. Two fields were added during its review, because the draft silently destroyed prose that was not a note bullet. The final data model is:

- `Item.tail: list[str]` — post-item lines that are blank or plain-unindented, held **verbatim and not in `raw`**. Keeps such prose in position by construction.
- `Section.footer: list[str]` — at section close (next heading, and at EOF), if the section has items and the **last** item's `tail` contains a non-blank line, that whole run moves here and the item's `tail` is cleared. Blank-only tails stay on the item.
- `serialize` per section: `raw_heading`, `body`, then per item `item.raw + item.tail` when clean or `render_item(item)` when dirty, then `section.footer`.
- `render_item` emits the text line, note bullets, then `item.tail` verbatim.

Why both tiers: a footer describing a whole section must not travel with an item when Task 4's `place` moves it, while prose between two items must stay between them. One tier can only satisfy one of those. **Task 4 must not move `Section.footer` when relocating an item.**
  - `parse(text: str) -> Document`
  - `serialize(doc: Document) -> str`
  - `render_item(item: Item) -> list[str]`

**Key design decision — how fidelity is achieved:** each `Item` retains its original lines in `raw`. `serialize` emits `raw` for any item with `dirty == False`, and calls `render_item` to regenerate only for modified items. This sidesteps the tabs-versus-spaces normalization problem entirely: untouched lines are never rewritten, so they cannot be corrupted. `checked is None` represents a non-checkbox bullet (the real file contains a bare `- batteries?` line).

- [ ] **Step 1: Create the fixture with every real edge case**

Create `someday-triage/scripts/fixtures/sample.md`. Every oddity here is drawn from the real file — do not "clean them up", they are the test.

```markdown
A less aspirational cousin of [[things I might do]]

# intake

- [ ] check out [thing](https://example.com/thing)

# tier 1 — small enough to finish in one sitting

## blog & site

- [ ] play with [q5.js](https://github.com/q5js/q5.js) on blog?
	- good fit for 2D — 42kb brotli vs p5's 199
	- but **zero 3D** → pinned `<script>` tag only
- [ ] Check our [spec kit]((https://github.com/github/spec-kit from github
- [x] already done thing

## lights

- [ ] Led strip for under bar
- [ ] Led strip for above sink

# tier 2 — real projects

- [ ] Work on [[blog/drafts/adventures in handwriting recognition|adventures in handwriting recognition]]
  - a note indented with spaces, not a tab
- [ ] [[people/mike heavers]]'s presentation
	- [ ] a nested bullet that is itself a checkbox
	- gradio components

# unclear

- batteries?
```

Note line 4 of the tier-1 blog cluster: `[spec kit]((https://...` has unbalanced parens and no closing bracket. It must survive round-trip untouched.

- [ ] **Step 2: Write the failing round-trip test**

Add to `someday-triage/scripts/test_someday.py`:

```python
from pathlib import Path

import someday

FIXTURES = Path(__file__).parent / "fixtures"


def test_round_trip_is_byte_exact():
    text = (FIXTURES / "sample.md").read_text()
    assert someday.serialize(someday.parse(text)) == text
```

- [ ] **Step 3: Run it and confirm it fails**

Run: `cd ~/devel/lmorchard-agent-skills && uv run --with pytest pytest someday-triage/scripts -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'someday'`

- [ ] **Step 4: Implement the parser and serializer**

Create `someday-triage/scripts/someday.py`:

```python
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

        if item is not None and (INDENTED_RE.match(line) or line == ""):
            item.raw.append(line)
            stripped = line.strip()
            if stripped.startswith("- "):
                item.notes.append(stripped[2:])
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
    text = "\n".join(out)
    if doc.trailing_newline:
        text += "\n"
    return text
```

- [ ] **Step 5: Run the test and confirm it passes**

Run: `uv run --with pytest pytest someday-triage/scripts -v`
Expected: PASS

If it fails, diff the output against the fixture to find which line class is mishandled:

```python
import difflib, someday
text = open("someday-triage/scripts/fixtures/sample.md").read()
print("\n".join(difflib.unified_diff(text.split("\n"), someday.serialize(someday.parse(text)).split("\n"), lineterm="")))
```

- [ ] **Step 6: Add structural assertions and the real-file guard**

```python
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


def test_malformed_link_survives_round_trip():
    text = (FIXTURES / "sample.md").read_text()
    assert "[spec kit]((https://github.com/github/spec-kit from github" in someday.serialize(
        someday.parse(text)
    )
```

Then the guard against the live file, which skips cleanly on a machine without the vault:

```python
import os

import pytest

REAL = Path(
    os.environ.get("SOMEDAY_VAULT", str(Path.home() / "Documents" / "Obsidian" / "main"))
) / "pages" / "someday.md"


@pytest.mark.skipif(not REAL.exists(), reason="vault not present")
def test_round_trip_on_real_file():
    text = REAL.read_text()
    assert someday.serialize(someday.parse(text)) == text
```

- [ ] **Step 7: Run all tests**

Run: `uv run --with pytest pytest someday-triage/scripts -v`
Expected: all PASS (the real-file test may report SKIPPED)

- [ ] **Step 8: Wire into the Makefile**

In the repo-root `Makefile`, change the `test` target to add the new script directory:

```make
test:
	uv run --with pytest pytest standup-digest/scripts laurels/scripts someday-triage/scripts -q
```

- [ ] **Step 9: Run the full gate**

Run: `make check`
Expected: ruff check passes, ruff format --check passes, all tests pass. If ruff reformats, run `make format` and re-run `make check`.

- [ ] **Step 10: Commit**

```bash
git add someday-triage/scripts/someday.py someday-triage/scripts/test_someday.py someday-triage/scripts/fixtures/sample.md Makefile
git commit -m "feat(someday-triage): parser and serializer with round-trip fidelity"
```

---

## Task 2: Item IDs, file loading, and the `status` command

**Files:**
- Modify: `someday-triage/scripts/someday.py`
- Modify: `someday-triage/scripts/test_someday.py`

**Interfaces:**
- Consumes: `parse`, `Document`, `Item` from Task 1
- Produces:
  - `normalize(text: str) -> str`
  - `assign_ids(doc: Document) -> None` — sets `Item.id` in place
  - `digest(text: str) -> str` — 12 hex chars of sha256
  - `vault_root() -> Path`, `source_path() -> Path`, `archive_path() -> Path`
  - `load(path: Path) -> tuple[Document, str]` — returns parsed doc and raw text
  - `cmd_status(args) -> int`
  - `build_parser()`, `main(argv=None) -> int`

- [ ] **Step 1: Write the failing tests for ids and digest**

```python
def test_ids_are_stable_and_collision_suffixed():
    doc = someday.parse(
        "# intake\n- [ ] Same Thing\n- [ ] same   thing\n- [ ] other\n"
    )
    someday.assign_ids(doc)
    ids = [i.id for i in doc.sections[0].items]
    assert ids[0] != ids[2]
    assert ids[1] == ids[0] + "-2"


def test_digest_changes_with_content():
    assert someday.digest("a") != someday.digest("b")
    assert someday.digest("a") == someday.digest("a")
    assert len(someday.digest("a")) == 12
```

- [ ] **Step 2: Run and confirm failure**

Run: `uv run --with pytest pytest someday-triage/scripts -k "ids or digest" -v`
Expected: FAIL with `AttributeError: module 'someday' has no attribute 'assign_ids'`

- [ ] **Step 3: Implement ids, digest, and paths**

Add to `someday.py` (new imports at top: `hashlib`, `os`, `from pathlib import Path`):

```python
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
```

- [ ] **Step 4: Run and confirm pass**

Run: `uv run --with pytest pytest someday-triage/scripts -k "ids or digest" -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for `status`**

`status` is the cheap morning path. It must report the intake count, the `needs-research` queue depth, per-tier counts, and the digest — and must be JSON-emitting so the skill can branch on it without re-reading the file.

```python
import json

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
```

- [ ] **Step 6: Run and confirm failure**

Run: `uv run --with pytest pytest someday-triage/scripts -k status -v`
Expected: FAIL — `main` does not exist yet

- [ ] **Step 7: Implement `status` and the CLI skeleton**

Add to `someday.py` (new imports: `argparse`, `json`, `sys`):

```python
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
```

- [ ] **Step 8: Run and confirm pass**

Run: `uv run --with pytest pytest someday-triage/scripts -v`
Expected: all PASS

- [ ] **Step 9: Verify against the real file by hand**

Run: `python3 someday-triage/scripts/someday.py status`
Expected: intake count matches what is actually in `# intake`, and open total is close to 174. This is a sanity check on real data, not an assertion.

- [ ] **Step 10: Commit**

```bash
git add someday-triage/scripts/someday.py someday-triage/scripts/test_someday.py
git commit -m "feat(someday-triage): item ids, digest, and status command"
```

---

## Task 3: Plan loading, digest guard, atomic write, and in-place ops

**Files:**
- Modify: `someday-triage/scripts/someday.py`
- Modify: `someday-triage/scripts/test_someday.py`

**Interfaces:**
- Consumes: `load`, `digest`, `serialize`, `assign_ids`, `Item` from Tasks 1-2
- Produces:
  - `PlanError(Exception)`
  - `index_items(doc: Document) -> dict[str, Item]`
  - `atomic_write(path: Path, text: str) -> None`
  - `apply_annotate(item, notes)`, `apply_retitle(item, text)`, `apply_flag(item, question, remove)`
  - `cmd_apply(args) -> int`

This task implements the three operations that do not move items between sections or files, so reconciliation is trivially satisfied and the safety plumbing can be proven before the harder ops land.

- [ ] **Step 1: Write the failing safety tests**

These four are the tests that justify the entire script-backed approach. Write them first.

```python
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
    assert rc != 0
    assert "stale" in capsys.readouterr().err.lower()
    assert src.read_text() == before


def test_apply_rejects_unknown_item_id(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    src = _seed(tmp_path, BASIC)
    plan = _plan(
        tmp_path, [{"op": "retitle", "item": "deadbeef", "text": "nope"}]
    )
    before = src.read_text()
    rc = someday.main(["apply", str(plan)])
    assert rc != 0
    assert "deadbeef" in capsys.readouterr().err
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
    real_replace = os.replace

    def boom(src, dst):
        raise OSError("simulated failure")

    monkeypatch.setattr(someday.os, "replace", boom)
    try:
        someday.atomic_write(target, "replacement\n")
    except OSError:
        pass
    monkeypatch.setattr(someday.os, "replace", real_replace)
    assert target.read_text() == "original\n"
    assert list(tmp_path.glob("*.tmp*")) == []
```

- [ ] **Step 2: Run and confirm they fail**

Run: `uv run --with pytest pytest someday-triage/scripts -k "apply or dry_run or atomic" -v`
Expected: FAIL — `apply` subcommand and `atomic_write` do not exist

- [ ] **Step 3: Implement plan loading, the digest guard, and atomic write**

```python
class PlanError(Exception):
    pass


def index_items(doc: Document) -> dict[str, Item]:
    return {i.id: i for s in doc.sections for i in s.items}


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
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
    item.notes.extend(notes)
    item.dirty = True


def apply_retitle(item: Item, text: str) -> None:
    item.text = text
    item.dirty = True


def apply_flag(item: Item, question: str, remove: bool, today: str) -> None:
    item.notes = [n for n in item.notes if not FLAG_RE.match(n)]
    if not remove:
        item.notes.append(f"needs-research ({today}): {question}")
    item.dirty = True
```

- [ ] **Step 4: Implement `cmd_apply` for in-place ops**

```python
IN_PLACE_OPS = {"annotate", "retitle", "flag"}


def cmd_apply(args) -> int:
    src = source_path()
    doc, text = load(src)

    plan = json.loads(Path(args.plan).read_text())
    if plan.get("digest") != digest(text):
        print(
            f"stale plan: source digest is {digest(text)}, plan expects "
            f"{plan.get('digest')}. Re-snapshot and rebuild the plan.",
            file=sys.stderr,
        )
        return 2

    items = index_items(doc)
    unknown = sorted(
        {
            ref
            for op in plan.get("ops", [])
            for ref in ([op.get("item")] if op.get("item") else [])
            if ref not in items
        }
    )
    if unknown:
        print(f"unknown item ids: {', '.join(unknown)}", file=sys.stderr)
        return 2

    today = args.today or date.today().isoformat()
    before_origins = {i.origin for i in items.values()}
    removed_origins: set[int] = set()

    for op in plan.get("ops", []):
        kind = op["op"]
        if kind not in IN_PLACE_OPS:
            print(f"unsupported op: {kind}", file=sys.stderr)
            return 2
        item = items[op["item"]]
        if kind == "annotate":
            apply_annotate(item, op["notes"])
        elif kind == "retitle":
            apply_retitle(item, op["text"])
        elif kind == "flag":
            apply_flag(item, op.get("question", ""), op.get("remove", False), today)

    # Two independent checks. The first is exact identity conservation on
    # `origin`, which survives retitle; the second proves the serializer
    # emitted something that parses back to the same population.
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
    if reparsed_count != len(surviving):
        print(
            f"serializer check failed: {len(surviving)} items in memory but "
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
    atomic_write(src, out)
    print(f"wrote {src}")
    return 0
```

Register it in `build_parser()`:

```python
    p_apply = sub.add_parser("apply", help="apply a JSON plan (the only mutating command)")
    p_apply.add_argument("plan")
    p_apply.add_argument("--dry-run", action="store_true")
    p_apply.add_argument("--today", default="", help="override date (testing)")
    p_apply.set_defaults(func=cmd_apply)
```

Add `from datetime import date` to the imports.

- [ ] **Step 5: Run and confirm all four safety tests pass**

Run: `uv run --with pytest pytest someday-triage/scripts -v`
Expected: all PASS

- [ ] **Step 6: Add a behavioural test that the ops actually work**

```python
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
```

- [ ] **Step 7: Run all tests and the gate**

Run: `uv run --with pytest pytest someday-triage/scripts -v && make check`
Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add someday-triage/scripts/someday.py someday-triage/scripts/test_someday.py
git commit -m "feat(someday-triage): plan apply with digest guard, atomic write, in-place ops"
```

---

## Task 4: The `place` operation

**Files:**
- Modify: `someday-triage/scripts/someday.py`
- Modify: `someday-triage/scripts/test_someday.py`

**Interfaces:**
- Consumes: `cmd_apply`, `index_items`, `Section`, `Document` from Tasks 1-3
- Produces:
  - `find_section(doc: Document, bucket: str, cluster: str | None) -> Section`
  - `apply_place(doc: Document, item: Item, bucket: str, cluster: str | None, allow_new: bool) -> None`

`place` moves an item out of `# intake` into a tier bucket and optional cluster. Sections are matched by exact title; a missing target is an error unless `--allow-new-clusters`.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run and confirm failure**

Run: `uv run --with pytest pytest someday-triage/scripts -k place -v`
Expected: FAIL with `unsupported op: place`

- [ ] **Step 3: Implement section lookup and `place`**

```python
def find_section(
    doc: Document, bucket: str, cluster: str | None, allow_new: bool
) -> Section:
    bucket_idx = next(
        (
            n
            for n, s in enumerate(doc.sections)
            if s.level == 1 and s.title == bucket
        ),
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


def apply_place(
    doc: Document, item: Item, bucket: str, cluster: str | None, allow_new: bool
) -> None:
    for section in doc.sections:
        if item in section.items:
            section.items.remove(item)
            break
    find_section(doc, bucket, cluster, allow_new).items.append(item)
```

In `cmd_apply`, add `"place"` handling before the `IN_PLACE_OPS` check and wrap the op loop so `PlanError` becomes a clean exit:

```python
    try:
        for op in plan.get("ops", []):
            kind = op["op"]
            item = items[op["item"]]
            if kind == "place":
                apply_place(
                    doc, item, op["bucket"], op.get("cluster"), args.allow_new_clusters
                )
            elif kind == "annotate":
                apply_annotate(item, op["notes"])
            elif kind == "retitle":
                apply_retitle(item, op["text"])
            elif kind == "flag":
                apply_flag(item, op.get("question", ""), op.get("remove", False), today)
            else:
                print(f"unsupported op: {kind}", file=sys.stderr)
                return 2
    except PlanError as exc:
        print(str(exc), file=sys.stderr)
        return 2
```

Add the flag to the parser:

```python
    p_apply.add_argument("--allow-new-clusters", action="store_true")
```

Note: a placed item keeps `dirty == False`, so its original lines are emitted verbatim in the new location. Moving must not rewrite text.

- [ ] **Step 4: Run and confirm pass**

Run: `uv run --with pytest pytest someday-triage/scripts -v`
Expected: all PASS

- [ ] **Step 5: Run the gate and commit**

```bash
make check
git add someday-triage/scripts/someday.py someday-triage/scripts/test_someday.py
git commit -m "feat(someday-triage): place operation with cluster creation guard"
```

---

## Task 5: `archive` and `merge` — the cross-file operations

**Files:**
- Modify: `someday-triage/scripts/someday.py`
- Modify: `someday-triage/scripts/test_someday.py`

**Interfaces:**
- Consumes: everything from Tasks 1-4
- Produces:
  - `ARCHIVE_SECTIONS: dict[str, str]` — reason to archive heading
  - `APPROVAL_REASONS: frozenset[str]`
  - `archive_entry(item: Item, note: str) -> list[str]`
  - `append_archive(path: Path, groups: dict[str, list[list[str]]], today: str) -> None`
  - `apply_archive(...)`, `apply_merge(...)`
  - full reconciliation across both files

`reason` determines both the archive heading and whether approval was needed. `routed` is autonomous; `done`, `closed`, and `missed` are retirements the model must have had confirmed. The script does not enforce approval — it records the reason so the diff shows which happened.

- [ ] **Step 1: Write the failing tests**

```python
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
    _seed(tmp_path, "Completed items from [[someday]]\n\n- [x] old thing\n", "someday-done.md")
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
```

- [ ] **Step 2: Run and confirm failure**

Run: `uv run --with pytest pytest someday-triage/scripts -k "archive or merge or reconciliation" -v`
Expected: FAIL with `unsupported op: archive`

- [ ] **Step 3: Implement the archive writer**

```python
ARCHIVE_SECTIONS = {
    "done": "done",
    "missed": "missed",
    "closed": "closed by research",
    "routed": "routed elsewhere",
    "merged": "collapsed duplicates",
}
APPROVAL_REASONS = frozenset({"done", "closed", "missed"})


def archive_entry(item: Item, note: str) -> list[str]:
    lines = [f"- {item.text}"]
    lines.extend(f"\t- {n}" for n in item.notes if not FLAG_RE.match(n))
    if note:
        lines.append(f"\t- {note}")
    return lines


def append_archive(path: Path, groups: dict[str, list[list[str]]], today: str) -> None:
    existing = path.read_text() if path.exists() else ""
    parts = [existing.rstrip("\n"), "", f"# triage {today}", ""]
    for reason, entries in groups.items():
        parts.append(f"## {ARCHIVE_SECTIONS[reason]}")
        parts.append("")
        for entry in entries:
            parts.extend(entry)
        parts.append("")
    atomic_write(path, "\n".join(parts).lstrip("\n") + "\n")
```

- [ ] **Step 4: Implement `archive` and `merge` in `cmd_apply`**

Collect entries during the op loop, then write both files only after reconciliation passes.

```python
    archived: dict[str, list[list[str]]] = {}

    def drop(item: Item) -> None:
        for section in doc.sections:
            if item in section.items:
                section.items.remove(item)
                return
```

`removed_origins` already exists from Task 3 — reuse it rather than adding a parallel set keyed on `id`. Item ids are content hashes and change under `retitle`; `origin` does not.

Add these two branches to the op loop:

```python
            elif kind == "archive":
                reason = op["reason"]
                if reason not in ARCHIVE_SECTIONS:
                    raise PlanError(f"unknown archive reason: {reason}")
                archived.setdefault(reason, []).append(
                    archive_entry(item, op.get("note", ""))
                )
                removed_origins.add(item.origin)
                drop(item)
            elif kind == "merge":
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
```

`merge` references `into` and `from` rather than `item`, so extend the unknown-id check in Task 3 to cover them:

```python
    def refs(op: dict) -> list[str]:
        out = []
        if op.get("item"):
            out.append(op["item"])
        if op.get("into"):
            out.append(op["into"])
        out.extend(op.get("from", []))
        return out

    unknown = sorted(
        {r for op in plan.get("ops", []) for r in refs(op) if r not in items}
    )
```

**The reconciliation block from Task 3 needs no change** — it already subtracts `removed_origins`, so archived items are accounted for automatically. This is why `origin` was worth introducing.

Replace only the write section at the end of `cmd_apply`:

```python
    if args.dry_run:
        print("--- dry run, no write ---")
        print(out)
        return 0

    # Archive FIRST, then the source. If the second write fails, the item
    # exists in BOTH files — visible and trivially fixable. The reverse order
    # would leave it in NEITHER, which is the exact failure this design exists
    # to prevent. Never reorder these two calls.
    if archived:
        append_archive(archive_path(), archived, today)
        print(f"appended {len(removed_origins)} to {archive_path()}")
    atomic_write(src, out)
    print(f"wrote {src}")
    return 0
```

The ordering is load-bearing and the comment says so, because it looks arbitrary and a future reader would otherwise be free to "tidy" it. Worst case under this order is a duplicated item; worst case under the other is a lost one.

- [ ] **Step 5: Run and confirm pass**

Run: `uv run --with pytest pytest someday-triage/scripts -v`
Expected: all PASS

- [ ] **Step 6: Run the gate and commit**

```bash
make check
git add someday-triage/scripts/someday.py someday-triage/scripts/test_someday.py
git commit -m "feat(someday-triage): archive and merge with cross-file reconciliation"
```

**Phase 1 is complete at this point.** The four safety tests are green and the skill can already drive a safe hand-built triage. Do not start Task 9 before this point.

---

## Task 6: The `dupes` command

**Files:**
- Modify: `someday-triage/scripts/someday.py`
- Modify: `someday-triage/scripts/test_someday.py`

**Interfaces:**
- Consumes: `load`, `open_items`, `normalize`, `Item`
- Produces: `similarity(a: str, b: str) -> float`, `find_dupes(doc, threshold) -> list[list[Item]]`, `cmd_dupes(args) -> int`

Uses `difflib.SequenceMatcher` on normalized text. The threshold has to survive a hard negative case: "Led strip for under bar" and "Led strip for above sink" are about 90% similar as strings and must not group.

> **AMENDED 2026-08-04 during implementation — read this before the steps below.** The step-by-step tests in this task originally required the `logotron` ×3 cluster to group. **That is not achievable with this metric**, proved analytically during implementation: the true-duplicate logotron pair scores **0.4304** while the unrelated under-bar/above-sink pair scores **0.4858**. The true duplicate scores *lower* than the false one, so no threshold separates them. `SequenceMatcher` rewards surface form, which is exactly the misleading signal here; closing the gap needs corpus-wide term-rarity weighting.
>
> The specification was narrowed rather than the metric chased: **`dupes` is a near-verbatim duplicate detector.** Positives to test are byte-identical texts and case/punctuation variants (e.g. "Led strip for under bar" vs "led strip for UNDER bar"). The hard negative stays. A further test pins the logotron trio as *not* grouping, commented as a documented limitation so nobody later assumes paraphrase detection works.
>
> Rationale: most real duplicate clusters in this file were verbatim repeats; the paraphrased ones were found by a human reading the list. An over-eager detector proposes merging unrelated items, which is a worse failure than a recall gap. Paraphrase detection is the model's job — Task 9's `SKILL.md` must state that in writing.

- [ ] **Step 1: Write the failing tests, negative case first**

```python
DUPES = """# tier 1 — quick

## lights

- [ ] Led strip for under bar
- [ ] Led strip for above sink

## infra

- [ ] Get logotron working again with docker-in-docker?
- [ ] get [[logotron]] working again and persistently - docker in docker?
- [ ] get [[pages/logotron|logotron]] dockerized
- [ ] Build a tool to export spotify playlist as markdown?
- [ ] tool to export my playlists from Spotify API (to plex?)?
"""


def test_dupes_does_not_group_under_bar_with_above_sink(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, DUPES)
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    groups = someday.find_dupes(doc, 0.75)
    for group in groups:
        texts = {i.text for i in group}
        assert not ("Led strip for under bar" in texts and "Led strip for above sink" in texts)


def test_dupes_groups_the_three_logotron_items(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, DUPES)
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    groups = someday.find_dupes(doc, 0.75)
    logotron = [g for g in groups if any("logotron" in i.text for i in g)]
    assert len(logotron) == 1
    assert len(logotron[0]) == 3


def test_dupes_json_output(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, DUPES)
    rc = someday.main(["dupes", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert all("items" in g for g in data["groups"])
```

- [ ] **Step 2: Run and confirm failure**

Run: `uv run --with pytest pytest someday-triage/scripts -k dupes -v`
Expected: FAIL — `find_dupes` missing

- [ ] **Step 3: Implement**

Add `import difflib` and:

```python
STOPWORDS = frozenset(
    {"a", "an", "the", "for", "with", "to", "and", "or", "on", "of", "my", "again"}
)


def content_words(text: str) -> set[str]:
    bare = re.sub(r"\[\[|\]\]|[\[\]()?#*`|]", " ", normalize(text))
    bare = re.sub(r"https?://\S+", " ", bare)
    return {w for w in bare.split() if w and w not in STOPWORDS}


def similarity(a: str, b: str) -> float:
    ratio = difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()
    wa, wb = content_words(a), content_words(b)
    if not wa or not wb:
        return ratio
    jaccard = len(wa & wb) / len(wa | wb)
    return (ratio + jaccard) / 2


def find_dupes(doc: Document, threshold: float) -> list[list[Item]]:
    items = open_items(doc)
    groups: list[list[Item]] = []
    claimed: set[int] = set()
    for i, left in enumerate(items):
        if i in claimed:
            continue
        group = [left]
        for j, right in enumerate(items[i + 1 :], start=i + 1):
            if j in claimed:
                continue
            if similarity(left.text, right.text) >= threshold:
                group.append(right)
                claimed.add(j)
        if len(group) > 1:
            claimed.add(i)
            groups.append(group)
    return groups


def cmd_dupes(args) -> int:
    doc, _ = load(source_path())
    groups = find_dupes(doc, args.threshold)
    if args.json:
        print(
            json.dumps(
                {
                    "threshold": args.threshold,
                    "groups": [
                        {"items": [{"id": i.id, "text": i.text} for i in g]}
                        for g in groups
                    ],
                },
                indent=2,
            )
        )
    else:
        for group in groups:
            print("candidate group:")
            for item in group:
                print(f"  {item.id}  {item.text}")
    return 0
```

Register:

```python
    p_dupes = sub.add_parser("dupes", help="duplicate candidate groups")
    p_dupes.add_argument("--threshold", type=float, default=0.75)
    p_dupes.add_argument("--json", action="store_true")
    p_dupes.set_defaults(func=cmd_dupes)
```

**This claim was tested and is false** — kept here because the reasoning is instructive. The intent was that Jaccard on content words would separate the cases: the logotron items share `logotron`, `working`, `docker`, while under-bar and above-sink share only `led`, `strip`. In practice both pairs land at the same Jaccard (2 shared of 6 union), and averaging in `SequenceMatcher` then *favours* the false pair because its strings are structurally alike. Measured: logotron 0.4304, LED 0.4858. See the amendment note at the top of this task.

- [ ] **Step 4: Run and confirm pass; tune only if needed**

Run: `uv run --with pytest pytest someday-triage/scripts -k dupes -v`
Expected: all PASS. If the negative test fails, raise the default threshold — do not weaken the assertion.

- [ ] **Step 5: Sanity check against the real file**

Run: `python3 someday-triage/scripts/someday.py dupes`
Expected: few or no groups, since duplicates were collapsed on 2026-08-04. Any group it reports is worth reading.

- [ ] **Step 6: Run the gate and commit**

```bash
make check
git add someday-triage/scripts/someday.py someday-triage/scripts/test_someday.py
git commit -m "feat(someday-triage): duplicate detection with content-word similarity"
```

---

## Task 7: The `lint` command

**Files:**
- Modify: `someday-triage/scripts/someday.py`
- Modify: `someday-triage/scripts/test_someday.py`

**Interfaces:**
- Consumes: `load`, `open_items`, `is_flagged`, `FLAG_RE`
- Produces: `VERIFIED_RE`, `lint_document(doc, today, stale_days) -> dict[str, list[dict]]`, `cmd_lint(args) -> int`

Reports mechanical smells only. It must not attempt content judgment — in particular it nominates research candidates only where it can prove one (a URL or markdown link, or an existing flag), because a regex cannot tell that "get a vectrex flash card" names a purchasable product.

- [ ] **Step 1: Write the failing tests**

```python
LINTABLE = """A preamble line

# intake

- [ ] go to the show on 2026-09-14
- [ ] check out [thing](https://example.com)
- [ ] plain idea with no link

# tier 1 — quick

- [ ] researched thing
	- alive and maintained (verified 2025-01-01)
- [ ] fresh thing
	- alive and maintained (verified 2026-08-01)

# unclear

- batteries?
"""


def test_lint_flags_dated_items(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, LINTABLE)
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    assert any("2026-09-14" in f["text"] for f in report["dated"])


def test_lint_flags_non_checkbox_fragments(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, LINTABLE)
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    assert [f["text"] for f in report["fragments"]] == ["batteries?"]


def test_lint_nominates_only_provable_research_candidates(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, LINTABLE)
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    texts = [f["text"] for f in report["research_candidates"]]
    assert "check out [thing](https://example.com)" in texts
    assert "plain idea with no link" not in texts


def test_lint_flags_stale_verified_annotations(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, LINTABLE)
    doc, _ = someday.load(tmp_path / "pages" / "someday.md")
    report = someday.lint_document(doc, "2026-08-04", 180)
    stale = [f["text"] for f in report["stale"]]
    assert "researched thing" in stale
    assert "fresh thing" not in stale
```

- [ ] **Step 2: Run and confirm failure**

Run: `uv run --with pytest pytest someday-triage/scripts -k lint -v`
Expected: FAIL — `lint_document` missing

- [ ] **Step 3: Implement**

```python
VERIFIED_RE = re.compile(r"\(verified (\d{4}-\d{2}-\d{2})\)")
DATE_IN_TEXT_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2})\b"
    r"|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2}\b",
    re.I,
)
LINK_RE = re.compile(r"https?://|\]\(")


def lint_document(doc: Document, today: str, stale_days: int) -> dict[str, list[dict]]:
    report: dict[str, list[dict]] = {
        "dated": [],
        "fragments": [],
        "untiered": [],
        "research_candidates": [],
        "stale": [],
    }
    cutoff = date.fromisoformat(today) - timedelta(days=stale_days)
    bucket = None
    for section in doc.sections:
        if section.level == 1:
            bucket = section.title
        for item in section.items:
            if item.checked is True:
                continue
            entry = {"id": item.id, "text": item.text, "bucket": bucket}
            if DATE_IN_TEXT_RE.search(item.text):
                report["dated"].append(entry)
            if item.checked is None:
                report["fragments"].append(entry)
            if bucket is None:
                report["untiered"].append(entry)
            if LINK_RE.search(item.text) or is_flagged(item):
                report["research_candidates"].append(entry)
            for note in item.notes:
                found = VERIFIED_RE.search(note)
                if found and date.fromisoformat(found.group(1)) < cutoff:
                    report["stale"].append(entry)
                    break
    return report


def cmd_lint(args) -> int:
    doc, _ = load(source_path())
    today = args.today or date.today().isoformat()
    report = lint_document(doc, today, args.stale_days)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for name, entries in report.items():
            if entries:
                print(f"{name}: {len(entries)}")
                for entry in entries:
                    print(f"  {entry['id']}  {entry['text']}")
    return 0
```

Add `timedelta` to the datetime import. Register:

```python
    p_lint = sub.add_parser("lint", help="structural smells and research candidates")
    p_lint.add_argument("--json", action="store_true")
    p_lint.add_argument("--stale-days", type=int, default=180)
    p_lint.add_argument("--today", default="")
    p_lint.set_defaults(func=cmd_lint)
```

- [ ] **Step 4: Run, gate, commit**

```bash
uv run --with pytest pytest someday-triage/scripts -v
make check
git add someday-triage/scripts/someday.py someday-triage/scripts/test_someday.py
git commit -m "feat(someday-triage): lint for dated items, fragments, and stale annotations"
```

---

## Task 8: The `done-check` command

**Files:**
- Modify: `someday-triage/scripts/someday.py`
- Modify: `someday-triage/scripts/test_someday.py`

**Interfaces:**
- Consumes: `load`, `open_items`, `content_words`, `archive_path`
- Produces: `distinctive_terms(item, corpus_counts) -> list[str]`, `find_already_done(doc, haystacks) -> list[dict]`, `cmd_done_check(args) -> int`

Tuned for recall over precision. A false positive costs one glance; the false negative on this check cost seven months of a finished item sitting open.

- [ ] **Step 1: Write the failing tests**

```python
def test_done_check_finds_item_present_in_archive(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, "# tier 1 — quick\n\n- [ ] build a mermaid rendering web component for my blog\n- [ ] something entirely unrelated to anything\n")
    _seed(
        tmp_path,
        "- [x] Wrapping Mermaid Diagrams in a Web Component\n",
        "someday-done.md",
    )
    rc = someday.main(["done-check", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    texts = [c["text"] for c in data["candidates"]]
    assert "build a mermaid rendering web component for my blog" in texts
    assert "something entirely unrelated to anything" not in texts


def test_done_check_searches_extra_dirs(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOMEDAY_VAULT", str(tmp_path))
    _seed(tmp_path, "# tier 1 — quick\n\n- [ ] wayback machine link fixer\n")
    _seed(tmp_path, "nothing here\n", "someday-done.md")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "notes.md").write_text("finished the wayback machine link fixer last week\n")
    rc = someday.main(["done-check", "--repos", str(repo), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert any("wayback" in c["text"] for c in data["candidates"])
```

- [ ] **Step 2: Run and confirm failure**

Run: `uv run --with pytest pytest someday-triage/scripts -k done_check -v`
Expected: FAIL — `done-check` subcommand missing

- [ ] **Step 3: Implement**

```python
def distinctive_terms(item: Item, corpus_counts: dict[str, int]) -> list[str]:
    words = [w for w in content_words(item.text) if len(w) > 3]
    words.sort(key=lambda w: (corpus_counts.get(w, 0), -len(w)))
    return words[:3]


def find_already_done(doc: Document, haystacks: list[str]) -> list[dict]:
    items = open_items(doc)
    counts: dict[str, int] = {}
    for item in items:
        for word in content_words(item.text):
            counts[word] = counts.get(word, 0) + 1
    blob = "\n".join(haystacks).lower()
    hits = []
    for item in items:
        terms = distinctive_terms(item, counts)
        if not terms:
            continue
        matched = [t for t in terms if t in blob]
        if len(matched) >= max(2, len(terms) - 1):
            hits.append({"id": item.id, "text": item.text, "matched": matched})
    return hits


def cmd_done_check(args) -> int:
    doc, _ = load(source_path())
    haystacks = []
    if archive_path().exists():
        haystacks.append(archive_path().read_text())
    for root in args.repos:
        for path in Path(root).rglob("*.md"):
            if ".git" in path.parts or "node_modules" in path.parts:
                continue
            try:
                haystacks.append(path.read_text(errors="ignore"))
            except OSError:
                continue
    candidates = find_already_done(doc, haystacks)
    if args.json:
        print(json.dumps({"candidates": candidates}, indent=2))
    else:
        for hit in candidates:
            print(f"{hit['id']}  {hit['text']}  (matched: {', '.join(hit['matched'])})")
    return 0
```

Register:

```python
    p_done = sub.add_parser("done-check", help="items that may already be finished")
    p_done.add_argument("--repos", nargs="*", default=[])
    p_done.add_argument("--json", action="store_true")
    p_done.set_defaults(func=cmd_done_check)
```

- [ ] **Step 4: Run, gate, commit**

```bash
uv run --with pytest pytest someday-triage/scripts -v
make check
git add someday-triage/scripts/someday.py someday-triage/scripts/test_someday.py
git commit -m "feat(someday-triage): done-check for items that may already be finished"
```

**Phase 2 is complete at this point.**

---

## Task 9: `SKILL.md`, `README.md`, and link verification

**Files:**
- Create: `someday-triage/SKILL.md`
- Create: `someday-triage/README.md`

**Interfaces:**
- Consumes: the full CLI from Tasks 1-8
- Produces: the skill itself, discoverable via `make link`

- [ ] **Step 1: Write `SKILL.md`**

Frontmatter `description` must state the triggers, matching the style of the other skills in this repo.

```markdown
---
name: someday-triage
description: Use when Les wants to triage pages/someday.md — process the # intake section, file and sharpen new items, dedupe, research candidates, archive dead ideas, or run a periodic audit of the whole list. Triggers: "triage someday", "process my intake", "someday audit", or a morning-ritual pass over captured ideas.
---

# Someday Triage

Two modes over `pages/someday.md` in the Obsidian vault. All mechanical work is done by
`scripts/someday.py` — **never hand-edit the markdown.** You emit a JSON plan; the script
validates and applies it, reconciles the item count, and refuses stale plans.

Run everything from the repo containing this skill, or use an absolute path to the script.

## Hard rules

- **Never edit `someday.md` or `someday-done.md` directly.** Every change goes through
  `someday.py apply`. The script guarantees no item is silently lost; freehand editing does not.
- **Never run git against the vault.** Its `.git` is an empty directory — Syncthing carries
  files but not git internals. History lives in the `obsidian-main-backup` repo.
- **Always `apply --dry-run` first**, show Les the reconciliation line, then apply.
- **Kills need consent.** `archive` with reason `done`, `closed`, or `missed` requires Les's
  yes/no. `archive` with reason `routed` does not.

## Mode: intake (default)

1. `someday.py status --json`. If `intake` and `needs_research` are both `0`, print a one-line
   summary plus `someday.py lint` totals and **stop**. This is the common morning case; do not
   read the rest of the list.
2. Read the `# intake` items and the heading skeleton only — not all existing items.
3. Gather signals: `lint --json`, `dupes --json`, `done-check --json`.
4. **Drain order:** existing `needs-research` flags first, oldest date first, then new intake
   items. Shared budget of 3 research tasks per run (`--agents`-style cap is your judgment,
   not a script flag). Overflow gets a `flag` op, not research.
5. For each intake item decide, in order:
   - **Not someday-shaped?** → `archive` with reason `routed`, then invoke the `journal-note`
     skill to place it. Appointments and anything with a date go to `# followup`; blog ideas to
     `# notes`; near-term todos to `# today` or `# this week`. Autonomous.
   - **Duplicate of an existing item?** → propose `merge`.
   - **Already done?** (from `done-check`) → propose `archive` with reason `done`.
   - **Otherwise** → `place` into a tier and cluster, `retitle` if the wording is vague, and
     `annotate` with one concrete first step.
6. Research a candidate only if it would change the disposition. Append `(verified YYYY-MM-DD)`
   to any factual note you write.
7. Emit the plan, run `apply --dry-run`, show the reconciliation, get consent for any kills,
   then `apply`. Report one line per item.

## Mode: audit

Runs intake first, then, because pruning already happens at intake, this is mostly maintenance:

1. `lint --json` and `dupes --json` over the whole file; `done-check --repos ~/devel`.
2. **Stale-annotation sweep — the main job.** Re-verify notes whose `(verified …)` date is past
   the threshold. Stock counts, version numbers, and "actively maintained" all rot.
3. Route anything date-bound out of the list.
4. Propose cluster restructuring if clusters have drifted lopsided.
5. Apply, then write findings to the journal via the `journal-note` skill.

## Choosing a tier

Tiers describe **division of labour**, not priority:

1. Small enough to finish in one sitting — a PR-sized change.
2. Real projects in an agent's wheelhouse — multi-session, mostly code.
3. An agent plans it or writes the firmware; Les does the physical half.
4. An agent can research, spec, or draft; Les has to pull the trigger — purchases, appointments, visits.
5. All Les — physical labour, in-person, personal.

## Research brief template

When dispatching research, include these verbatim. Each exists because its absence cost
something in the 2026-08-04 pass:

- "If you cannot ground a claim, say **insufficient research** for that item. Do not fill gaps
  with plausible-sounding guesses. Five solid items and four honest gaps beat nine where I
  cannot tell which is which."
- "Verify last-commit and last-release dates. Do not infer liveness from impressions — check."
- "Distinguish what you **tested live** from what you only **read in docs**. Label each."

Target decision-changing questions: is it maintained? superseded? purchasable and in stock?
already solved? is the obvious approach a trap?

## Plan format

```json
{
  "digest": "<from status --json>",
  "ops": [
    {"op": "place", "item": "a1b2c3d4", "bucket": "tier 1 — small enough to finish in one sitting", "cluster": "blog & site"},
    {"op": "retitle", "item": "a1b2c3d4", "text": "sharpened wording"},
    {"op": "annotate", "item": "a1b2c3d4", "notes": ["first step: ... (verified 2026-08-04)"]},
    {"op": "flag", "item": "e5f6a7b8", "question": "is it still maintained?"},
    {"op": "merge", "into": "a1b2c3d4", "from": ["e5f6a7b8"], "note": "collapsed duplicate"},
    {"op": "archive", "item": "c9d0e1f2", "reason": "closed", "note": "why it is dead"}
  ]
}
```

`reason` is one of `done`, `missed`, `closed`, `routed`, `merged`.

## Commands

    someday.py status      [--json]
    someday.py dupes       [--threshold 0.75] [--json]
    someday.py lint        [--json] [--stale-days 180]
    someday.py done-check  [--repos DIR...] [--json]
    someday.py apply PLAN  [--dry-run] [--allow-new-clusters]
```

- [ ] **Step 2: Write `README.md`**

```markdown
# someday-triage

Mechanical triage for `pages/someday.md` in the Obsidian vault. The model decides; the script
does everything that could lose data.

## Why a script

A 200-line markdown rewrite that silently drops four items looks identical to one that does
not. This script makes that failure impossible: round-trip fidelity is a tested invariant, item
counts are reconciled across both files before anything is written, and stale plans are refused.

## Commands

See `someday.py --help`. `status` is the cheap path — one call tells you whether there is
anything to do.

## Tests

    make check      # ruff + pytest, from the repo root

The four tests that matter: round-trip fidelity, reconciliation catching a dropped item,
stale-plan rejection, and atomic write leaving the original intact on failure.

## Recovery

`apply` appends to `someday-done.md` **before** writing `someday.md`, deliberately. If the
second write fails, an archived item exists in both files — visible and trivially fixable. The
reverse order would leave it in neither. Do not reorder those two writes.

If you do need history, use the `obsidian-main-backup` repo — the vault's own `.git` is an empty
directory, because Syncthing carries files but not git internals.
```

- [ ] **Step 3: Verify the skill links and is discoverable**

Run: `make link && make links`
Expected: `someday-triage` reports `linked`.

- [ ] **Step 4: Smoke-test the real workflow read-only**

```bash
python3 someday-triage/scripts/someday.py status
python3 someday-triage/scripts/someday.py lint
python3 someday-triage/scripts/someday.py dupes
```
Expected: all three run against the real vault without error. Nothing is written.

- [ ] **Step 5: Run the gate and commit**

```bash
make check
git add someday-triage/SKILL.md someday-triage/README.md
git commit -m "feat(someday-triage): skill procedure and README"
```

---

## Self-Review Notes

**Spec coverage.** Every spec section maps to a task: architecture and plan ops → Tasks 3-5; generalization seam → see the deferral note below; data model → Task 1; CLI → Tasks 2, 3, 6, 7, 8; modes → Task 9; research brief → Task 9; error handling → Tasks 3-5, 7; testing → all tasks; repo integration → Tasks 1, 9.

**One deliberate deferral.** The spec describes a named **profile** as the generalization seam for reusing the parser on other documents. No task implements it, because nothing in v1 needs a second profile and building the indirection now would be speculative. What the plan does preserve is the precondition: `source_path()` and `archive_path()` are the only places that know the file layout, and no parser code references tiers or intake by name except the `INTAKE_TITLE` constant. Adding a profile later is a change in one region, not a rewrite. If Les wants the seam now, add a task before Task 2 introducing a `PROFILES` dict and a `--profile` argument threaded through those two functions.

**Type consistency.** `Item.checked` is `bool | None` throughout — `None` for non-checkbox fragments, and `checked is not True` is the open-item test everywhere so fragments count as open. `find_section` takes `allow_new` in every call site. `apply_flag` takes `today` explicitly rather than reading the clock, so tests can pin it. `content_words` is defined in Task 6 and reused by Task 8; if Task 8 is implemented first, move that helper up.

**Amendments made 2026-08-04 after a pre-flight review, before any code was written.** Three items where the plan's first draft mandated something a reviewer would rightly flag:

1. `Document.trailing_newline` was a dynamic attribute set with a `# type: ignore`. Now a declared field. Identical behaviour, no smell.
2. Reconciliation compared item *counts*, which a retitle-plus-drop plan could satisfy while losing an item. Now `Item.origin` — an immutable parse-order sequence number — gives exact identity conservation via `reconcile()`, which is unit-tested directly rather than only through the CLI. This removed the staged weakness entirely, so Task 5 no longer needs its own reconciliation variant.
3. **The write order was a real durability bug.** The draft wrote `someday.md` first and appended the archive second, so a failure between them destroyed the item. Reversed: worst case is now a duplicate, not a loss. There is a test asserting the order, because the correct order looks arbitrary and invites tidying.
