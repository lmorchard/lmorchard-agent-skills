#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="${SKILL_DIR}/config/config.json"
DATA_DIR="${SKILL_DIR}/data"

# Default to rolling 24-hour window (24 hours ago through now)
# Note: The APIs treat end date as exclusive, so we use tomorrow for end
get_rolling_24h() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS date command
        START_DATE=$(date -v-1d +%Y-%m-%d)
        END_DATE=$(date -v+1d +%Y-%m-%d)
    else
        # Linux date command
        START_DATE=$(date -d "1 day ago" +%Y-%m-%d)
        END_DATE=$(date -d "tomorrow" +%Y-%m-%d)
    fi
}

# Get full day (00:00 to 23:59 for a specific date)
get_full_day() {
    local target_date=$1
    START_DATE="$target_date"

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS date command
        END_DATE=$(date -j -f "%Y-%m-%d" -v+1d "$target_date" +%Y-%m-%d)
    else
        # Linux date command
        END_DATE=$(date -d "$target_date + 1 day" +%Y-%m-%d)
    fi
}

# Parse command line arguments
START_DATE=""
END_DATE=""
TARGET_DATE=""
OUTPUT_DIR="${DATA_DIR}/latest"

while [[ $# -gt 0 ]]; do
    case $1 in
        --date)
            TARGET_DATE="$2"
            shift 2
            ;;
        --start)
            START_DATE="$2"
            shift 2
            ;;
        --end)
            END_DATE="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: fetch-sources.sh [options]"
            echo ""
            echo "Options:"
            echo "  --date DATE       Fetch full day (YYYY-MM-DD), fetches 00:00 to 23:59 for that date"
            echo "  --start DATE      Start date (YYYY-MM-DD), for custom range"
            echo "  --end DATE        End date (YYYY-MM-DD), for custom range"
            echo "  --output-dir DIR  Output directory (default: data/latest)"
            echo "  -h, --help        Show this help message"
            echo ""
            echo "If no options provided, fetches rolling 24-hour window (yesterday to now)"
            echo ""
            echo "Examples:"
            echo "  fetch-sources.sh                           # Rolling 24-hour window"
            echo "  fetch-sources.sh --date 2025-12-15         # Full day: Dec 15"
            echo "  fetch-sources.sh --start 2025-12-14 --end 2025-12-15"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Determine date range
if [ -n "$TARGET_DATE" ]; then
    # Full day specified
    get_full_day "$TARGET_DATE"
elif [ -z "$START_DATE" ] || [ -z "$END_DATE" ]; then
    # No dates specified, use rolling 24-hour window
    get_rolling_24h
fi
# else: custom start/end dates were provided, use those

echo "╔════════════════════════════════════════╗"
echo "║   Daily Post Source Fetcher           ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Fetching data from ${START_DATE} to ${END_DATE}"
echo ""

# Check if configured
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "❌ Not configured yet. Running setup..."
    echo ""
    "${SCRIPT_DIR}/setup.sh"
    echo ""
fi

# Detect platform
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case $ARCH in
    x86_64) ARCH="amd64" ;;
    aarch64|arm64) ARCH="arm64" ;;
esac

BIN_DIR="${SKILL_DIR}/bin/${OS}-${ARCH}"

# Check if binaries exist
if [ ! -f "${BIN_DIR}/mastodon-to-markdown" ] || [ ! -f "${BIN_DIR}/linkding-to-markdown" ]; then
    echo "❌ Binaries not found for platform: ${OS}-${ARCH}"
    echo "   Please run scripts/download-binaries.sh first"
    exit 1
fi

# Load config using jq (if not available, use basic parsing)
if command -v jq &> /dev/null; then
    MASTODON_SERVER=$(jq -r .mastodon.server "${CONFIG_FILE}")
    MASTODON_TOKEN=$(jq -r .mastodon.token "${CONFIG_FILE}")
    LINKDING_URL=$(jq -r .linkding.url "${CONFIG_FILE}")
    LINKDING_TOKEN=$(jq -r .linkding.token "${CONFIG_FILE}")
else
    echo "⚠️  Warning: jq not found. Using basic config parsing."
    echo "   Install jq for better config handling: brew install jq"
    # Basic parsing fallback (not recommended for production)
    MASTODON_SERVER=$(grep -o '"server"[[:space:]]*:[[:space:]]*"[^"]*"' "${CONFIG_FILE}" | cut -d'"' -f4 | head -1)
    MASTODON_TOKEN=$(grep -o '"token"[[:space:]]*:[[:space:]]*"[^"]*"' "${CONFIG_FILE}" | cut -d'"' -f4 | head -1)
    LINKDING_URL=$(grep -o '"url"[[:space:]]*:[[:space:]]*"[^"]*"' "${CONFIG_FILE}" | cut -d'"' -f4 | tail -1)
    LINKDING_TOKEN=$(grep -o '"token"[[:space:]]*:[[:space:]]*"[^"]*"' "${CONFIG_FILE}" | cut -d'"' -f4 | tail -1)
fi

# Create output directory
mkdir -p "${OUTPUT_DIR}"

# Create config files for the tools
MASTODON_CONFIG="${OUTPUT_DIR}/mastodon-config.yaml"
LINKDING_CONFIG="${OUTPUT_DIR}/linkding-config.yaml"

cat > "${MASTODON_CONFIG}" <<EOF
mastodon:
  server: "${MASTODON_SERVER}"
  access_token: "${MASTODON_TOKEN}"
EOF

cat > "${LINKDING_CONFIG}" <<EOF
linkding:
  url: "${LINKDING_URL}"
  token: "${LINKDING_TOKEN}"
EOF

# Fetch from Mastodon
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📱 Fetching Mastodon posts..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

"${BIN_DIR}/mastodon-to-markdown" fetch \
    --config "${MASTODON_CONFIG}" \
    --start "${START_DATE}" \
    --end "${END_DATE}" \
    --output "${OUTPUT_DIR}/mastodon.md" \
    --verbose

echo "✅ Mastodon posts saved to: ${OUTPUT_DIR}/mastodon.md"
echo ""

# Fetch from Linkding
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔖 Fetching Linkding bookmarks..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

"${BIN_DIR}/linkding-to-markdown" fetch \
    --config "${LINKDING_CONFIG}" \
    --since "${START_DATE}" \
    --until "${END_DATE}" \
    --output "${OUTPUT_DIR}/linkding.md" \
    --verbose

echo "✅ Linkding bookmarks saved to: ${OUTPUT_DIR}/linkding.md"
echo ""

# Cleanup config files (they contain secrets)
rm -f "${MASTODON_CONFIG}" "${LINKDING_CONFIG}"

echo "╔════════════════════════════════════════╗"
echo "║   Fetch Complete!                      ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Output directory: ${OUTPUT_DIR}"
echo "Files:"
echo "  - mastodon.md"
echo "  - linkding.md"
echo ""
