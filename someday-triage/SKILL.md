---
name: someday-triage
description: Use when Les wants to triage pages/someday.md — process the # intake section, file and sharpen new items, dedupe, research candidates, archive dead ideas, or run a periodic audit of the whole list. Triggers: "triage someday", "process my intake", "someday audit", or a morning-ritual pass over captured ideas.
---

# Someday Triage

Two modes over `pages/someday.md` in the Obsidian vault. All mechanical work is done by
`scripts/someday.py` — **never hand-edit the markdown.** You emit a JSON plan; the script
validates it, reconciles item identity across both files, and refuses stale plans.

Invoke the script by absolute path:

    python3 ~/.claude/skills/someday-triage/scripts/someday.py <command>

`SOMEDAY_VAULT` overrides the vault root (default `~/Documents/Obsidian/main`); the script
always reads `pages/someday.md` and `pages/someday-done.md` beneath it.

## Hard rules

- **Never edit `someday.md` or `someday-done.md` directly.** Every change goes through
  `someday.py apply`. The script guarantees no item is silently lost; freehand editing does not.
- **Always `apply --dry-run` first**, show Les the reconciliation line, then apply.
- **Retirements need consent — except when the box is already ticked.** The rule is about the
  item's *state*, which the script can see (`item.checked`), not about the reason string alone:
  - `archive reason=done` on an item that is **already `- [x]`** → autonomous. Les ticked it
    himself; that is his own declaration the thing is finished, not the tool guessing.
  - `archive reason=done` on an item that is **still open**, proposed from a `done-check` hit →
    requires Les's yes/no. There the tool is inferring, not reading a fact he already recorded.
  - `closed` and `missed` → always require yes/no, regardless of checkbox state.
  - `routed` (not someday-shaped, going to the journal) → always autonomous.
  The script does **not** enforce any of this — it only records the reason, so the archive diff
  shows which case happened. The rule lives here; keep it.
- **The archive entry preserves the checkbox.** `archive_entry` renders `- [x] `, `- [ ] `, or a
  bare `- ` for a non-checkbox fragment, matching the item's state at the moment it was retired —
  not always `- [x]` and not always bare. The one thing that does **not** travel from the source
  line: a `needs-research` flag line is stripped. That is deliberate (a stale research question on
  a retired item is noise) but it is the single carve-out from "everything indented below the item
  travels with it" — worth knowing before you go looking for a flag note that's supposed to be
  gone.
- **Never run git against the vault.** `/Users/lorchard/Documents/Obsidian/main/.git` is an
  empty directory — Syncthing carries files but not git internals. History lives in the private
  `obsidian-main-backup` repo. Anything that walks the vault for git history will correctly find
  nothing; that is expected, not a failure.
- Write the plan JSON to a temp path (`"$TMPDIR"/someday-plan.json`). Never into the vault.

## What the script cannot do

Read this before trusting any command's output. Each line below was measured, not guessed.

- **`dupes` finds near-verbatim duplicates only** — byte-identical texts and case/punctuation
  variants. It cannot find reworded duplicates, and no threshold change would fix that: on the
  real file a true paraphrased duplicate pair scored **0.4304** while an unrelated but
  surface-similar pair (`Led strip for under bar` / `Led strip for above sink`) scored **0.4858**
  — the real duplicate scored *lower*. A test pins this limitation deliberately.
  **You must read the intake items yourself for reworded duplicates.** Expect `dupes` to print
  nothing most runs; that is the tool working, not a clean list.
- **`lint`'s `research_candidates` is the provable subset only** — items containing a URL or a
  markdown link, or already carrying a `needs-research` flag. It cannot know that "get a vectrex
  flash card" names a purchasable product. **The script nominates; you add the rest.**
- **`done-check` cannot tell "already finished" from "finished before, due again."** Real cases:
  `Dentist appointment` is open *and* `- [x] dentist appointment` sits in the archive from an
  earlier cycle; likewise `haircut appointment` (twice) and `Clean furnace filter` (twice). The
  evidence is genuinely identical, so no metric separates them. **Never propose archiving a
  recurring task on a `done-check` hit.** Appointments, filter changes, haircuts, renewals,
  inspections — judgment call, always.
- **`status --json`'s `buckets` holds every level-1 heading except `# intake`**, not just the
  tiers. The real file yields `triage notes`, the five `tier N …` headings, and `unclear`. Do not
  write logic that assumes five keys, and copy bucket titles from this output rather than typing
  them — they contain em dashes.
