# `make lint` (ruff) Scaffold — Implementation Plan

**Goal:** Add a real lint/format gate (`make lint`, `make format`, `make check`) backed by ruff, and bring all 8 Python scripts clean under it.

**Approach:** Pin ruff's ruleset and target-version explicitly in a root `.ruff.toml` (stock defaults are broader than documented and move between releases), scope it to `*.py` so `ruff format` doesn't rewrite Markdown docs or archived dev-session artifacts, and invoke it via `uvx ruff@0.16.1` — mirroring the existing `uv run --with pytest` ephemeral-tool pattern at `Makefile:8` rather than introducing a `pyproject.toml`.

**Tech stack:** ruff 0.16.1 via `uvx`, GNU make, pytest via `uv run --with pytest`.

**TDD framing:** There is no new runtime behavior to test, so this is infrastructure scaffolding — the standard "write a failing unit test" step doesn't apply. The gate itself is the test: Phase 1 installs a `make check` that **fails** with 38 known findings, Phases 2 and 3 drive it to green. Each phase records the actual finding count as its evidence.

**Standing invariant across all three phases:** `make test` must report **83 passed**. That number is the pre-change baseline and was independently reproduced on two fully-reformatted scratch copies of the tree, so it is a stable assertion, not a single observation. Any deviation means a formatting change altered behavior — a bug to fix, not to accept.

---

## Phase 1: Install the gate (failing)

Creates the ruff config and the three Makefile targets. At the end of this phase `make lint` runs a real linter and exits non-zero with a known, enumerated finding set — the foundation Phases 2 and 3 build on. `make test` is untouched and still green.

**Files:**
- Create: `.ruff.toml`
- Modify: `Makefile` — add `lint`, `format`, `check` to `.PHONY`; add three `@echo` lines to `help`; append the three target bodies; introduce a `RUFF` variable so the pinned version lives in one place.

**Key changes:**

`.ruff.toml` (new, complete file):

```toml
# ruff configuration for lmorchard-agent-skills.
#
# Scope: Python scripts only. `ruff format` also rewrites Python code blocks
# embedded in Markdown. Left unrestricted it would rewrite SKILL.md documentation
# (whose snippets are illustrative and not always valid Python) and the archived
# docs/dev-sessions/**/plan.md and notes.md session artifacts, which are a
# historical record rather than maintained code.
extend-exclude = ["*.md"]

# Pinned rather than inherited. Stock ruff defaults are broader than the
# documented E4/E7/E9/F set and shift between releases, so an inherited default
# is a gate that moves underneath you on upgrade.
target-version = "py310"

[lint]
#   E4/E7/E9 - pycodestyle errors (import placement, statements, syntax)
#   F        - pyflakes (undefined names, unused imports and variables)
#   I        - isort (import ordering)
#   UP       - pyupgrade (modern syntax for the target version)
select = ["E4", "E7", "E9", "F", "I", "UP"]
```

`Makefile` — final state:

```makefile
.PHONY: help test standup lint format check

RUFF := uvx ruff@0.16.1

help:
	@echo "test     - run the standup-digest test suite"
	@echo "standup  - print yesterday's digest JSON"
	@echo "lint     - ruff check + format check, no writes"
	@echo "format   - ruff format + apply safe lint fixes"
	@echo "check    - lint + test, the full gate"

test:
	uv run --with pytest pytest standup-digest/scripts -q

standup:
	python3 standup-digest/scripts/standup_digest.py

lint:
	$(RUFF) check .
	$(RUFF) format --check .

format:
	$(RUFF) check --fix .
	$(RUFF) format .

check: lint test
```

**Order matters in `format`:** `check --fix` runs *first*, `format` second. Autofixes delete imports and rewrite annotations, which can leave a file needing reformatting; running `format` first would leave the tree failing `lint`'s `format --check` immediately after a `make format`. This is the order validated in the scratch runs.

Recipe lines use real tabs. The `help` echo lines keep the existing 9-column alignment (`test` + 5 spaces, `standup` + 2 spaces).

**Verification — automated:**
- [x] `make help` lists all five targets with aligned descriptions — **all 5 printed, 9-column alignment held**
- [x] `make lint` exits non-zero, reporting **38 errors** with this exact distribution: UP006×10, F401×5, F541×5, I001×5, E402×4, UP035×4, F841×2, UP015×2, UP045×1 — **exit 2, 38 errors, distribution matched exactly**
- [x] `make test` passes — **83 passed in 0.06s**
- [!] `uvx ruff@0.16.1 check --show-files .` lists exactly the 8 `.py` files and no `.md` file —
      **DOES NOT HOLD as written.** It lists **9** entries: the 8 `.py` files *plus
      `.ruff.toml` itself*. Not a failure of the work — the plan's assertion was
      written from a measurement taken before `.ruff.toml` existed, and ruff lists
      its own config among discovered files without linting it as Python. The
      load-bearing half of the claim does hold: **zero `.md` files listed.**
