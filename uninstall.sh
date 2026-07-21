#!/usr/bin/env bash
# Demeter dotfile uninstaller
# Removes symlinks created by install.sh and restores a clean state.
#
# It works by scanning your home directory and ~/.claude for symlinks whose
# target points back into this repo, then removing them. This is layout-agnostic
# — it reverses whatever install.sh linked, regardless of which profile was used.
#
# It also removes the templated settings.json copy, and can optionally restore
# the most recent ~/.claude backup that install.sh created.

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

  # ── clean up now-empty skill dirs left behind ────────────────────────────
  if [[ -d "$claude_dst/skills" ]]; then
    find "$claude_dst/skills" -mindepth 1 -type d -empty -delete 2>/dev/null || true
    # remove skills/ itself if it ended up empty
    rmdir "$claude_dst/skills" 2>/dev/null || true
  fi

  # ── offer to restore the most recent .claude backup ──────────────────────
  local latest_backup
  latest_backup="$(ls -dt "${claude_dst}".bak.* 2>/dev/null | head -n1 || true)"
  if [[ -n "$latest_backup" && -d "$latest_backup" ]]; then
    bold "Found backup: $latest_backup"
    if ask "Restore this backup over $claude_dst?" "n"; then
      # Move current (mostly-unlinked) .claude aside, then restore the backup.
      if [[ -d "$claude_dst" ]]; then
        local aside="${claude_dst}.uninstall.$(date +%Y%m%d%H%M%S)"
        mv "$claude_dst" "$aside"
        warn "Moved current $claude_dst to $aside"
      fi
      cp -a "$latest_backup" "$claude_dst"
      success "Restored $claude_dst from backup"
    fi
  fi

  echo ""
  success "Done. Removed $removed symlink(s)/file(s); kept $kept."
  info "Backups (~/.claude.bak.*) and skill data directories were left in place."
  info "You may need to restart your shell for changes to take effect."
}

main "$@"
