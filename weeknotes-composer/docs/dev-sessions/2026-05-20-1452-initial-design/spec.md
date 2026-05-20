# weeknotes-composer — Initial Design Spec

**Date:** 2026-05-20
**Status:** Draft

## Goal

Create a new agent skill `weeknotes-composer` in `lmorchard-agent-skills/`
that composes Jekyll-style weeknotes blog posts using the `me-to-markdown`
orchestrator as its sole data source. The new skill supersedes the existing
`weeknotes-blog-post-composer` (which stays in place as legacy) and takes
advantage of all six sources that `me-to-markdown` now coordinates:

- Mastodon (posts, boosts, favorites)
- Linkding (bookmarks)
- GitHub (activity feed)
- Spotify (recently played tracks)
- YouTube (liked videos)
- Pocket Casts (listening history + starred episodes)

## Non-Goals

- Modifying the existing `weeknotes-blog-post-composer` skill.
- Wrapping or replacing functionality `me-to-markdown` already provides
  (binary install, auth flows, env-file management, parallel fetching,
  concatenated output).
- Adding new functionality to any of the `*-to-markdown` source tools.
- Building an installer / bootstrap for `me-to-markdown` itself.

## Architectural Principle: Pure Delegation

The skill is a thin composition layer on top of `me-to-markdown`. It
assumes the user has already:

1. Installed `me-to-markdown` (on `$PATH`).
2. Installed the per-source binaries (`me-to-markdown install`).
3. Authorized each source (`me-to-markdown auth`).

If any of those prerequisites are missing, the skill detects this and
points the user at the orchestrator's docs — it does **not** try to do
the install/auth work itself. This is a deliberate constraint to avoid
duplicating logic the orchestrator owns.

Concrete consequences:

- No `setup.sh`, `fetch-sources.sh`, `download-binaries.sh`, or
  `common.sh` in this skill.
