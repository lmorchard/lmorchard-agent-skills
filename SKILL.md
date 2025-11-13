---
name: weeknotes-blog-post-composer
description: Compose weeknotes blog posts in Jekyll-style Markdown from multiple data sources including Mastodon and Linkding. Use this skill when the user requests to create, draft, or generate weeknotes content for a blog post.
---

# Weeknotes Blog Post Composer

## Overview

This skill enables composing weeknotes blog posts by automatically fetching content from multiple sources (Mastodon posts and Linkding bookmarks) and combining them into a well-formatted Jekyll-style Markdown document with YAML frontmatter. The skill handles data collection, formatting, and composition into a ready-to-publish blog post.

## Quick Start

When a user first requests to create weeknotes, check if the skill is configured:

```bash
cd /path/to/weeknotes-blog-post-composer

# Check if config exists
if [ ! -f "./config/config.json" ]; then
  echo "First-time setup required."
  ./scripts/setup.sh
fi
```

If configuration doesn't exist:
1. Inform the user that first-time setup is needed
2. Ask for their Mastodon server URL and access token
3. Ask for their Linkding instance URL and API token
4. Run `scripts/setup.sh` with their inputs

### Getting API Credentials

**Mastodon Access Token:**
1. Log into the Mastodon instance
2. Go to Settings → Development → New Application
3. Give it a name (e.g., "Weeknotes Composer")
4. Grant "read" permissions
5. Copy the access token

**Linkding API Token:**
1. Log into the Linkding instance
2. Go to Settings → Integrations
3. Click "Create Token"
4. Copy the generated token

## Composing Weeknotes

The primary workflow for composing weeknotes follows these steps:

### Step 1: Determine Date Range

By default, use Monday-Sunday of the current week. If the user specifies a different timeframe, parse their request and extract start/end dates.

Examples of user requests:
- "Draft weeknotes for this week" → Current Monday-Sunday
- "Create weeknotes for last week" → Previous Monday-Sunday
- "Generate weeknotes from November 4-10" → 2025-11-04 to 2025-11-10

### Step 2: Fetch Source Data

Run the fetch script to collect data from all configured sources:

```bash
cd /path/to/weeknotes-blog-post-composer

# For current week (automatic date calculation)
./scripts/fetch-sources.sh

# For specific date range
./scripts/fetch-sources.sh --start YYYY-MM-DD --end YYYY-MM-DD

# For custom output directory
./scripts/fetch-sources.sh --start YYYY-MM-DD --end YYYY-MM-DD --output-dir ./data/custom
```

This fetches:
- Mastodon posts from the specified date range
- Linkding bookmarks from the specified date range

Output files are saved to `data/latest/` (or specified directory):
- `mastodon.md` - Formatted Mastodon posts
- `linkding.md` - Formatted bookmarks

### Step 3: Read and Analyze Source Data

Verify the fetched data is ready and understand what content is available:

```bash
cd /path/to/weeknotes-blog-post-composer
./scripts/prepare-sources.py
```

This shows which source files are available and their sizes.

Then read the fetched markdown files to understand the content:

```bash
# Read Mastodon posts
cat data/latest/mastodon.md

# Read Linkding bookmarks
cat data/latest/linkding.md
```

### Step 3.5: Review Past Weeknotes for Style Reference (Recommended)

Before composing, review 1-2 of the user's past weeknotes to understand their writing style and voice:

**User's weeknotes archive:** https://blog.lmorchard.com/tag/weeknotes/

Key style elements observed in past weeknotes:

1. **Voice & Tone:**
   - Conversational and self-deprecating
   - Frequent parenthetical asides and tangents
   - Playful language (e.g., "Ope", casual interjections)
   - Self-aware meta-commentary about the writing process itself

2. **Structure:**
   - Often starts with a TL;DR summary
   - 2-3 deeper dives into specific projects or topics (main body)
   - "Miscellanea" section near the end for brief observations and items that didn't fit elsewhere
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

**Important:** Do not use template substitution. Instead, read the source markdown and compose it into readable prose.

**Style guidance:** Match the user's voice from past weeknotes (see Step 3.5) - conversational, self-deprecating, with parenthetical asides and comfortable with tangents. Include a TL;DR summary. Use a "Miscellanea" section near the end (just before the conclusion) as a grab-bag for brief observations and items that didn't fit under other thematic sections.

Analyze the fetched content and compose a conversational weeknotes post that:

1. **Summarizes Mastodon activity** - Don't just list every post. Instead:
   - Identify themes and topics from the week
   - Highlight interesting conversations or thoughts
   - Group related posts together
   - Write in a natural, conversational tone
   - Include specific details that are interesting or noteworthy
   - **Link to actual Mastodon posts** using the URLs from the source (e.g., `[posted about X](https://masto.hackers.town/@user/12345)`)
   - **Embed images inline** when they add value (e.g., `![Alt text](image-url)`)

2. **Integrates bookmarks meaningfully** - Don't just list links. Instead:
   - Group bookmarks by theme or topic
   - Explain why things were interesting or relevant
   - Connect bookmarks to larger thoughts or projects
   - Mention patterns in what was saved
   - **Include actual bookmark URLs** with descriptive link text (e.g., `[Article title](https://example.com)`)
   - Can be formatted as inline links in prose or as bullet lists with links

