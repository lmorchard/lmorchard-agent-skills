# someday-triage — design spec

Date: 2026-08-04

## Problem

`pages/someday.md` in the Obsidian vault is a dumping ground for ideas captured throughout the day. It accumulates and never gets triaged. A one-off manual triage on 2026-08-04 processed 209 open items and found:

- **8 items were dead on the merits** — the tool was abandoned, superseded, or unsafe. They had sat on the list for months or years attracting no attention and no decision.
- **1 item was already finished** — a mermaid web component, shipped seven months earlier with a published blog post, checkbox still open.
- **1 item had expired** — a gallery exhibit with an end date, on a list with no concept of dates.
- **~24 items were duplicates or near-duplicates**, including three separate copies of the same idea.

The value was concentrated in *removal and correction*, not in sorting. A triage process that only sorts is a slow reread.

The manual pass also cost three research subagents and a large token spend for nine researched items. That is not a repeatable weekly cost, but the research is where the removals came from. So the design problem is: **how to get research-driven pruning at a cadence that survives contact with a morning routine.**

## Goals

1. Make triage cheap enough to run daily and valuable enough to be worth running.
2. Prune on arrival rather than on audit — dead ideas should never join the list.
3. Never silently lose an item.
4. Route non-someday items (appointments, dated events, real todos, blog ideas) to where they belong.
5. Keep research facts from rotting silently.

## Non-goals

- Automatic scheduling. Manual invocation only for v1; Les intends a morning ritual and will automate later if the habit does not form. The design must not preclude adding a cron or session-wrapup trigger later.
- Generalizing the *judgment* layer to other documents. The parser is generic; tier semantics and routing rules are someday-specific.
- Touching git in the vault. `/Users/lorchard/Documents/Obsidian/main/.git` is an **empty directory** — Syncthing carries files but not git internals, so there is no local git data. History lives in the private backup repo `github.com/lmorchard/obsidian-main-backup`. Any code that walks the vault for git history will correctly find nothing; that is expected, not a failure.

## Core architecture: the model never edits the markdown

The model emits a **plan** (JSON); a tested script applies it. Every mutation goes through one validated path.

Operations:

| op | effect |
|---|---|
| `place` | file an intake item into a tier + cluster |
| `annotate` | add nested note bullets to an item |
| `retitle` | rewrite item text (sharpen vague wording) |
| `merge` | collapse duplicates into one item, archiving the losers |
| `archive` | move an item to `someday-done.md` under a reason section |
| `flag` | add or remove a `needs-research` note |

`archive` carries a `reason` that determines whether it needs approval:

- `reason: routed` — the item is not someday-shaped and is going to the journal. **Autonomous.**
- `reason: done` / `closed` / `missed` — the item is being retired on the merits. **Requires yes/no.**

This is the one op with split autonomy, so the distinction lives in the data rather than in the skill's prose.

Three properties follow:

**Round-trip fidelity as a tested invariant.** `serialize(parse(x)) == x` byte-for-byte for an unmodified file. If that holds, any diff after applying a plan is exactly the plan and nothing else.

**Automatic reconciliation.** The script computes items-in, items-out, and a per-operation delta, and refuses to write if anything is unaccounted for. In the manual pass this arithmetic was done by hand (209 → 174 with every unit of the delta explained); it must not depend on someone bothering.

**Stale-plan rejection.** The plan carries a digest of the source file. `apply` refuses if `someday.md` changed since the snapshot was taken. Obsidian is typically open and Syncthing is running, so a mid-sweep edit is realistic. Given recovery requires the backup repo, refusing beats merging.

**`apply` never deletes.** `archive` and `merge` both move text into `someday-done.md`. No operation destroys a line.

### Deliberately not in the script

- **Tier and cluster assignment, sharpening, kill judgment.** No heuristic decides whether something is tier 2 or tier 3.
- **Routing to the journal.** When an item is not someday-shaped, the script removes it and records where it went; placing it in the journal is `journal-note`'s job, invoked separately. Duplicating that logic would create two writers of the journal that disagree about conventions.

## Generalization seam

The parser knows nothing about "someday" — heading-bucketed checklists with nested notes are a common Obsidian shape. Document-specific knowledge lives in a named **profile** (default `someday`): the bucket heading pattern, that `# intake` is the inbox, and which file is the archive. Adding `--profile reading-list` later is config, not a new parser.

## Data model

```
Document  preamble, sections[]
Section   level (1 = bucket, 2 = cluster), title, body, items[]
Item      id, checked, text, notes[], raw
```

- `raw` is retained per item so fidelity is provable rather than reconstructed.
- `id` is a content hash, `sha1(normalized_text)[:8]`, with a `-N` suffix for exact collisions. Not an index, so a plan survives unrelated lines moving. Exact-text collisions surface as duplicates, which is the signal we want.

