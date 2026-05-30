#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

# Default to last 7 days (from 7 days ago through today)
get_week_dates() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        START_DATE=$(date -v-7d +%Y-%m-%d)
        END_DATE=$(date +%Y-%m-%d)
    else
        START_DATE=$(date -d "7 days ago" +%Y-%m-%d)
        END_DATE=$(date +%Y-%m-%d)
    fi
}

# Locate the me-to-markdown orchestrator binary.
# Resolution order: $ME_TO_MARKDOWN_BIN -> $PATH.
find_orchestrator() {
    if [ -n "${ME_TO_MARKDOWN_BIN}" ] && [ -x "${ME_TO_MARKDOWN_BIN}" ]; then
        echo "${ME_TO_MARKDOWN_BIN}"
        return 0
    fi
    if command -v me-to-markdown &> /dev/null; then
        command -v me-to-markdown
        return 0
    fi
    return 1
}

# Parse command line arguments
START_DATE=""
END_DATE=""
OUTPUT_DIR="${DATA_BASE}/latest"

while [[ $# -gt 0 ]]; do
    case $1 in
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
            echo "Fetches a week of personal activity via the me-to-markdown orchestrator,"
            echo "which fans out to all configured sources (Mastodon, Linkding, GitHub,"
            echo "Spotify, YouTube, Pocket Casts) and writes one combined Markdown file."
            echo ""
            echo "Options:"
            echo "  --start DATE      Start date (YYYY-MM-DD), defaults to 7 days ago"
            echo "  --end DATE        End date (YYYY-MM-DD), defaults to today"
            echo "  --output-dir DIR  Output directory (default: data/latest)"
            echo "  -h, --help        Show this help message"
            echo ""
            echo "Environment:"
            echo "  ME_TO_MARKDOWN_BIN  Override path to the me-to-markdown binary"
            echo ""
            echo "Examples:"
            echo "  fetch-sources.sh                                    # Fetch this week"
            echo "  fetch-sources.sh --start 2026-05-21 --end 2026-05-29"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# If dates not provided, use current week
if [ -z "$START_DATE" ] || [ -z "$END_DATE" ]; then
    get_week_dates
fi

echo "╔════════════════════════════════════════╗"
echo "║   Weeknotes Source Fetcher            ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Fetching data from ${START_DATE} to ${END_DATE}"
echo ""

# Locate the orchestrator
ORCHESTRATOR="$(find_orchestrator)" || {
    echo "❌ Could not find the 'me-to-markdown' orchestrator binary."
    echo ""
    echo "   Install it on your \$PATH, or set ME_TO_MARKDOWN_BIN to its location."
    echo "   Source + build instructions: https://github.com/lmorchard/me-to-markdown"
    echo ""
    echo "   The orchestrator manages its own per-tool binaries and credentials"
    echo "   (run 'me-to-markdown install' and 'me-to-markdown auth' once)."
    exit 1
}
echo "Using orchestrator: ${ORCHESTRATOR}"
echo ""

# Create output directory
mkdir -p "${OUTPUT_DIR}"
COMBINED_FILE="${OUTPUT_DIR}/combined.md"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📡 Running me-to-markdown export (all sources)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# me-to-markdown auto-loads its shared env file (~/.config/me-to-markdown/env),
# so each underlying tool sees its own credentials without per-tool plumbing.
# --omit-errors keeps the combined output clean when a source has no activity
# or isn't authed; failures still surface on stderr.
"${ORCHESTRATOR}" export \
    --since "${START_DATE}" \
    --until "${END_DATE}" \
    --omit-errors \
    -o "${COMBINED_FILE}"

echo "✅ Combined sources saved to: ${COMBINED_FILE}"
echo ""

echo "╔════════════════════════════════════════╗"
echo "║   Fetch Complete!                      ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Output directory: ${OUTPUT_DIR}"
echo "File:"
echo "  - combined.md  (## Mastodon / Linkding / GitHub / Spotify / YouTube / Pocket Casts)"
echo ""
