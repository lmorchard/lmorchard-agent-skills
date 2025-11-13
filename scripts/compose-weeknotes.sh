#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="${SKILL_DIR}/data/latest"
TEMPLATE_FILE="${SKILL_DIR}/assets/weeknotes-template.md"

# Parse command line arguments
INPUT_DIR="${DATA_DIR}"
OUTPUT_FILE=""
TITLE=""
START_DATE=""
END_DATE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --input-dir)
            INPUT_DIR="$2"
            shift 2
            ;;
        --output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --title)
            TITLE="$2"
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
        -h|--help)
            echo "Usage: compose-weeknotes.sh [options]"
            echo ""
            echo "Options:"
            echo "  --input-dir DIR   Input directory with fetched data (default: data/latest)"
            echo "  --output FILE     Output file (default: stdout)"
            echo "  --title TITLE     Custom title for the post"
            echo "  --start DATE      Start date (YYYY-MM-DD)"
            echo "  --end DATE        End date (YYYY-MM-DD)"
            echo "  -h, --help        Show this help message"
            echo ""
            echo "Examples:"
            echo "  compose-weeknotes.sh --output weeknotes-2025-11-11.md"
            echo "  compose-weeknotes.sh --start 2025-11-04 --end 2025-11-10 --output weeknotes.md"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "╔════════════════════════════════════════╗"
echo "║   Weeknotes Composer                   ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Check if input directory exists
if [ ! -d "${INPUT_DIR}" ]; then
    echo "❌ Input directory not found: ${INPUT_DIR}"
    echo "   Please run fetch-sources.sh first"
    exit 1
fi

# Check if required files exist
if [ ! -f "${INPUT_DIR}/mastodon.md" ]; then
    echo "⚠️  Warning: mastodon.md not found in ${INPUT_DIR}"
    MASTODON_CONTENT="*No Mastodon activity found for this period.*"
else
    MASTODON_CONTENT=$(cat "${INPUT_DIR}/mastodon.md")
fi

if [ ! -f "${INPUT_DIR}/linkding.md" ]; then
    echo "⚠️  Warning: linkding.md not found in ${INPUT_DIR}"
    LINKDING_CONTENT="*No bookmarks found for this period.*"
else
    LINKDING_CONTENT=$(cat "${INPUT_DIR}/linkding.md")
fi

# Try to infer dates from data if not provided
if [ -z "$START_DATE" ] || [ -z "$END_DATE" ]; then
    # Try to extract from mastodon.md metadata if available
    if [ -f "${INPUT_DIR}/mastodon.md" ]; then
        # Look for date range in the content
        START_DATE=$(grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' "${INPUT_DIR}/mastodon.md" | head -1 || echo "")
        END_DATE=$(grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' "${INPUT_DIR}/mastodon.md" | tail -1 || echo "")
    fi

    # Fallback to current week if still empty
    if [ -z "$START_DATE" ] || [ -z "$END_DATE" ]; then
        # Get current week dates
        dow=$(date +%u)
        days_to_monday=$((dow - 1))

        if [[ "$OSTYPE" == "darwin"* ]]; then
            START_DATE=$(date -v-${days_to_monday}d +%Y-%m-%d)
            END_DATE=$(date -v+$((7-dow))d +%Y-%m-%d)
        else
            START_DATE=$(date -d "-${days_to_monday} days" +%Y-%m-%d)
            END_DATE=$(date -d "+$((7-dow)) days" +%Y-%m-%d)
        fi
    fi
fi

# Generate week range for title
if [[ "$OSTYPE" == "darwin"* ]]; then
    WEEK_RANGE="${START_DATE} to ${END_DATE}"
else
    WEEK_RANGE="${START_DATE} to ${END_DATE}"
fi

# Use custom title if provided
if [ -z "$TITLE" ]; then
    TITLE="Weeknotes for ${WEEK_RANGE}"
fi

# Post date is typically the end date of the week
POST_DATE="${END_DATE}"

echo "📅 Date range: ${START_DATE} to ${END_DATE}"
echo "📝 Title: ${TITLE}"
echo ""

# Load template
if [ ! -f "${TEMPLATE_FILE}" ]; then
    echo "❌ Template not found: ${TEMPLATE_FILE}"
    exit 1
fi

TEMPLATE_CONTENT=$(cat "${TEMPLATE_FILE}")

# Replace placeholders
OUTPUT_CONTENT="${TEMPLATE_CONTENT}"
OUTPUT_CONTENT="${OUTPUT_CONTENT//\{\{WEEK_RANGE\}\}/${WEEK_RANGE}}"
OUTPUT_CONTENT="${OUTPUT_CONTENT//\{\{POST_DATE\}\}/${POST_DATE}}"
OUTPUT_CONTENT="${OUTPUT_CONTENT//\{\{START_DATE\}\}/${START_DATE}}"
OUTPUT_CONTENT="${OUTPUT_CONTENT//\{\{END_DATE\}\}/${END_DATE}}"
OUTPUT_CONTENT="${OUTPUT_CONTENT//\{\{TITLE\}\}/${TITLE}}"

# For content sections, we need to handle multi-line replacement
# Use a temporary file approach
TMP_FILE=$(mktemp)
echo "${OUTPUT_CONTENT}" > "${TMP_FILE}"

# Replace Mastodon content placeholder
if command -v perl &> /dev/null; then
    # Use perl for multi-line replacement (more reliable)
    perl -i -0pe "s/\{\{MASTODON_CONTENT\}\}/$(echo "${MASTODON_CONTENT}" | sed 's/\\/\\\\/g' | sed 's/\//\\\//g' | sed ':a;N;$!ba;s/\n/\\n/g')/g" "${TMP_FILE}"
    perl -i -0pe "s/\{\{LINKDING_CONTENT\}\}/$(echo "${LINKDING_CONTENT}" | sed 's/\\/\\\\/g' | sed 's/\//\\\//g' | sed ':a;N;$!ba;s/\n/\\n/g')/g" "${TMP_FILE}"
else
    # Fallback to sed (may have issues with special characters)
    MASTODON_ESCAPED=$(echo "${MASTODON_CONTENT}" | sed 's/[&/\]/\\&/g' | sed ':a;N;$!ba;s/\n/\\n/g')
    LINKDING_ESCAPED=$(echo "${LINKDING_CONTENT}" | sed 's/[&/\]/\\&/g' | sed ':a;N;$!ba;s/\n/\\n/g')
    sed -i.bak "s|{{MASTODON_CONTENT}}|${MASTODON_ESCAPED}|g" "${TMP_FILE}"
    sed -i.bak "s|{{LINKDING_CONTENT}}|${LINKDING_ESCAPED}|g" "${TMP_FILE}"
    rm -f "${TMP_FILE}.bak"
fi

OUTPUT_CONTENT=$(cat "${TMP_FILE}")
rm -f "${TMP_FILE}"

# Output to file or stdout
if [ -z "$OUTPUT_FILE" ]; then
    echo "${OUTPUT_CONTENT}"
else
    echo "${OUTPUT_CONTENT}" > "${OUTPUT_FILE}"
    echo "✅ Weeknotes post saved to: ${OUTPUT_FILE}"
    echo ""
fi

echo "╔════════════════════════════════════════╗"
echo "║   Composition Complete!                ║"
echo "╚════════════════════════════════════════╝"
echo ""
