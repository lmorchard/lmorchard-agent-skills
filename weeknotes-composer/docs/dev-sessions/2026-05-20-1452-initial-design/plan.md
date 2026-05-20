# weeknotes-composer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the new `weeknotes-composer` skill as a thin delegation layer on top of `me-to-markdown`, plus fix stale READMEs surfaced during design.

**Architecture:** Pure-delegation skill. SKILL.md + README.md + one Python helper. No setup scripts, no managed binaries, no per-source config — `me-to-markdown` owns all of that. Skill assumes `me-to-markdown` is installed and `me-to-markdown auth` has been run.

**Tech Stack:** Markdown (SKILL.md), Python 3 (calculate-week.py), shell invocation of `me-to-markdown`.

---

## Repo Context

Two repos are touched by this plan:

| Path | Role | Working state at plan time |
|---|---|---|
| `/Users/lorchard/devel/lmorchard-agent-skills/` | New skill lives here | Git repo. Has unrelated uncommitted work (dev-session edits, go-cli-builder template tweaks). **Do not stage those.** Stage only paths under `weeknotes-composer/`. |
| `/Users/lorchard/devel/x-to-markdown/me-to-markdown/` | Stale README to fix | Git repo (per-tool repo, sibling of other `*-to-markdown` tools). Per memory `feedback_direct_push_norm.md`, direct push to main is the norm for this family — commit + push without PR ceremony. |

Spec lives at: `/Users/lorchard/devel/lmorchard-agent-skills/weeknotes-composer/docs/dev-sessions/2026-05-20-1452-initial-design/spec.md`

The `weeknotes-composer/` directory was created during the design step (it contains the spec and this plan). The scripts/, SKILL.md, and README.md don't exist yet.

---

## File Structure

```
lmorchard-agent-skills/weeknotes-composer/
├── SKILL.md                # NEW — composition workflow + voice guidance
├── README.md               # NEW — what this skill does + prereqs
├── docs/dev-sessions/2026-05-20-1452-initial-design/
│   ├── spec.md             # already exists
│   ├── plan.md             # this file
│   └── notes.md            # NEW (last task) — final session summary
└── scripts/
    └── calculate-week.py   # NEW — copied + tweaked from legacy skill
```

x-to-markdown/me-to-markdown/:
- `README.md` — MODIFY (add YouTube to tool list + env example + tool slugs; fix "five tools" → "six")

---

## Task 1: Scaffold `scripts/calculate-week.py`

**Files:**
- Create: `lmorchard-agent-skills/weeknotes-composer/scripts/calculate-week.py`

Reuses the legacy implementation with one tweak: the spec mandates titles like `"2026 Week 20"` (no `"Weeknotes: "` prefix), so the `title` field in the helper changes accordingly.

- [ ] **Step 1: Create `scripts/` directory**

```bash
mkdir -p /Users/lorchard/devel/lmorchard-agent-skills/weeknotes-composer/scripts
```

- [ ] **Step 2: Write `calculate-week.py`**

Use the Write tool to create `/Users/lorchard/devel/lmorchard-agent-skills/weeknotes-composer/scripts/calculate-week.py` with this exact content:

```python
#!/usr/bin/env python3
"""
Calculate the current ISO week number and generate the weeknotes filename.

Usage:
    ./scripts/calculate-week.py [--date YYYY-MM-DD] [--json]

If no date is provided, uses today's date.

Output path matches the spec's blog convention:
    content/posts/{YYYY}/{YYYY-MM-DD}-w{WW}/index.md
(directory-style page bundle, not a flat file).
"""

import argparse
from datetime import datetime


def calculate_week_info(date=None):
    """Calculate week information for the given date (or today)."""
    if date is None:
        date = datetime.now()
    elif isinstance(date, str):
        date = datetime.strptime(date, '%Y-%m-%d')

    week_number = date.isocalendar()[1]
    year = date.year
    date_str = date.strftime('%Y-%m-%d')
    slug = f"{date_str}-w{week_number:02d}"

    return {
        'date': date_str,
        'year': year,
        'week': week_number,
        'slug': slug,
        'directory': f"content/posts/{year}/{slug}",
        'filename': f"content/posts/{year}/{slug}/index.md",
        'title': f"{year} Week {week_number}",
    }


def main():
    parser = argparse.ArgumentParser(description='Calculate weeknotes week number and filename')
    parser.add_argument('--date', type=str, help='Date in YYYY-MM-DD format (default: today)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    info = calculate_week_info(args.date)

    if args.json:
        import json
        print(json.dumps(info, indent=2))
    else:
        print(f"Date:      {info['date']}")
        print(f"ISO Week:  {info['week']}")
        print(f"Title:     {info['title']}")
        print(f"Directory: {info['directory']}")
        print(f"Filename:  {info['filename']}")


if __name__ == '__main__':
    main()
```