- **The staleness sweep is currently inert.** No `(verified YYYY-MM-DD)` annotation exists
  anywhere in the real `someday.md` yet — the research notes added in the 2026-08-04
  reorganization carry no dates — so `lint`'s `stale` category reports nothing. Audit mode has to
  backfill those dates before the mechanism can ever fire. See the audit section.
- **`lint`'s `malformed_dates` category catches a marker the tooling can't read.** `VERIFIED_RE`
  only checks digit shape, so a typo like `(verified 2026-13-45)` matches the pattern but isn't a
  real calendar date. Such a note is skipped when computing staleness — the item is treated as
  having no usable verification date, same as if the note weren't there at all — and surfaced
  separately under `malformed_dates` so you know to go fix the date rather than have it silently
  ignored.
- **No op touches headings or a section's prose.** Every operation acts on an *item*. There is no
  way to add, rename, remove, or reorder a `#`/`##` heading, and no way to edit the prose body
  under one. `place` can file an item into an existing bucket or create a *cluster* with
  `--allow-new-clusters`, and that is the whole of the structural surface. So if Les asks to drop a
  section, rename a tier, or delete a paragraph of preamble, say plainly that the tool cannot and
  let him decide — do **not** reach for a hand-edit on your own initiative. If he authorises one
  anyway (reasonable for a section holding zero items, where the never-lose-an-item guarantee is
  not in play), verify afterwards that `status`'s `open_total` is unchanged and that
  `serialize(parse(text)) == text` still holds, and say you checked.

## The cheap path

Start every invocation with:

    someday.py status --json

A nonzero `completed` is never "nothing to do" — it is the completed-items sweep's whole reason
to exist (see intake mode, step 2), and it must run regardless of how empty everything else looks.
Only when `intake`, `needs_research`, **and** `completed` are all `0` should you report that plus
one line of `lint` totals and **stop** without reading the rest of the list. This is the common
morning case and the whole reason `status` exists — but it is not the common case *between*
capture bursts, when intake is typically empty and a backlog of ticked boxes is exactly what's
sitting there waiting to be swept.

## Mode: intake (default, run often)

1. `status --json`. Bail per the cheap path — checking `intake`, `needs_research`, **and**
   `completed` — if there is genuinely nothing to do. Keep the `digest`.
2. **Sweep completed items — before touching intake, and before any decision to stop.** For each
   entry in `completed_items`, emit an `archive` op with `reason: done`. This runs whenever
   `completed` is nonzero, independent of `intake` and `needs_research` — a completed item pending
   sweep is never "nothing to do," which is exactly why the cheap path in step 1 checks `completed`
   too. Do not let a future reordering of these steps put a bail check ahead of this one. This op
   is **autonomous — no confirmation needed**: a ticked `- [x]` box is Les's own declaration that
   the thing is finished, not the tool inferring one. Fold these ops into the same plan as the
   intake work below; at step 7's yes/no, ask only about the ops that need it — sweep archives are
   not among them.
3. Read the `# intake` items and the heading skeleton only — not all existing items. The ids you
   will file ops against come from that same `status --json`, under `intake_items`.
4. Gather signals: `lint --json`, `dupes --json`, and `done-check --json` (archive-only, no
   `--repos`; in intake you are only judging a handful of new items, so the noise rate is a
   non-issue).
5. **Drain order:** existing `needs-research` flags first, oldest flag date first, then new
   intake items. Budget **3 research tasks per run** — a convention you enforce, not a script
   flag — so the queue cannot starve behind a drip of new ideas. Overflow gets a `flag` op
   carrying the specific question, not research.
