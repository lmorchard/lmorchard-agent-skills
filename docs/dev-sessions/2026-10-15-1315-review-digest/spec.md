# review-digest Spec

**Goal:** Gather a half-year's evidence of work from the vault and external systems, and
draft a performance self-review — in the prior review's format, scored against a career
levelling guide at current and target level — that the author then cuts down.

**Source:** user request, 2026-10-15 (see `notes.md` for the pre-brainstorm decisions).

## Current state

- No skill does this. `standup-digest` is the nearest relative: a stdlib extractor that
  shells out through one `_run` seam, plus a SKILL.md that composes under explicit
  language rules (research.md, "Repo patterns").
- Evidence is spread across: daily journals (fixed template, substance in `##` sections
  under `# notes`, mixed work/personal), standup digests (from late July), GitHub PRs,
  Linear issues (MCP, agent-side only), and Google Docs (no working auth yet — see
  research.md, "Evidence sources").
- Reference material (levelling guide transcription, prior self-review) is in the vault
  under `pages/reviews/`, deliberately not in this public repo.

## Desired end state

A new skill `review-digest/` (SKILL.md, README.md, `scripts/gather.py` + tests). One run
for a cycle (e.g. `2026-H2`) goes:

1. **Linear pull (agent).** Issues assigned to or created by the user, updated in the
   window, written to `<cache>/linear.json` (`id, title, statusType, completedAt, project,
   team, url`).
2. **Gather (script).** `gather.py --cycle 2026-H2 [--since --until] [--linear PATH]`
   writes to `<cache>` = `~/.cache/review-digest/<cycle>/`:
   - `ledger.json` — every evidence item with a stable ID, source, date, tier, and text or
     metadata; plus `warnings`/`notes` (standup-digest semantics).
   - `months/YYYY-MM.input.md` — a condensed per-month slice for a subagent, and an
     input hash per month (covers the slice, relevant overrides, and an extract-prompt
     version).
3. **Month extracts (parallel subagents).** For each month whose hash changed, a subagent
   reads its slice and writes `months/YYYY-MM.extract.md`: a section classification
   table (work / tooling / personal + one-line reason), cited accomplishments,
   collaborations, stated plans and intentions, and tentative CLG tags (dimension +
   level signal). The hash goes in the extract's frontmatter.
4. **Synthesis (main agent).** Reads the extracts, the prior self-review, and the
   levelling guide; writes three vault files under `pages/reviews/`:
   - `<cycle> self-review draft.md` — **every** candidate example in the prior review's
     shape (*Outcome / progress made*, *CLG behaviors demonstrated*, *What I'll carry
     forward and do next*), ranked; the author cuts to 1–3.
   - `<cycle> CLG evidence.md` — matrix of CLG dimension × current/target level, each
     cell listing cited evidence or "no evidence".
   - `<cycle> gap report.md` — where target-level evidence is thin, progress against the
     prior review's stated commitments, and concrete suggestions for the rest of the half.
5. **Iterate.** The author edits overrides in the config and re-runs; only months whose
   hash changed are re-extracted.

## Design decisions

- **Cache outside the vault, readable artifacts inside it.** `~/.cache/review-digest/`
  holds the ledger, slices, and extracts; the vault gets only the three outputs and the
  config.
  - **Why:** the vault's AGENTS.md says derivative artifacts live outside it.
  - **Rejected:** the ledger in the vault (sync churn, clutter).
- **Config is one JSON file in the vault:** `pages/reviews/review-digest.config.json`
  with `levels {current, target}`, `clg_path`, `prior_review_path`, `work_orgs`,
  `tooling_repos`, `linear_teams`, `heading_denylist` (case-insensitive regexes), and
  `overrides` (`evidence-id → work|tooling|personal`). The vault root comes from env var
  `REVIEW_DIGEST_VAULT` (default `~/Documents/Obsidian/main`).
  - **Why:** stdlib has `json` but not YAML; the env-var-with-default mirrors
    `SOMEDAY_VAULT` (research.md) and lets tests point at `tmp_path`. Employer-specific
    values stay out of the public repo.
  - **Rejected:** YAML (third-party dep); hardcoded org lists.
- **Cycle naming.** `--cycle YYYY-H1|H2` gives Jan 1–Jul 1 or Jul 1–Jan 1, with `until`
  capped at tomorrow's midnight; `--since/--until` override. The prior half is context
  only, via `prior_review_path` — its journals aren't gathered.
  - **Why:** the prior review's "carry forward" commitments are the useful context;
    re-reading the whole prior half doubles the cost for little gain.
- **Evidence IDs:** `j:2026-08-14#<heading-slug>` (journal section), `t:2026-08-14`
  (completed tasks that day), `sd:2026-08-14` (standup digest), `gh:owner/repo#N`,
  `lin:ABC-123`, `doc:<id-or-url-hash>`. Drafts cite them as Obsidian links (journals,
  digests) or URLs (GitHub, Linear, Docs).
  - **Why:** stable across runs so overrides keep applying; clickable for checking claims.
