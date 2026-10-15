# review-digest Implementation Plan

**Goal:** A `review-digest` skill. A stdlib gather script builds a cited evidence ledger
plus per-month slices for a review cycle; SKILL.md drives the Linear pull, parallel month
extracts, and synthesis into a draft self-review, a CLG evidence matrix, and a gap report.

**Approach:** Deterministic gathering and filtering in `gather.py` (journals, digests,
docs, GitHub, merged Linear), all behind one `_run` subprocess seam. The cache lives in
`~/.cache/review-digest/<cycle>/`, config and outputs in the vault. Judgment work
(classification, CLG mapping, drafting) belongs to subagents under an evidence firewall
written into SKILL.md and `prompts/`.

**Tech stack:** Python 3.10+ stdlib only; `gh` CLI; Linear MCP (agent-side); optional
`gws` CLI; pytest via `uv run --with pytest`; ruff via `make lint`.

**Shared definitions (used across phases):**

```python
SCHEMA_VERSION = 1
PROMPT_VERSION = 1          # must match the version line in prompts/month-extract.md
VAULT_ENV = "REVIEW_DIGEST_VAULT"
DEFAULT_VAULT = Path.home() / "Documents" / "Obsidian" / "main"
CONFIG_REL = Path("pages/reviews/review-digest.config.json")
CACHE_ROOT = Path.home() / ".cache" / "review-digest"
SECTION_CHAR_LIMIT = 6000

@dataclass(frozen=True)
class Window:
    since: date   # inclusive
    until: date   # exclusive

@dataclass
class Config:
    levels: dict            # {"current": "IC4", "target": "IC5"}
    clg_path: str           # vault-relative
    prior_review_path: str  # vault-relative
    work_orgs: list[str]
    tooling_repos: list[str]        # "owner/name"
    linear_teams: list[str]         # empty = every team counts as work
    heading_denylist: list[str]     # case-insensitive regexes on ## headings
    overrides: dict[str, str]       # evidence id -> work|tooling|personal

# Ledger item (a dict, so it serialises directly):
# {"id", "source": journal|tasks|digest|github|linear|doc, "date": "YYYY-MM-DD" | None,
#  "tier": work|tooling|unclassified, "title", "text", "url", "meta": {...}}
```

Ledger top level: `schema_version, cycle, window{since,until}, generated_at, config_path,
items, warnings, notes, months{"YYYY-MM"|"undated": {"input_hash", "items"}}`.

---

## Phase 1: Journal evidence into a ledger

`gather.py --cycle 2026-H2` reads the config and the journals in the window, and writes
`ledger.json` containing journal-section and completed-task items, with the denylist and
template rules applied.

**Files:**
- Create: `review-digest/scripts/gather.py`
- Create: `review-digest/scripts/test_gather.py`
- Create: `review-digest/config.example.json` (synthetic values only)
- Modify: `Makefile` — add `review-digest/scripts` to `test:`
- ~~Modify: `.ruff.toml` — E402 exemption~~ — **not needed:** window logic is date-only
  (journals are per-day), so the tests need no TZ pin. Also adapted during execute:
  `build_ledger(config, window, cycle, items, warnings, notes)` takes no vault, the ledger
  has no `config_path` key, `main(argv, today=None)` takes `today` for tests, and
  `--no-github` exists from Phase 1 (a no-op until Phase 3).

**Key changes:**
- `resolve_cycle(cycle: str, today: date, since: str|None, until: str|None) -> Window`.
  `"2026-H2"` → Jul 1 2026 to Jan 1 2027; `"2026-H1"` → Jan 1 to Jul 1. `until` is capped
  at `today + 1 day`. `--since`/`--until` (YYYY-MM-DD) override either bound. A bad cycle
  string or `until <= since` raises `ValueError`.
- `vault_root() -> Path` — `$REVIEW_DIGEST_VAULT`, else `DEFAULT_VAULT`.
- `load_config(path: Path) -> Config` — JSON → Config. A missing file raises
  `FileNotFoundError`; `main` turns that into exit 2 with "copy config.example.json to
  <path>".
- `slugify(heading: str) -> str` — reduces `[[a/b|c]]` to `c` and `[[x]]` to `x`,
  lowercases, turns runs of non-alphanumerics into `-`, strips, truncates to 60.
