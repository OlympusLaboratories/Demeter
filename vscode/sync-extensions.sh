#!/usr/bin/env bash
# Refresh vscode/extensions.txt from the extensions installed in this editor.
#
# install.sh reads that list and installs anything missing. This script is the
# other direction: run it after installing extensions from the Marketplace so
# the list catches up, then commit the diff.
#
# Extensions built from tools/ are excluded — they are installed by their own
# make target, and asking the Marketplace for them would fail.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIST="$REPO_DIR/vscode/extensions.txt"

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}${*}${RESET}"; }
success() { echo -e "${GREEN}✓ ${*}${RESET}"; }
warn()    { echo -e "${YELLOW}! ${*}${RESET}"; }
error()   { echo -e "${RED}✗ ${*}${RESET}"; }
bold()    { echo -e "${BOLD}${*}${RESET}"; }

ask() {
  local prompt="$1" default="${2:-y}"
  local yn_display
  [[ "$default" == "y" ]] && yn_display="[Y/n]" || yn_display="[y/N]"
  echo -en "${BOLD}${prompt} ${yn_display} ${RESET}"
  read -r reply
  reply="${reply:-$default}"
  [[ "$reply" =~ ^[Yy]$ ]]
}

# PATH first, then the macOS app bundle — present even when the user never ran
# "Shell Command: Install 'code' command in PATH".
editor_cli() {
  if command -v code >/dev/null 2>&1; then
    command -v code
  elif command -v codium >/dev/null 2>&1; then
    command -v codium
  elif [[ -x "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" ]]; then
    echo "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
  else
    return 1
  fi
}

# Extension ids published from tools/, derived from each package.json rather
# than hardcoded, so a new tool is excluded without editing this script.
local_tool_extensions() {
  local pkg
  for pkg in "$REPO_DIR"/tools/*/package.json; do
    [[ -f "$pkg" ]] || continue
    python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
pub, name = d.get('publisher'), d.get('name')
if pub and name:
    print(f'{pub}.{name}'.lower())
" "$pkg" 2>/dev/null || true
  done
}

main() {
  bold "\n=== Sync VS Code Extensions ==="
  echo ""

  local cli
  if ! cli="$(editor_cli)"; then
    error "No VS Code CLI found."
    info "Run \"Shell Command: Install 'code' command in PATH\" from the command palette."
    exit 1
  fi
  info "Editor CLI : $cli"
  info "List       : $LIST"
  echo ""

  local excluded
  excluded="$(local_tool_extensions)"

  local current=""
  [[ -f "$LIST" ]] && current="$(sed -e 's/#.*//' -e 's/[[:space:]]//g' "$LIST" | grep -v '^$' | sort -f || true)"

  local installed
  installed="$("$cli" --list-extensions 2>/dev/null | sort -f || true)"

  # Drop locally-built tool extensions from what we are about to record.
  local recorded="$installed"
  if [[ -n "$excluded" ]]; then
    recorded="$(grep -vixF "$excluded" <<<"$installed" || true)"
  fi

  if [[ "$recorded" == "$current" ]]; then
    success "Already up to date — $(grep -c . <<<"$recorded" || echo 0) extension(s), no changes."
    exit 0
  fi

  local added removed
  added="$(comm -13 <(echo "$current") <(echo "$recorded") || true)"
  removed="$(comm -23 <(echo "$current") <(echo "$recorded") || true)"

  [[ -n "$added" ]]   && { bold "New since last sync:"; sed 's/^/  + /' <<<"$added"; }
  [[ -n "$removed" ]] && { bold "In the list but not installed here:"; sed 's/^/  - /' <<<"$removed"; }
  echo ""

  if [[ -n "$removed" ]]; then
    warn "Writing drops those from the list, so other machines stop getting them."
    info "If they are simply not installed on this machine yet, run install.sh first."
    echo ""
  fi

  if ask "Write $(grep -c . <<<"$recorded" || echo 0) extension(s) to extensions.txt?"; then
    printf '%s\n' "$recorded" > "$LIST"
    success "Updated $LIST"
    info "Commit the diff to share it with your other machines."
  else
    info "Left unchanged."
  fi
}

main "$@"
