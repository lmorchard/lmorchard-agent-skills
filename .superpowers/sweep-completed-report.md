# Sweep-completed feature — report

Branch `someday-sweep-completed`, base `1f35963`. All work in
`someday-triage/scripts/someday.py`, `someday-triage/scripts/test_someday.py`,
`someday-triage/SKILL.md`, `someday-triage/README.md`.

## Change 1 — preserve the checkbox in archive entries

Extracted `render_box(checked: bool | None) -> str` (returns `"[x] "`, `"[ ] "`, or `""`)
and made both `render_item` and `archive_entry` call it, so the two rendering paths
can't drift.

Covering tests (all new, all failed before the fix — verified by running
`pytest -k "completed or archive_of_item_still_open or archive_of_non_checkbox or sweep_archives"`
against the pre-change code):

- `test_archive_of_item_still_open_carries_unchecked_box` — archives an open item
  (`checked=False`) under `reason=closed`, asserts `"- [ ] dead on arrival thing"` in the
  archive. Failed before (bare `-`).
- `test_archive_of_non_checkbox_fragment_carries_bare_dash` — archives a fragment
  (`checked=None`, e.g. `batteries?`), asserts bare `"- batteries?"`, no box either way.
  This one *passed* even before the fix, because `checked is None` already rendered
  without a box — it's included as a real regression test for that case, not proof of
  a prior bug.
- `test_sweep_archives_completed_item_with_all_its_indented_content` — covers change 1
  and change 2 together (see below).

**Existing tests touched:** none. I went looking for an existing assertion that pinned
the old bare-dash form exactly (equality on a line, or `.splitlines()[0] ==`), since the
task warned this change alters archive output for `closed`/`missed`/`routed`/`merged`
entries. There isn't one — every existing archive/merge test asserts on *substrings*
of item text (`"dead on arrival thing" in archive`), which are unaffected by a
prefix change. So no existing test needed modification; the change was a pure addition
of coverage.

## Change 2 — `status` surfaces completed items

Added `completed` (int) and `completed_items` (list of `{id, text}`) to `cmd_status`'s
JSON, collected in the same walk as `intake_items` (same shape, same document-order
guarantee), but unconditional on section — i.e. across the whole file, not gated to
`# intake`. Added `completed: N` to the human-readable line (`open total: N   completed: N`).

Covering tests (new, failed before with `KeyError: 'completed_items'` / assertion on
missing "completed: 1" in stdout):

- `test_status_json_lists_completed_items_with_ids` — mirrors the existing intake-items
  test; checks id/text/order against a hand-built expectation from `someday.load`.
- `test_status_completed_items_empty_when_nothing_checked` — empty list, `completed: 0`,
  `open_total` unaffected.
- `test_status_human_readable_reports_completed` — plain-text output contains
  `"completed: 1"`.

**Existing tests touched:** none required changes — `open_total`/`intake`/`buckets`
assertions in the pre-existing status tests only ever check unchecked items, which
`completed_items` doesn't touch.

## Change 3 — SKILL.md / README.md

- **Intake mode**: inserted a new step 2, "Sweep completed items — before touching
  intake," ahead of the intake-item read. States it's autonomous — no confirmation
  needed — and to fold the sweep's `archive reason=done` ops into the same plan as the
  intake ops, asking Les's yes/no only for the ops that need it.
- **Hard rules**: split the old single "retirements need consent" bullet into the
  four-way rule the task specified — `done` on an already-`[x]` item is autonomous,
  `done` inferred from `done-check` on a still-open item needs consent, `closed`/`missed`
  always need consent, `routed` is always autonomous.
- Added a bullet documenting that `archive_entry` now preserves the checkbox state, and
  that the one carve-out from "everything indented below travels with the item" is that
  `needs-research` flag lines are stripped.
- Updated the `status` JSON reference to document `completed` and `completed_items`.
- Updated `README.md`'s test count from 109 to 115.
- Did **not** touch `journal-note/SKILL.md`.

## Real-vault sanity check

    python3 someday-triage/scripts/someday.py status --json

Result: `open_total: 131`, `completed: 43`, `digest: 3534b0adb204`. Cross-checked
independently against the raw file: `grep -c '^\- \[x\]' pages/someday.md` → 43,
`grep -c '^\- ' pages/someday.md` → 174 (131 + 43 = 174, consistent). Did not run
`apply` against the vault.

**Disagreement to flag:** the task brief states "Les just marked 41 items" and asks me
to confirm `completed` is 41. The real count is **43**, not 41, and it's internally
consistent (matches a plain grep, and open + completed sums to the full 174-item file).
I'm reporting the actual number rather than adjusting anything to match 41 — nothing in
the code looks wrong, so this reads as the estimate in the brief being off by two, not a
bug on my end. Worth a second look if 41 was load-bearing for something.

## Test suite

`make check` from repo root: ruff check clean, ruff format clean, 222 tests passed
(216 baseline + 6 new). someday-triage alone: 115 tests (109 + 6).

## Follow-up: cheap-path bail made the sweep unreachable

Coordinator review caught a real gap: "The cheap path" section's early-exit gate
(`intake == 0 and needs_research == 0` → report and stop, don't read further) was
untouched by this diff, and intake mode's step 1 bails per that same gate *before*
reaching the new step 2 sweep. The real vault's actual state — `intake: 0,
needs_research: 0, completed: 43` — hits that gate exactly, so a model following the
documented flow today stops without ever sweeping, in what is apparently the normal
between-capture-bursts state of the file.

Checked for every place the early-exit condition is restated (grep across SKILL.md and
README.md for "nothing to do", "bail", "stop", the field names): the "cheap path" section
is the sole canonical statement; intake step 1 only *refers* to it ("bail per the cheap
path"), it doesn't re-list the fields. So one edit closes the gap, not two independent
ones that could drift apart again.

Fix, docs-only, no code change (confirmed none needed — this was purely a
documentation-ordering defect, exactly as flagged):

- `someday-triage/SKILL.md`, "The cheap path": the gate now reads `intake`,
  `needs_research`, **and** `completed` all `0` before stopping, with a sentence stating
  plainly that a nonzero `completed` is never "nothing to do" and must run regardless of
  how empty everything else looks.
- `someday-triage/SKILL.md`, intake mode step 1: now names all three fields it defers to
  the cheap path for, instead of a bare "if there is nothing to do."
- `someday-triage/SKILL.md`, intake mode step 2 (the sweep): added an explicit sentence
  that it runs "before touching intake, and before any decision to stop," runs whenever
  `completed` is nonzero independent of the other two fields, and a note against a future
  edit reordering the steps and reintroducing a bail-before-sweep path.

Also checked the coordinator's discoverability question: `status`'s human-readable output
already prints `completed: N` (added in this feature), and nothing in SKILL.md told the
model to disregard that field when intake is empty — the cheap-path fix above is what
makes it load-bearing instead of decorative. No separate change needed there.

`make check` re-run after this fix: still 222 passed, ruff clean — expected, since this
was a pure documentation edit.