## CLI

```
someday.py status      [--json]                intake count, needs-research depth, per-tier, digest
someday.py dupes       [--threshold] [--json]  duplicate candidate clusters
someday.py done-check  [--repos DIR...]        already-done candidates
someday.py lint        [--json]                structural smells + research candidates
someday.py apply PLAN  [--dry-run]             the only mutating command
```

`status` is the cheap morning path: one call, and if intake and the research queue are both empty the skill stops without reading the whole list.

`lint` reports mechanical smells only, never content judgment:

- items whose text contains a date or deadline (the expiry failure mode)
- non-checkbox fragments (e.g. a bare `batteries?` line)
- items outside any tier
- notes orphaned from their item
- **research candidates**: the script detects only what it can do reliably — items containing a URL or a markdown link, and items with a `needs-research` flag. Recognizing that "get a vectrex flash card" names a purchasable product with no link attached is model work. The script nominates; the model adds to the list. Overstating what the regex can do here would produce a queue that misses exactly the items that most need checking.
- **stale annotations**: notes whose `(verified YYYY-MM-DD)` date is older than the staleness threshold (default 180 days, `--stale-days`)

### Marker formats

Pinned so they round-trip and stay greppable in Obsidian:

- research flag: `- needs-research (YYYY-MM-DD): <the specific question>` — a nested note bullet on the item. Carries its own question so the next run does not re-derive it, and its own date so queue age is visible.
- verified annotation: a research note bullet ending in `(verified YYYY-MM-DD)`.

`done-check` checks each item's distinctive terms against `someday-done.md` and optionally `~/devel` repos, nominating a candidate when at least 2 of an item's terms co-occur on a single line of some file. Tuned for recall over precision: a false positive costs one glance, a false negative cost seven months. (An earlier version matched terms against one lowercased blob of all haystack text with a looser threshold; measured on the real 174-item vault, that nominated 40% of open items from the archive alone and 95% with `--repos ~/devel` added, because enough concatenated text makes almost any pair of common words co-occur *somewhere*. Rejected in favor of the single-line co-occurrence rule above, which keeps the same recall-over-precision intent but requires the match to mean something.)

`--repos` skips `.git`, `node_modules`, `.superpowers`, `.venv`, `venv`, `dist`, `build`, `__pycache__`, `.tox`, and this project's own `docs/dev-sessions/` tree — without that, the tool matches its own dev-session reports (which quote real item text) as if they were independent evidence of completion. That bug alone accounted for a third of one real audit run's hits.

Even with that fixed, `--repos` stays noisy by design and is audit-only, not part of routine intake: intake only ever runs `done-check` on the 2-3 new intake items in a run, where noise is negligible, while a full-vault audit run measures roughly 10% of all open items nominated from the archive alone versus roughly 60% with `--repos ~/devel` (~100 code repos) added. The gap is `distinctive_terms` ranking rarity *within the vault* — words rare in a todo list (`build`, `check`, `system`, `agent`) are common in software documentation, so a large enough pile of markdown makes them co-occur by chance. The principled fix (rank against the haystack, not the vault) is not being built: the archive is a curated record of finished work, a hundred code repos are just prose, and scanning them for "have I done this" was always a stretch. Use `--repos` for a deliberate audit with noise expected, not routine intake.

`done-check` cannot distinguish "already finished" from "finished before, due again" — a recurring task (an appointment, a filter change, a renewal) legitimately shows up both open and in the archive, and no threshold fixes that because the evidence is genuinely identical. **Never propose archiving a recurring task on a `done-check` hit alone.**

## Modes

### `intake` (default, run often)

1. `status --json`. If intake and the research queue are both empty, report that plus a one-line `lint` summary and stop.
2. Read only the intake items and the heading skeleton — not all existing items.
3. `lint --json` to nominate research candidates; `dupes` (intake vs everything); `done-check` on intake items.
4. **Drain order:** `needs-research` queue first, oldest first, then new intake items. Shared budget of N research tasks per run (default 3) so the queue cannot starve behind a drip of new ideas.
5. Per item, decide in order: is it someday-shaped? → duplicate of an existing item? → already done? → otherwise `place`, `retitle` if vague, `annotate` with one concrete first step.
6. If an item is a research candidate and budget remains, research it now. Otherwise `flag` it with the specific question.
7. Dead-on-arrival items are proposed for `archive` at entry, so they never join the list.
8. Kill and merge proposals are presented for yes/no. Placing, annotating, sharpening, and routing are autonomous.
9. Emit plan → `apply --dry-run` → show reconciliation → `apply`. Report one line per item.

### `audit` (run quarterly, or when the list feels stale)

Runs `intake` first, then:

1. `lint` and `dupes` across the whole file; `done-check --repos ~/devel`.
2. **Stale-annotation sweep** — the primary job. Research facts rot: stock counts, version numbers, "actively maintained." Items whose `(verified …)` date is past threshold get re-verified.
3. Expiry sweep: anything date-bound routed out.
4. Cluster drift: propose restructuring if clusters have grown lopsided or incoherent.
5. Apply, then write findings to the journal via `journal-note`.

Because pruning happens at intake, audit is maintenance and review rather than a repeat of the original heavyweight pass.

## Research brief template

Encodes three lessons from the manual pass, each of which changed an outcome:

1. **"Say *insufficient research* rather than guess."** Two of nine researched items returned honest gaps, which was more useful than confident filler. A report where you cannot tell which parts are grounded is worse than a shorter one.
2. **Verify last-commit and last-release dates.** Do not infer liveness from impressions. Several corrections were projects that looked dead but were not (CodeMirror: every GitHub repo archived, development moved to self-hosted Forgejo) or looked alive but were not (Takahē: never archived, zero commits in two years).
3. **Distinguish live-tested from docs-only.** Every finding that changed a decision came from exercising the thing: the IA Availability API returning `200` with an empty result for a site archived since 1997; `lychee --suggest` silently emitting nothing on current stable; unpaced Wayback requests producing a TCP connection refusal rather than a `429`, so status-code retry logic never fires.

Research should target decision-changing questions specifically: is it maintained? superseded? purchasable and in stock? already solved elsewhere? is the obvious approach a trap?

## Error handling

- Malformed markdown: parse errors cite line numbers and refuse to proceed.
- Plan references an unknown item id: reject.
- Plan targets a nonexistent cluster: reject unless `--allow-new-clusters`.
- Reconciliation shortfall: reject, report the unaccounted items.
- Digest mismatch: reject as stale.
- Writes are atomic — temp file plus rename, so an interrupted run leaves the original intact.
- Empty intake and empty queue: exit successfully and cheaply.

## Testing

Fixtures are drawn from the real file, which is where the useful edge cases are.

**Fidelity and parsing**
- `serialize(parse(x)) == x` byte-for-byte on a snapshot of the real `someday.md`.
- Malformed link survives round-trip: the real file contains `[spec kit]((https://github.com/github/spec-kit` — unbalanced parens, no closing bracket. This is a fixture, not a defect to quietly repair.
- Nested notes indented with tabs and with spaces; wikilinks containing pipes and brackets; `- [x]` items; non-checkbox bullets; sub-bullets that are themselves checkboxes; headings containing em-dashes.

**Duplicate detection**
- Positives: **near-verbatim only** — byte-identical texts and case/punctuation variants. Amended 2026-08-04: the `logotron` ×3 and spotify ×3 clusters are *paraphrased* duplicates and are provably out of reach for this metric (the true logotron pair scores 0.4304 versus the unrelated LED pair's 0.4858, so no threshold separates them). `dupes` is specified as a near-verbatim detector; a test pins the logotron trio as not grouping, and the model owns paraphrase detection.
- **Hard negative:** "Led strip for under bar" vs "Led strip for above sink" — ~90% string similarity, must not merge. This test is the one that keeps the threshold honest.

**Safety**
- Reconciliation catches an injected dropped item.
- Stale-plan rejection fires on digest mismatch.
- `--dry-run` leaves file mtime unchanged.
- Simulated mid-write failure leaves the original file byte-identical.

These four safety tests are the justification for the whole script-backed approach. Everything else is convenience.

## Implementation order

The spec is one skill, but it should land in phases so the risky part is proven before the convenient parts are built:

1. **Safety core** — parser, serializer, round-trip test, `status`, `apply` with reconciliation, digest rejection, atomic write. At the end of this phase the skill can already do a useful hand-driven triage safely, and the four safety tests pass.
2. **Analysis commands** — `dupes`, `lint`, `done-check`, with the known-answer fixtures from the 2026-08-04 pass as regression tests.
3. **`SKILL.md` and the two modes** — intake flow, research budget and queue drain, audit's stale-annotation sweep, research brief template.

Phase 1 is the part that justifies the approach; do not start phase 3 before its tests are green.

## Repo integration

- Skill lives at `someday-triage/` in `~/devel/lmorchard-agent-skills`, following the `laurels` pattern: `SKILL.md`, `scripts/someday.py`, `scripts/test_someday.py`, optional `README.md`.
- Add `someday-triage/scripts` to the Makefile `test` target.
- `make link` picks it up automatically via the `*/SKILL.md` glob.
- `make check` (ruff lint + format + pytest) is the gate.

## Open questions

None blocking. Two decisions deferred by choice:

- **Trigger automation.** Manual for v1. If the morning ritual does not stick, add either a cron run or a `session-wrapup` nudge; the design does not preclude either.
- **Research budget default.** Starting at 3 items per run. Tune once there is real usage data on how many ideas arrive per day.