- **Filtering in three layers.** (1) The `heading_denylist` drops journal sections in
  the script before any LLM sees them; template sections are dropped except `# notes`,
  `# TIL`, and completed `- [x]` items in `# today`/`# this week`/`# followup`.
  *(Revised during execute: `##` sections under `# TIL` become separate items, the
  same as `# notes`, because TIL often holds full write-ups. The denylist applies
  there too.)*
  (2) GitHub repos are tiered from config: `work_orgs` → work, `tooling_repos` →
  tooling, anything else → excluded (counted in `notes`, not shown). (3) A subagent labels
  the remaining journal sections; `overrides` win and persist.
  - **Why:** the author reviews every output, so the denylist is about cheapness and
    clutter more than privacy; the deterministic layers cost nothing, and the judgment
    layer is the only one that can tell personal-project work from work.
  - **Rejected:** LLM-only filtering (unauditable, re-decides every run).
- **Tooling tier.** Personal projects used as work tooling count at lower weight:
  evidence of practice and team-standards influence, never product deliverables.
- **Docs is an adapter with three sources, one output shape.** (a) Doc URLs extracted
  from journal sections (always); (b) `pages/reviews/<cycle> docs.md`, a hand list of
  `- [title](url) — note` lines (optional); (c) the `gws` CLI through `_run`, if it's
  installed and authenticated (owned docs changed in the window, plus the user's comments
  on known docs). A missing or failing `gws` gives a `warnings` entry and falls back.
  - **Why:** gcloud's default client is blocked or deprecated for Drive scopes; Workspace
    auth is an unresolved setup task that shouldn't block the skill.
  - **Rejected:** a hand-rolled urllib Drive client (re-implements what `gws` does);
    waiting on auth.
- **GitHub via `gh search prs`** — authored PRs (merged or open) and reviewed PRs in the
  window, with the role recorded. Titles and URLs only, no bodies.
  - **Why:** PR titles plus the journal narrative carry enough; bodies blow up the slices.
- **Linear stays agent-side.** The MCP tools can't be called from a stdlib script, so the
  agent writes `linear.json` and the script merges it.
- **Draft everything, then cut.** Synthesis writes every viable example rather than
  asking the author to pick first.
  - **Why:** the author wants to see the prospective material.
- **Evidence firewall** (adapted from standup-digest's language rules, written into
  SKILL.md): *Outcome* bullets need a cited artifact (merged PR, completed Linear issue,
  doc, or digest-confirmed item); journal and standup narrative alone licenses
  "worked on / led discussion / proposed"; plans render as intent; CLG mapping is
  interpretation and says so; current-level-only evidence is labelled honestly rather
  than stretched to the target level.

## Patterns to follow

- Stdlib-only script, single `_run(cmd, timeout)` seam returning `None` on failure —
  `standup-digest/scripts/standup_digest.py:500-510`.
- Window resolution with local midnights, DST-safe shifting —
  `standup_digest.py:24-82`.
- `warnings` (degradation) vs `notes` (bookkeeping) — `standup_digest.py:703, 773-793`.
- Tests: pin `TZ=UTC` before importing datetime (`test_standup_digest.py:5-6`, plus a
  `.ruff.toml` E402 exemption); fake `_run` with `monkeypatch` and dispatch on `cmd[0]`
  (`:954-981`); lock schema key sets in a test (`:946-1000`); small fixtures in
  `scripts/fixtures/`.
- Vault root from an env var with a default — `someday-triage/scripts/someday.py:184-198`;
  tests set it to `tmp_path`.
- Add `review-digest/scripts` to the Makefile `test:` target; `make check` must pass.
- SKILL.md frontmatter has only `name` and a `description` starting "Use when…".

## What we're NOT doing

- **Workspace auth setup** — creating an OAuth client or installing and authenticating
  `gws`. That's a separate task; the adapter just uses `gws` if it's present.
- Calendar, Slack, email, or the Drive Activity API as sources.
- Handwritten notepad PDFs (personal journals).
- Gathering the prior half's journals (only the prior self-review is read).
- Harvesting git commits directly (PRs cover it; direct-to-main commits are a known gap,
  noted in the README).
- Writing to Google Docs or submitting to the HR system; outputs are vault markdown only.
- Changing `standup-digest`.
- Committing any employer-internal content to this repo — fixtures are synthetic.

## Open questions

- **Month extract prompt: in SKILL.md or a separate file?** Default: a
  `review-digest/prompts/month-extract.md` the agent passes to each subagent, versioned
  by a constant the script includes in the hash.
- **Do GitHub PRs open at window end count?** Default: included, labelled open; the
  firewall allows only "opened / in review" language for them.
- **First run scope.** Default: this session's execute phase ends with a real `2026-H2`
  run; its output tunes the prompts and firewall before the PR (structure first, then
  feel).
