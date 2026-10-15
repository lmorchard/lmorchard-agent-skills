# review-digest — session notes

## Hard constraint: this repo is public

The skill holds **method only**. Employer-internal material — the career-levelling
guide, prior self-reviews, generated evidence ledgers, drafts — lives in the Obsidian
vault (`pages/reviews/`) and the skill references it by path. Session docs here
(spec/plan/notes) stay generic too: no review content, no internal project detail.

## Decisions so far (2026-10-15, pre-brainstorm conversation)

- **Purpose:** gather evidence for a half-year performance self-review and draft it.
  Reusable for future cycles (mid-year, annual, promo packets).
- **Window:** the review half (here H2: Jul 1 → now), with the prior half read for
  context — chiefly the previous self-review's stated "carry forward" commitments.
- **Sources:** daily journals (with standup-meeting sections extracted separately),
  standup digests, GitHub PRs authored + reviewed, Linear issues, Google Docs authored
  or commented. **Excluded:** handwritten notepad PDFs (personal journals).
- **Output shape:** mirrors the prior self-review — 1–3 examples, each with
  *Outcome / progress*, *CLG behaviors demonstrated*, *What I'll carry forward*. Plus
  a CLG evidence matrix (dimension × current/target level) and a target-level gap
  report with suggestions for the rest of the half.
- **Levels:** score against the current level (meets expectations) *and* the target
  level (promotion case); be honest where evidence is current-level only.
- **Evidence firewall** (borrowed from standup-digest): outcome bullets need a cited
  artifact; conversation and plans render as intent; CLG mapping is interpretation
  and is where the human iterates.
- **Personal-project filtering:** work orgs are in; personal repos out by default, with
  a small "work tooling" tier (personal projects used as work tooling — lower weight,
  evidence of practice not product). Refined by iterating on draft content; the
  exclusion list should be config, not hardcoded.
- **Process:** first real run happens inside this session so output tunes the skill
  before it's locked (structure first, then feel).

## Prior art noticed

- Vault has personal year-in-review notes (month-by-month bullets) — confirms
  journals mix personal and work heavily; filtering is load-bearing.
- `standup-digest` extractor is the model for a deterministic gather script + LLM
  composition under explicit language rules.

## Decisions during execute

- **Slice ordering (Phase 5):** within a month slice, work-authored PRs first, then
  reviewed PRs, then tooling PRs collapsed to a per-repo count plus a few sample titles.
  Tooling repos can out-number product work by PR count; the subagent's attention should
  follow weight, not volume.
- **Peer review is no longer a reliable signal.** Teams increasingly rely on AI review
  rather than human peer review, on both work and side projects. The prompts must not
  treat a low reviewed-PR count as a gap. Look instead for evidence of *shaping* the
  review and agent-delivery practice (standards, write-ups, workflow changes) — that maps
  to target-level "elevate standards / lead change" dimensions.
- **Plan defect caught by the first real run (Phase 3):** open PRs had to be bounded below
  by the window start, or never-merged PRs from years ago leak in.
- **gws phase moved ahead of the first real run**, since `gws` turned out to be installed
  and authenticated (`gws drive files list --params '{json}'`; `--page-all` gives NDJSON).

## First real run (Phase 7), 2026-10-15

Ran end to end for a half-year cycle: Linear pull → gather (~72s, ~1,440 items) → five
parallel month extracts (~3 min wall clock) → synthesis → three vault drafts. Every
evidence id cited in the drafts resolved against the ledger.

Defects the real run found, each fixed test-first:
- Linear `duplicate` status leaked through like `canceled`.
- Issues completed before the window but updated inside it made an extra month slice;
  `build_ledger` now drops dated items outside the window.
- **Plaintext credentials in journals.** Subagents spotted pasted tokens (GitHub,
  Anthropic, Google, AWS, plus an employer-specific format). The user chose to redact on
  read, not in the vault: `build_ledger` scrubs built-in credential formats and config
  `secret_patterns` before anything is written to the cache. Lesson for any
  vault-reading skill: assume journals contain secrets.
- My own masking one-liner was wrong and echoed most of one token into the session.
  When displaying a found secret, print a fixed-length prefix from Python, never a sed
  regex guess.

Tuning candidates (not done yet):
- **Linear relation.** The slice doesn't say whether the user was assignee or creator,
  so extracts can't tell "planned" from "owns". Record `relation` during the pull and
  render it.