- [x] `make check` exits non-zero (confirms `check` actually gates on `lint`) — **exit 2**

**Verification — manual:**
- [x] `git status` shows no modification to any `.md` file — **only `M Makefile` plus untracked `.ruff.toml` and the session docs**
- [x] `.ruff_cache/` does not appear in `git status` (ruff self-ignores its cache dir) — **absent, confirmed**

---

## Phase 2: Mechanical fixes — autofix and format

Runs the new `make format` target to apply every safe lint fix and reformat all 8 scripts. This is the bulk of the diff: ~683 changed lines across 7 files (`daily-blog-post-composer/scripts/prepare-sources.py` is already clean and should not change). Drops the finding count from 38 to 5.

**Files (all modified by tooling, no hand edits):**
- Modify: `daily-blog-post-composer/scripts/extract-timestamps.py` — trailing whitespace stripped (28 lines carried it), `typing.List/Dict` → `list/dict`, single→double quotes, long calls wrapped
- Modify: `daily-blog-post-composer/scripts/parse-daily-post.py` — trailing whitespace stripped (15 lines), unused `typing.List` import removed, `typing.Dict` → `dict`
- Modify: `go-cli-builder/scripts/add_command.py` — unused `os` and `datetime.datetime` imports removed, imports sorted
- Modify: `go-cli-builder/scripts/scaffold_project.py` — unused `os` and `shutil` imports removed, imports sorted
- Modify: `standup-digest/scripts/standup_digest.py` — formatter-only churn
- Modify: `standup-digest/scripts/test_standup_digest.py` — formatter-only churn (largest single diff, ~216 lines)
- Modify: `weeknotes-composer/scripts/calculate-week.py` — single→double quotes, `datetime.now()` reformat
- Unchanged: `daily-blog-post-composer/scripts/prepare-sources.py`

**Key changes:** No hand-written code. The command is exactly:

```sh
make format
```

which expands to `uvx ruff@0.16.1 check --fix .` followed by `uvx ruff@0.16.1 format .`, in that order.

Do **not** pass `--unsafe-fixes`. One unsafe fix is available — the `F841` on `scaffold_project.py`'s `skip_next`, which Phase 3 deletes by hand instead. (The *other* `F841`, the bound-but-unused `e` in `except Exception as e` at `extract-timestamps.py:110`, is a **safe** fix and is applied automatically here, rewriting it to a bare `except Exception:`. An earlier draft of this plan attributed the unsafe fix to that line; it belongs to `skip_next`.)

**Correction applied during execution:** the `format` target as first written was `$(RUFF) check --fix .` followed by `$(RUFF) format .`, and it **failed** — `ruff check --fix` exits non-zero whenever any finding remains unfixed, so make aborted the recipe and `ruff format` never ran (`format --check` still reported 7 files unformatted). Fixed by adding `--exit-zero` to the `check --fix` line: `format` is a fix-it-up target, and `make lint` is the gate that reports what's left.

**Verification — automated:**
- [x] `make lint` exits non-zero with exactly **5 errors**: `go-cli-builder/scripts/scaffold_project.py:109 F841` and four `E402` in `standup-digest/scripts/test_standup_digest.py` (lines 8, 9, 11, 12) — **matched exactly, all five line numbers as predicted**
- [x] `uvx ruff@0.16.1 format --check .` reports **8 files already formatted** — **"8 files already formatted"**
- [x] `make test` passes — **83 passed in 0.16s** (load-bearing: proves the reformat is behavior-preserving)
- [x] `git diff --stat -- '*.md'` is empty — **empty**
- [x] `git diff --stat -- daily-blog-post-composer/scripts/prepare-sources.py` is empty — **empty, file untouched as predicted**

Actual diffstat: **460 insertions, 274 deletions across 7 `.py` files** (plus the `Makefile` `--exit-zero` correction). The plan's "~683 changed lines" estimate came from a `diff -u` line count on the scratch copy; the git-reported figure is the same work counted differently.

