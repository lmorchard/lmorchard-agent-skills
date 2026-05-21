# weeknotes-composer — Session Notes (2026-05-20)

## What was built

A new agent skill at `lmorchard-agent-skills/weeknotes-composer/` that
composes Jekyll-style weeknotes from six sources of personal signal,
delegating all data collection and auth to the `me-to-markdown`
orchestrator. Files added:

- `SKILL.md` — workflow Claude follows when composing
- `README.md` — human-facing repo README
- `scripts/calculate-week.py` — ISO-week → filename helper

Commits in `lmorchard-agent-skills`:

| SHA | What |
|---|---|
| `a02d00a` | weeknotes-composer: add calculate-week helper |
| `32a7019` | weeknotes-composer: write SKILL.md |
| `991e2df` | weeknotes-composer: address review findings in SKILL.md |
| `f57fb6c` | weeknotes-composer: add README |
| `0e94c8a` | weeknotes-composer: dev session artifacts (spec, plan, notes) |
| `fd0a6fc` | weeknotes-composer: notes — catchup-window trial + corrected findings |
| `1ff67f1` | weeknotes-composer: integrate optional youtube transcripts |
| `42da8e0` | weeknotes-composer: SKILL.md — advise `<youtube-embed>` for substantive video cites |

Each commit isolated `weeknotes-composer/*` from the repo's pre-existing
uncommitted work (dev-session edits, go-cli-builder templates). Initial
commit accidentally swept up three pre-staged files; recovered via
mixed reset and recommitted cleanly. Subsequent commits used
`git stash push --staged` to neutralize the pre-staged work during
commit, then restored it. (Note: `git stash pop` does not preserve
staged-vs-unstaged distinction — the go-cli-builder files ended this
session as unstaged-modified rather than staged-modified. Content intact;
user can re-stage when ready.)

## Adjacent fixes

- **`me-to-markdown/README.md`** (commit `d689889`, pushed to main) —
  added YouTube to the tool bullet list, slug list, and env-file
  example; changed "five tools" copy to "six tools".
- **`linkding-to-markdown/README.md`** (commit `176cbba`, pushed to
  main) — "See Also" section listed only `mastodon-to-markdown`; added
  the four other siblings in registry order.
- Surveyed the other four sibling READMEs (mastodon, github, spotify,
  pocketcasts). All used generic family references rather than
  enumerated lists, so no updates needed.

## Smoke test results

### Infrastructure (subagent)

- Built `me-to-markdown` from source via `make build`. Local build
  shadows installed version via `$PATH`-first resolution.
- `me-to-markdown list` shows all six tools as `found (managed)`.
- `me-to-markdown export --since 2026-05-13 --until 2026-05-20` exited
  cleanly with no per-tool errors. Output: 2,376 lines, 128KB.
- Section breakdown by line count: Mastodon 1829, Linkding 80,
  GitHub 306, Spotify 51, YouTube 39, Pocket Casts 65. Section
  ordering matches registry order.
- `scripts/calculate-week.py` and the SKILL.md inline-Python
  equivalent both produce `content/posts/2026/2026-05-20-w21/index.md`
  for today.

### Composition trial (controller, interactive)

Composed a weeknotes draft for 2026-05-13 → 2026-05-20 following
SKILL.md against the cached `combined.md`. Output saved to
`/tmp/weeknotes-2026-05-20.md`. Verification checklist:

- Frontmatter present (title, date, tags x 6, layout, thumbnail) — ✓
- Title format `2026 Week 21`, no "Weeknotes:" prefix — ✓
- Opening paragraph with inline `TL;DR:`, then `<!--more-->` — ✓
- TOC nav present (5 main sections) — ✓
- Mastodon content composed as first-person prose with linked posts — ✓
- Boosted/favorited content attributed, not quoted as own — ✓
- GitHub treated thematically (me-to-markdown family launch) rather
  than as raw event dump — ✓
- Linkding integration: 2 of 4 bookmarks ended up in a top-level
  "Tech-work mood" section (Emacsification + ZIRP pieces) and 2 in
  Miscellanea (asm.js, Zorker). This is a *deviation* from SKILL.md's
  "Linkding always in Miscellanea" rule — see SKILL.md findings below.
- Spotify, YouTube, Pocket Casts: in Miscellanea as bullets — ✓
- Thumbnail image set to the Tahoe macOS screenshot — ✓
- No "Generated with Claude Code" footer — ✓
- Output filename: `/tmp/weeknotes-2026-05-20.md` (the not-in-blog-dir
  fallback, since the controller cwd was `x-to-markdown` not a blog
  directory).

### Catchup-window trial (controller, interactive)

After the weekly trial, ran a second composition over a 4-week
catchup window (2026-04-24 → 2026-05-20) — the user noted that
weekly is the standard cadence but they'd been remiss and missed
multiple weeks.

