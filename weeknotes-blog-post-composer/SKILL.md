---
name: weeknotes-blog-post-composer
description: Compose weeknotes blog posts in Jekyll-style Markdown from multiple data sources including Mastodon and Linkding. Use this skill when the user requests to create, draft, or generate weeknotes content for a blog post.
---

# Weeknotes Blog Post Composer

## Overview

This skill enables composing weeknotes blog posts by automatically fetching content from multiple sources (Mastodon, Linkding, GitHub, Spotify, YouTube, and Pocket Casts, via the `me-to-markdown` orchestrator) and combining them into a well-formatted Jekyll-style Markdown document with YAML frontmatter. The skill handles data collection, formatting, and composition into a ready-to-publish blog post. Optionally, the skill can reference past weeknotes to match the user's personal writing style and voice.

## Quick Start

Source data is fetched through the [`me-to-markdown`](https://github.com/lmorchard/me-to-markdown)
orchestrator, which owns all per-source **credentials** (Mastodon, Linkding,
GitHub, Spotify, YouTube, Pocket Casts) in its own shared env file. This skill's
`config.json` is now used only for the optional **weeknotes archive URL** (style
reference).

**Prerequisites (one-time):**
1. Install the orchestrator so `me-to-markdown` is on `$PATH` (or set
   `ME_TO_MARKDOWN_BIN`). See https://github.com/lmorchard/me-to-markdown
2. Install the per-tool binaries: `me-to-markdown install`
3. Authenticate every source: `me-to-markdown auth`
4. Verify: `me-to-markdown list` (should show each tool as `found`)

**Optional skill config (style reference):**

```bash
if [ ! -f "$HOME/.claude/config/weeknotes-blog-post-composer/config.json" ]; then
  echo "No skill config yet — run setup.sh to set the weeknotes archive URL."
  ./scripts/setup.sh
fi
```

Run `scripts/setup.sh` to set (or update) the weeknotes archive URL used for
matching the user's writing voice. That URL is the only thing this skill
configures; all source credentials live with the orchestrator.

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

### Step 2: Fetch Source Data

Run the fetch script to collect data from all configured sources. Under the
hood this drives the [`me-to-markdown`](https://github.com/lmorchard/me-to-markdown)
orchestrator, which fans out to every configured source in parallel:

```bash
# For current week (automatic date calculation)
./scripts/fetch-sources.sh

# For specific date range
./scripts/fetch-sources.sh --start YYYY-MM-DD --end YYYY-MM-DD

# For custom output directory
./scripts/fetch-sources.sh --start YYYY-MM-DD --end YYYY-MM-DD --output-dir PATH
```

This fetches, for the specified date range:
- **Mastodon** — posts, boosts, favorites
- **Linkding** — bookmarks
- **GitHub** — activity (pushes, PRs, reviews, branches)
- **Spotify** — recently played tracks
- **YouTube** — liked videos
- **Pocket Casts** — listening history and starred episodes

Output is saved as a single combined file to
`~/.claude/cache/weeknotes-blog-post-composer/data/latest/` (or specified directory):
- `combined.md` — all sources, each under a `## {Source}` section header

The orchestrator binary must be installed (`me-to-markdown` on `$PATH`, or set
`ME_TO_MARKDOWN_BIN`) and authenticated once (`me-to-markdown install` then
`me-to-markdown auth`). Sources with no activity or missing auth are omitted
from the output rather than erroring.

### Step 3: Read and Analyze Source Data

Verify the fetched data is ready and understand what content is available:

```bash
./scripts/prepare-sources.py
```

This shows which source files are available and their sizes.

Then read the combined markdown file to understand the content:

```bash
cat ~/.claude/cache/weeknotes-blog-post-composer/data/latest/combined.md
```

The file is organized into `## Mastodon`, `## Linkding`, `## GitHub`,
`## Spotify`, `## YouTube`, and `## Pocket Casts` sections. Not every section
will be a headline — listening/podcast history is often best mined for *themes*
(what was on heavy rotation, recurring shows) rather than enumerated track by
track. GitHub activity is a good source for "what I actually built this week."

### Step 3.5: Review Past Weeknotes for Style Reference (Optional)

**Check for configured style reference:**

```bash
# Check if weeknotes_archive URL is configured
cat ~/.claude/config/weeknotes-blog-post-composer/config.json
```

If the config contains a `weeknotes_archive` URL, fetch and review 1-2 of the user's past weeknotes to understand their writing style and voice. Use the WebFetch tool to analyze the archive page and individual posts.

If no `weeknotes_archive` is configured, skip this step and compose in a conversational blog post style.

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

### Step 4: Compose Conversational Weeknotes

**CRITICAL - Check Previous Weeknotes:** Before composing, read the most recent weeknotes post from the blog to identify topics and content already covered. Weeknotes should build on previous posts, not repeat them:
- If a topic was introduced in the previous post (e.g., "Project X is having issues"), this week should provide updates or resolution, not re-explain the original issue
- Ongoing situations should reference the previous mention briefly (e.g., "As I mentioned last week...") then focus on what's new
- Do NOT repeat context, descriptions, or explanations that were already provided in the previous post
- Treat weeknotes as a serial narrative where readers have context from prior installments

**Important:** Do not use template substitution. Instead, read the source markdown and compose it into readable prose.

**Style guidance:** Match the user's voice from past weeknotes (see Step 3.5) - conversational, self-deprecating, with parenthetical asides and comfortable with tangents. Start with an opening paragraph containing an inline "TL;DR: ..." summary (not a header), followed by `<!--more-->` on its own line. Use a "Miscellanea" section near the end (just before the conclusion) as a grab-bag for brief observations and items that didn't fit under other thematic sections. **CRITICAL:** Format ALL Miscellanea items as bullet points, including bookmarks and links - do NOT create a separate "Bookmarks and Reading" section.

Analyze the fetched content and compose a conversational weeknotes post that:

1. **Summarizes Mastodon activity** - Don't just list every post. Instead:
   - Identify themes and topics from the week
   - Highlight interesting conversations or thoughts
   - Group related posts together
   - Write in a natural, conversational tone
   - Include specific details that are interesting or noteworthy
   - **Link to actual Mastodon posts** using the URLs from the source (e.g., `[posted about X](https://masto.hackers.town/@user/12345)`)
   - **CRITICAL - AVOID PLAGIARISM:** Only use the user's own words from "My Posts" sections directly in prose. Content from "Posts I Boosted" or "Posts I Favorited" should ONLY be:
     - Referenced/cited with attribution (e.g., "Someone on Mastodon pointed out that...")
     - Summarized in your own words, not quoted verbatim as if the user wrote them
     - Alternatively, include blocks of text using blockquotes where it seems interesting
     - Linked to without incorporating their text into the narrative
     - This is extremely important to avoid unintentional plagiarism
   - **IMPORTANT: Embed images inline** when they add value (e.g., `![Alt text](image-url)`)
   - **Look for posts with Media entries** in the `## Mastodon` section of combined.md - these contain images that should be included
   - Images are especially important for: cats, interesting screenshots, funny visuals, project photos, etc.

2. **Integrates bookmarks meaningfully** - Don't just list links. Instead:
   - **CRITICAL: ALL bookmarks MUST go in the Miscellanea section as bullet points**
   - Do NOT create a separate "Bookmarks and Reading" section
   - Group related bookmarks together within Miscellanea bullets when possible
   - Explain why things were interesting or relevant in the bullet text
   - Connect bookmarks to larger thoughts or projects
   - **Include actual bookmark URLs** with descriptive link text (e.g., `[Article title](https://example.com)`)
   - Format as bullet points with links in the Miscellanea section

3. **Creates a cohesive narrative** - The post should read like a blog post, not a data dump:
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

**CRITICAL - Only use the user's own posts this way!** If you want to reference a boosted/favorited post or bookmark:

> There's been this interesting [article making the rounds](https://example.com/article) about BBS-era communication patterns - explaining how those carefully drafted essay-like responses created a distinctive writing style. But nope, it's just how we learned to write when bandwidth was scarce.

Then for bookmarks in Miscellanea, reference them naturally wrapped in the `weeknote-miscellanea` div:

```markdown
## Miscellanea

<div class="weeknote-miscellanea">

* [*Thinking About Thinking With LLMs*](https://example.com/article) - explores how new tools make it easier to code with shallower understanding
* [Another piece](https://example.com/article2) argues that the best programmers still dig deep to understand what's happening underneath

</div>
```

**IMPORTANT: Always scan the `## Mastodon` section of combined.md for images!**

The Mastodon entries include `Media:` lines with image URLs and descriptions. Look for these and include them in your weeknotes. Example from the source:

```
Media: [image](https://cdn.masto.host/.../image.jpg) - Description of the image
```

When you find these, embed them in the weeknotes like this:

**Single image:**
> Miss Biscuits [discovered a new perch](https://masto.hackers.town/@user/12347):
>
> ![Description of the image](https://cdn.masto.host/.../image.jpg)

**Multiple images (3+) - use image gallery:**
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

### Step 5: Review and Revise the Draft

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

### Step 6: Write the Final Blog Post

Create the Jekyll blog post file with:

1. **YAML frontmatter:**
```yaml
---
title: "[Date Range]"
date: YYYY-MM-DD
tags:
  - weeknotes
  - [contextual-tag-1]
  - [contextual-tag-2]
  - [contextual-tag-3]
layout: post
---
```

**Important - Title Format:** Use the date range format without the word "Weeknotes" (e.g., "2025 Week 48" or "November 22-26, 2025"). The "weeknotes" tag already categorizes the post, so the title should be concise.

**Important - Tags:** Always include "weeknotes" as the first tag, then add 2-6 additional contextually appropriate tags based on the content (3-7 tags total). Tags should reflect major themes, technologies, topics, or projects discussed in the post. Examples:
- Technical topics: `ai`, `javascript`, `golang`, `docker`, `apis`
- Project types: `side-projects`, `open-source`, `blogging`
- Activities: `learning`, `refactoring`, `debugging`
- Themes: `productivity`, `tools`, `workflows`

Analyze the composed content and choose tags that genuinely reflect what the post is about.

2. **Composed content** - The conversational weeknotes you composed in Step 4 and revised in Step 5

**CRITICAL:** Do NOT include "Generated with Claude Code" or similar AI attribution footer in weeknotes posts. These are personal blog posts that should maintain the author's authentic voice throughout.

3. **Save** to the appropriate location and filename:

**Detecting the blog directory:**
Check if the current working directory contains `content/posts/` - if so, you're in the blog directory.

```bash
if [ -d "content/posts" ]; then
  echo "In blog directory - using blog naming convention"
fi
```

**If running from the user's blog directory**, use this directory-based structure:
```
content/posts/{YYYY}/{YYYY-MM-DD-wWW}/index.md
```

Where:
- `{YYYY}` = 4-digit year (of today's date)
- `{YYYY-MM-DD}` = Today's date (the publication date)
- `{wWW}` = ISO week number for today (e.g., w16, w17, w42)

Examples:
- `content/posts/2025/2025-04-18-w16/index.md` (Week 16, published April 18, 2025)
- `content/posts/2025/2025-11-13-w46/index.md` (Week 46, published November 13, 2025)

**Why use a directory structure?**
Using a directory (page bundle) instead of a flat file provides several benefits:
1. **Co-located assets**: Images and attachments can be stored alongside the post
2. **Cleaner organization**: All post-related files are grouped together
3. **Easier management**: Moving or archiving a post means moving one directory
4. **Jekyll/Hugo compatibility**: This is a standard pattern for static site generators

**To calculate the week number and filename**, use the helper script:
```bash
cd /path/to/weeknotes-blog-post-composer
./scripts/calculate-week.py

# Or for a specific date:
./scripts/calculate-week.py --date 2025-11-13

# Or get JSON output:
./scripts/calculate-week.py --json
```

This script uses **today's date** (not the start date) and calculates the ISO week number, generating the correct directory path: `content/posts/{year}/{date}-w{week}/index.md`

**Important:** Ensure both the year directory and post directory exist before saving:
```bash
# Create the directory structure
mkdir -p content/posts/2026/2026-01-14-w03

# Then write the index.md file
# Use the Write tool to create the file at:
# content/posts/2026/2026-01-14-w03/index.md
```

**If not in the blog directory**, save to a temporary location (e.g., `/tmp/weeknotes-YYYY-MM-DD.md`) and ask the user where they'd like to move it

### Step 7: Select Cover Image Thumbnail

Review the images already embedded in the post and select one to use as the cover thumbnail:

1. **Analyze embedded images:**
   - Review all images included in the post (from Mastodon posts)
   - Consider their alt text/descriptions
   - Evaluate which image best represents the overall themes of the weeknotes

2. **Selection criteria:**
   - **Thematic relevance**: Image should represent main topics/themes, not just incidental content
   - **Visual interest**: Choose images that are visually distinct and engaging
   - **Quality**: Avoid low-quality screenshots or purely text-based images
   - **Context**: Consider the image's role in the narrative - is it central to a main section or just a side note?

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
   title: "Weeknotes: [Date Range]"
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

### Step 8: User Feedback and Final Refinement

1. Present the composed weeknotes to the user
2. Ask if they want any adjustments:
   - Different tone or style
   - More/less detail in certain areas
   - Additional context or reflection
   - Restructuring of content
3. Make requested edits
4. Offer to add a final reflection section if desired

## Additional Operations

### Updating Binaries

Source binaries are now managed by the `me-to-markdown` orchestrator, not by
this skill. To update the orchestrator and its per-tool binaries:

```bash
# Update the orchestrator itself (however you installed it), then refresh tools:
me-to-markdown install
```

`me-to-markdown list` shows where each tool resolves and its version. To change
which sources are authenticated, use `me-to-markdown auth`.

### Reconfiguring

This skill's only setting is the optional weeknotes archive URL (style
reference). To set or update it:

```bash
cd /path/to/weeknotes-blog-post-composer
./scripts/setup.sh
```

Source credentials are not managed here — use `me-to-markdown auth` for those.

### Customizing the Output Style

The composition process is flexible and can be customized based on user preferences:

1. **Tone and Style:**
   - More formal or casual
   - Technical vs. personal
   - Detailed vs. high-level summaries

2. **Structure:**
   - Different section organization
   - Thematic groupings vs. chronological
   - Depth of technical detail

3. **Content Selection:**
   - Which topics to emphasize
   - What to skip or summarize briefly
   - Which links/posts deserve more attention

Ask the user about their preferences for these aspects when composing weeknotes.

### Adding New Data Sources

New sources are added to the `me-to-markdown` orchestrator itself (a new
`*-to-markdown` tool registered in its tool registry), not to this skill. Once
the orchestrator emits a new `## {Source}` section in `combined.md`, update:

1. SKILL.md Step 2/3 to list the new source
2. Step 4 composition guidance to explain how to integrate the new content

## Resources

### scripts/

- `setup.sh` - Set the optional weeknotes archive URL (style reference)
- `fetch-sources.sh` - Fetch a week of activity via the me-to-markdown orchestrator
- `prepare-sources.py` - Verify fetched data and prepare for composition
- `calculate-week.py` - Calculate ISO week number and generate filename for weeknotes

### Runtime Data Directories

All runtime data is stored under `~/.claude/` to keep it separate from skill source code:

**Config** (`~/.claude/config/weeknotes-blog-post-composer/`):
- `config.json` - Created by setup.sh; holds only the optional `weeknotes_archive`
  URL for style reference. No source credentials live here — those are owned by
  the `me-to-markdown` orchestrator (see its `auth` command).

**Cache** (`~/.claude/cache/weeknotes-blog-post-composer/data/`):
- `latest/` - Most recently fetched source data
- Other directories for historical or custom fetches
- Contains `combined.md` after fetching
- This is temporary/ephemeral data that can be safely deleted

## Troubleshooting

### Orchestrator Not Found

If `fetch-sources.sh` can't find `me-to-markdown`:
- Ensure the binary is on `$PATH`, or set `ME_TO_MARKDOWN_BIN` to its location
- Verify the per-tool binaries resolve: `me-to-markdown list`
- Install/refresh tools with `me-to-markdown install`

### Empty or Missing Sources

If a source's section is empty or absent from `combined.md`:
- Verify the date range includes actual activity
- Confirm that source is authenticated: `me-to-markdown auth`
- Run the orchestrator directly with `--since`/`--until` to see stderr detail

### Composition

The post is composed directly from `combined.md` — there is no output template
to maintain. Read the file, match the user's voice (see Step 3.5), and write the
Jekyll post per Step 6.
