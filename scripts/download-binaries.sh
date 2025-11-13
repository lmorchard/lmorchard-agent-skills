#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
BIN_DIR="${SKILL_DIR}/bin"

echo "╔════════════════════════════════════════╗"
echo "║   Weeknotes Binary Downloader         ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Create bin directory structure
mkdir -p "${BIN_DIR}/darwin-arm64"
mkdir -p "${BIN_DIR}/darwin-amd64"
mkdir -p "${BIN_DIR}/linux-amd64"

# Function to download and extract a GitHub release
download_tool() {
    local repo=$1
    local tool_name=$2
    local platform=$3
    local arch=$4

    echo "📦 Downloading ${tool_name} for ${platform}-${arch}..."

    # Construct the asset name based on the naming convention
    local archive_name="${tool_name}-${platform}-${arch}.tar.gz"
    local asset_url="https://github.com/${repo}/releases/download/latest/${archive_name}"
    local temp_archive="/tmp/${archive_name}"
    local target_dir="${BIN_DIR}/${platform}-${arch}"
    local target_binary="${target_dir}/${tool_name}"

    # Download the archive
    echo "   Downloading from ${asset_url}..."
    if curl -L -f -o "${temp_archive}" "${asset_url}"; then
        echo "   ✅ Downloaded archive"

        # Extract the binary from the archive
        echo "   Extracting binary..."
        tar -xzf "${temp_archive}" -C "${target_dir}" "${tool_name}" 2>/dev/null || {
            # If extraction with specific file fails, extract all and find the binary
            tar -xzf "${temp_archive}" -C /tmp/
            find /tmp -name "${tool_name}" -type f -exec mv {} "${target_binary}" \;
        }

        # Make binary executable
        chmod +x "${target_binary}"

        # Cleanup
        rm -f "${temp_archive}"

        # Verify the binary exists
        if [ -f "${target_binary}" ]; then
            echo "   ✅ Installed to ${target_binary}"
        else
            echo "   ❌ Failed to extract binary"
            return 1
        fi
    else
        echo "   ❌ Failed to download from ${asset_url}"
        return 1
    fi

    echo ""
}

# Download mastodon-to-markdown
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Mastodon to Markdown"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
download_tool "lmorchard/mastodon-to-markdown" "mastodon-to-markdown" "darwin" "arm64"
download_tool "lmorchard/mastodon-to-markdown" "mastodon-to-markdown" "darwin" "amd64"
download_tool "lmorchard/mastodon-to-markdown" "mastodon-to-markdown" "linux" "amd64"

# Download linkding-to-markdown
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Linkding to Markdown"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
download_tool "lmorchard/linkding-to-markdown" "linkding-to-markdown" "darwin" "arm64"
download_tool "lmorchard/linkding-to-markdown" "linkding-to-markdown" "darwin" "amd64"
download_tool "lmorchard/linkding-to-markdown" "linkding-to-markdown" "linux" "amd64"

echo "╔════════════════════════════════════════╗"
echo "║   Download Complete!                   ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Binary locations:"
tree "${BIN_DIR}" || ls -R "${BIN_DIR}"
