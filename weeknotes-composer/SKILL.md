---
name: weeknotes-composer
description: Compose weeknotes blog posts in Jekyll-style Markdown from six sources of personal signal (Mastodon, Linkding, GitHub, Spotify, YouTube, Pocket Casts) via the me-to-markdown orchestrator. Use this skill when the user requests to create, draft, or generate weeknotes content for a blog post.
---

# Weeknotes Composer

This skill composes weeknotes blog posts in Jekyll-style Markdown by fetching personal signal from six sources — Mastodon, Linkding, GitHub, Spotify, YouTube, and Pocket Casts — through the `me-to-markdown` orchestrator, then synthesizing that signal into a readable, first-person blog post. The skill is a pure delegation layer: it calls `me-to-markdown export` to collect all data in one combined file, then reads and composes from that file. It does not manage tokens, install binaries, or run auth flows — those are `me-to-markdown`'s job. Output is a Jekyll-style Markdown file with YAML frontmatter saved to the blog's standard post directory structure.

## Prerequisites

- `me-to-markdown` is on `$PATH` — verify with `me-to-markdown version`
- `me-to-markdown install` has been run to populate its managed binaries
- `me-to-markdown auth` has been run (or the user has hand-written the env file at `$XDG_CONFIG_HOME/me-to-markdown/env`)
- Verify all tools resolve: `me-to-markdown list` — all six tools should show status `path` or `managed`, not `missing`
- **If any prerequisite fails, the skill MUST direct the user to run the relevant `me-to-markdown` command and stop. The skill MUST NOT attempt to install binaries or run auth flows on the user's behalf.**

## Quick Start

```bash
# Determine the week's date range (default: last 7 days).
# Then fetch combined signal:
mkdir -p ~/.claude/cache/weeknotes-composer/data/latest
me-to-markdown export --since YYYY-MM-DD --until YYYY-MM-DD \
    -o ~/.claude/cache/weeknotes-composer/data/latest/combined.md
# Optional: also render YouTube transcripts if the cache has any.
# Offline-only; produces a "no transcripts available" file if cache is empty.
youtube-to-markdown transcripts render --since YYYY-MM-DD --until YYYY-MM-DD \
    -o ~/.claude/cache/weeknotes-composer/data/latest/youtube-transcripts.md
# Then read both files and compose per the workflow below.
```

## Composing Weeknotes

The primary workflow for composing weeknotes follows these steps:

### Step 1: Determine Date Range

By default, use the last 7 days (from 7 days ago to today). If the user specifies a different timeframe, parse their request and extract start/end dates.

Examples of user requests:
- "Draft weeknotes for this week" → 7 days ago to today
- "Create weeknotes for last week" → 14 days ago to 7 days ago
- "Generate weeknotes from November 4-10" → 2025-11-04 to 2025-11-10

**Default date calculation:**
```python
from datetime import datetime, timedelta
today = datetime.now()
end_date = today.strftime("%Y-%m-%d")
start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
```

So if today is Thursday November 14, 2025:
- Start date: Thursday November 7, 2025
- End date: Thursday November 14, 2025

Use ISO date format (`YYYY-MM-DD`) for both flags. The orchestrator handles end-of-day inclusivity natively — pass `--until YYYY-MM-DD` directly with no adjustment.

### Step 2: Fetch Combined Signal

With start/end dates from Step 1, run the orchestrator to collect all six sources in parallel:

```bash
mkdir -p ~/.claude/cache/weeknotes-composer/data/latest
me-to-markdown export --since YYYY-MM-DD --until YYYY-MM-DD \
    -o ~/.claude/cache/weeknotes-composer/data/latest/combined.md
```

If the exit code is non-zero, the orchestrator has already written per-tool error sections into `combined.md`. Surface those error sections to the user (so they know which source failed and why), but continue composing with whatever signal did come through. A partial run is better than no post.

### Step 2.5: Fetch YouTube Transcripts (Optional)

`youtube-to-markdown` ships an optional companion command, `transcripts render`, that emits transcript text for liked videos in the window — actual prose, not just titles. This is offline-only (reads from a local cache; no yt-dlp, no network), so it's safe to run unconditionally:

```bash
youtube-to-markdown transcripts render \
    --since YYYY-MM-DD --until YYYY-MM-DD \
    -o ~/.claude/cache/weeknotes-composer/data/latest/youtube-transcripts.md
```