6. For each intake item decide, in this order:
   - **Not someday-shaped?** → `archive` with reason `routed`, then invoke the `journal-note`
     skill to place it. Appointments and anything with a date go to `# followup`; blog ideas to
     `# notes`; near-term todos to `# today` or `# this week`. Autonomous.
   - **Duplicate of an existing item?** → propose `merge`. Remember `dupes` only catches
     near-verbatim repeats; you own paraphrases.
   - **Already done?** → propose `archive` with reason `done`. Not if it is recurring. (This is
     the `done-check`-inferred case, still open — different from step 2's sweep of items already
     ticked; this one needs Les's yes/no.)
   - **Dead on the merits?** → propose `archive` with reason `closed`. Pruning on arrival is the
     point: dead ideas should never join the list.
   - **Otherwise** → `place` into a bucket and cluster, `retitle` if the wording is vague, and
     `annotate` with one concrete first step.
7. Research an item only when the answer would change its disposition. Every factual note you
   write must end in `(verified YYYY-MM-DD)`.
8. Emit the plan → `apply --dry-run` → show Les the reconciliation line → get yes/no on any
   retirements and merges that need it (see step 2 for the ones that don't) → `apply`. Report one
   line per item.

## Mode: audit (periodic, or when the list feels stale)

Runs intake first. Because pruning already happens at intake, the rest is maintenance:

1. `lint --json` and `dupes --json` over the whole file. `done-check --repos ~/devel` only here,
   and only with noise expected — measured on the real 174-item file, archive-only nominates 19
   items (~11%), while adding ~100 repos under `~/devel` nominates 105 (~60%), which is close to
   useless. Review every evidence line; never batch-accept.
2. **Stale-annotation sweep — the main job.** Research facts rot: stock counts, version numbers,
   "actively maintained."
   - **First run: backfill.** `lint --stale-days N` finds nothing today because no note carries a
     `(verified …)` date. Walk the existing research notes and `annotate` each with a dated note
     recording what is currently believed and when it was checked. Until this happens the whole
     staleness mechanism silently never fires.
   - **Later runs:** re-verify anything `lint` reports under `stale` and `annotate` the fresh
     finding with today's date.
   - No op edits or removes an existing note line, so re-verification *appends* a fresh
     `(verified YYYY-MM-DD)` note beside the old one rather than replacing it. `lint` decides
     staleness from the **most recent** `(verified …)` date on an item, not the oldest, so the
     new note is what counts — the item clears on the next `lint` once it carries a date inside
     the window, and the old note is just left in place as history. Do not work around this by
     hand-editing the file.
   - Also check `lint`'s `malformed_dates` category: a `(verified …)` note whose date isn't a
     real calendar date (e.g. a typo'd `2026-13-45`) is skipped, not treated as fresh or stale, so
     it never fires the mechanism at all. `annotate` a corrected `(verified YYYY-MM-DD)` note the
     same way you would re-verify a stale one.
3. Expiry sweep: route anything date-bound out of the list (`lint`'s `dated` category).
4. Cluster drift: propose restructuring where clusters have grown lopsided or incoherent. New
   clusters require `apply --allow-new-clusters`.
5. Apply, then write the findings to the journal via the `journal-note` skill.

## Choosing a bucket

Tiers describe **division of labour, not priority**:

1. **tier 1** — small enough to finish in one sitting; a PR-sized change.
2. **tier 2** — real projects in an agent's wheelhouse; multi-session, mostly code.
3. **tier 3** — an agent plans it or writes the code; Les does the physical half.
4. **tier 4** — an agent can research, spec, or draft; Les has to pull the trigger — purchases,
   appointments, visits.
5. **tier 5** — all Les: physical labour, in person, personal.

`unclear` is the honest answer when the division of labour is genuinely undecided; do not guess a
tier to empty it.

## Research brief template

Include these three instructions **verbatim** in every research dispatch. Each exists because
its absence cost something in the 2026-08-04 manual pass:

- "If you cannot ground a claim, say **insufficient research** for that item. Do not fill gaps
  with plausible-sounding guesses. Five solid items and four honest gaps beat nine where I cannot
  tell which is which."
- "Verify last-commit and last-release dates. Do not infer liveness from impressions — check."
- "Distinguish what you **tested live** from what you only **read in docs**. Label each."

Target decision-changing questions: is it maintained? superseded? purchasable and in stock?
already solved elsewhere? is the obvious approach a trap?

## Plan format

`digest` must be the `digest` from the `status --json` you based the plan on; `apply` exits 2 if
the file changed since.

**Where ids come from.** Ids are content hashes — `sha1(normalized text)[:8]`, `-2` suffix on
exact collisions — so **never compute or guess one by hand.** Normalization lowercases and
collapses runs of whitespace before hashing, so a hand-derived id is wrong for any text with mixed
case or a doubled space, and `apply` rejects the plan (exit 2, `unknown item ids`). Read every id
out of command output:

- **Intake work → `status --json`'s `intake_items`**, a `{id, text}` entry per open item in the
  `# intake` bucket, in document order. This is the only place ids for *ordinary* items appear;
  without it the intake flow has nothing to file ops against.
- `lint --json`, `dupes --json`, `done-check --json` carry ids **only for the items they surface**
  — one that trips no lint category, matches no duplicate and hits no archive line appears in
  none of them. Use these when acting on what they found; use `intake_items` otherwise.
- An id changes when the item's text changes, so re-snapshot after any apply.

```json
{
  "digest": "bb04e52349d8",
  "ops": [
    {"op": "place", "item": "a1b2c3d4", "bucket": "tier 1 — small enough to finish in one sitting", "cluster": "blog & site"},
    {"op": "retitle", "item": "a1b2c3d4", "text": "sharpened wording"},
    {"op": "annotate", "item": "a1b2c3d4", "notes": ["first step: ... (verified 2026-08-04)"]},
    {"op": "flag", "item": "e5f6a7b8", "question": "is it still maintained?"},
    {"op": "flag", "item": "e5f6a7b8", "remove": true},
    {"op": "merge", "into": "a1b2c3d4", "from": ["e5f6a7b8"], "note": "collapsed duplicate"},
    {"op": "archive", "item": "c9d0e1f2", "reason": "closed", "note": "why it is dead"}
  ]
}
```

- `place` — `cluster` is optional; omit it to file directly under the level-1 bucket (tier 5 has
  no clusters). Titles match exactly, no fuzzy matching. An unknown cluster is rejected unless
  `--allow-new-clusters`; an unknown bucket is always rejected.
- `annotate` — `notes` is a list of strings, appended as tab-indented bullets.
- `flag` — writes `needs-research (today): <question>`; the script formats the marker, so don't.
  `"remove": true` clears the flag instead.
- `merge` — the winner (`into`) stays; each id in `from` is archived under `collapsed duplicates`.
- `archive` — `reason` is one of `done`, `missed`, `closed`, `routed`, `merged`.

Two rules about plan *shape*, both enforced before anything is written:

- **Nothing may reference an item after the op that removes it.** Ops run in order and removal is
  final, so an `annotate` sequenced after that item's `archive` — or after the `merge` that
  archived it — would write its note to neither file. `apply` rejects the whole plan (exit 2,
  naming the id and both op indices) rather than discard the edit. Put edits *before* the removing
  op, where they still reach the archive entry; a removing op is the last word on its item, and one
  item gets at most one.
- **Field types are checked.** `notes` and `from` must be lists of strings; `item`, `into`,
  `bucket`, `cluster`, `reason`, `question`, `note`, `text` must be strings; `remove` must be a
  real `true`/`false`. `"notes": "buy it"` is refused, not spread one character per bullet, and
  `"remove": "false"` is refused rather than read as truthy and clearing the flag.

Exit codes: `0` success, `2` plan rejected (bad JSON, stale digest, unknown id, unknown bucket or
cluster, unknown reason, unsupported op, an op after the one that removes its item, a wrongly typed
field), `3` reconciliation or serializer check failed — an internal invariant broke, so stop and
report rather than retry.

## Commands

    someday.py status                                                    # counts, buckets, digest
    someday.py status     --json
    someday.py dupes      [--threshold 0.75] [--json]
    someday.py lint       [--json] [--stale-days 180] [--today YYYY-MM-DD]
    someday.py done-check [--repos DIR ...] [--json]                     # no --repos = archive only
    someday.py apply PLAN [--dry-run] [--allow-new-clusters] [--today YYYY-MM-DD]

`apply` is the only command that writes. `--today` on `lint` and `apply` exists for testing.

JSON shapes:

- `status` → `intake`, `intake_items` (list of `{id, text}`, open `# intake` items in document
  order), `completed` (count of items with `checked is True`, whole file), `completed_items`
  (list of `{id, text}`, same shape and ordering guarantee as `intake_items`, whole file, document
  order), `needs_research`, `open_total`, `buckets` (title → open count), `digest`
- `lint` → `dated`, `fragments`, `untiered`, `research_candidates`, `stale`, `malformed_dates`;
  each a list of `{id, text, bucket}`
- `dupes` → `threshold`, `groups[].items[].{id, text}`
- `done-check` → `candidates[].{id, text, matched, evidence: {source, line}}`
