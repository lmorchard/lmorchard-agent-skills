# Weeknotes Blog Post Composer

A Claude Code skill for composing conversational weeknotes blog posts from multiple data sources.

## Overview

This skill automatically fetches content from Mastodon and Linkding, then composes it into a well-formatted Jekyll-style blog post with proper voice, tone, and narrative structure. No more copy-paste dumps—get readable, conversational weeknotes that sound like you.

## Features

- **Multi-source data fetching**: Mastodon posts and Linkding bookmarks
- **Conversational composition**: Claude reads your content and composes readable prose
- **Style matching**: Optionally reference your past weeknotes to maintain consistent voice
- **Smart tagging**: Automatically generates 3-7 contextually appropriate tags
- **Jekyll-ready output**: YAML frontmatter with proper filename conventions
- **Cross-platform**: Supports macOS (ARM64/Intel) and Linux (AMD64)

## Quick Start

### Installation

Install this skill as a Claude Code marketplace:

```bash
# Add to your Claude config
# ~/.claude/config/settings.json
{
  "plugins": [
    "/path/to/lmorchard-agent-skills-private"
  ]
}
```

Restart Claude Code to load the skill.

### First-Time Setup

The first time you use the skill, Claude will guide you through configuration:

```
User: Draft weeknotes for this week
Claude: I need to configure the skill first. I'll need:
  - Your Mastodon server URL and access token
  - Your Linkding instance URL and API token
  - (Optional) URL to your past weeknotes for style reference
```

**Getting API credentials:**

- **Mastodon**: Settings → Development → New Application (read permissions)
- **Linkding**: Settings → Integrations → Create Token

### Basic Usage

```
# Default: last 7 days (rolling 7-day window)
Draft weeknotes for this week

# Specific date range
Create weeknotes from November 4-10
```

Claude will:
1. Fetch your Mastodon posts and Linkding bookmarks
2. Analyze the content for themes and topics
3. Compose conversational prose that sounds like you
4. Generate contextually appropriate tags
5. Save to your blog directory (if detected) or offer to save elsewhere

## Configuration

After initial setup, your config lives in `config/config.json`:

```json
{
  "mastodon": {
    "server": "https://your-instance.social",
    "token": "your-access-token"
  },
  "linkding": {
    "url": "https://your-linkding.com",
    "token": "your-api-token"
  },
  "weeknotes_archive": "https://yourblog.com/tag/weeknotes/"
}
```

To reconfigure:

```bash
./scripts/setup.sh
```

## Project Structure

```
weeknotes-blog-post-composer/
├── SKILL.md              # Detailed documentation for Claude
├── README.md             # This file
├── bin/                  # Platform-specific Go CLI binaries
│   ├── darwin-arm64/
│   ├── darwin-amd64/
│   └── linux-amd64/
├── scripts/
│   ├── setup.sh          # First-time configuration
│   ├── fetch-sources.sh  # Fetch data from sources
│   ├── prepare-sources.py # Verify fetched data
│   └── download-binaries.sh # Update CLI binaries
├── config/
│   └── config.json       # API credentials (gitignored)
└── data/                 # Fetched markdown files (gitignored)
```

## Data Sources

Currently supported:
- **Mastodon**: Posts from specified date range
- **Linkding**: Bookmarks from specified date range

The architecture supports adding additional data sources in the future.

## Output Format

Generated blog posts include:

- **Jekyll YAML frontmatter** with title, date, tags, and layout
- **Conversational prose** composed from your content
- **Short contextual links** (3-5 words) for readability
- **Inline images** from Mastodon posts
- **3-7 tags** including "weeknotes" plus contextual tags
- **Proper structure** with TL;DR, main sections, Miscellanea, and conclusion

## Filename Convention

When run from your blog directory, posts are saved to:

```
content/posts/{YYYY}/{YYYY-MM-DD-wWW}.md
```

Where:
- `{YYYY}` = 4-digit year of start date
- `{YYYY-MM-DD}` = Start date of the 7-day period
- `{wWW}` = ISO week number (e.g., w16, w45)

Example: `content/posts/2025/2025-11-07-w45.md`

## Manual Commands

You can run individual components if needed:

```bash
# Update binaries to latest releases
./scripts/download-binaries.sh

# Fetch data for specific date range
./scripts/fetch-sources.sh --start 2025-11-01 --end 2025-11-07

# Verify fetched data
./scripts/prepare-sources.py
```

## Security

- API credentials stored in `config/config.json` with 600 permissions
- Config file is gitignored
- Temporary config files cleaned up after use
- Fetched data is gitignored

## Documentation

For detailed documentation on how the skill works and how Claude uses it, see [SKILL.md](SKILL.md).

## Requirements

- **Claude Code**: Latest version
- **Bash**: For shell scripts
- **Python 3**: For Python scripts
- **curl**: For API testing (during setup)
- **jq** (optional): For better config parsing

Binaries for Mastodon and Linkding fetching are included for all supported platforms.

## License

This is a personal skill for use with Claude Code. Binaries for `mastodon-to-markdown` and `linkding-to-markdown` are subject to their respective licenses.
