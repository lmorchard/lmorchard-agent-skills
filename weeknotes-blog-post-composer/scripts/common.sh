#!/bin/bash
# Common configuration for weeknotes-blog-post-composer scripts
# Source this file at the beginning of each script.
#
# Source data is fetched via the me-to-markdown orchestrator, which owns all
# per-source credentials and binaries. This skill only keeps a small config
# file (for the optional weeknotes archive URL) and a cache directory for
# fetched output.

CLAUDE_HOME="${HOME}/.claude"
SKILL_NAME="weeknotes-blog-post-composer"

# Configuration directory (optional weeknotes archive URL for style reference)
CONFIG_BASE="${CLAUDE_HOME}/config/${SKILL_NAME}"
CONFIG_FILE="${CONFIG_BASE}/config.json"

# Cache directory (temporary data, fetched markdown)
CACHE_BASE="${CLAUDE_HOME}/cache/${SKILL_NAME}"
DATA_BASE="${CACHE_BASE}/data"

# Create directories if they don't exist
mkdir -p "${CONFIG_BASE}"
mkdir -p "${DATA_BASE}"