- `parse_journal(day: date, text: str, denylist: list[re.Pattern]) -> tuple[list[dict], int]`
  — returns (items, dropped_count):
  - Tracks the current `# H1`. Keeps only `# notes` and `# TIL`, plus completed tasks.
  - Under `# notes`: each `## heading` block → item `j:<day>#<slug>` (title = heading).
    Text before the first `##` (if non-blank) → `j:<day>#notes`. Repeated slugs on one
    day get `-2`, `-3`.
  - `# TIL` block (non-blank) → one item `j:<day>#til`.
  - Lines matching `^\s*- \[x\] ` under `# today`, `# tomorrow`, `# this week`, or
    `# followup` → one item `t:<day>` whose text joins the task lines.
  - A `##` heading matching any denylist pattern is dropped along with its body, and
    `dropped_count` increments.
  - Text longer than `SECTION_CHAR_LIMIT` is cut and ends with `\n[…truncated]`;
    `meta.truncated = true`.
  - Every item gets `tier = overrides.get(id, "unclassified")` (applied later in
    `build_ledger`), `url = None`, and `meta.path = "journals/YYYY/YYYY-MM-DD"`.
- `discover_journals(vault: Path, window: Window) -> list[tuple[date, Path]]` — globs
  `journals/*/YYYY-MM-DD.md` and keeps dates in `[since, until)`.
- `build_ledger(vault, config, window, cycle, sources) -> dict` — `sources` is the list
  of collected items; applies overrides and assembles the top level. Notes get
  "dropped N journal sections by heading_denylist" and "truncated N sections".
- `main(argv) -> int` — args `--cycle` (required), `--since`, `--until`, `--config`
  (default `vault_root()/CONFIG_REL`), `--cache` (default `CACHE_ROOT/<cycle>`). Writes
  `<cache>/ledger.json`. Prints a summary (`items: N`, warnings, notes) to stdout.

```python
_TASK_RE = re.compile(r"^\s*- \[x\] (.+)$")
_LINK_RE = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]")
TASK_SECTIONS = {"today", "tomorrow", "this week", "followup"}
KEEP_SECTIONS = {"notes", "til"}
```

Tests (written first, each failing before the code exists):
- `test_resolve_cycle_h2_caps_at_tomorrow` — today 2026-10-15 → (2026-07-01, 2026-10-16).
- `test_resolve_cycle_h1_full` — today 2026-12-01 → (2026-01-01, 2026-07-01).
- `test_resolve_cycle_rejects_bad_string` — `"2026-Q3"` raises `ValueError`.
- `test_parse_journal_keeps_notes_sections_and_til` — template with `# daily` / `# today`
  / `# notes` (two `##`) / `# TIL` → ids `j:D#alpha`, `j:D#beta`, `j:D#til`; nothing from
  `# daily`.
- `test_parse_journal_collects_completed_tasks` — `- [x] ship it` under `# today` and
  `- [ ] not yet` → one `t:D` item containing only "ship it".
- `test_parse_journal_denylist_drops_section` — `## therapy` with denylist `["^therapy$"]`
  → dropped_count 1, no item contains its body text.
- `test_parse_journal_slug_handles_wikilinks_and_dupes` — `## 1:1 w/ [[people/x|x y]]`
  → `1-1-w-x-y`; two `## standup` → `standup`, `standup-2`.
- `test_parse_journal_truncates_long_section` — 7000-char body → text ends with
  `[…truncated]`, `meta.truncated` true.
- `test_override_sets_tier` — override `{"j:D#alpha": "personal"}` → that item's tier is
  `personal`; the others stay `unclassified`.
- `test_main_writes_ledger` — `tmp_path` vault (env var set) with config plus two
  journals (one outside the window) → `ledger.json` exists; `schema_version == 1`; only
  in-window items present.
- `test_main_missing_config_exits_2`.
- `test_ledger_top_level_keys` — locks the top-level key set.

**Verification — automated:**
- [x] `uv run --with pytest pytest review-digest/scripts -q` passes — **19 passed**
- [x] `make check` passes — **ruff clean, 254 passed**

**Verification — manual:**
- [x] `config.example.json` has no employer-specific values — synthetic orgs/repos only
- [x] Against the real vault with a scratch config: `python3 review-digest/scripts/gather.py --cycle 2026-H2 --cache /tmp/rd-test` gives a plausible item count, and the denylisted headings appear in the notes count, not in items — **273 items (241 journal, 32 tasks), ~506k chars; 15 sections denylisted, 15 truncated.** One therapy-prefixed heading slipped past an anchored scratch pattern: config tuning, not a code defect.

