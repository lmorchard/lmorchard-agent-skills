# Research — `make lint` (ruff) scaffold

Documentarian pass + measured `ruff 0.16.1` baseline, run 2026-07-31 in the
`chore/make-lint-ruff` worktree.

## 1. Python surface: 8 files, all standalone scripts

| File | Shebang | exec bit | `__main__` |
|---|---|---|---|
| `daily-blog-post-composer/scripts/prepare-sources.py:1` | yes | yes | `:101` |
| `daily-blog-post-composer/scripts/parse-daily-post.py:1` | yes | yes | `:141` |
| `daily-blog-post-composer/scripts/extract-timestamps.py:1` | yes | yes | `:217` |
| `go-cli-builder/scripts/scaffold_project.py:1` | yes | yes | `:209` |
| `go-cli-builder/scripts/add_command.py:1` | yes | yes | `:78` |
| `weeknotes-composer/scripts/calculate-week.py:1` | yes | yes | `:68` |
| `standup-digest/scripts/standup_digest.py:1` | yes | **no** | `:784` |
| `standup-digest/scripts/test_standup_digest.py` | no | no | pytest module |

No package structure, no `__init__.py`, no imports across skill directories.
`test_standup_digest.py:13` does `import standup_digest as sd` (same-dir import,
works because pytest adds the test's dir to `sys.path`).
No PEP-723 `# /// script` blocks anywhere.

## 2. Existing config: none

Zero matches tree-wide for `pyproject.toml`, `setup.cfg`, `.ruff.toml`/`ruff.toml`,
`tox.ini`, `requirements*.txt`, `.pre-commit-config.yaml`, `.editorconfig`,
`pytest.ini`, `conftest.py`.

`.gitignore` covers Python artifacts (`__pycache__/`, `*.py[cod]`, `.venv`) and
`.worktrees/`. `.ruff_cache/` and `.pytest_cache/` are **not** in `.gitignore`, but
both tools write a self-ignoring `.gitignore` (`*`) inside their own cache dir, so
neither shows in `git status`.

## 3. Makefile (root, only one in the repo)

```makefile
.PHONY: help test standup

help:
	@echo "test     - run the standup-digest test suite"
	@echo "standup  - print yesterday's digest JSON"

test:
	uv run --with pytest pytest standup-digest/scripts -q

standup:
	python3 standup-digest/scripts/standup_digest.py
```

`help` is the documentation convention in use (echo lines, one per target).
The `test` target uses `uv run --with pytest` — ephemeral dependency, no lockfile,
no virtualenv checked in. That's the established pattern for pulling in a tool.

`go-cli-builder/assets/templates/Makefile.template` is a *generated-project* asset,
not this repo's build (`go-cli-builder/scripts/scaffold_project.py:148-150`).

## 4. CI: none

No `.github/workflows/`; no `.yml`/`.yaml` anywhere in the tree. The three
`*.yml.template` files under `go-cli-builder/assets/templates/` are scaffolding for
generated Go projects (`scaffold_project.py:166-168`).

Nothing in the repo currently invokes a Python linter or formatter. The strings
`make format && make lint` in `go-cli-builder/SKILL.md` and `add_command.py:65` are
next-step guidance printed for a *scaffolded Go project*.

## 5. Layout and non-Python content

Eight sibling skill directories (`daily-blog-post-composer`, `dev-session`,
`go-cli-builder`, `journal-note`, `send-notification`, `standup-digest`,
`television-companion`, `weeknotes-composer`), each with a `SKILL.md`, optionally
`scripts/`, `references/`, `assets/`, and per-skill `docs/dev-sessions/`.

A tree-wide tool run encounters:
- **44 Markdown files** — the dominant file type (SKILL.md, README.md, and dev-session
  `spec.md`/`plan.md`/`notes.md` artifacts).
- 5 shell scripts, 1 real `.go` file + 17 `.template` files, 1 JSON, 1 HTML.
- No JS/TS.

## 6. Measured ruff baseline (`ruff 0.16.1`, `--isolated`, i.e. stock defaults)

### `ruff check .` → 43 findings across 8 files

| Rule | Count | Fixable |
|---|---|---|
| UP006 non-pep585-annotation | 10 | auto |
| F401 unused-import | 5 | auto |
| F541 f-string-missing-placeholders | 5 | auto |
| I001 unsorted-imports | 5 | auto |
| UP035 deprecated-import | 4 | no |
| C414 unnecessary-double-cast-or-process | 3 | no |
| DTZ005 call-datetime-now-without-tzinfo | 3 | no |
| DTZ007 call-datetime-strptime-without-zone | 2 | no |
| F841 unused-variable | 2 | 1 auto / 1 unsafe |
| BLE001 blind-except | 1 | no |
| DTZ001 call-datetime-without-tzinfo | 1 | no |
| EXE001 shebang-not-executable | 1 | no |
| UP045 non-pep604-annotation-optional | 1 | auto |

27 of 43 auto-fixable; 4 more behind `--unsafe-fixes`.

Note: stock `ruff 0.16.1` defaults are broader than the historically documented
`["E4","E7","E9","F"]` — the isolated run emits `UP`, `I`, `DTZ`, `C4`, `BLE`, `EXE`
findings with no config present. Whatever ruleset we pin should be written down
explicitly rather than inherited from a moving default.

### Per-file finding counts

```
daily-blog-post-composer/scripts/extract-timestamps.py    16
daily-blog-post-composer/scripts/parse-daily-post.py       8
go-cli-builder/scripts/add_command.py                      8
go-cli-builder/scripts/scaffold_project.py                 5
standup-digest/scripts/test_standup_digest.py              2
weeknotes-composer/scripts/calculate-week.py               2
daily-blog-post-composer/scripts/prepare-sources.py        1
standup-digest/scripts/standup_digest.py                   1
```

### Judgment-required findings (the non-auto-fixable set)

```
extract-timestamps.py:110:20  BLE001 Do not catch blind exception: `Exception`
extract-timestamps.py:110:33  F841  Local variable `e` assigned but never used
parse-daily-post.py:87,88,89  C414  Unnecessary `list()` call within `sorted()`
scaffold_project.py:105:9     F841  Local variable `skip_next` assigned but never used
standup_digest.py:1:1         EXE001 Shebang present but file is not executable
test_standup_digest.py:18:13  DTZ001 datetime() without tzinfo  (deliberate: local() helper)
calculate-week.py:22,24       DTZ005/DTZ007  datetime.now()/strptime() naive
```

### `ruff format .` → **13 files, 6 of them Markdown**

ruff 0.16 formats Python code blocks embedded in Markdown. Scanning `.` finds 51
files (8 `.py` + 43 `.md`) and would rewrite:

```
daily-blog-post-composer/SKILL.md                                              <- doc
weeknotes-composer/SKILL.md                                                    <- doc
standup-digest/docs/dev-sessions/2026-07-29-0916-initial-design/notes.md       <- history
standup-digest/docs/dev-sessions/2026-07-29-0916-initial-design/plan.md        <- history
standup-digest/docs/dev-sessions/2026-07-30-0919-digest-fuller-capture/plan.md <- history
weeknotes-composer/docs/dev-sessions/2026-05-20-1452-initial-design/plan.md    <- history
daily-blog-post-composer/scripts/extract-timestamps.py
daily-blog-post-composer/scripts/parse-daily-post.py
go-cli-builder/scripts/add_command.py
go-cli-builder/scripts/scaffold_project.py
standup-digest/scripts/standup_digest.py
standup-digest/scripts/test_standup_digest.py
weeknotes-composer/scripts/calculate-week.py
```

Restricted to `*.py`: 7 of 8 files would be reformatted
(`prepare-sources.py` is already clean).

## 7. Code style actually present

- **Line length:** no enforced limit. `standup_digest.py` reads as deliberately
  wrapped near 88 (max 97). Others run longer: `scaffold_project.py` max 127,
  `prepare-sources.py` max 139 (a box-drawing banner string, e.g. `:41`),
  `extract-timestamps.py` max 104, `add_command.py` max 101.
- **Quotes:** overwhelmingly double. `calculate-week.py` is the outlier
  (23 single-quote lines vs 15 double), e.g. `calculate-week.py:24`
  `datetime.strptime(date, '%Y-%m-%d')`.
- **Imports:** inconsistent. `standup_digest.py:7-16` sorted, with
  `from __future__ import annotations` first. `scaffold_project.py:9-14` unsorted
  (`shutil`, `datetime` after `pathlib`).
- **Type hints:** split by file. `standup_digest.py` fully typed with PEP 604/585
  (`records: list[dict]` at `:35`, `date: str | None` at `:60`). `parse-daily-post.py:16`
  and `extract-timestamps.py:17` use legacy `typing.List/Dict/Any/Optional` — this is
  the entire source of the 10× UP006 + 4× UP035 + 1× UP045.
  `scaffold_project.py`, `add_command.py`, `calculate-week.py`, `prepare-sources.py`
  have no annotations at all.
- **Docstrings:** triple-double everywhere; module docstring in every file.
  `standup_digest.py` uses multi-paragraph rationale docstrings (`:44-52`, `:216-224`).
- **Trailing whitespace:** `extract-timestamps.py` (28 lines) and `parse-daily-post.py`
  (15 lines) carry it; the other six files do not.

## 8. Open questions this raises for the spec

1. Does ruff's scope include Markdown code blocks, or `*.py` only?
2. Pinned explicit ruleset, or inherit ruff's (moving) defaults?
3. `uvx ruff` ephemeral (matches the `uv run --with pytest` pattern) or a
   `pyproject.toml` with a pinned dev dependency?
4. Which of the 16 judgment findings get fixed vs. `noqa`'d vs. rule-disabled?
