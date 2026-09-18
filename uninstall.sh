#!/usr/bin/env bash
# Demeter dotfile uninstaller
# Removes symlinks created by install.sh and restores a clean state.
#
# It works by scanning your home directory and ~/.claude for symlinks whose
# target points back into this repo, then removing them. This is layout-agnostic
# — it reverses whatever install.sh linked, regardless of which profile was used.
#
# It also removes the templated settings.json copy and the VS Code settings
# symlink, which lives outside both scanned trees.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# ── helpers ───────────────────────────────────────────────────────────────────

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

# Resolve a symlink's target to an absolute path (target may be relative).
resolve_link() {
  local link="$1" target
  target="$(readlink "$link")"
  if [[ "$target" == /* ]]; then
    echo "$target"
  else
    echo "$(cd "$(dirname "$link")" && cd "$(dirname "$target")" 2>/dev/null && pwd)/$(basename "$target")"
  fi
}

# True if the symlink points into REPO_DIR (whether or not the target still exists).
points_into_repo() {
  local link="$1" target
  target="$(readlink "$link")"
  # Fast path: absolute target with repo prefix.
  [[ "$target" == "$REPO_DIR/"* || "$target" == "$REPO_DIR" ]] && return 0
  # Relative target: resolve and compare.
  local resolved
  resolved="$(resolve_link "$link" 2>/dev/null || true)"
  [[ -n "$resolved" && ( "$resolved" == "$REPO_DIR/"* || "$resolved" == "$REPO_DIR" ) ]]
}

removed=0
kept=0

remove_if_ours() {
  local link="$1"
  [[ -L "$link" ]] || return 0
  if points_into_repo "$link"; then
    warn "Removing symlink: $link -> $(readlink "$link")"
    rm -f "$link"
    ((removed++)) || true
  fi
}

# ── main ──────────────────────────────────────────────────────────────────────

main() {
  bold "\n=== Demeter Dotfile Uninstaller ==="
  echo ""
  info "Repo : $REPO_DIR"
  info "Home : $HOME"
  echo ""
  warn "This removes all symlinks pointing into the Demeter repo from your"
  warn "home directory and ~/.claude. Your repo files are NOT touched."
  echo ""

  if ! ask "Proceed?"; then
    echo "Aborted."
    exit 0
  fi
  echo ""

  local home="$HOME"
  local claude_dst="$home/.claude"

  # ── top-level dotfiles in $HOME ──────────────────────────────────────────
  bold "Removing dotfile symlinks in $home ..."
  for link in "$home"/.*; do
    local name
    name="$(basename "$link")"
    [[ "$name" == "." || "$name" == ".." ]] && continue
    # Never descend into or remove .claude here; handled separately below.
    [[ "$name" == ".claude" ]] && continue
    remove_if_ours "$link"
  done
  echo ""

  # ── ~/.claude contents (recursive) ───────────────────────────────────────
  if [[ -d "$claude_dst" ]]; then
    bold "Removing Demeter symlinks under $claude_dst ..."
    # find every symlink under ~/.claude and drop the ones pointing into the repo
    while IFS= read -r -d '' link; do
      remove_if_ours "$link"
    done < <(find "$claude_dst" -type l -print0 2>/dev/null)

    # settings.json is COPIED (not symlinked) with repo-path templating.
    # Detect it by the templated repo path and offer to remove it.
    local settings="$claude_dst/settings.json"
    if [[ -f "$settings" && ! -L "$settings" ]] && grep -q "$REPO_DIR" "$settings" 2>/dev/null; then
      if ask "Remove templated settings.json ($settings)?"; then
        rm -f "$settings"
        success "Removed: $settings"
        ((removed++)) || true
      else
        ((kept++)) || true
      fi
    fi
  else
    info "No ~/.claude directory found; skipping."
  fi
  echo ""

  # ── vscode settings ──────────────────────────────────────────────────────
  # Editor settings live outside $HOME's dotfiles and ~/.claude, so the scans
  # above never reach them. Check every path install.sh knows about, on both
  # platforms — a path that does not exist is simply skipped.
  bold "Removing VS Code settings symlinks ..."
  for editor_dir in \
    "$home/Library/Application Support/Code/User" \
    "$home/Library/Application Support/Code - Insiders/User" \
    "$home/Library/Application Support/VSCodium/User" \
    "$home/.config/Code/User" \
    "$home/.config/Code - Insiders/User" \
    "$home/.config/VSCodium/User" \
  ; do
    [[ -d "$editor_dir" ]] || continue
    local settings_link="$editor_dir/settings.json"
    [[ -L "$settings_link" ]] && points_into_repo "$settings_link" || continue
    remove_if_ours "$settings_link"

    # install.sh backs the original up alongside it as settings.json.bak.<ts>.
    local latest_settings
    latest_settings="$(ls -dt "$settings_link".bak.* 2>/dev/null | head -n1 || true)"
    if [[ -n "$latest_settings" && -f "$latest_settings" ]]; then
      if ask "Restore $latest_settings over $settings_link?"; then
        cp "$latest_settings" "$settings_link"
        success "Restored: $settings_link"
      else
        ((kept++)) || true
      fi
    fi
  done
  echo ""

  # ── clean up now-empty dirs left behind ──────────────────────────────────
  for dir in "$claude_dst/skills" "$claude_dst/hooks" "$claude_dst/tools"; do
    [[ -d "$dir" ]] || continue
    find "$dir" -mindepth 1 -type d -empty -delete 2>/dev/null || true
    # remove the directory itself if it ended up empty
    rmdir "$dir" 2>/dev/null || true
  done

  echo ""
  success "Done. Removed $removed symlink(s)/file(s); kept $kept."
  info "Skill data directories were left in place."
  info "You may need to restart your shell for changes to take effect."
}

main "$@"