---

## Phase 2: Standup digests and docs

Adds standup digests (`sd:` items), Google Doc links found in kept journal sections, and
the optional hand-kept `docs.md`, all as ledger items.

**Files:**
- Modify: `review-digest/scripts/gather.py`
- Modify: `review-digest/scripts/test_gather.py`

**Key changes:**
- `collect_digests(vault: Path, window: Window) -> list[dict]` — `standup-digests/YYYY-MM-DD.md`
  in the window → item `sd:<date>`, source `digest`, tier `unclassified`, text = file
  contents (capped at `SECTION_CHAR_LIMIT`), `meta.path = "standup-digests/<date>"`.
- `extract_doc_links(items: list[dict]) -> list[dict]` — scans journal and task items for
  `_GDOC_RE`; one item per doc id: `doc:<id>`, source `doc`, date = first mention,
  title = `"<kind> <id[:8]>"`, url = canonical `https://docs.google.com/<kind>/d/<id>`,
  text = the first line that mentions it (≤300 chars),
  `meta = {"kind", "mentions": [ids], "origin": "journal"}`, tier `unclassified`.
- `parse_docs_md(text: str) -> list[dict]` — lines
  `- [title](url) — note (YYYY-MM-DD)`; the date suffix is optional. Id is `doc:<gdoc-id>`
  if the URL is a Google Doc, else `doc:` + `sha1(url)[:10]`. Date = the suffix or `None`.
  `meta.origin = "docs.md"`, tier `work`. A docs.md entry with the same id as a
  journal-found doc is merged into it: title and note from docs.md, mentions kept.
- `main` reads `vault/pages/reviews/<cycle> docs.md` if present; if absent, adds the note
  "no <cycle> docs.md".

```python
_GDOC_RE = re.compile(r"https://docs\.google\.com/(document|spreadsheets|presentation)/d/([A-Za-z0-9_-]+)")
_DOCS_MD_RE = re.compile(r"^\s*-\s*\[(?P<title>[^\]]+)\]\((?P<url>[^)]+)\)\s*(?:[—-]\s*(?P<note>.*?))?\s*(?:\((?P<date>\d{4}-\d{2}-\d{2})\))?\s*$")
```

Tests (first):
- `test_collect_digests_in_window_only`
- `test_extract_doc_links_dedupes_and_records_mentions` — the same doc in two days'
  sections → one item, date = earlier day, two mentions.
- `test_extract_doc_links_ignores_denylisted_sections` — the link only appears inside a
  dropped section → no doc item.
- `test_parse_docs_md_with_and_without_date`
- `test_docs_md_merges_with_journal_doc`

**Verification — automated:**
- [x] `uv run --with pytest pytest review-digest/scripts -q` passes — **25 passed**
- [x] `make check` passes — **ruff clean, 260 passed**

**Verification — manual:**
- [x] A real-vault scratch run shows about a dozen `doc:` items for H2, with sensible first-mention lines — **12 docs, 28 digests.** Doc titles are id stubs; the gws phase supplies real titles for owned docs. Adapted: `merge_docs(found, listed)` is its own function rather than inline in `parse_docs_md`.

---

## Phase 3: GitHub PRs

Adds authored and reviewed PRs via `gh search prs`, tiered by config; excluded repos are
counted in notes only.

**Files:**
- Modify: `review-digest/scripts/gather.py`
- Modify: `review-digest/scripts/test_gather.py`

**Key changes:**
- `_run(cmd: list[str], timeout: int = 60) -> str | None` — same contract as
  standup-digest's (`standup_digest.py:500-510`); copied, not imported, because skills
  are independent.