- ~~**Citation conversion as a script.**~~ **Done:** `scripts/cite.py`, with tests. It
  rewrites drafts in place, and an unresolved id exits 1, which makes it the
  grounding check. Its output matched the first run's throwaway script byte for byte
  on all three drafts.
- **Linear pull friction.** Large MCP pages overflow to tool-result files (easy to load),
  but inline pages have to be transcribed. SKILL.md now documents the compact path.
- **Tooling-tier drift.** Extracts labelled journal sections about some personal agent
  projects as "tooling" even though the repo tiers didn't list them. Pending the user's
  call: per-id overrides, or a category rule.
- After redaction changed the slices, four months showed `stale`. Synthesis used the
  existing extracts, since the only diff was redaction markers they never quoted. The
  first override round will re-extract them anyway.

## PR self-review: adversarial pass (fresh subagent)

Every finding was verified first-hand by a failing test before its fix. All 18 new
tests failed first. Outcomes:

| # | Finding | Outcome |
|---|---|---|
| 1 | Loose `#notes`/`#til` ids collided with `## Notes`/`## TIL` section slugs | fixed: one `used` set across loose and section ids |
| 2 | Dedupe suffix could collide with a real heading (`foo`, `foo`, `Foo 2`) | fixed: suffix until unused. Positional suffixes still renumber if an earlier duplicate is added (documented) |
| 3 | `# ` lines inside code fences reset the H1, losing text and leaking denylisted bodies | fixed: fence tracking |
| 4 | Redaction skipped `url` and `meta` | fixed: recursive redaction of title, text, url, meta |
| 5 | Truncation before redaction left token fragments | fixed: cap at the last whitespace before the limit |
| 6 | Linear overrides didn't change the slice or its hash | fixed: Linear lines carry `[tier: …]` |
| 7 | Collapsed tooling samples had no citable ids | fixed: samples carry `gh:` ids |
| 8 | Malformed gws or Linear output crashed gather | fixed: pretty-printed JSON accepted; garbage warns; incomplete entries skipped and counted |
| 9 | Merged/open label trusted gh's `state` | fixed: `--merged-at` results are merged by construction |
| 10 | Org/repo matching was case-sensitive | fixed |
| 11 | Doc titles with brackets and missing URLs broke cite links | fixed: escape brackets; plain label when there's no URL |
| 12 | Anchors on duplicate headings hit the first one | fixed: duplicate headings link to the day |
| 13 | cite rewrites ids inside code fences | not fixed, documented: SKILL tells synthesis to keep paste-ready override lines unbackticked |
| low | `- [X]`, denylist on tasks, invalid docs.md date, doc text heading demotion, printed item count | fixed |
| low | `tomorrow` in task sections; GitHub dates use the UTC day | kept as is (intentional / negligible) |

Re-gathered against the real vault afterwards: no duplicate ids, and all 125 ids cited
in the first drafts still resolve.

## PR review: Copilot (12 comments, all fixed)

Each comment was verified first-hand by a failing test before the fix. 13 tests,
one parametrized over two prefixes:

| # | Finding | Outcome |
|---|---|---|
| 1 | `_cap` with no whitespace still sliced a token | fixed: drop the trailing unbroken run |
| 2 | Secrets in headings survived into slug ids | fixed: headings redacted before slugging |
| 3 | Doc-link text cut at 300 chars before redaction | fixed: keep the whole line |
| 4 | `sk-proj-` / `sk-svcacct-` OpenAI keys missed | fixed: pattern added |
| 5 | cite ignored malformed prefixed ids instead of reporting them | fixed: any backticked prefixed value counts as a citation; the ledger decides validity |
| 6 | Alias pipes in table cells broke the evidence matrix | fixed: escaped inside table rows. The vault matrix and gap report were regenerated; their diff is only pipe escapes |
| 7 | Fences toggled on any fence-looking line | fixed: close only on a matching, long-enough delimiter |
| 8 | Tooling samples hid state and author | fixed: they use the work PR formatter |
| 9 | Hash ignored levels and the levelling guide | fixed: `extraction_context` folded into the hash |
| 10 | Orphan extracts survived window changes | fixed: removed with orphan inputs |
| 11 | Comment counts included out-of-window comments | fixed: filtered by `createdTime` |
| 12 | Drive discovery listed folders and binaries as docs | fixed: query limited to Docs, Sheets, Slides |
