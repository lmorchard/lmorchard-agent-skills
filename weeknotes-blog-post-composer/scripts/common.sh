#!/bin/bash
# Common configuration for weeknotes-blog-post-composer scripts
# Source this file at the beginning of each script

# Base directories following ~/.claude/{config,share,cache} pattern
CLAUDE_HOME="${HOME}/.claude"
SKILL_NAME="weeknotes-blog-post-composer"

# Configuration directory (API tokens, user settings)
CONFIG_BASE="${CLAUDE_HOME}/config/${SKILL_NAME}"
CONFIG_FILE="${CONFIG_BASE}/config.json"

# Shared data directory (downloaded binaries, tools)
SHARE_BASE="${CLAUDE_HOME}/share/${SKILL_NAME}"
BIN_BASE="${SHARE_BASE}/bin"

# Cache directory (temporary data, fetched markdown)
CACHE_BASE="${CLAUDE_HOME}/cache/${SKILL_NAME}"
DATA_BASE="${CACHE_BASE}/data"

# Create directories if they don't exist
mkdir -p "${CONFIG_BASE}"
mkdir -p "${BIN_BASE}"
mkdir -p "${DATA_BASE}"

# Detect platform for binary selection
detect_platform() {
    local os=$(uname -s | tr '[:upper:]' '[:lower:]')
    local arch=$(uname -m)

    case $arch in
        x86_64) arch="amd64" ;;
        aarch64|arm64) arch="arm64" ;;
    esac

    echo "${os}-${arch}"
}

# Get the platform-specific binary directory
PLATFORM=$(detect_platform)
BIN_DIR="${BIN_BASE}/${PLATFORM}"

# Ensure platform-specific directory exists
mkdir -p "${BIN_DIR}"
