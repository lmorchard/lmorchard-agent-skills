#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="${SKILL_DIR}/config/config.json"
DATA_DIR="${SKILL_DIR}/data"

echo "╔════════════════════════════════════════╗"
echo "║   Weeknotes Composer Setup            ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Check if config already exists
if [ -f "${CONFIG_FILE}" ]; then
    echo "⚠️  Configuration already exists."
    read -p "Do you want to reconfigure? (y/N): " RECONFIGURE
    if [[ ! "$RECONFIGURE" =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 0
    fi
    echo ""
fi

echo "This setup will configure connections to your data sources."
echo ""

# ============================================================================
# Mastodon Configuration
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📱 Mastodon Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Enter your Mastodon instance details."
echo "Example server: https://mastodon.social"
echo ""

read -p "Mastodon server URL: " MASTODON_SERVER
MASTODON_SERVER="${MASTODON_SERVER%/}"

# Validate URL format
if [[ ! "$MASTODON_SERVER" =~ ^https?:// ]]; then
    echo "❌ Error: URL must start with http:// or https://"
    exit 1
fi

echo ""
echo "To get your Mastodon access token:"
echo "1. Log into your Mastodon instance"
echo "2. Go to Settings → Development → New Application"
echo "3. Give it a name (e.g., 'Weeknotes Composer')"
echo "4. Grant 'read' permissions"
echo "5. Copy the access token"
echo ""

read -sp "Mastodon access token: " MASTODON_TOKEN
echo ""

# Validate token is not empty
if [ -z "$MASTODON_TOKEN" ]; then
    echo "❌ Error: Access token cannot be empty"
    exit 1
fi

# Test the Mastodon connection
echo ""
echo "🔍 Testing Mastodon connection..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    "${MASTODON_SERVER}/api/v1/accounts/verify_credentials" \
    -H "Authorization: Bearer ${MASTODON_TOKEN}")

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "✅ Mastodon connection successful!"
else
    echo "❌ Mastodon connection failed (HTTP ${HTTP_CODE})"
    echo "   Please check your server URL and token."
    exit 1
fi

echo ""

# ============================================================================
# Linkding Configuration
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔖 Linkding Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Enter your Linkding instance details."
echo "Example: https://linkding.example.com"
echo ""

read -p "Linkding URL: " LINKDING_URL
LINKDING_URL="${LINKDING_URL%/}"

# Validate URL format
if [[ ! "$LINKDING_URL" =~ ^https?:// ]]; then
    echo "❌ Error: URL must start with http:// or https://"
    exit 1
fi

echo ""
echo "To get your Linkding API token:"
echo "1. Log into your Linkding instance"
echo "2. Go to Settings → Integrations"
echo "3. Click 'Create Token'"
echo "4. Copy the generated token"
echo ""

read -sp "Linkding API token: " LINKDING_TOKEN
echo ""

# Validate token is not empty
if [ -z "$LINKDING_TOKEN" ]; then
    echo "❌ Error: API token cannot be empty"
    exit 1
fi

# Test the Linkding connection
echo ""
echo "🔍 Testing Linkding connection..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    "${LINKDING_URL}/api/bookmarks/?limit=1" \
    -H "Authorization: Token ${LINKDING_TOKEN}")

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "✅ Linkding connection successful!"
else
    echo "❌ Linkding connection failed (HTTP ${HTTP_CODE})"
    echo "   Please check your URL and token."
    exit 1
fi

echo ""

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
echo "Leave blank to skip style reference."
echo ""

read -p "Weeknotes archive URL (optional): " WEEKNOTES_ARCHIVE_URL

# Remove trailing slash if present
WEEKNOTES_ARCHIVE_URL="${WEEKNOTES_ARCHIVE_URL%/}"

# Validate URL format if provided
if [ -n "$WEEKNOTES_ARCHIVE_URL" ] && [[ ! "$WEEKNOTES_ARCHIVE_URL" =~ ^https?:// ]]; then
    echo "⚠️  Warning: URL should start with http:// or https://"
    echo "   Proceeding anyway..."
fi

if [ -n "$WEEKNOTES_ARCHIVE_URL" ]; then
    echo "✅ Style reference URL configured"
else
    echo "⏭️  Skipping style reference"
fi

echo ""

# ============================================================================
# Save Configuration
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💾 Saving Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Create config directory if it doesn't exist
mkdir -p "$(dirname "${CONFIG_FILE}")"

# Create data directory if it doesn't exist
mkdir -p "${DATA_DIR}"

# Write config file with conditional weeknotes_archive
if [ -n "$WEEKNOTES_ARCHIVE_URL" ]; then
cat > "${CONFIG_FILE}" <<EOF
{
  "mastodon": {
    "server": "${MASTODON_SERVER}",
    "token": "${MASTODON_TOKEN}"
  },
  "linkding": {
    "url": "${LINKDING_URL}",
    "token": "${LINKDING_TOKEN}"
  },
  "weeknotes_archive": "${WEEKNOTES_ARCHIVE_URL}",
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
else
cat > "${CONFIG_FILE}" <<EOF
{
  "mastodon": {
    "server": "${MASTODON_SERVER}",
    "token": "${MASTODON_TOKEN}"
  },
  "linkding": {
    "url": "${LINKDING_URL}",
    "token": "${LINKDING_TOKEN}"
  },
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
fi

# Secure the config file
chmod 600 "${CONFIG_FILE}"

echo "✅ Configuration saved to: ${CONFIG_FILE}"
echo ""
echo "╔════════════════════════════════════════╗"
echo "║   Setup Complete!                      ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "You can now use the weeknotes composer."
echo ""
