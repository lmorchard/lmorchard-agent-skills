# Daily Blog Post Composer

A Claude Code skill for composing and iteratively updating daily blog posts from multiple data sources (Mastodon and Linkding). 

## Overview

This skill enables an **iterative daily journaling workflow** where you can:

- Fetch content from a rolling 24-hour window
- Create and update daily blog posts throughout the day
- Organize content into "miscellanea" (bullet points) and focused posts (prose)
- Automatically extract themes from miscellanea into focused posts
- Use future-dating as a draft mechanism
- Respect manual edits while intelligently merging new content

## Multi-Post Single-File Format

Unlike traditional blog posts, this skill uses a special format where **multiple posts for one day live in a single file** (`YYYY-MM-DD.md`):

```markdown
8<--- { "title": "Focused Post Title", "slug": "post-slug", "tags": ["tag1"], "time": "14:00:00-07:00" }

This is a focused post about a specific topic...

8<--- { "title": "Miscellanea for 2025-12-15", "time": "23:59:00-07:00", "type": "miscellanea", "slug": "miscellanea", "tags": ["miscellanea"] }

- Hello world!
- First observation with [a link](https://example.com)
- Another bullet point
```

### Key Concepts

- **Future-dating as drafts**: Posts with times in the future won't be fully published until that time arrives
- **Miscellanea at 23:59**: Always the last thing published each day
- **Focused posts**: Get earlier times (derived from actual Mastodon/bookmark timestamps)
- **Iterative updates**: Run the composer multiple times throughout the day to add new content

## Quick Start

### First-Time Setup

```bash
cd daily-blog-post-composer

# Run setup (configure Mastodon and Linkding APIs)
./scripts/setup.sh
```

You'll be prompted for:
- Mastodon server URL and access token
- Linkding URL and API token
- (Optional) Blog archive URL for style reference

### Daily Usage

**Morning**: Start the day's post
```bash
# Fetch rolling 24-hour window
./scripts/fetch-sources.sh

# Parse and review source data
cat data/latest/mastodon.md
cat data/latest/linkding.md

# Use Claude Code skill to compose initial post
# (creates YYYY-MM-DD.md with miscellanea)
```

**Throughout the day**: Update with new content
```bash
# Fetch latest content (rolling 24-hour window)
./scripts/fetch-sources.sh

# Use Claude Code skill to update existing post
# - Adds new bullets to miscellanea
# - Extracts themes into focused posts
# - Expands existing focused posts
```

**End of day**: Final polish
```bash
# Final fetch and update
./scripts/fetch-sources.sh

# Use Claude Code skill for final review
# - Polish prose
# - Finalize miscellanea
# - Verify all content is included
```

## Scripts

### `scripts/fetch-sources.sh`

Fetch content from Mastodon and Linkding.

```bash
# Rolling 24-hour window (default)
./scripts/fetch-sources.sh

# Specific full day (00:00 to 23:59)
./scripts/fetch-sources.sh --date 2025-12-15

# Custom range
./scripts/fetch-sources.sh --start 2025-12-14 --end 2025-12-15
```

### `scripts/parse-daily-post.py`

Parse existing daily post file to extract structured information.

```bash
# Parse file and show summary
./scripts/parse-daily-post.py /path/to/blog/content/posts/2025/2025-12-15.md

# Output as JSON
./scripts/parse-daily-post.py /path/to/blog/content/posts/2025/2025-12-15.md --json
```

Returns:
- Existing posts and their metadata
- Covered URLs and Mastodon post IDs
- Identified themes

### `scripts/extract-timestamps.py`

Extract timestamps from source files for focused post timing.

```bash
# Show all timestamps
./scripts/extract-timestamps.py

# Find earliest timestamp for specific URLs
./scripts/extract-timestamps.py --urls https://example.com/article https://masto.server/@user/12345

# Output as JSON
./scripts/extract-timestamps.py --json
```

### `scripts/prepare-sources.py`

Verify fetched data is ready for composition.

```bash
./scripts/prepare-sources.py
```

### `scripts/setup.sh`

Configure API credentials (run once, or when reconfiguring).

```bash
./scripts/setup.sh
```

### `scripts/download-binaries.sh`

Update Go CLI binaries to latest releases.

```bash
./scripts/download-binaries.sh
```

## Workflow Details

### Iterative Composition

The skill is designed for **multiple runs throughout the day**:

1. **Parse existing file** (if it exists) to understand what's covered
2. **Fetch rolling 24-hour window** of new content
3. **Intelligently place new content**:
   - Add to existing focused posts if relevant
   - Extract themes from miscellanea (3-5 max focused posts/day)
   - Add to miscellanea as fallback
4. **Respect manual edits** - don't overwrite user changes
5. **Write updated file** preserving structure

### Theme Extraction

The skill automatically extracts themes from miscellanea:

- **3+ clearly related bullets** → extract automatically
- **2 strongly related bullets** → extract if cohesive
- **Maximum 3-5 focused posts per day** - don't over-extract
- Be selective - err on side of keeping items in miscellanea

### Post Timing

- **Miscellanea**: Always `23:59:00-07:00` (last to publish)
- **Focused posts**: Derived from earliest related Mastodon post or bookmark timestamp
  - Optionally rounded to nearest 15 minutes
  - Falls back to standard intervals (09:00, 12:00, 15:00, 18:00)

### Style Reference

The skill can learn your writing style by reviewing recent daily posts:

```bash
# Check recent posts in blog directory
ls -lt /path/to/blog/content/posts/2025/*.md | head -5
```

When composing, it will:
- Match your voice and tone
- Follow your miscellanea bullet formatting
- Mirror your focused post depth and structure

## File Structure

```
daily-blog-post-composer/
├── SKILL.md              # Claude Code skill instructions
├── README.md             # This file
├── bin/                  # Platform-specific binaries
│   ├── darwin-arm64/
│   ├── darwin-amd64/
│   └── linux-amd64/
├── config/
│   └── config.json       # API credentials (created by setup.sh)
├── data/
│   └── latest/          # Most recent fetch
│       ├── mastodon.md
│       └── linkding.md
└── scripts/
    ├── fetch-sources.sh        # Fetch content from APIs
    ├── parse-daily-post.py     # Parse existing daily posts
    ├── extract-timestamps.py   # Extract timestamps from sources
    ├── prepare-sources.py      # Verify fetched data
    ├── setup.sh               # Configure APIs
    └── download-binaries.sh    # Update binaries
```

## Platform Support

Automatically detects and uses appropriate binaries for:
- macOS ARM64 (Apple Silicon)
- macOS AMD64 (Intel)
- Linux AMD64

## Troubleshooting

### Binaries Not Found

If you see "Binaries not found" error:

```bash
./scripts/download-binaries.sh
```

### Configuration Issues

If setup fails or API calls fail:

```bash
# Reconfigure
./scripts/setup.sh

# Verify config (don't share this output - contains secrets!)
cat config/config.json
```

### Empty Content

If fetched data is empty:
- Verify the date range includes actual activity
- Check API credentials have read permissions
- Ensure API tokens are not expired

## Related Skills

- **weeknotes-blog-post-composer**: Compose weekly roundup posts (7-day window, single cohesive narrative)
