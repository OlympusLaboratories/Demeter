#!/usr/bin/env bash
# Refresh vscode/extensions.txt from the extensions installed in this editor.
#
# install.sh reads that list and installs anything missing. This script is the
# other direction: run it after installing extensions from the Marketplace so
# the list catches up, then commit the diff.
#
# Extensions built from tools/ are excluded — they are installed by their own
# make target, and asking the Marketplace for them would fail.
#
# The editor CLI, the tool-id extraction and the list parser all come from
# vscode/lib.sh, shared with install.sh: a second copy of any of them drifts
# into a weaker subset, which is how this script used to fail outright on a
# Remote-SSH box that install.sh handled fine.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIST="$REPO_DIR/vscode/extensions.txt"

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
source "$REPO_DIR/vscode/lib.sh"

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

# Extension ids published from tools/, so a new tool is excluded without
# editing this script.
local_tool_extensions() {
  local tool_dir id
  for tool_dir in "$REPO_DIR"/tools/*/; do
    [[ -d "$tool_dir" ]] || continue
    id="$(tool_extension_id "${tool_dir%/}")" || continue
    echo "$id"
  done
}

main() {
  bold "\n=== Sync VS Code Extensions ==="
  echo ""

  local cli
  if ! cli="$(editor_cli)"; then
    error "No VS Code CLI found."
    info "Looked on PATH, in the macOS app bundle, and under ~/.vscode-server."
    info "Run \"Shell Command: Install 'code' command in PATH\" from the command palette."
    exit 1
  fi
  info "Editor CLI : $cli"
  info "List       : $LIST"
  echo ""

  local excluded
  excluded="$(local_tool_extensions)"
  # tool_extension_id shells out to python3 and reports failure the same way it
  # reports a package.json without a publisher. Writing the list with an empty
  # exclusion set would record the locally-built ids and send every other
  # machine to the Marketplace for extensions that are not there.
  if [[ -z "$excluded" ]] && compgen -G "$REPO_DIR/tools/*/package.json" >/dev/null; then
    error "tools/ has package.json files but no extension id could be read from any of them."
    info "python3 is needed to parse them; without it the list would record locally-built extensions."
    exit 1
  fi

  # Both sides must agree on case and on collation, or comm reports differences
  # that are not there — silently, and exiting 0. --list-extensions reports a
  # publisher's registered case while the list on disk is lowercase, so a
  # mixed-case id would otherwise show up as both an add and a drop; and plain
  # sort is locale-collated, which orders punctuation differently under glibc
  # than under macOS. LC_ALL=C on every sort and every comm pins both.
  local current=""
  current="$(read_extension_list "$LIST" | tr '[:upper:]' '[:lower:]' | LC_ALL=C sort || true)"

  local installed
  installed="$("$cli" --list-extensions 2>/dev/null | tr '[:upper:]' '[:lower:]' | LC_ALL=C sort || true)"

  # Drop locally-built tool extensions from what we are about to record.
  local recorded="$installed"
  if [[ -n "$excluded" ]]; then
    recorded="$(grep -vxF "$excluded" <<<"$installed" || true)"
  fi

  if [[ "$recorded" == "$current" ]]; then
    success "Already up to date — $(grep -c . <<<"$recorded" || echo 0) extension(s), no changes."
    exit 0
  fi

  local added removed
  added="$(LC_ALL=C comm -13 <(echo "$current") <(echo "$recorded") || true)"
  removed="$(LC_ALL=C comm -23 <(echo "$current") <(echo "$recorded") || true)"

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