Changes vs. legacy:
- Title: `f"{year} Week {week_number}"` (no `"Weeknotes: "` prefix).
- Filename: `content/posts/{year}/{slug}/index.md` (directory-bundle), not `content/posts/{year}/{slug}.md`.
- Added `directory` and `slug` fields to the dict for convenience.
- Week number is zero-padded to 2 digits (`w03`, not `w3`) — matches spec example `2026-01-14-w03`.

- [ ] **Step 3: Make it executable**

```bash
chmod +x /Users/lorchard/devel/lmorchard-agent-skills/weeknotes-composer/scripts/calculate-week.py
```

- [ ] **Step 4: Smoke-run against today and a specific date**

```bash
/Users/lorchard/devel/lmorchard-agent-skills/weeknotes-composer/scripts/calculate-week.py
```

Expected output (date will vary):
```
Date:      2026-05-20
ISO Week:  21
Title:     2026 Week 21
Directory: content/posts/2026/2026-05-20-w21
Filename:  content/posts/2026/2026-05-20-w21/index.md
```

Then check JSON output and a pinned date for week-number-formatting:

```bash
/Users/lorchard/devel/lmorchard-agent-skills/weeknotes-composer/scripts/calculate-week.py --date 2026-01-14 --json
```

Expected:
```json
{
  "date": "2026-01-14",
  "year": 2026,
  "week": 3,
  "slug": "2026-01-14-w03",
  "directory": "content/posts/2026/2026-01-14-w03",
  "filename": "content/posts/2026/2026-01-14-w03/index.md",
  "title": "2026 Week 3"
}
```

If the week is not zero-padded to `w03`, the format string is wrong — fix it.

- [ ] **Step 5: Commit**

```bash
cd /Users/lorchard/devel/lmorchard-agent-skills
git add weeknotes-composer/scripts/calculate-week.py
git commit -m "weeknotes-composer: add calculate-week helper"
```

(Do not use `git add -A` — the repo has unrelated uncommitted changes that must stay untouched.)

---

## Task 2: Write SKILL.md

**Files:**
- Create: `lmorchard-agent-skills/weeknotes-composer/SKILL.md`

This is the brain of the skill. The legacy skill at `lmorchard-agent-skills/weeknotes-blog-post-composer/SKILL.md` is the primary source material — most voice/structure/composition guidance ports over with light edits. The fetch/setup/binary-management sections are dropped entirely and replaced with the single-command `me-to-markdown export` invocation.

**Before writing, the executor MUST read the legacy SKILL.md** so they can port voice/structure guidance verbatim where appropriate. Path: `lmorchard-agent-skills/weeknotes-blog-post-composer/SKILL.md`.

- [ ] **Step 1: Read source material**

