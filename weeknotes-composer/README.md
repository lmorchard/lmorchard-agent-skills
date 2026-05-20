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