**Verification — manual:**
- [x] Spot-check `weeknotes-composer/scripts/calculate-week.py` — **the only arithmetic-adjacent diff line is `'%Y-%m-%d'` → `"%Y-%m-%d"`; no change to `isocalendar`, `timedelta`, `weekday`, or `now()`**
- [x] Spot-check `daily-blog-post-composer/scripts/extract-timestamps.py:110` — **now `except Exception:` (safe F841 fix dropped the unused `as e`); still catches, still prints `Warning: Could not parse date: ...` to stderr**
- [x] `python3 weeknotes-composer/scripts/calculate-week.py --date 2026-05-20 --json` still emits valid JSON — **valid, exit 0, `week: 21`, `slug: 2026-05-20-w21`**
- [x] Extra check not in the plan: `--help` runs clean on all five argparse scripts (`extract-timestamps`, `parse-daily-post`, `prepare-sources`, `add_command`, `scaffold_project`) — catches import-level breakage the pytest suite doesn't cover, since it only exercises `standup_digest`

---

## Phase 3: Resolve the two judgment findings

Clears the 5 residual findings so `make check` is green. Two distinct causes, two distinct treatments: the `E402` cluster is a deliberate, documented import ordering that gets a config exemption; the `F841` is genuinely dead code that gets deleted.

**Files:**
- Modify: `.ruff.toml` — add a `[lint.per-file-ignores]` section
- Modify: `go-cli-builder/scripts/scaffold_project.py` — delete one dead line

**Key changes:**

Append to `.ruff.toml`:

```toml
[lint.per-file-ignores]
# This test module sets TZ=UTC and calls time.tzset() before importing datetime,
# so the timezone-sensitive window tests are deterministic regardless of the
# machine's local zone. The imports below that setup cannot be hoisted above it,
# which is exactly what E402 flags.
"standup-digest/scripts/test_standup_digest.py" = ["E402"]
```

A single documented config entry is used rather than four inline `# noqa: E402` comments: the reason is file-wide and already stated in the file's first six lines, and `noqa` markers drift as line numbers move.

In `go-cli-builder/scripts/scaffold_project.py`, inside `remove_database_from_root`, delete the dead initialization:

```python
        lines = content.split("\n")
        # Remove database flag and its binding
        filtered = []
        skip_next = False          # <- delete this line only
        for line in lines:
```

`skip_next` is never read and never reassigned anywhere in the function — `F841` is a true positive. The surrounding filter loop is untouched.

**Verification — automated:**
- [x] `make lint` passes — **"All checks passed!"** and **"8 files already formatted"**, exit 0
- [x] `make test` passes — **83 passed in 0.07s**
- [x] `make check` passes end to end, exit 0 — **exit 0**
- [x] `grep -n skip_next go-cli-builder/scripts/scaffold_project.py` returns nothing — **no output, grep exit 1**
- [x] `uvx ruff@0.16.1 check --select E402 standup-digest/scripts/test_standup_digest.py` reports no findings, while `--isolated --select E402` on the same file still reports 4 — **"All checks passed!" with config vs "Found 4 errors." isolated. The ignore is doing the work; the finding did not vanish on its own.**

**Verification — manual:**
- [x] `python3 go-cli-builder/scripts/scaffold_project.py ruff-check-cli --path <dir> --no-database` succeeds, and the generated `cmd/root.go` contains no `database` flag — **exit 0; `grep -c database` returns 0. Stronger evidence than planned: ran the same command from the pre-deletion tree into `/tmp/scaffold-before` and post-deletion into `/tmp/scaffold-after`, then `diff -r` — output is byte-identical across all 12 generated files. `skip_next` was provably dead.**
- [x] `standup-digest/scripts/test_standup_digest.py` lines 1-13 still read `import json/os/time`, then the `TZ` assignment and `tzset()`, then the remaining imports — **ordering intact. One change from Phase 2's isort pass: `import pytest` and `import standup_digest as sd` are now adjacent at lines 11-12 (previously 11 and 13 with a blank between). Both still sit below `tzset()`, which is the property that matters.**
- [x] Re-read the final `.ruff.toml`: every non-obvious setting carries a comment explaining why — **all four settings (`extend-exclude`, `target-version`, `select`, `per-file-ignores`) carry a rationale comment**

---

## Out of scope for this plan

Named here so execution refuses them (from `spec.md` "What we're NOT doing"): CI workflow, `pyproject.toml`, DTZ/timezone fixes, the `BLE001` blind-except, the three `C414` `sorted(list(...))` calls, `EXE001` (`standup_digest.py`'s shebang without an exec bit), adding annotations to the four unannotated scripts, shell/Go/JSON linting, and `make serve` / `make build`.