Read these files:
- `lmorchard-agent-skills/weeknotes-blog-post-composer/SKILL.md` (legacy skill — source of voice/structure guidance)
- `/Users/lorchard/devel/x-to-markdown/me-to-markdown/README.md` (orchestrator interface — confirm flag names, output format)
- `/Users/lorchard/devel/lmorchard-agent-skills/weeknotes-composer/docs/dev-sessions/2026-05-20-1452-initial-design/spec.md` (this dev session's spec)

- [ ] **Step 2: Write SKILL.md following this structure**

Use the Write tool to create `/Users/lorchard/devel/lmorchard-agent-skills/weeknotes-composer/SKILL.md`. The file must contain the following sections in order. Where the section header says **PORT FROM LEGACY**, copy the relevant content from the legacy SKILL.md and adapt for new context (six sources, no per-source config). Where the section header says **NEW**, write fresh content per the guidance below.

**Required sections:**

1. **YAML frontmatter (NEW):**

   ```yaml
   ---
   name: weeknotes-composer
   description: Compose weeknotes blog posts in Jekyll-style Markdown from six sources of personal signal (Mastodon, Linkding, GitHub, Spotify, YouTube, Pocket Casts) via the me-to-markdown orchestrator. Use this skill when the user requests to create, draft, or generate weeknotes content for a blog post.
   ---
   ```

2. **`# Weeknotes Composer` + Overview (NEW):**
   One paragraph explaining what the skill does and what it depends on (`me-to-markdown` installed + authorized). Mention all six sources by name. State the pure-delegation principle: this skill does not manage tokens, install binaries, or run auth flows — those are `me-to-markdown`'s job.

3. **`## Prerequisites` (NEW):**
   Bulleted list:
   - `me-to-markdown` is on `$PATH`
   - `me-to-markdown install` has populated per-source binaries
   - `me-to-markdown auth` has been run (or the user has hand-written the env file)
   - Test: `me-to-markdown list` should show all six tools as resolved (status `path` or `managed`, not `missing`)
   - If any of the above fails, the skill MUST direct the user to run the relevant `me-to-markdown` command and stop — it MUST NOT attempt to install or auth on the user's behalf.

4. **`## Quick Start` (NEW):**
   The minimal happy-path command sequence:
   ```bash
   # 1. Determine the week's date range (default: last 7 days).
   # 2. Fetch combined signal:
   mkdir -p ~/.claude/cache/weeknotes-composer/data/latest
   me-to-markdown export --since YYYY-MM-DD --until YYYY-MM-DD \
       -o ~/.claude/cache/weeknotes-composer/data/latest/combined.md
   # 3. Read combined.md, then compose per the rest of this skill.
   ```

5. **`## Composing Weeknotes` (NEW + PORT):**

   Subsections:

   - **`### Step 1: Determine Date Range`** — PORT from legacy (lines ~52-71). Default last 7 days. Note the new orchestrator uses `--since`/`--until` flags both accepting `YYYY-MM-DD`. Drop the `--end +1d` quirk from the legacy (it was a workaround for one underlying tool's exclusive-end semantics; `me-to-markdown` handles end-of-day inclusivity natively per its README).

   - **`### Step 2: Fetch Combined Signal`** — NEW. The single `me-to-markdown export` command shown in Quick Start. If the command exits non-zero, the orchestrator already wrote per-tool error sections into `combined.md`; surface those to the user but continue with whatever signal did come through. Cache location is `~/.claude/cache/weeknotes-composer/data/latest/combined.md`.

   - **`### Step 3: Read and Analyze`** — NEW. Read `combined.md`. It contains six section headers (`## Mastodon`, `## Linkding`, `## GitHub`, `## Spotify`, `## YouTube`, `## Pocket Casts`) in that order. For each: skim, identify themes, note interesting items. If a section is empty or contains an error block, mention it briefly to the user.

   - **`### Step 3.5: Style Reference (Optional)`** — PORT from legacy (lines ~115-165) with one adjustment: config file path is `~/.claude/config/weeknotes-composer/config.json` (not `weeknotes-blog-post-composer`), and the schema is a single optional field `weeknotes_archive`. If the config file doesn't exist, prompt the user once for an archive URL; write the file with either the URL or `null` so we don't prompt again. The voice/structure analysis bullets ("Voice & Tone", "Structure", "Content Balance", "Transitions", "Distinctive Elements") PORT verbatim from legacy lines 130-163.

   - **`### Step 4: Check Most Recent Weeknote`** — PORT from legacy (lines ~168-173). "Before composing, read the most recent weeknotes post from the blog to identify topics already covered."

   - **`### Step 5: Compose`** — Combination of PORT + NEW. This is the largest section.

     **PORT verbatim** from legacy:
     - The voice/style guidance ("Match the user's voice...", lines ~176)
     - The Mastodon composition rules including the plagiarism guard for boosts/favorites (lines ~180-196)
     - The bookmark integration rules (lines ~197-205)
     - The cohesive narrative guidance (lines ~206-212)
     - The proper formatting checklist (lines ~213-222)
     - The example opening structure (lines ~223-234)
     - The `<image-gallery>` rules for 3+ consecutive images (lines ~241-255)
     - The Miscellanea `<div class="weeknote-miscellanea">` wrapper rule (lines ~266-277)
     - The "scan mastodon.md for images" guidance (lines ~279-305)

     **NEW per-source composition guidance** — add a new subsection `#### Per-Source Treatment` with this content (write all bullets verbatim):

     - **Mastodon** — Primary narrative driver. Write in first-person prose. Only quote your own posts directly; summarize boosts/favorites with attribution ("someone on Mastodon pointed out...") or use blockquotes. Always link to posts with 3-5 word link text. Embed images inline (single) or use `<image-gallery>` (3+). All the legacy plagiarism-guard rules apply.

     - **Linkding** — Always Miscellanea bullets inside the `weeknote-miscellanea` div. Never a top-level section. Group related bookmarks together; explain *why* something was interesting in the bullet text, don't just paste a title.

     - **GitHub** — Thematic project-by-project treatment when there's enough signal. Group events by repo/project. Write about what you actually *did* this week ("spent the week on X, fixed Y") — don't dump raw event lists. Link to specific PRs/commits/issues where they illustrate the story. If GitHub activity was light this week, demote to one or two Miscellanea bullets ("Pushed some small fixes to project X").

     - **Spotify** — Passive consumption signal. Default to Miscellanea bullets if anything at all ("Spent a lot of time with [album]"). Promote to a dedicated section ONLY when listening was thematically central to the week (e.g., a specific album in heavy rotation tied to a mood or project). Keep volume proportionate — a week of background music ≠ a week's narrative.

     - **YouTube** — Liked-videos signal. Default to Miscellanea bullets. Promote to a section only when a video or theme was notably influential ("watched [video] this week which kicked off thinking about Z"). Liked videos are a *deliberate* signal of interest, more so than Spotify plays — but still passive consumption.

     - **Pocket Casts** — Podcast listening signal. Same rule as Spotify/YouTube — Miscellanea bullets by default, dedicated section only when a specific episode or show drove a week's thinking.

     **NEW source-weighting principle** — add this paragraph after the per-source bullets:

     > The composer's job is to identify what *actually mattered* this week, not to give every source equal column inches. A week with no GitHub activity but heavy Mastodon discussion produces a post dominated by Mastodon. A week of deep work on one project produces a GitHub-thematic post. The combined.md file is raw signal; the post is curated narrative.

   - **`### Step 6: Review and Revise`** — PORT from legacy lines 307-333 verbatim. Structure check, prose polish, content verification, final touches.

   - **`### Step 7: Write the Final Blog Post`** — PORT from legacy lines 334-422 with these changes:
     - Title format: `"{year} Week {week}"` (use `scripts/calculate-week.py` to compute) — no "Weeknotes:" prefix.
     - Path computation: use `scripts/calculate-week.py --json` and read the `directory` and `filename` fields.
     - Drop the legacy bash heredoc for `mkdir -p content/posts/2026/2026-01-14-w03` — instead show using `calculate-week.py`'s JSON output.
     - PORT the "If not in the blog directory, save to /tmp/" fallback (line 422) verbatim.
     - PORT the "CRITICAL: Do NOT include Generated with Claude Code footer" rule (line 364) verbatim.

   - **`### Step 8: Select Cover Image Thumbnail`** — PORT from legacy lines 424-466 verbatim.

   - **`### Step 9: User Feedback and Final Refinement`** — PORT from legacy lines 467-476 verbatim.

6. **`## Skill Configuration` (NEW):**
   Document the optional `~/.claude/config/weeknotes-composer/config.json` schema:
   ```json
   {
     "weeknotes_archive": "https://blog.example.com/tags/weeknotes/"
   }
   ```
   One field. May be `null`. No tokens, no per-source settings — those live in `me-to-markdown`'s env file (`$XDG_CONFIG_HOME/me-to-markdown/env`).

7. **`## Troubleshooting` (NEW):**
   - **`me-to-markdown: command not found`** — install per orchestrator's README.
   - **One or more sources missing from combined.md** — run `me-to-markdown list` to see which binaries resolve. Run `me-to-markdown install` for missing ones.
   - **A source's section in combined.md contains an error block** — the per-tool error is shown there. Common cause: that tool's auth expired. Fix: `me-to-markdown auth` (it will walk through each tool; you can skip the ones already working).
   - **Empty content despite the date range covering activity** — verify your env file (`me-to-markdown export --since 24h --include mastodon -o /tmp/test.md` for a single-source smoke test).

8. **`## Resources` (NEW):**
   - `scripts/calculate-week.py` — ISO week number + output filename helper. Run with `--help` for options.
   - `~/.claude/config/weeknotes-composer/config.json` — optional skill config (style reference URL).
   - `~/.claude/cache/weeknotes-composer/data/latest/combined.md` — most recent fetched signal. Ephemeral; safe to delete.

- [ ] **Step 3: Self-check the file**

After writing, read the file back and verify:

- [ ] Frontmatter `name:` is `weeknotes-composer` (not `weeknotes-blog-post-composer`).
- [ ] `description:` mentions all six sources by name.
- [ ] No reference to `setup.sh`, `fetch-sources.sh`, `download-binaries.sh`, `common.sh`, `bin/darwin-arm64/`, or any other legacy-scaffolding artifact — those files don't exist in this skill.
- [ ] No reference to API tokens, access tokens, or per-source credentials.
- [ ] Config path is `~/.claude/config/weeknotes-composer/` (not `weeknotes-blog-post-composer`).
- [ ] Cache path is `~/.claude/cache/weeknotes-composer/data/latest/combined.md`.
- [ ] The `me-to-markdown export` command appears at least once with `--since` and `--until` flags.
- [ ] The `<div class="weeknote-miscellanea">` wrapper rule is present.
- [ ] The `<image-gallery>` rule (3+ images) is present.
- [ ] The plagiarism guard for Mastodon boosts/favorites is present.
- [ ] All six sources have explicit composition guidance.
- [ ] Title format is `"{year} Week {week}"` (no "Weeknotes:" prefix).
- [ ] Output filename references `content/posts/{YYYY}/{YYYY-MM-DD-wWW}/index.md`.

Fix any failed checks inline.

- [ ] **Step 4: Commit**

```bash
cd /Users/lorchard/devel/lmorchard-agent-skills
git add weeknotes-composer/SKILL.md
git commit -m "weeknotes-composer: write SKILL.md"
```

---

## Task 3: Write README.md

**Files:**
- Create: `lmorchard-agent-skills/weeknotes-composer/README.md`

Brief skill README aimed at humans browsing the `lmorchard-agent-skills` repo (not at Claude — that's what SKILL.md is for).

- [ ] **Step 1: Write README.md**

Use the Write tool to create `/Users/lorchard/devel/lmorchard-agent-skills/weeknotes-composer/README.md` with this content:

````markdown
# weeknotes-composer

An agent skill that composes weeknotes blog posts in Jekyll-style Markdown
from six sources of personal signal:

- Mastodon (posts, boosts, favorites)
- Linkding (bookmarks)
- GitHub (activity)
- Spotify (listening history)
- YouTube (liked videos)
- Pocket Casts (podcast episodes)

The skill is a thin composition layer on top of
[`me-to-markdown`](https://github.com/lmorchard/me-to-markdown), which
does the actual parallel fetching, auth, and binary management. This
skill assumes `me-to-markdown` is installed and authorized — it does
not duplicate any of that work.

## Prerequisites

```sh
# Install the orchestrator and its per-tool binaries.
go install github.com/lmorchard/me-to-markdown@latest   # or grab a release
me-to-markdown install

# Run the orchestrated auth flow once (per tool).
me-to-markdown auth

# Verify everything resolves.
me-to-markdown list
```

If `me-to-markdown list` shows any tool as `missing`, re-run
`me-to-markdown install`. If a tool resolves but later produces empty
output, re-run `me-to-markdown auth` for that one.

## What it does

When the user asks Claude to "draft weeknotes" (or similar), this skill:

1. Determines the date range (default: last 7 days).
2. Runs `me-to-markdown export --since … --until …` to fetch a single
   combined Markdown document covering all six sources.
3. Reads the combined file, plus (optionally) one or two past weeknotes
   for style reference.
4. Composes a Jekyll-formatted blog post with appropriate source
   weighting — Mastodon and GitHub usually drive the narrative;
   bookmarks, listening, and watching default to a Miscellanea section.
5. Saves to `content/posts/{YYYY}/{YYYY-MM-DD}-w{WW}/index.md` if run
   from a blog directory.

See `SKILL.md` for the full workflow that Claude follows.

## Relationship to `weeknotes-blog-post-composer`

This skill supersedes the older `weeknotes-blog-post-composer` skill in
this repo. The older skill remains in place for users who only want
Mastodon + Linkding signal and don't want to install the orchestrator.

Key differences:

| | `weeknotes-blog-post-composer` (legacy) | `weeknotes-composer` (this skill) |
|---|---|---|
| Sources | Mastodon + Linkding | All six (via me-to-markdown) |
| Setup | Manages its own binaries + per-source config | Defers to `me-to-markdown install` / `auth` |
| Footprint | `~/.claude/share/{skill}/bin/`, `~/.claude/config/{skill}/config.json` with tokens | `~/.claude/config/{skill}/config.json` with one optional field |

## Files

- `SKILL.md` — workflow Claude follows when composing
- `scripts/calculate-week.py` — ISO week → filename helper
- `docs/dev-sessions/` — design history (spec, plan, notes)
````

- [ ] **Step 2: Commit**

```bash
cd /Users/lorchard/devel/lmorchard-agent-skills
git add weeknotes-composer/README.md
git commit -m "weeknotes-composer: add README"
```

---

## Task 4: Fix `me-to-markdown/README.md` staleness

**Files:**
- Modify: `/Users/lorchard/devel/x-to-markdown/me-to-markdown/README.md`

The orchestrator's README enumerates 5 tools in several places but the registry has 6 (YouTube was added). Specific stale spots (line numbers from current file):

| Line | Current | Fix |
|---|---|---|
| 13-17 | 5-tool bullet list | Add YouTube bullet in registry order (between Spotify and Pocket Casts) |
| 135 | `'mastodon', 'linkding', 'github', 'spotify', 'pocketcasts'` | Add `youtube` in registry order |
| 171 | `"keeping all five tools' secrets"` | `"keeping all six tools' secrets"` |
| ~193 (env example) | Mastodon/Linkding/GitHub/Spotify/Pocket Casts vars | Add `YOUTUBE_CLIENT_ID=` and `YOUTUBE_CLIENT_SECRET=` |

Registry order (from `internal/registry/registry.go`):
1. mastodon
2. linkding
3. github
4. spotify
5. **youtube** ← was missing
6. pocketcasts

- [ ] **Step 1: Read current README**

Read `/Users/lorchard/devel/x-to-markdown/me-to-markdown/README.md` in full to confirm line numbers haven't shifted since plan-writing.

- [ ] **Step 2: Edit the tool bullet list (lines 13-17)**

Use Edit tool. Find:

```
- [`mastodon-to-markdown`](https://github.com/lmorchard/mastodon-to-markdown) — Mastodon posts, boosts, favorites
- [`linkding-to-markdown`](https://github.com/lmorchard/linkding-to-markdown) — Linkding bookmarks
- [`github-to-markdown`](https://github.com/lmorchard/github-to-markdown) — GitHub activity
- [`spotify-to-markdown`](https://github.com/lmorchard/spotify-to-markdown) — Spotify listening history
- [`pocketcasts-to-markdown`](https://github.com/lmorchard/pocketcasts-to-markdown) — Pocket Casts episodes
```

Replace with:

```
- [`mastodon-to-markdown`](https://github.com/lmorchard/mastodon-to-markdown) — Mastodon posts, boosts, favorites
- [`linkding-to-markdown`](https://github.com/lmorchard/linkding-to-markdown) — Linkding bookmarks
- [`github-to-markdown`](https://github.com/lmorchard/github-to-markdown) — GitHub activity
- [`spotify-to-markdown`](https://github.com/lmorchard/spotify-to-markdown) — Spotify listening history
- [`youtube-to-markdown`](https://github.com/lmorchard/youtube-to-markdown) — YouTube liked videos
- [`pocketcasts-to-markdown`](https://github.com/lmorchard/pocketcasts-to-markdown) — Pocket Casts episodes
```

- [ ] **Step 3: Edit the slug list (line ~135)**

Find:

```
Tool slugs match the `SLUG` column in `me-to-markdown list` (e.g. `mastodon`,
`linkding`, `github`, `spotify`, `pocketcasts`).
```

Replace with:

```
Tool slugs match the `SLUG` column in `me-to-markdown list` (e.g. `mastodon`,
`linkding`, `github`, `spotify`, `youtube`, `pocketcasts`).
```

- [ ] **Step 4: Edit the "five tools" copy (line ~171)**

Find:

```
keeping all five tools' secrets in one place without per-tool config
```

Replace with:

```
keeping all six tools' secrets in one place without per-tool config
```

- [ ] **Step 5: Edit the env-file example**

Find:

```
MASTODON_SERVER=https://mastodon.social
MASTODON_ACCESS_TOKEN=...
LINKDING_URL=https://bookmarks.example.com
LINKDING_TOKEN=...
GITHUB_TOKEN=ghp_...
SPOTIFY_CLIENT_ID=...
POCKETCASTS_EMAIL=you@example.com
POCKETCASTS_PASSWORD=...
```

Replace with:

```
MASTODON_SERVER=https://mastodon.social
MASTODON_ACCESS_TOKEN=...
LINKDING_URL=https://bookmarks.example.com
LINKDING_TOKEN=...
GITHUB_TOKEN=ghp_...
SPOTIFY_CLIENT_ID=...
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
POCKETCASTS_EMAIL=you@example.com
POCKETCASTS_PASSWORD=...
```

- [ ] **Step 6: Verify no other stale "five" / missing-YouTube references**

```bash
cd /Users/lorchard/devel/x-to-markdown/me-to-markdown
grep -n -i 'five tools\|five\b' README.md || echo "OK — no stragglers"
grep -n 'youtube' README.md
```

Expected: the "five tools" grep returns no output (or only innocuous matches like "five minutes"); the "youtube" grep shows the new mentions.

- [ ] **Step 7: Commit and push**

Per the family's direct-push norm (memory: `feedback_direct_push_norm.md`), commit and push directly to main.

```bash
cd /Users/lorchard/devel/x-to-markdown/me-to-markdown
git add README.md
git commit -m "README: list YouTube in tool inventory + env example"
git push
```

---

## Task 5: Sibling README staleness survey

**Files:**
- Read-only check across: `/Users/lorchard/devel/x-to-markdown/{mastodon,linkding,github,spotify,youtube,pocketcasts}-to-markdown/README.md`

Some sibling READMEs may cross-link to the family but omit YouTube (since YouTube is newer than the others). This task identifies and fixes such drift.

- [ ] **Step 1: Survey each sibling README for family cross-references**

```bash
cd /Users/lorchard/devel/x-to-markdown
for tool in mastodon-to-markdown linkding-to-markdown github-to-markdown spotify-to-markdown pocketcasts-to-markdown; do
  echo "=== $tool ==="
  grep -nE 'sibling|family|to-markdown\)|me-to-markdown' "$tool/README.md" 2>/dev/null || echo "  (no cross-refs)"
done
```

For each tool, look at the matching lines and judge whether:

a) The README mentions the family but omits YouTube — fix needed.
b) The README mentions the family and already includes YouTube — no change.
c) The README doesn't cross-reference the family — no change.

- [ ] **Step 2: For each tool needing a fix, edit its README**

For each tool README that needs updating, use the Edit tool to add YouTube to whatever sibling list/cross-reference is stale. Keep the registry order (mastodon → linkding → github → spotify → youtube → pocketcasts).

Common patterns to look for and fix:

- A "Siblings:" or "Related tools:" bulleted list missing YouTube — add a YouTube bullet.
- An inline prose list like "...alongside mastodon-to-markdown, linkding-to-markdown, github-to-markdown, spotify-to-markdown, and pocketcasts-to-markdown" — add youtube-to-markdown in registry order.
- An env-file example that lists per-tool vars and omits YouTube — add `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET`.

If a tool's README appears fully current, note it and move on — do not edit for the sake of editing.

(Note: `youtube-to-markdown/README.md` already includes itself, so it's automatically not stale in this dimension — but worth a quick skim for other staleness while you're there.)

- [ ] **Step 3: Commit and push each modified sibling**

For each tool that needed a fix:

```bash
cd /Users/lorchard/devel/x-to-markdown/<tool>-to-markdown
git add README.md
git commit -m "README: add YouTube to family cross-references"
git push
```

Direct push to main per the family norm.

If no siblings needed fixes, record that in the session notes (Task 7) and move on.

---

## Task 6: Local smoke test

**Files:**
- Read-only: `~/.claude/cache/weeknotes-composer/data/latest/combined.md` (produced by the test run)

This task verifies the skill works end-to-end against a real recent date range using a **local development build** of `me-to-markdown` (not a release binary). Per memory `project_orchestrator_managed_binaries.md`, the orchestrator resolves binaries `$PATH`-first then the managed dir — so a freshly built `./me-to-markdown` on `$PATH` will shadow any installed version. The per-source binaries similarly need to be the freshly-built local versions if you've changed any of them; re-`install --from-source` if so.

- [ ] **Step 1: Build `me-to-markdown` from source**

```bash
cd /Users/lorchard/devel/x-to-markdown/me-to-markdown
make build
./me-to-markdown version
```

Expected: prints version, commit, and build date for the local build.

- [ ] **Step 2: Ensure the local build is the one being used**

Decide which copy of `me-to-markdown` the skill should invoke during the smoke test. Two options:

a) **Put the local build first on `$PATH` for the smoke test**:
   ```bash
   export PATH="/Users/lorchard/devel/x-to-markdown/me-to-markdown:$PATH"
   which me-to-markdown
   ```
   Expected: `/Users/lorchard/devel/x-to-markdown/me-to-markdown/me-to-markdown`

