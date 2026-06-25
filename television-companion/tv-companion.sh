#!/usr/bin/env bash
#
# tv-companion.sh — drive a display-only Television "visual companion".
#
# Subcommands:
#   start "<topic>"            create + focus a Television screen for this session
#   show  "<card>" [file]      render a fragment (file or stdin) as a card on the screen
#   list                       list the session's cards
#   stop                       end the active session (screen + cards persist in TV)
#
# Cards are named. A new name adds a new card; reusing a name rewrites that
# card's HTML in place (Television re-serves the changed file automatically).
#
# Working files live under <project>/.television-companion/<session>/ and are
# self-ignored by git (a `.gitignore` containing `*` is dropped in the base dir).
#
# Feedback is DISPLAY-ONLY: the user reads the screen and responds in the
# terminal. There is no click-back channel (see SKILL.md "Bi-directional").

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAME="$SCRIPT_DIR/frame.html"

# --- project + session paths -------------------------------------------------
project_root() {
  git rev-parse --show-toplevel 2>/dev/null || pwd
}
BASE="$(project_root)/.television-companion"
ACTIVE="$BASE/active"

die() { echo "tv-companion: $*" >&2; exit 1; }

slugify() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g' | cut -c1-48
}

# Television 0.1.160 reads its token from <storage>/state/token. Older daemons
# wrote <storage>/token. Bridge if the new location is missing but the old isn't.
ensure_token() {
  local sp tok
  sp="$(tv storage-path 2>/dev/null | sed -E 's/.*"storagePath":"([^"]*)".*/\1/')" || return 0
  [ -n "$sp" ] || return 0
  if [ ! -f "$sp/state/token" ] && [ -f "$sp/token" ]; then
    mkdir -p "$sp/state" && cp "$sp/token" "$sp/state/token"
  fi
}

tv_id() { grep -oE '01[A-Z0-9]{24}' | head -1; }   # pull a ULID from tv output

# --- subcommands -------------------------------------------------------------
cmd_start() {
  local topic="${1:-}"; [ -n "$topic" ] || die 'start needs a topic: start "Inspector layout"'
  ensure_token
  local slug sess screen
  slug="$(slugify "$topic")"
  sess="$BASE/$slug"
  mkdir -p "$sess"
  printf '*\n' > "$BASE/.gitignore"   # self-ignore the whole companion dir

  screen="$(tv create-screen --name "Brainstorm: $topic" --focus-screen </dev/null 2>&1 | tv_id)"
  [ -n "$screen" ] || die "could not create screen (is the tv daemon running? try: tv status)"

  : > "$sess/cards.tsv"
  printf 'topic\t%s\nslug\t%s\nscreen\t%s\n' "$topic" "$slug" "$screen" > "$sess/session.meta"
  echo "$slug" > "$ACTIVE"

  echo "session : $slug"
  echo "screen  : $screen (focused)"
  echo "workdir : $sess"
  echo "next    : tv-companion.sh show \"<card-name>\" <fragment.html>"
}

active_session() {
  [ -f "$ACTIVE" ] || die "no active session — run: tv-companion.sh start \"<topic>\""
  local slug; slug="$(cat "$ACTIVE")"
  echo "$BASE/$slug"
}

cmd_show() {
  local card="${1:-}"; [ -n "$card" ] || die 'show needs a card name: show "layout-a" frag.html'
  shift || true
  local sess screen cslug out frag
  sess="$(active_session)"
  screen="$(sed -nE 's/^screen\t(.*)$/\1/p' "$sess/session.meta")"
  cslug="$(slugify "$card")"
  out="$sess/$cslug.html"

  # read fragment from file arg or stdin
  frag="$(mktemp)"; trap 'rm -f "$frag"' RETURN
  if [ "${1:-}" ] && [ -f "$1" ]; then cat "$1" > "$frag"; else cat > "$frag"; fi
  [ -s "$frag" ] || die "empty fragment for card \"$card\""

  # full document? serve as-is. otherwise wrap in the frame.
  if head -c 200 "$frag" | grep -qiE '<!doctype|<html'; then
    cp "$frag" "$out"
  else
    awk -v t="$card" -v frag="$frag" '
      { gsub(/__TITLE__/, t) }
      /<!--TVC_FRAGMENT_INJECT-->/ { while ((getline line < frag) > 0) print line; next }
      { print }
    ' "$FRAME" > "$out"
    # Guard: the body must actually contain the fragment. If the sentinel
    # survived (frame edited badly) or the <body> is empty, fail loudly —
    # a card that serves a blank page is worse than an error.
    if grep -q 'TVC_FRAGMENT_INJECT' "$out"; then
      die "frame sentinel not replaced — check frame.html has exactly one <!--TVC_FRAGMENT_INJECT--> in <body>"
    fi
    if ! awk '/<body>/{b=1;next} /<\/body>/{b=0} b && NF{print}' "$out" | grep -q .; then
      die "wrapped card \"$card\" has an empty <body> — fragment did not inject"
    fi
  fi

  # new card -> create artifact; existing -> file rewrite already live.
  local existing
  existing="$(sed -nE "s/^$cslug\t(.*)$/\1/p" "$sess/cards.tsv")"
  if [ -n "$existing" ]; then
    echo "updated card \"$card\" (artifact $existing) — Television re-serves the change"
  else
    ensure_token
    local art
    art="$(tv create-path-artifact --screen "$screen" --title "$card" --path "$out" --no-focus </dev/null 2>&1 | tv_id)"
    [ -n "$art" ] || die "could not create card artifact for \"$card\""
    printf '%s\t%s\n' "$cslug" "$art" >> "$sess/cards.tsv"
    echo "added card \"$card\" (artifact $art)"
  fi
}

cmd_list() {
  local sess; sess="$(active_session)"
  echo "session: $(sed -nE 's/^topic\t(.*)$/\1/p' "$sess/session.meta")"
  echo "screen : $(sed -nE 's/^screen\t(.*)$/\1/p' "$sess/session.meta")"
  echo "cards  :"
  if [ -s "$sess/cards.tsv" ]; then awk -F'\t' '{print "  - "$1" ("$2")"}' "$sess/cards.tsv"; else echo "  (none yet)"; fi
}

cmd_stop() {
  [ -f "$ACTIVE" ] || { echo "no active session"; return 0; }
  local slug; slug="$(cat "$ACTIVE")"
  rm -f "$ACTIVE"
  echo "ended session \"$slug\" — its screen and cards remain in Television"
}

# --- dispatch ----------------------------------------------------------------
sub="${1:-}"; shift || true
case "$sub" in
  start) cmd_start "$@" ;;
  show)  cmd_show  "$@" ;;
  list)  cmd_list  "$@" ;;
  stop)  cmd_stop  "$@" ;;
  *) die "usage: tv-companion.sh {start|show|list|stop} ..." ;;
esac
