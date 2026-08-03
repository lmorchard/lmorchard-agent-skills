# `make lint` (ruff) Scaffold Spec

**Goal:** Give this repo a real lint/format gate — `make lint`, `make format`, `make check` — so the dev-session workflow's verification steps run an actual linter instead of the `python3 -m py_compile` stand-in.

**Source:** https://github.com/lmorchard/lmorchard-agent-skills/issues/5

## Current state

- Root `Makefile` has three targets: `help`, `test` (`uv run --with pytest pytest standup-digest/scripts -q`), `standup`. No lint, no format, no check.
- **Zero** Python config anywhere in the tree: no `pyproject.toml`, `.ruff.toml`, `setup.cfg`, `tox.ini`, `requirements*.txt`, `.pre-commit-config.yaml`, `.editorconfig` (`research.md` §2).
- No CI. Nothing in the repo invokes a linter or formatter (`research.md` §4).
- 8 Python files, all standalone scripts across four skill directories. No package structure, no `__init__.py`, no cross-directory imports (`research.md` §1).
- Style is inconsistent by file: `standup_digest.py` is fully typed with PEP 604/585 and sorted imports; `parse-daily-post.py` / `extract-timestamps.py` use legacy `typing.List/Dict`; `scaffold_project.py` has unsorted imports and no annotations; two files carry trailing whitespace (`research.md` §7).

## Desired end state

`make check` is the single gate, and it passes clean on a fresh checkout:

```
make lint     -> uvx ruff@0.16.1 check .      then  uvx ruff@0.16.1 format --check .
make format   -> uvx ruff@0.16.1 check --fix . then  uvx ruff@0.16.1 format .
make check    -> lint + test
make test     -> unchanged
```

- New `.ruff.toml` at repo root pinning the ruleset and excluding Markdown.
- All 8 Python scripts formatted and lint-clean under that ruleset.
- `make help` lists the new targets, following its existing echo-per-target convention.
- `make test` still reports **83 passed** — formatting must be behavior-preserving.

Measured: applying `ruff check --fix` + `ruff format` under the chosen config changes 683 lines across 7 files (`prepare-sources.py` is already clean) and leaves exactly 5 residual findings (4× `E402`, 1× `F841`), each handled explicitly below. A scratch run of the fully-formatted tree passes all 83 tests.

## Design decisions

- **Decision:** Scope ruff to `*.py` only, via `extend-exclude = ["*.md"]`.
  - **Why:** `ruff format` rewrites Python code blocks inside Markdown. Unrestricted, it would rewrite 6 `.md` files — including 4 archived `docs/dev-sessions/**/plan.md` and `notes.md` artifacts (`research.md` §6). Those are a historical record; reformatting them rewrites history. SKILL.md code blocks are documentation — sometimes illustrative or deliberately elided, not necessarily valid Python.
  - **Rejected:** Formatting `.py` + live docs while excluding `docs/dev-sessions/**` — more config, and still risks mangling illustrative snippets for no gain.

- **Decision:** Pin `select = ["E4", "E7", "E9", "F", "I", "UP"]` explicitly in `.ruff.toml`.
  - **Why:** Stock `ruff 0.16.1` defaults are broader than the historically documented `E4/E7/E9/F` — an isolated run also emits `DTZ`, `BLE`, `C4`, `EXE` findings with no config present (`research.md` §6). An inherited default is a gate that moves under you on upgrade. Pinning writes the contract down. This set covers the real breakage (pyflakes) plus two cheap consistency wins (import sorting, pyupgrade) and is ~all auto-fixable.
  - **Rejected:** Stock defaults (drags in 6 `DTZ` findings on scripts where naive datetime is intentional, plus a deliberate blind-except); errors-only `E4/E7/E9/F` (leaves imports unsorted and legacy `typing.List` in place).

- **Decision:** Pin `target-version = "py310"` in `.ruff.toml`.
  - **Why:** `UP` rule behavior depends on the target Python version, and with no `pyproject.toml` there is no `requires-python` for ruff to infer from — so it falls back to a default that, like `select`, can move between releases. Measured: at `py39`, `UP006` becomes non-auto-fixable and `UP045` stops firing entirely (11 fixes drop to unsafe-only); at `py310` and `py313` the finding set is identical at 38. `py310` is the lowest version that gives the full modern-syntax set, so it's the honest floor to declare rather than assuming the 3.13 that happens to be installed.
  - **Rejected:** Leaving it unset (inherits a moving default — the same failure mode as unpinned `select`); `py313` (assumes a newer floor than these standalone `#!/usr/bin/env python3` scripts have any reason to require, for zero additional benefit).