- No per-source config files or API tokens managed by this skill
  (tokens, server URLs, and per-source settings all live in
  `me-to-markdown`'s env file and per-tool configs).
- No `bin/` directory of vendored binaries.
- The skill's only filesystem footprint outside its own directory is:
  - `~/.claude/cache/weeknotes-composer/data/latest/combined.md` —
    cached output from `me-to-markdown export`.
  - `~/.claude/config/weeknotes-composer/config.json` (optional) —
    holds only the `weeknotes_archive` URL for style reference.

## Skill Layout

```
weeknotes-composer/
├── SKILL.md                # Composition workflow + voice/structure guidance
├── README.md               # Brief: what it does, prerequisites, link to me-to-markdown
└── scripts/
    └── calculate-week.py   # ISO week number + output filename helper
```

That's the whole skill. No other scripts, no `assets/`, no `bin/`, no
`config/` directories shipped with the skill.

## Workflow (SKILL.md)

The composition workflow has these phases:

### 1. Preflight

Verify `me-to-markdown` is on `$PATH` (via `command -v` or
`me-to-markdown version`). If missing, instruct the user to install it
and run `me-to-markdown auth`, then stop. Do not attempt to install.

### 2. Determine Date Range

Same semantics as the legacy skill:

- Default: last 7 days (today minus 7 → today).
- Parse user phrases: "this week", "last week", "from X to Y",
  explicit ISO dates.
- Output: `--since YYYY-MM-DD --until YYYY-MM-DD` (using the
  orchestrator's flag format, which accepts ISO dates).

### 3. Fetch Combined Signal

A single command pulls all sources in parallel:

```sh
mkdir -p ~/.claude/cache/weeknotes-composer/data/latest
me-to-markdown export \
    --since "$START" --until "$END" \
    -o ~/.claude/cache/weeknotes-composer/data/latest/combined.md
```

If exit code is non-zero, the orchestrator already emitted a per-tool
error section into the combined output and printed stderr. The skill
should surface that to the user and continue with whatever data did
come back.

### 4. Read & Analyze

Read the combined file. It contains `## Mastodon`, `## Linkding`,
`## GitHub`, `## Spotify`, `## YouTube`, `## Pocket Casts` sections (in
registry order). Skim each to understand what's available this week.

### 5. Style Reference (Optional)

Check for `~/.claude/config/weeknotes-composer/config.json`. If it
exists and contains a `weeknotes_archive` URL, fetch 1-2 recent
weeknotes from that archive via WebFetch to internalize voice/style.
If the config file doesn't exist, prompt once for an optional archive
URL, write the file, and either fetch or skip. If the user declines,
record `"weeknotes_archive": null` so we don't prompt again.

### 6. Check Most Recent Weeknote

If we're in a blog directory (`content/posts/` exists), read the most
recent weeknotes post to identify topics already covered, so this
week's draft builds on rather than repeats.

### 7. Compose

Apply differentiated-by-source treatment:

- **Mastodon** — primary narrative driver. First-person prose. Link
  to posts with 3-5 word link text. Inline images (single) or
  `<image-gallery>` (3+). Plagiarism guard: only quote the user's own
  posts directly; summarize/attribute boosts and favorites.
- **GitHub** — thematic project-by-project treatment when there's
  enough signal ("spent the week on X"). Link to PRs/commits/repos.
  Demoted to Miscellanea bullets if activity is light.
- **Linkding** — Miscellanea bullets, always. Inside the
  `<div class="weeknote-miscellanea">` wrapper.
- **Spotify / YouTube / Pocket Casts** — Miscellanea bullets by
  default. Promoted to a dedicated section only when thematically
  central (e.g., "got deep into a particular album / show this week").
  Keep it light — these are passive-consumption signals that shouldn't
  dominate the narrative by volume.

Apply structural conventions (all carried over from the legacy skill):

- Jekyll YAML frontmatter: `title`, `date`, `tags`, `layout: post`,
  optional `thumbnail`.
- Title format: `YYYY Week WW` or `Month D-D, YYYY` — no "Weeknotes:"
  prefix (the tag already categorizes).
- Tags: `weeknotes` first, then 2-6 contextual tags (3-7 total).
- Opening paragraph with inline `TL;DR: ...` (not a header).
- `<!--more-->` on its own line after the opening.
- `<nav role="navigation" class="table-of-contents"></nav>` on its
  own line after `<!--more-->` when there are 2+ main sections.
- Miscellanea section near the end, just before the conclusion, with
  bullets wrapped in `<div class="weeknote-miscellanea">`.
- Concluding reflection paragraph.
- No "Generated with Claude Code" footer.

Apply voice conventions:

- Conversational, self-deprecating, parenthetical asides, playful
  language, comfortable with digression.
- Self-aware meta-commentary OK in moderation.
- Match style of past weeknotes when archive is configured.

### 8. Save Output

Detect blog directory by checking for `content/posts/`. If present:

```
content/posts/{YYYY}/{YYYY-MM-DD-wWW}/index.md
```

Use `scripts/calculate-week.py` to compute the path. Ensure both the
year directory and post directory exist (`mkdir -p`).

If not in a blog directory, save to `/tmp/weeknotes-YYYY-MM-DD.md`
and ask the user where to move it.

### 9. Cover Image

Review embedded images, pick one that represents the week's themes,
set `thumbnail:` in the frontmatter. Skip if no good candidate.

### 10. Feedback Loop

Present the draft to the user. Make requested edits.

## calculate-week.py

Carried over from the legacy skill verbatim (or near-verbatim). It
computes the ISO week number for a given date (default: today),
emits the relative output path
`content/posts/{YYYY}/{YYYY-MM-DD-wWW}/index.md`, supports `--date` and
`--json` flags. No reason to rewrite.

## Optional Skill Config

`~/.claude/config/weeknotes-composer/config.json`:

```json
{
  "weeknotes_archive": "https://blog.example.com/tags/weeknotes/"
}
```

That's the entire schema. One optional field. No tokens, no per-source
settings. If file is absent, the skill prompts once and creates it
(possibly with `null` if the user has no archive).

## Smoke Testing

Before declaring the skill done, smoke-test against real data using a
local development build of `me-to-markdown`. Procedure:

1. Build `me-to-markdown` from source in `~/devel/x-to-markdown/me-to-markdown/`.
2. Ensure the local binary shadows any installed version on `$PATH`
   (the orchestrator's `$PATH`-first resolution makes this easy).
3. Run the skill end-to-end against a real recent date range with
   actual signal across all six sources.
4. Verify each `## {Source}` section in `combined.md` is non-empty
   and well-formed.
5. Verify the composed post:
   - Has correct frontmatter (title, date, tags, layout, thumbnail).
   - Opens with inline `TL;DR:` and `<!--more-->`.
   - Has TOC nav if multiple sections.
   - Mastodon content is first-person prose with linked posts.
   - GitHub activity is thematically grouped, not a raw event dump.
   - Linkding bookmarks are in the Miscellanea div as bullets.
   - Spotify/YouTube/Pocket Casts are appropriately weighted (likely
     Miscellanea unless the week had heavy listening/watching).
   - No plagiarism (boosted/favorited content is attributed, not
     quoted as the user's own).
6. Confirm the output filename + path matches
   `content/posts/{YYYY}/{YYYY-MM-DD-wWW}/index.md` when run from a
   blog dir.

This isn't an automated test suite — it's a human-in-the-loop
verification that the workflow produces good output against real
data. The skill's correctness depends on judgment calls (what's
thematically central this week?) that can't be unit-tested.

## Adjacent Work: Stale READMEs

While building this skill, also fix:

- **`me-to-markdown/README.md`** — lists 5 registered tools in the
  "What it does" section but the registry has 6 (YouTube is wired in).
  Add YouTube to the bullet list. Check the env-file example and any
  other places that enumerate tools.
- **Sibling READMEs** — do a quick survey pass to check whether any of
  the six source tools' READMEs cross-link to the family in a way that
  omits YouTube or other newer additions. Fix any drift found.

These README fixes are tracked as part of this dev session because
they were surfaced while surveying the family for this skill design.
They are not strict prerequisites for the skill itself.

## Open Questions

None at design time. Open questions that come up during
implementation should be raised before guessing — the
"differentiated by source character" treatment in particular requires
judgment calls that the implementation plan should make concrete with
worked examples.

## Success Criteria

1. `weeknotes-composer/` exists in `lmorchard-agent-skills/` with the
   files specified above (SKILL.md, README.md, scripts/calculate-week.py).
2. Running the skill against a real week of personal-signal data
   produces a draft post that:
   - Reads as authored by the user (matches voice from archive).
   - Integrates all six sources at appropriate weight.
   - Follows all structural conventions (frontmatter, TL;DR,
     `<!--more-->`, Miscellanea div, image gallery, etc.).
   - Saves to the correct blog path.
3. The skill never duplicates work `me-to-markdown` already does
   (no auth, no install, no per-source config).
4. The `me-to-markdown` README is current (six tools listed).
5. The legacy `weeknotes-blog-post-composer` skill is unmodified and
   still works for its narrower flow.