- `month_ranges(window: Window) -> list[tuple[date, date]]` — calendar-month chunks
  clipped to the window (inclusive end dates for gh's `A..B` syntax).
- `collect_github(config: Config, window: Window, warnings: list, notes: list) -> list[dict]`:
  - For each month chunk and each role in (`author`, `reviewed-by`):
    `gh search prs --<role>=@me --merged-at A..B --limit 1000 --json number,repository,state,title,url,closedAt,createdAt,author`.
  - Once: `gh search prs --author=@me --state open --limit 1000 --json …`, keeping only
    PRs with `createdAt < until`.
  - Item: `gh:<owner/name>#<n>`, source `github`, date = `closedAt[:10]` (merged) or
    `createdAt[:10]` (open), title = PR title, url,
    `meta = {"role": "author"|"reviewer", "state": "merged"|"open", "repo", "pr_author"}`.
  - Tier: owner in `work_orgs` → `work`; `owner/name` in `tooling_repos` → `tooling`;
    otherwise excluded (not emitted), counted per repo into one note
    `"excluded N PRs from M repos not in work_orgs/tooling_repos"`.
  - `None` from `_run` → warning `"gh search failed (<role>, <A>..<B>); GitHub evidence incomplete"`.
    Exactly 1000 results → warning `"gh search hit the 1000-result cap (<role>, <A>..<B>)"`.
    Unparseable JSON → warning.
  - Dedupe by id; author wins over reviewer.
- `main` gains `--no-github` (skip, with the note "GitHub skipped (--no-github)").

Tests (first; `_run` monkeypatched and dispatching on argv contents):
- `test_month_ranges_clips_to_window` — Jul 1 → Oct 16 gives four chunks, the last
  Oct 1..Oct 15.
- `test_collect_github_tiers_and_excludes` — PRs in a work org, a tooling repo, and a
  personal repo → two items with the right tiers; one exclusion note.
- `test_collect_github_open_prs_dated_by_created`
- `test_collect_github_failure_warns` — `_run` returns `None` → warning, no crash.
- `test_collect_github_cap_warns` — 1000 results → cap warning.
- `test_main_no_github_never_calls_run` — a `boom` fake asserts no subprocess.

**Verification — automated:**
- [x] `uv run --with pytest pytest review-digest/scripts -q` passes — **33 passed**
- [x] `make check` passes — **ruff clean, 268 passed**

**Verification — manual:**
- [x] A real scratch run: PR counts per work repo look plausible against the org listing from brainstorm, and no personal repos appear in items — **804 PRs (801 merged, 3 open), Jul 6 – Oct 15; 662 PRs from 20 repos excluded; ~42s for 9 searches.** The first real run exposed a plan defect: open PRs were kept when `createdAt < until`, which pulled in never-merged PRs from 2014–2025. Fixed to `since <= createdAt < until`, with a regression test. Also added a `--no-gws` flag (a no-op until the gws phase).

---

## Phase 4: Linear merge

`--linear PATH` merges the agent-written Linear JSON into the ledger.

**Files:**
- Modify: `review-digest/scripts/gather.py`
- Modify: `review-digest/scripts/test_gather.py`

**Key changes:**
- `load_linear(path: Path, config: Config, notes: list) -> list[dict]` — input is a JSON
  list of `{id, title, statusType, completedAt, project, team, url}`.
  - `statusType == "canceled"` → skipped and counted in notes.
  - `team` not in `linear_teams` (when the list is non-empty) → skipped and counted.
  - Item: `lin:<id>`, source `linear`, date = `completedAt[:10]` or `None`, tier `work`,
    title, url, `meta = {"status": statusType, "project", "team"}`.
- `main`: `--linear` defaults to `<cache>/linear.json` if that exists; otherwise adds the
  warning "no Linear data (run the Linear pull first)".

Tests (first):
- `test_load_linear_skips_canceled_and_other_teams`
- `test_load_linear_undated_when_not_completed`
- `test_main_warns_without_linear`

**Verification — automated:**
- [x] `uv run --with pytest pytest review-digest/scripts -q` passes — **38 passed**
- [x] `make check` passes — **ruff clean, 273 passed**

**Verification — manual:**
- [x] none beyond automated (exercised for real in Phase 7) — n/a

---

## Phase 5: Month slices, hashes, and staleness

Writes `months/<YYYY-MM>.input.md` (plus `undated.input.md`) with an input hash, and
reports which month extracts are missing or stale.

**Files:**
- Modify: `review-digest/scripts/gather.py`
- Modify: `review-digest/scripts/test_gather.py`
- Create: `review-digest/prompts/month-extract.md` — must contain the line
  `prompt_version: 1` (its full content comes in Phase 6; this phase creates the file
  with the version line and a heading so the invariant test can run)

**Key changes:**
- `month_key(item) -> str` — `item["date"][:7]` or `"undated"`.
- `render_month(cycle: str, month: str, items: list[dict]) -> str` — a body with sections
  in a fixed order: Journal sections, Completed tasks, Standup digests, GitHub PRs
  (work-authored, then reviewed, then tooling collapsed to `<repo>: N PRs` plus up to 5
  sample titles), Linear issues, Docs. Each item header:
  `### <id> — <date> — <title> [tier: <tier>]`, followed by its text, or for
  GitHub/Linear/doc a single line with url and meta. Items are sorted by (date, id) for
  determinism.
- `input_hash(body: str) -> str` — `sha256(f"{PROMPT_VERSION}\n{body}")[:16]`.
- `write_months(cache: Path, cycle: str, items: list[dict]) -> dict[str, dict]` — writes
  each `months/<m>.input.md` as frontmatter (`cycle`, `month`, `input_hash`,
  `prompt_version`) plus body; returns `{m: {"input_hash", "items"}}` for the ledger.
- `month_status(cache: Path, months: dict) -> dict[str, str]` — `"missing"` if
  `months/<m>.extract.md` doesn't exist; `"stale"` if its frontmatter `input_hash`
  differs; else `"fresh"`.
- `main` prints a status table (`2026-07  stale`) after the summary.

Tests (first):
- `test_render_month_is_deterministic` — shuffled input → identical output.
- `test_input_hash_changes_with_override` — flipping one override changes the tier label,
  and with it the hash.
- `test_input_hash_changes_with_prompt_version` — monkeypatch `PROMPT_VERSION`.
- `test_month_status_missing_stale_fresh`
- `test_prompt_file_version_matches_constant` — reads `prompts/month-extract.md` and
  asserts `prompt_version: {PROMPT_VERSION}` is present (structural invariant: the prompt
  and the hash can't drift).

**Verification — automated:**
- [x] `uv run --with pytest pytest review-digest/scripts -q` passes — **50 passed**
- [x] `make check` passes — **ruff clean, 285 passed**

**Verification — manual:**
- [!] A real scratch run writes four month files plus undated; one month file reads cleanly as subagent input — **four month files, no undated** (undated only appears once Linear or docs.md bring undated items; the logic is covered by `test_write_months_and_status`). ~200–245 KB per month (~60k tokens), which is fine for a subagent. The real run exposed two defects, both fixed test-first: (1) `# TIL` blocks hold full `##` write-ups, so TIL is now split into sections like `# notes`, and the denylist applies there too; (2) `##` headings inside digest and journal text collided with the slice structure, so `demote_headings` now pushes them down three levels. Also added: slices for months no longer present get removed.

---

## Phase 6: Skill instructions and prompts (doc-only; TDD opt-out)

SKILL.md, README.md, the month-extract prompt, and the synthesis guidance: everything the
agent needs to run the pipeline end to end.

**Files:**
- Create: `review-digest/SKILL.md` — frontmatter `name: review-digest`, description
  "Use when Les is preparing a performance self-review, promo packet, or wants a cited
  summary of a half's work…". Sections:
  1. **Setup** — config path, copying `config.example.json`, the optional `<cycle> docs.md`.
  2. **Run** — (a) Linear pull: `list_issues` with `assignee: "me"` and `creator: "me"`,
     `updatedAt: <since>`, deduped, written to `<cache>/linear.json`; (b)
     `python3 ~/.claude/skills/review-digest/scripts/gather.py --cycle <c>`; (c) dispatch
     one subagent per `missing`/`stale` month with `prompts/month-extract.md` and that
     month's input path, all in parallel; (d) synthesis.
  3. **Synthesis** — read the extracts (never the raw ledger), the prior review at
     `prior_review_path`, and the CLG at `clg_path`; write the three vault files named in
     the spec; every candidate example in the prior review's shape; rank by target-level
     signal.
  4. **Evidence firewall** — the table of evidence → permitted phrasing (merged PR /
     completed Linear issue / doc → shipped, wrote, led; open PR → opened, in review;
     journal or standup narrative only → worked on, proposed, discussed; plans → intent);
     CLG mapping labelled as interpretation; current-level-only evidence said plainly;
     the tooling tier never presented as a product deliverable; `warnings` → a degraded-run
     line at the top of each output.
  5. **Iterate** — editing `overrides`, re-running gather, re-extracting only stale months.
  6. **Public-repo rule** — the skill holds method only; internal content stays in the vault.
- Modify: `review-digest/prompts/month-extract.md` — `prompt_version: 1`; inputs; an output
  template: frontmatter `input_hash` copied from the input, a classification table
  (`id | label | reason`, labels work/tooling/personal, existing non-`unclassified` tiers
  respected), accomplishments (each citing ids), collaborations (people and teams, cited),
  stated plans and intentions (intent language), tentative CLG tags (`dimension | level
  signal | ids`); firewall rules repeated in short form; personal-labelled items excluded
  from every section except the table.
- Create: `review-digest/README.md` — what it is, data flow, known gaps (direct commits,
  Docs auth, reviewed-PR dating by merge date), and how to run the tests.

**Verification — automated:**
- [x] `make check` passes (the prompt-version invariant still holds) — **292 passed**
- [x] `grep -riE "mozilla|ichabod|tabstack|pilo|CLOUD-" review-digest/` finds nothing — **exit 1, no matches**

**Verification — manual:**
- [ ] Les reads SKILL.md and the month-extract prompt; the firewall table matches the spec

---

## Phase 7: First real run and tuning (manual; structure, then feel)

Run the pipeline for `2026-H2` against the real vault, review the outputs with Les, and
tune the prompts and firewall. Code changes only if the run exposes a gather defect, each
with a failing test first.

**Steps:**
1. Write `pages/reviews/review-digest.config.json` with Les: levels IC4 → IC5, paths to
   the CLG and H1 review notes, `work_orgs` (the three confirmed in brainstorm),
   `tooling_repos` (the two confirmed in brainstorm), `heading_denylist` (therapy,
   medication), and empty `overrides`.
2. Linear pull → `~/.cache/review-digest/2026-H2/linear.json`.
3. `gather.py --cycle 2026-H2`; review the summary and warnings.
4. Dispatch the month extracts in parallel; spot-check one against its input.
5. Synthesis → the three vault files.
6. Les reviews; record misclassifications as overrides; re-run (only stale months
   re-extract); tune the prompt wording (bumping `PROMPT_VERSION` and the prompt's line
   together).
7. Record learnings in `notes.md` (generic; no review content).

**Verification — automated:**
- [x] `make check` passes after any tuning changes — **303 passed** (after duplicate-skip, out-of-window drop, and secret redaction fixes)

**Verification — manual:**
- [ ] The second run re-extracts only the months whose overrides changed
- [ ] Every Outcome bullet in the draft cites at least one evidence link that resolves
- [ ] Les judges the draft useful as raw material, and the gap report actionable

---

## Phase 8 (conditional): `gws` Docs adapter

**Executed before Phases 6 and 7**, since `gws` was installed and authenticated
mid-session. Verified syntax: `gws drive files list --params '{json}' --page-all` (NDJSON,
one page per line), `gws drive files get`, `gws drive comments list`; the keyring notice
goes to stderr. Adapted beyond the plan: comment counts are split into
`{by_me, by_others}` (comments from others on owned docs are evidence of "solicit
feedback on proposals"), known non-owned docs get title and owner via `files.get`, and
an autouse fixture now refuses any unfaked `_run` (three older tests had been reaching
the real `gws`).

Only if `gws` is installed and authenticated by this point; otherwise skip, and record it
in `notes.md` as a follow-up. The `gws` command syntax is **unverified**. Confirm it from
`gws --help` and its README before writing the fake in the tests.

**Files:**
- Modify: `review-digest/scripts/gather.py`, `test_gather.py`, `SKILL.md`, `README.md`

**Key changes:**
- `collect_gws_docs(window, warnings) -> list[dict]` — via `_run`, lists Drive files the
  user owns with `modifiedTime` in the window (Drive v3 `files.list` with
  `q="'me' in owners and modifiedTime >= '<since>T00:00:00Z' and trashed = false"`,
  fields `id, name, mimeType, modifiedTime, webViewLink`). Items: `doc:<id>`, source
  `doc`, `meta.origin = "gws"`, merged with journal and docs.md doc items by id. If `gws`
  is not found or fails → warning `"gws unavailable; Docs from journal links and docs.md only"`.
- Comments on known docs (Drive v3 `comments.list`, filtered to the current user) are added
  as `meta.my_comments` counts, if the CLI exposes them.

Tests (first): `test_collect_gws_docs_maps_files`, `test_collect_gws_missing_warns`,
`test_gws_doc_merges_with_journal_doc`.

**Verification — automated:**
- [x] `uv run --with pytest pytest review-digest/scripts -q` passes — **57 passed**
- [x] `make check` passes — **ruff clean, 292 passed in 0.67s**

**Verification — manual:**
- [x] A real run lists owned docs changed in H2, and they show up in the right months — **25 docs (13 owned, 12 colleagues') with real titles, owners, and comment counts; 1 known doc unreadable (noted). Full gather ~72s.**
