#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

echo "╔════════════════════════════════════════╗"
echo "║   Weeknotes Composer Setup            ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Source data (Mastodon, Linkding, GitHub, Spotify, YouTube, Pocket Casts)"
echo "is fetched through the me-to-markdown orchestrator, which owns all of its"
echo "own credentials. Configure those once with:"
echo ""
echo "    me-to-markdown install   # fetch the per-tool binaries"
echo "    me-to-markdown auth      # authenticate every source"
echo "    me-to-markdown list      # verify each tool resolves"
echo ""
echo "This setup only records the optional weeknotes archive URL used to match"
echo "your writing voice when composing."
echo ""

# Show existing value if present
if [ -f "${CONFIG_FILE}" ]; then
    EXISTING=$(grep -o '"weeknotes_archive"[[:space:]]*:[[:space:]]*"[^"]*"' "${CONFIG_FILE}" 2>/dev/null | cut -d'"' -f4)
    if [ -n "$EXISTING" ]; then
        echo "Current weeknotes archive URL: ${EXISTING}"
        echo ""
    fi
fi

# ============================================================================
# Style Reference Configuration (Optional)
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎨 Style Reference (Optional)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Enter a URL to your past weeknotes archive for style reference."
echo "This helps maintain consistent voice and tone in composed posts."
echo "Example: https://blog.example.com/tag/weeknotes/"
echo ""
echo "Leave blank to skip (or keep the existing value, if any)."
echo ""

read -p "Weeknotes archive URL (optional): " WEEKNOTES_ARCHIVE_URL
WEEKNOTES_ARCHIVE_URL="${WEEKNOTES_ARCHIVE_URL%/}"

# If left blank, preserve the existing value (when present)
if [ -z "$WEEKNOTES_ARCHIVE_URL" ] && [ -n "${EXISTING:-}" ]; then
    WEEKNOTES_ARCHIVE_URL="$EXISTING"
fi

# Validate URL format if provided
if [ -n "$WEEKNOTES_ARCHIVE_URL" ] && [[ ! "$WEEKNOTES_ARCHIVE_URL" =~ ^https?:// ]]; then
    echo "⚠️  Warning: URL should start with http:// or https:// — proceeding anyway."
fi

# ============================================================================
# Save Configuration
# ============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💾 Saving Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -n "$WEEKNOTES_ARCHIVE_URL" ]; then
cat > "${CONFIG_FILE}" <<EOF
{
  "weeknotes_archive": "${WEEKNOTES_ARCHIVE_URL}",
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
    echo "✅ Style reference URL configured"
else
cat > "${CONFIG_FILE}" <<EOF
{
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
    echo "⏭️  No style reference URL set"
fi

chmod 600 "${CONFIG_FILE}"

echo "✅ Configuration saved to: ${CONFIG_FILE}"
echo ""
echo "╔════════════════════════════════════════╗"
echo "║   Setup Complete!                      ║"
echo "╚════════════════════════════════════════╝"
echo ""