If `youtube-to-markdown` is on `$PATH` (it should be after `me-to-markdown install`), run this. If the binary isn't found, skip silently.

Look at the resulting file. Three outcomes:

- **Populated** — multiple `### [Title](URL)` blocks each followed by prose. Use this content when composing the YouTube section; transcripts are the actual signal here, not the title-only listings in `combined.md`.
- **`_No transcripts available in this window._`** — the user has not run `youtube-to-markdown transcripts fetch` for this window. The cache is empty for this period. Compose YouTube content from titles only (as in `combined.md`), and at the END of the workflow (Step 9 feedback) mention the user can run `youtube-to-markdown transcripts fetch --since YYYY-MM-DD --until YYYY-MM-DD` (requires `yt-dlp` installed) before re-running the skill if they want richer YouTube context next time.
- **Some videos with transcripts, others without** — use transcript prose where available; treat the rest as title-only.

The skill MUST NOT run `transcripts fetch` itself — that step requires yt-dlp, makes network calls, takes time, can fail, and is intentionally a user-driven workflow.

### Step 3: Read and Analyze

Read `~/.claude/cache/weeknotes-composer/data/latest/combined.md`. The file contains six section headers in registry order:

- `## Mastodon`
- `## Linkding`
- `## GitHub`
- `## Spotify`
- `## YouTube`
- `## Pocket Casts`

Skim each section. Identify themes, note interesting items, get a sense of what this week was actually about. If a source's section is empty or contains an error block, mention it briefly to the user — but treat the active sources (Mastodon, GitHub, Linkding) differently from passive ones (Spotify, YouTube, Pocket Casts). For active sources, absence may be worth flagging ("no Mastodon activity this week — was that intentional?"). For passive sources, absence usually just means a quiet week and you can silently omit them from the composed post.

If Step 2.5 produced a populated transcripts file, also read `~/.claude/cache/weeknotes-composer/data/latest/youtube-transcripts.md`. For videos with transcripts, the prose body is the substantive content — the title alone is rarely enough to know whether a video was thematically central. Skim for ideas, arguments, vivid moments, or things that connect to the week's other threads.

### Step 3.5: Style Reference (Optional)

**Check for configured style reference:**

```bash
# Check if weeknotes_archive URL is configured
cat ~/.claude/config/weeknotes-composer/config.json
```

If the config contains a `weeknotes_archive` URL, fetch and review 1-2 of the user's past weeknotes to understand their writing style and voice. Use the WebFetch tool to analyze the archive page and individual posts.

If the config file doesn't exist, prompt the user once for an optional archive URL. Write the config file with either the provided URL or `"weeknotes_archive": null` if the user declines or has no archive — this prevents re-prompting on future runs.

If no `weeknotes_archive` is configured (or the file has `null`), skip this step and compose in a conversational blog post style.

**Key style elements to look for in past weeknotes:**

1. **Voice & Tone:**
   - Conversational and self-deprecating
   - Frequent parenthetical asides and tangents
   - Playful language (e.g., "Ope", casual interjections)
   - Self-aware meta-commentary about the writing process itself

2. **Structure:**
   - Starts with an opening paragraph containing inline "TL;DR: ..." summary
   - Followed by `<!--more-->` on its own line (marks intro for Jekyll excerpt)
   - 2-3 deeper dives into specific projects or topics (main body)
   - **"Miscellanea" section near the end** (just before conclusion) for brief observations and items that didn't fit elsewhere
     - **CRITICAL:** Use bullet points for each item in Miscellanea
     - **CRITICAL:** Include ALL bookmarks/links here as bullet points, not in a separate section
     - **CRITICAL:** Wrap the Miscellanea bullet points in `<div class="weeknote-miscellanea">` tags
     - Miscellanea is a catch-all grab bag for everything else: short observations, bookmarks, reading, random thoughts
   - Concluding reflection on the week

3. **Content Balance:**
   - Equal weighting of technical depth and personal reflection
   - Mixed technical projects, personal observations, and humor
   - Philosophy embedded in technical writing
   - Comfortable with digression and associative thinking

4. **Transitions:**
   - Uses bullet points and whitespace rather than formal prose bridges
   - Ideas progress through thematic gravity or personal relevance
   - Stream-of-consciousness feel ("notes accumulated throughout the week")