b) **Run the local binary explicitly**: invoke as `./me-to-markdown` instead of `me-to-markdown`.

Either is fine; (a) is closer to what the skill will actually do (which uses bare `me-to-markdown`).

- [ ] **Step 3: Confirm per-source binaries resolve and auth is valid**

```bash
me-to-markdown list
```

Expected: all six tools listed, each with status `path` or `managed` and a reported version. If any are `missing`, run `me-to-markdown install` for them. If a tool is present but later fails to fetch, run `me-to-markdown auth` for it.

- [ ] **Step 4: Fetch a real week of combined signal**

Use a real recent week with known activity. For 2026-05-13 → 2026-05-20:

```bash
mkdir -p ~/.claude/cache/weeknotes-composer/data/latest
me-to-markdown export \
    --since 2026-05-13 \
    --until 2026-05-20 \
    -o ~/.claude/cache/weeknotes-composer/data/latest/combined.md
echo "Exit: $?"
ls -la ~/.claude/cache/weeknotes-composer/data/latest/combined.md
```

Expected: exit code 0, non-empty file, all six section headers present.

- [ ] **Step 5: Inspect each source section**

```bash
grep -n '^## ' ~/.claude/cache/weeknotes-composer/data/latest/combined.md
```

Expected: six lines printed, in registry order:
```
N: ## Mastodon
N: ## Linkding
N: ## GitHub
N: ## Spotify
N: ## YouTube
N: ## Pocket Casts
```