- Export: 4,406 lines, 6 sections all non-empty (Mastodon 3048,
  Linkding 814, GitHub 302, Spotify 79, YouTube 40, Pocket Casts 122).
- GitHub size barely changed vs the weekly export (302 → 306) — the
  events API window is short enough that a longer `--since` doesn't
  surface much more. Linkding grew ~10×. Mastodon ~1.6×.
- First catchup draft used title `"April 20 – May 20, 2026 (monthly
  catchup)"` and added a `monthly` tag. User pushed back: this isn't
  a monthly mode, it's a regular weeknote that happens to cover
  multiple weeks. Re-ran with corrected window (2026-04-24) and
  corrected framing. Final draft: `/tmp/weeknotes-2026-04-24-to-2026-05-20.md`.
- The corrected-window draft surfaced a major missed thread: the
  user's first tattoo (May 1-2). The wrong-window draft had picked
  up the backyard-pond opening posts from April 20-23 (which would
  have been in the previous weeknote) and missed the tattoo as the
  lead.
- Mastodon at 3000+ lines required deliberate sampling — grep for
  `^### My Posts$` boundaries, read those chunks, treat boosts/favs
  as thematic anchors via spot reads rather than sequential reading.

## SKILL.md findings worth a follow-up

These were observed during the two live composition trials and are
worth considering as future SKILL.md edits (not blockers for this
session):

1. **Linkding "always Miscellanea" is too rigid.** When a bookmark
   becomes thematically central (e.g., the Emacsification piece in
   the weekly trial, the cluster of AI-coding pieces in the catchup
   trial), it wants to be quoted in a real section, not summarized
   in a bullet. The Per-Source Treatment rule for Linkding should
   probably parallel GitHub: *default to Miscellanea, promote when
   thematically central*. This was observed in both trials.

2. **Catchup weeknotes (windows > 7 days) need light accommodation,
   not a separate mode.** The standard cadence is weekly. When the
   user occasionally misses a few weeks, the resulting catchup post
   is still a weeknote — same voice, same structure, just a wider
   window. Specific accommodations to add to SKILL.md:
   - **Title:** when window > 7 days, use a date-range or
     "Catching up: …" prefix rather than `{year} Week {week}`. The
     `calculate-week.py` helper assumes weekly cadence — for catchup
     windows, the title should explicitly span the period.
   - **Tags:** stay with `weeknotes` + content tags. Do NOT add
     `monthly` or similar — the post is still a weeknote.
   - **"Carryover from last week" framing** doesn't apply when
     catching up; the previous post is older and probably less
     relevant. SKILL.md's Step 4 (check most recent weeknote) should
     note: when the window covers multiple missed weeks, the previous
     post is less useful as a continuity anchor.