5. **Distinctive Elements:**
   - Metaphorical thinking (uses analogies to explain technical challenges)
   - Acknowledges when feeling scattered or self-doubting
   - References to ongoing projects and past posts
   - Comfortable admitting uncertainty or work-in-progress status

When composing, aim to match this voice rather than writing in a generic blog style.

### Step 4: Check Most Recent Weeknote

Step 3.5 was about voice and style. This step is different — it's about content continuity, specifically what NOT to repeat from the previous post.

**CRITICAL — Check Previous Weeknotes:** Before composing, if running from a blog directory (i.e., `content/posts/` exists), find the most recently modified post and read it to identify topics and content already covered. If not in a blog directory, skip this step and note that you're composing without prior-week continuity context. Weeknotes should build on previous posts, not repeat them:
- If a topic was introduced in the previous post (e.g., "Project X is having issues"), this week should provide updates or resolution, not re-explain the original issue
- Ongoing situations should reference the previous mention briefly (e.g., "As I mentioned last week...") then focus on what's new
- Do NOT repeat context, descriptions, or explanations that were already provided in the previous post
- Treat weeknotes as a serial narrative where readers have context from prior installments

**Catchup-window caveat:** When the composing window spans multiple weeks (more than ~7 days), the previous post is older than "last week" and is less load-bearing as a continuity anchor. Still skim it briefly, but it's expected that this post will re-introduce some context the reader hasn't seen recently — that's a feature of catchup posts, not a violation of the no-repetition rule. A reasonable touchpoint: "Last weeknote was [N] weeks ago; here's what's happened since…"

### Step 5: Compose

**Style guidance:** Match the user's voice from past weeknotes (see Step 3.5), and avoid repeating topics from the most recent post (see Step 4) — conversational, self-deprecating, with parenthetical asides and comfortable with tangents. Start with an opening paragraph containing an inline "TL;DR: ..." summary (not a header), followed by `<!--more-->` on its own line. Use a "Miscellanea" section near the end (just before the conclusion) as a grab-bag for brief observations and items that didn't fit under other thematic sections. **CRITICAL:** Format ALL Miscellanea items as bullet points, including bookmarks and links — do NOT create a separate "Bookmarks and Reading" section.

Analyze the fetched content and compose a conversational weeknotes post that:

1. **Summarizes Mastodon activity** — Don't just list every post. Instead:
   - Identify themes and topics from the week
   - Highlight interesting conversations or thoughts
   - Group related posts together
   - Write in a natural, conversational tone
   - Include specific details that are interesting or noteworthy
   - **Link to actual Mastodon posts** using the URLs from the source (e.g., `[posted about X](https://masto.hackers.town/@user/12345)`)
   - **CRITICAL — AVOID PLAGIARISM:** Only use the user's own words from "My Posts" sections directly in prose. Content from "Posts I Boosted" or "Posts I Favorited" should ONLY be:
     - Referenced/cited with attribution (e.g., "Someone on Mastodon pointed out that...")
     - Summarized in your own words, not quoted verbatim as if the user wrote them
     - Alternatively, include blocks of text using blockquotes where it seems interesting
     - Linked to without incorporating their text into the narrative
     - This is extremely important to avoid unintentional plagiarism
   - **IMPORTANT: Embed images inline** when they add value (e.g., `![Alt text](image-url)`)
   - **Look for posts with Media entries** in the `## Mastodon` section of `combined.md` — these contain images that should be included
   - Images are especially important for: cats, interesting screenshots, funny visuals, project photos, etc.

2. **Integrates bookmarks meaningfully** — Don't just list links. Instead:
   - **CRITICAL: ALL bookmarks MUST go in the Miscellanea section as bullet points**
   - Do NOT create a separate "Bookmarks and Reading" section
   - Group related bookmarks together within Miscellanea bullets when possible
   - Explain why things were interesting or relevant in the bullet text
   - Connect bookmarks to larger thoughts or projects
   - **Include actual bookmark URLs** with descriptive link text (e.g., `[Article title](https://example.com)`)
   - Format as bullet points with links in the Miscellanea section

3. **Creates a cohesive narrative** — The post should read like a blog post, not a data dump:
   - Write in first person
   - Use conversational language
   - Connect different activities together
   - Add context and reflection
   - Include section headings that make sense for the content