For each section, eyeball:
- Mastodon: has individual posts with URLs, boosts/favorites sections, and Media: entries where applicable.
- Linkding: has bookmarks with URLs and notes.
- GitHub: has events grouped by repo.
- Spotify: has tracks with timestamps.
- YouTube: has liked videos with titles and URLs.
- Pocket Casts: has episodes with podcast names and dates.

If any section is empty or contains an error block, record it in notes and proceed — the skill should handle partial signal gracefully.

- [ ] **Step 6: Run the skill end-to-end**

This step is the actual SKILL.md verification. In a Claude conversation (or by following SKILL.md as an executable spec), draft a weeknotes post for the same date range. Use the locally-cached `combined.md` as input.

If running interactively in Claude, the user prompt is something like:
> "Draft weeknotes for May 13-20, 2026 using the weeknotes-composer skill."

Verify the produced draft:

- [ ] Frontmatter present with `title`, `date`, `tags` (weeknotes + 2-6 others, 3-7 total), `layout: post`.
- [ ] Title format is `"2026 Week 20"` or similar (no "Weeknotes:" prefix).
- [ ] Opening paragraph has inline `TL;DR: ...` (not a header).
- [ ] `<!--more-->` on its own line after the opening.
- [ ] TOC nav (`<nav role="navigation" class="table-of-contents"></nav>`) present if 2+ main sections.
- [ ] Mastodon content is first-person prose, not a list dump.
- [ ] Boosted/favorited content is attributed (not quoted as the user's own).
- [ ] GitHub activity is thematic, not raw event dump.
- [ ] Linkding bookmarks are bullets inside `<div class="weeknote-miscellanea">`.
- [ ] Spotify / YouTube / Pocket Casts content is in Miscellanea unless thematically central.
- [ ] Images are embedded inline (single) or in `<image-gallery>` (3+).
- [ ] No "Generated with Claude Code" footer.
- [ ] Output filename matches `content/posts/2026/2026-05-20-w20/index.md` (or appropriate week) if run from a blog directory.
- [ ] `thumbnail:` field set to a meaningful image URL (or omitted if no good candidate).

- [ ] **Step 7: Record smoke test results**

Record in the session notes (Task 7) for each verification:
- Which checks passed
- Which checks failed (with the specific output that failed)
- Any SKILL.md fixes needed
- Any orchestrator/source-tool bugs surfaced (those go into separate dev sessions for those repos, not this one)

If SKILL.md needs fixes, make them, re-commit, and re-run the smoke test.

---

## Task 7: Write session notes

**Files:**
- Create: `lmorchard-agent-skills/weeknotes-composer/docs/dev-sessions/2026-05-20-1452-initial-design/notes.md`

Per the user's CLAUDE.md dev-session convention, capture a final summary of the session before committing to git.

- [ ] **Step 1: Write `notes.md`**

Use the Write tool to create `/Users/lorchard/devel/lmorchard-agent-skills/weeknotes-composer/docs/dev-sessions/2026-05-20-1452-initial-design/notes.md` with these sections:

```markdown
# weeknotes-composer — Session Notes (2026-05-20)

## What was built

- New skill `weeknotes-composer` in `lmorchard-agent-skills/`
- Files: `SKILL.md`, `README.md`, `scripts/calculate-week.py`
- Pure delegation to `me-to-markdown` — no setup scripts, no binaries, no per-source config

## Adjacent fixes

- `me-to-markdown/README.md` updated to list 6 tools (YouTube was missing)
- Sibling READMEs surveyed for similar staleness: [list which ones were fixed, or "none needed updates"]

## Smoke test results

[fill in from Task 6 Step 7]

## What stayed in legacy `weeknotes-blog-post-composer`

The legacy skill is untouched. It continues to work for users who want
Mastodon + Linkding only and don't want to install `me-to-markdown`.

## Next sessions

- [any follow-up items surfaced during smoke testing — likely empty if the
  smoke test passed cleanly]
```

- [ ] **Step 2: Commit**

```bash
cd /Users/lorchard/devel/lmorchard-agent-skills
git add weeknotes-composer/docs/dev-sessions/2026-05-20-1452-initial-design/notes.md
git commit -m "weeknotes-composer: dev session notes"
```

(Leave the spec.md / plan.md commits to whoever set the session up — they may already be staged or committed.)

---

## Final Self-Review Checklist

Before declaring this plan complete, the executor confirms:

- [ ] All seven tasks above are checked off.
- [ ] `weeknotes-composer/` exists with the three planned files.
- [ ] No legacy-scaffolding artifacts (setup.sh, fetch-sources.sh, bin/, etc.) were created in the new skill.
- [ ] `me-to-markdown/README.md` lists six tools.
- [ ] Smoke test produced a real composed weeknotes draft that satisfied all verification checks.
- [ ] `notes.md` captures any deviations from this plan and any open follow-ups.
- [ ] No commits accidentally swept up the unrelated uncommitted work in `lmorchard-agent-skills` (dev-session edits, go-cli-builder template tweaks).