- **Decision:** `uvx ruff@0.16.1` in the Makefile; config in `.ruff.toml`, **no** `pyproject.toml`.
  - **Why:** Mirrors the established ephemeral-tool pattern at `Makefile:8` (`uv run --with pytest`) — no lockfile, no venv, no install step. A `pyproject.toml` would imply this repo is an installable Python package; it's a skills collection with 8 loose scripts and no package structure (`research.md` §1).
  - **Rejected:** Unpinned `uvx ruff` — the gate silently changes when ruff ships new default rules, which is exactly the failure mode research surfaced.

- **Decision:** Silence the 4 `E402` findings in `standup-digest/scripts/test_standup_digest.py` with a commented `per-file-ignores` entry in `.ruff.toml`.
  - **Why:** That file sets `os.environ["TZ"] = "UTC"; time.tzset()` at lines 5-6 *before* importing `datetime` — load-bearing ordering that makes the timezone-sensitive tests deterministic. The imports genuinely can't move. One documented config entry beats four inline `# noqa: E402` comments that drift as lines move.
  - **Rejected:** Inline `# noqa: E402` ×4 (repetitive, and the *reason* lives four lines above the first one anyway); reordering the imports (breaks the tests).

- **Decision:** Delete the dead `skip_next = False` at `go-cli-builder/scripts/scaffold_project.py:105`.
  - **Why:** It's inside `remove_database_from_root` and is never read or reassigned — genuinely dead, not a stub. `F841` is right. Deleting one line is the honest fix.
  - **Rejected:** `# noqa: F841` (suppresses a true positive).

## Patterns to follow

- **Makefile style** — `Makefile:1-12`: `.PHONY` on line 1 listing every target; `help` as the first target with one `@echo "name     - description"` line per target, aligned. Add `lint`, `format`, `check` to both `.PHONY` and `help`. Real tabs, not spaces.
- **Composition over duplication** — `make check` calls the `lint` and `test` targets, not their underlying commands.
- **Ephemeral tooling** — `Makefile:8` (`uv run --with pytest pytest ...`). `uvx ruff@0.16.1` is the same shape.
- **`.gitignore`** — `.ruff_cache/` needs no entry: ruff writes a self-ignoring `.gitignore` (`*`) inside its own cache dir, same as `.pytest_cache/` already does (`research.md` §2).

## What we're NOT doing

- **No CI.** No `.github/workflows/`. `make check` is a local gate only. Wiring it into GitHub Actions is a separate issue.
- **No `pyproject.toml`**, no dependency pinning beyond the `ruff@0.16.1` version in the Makefile, no lockfile, no venv.
- **No Markdown formatting.** The 6 `.md` files ruff would otherwise rewrite stay untouched.
- **No `DTZ` / timezone fixes.** The 6 naive-datetime findings in `calculate-week.py:22,24` and `test_standup_digest.py:18` are out of the selected ruleset. `test_standup_digest.py:18` is deliberate (a `local()` helper that intentionally builds a naive datetime then `.astimezone()`s it).
- **No `BLE001` fix.** The blind `except Exception` at `extract-timestamps.py:110` is deliberate defensive parsing; not in the selected ruleset.
- **No `C414` fix.** The three `sorted(list(...))` calls at `parse-daily-post.py:87-89` are not in the selected ruleset.
- **No `EXE001` fix.** `standup-digest/scripts/standup_digest.py:1` has a shebang without the exec bit. Not in the selected ruleset; leave the file mode alone.
- **No type-annotation campaign.** `UP006`/`UP035`/`UP045` will mechanically convert existing `typing.List/Dict/Optional` to builtin generics. We are *not* adding annotations to the four scripts that have none.
- **No behavior changes.** The only non-formatting source edit is deleting the dead `skip_next` line. If a formatting change alters behavior, that's a bug to fix, not accept.
- **No linting of shell scripts, Go, or JSON.** `shellcheck` and friends are a separate issue.
- **No `make serve` / `make build`.** Not applicable to this repo.

## Open questions

None. All three design questions were resolved during brainstorm; the residual lint findings were enumerated by measurement rather than left open.