4. **Uses proper formatting**:
   - Jekyll-style YAML frontmatter with title, date, tags ("weeknotes" should always be used, along with 3-7 additional tags relevant to the content), and layout
   - **Opening paragraph** with inline "TL;DR: ..." summary (NOT a header)
   - **`<!--more-->`** comment on its own line immediately after the opening paragraph (marks excerpt boundary)
   - **Table of contents nav** on its own line after `<!--more-->` if there are multiple sections (2+ headings): `<nav role="navigation" class="table-of-contents"></nav>`
   - Markdown headings (##, ###) for structure in the main body
   - Links to interesting posts or bookmarks
   - Inline images from Mastodon posts where relevant
   - Code blocks or quotes where appropriate

**Example opening structure:**
```markdown
TL;DR: Our 15-year-old solar inverter died this week, which kicked off a lot of thinking about technology longevity and IoT device lifecycles. Also spent time tinkering with Claude Code skills and bookmarking way too many articles about AI coding tools.

<!--more-->

<nav role="navigation" class="table-of-contents"></nav>

## Technology Longevity
...
```

**Critical: Always include the actual URLs!**

When referencing content:
- **Mastodon posts**: Link to the post URL with **short link text (3-5 words)** for aesthetics (e.g., `This week I [posted](https://masto.hackers.town/@user/12345) about solar inverters...`)
- **Bookmarks**: Include the bookmark URL with descriptive text (e.g., `I found [this article about AI coding](https://example.com/article) particularly interesting...`)
- **Images**: Embed Mastodon images inline using `![Description](image-url)` when they're interesting or funny
  - **For multiple consecutive images** (3+), wrap them in `<image-gallery>` tags with newlines before/after the opening and closing tags:
    ```markdown

    <image-gallery>

    ![First image](url1)

    ![Second image](url2)

    ![Third image](url3)

    </image-gallery>

    ```

**Example composition approach:**

Instead of listing every post, write something like:

> This week I [spent a lot](https://masto.hackers.town/@user/12345) of time thinking about technology longevity. Our 15-year-old solar inverter died, which [kicked off](https://masto.hackers.town/@user/12346) a whole thread about IoT devices and how frustrating it is when tech doesn't have a 15-20 year plan.

**CRITICAL — Only use the user's own posts this way!** If you want to reference a boosted/favorited post or bookmark:

> There's been this interesting [article making the rounds](https://example.com/article) about BBS-era communication patterns — explaining how those carefully drafted essay-like responses created a distinctive writing style.

Then for bookmarks in Miscellanea, reference them naturally wrapped in the `weeknote-miscellanea` div:

```markdown
## Miscellanea

<div class="weeknote-miscellanea">

* [*Thinking About Thinking With LLMs*](https://example.com/article) - explores how new tools make it easier to code with shallower understanding
* [Another piece](https://example.com/article2) argues that the best programmers still dig deep to understand what's happening underneath

</div>
```

**IMPORTANT: Always scan the `## Mastodon` section of `combined.md` for images!**

The Mastodon section includes `Media:` entries with image URLs and descriptions. Look for these and include them in your weeknotes. Example from the source:

```
Media: [image](https://cdn.masto.host/.../image.jpg) - Description of the image
```

When you find these, embed them in the weeknotes like this:

**Single image:**
> Miss Biscuits [discovered a new perch](https://masto.hackers.town/@user/12347):
>
> ![Description of the image](https://cdn.masto.host/.../image.jpg)

**Multiple images (3+) — use image gallery:**
> I [shared some photos](https://masto.hackers.town/@user/12348) of my 3D printing projects:
>
> <image-gallery>
>
> ![3D printed dragon](https://cdn.example.com/image1.jpg)
>
> ![Flexible octopus](https://cdn.example.com/image2.jpg)
>
> ![Cat playing with prints](https://cdn.example.com/image3.jpg)
>
> </image-gallery>

#### Per-Source Treatment

- **Mastodon** — Primary narrative driver. Write in first-person prose. Only quote your own posts directly; summarize boosts/favorites with attribution ("someone on Mastodon pointed out...") or use blockquotes. Always link to posts with 3-5 word link text. Embed images inline (single) or use `<image-gallery>` (3+). All the plagiarism-guard rules from the Mastodon composition section above apply.
- **Linkding** — Default to Miscellanea bullets inside the `weeknote-miscellanea` div. Group related bookmarks together; explain *why* something was interesting in the bullet text rather than just pasting a title. **Promote to a top-level section** when a cluster of 2+ bookmarks shares a thematic arc that's load-bearing for the week — e.g., "a month of bookmarks all circling the same question about coding-with-agents" wants a real section (with quoted excerpts and connecting prose), not a flat list. The mirror of the GitHub rule: bullets when light, section when thematically central. Plagiarism guard applies to bookmark excerpts the same way it does to Mastodon boosts — quote sparingly, attribute, and link.
- **GitHub** — Thematic project-by-project treatment when there's enough signal. Group events by repo/project. Write about what you actually *did* this week ("spent the week on X, fixed Y") — don't dump raw event lists. Link to specific PRs/commits/issues where they illustrate the story. If GitHub activity was light this week, demote to one or two Miscellanea bullets.
- **Spotify** — Passive consumption signal. Default to Miscellanea bullets if anything at all. Promote to a dedicated section ONLY when listening was thematically central to the week (e.g., a specific album in heavy rotation tied to a mood or project). Keep volume proportionate — a week of background music ≠ a week's narrative.
- **YouTube** — Liked-videos signal (deliberate, more meaningful than Spotify plays, but still passive consumption). Default to Miscellanea bullets. Promote to a section only when a video or theme was notably influential. **When transcripts are available** (see Step 2.5), prefer the transcript prose over the title as your composition source — titles like "How America Experienced Classic Doctor Who" only hint at the content; the transcript reveals the actual argument. Quote sparingly (videos are someone else's words, not yours — same plagiarism guard as boosts/favorites applies), but cite specific moments or claims to make the bullet substantive.

  **Embed component (`<youtube-embed>`).** The blog has a custom element for inline YouTube players. Use it like this, on its own line as its own paragraph (blank line before and after):

  ```html
  <youtube-embed video-id="VIDEO_ID"></youtube-embed>
  ```

  `VIDEO_ID` is the 11-character YouTube identifier (the `v=` parameter from a `youtube.com/watch?v=...` URL, or the path from a `youtu.be/...` URL). Do NOT manually set a `thumbnail` attribute. The blog has a `localize-images` build task that discovers `<youtube-embed>` elements, downloads the YouTube thumbnail, saves it into the post's page bundle with a content-addressed filename, and rewrites the markup to add `thumbnail="<hash>.jpg"`. Older posts in the archive already show this rewritten form — that's the build pipeline's output, not what the author types.

  When to embed (heuristic — be selective, embeds are heavy):
  - Use an embed when a video is being discussed *substantively* (its own paragraph, multiple sentences, transcript-derived content). Place the embed immediately after the prose that introduces it.
  - Do NOT embed every video in a Miscellanea list-cluster (e.g., a "retro-tech YouTube" bullet with five links) — that clutters the page. Plain markdown link text is the right form there.
  - Do NOT embed videos that are drive-by mentions or that you cite but didn't actually engage with.
  - Rough budget: 0–3 embeds per post is healthy; more than that and the videos start dominating the reading flow.
- **Pocket Casts** — Podcast listening signal. Miscellanea bullets by default; dedicated section only when a specific episode or show drove the week's thinking.

The composer's job is to identify what *actually mattered* this week, not to give every source equal column inches. A week with no GitHub activity but heavy Mastodon discussion produces a post dominated by Mastodon. A week of deep work on one project produces a GitHub-thematic post. The combined.md file is raw signal; the post is curated narrative.

### Step 6: Review and Revise

Before finalizing, review the composed weeknotes and make light revisions:

1. **Structure check:**
   - Ensure Miscellanea section is at the end (just before the conclusion)
   - Move any straggling bookmark bullets that didn't fit into main sections into Miscellanea
   - Verify all sections flow logically

2. **Prose polish:**
   - Tighten up verbose sentences
   - Remove unnecessary repetition
   - Ensure transitions between sections make sense
   - Check that the voice remains conversational and natural

3. **Content verification:**
   - All Mastodon post links are present (3-5 word link text)
   - All bookmark URLs are included
   - Images are properly embedded (single images inline, 3+ images in `<image-gallery>`)
   - Opening has inline "TL;DR: ..." followed by `<!--more-->`
   - Table of contents nav is present if there are multiple sections

4. **Final touches:**
   - Verify 3-7 tags (including "weeknotes")
   - Check that conclusion ties things together
   - Ensure Miscellanea items are formatted as bullet points

### Step 7: Write the Final Blog Post

Create the Jekyll blog post file with:

1. **YAML frontmatter:**
```yaml
---
title: "{year} Week {week}"
date: YYYY-MM-DD
tags:
  - weeknotes
  - [contextual-tag-1]
  - [contextual-tag-2]
  - [contextual-tag-3]
layout: post
---
```

**Important — Title Format:** Two cases.

- **Weekly cadence (window ≤ 7 days):** Use `{year} Week {week}` (e.g., "2025 Week 48" or "2026 Week 21"). See "Computing the output path" below for how to determine the correct week number.
- **Catchup cadence (window > 7 days):** Use a date range or "Catching up:" prefix (e.g., "Catching up: April 24 – May 20, 2026"). The `{year} Week {week}` format implies a single ISO week and is misleading when the window covers several. Pick whichever feels least clinical — date range is most informative; "Catching up: …" is friendlier prose.

In both cases: do NOT use a "Weeknotes:" prefix — the `weeknotes` tag already categorizes the post.

**Important — Tags:** Always include "weeknotes" as the first tag, then add 2-6 additional contextually appropriate tags based on the content (3-7 tags total). Tags should reflect major themes, technologies, topics, or projects discussed in the post. Examples:
- Technical topics: `ai`, `javascript`, `golang`, `docker`, `apis`
- Project types: `side-projects`, `open-source`, `blogging`
- Activities: `learning`, `refactoring`, `debugging`
- Themes: `productivity`, `tools`, `workflows`

Analyze the composed content and choose tags that genuinely reflect what the post is about.

**Catchup-window tags:** Even for posts covering multiple weeks (window > 7 days), keep `weeknotes` as the first tag and do NOT add `monthly`, `catchup`, `multi-week`, or similar meta-tags. Catchup posts are still weeknotes — same voice, same archive, same RSS feed. The meta-tag would partition the archive arbitrarily.

2. **Composed content** — The conversational weeknotes you composed in Step 5 and revised in Step 6

**CRITICAL:** Do NOT include "Generated with Claude Code" or similar AI attribution footer in weeknotes posts. These are personal blog posts that should maintain the author's authentic voice throughout.

3. **Save** to the appropriate location and filename:

**Detecting the blog directory:**
Check if the current working directory contains `content/posts/` — if so, you're in the blog directory.

```bash
if [ -d "content/posts" ]; then
  echo "In blog directory - using blog naming convention"
fi
```

**Computing the output path:**

The path is `content/posts/{YYYY}/{YYYY-MM-DD}-w{WW}/index.md` where:
- `{YYYY}` is the calendar year of the publication date
- `{YYYY-MM-DD}` is the publication date in ISO format
- `{WW}` is the ISO week number for the publication date, zero-padded to two digits (e.g. `w03`, `w42`)

You can compute this two ways:

1. **Inline (path-independent):** Use the bash tool with a one-liner. Today's path:
   ```bash
   python3 -c "from datetime import datetime as d; t=d.now(); s=t.strftime('%Y-%m-%d'); w=t.isocalendar()[1]; print(f'content/posts/{t.year}/{s}-w{w:02d}/index.md')"
   ```
   Or for a specific date:
   ```bash
   python3 -c "from datetime import datetime as d; t=d.strptime('2026-05-20','%Y-%m-%d'); s=t.strftime('%Y-%m-%d'); w=t.isocalendar()[1]; print(f'content/posts/{t.year}/{s}-w{w:02d}/index.md')"
   ```

2. **Via the helper script:** The skill includes `scripts/calculate-week.py` (located inside this skill's directory, not in the blog directory). If you know the skill's install path, you can invoke it with `--json` to get all path components at once. Use this when you also want the human-readable title string:
   ```bash
   /path/to/weeknotes-composer/scripts/calculate-week.py --date 2026-05-20 --json
   ```
   Output includes `slug`, `directory`, `filename`, and `title` fields.

Use whichever method is more convenient. The inline form works from any directory; the script gives the title for the frontmatter as a bonus.

The path uses **today's date** (not the start date) for the publication date. Examples:
- `content/posts/2025/2025-04-18-w16/index.md` (Week 16, published April 18, 2025)
- `content/posts/2025/2025-11-13-w46/index.md` (Week 46, published November 13, 2025)

**Why use a directory structure?**
Using a directory (page bundle) instead of a flat file provides several benefits:
1. **Co-located assets**: Images and attachments can be stored alongside the post
2. **Cleaner organization**: All post-related files are grouped together
3. **Easier management**: Moving or archiving a post means moving one directory
4. **Jekyll/Hugo compatibility**: This is a standard pattern for static site generators

**If not in the blog directory**, save to a temporary location (e.g., `/tmp/weeknotes-YYYY-MM-DD.md`) and ask the user where they'd like to move it.

### Step 8: Select Cover Image Thumbnail

Review the images already embedded in the post and select one to use as the cover thumbnail:

1. **Analyze embedded images:**
   - Review all images included in the post (from Mastodon posts)
   - Consider their alt text/descriptions
   - Evaluate which image best represents the overall themes of the weeknotes

2. **Selection criteria:**
   - **Thematic relevance**: Image should represent main topics/themes, not just incidental content
   - **Visual interest**: Choose images that are visually distinct and engaging
   - **Quality**: Avoid low-quality screenshots or purely text-based images
   - **Context**: Consider the image's role in the narrative — is it central to a main section or just a side note?

3. **Priority order:**
   - Images related to primary themes/topics in the post
   - Project photos, interesting technical subjects
   - Noteworthy screenshots or visual examples
   - Cat photos (only if cats are a significant theme of the week)
   - Last resort: use the first image in the post

4. **Add to frontmatter:**
   - Update the YAML frontmatter to include the `thumbnail:` property
   - Use the full URL of the selected image

   ```yaml
   ---
   title: "2026 Week 21"
   date: YYYY-MM-DD
   thumbnail: "https://cdn.masto.host/.../selected-image.jpg"
   tags:
     - weeknotes
     - [other-tags]
   layout: post
   ---
   ```

5. **If no suitable images exist in the post:**
   - Omit the `thumbnail:` property for now
   - The blog software will use the first image as a fallback
   - Note: Future enhancement will add public domain image search

### Step 9: User Feedback and Final Refinement

1. Present the composed weeknotes to the user
2. Ask if they want any adjustments:
   - Different tone or style
   - More/less detail in certain areas
   - Additional context or reflection
   - Restructuring of content
3. Make requested edits
4. Offer to add a final reflection section if desired

## Skill Configuration

The skill's only config is an optional style reference URL:

```json
{
  "weeknotes_archive": "https://blog.example.com/tags/weeknotes/"
}
```

Config path: `~/.claude/config/weeknotes-composer/config.json`

This file has one field and may be `null`. It does NOT contain API tokens, per-source credentials, or any other settings. Those live in `me-to-markdown`'s shared env file at `$XDG_CONFIG_HOME/me-to-markdown/env` (default: `~/.config/me-to-markdown/env`).

If the config file is absent, the skill prompts the user once and creates it — either with the provided URL or `"weeknotes_archive": null` if the user declines.

## Troubleshooting

- **`me-to-markdown: command not found`** — Install per the orchestrator's README: https://github.com/lmorchard/me-to-markdown. Then run `me-to-markdown install` to populate the per-source binaries and `me-to-markdown auth` to authorize each source.

- **One or more sources missing from `combined.md`** — Run `me-to-markdown list` to see which binaries resolve. Any showing `missing` need to be installed: `me-to-markdown install` (all tools) or `me-to-markdown install <slug>` (one at a time).

- **A source's section in `combined.md` contains an error block** — The most common cause is expired auth. Fix: `me-to-markdown auth` walks each tool interactively; skip ones that are already working. Re-run `me-to-markdown export` once auth is refreshed.

- **Empty content despite the date range covering activity** — Verify the env file is loaded correctly. Quick single-source smoke test: `me-to-markdown export --since 24h --include mastodon -o /tmp/test.md`. If that returns content, the issue is per-tool auth for the failing sources.

## Resources

- `scripts/calculate-week.py` — ISO week number + output filename helper. Run with `--json` to get machine-readable `directory` and `filename` fields.
- `~/.claude/config/weeknotes-composer/config.json` — Optional skill config. Contains only the `weeknotes_archive` style reference URL (or `null`).
- `~/.claude/cache/weeknotes-composer/data/latest/combined.md` — Most recent fetched signal from `me-to-markdown export`. Ephemeral; safe to delete.
- `~/.claude/cache/weeknotes-composer/data/latest/youtube-transcripts.md` — Optional companion file from `youtube-to-markdown transcripts render`. Contains prose bodies for liked videos with cached transcripts; present only when the user has run `youtube-to-markdown transcripts fetch` for the window. Ephemeral; safe to delete.