3. **Creates a cohesive narrative** - The post should read like a blog post, not a data dump:
   - Write in first person
   - Use conversational language
   - Connect different activities together
   - Add context and reflection
   - Include section headings that make sense for the content

4. **Uses proper formatting**:
   - Jekyll-style YAML frontmatter with title, date, tags, and layout
   - Markdown headings (##, ###) for structure
   - Links to interesting posts or bookmarks
   - Inline images from Mastodon posts where relevant
   - Code blocks or quotes where appropriate

**Critical: Always include the actual URLs!**

When referencing content:
- **Mastodon posts**: Link to the post URL (e.g., `This week I [posted about solar inverters](https://masto.hackers.town/@user/12345)...`)
- **Bookmarks**: Include the bookmark URL with descriptive text (e.g., `I found [this article about AI coding](https://example.com/article) particularly interesting...`)
- **Images**: Embed Mastodon images inline using `![Description](image-url)` when they're interesting or funny

**Example composition approach:**

Instead of listing every post, write something like:

> This week I spent a lot of time [thinking about technology longevity](https://masto.hackers.town/@user/12345). Our 15-year-old solar inverter died, which kicked off a [whole thread about IoT devices](https://masto.hackers.town/@user/12346) and how frustrating it is when tech doesn't have a 15-20 year plan.

Then for bookmarks, integrate them naturally:

> I saved several interesting articles about AI and coding this week. [*Thinking About Thinking With LLMs*](https://example.com/article) talked about how new tools make it easier to code with shallower understanding. But [another piece](https://example.com/article2) made the point that the best programmers still dig deep to understand what's happening underneath.

When images add value, include them:

> In more important news, [Miss Biscuits discovered a new perch](https://masto.hackers.town/@user/12347):
>
> ![Miss Biscuits in cabinet](https://cdn.example.com/image.jpg)

### Step 5: Write the Final Blog Post

Create the Jekyll blog post file with:

1. **YAML frontmatter:**
```yaml
---
title: "Weeknotes: [Date Range]"
date: YYYY-MM-DD
tags:
  - weeknotes
layout: post
---
```

2. **Composed content** - The conversational weeknotes you composed in step 4

3. **Save** to an appropriately named file (e.g., `weeknotes-2025-11-10.md`)

### Step 6: Review and Refine

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

To update the Go CLI binaries to the latest releases:

```bash
cd /path/to/weeknotes-blog-post-composer
./scripts/download-binaries.sh
```

This downloads the latest versions of:
- `mastodon-to-markdown`
- `linkding-to-markdown`

For all supported platforms (darwin-arm64, darwin-amd64, linux-amd64).

### Reconfiguring

To update API credentials or change data source settings:

```bash
cd /path/to/weeknotes-blog-post-composer
./scripts/setup.sh
```

The setup script will detect existing configuration and ask for confirmation before reconfiguring.

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

To extend the skill with additional data sources:

1. Add the new Go CLI binary to `bin/{platform}-{arch}/`
2. Update `scripts/fetch-sources.sh` to fetch from the new source
3. Add a new section placeholder to `assets/weeknotes-template.md`
4. Update `scripts/compose-weeknotes.sh` to include the new content

## Platform Detection

All scripts automatically detect the current platform and use the appropriate binary:

- **macOS ARM64**: `bin/darwin-arm64/`
- **macOS Intel**: `bin/darwin-amd64/`
- **Linux AMD64**: `bin/linux-amd64/`

Platform detection is handled automatically via `uname` commands. No manual configuration needed.

## Resources

### scripts/

**Core Scripts:**
- `setup.sh` - First-time configuration for API credentials
- `fetch-sources.sh` - Fetch data from all configured sources
- `prepare-sources.py` - Verify fetched data and prepare for composition
- `download-binaries.sh` - Update Go CLI binaries to latest releases

**Legacy Scripts** (kept for reference):
- `compose-weeknotes.py` - Template-based composition (deprecated in favor of Claude composition)
- `compose-weeknotes.sh` - Shell version of template composition (deprecated)

### bin/

Pre-compiled Go CLI binaries organized by platform:
- `mastodon-to-markdown` - Fetch Mastodon posts as markdown
- `linkding-to-markdown` - Fetch Linkding bookmarks as markdown

Binaries are platform-specific and automatically selected at runtime.

### assets/

- `weeknotes-template.md` - Example Jekyll blog post template (legacy reference, not used in composition)

### config/

- `config.json` - User configuration with API credentials (created by setup.sh)
- This file contains sensitive tokens and is secured with 600 permissions

### data/

- `latest/` - Most recently fetched source data
- Other directories for historical or custom fetches
- Contains `mastodon.md` and `linkding.md` after fetching

## Troubleshooting

### Configuration Issues

If setup fails:
- Verify API credentials are correct
- Check that server URLs are accessible
- Ensure tokens have appropriate permissions

### Binary Not Found

If platform detection fails:
```bash
# Check current platform
uname -s  # Should show: Darwin or Linux
uname -m  # Should show: arm64, x86_64, etc.

# Verify binary exists
ls -la bin/darwin-arm64/  # Or appropriate platform directory
```

### Empty Content

If fetched data is empty:
- Verify the date range includes actual activity
- Check that API credentials have read permissions
- Run fetch scripts with `--verbose` flag for debugging

### Template Errors

If composition fails with template errors:
- Verify `assets/weeknotes-template.md` exists and is readable
- Check that all required placeholders are present
- Ensure no syntax errors in template YAML frontmatter
