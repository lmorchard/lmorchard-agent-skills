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

### Step 3: Compose the Blog Post

Run the composition script to generate the final weeknotes post:

```bash
cd /path/to/weeknotes-blog-post-composer

# Generate from latest fetched data
./scripts/compose-weeknotes.py --output weeknotes-YYYY-MM-DD.md

# Generate from specific input directory
./scripts/compose-weeknotes.py --input-dir ./data/custom --output weeknotes.md

# With custom title and explicit dates
./scripts/compose-weeknotes.py \
  --start 2025-11-04 \
  --end 2025-11-10 \
  --title "Weekly Wrap-Up: November 4-10" \
  --output weeknotes.md
```

Note: A shell script version (`compose-weeknotes.sh`) is also available as an alternative.

The composed post includes:
- Jekyll-style YAML frontmatter (title, date, tags, layout)
- Sections for each data source
- Placeholder section for manual reflections
- Proper formatting and structure

### Step 4: Present to User

After composition:
1. Read the generated file to review content
2. Present the weeknotes to the user
3. Offer to make edits or refinements based on their feedback
4. Ask if they want to add custom reflections or commentary

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

### Customizing the Template

The weeknotes template is located at `assets/weeknotes-template.md`. To customize the output format:

1. Read the current template
2. Ask the user what changes they'd like
3. Edit the template to match their preferences
4. Rerun the composition step

Template variables:
- `{{WEEK_RANGE}}` - Date range string (e.g., "2025-11-04 to 2025-11-10")
- `{{POST_DATE}}` - Publication date (typically end date)
- `{{START_DATE}}` - Start date (YYYY-MM-DD)
- `{{END_DATE}}` - End date (YYYY-MM-DD)
- `{{TITLE}}` - Post title
- `{{MASTODON_CONTENT}}` - Fetched Mastodon posts (multi-line)
- `{{LINKDING_CONTENT}}` - Fetched bookmarks (multi-line)

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
- `compose-weeknotes.py` - Compose the final Jekyll blog post (Python)
- `compose-weeknotes.sh` - Compose the final Jekyll blog post (Shell alternative)
- `download-binaries.sh` - Update Go CLI binaries to latest releases

### bin/

Pre-compiled Go CLI binaries organized by platform:
- `mastodon-to-markdown` - Fetch Mastodon posts as markdown
- `linkding-to-markdown` - Fetch Linkding bookmarks as markdown

Binaries are platform-specific and automatically selected at runtime.

### assets/

- `weeknotes-template.md` - Jekyll blog post template with YAML frontmatter

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
