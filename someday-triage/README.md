# someday-triage

Mechanical triage for `pages/someday.md` in Les's Obsidian vault. The model decides; the script
does everything that could lose data. See [SKILL.md](./SKILL.md) for the procedure the model
follows.

## Why a script

A 200-line markdown rewrite that silently drops four items looks identical to one that doesn't.
That's the entire reason this exists. The model never edits the file — it emits a JSON plan, and
`someday.py apply` validates and applies it:

- **Round-trip fidelity is a tested invariant.** `serialize(parse(x)) == x` byte for byte on a
  snapshot of the real file, so any diff after an apply is exactly the plan and nothing else.
- **Item identity is reconciled** across `someday.md` and `someday-done.md` before anything is
  written, by immutable parse-order sequence number rather than by count — a plan that retitles
  one item and drops another can't balance the books.
- **Stale plans are refused.** The plan carries a digest of the source; Obsidian is usually open
  and Syncthing is running, so a mid-sweep edit is realistic.
- **Nothing is deleted.** `archive` and `merge` both move text into `someday-done.md`.

## Commands

    someday.py status     [--json]                              counts, buckets, digest
    someday.py dupes      [--threshold 0.75] [--json]           near-verbatim duplicate groups
    someday.py lint       [--json] [--stale-days 180]           structural smells, research candidates
    someday.py done-check [--repos DIR ...] [--json]            items that may already be finished
    someday.py apply PLAN [--dry-run] [--allow-new-clusters]    the only command that writes

`status` is the cheap path: one call says whether there's anything to do. `SOMEDAY_VAULT`
overrides the vault root (default `~/Documents/Obsidian/main`).

Two commands are deliberately narrower than they look, and SKILL.md says so at length: `dupes`
catches near-verbatim repeats only (paraphrases are provably out of reach for the metric), and
`lint`'s research candidates are only what a regex can prove — a URL, a markdown link, or an
existing flag. Both nominate; the model supplies the judgment.

## Tests

    make check      # ruff lint + format check + pytest, from the repo root

76 tests. The four that justify the whole approach:

- `test_round_trip_is_byte_exact` / `test_round_trip_on_real_file` — fidelity
- `test_apply_rejects_reconciliation_failure_from_broken_serializer` — a dropped item is caught
- `test_apply_rejects_stale_plan` — digest mismatch is refused
- `test_atomic_write_leaves_original_intact_on_failure` — a failed write leaves the original

Fixtures come from the real file, including a malformed link
(`[spec kit]((https://github.com/github/spec-kit`) that must survive a round trip untouched. It's
a fixture, not a defect to quietly repair.

## Recovery

`apply` appends to `someday-done.md` **before** writing `someday.md`, deliberately. If the second
write fails, an archived item exists in both files — visible and trivially fixable. The reverse
order would leave it in neither, which is the exact failure this design exists to prevent. **Do
not reorder those two writes**; `test_archive_is_written_before_source` pins them, because the
correct order looks arbitrary and invites tidying.

If you need history, use the private `obsidian-main-backup` repo. The vault's own `.git` is an
empty directory — Syncthing carries files but not git internals — so git run against the vault
finds nothing. That's expected, not a failure.
