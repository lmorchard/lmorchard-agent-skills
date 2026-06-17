#!/usr/bin/env bash
#
# Ad-hoc push notification to Les's phone via ntfy.
# Shares credentials with the Claude Code notify hook (~/.claude/hooks/notify.env).
#
# Usage: send.sh [--priority urgent|high|default|low|min] [--title TITLE] [--tags a,b] <message>
# Prints ntfy's JSON response; exits non-zero on misuse or transport failure.

set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/opt/homebrew/anaconda3/bin:/usr/bin:/bin:$PATH"

CONFIG="${HOME}/.claude/hooks/notify.env"
# shellcheck source=/dev/null
[ -r "$CONFIG" ] && . "$CONFIG"
: "${NTFY_URL:=https://ntfy.lmorchard.com}"
: "${NTFY_TOPIC:=cc-claude}"
: "${NTFY_TOKEN:=}"

priority="default"
title=""
tags=""
while [ $# -gt 0 ]; do
  case "$1" in
    --priority) priority="$2"; shift 2 ;;
    --title)    title="$2";    shift 2 ;;
    --tags)     tags="$2";     shift 2 ;;
    --)         shift; break ;;
    -*)         echo "unknown option: $1" >&2; exit 2 ;;
    *)          break ;;
  esac
done
message="$*"

[ -n "$NTFY_TOKEN" ] || { echo "NTFY_TOKEN not set in $CONFIG" >&2; exit 1; }
[ -n "$message" ]    || { echo "usage: send.sh [--priority P] [--title T] [--tags a,b] <message>" >&2; exit 2; }

curl -sS --max-time 10 \
  -H "Authorization: Bearer ${NTFY_TOKEN}" \
  ${title:+-H "Title: ${title}"} \
  -H "Priority: ${priority}" \
  ${tags:+-H "Tags: ${tags}"} \
  -d "$message" \
  "${NTFY_URL}/${NTFY_TOPIC}"