3. **Sampling strategy for huge Mastodon sections** (related to #2).
   At weekly scale (~1800 lines) this is annoying but doable. At
   catchup scale (3000+ lines) it's mandatory:
   - Grep `^### My Posts$` boundaries first; user's own posts are
     the prose driver and the only content directly quotable.
   - For boosts/favorites, do spot reads at thematic anchors
     identified from My Posts.
   - Do NOT attempt sequential top-to-bottom reads for windows > 7
     days. Adding this as explicit guidance in Step 5 would help.

4. **Style archive prompt-once logic was tested without a config
   file present.** I followed the SKILL.md instruction to compose
   without a style reference, but did not write the config file with
   `null` (skipped this since the smoke test shouldn't leave behind
   per-user config). The prompt-once mechanism wasn't exercised; in
   real use the skill should write the file on first encounter.

## Late-session SKILL.md additions (after the initial findings)

These were added mid-session in response to follow-up requests; they
shipped already, not deferred.

5. **YouTube transcripts integration (commit `1ff67f1`).**
   `youtube-to-markdown` ships an optional `transcripts render`
   subcommand that emits transcript prose for liked videos in a window
   (offline-only, reads a local cache populated by a separate
   `transcripts fetch` step that requires `yt-dlp`). SKILL.md now
   includes a new Step 2.5 that runs `transcripts render`
   unconditionally — if the cache is empty for the window, the
   companion file says `_No transcripts available in this window._`
   and the skill falls back to title-only YouTube content. If the
   cache is populated, the composer reads the transcripts alongside
   `combined.md` and uses the prose as the substantive source for
   YouTube content. The skill MUST NOT run `transcripts fetch` — that
   stays a user-driven workflow (yt-dlp dependency, network calls,
   can fail).

   Verified end-to-end against the catchup window: 13 of the liked
   videos in 2026-04-24 → 2026-05-20 had cached transcripts, including
   the Doctor Who essay and the OpenClaw video. The OpenClaw transcript
   in particular — a substantive AI-coding-platform autopsy — slotted
   directly into the existing AI-coding bookmarks section as a real
   case study, which would have been impossible from the title alone.

6. **`<youtube-embed>` component guidance (commit `42da8e0`).**
   The blog has a custom element `<youtube-embed video-id="..."></youtube-embed>`
   for inline YouTube players. SKILL.md now advises emitting it
   (on its own line, in its own paragraph) when a video is being
   discussed substantively — own paragraph, multiple sentences,
   transcript-derived content. Bullet-list clusters get plain markdown
   links; drive-by mentions get plain links. Rough budget: 0–3 embeds
   per post.

   No `thumbnail` attribute — the blog's `localize-images` build task
   discovers `<youtube-embed>` elements, downloads the YouTube
   thumbnail, content-addresses it into the post's page bundle, and
   rewrites the markup to add `thumbnail="<hash>.jpg"`. Archived posts
   show the rewritten form; the author types just the bare element.

   Note: the user initially referred to the element as
   `<youtube-video>`; verified against a live archived post that the
   actual name is `<youtube-embed>`. Good reminder to check live
   markup before encoding details into a skill that will be invoked
   without further review.

## Upstream bugs surfaced + outcomes

These came up while reading `combined.md` for composition. Both were
filed as issues; one was fixed in this session, one remains open.

- **mastodon-to-markdown** — favourites triplicated in fetch output.
  Originally reported as "boosts and favourites"; on diagnosis only
  favourites were affected (boosts come through `GetAccountStatuses`
  which paginates correctly by status.ID). Root cause: the favourites
  loop allocated a fresh `*mastodonAPI.Pagination` every iteration,
  discarding the in-place cursor update the go-mastodon library makes
  via the Link-header response (`mastodon.go:131`, `*pg = *pg2`). The
  manually-set `MaxID = favorites[last].ID` was also the wrong cursor
  type — the favourites endpoint paginates by an internal
  favourite-entry id, not a status id.
  - Filed: [#3](https://github.com/lmorchard/mastodon-to-markdown/issues/3)
  - Fixed in: [`592e1a4`](https://github.com/lmorchard/mastodon-to-markdown/commit/592e1a4) (pushed to main)
  - Verified: every previously-triplicated URL now appears 1x;
    unique-URL coverage unchanged (57 → 57); output ~1/3 the size.

- **github-to-markdown** — Push events all render as "pushed 0
  commit(s)" regardless of actual commit count. Other event types
  (PR, Issue, Comment, Branch create/delete) render correctly. The
  PushEvent payload includes a `commits` array (up to 20 commits with
  sha/message/author) and a `size` field which would be a simpler
  read; neither appears to be parsed.
  - Filed: [#4](https://github.com/lmorchard/github-to-markdown/issues/4)
  - **Still open at end of session.** Most natural "what's next" since
    the bug pattern is similar (single tool, narrow scope, clear repro)
    and Push events are by far the most common event type in any
    activity feed.

## What stayed in legacy `weeknotes-blog-post-composer`

The legacy skill is untouched and continues to work for its narrower
(Mastodon + Linkding) flow. It manages its own binaries and per-source
config under `~/.claude/share/` and `~/.claude/config/`. Users who don't
want to install `me-to-markdown` can keep using it.

## Next sessions

- **Fix the github-to-markdown push-event bug** (issue
  [#4](https://github.com/lmorchard/github-to-markdown/issues/4)) —
  natural next step. The bug pattern is similar to the mastodon
  triplication: single tool, narrow scope, clear repro from existing
  exports. Likely a JSON-path issue (`payload.commits` vs `payload.size`
  vs whichever field the renderer is reading). Push events are the
  most common event type in any activity feed, so the impact is
  comparable to the mastodon bug.
- Mastodon bug filing + fix is **done** this session (issue #3
  closed by `592e1a4`).
- Consider the four SKILL.md tightening ideas above when the new
  skill has been used in earnest a few times — wait for real-world
  signal before changing prompts. The Linkding-promotion softening
  and the catchup-window accommodations both replicated across two
  trials, so those have stronger signal than the others. Items #5
  and #6 (transcripts + `<youtube-embed>`) shipped in this session.
- The me-to-markdown README still has `## Adding a new tool to the
  registry` instructions but doesn't mention the family-contract
  issues (orchestrator #2/#3/#4) that propose `<tool> doctor`,
  `<tool> version --json`, and standardized `init --force`. Not a
  doc bug right now (those issues are still open and unresolved),
  but worth revisiting once they're implemented.
- The three catchup drafts in `/tmp/` are working artifacts only;
  none have been promoted to the actual blog. If the user wants the
  catchup post to ship, the canonical version is
  `/tmp/weeknotes-2026-04-24-to-2026-05-20-with-transcripts.md` and
  should be moved into the blog's `content/posts/2026/` directory
  (likely as `2026-05-20-w21/index.md` based on the standard naming).
