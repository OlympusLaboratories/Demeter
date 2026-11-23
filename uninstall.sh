#!/usr/bin/env bash
# Demeter dotfile uninstaller
# Removes symlinks created by install.sh and restores a clean state.
#
# It sweeps every directory install.sh links into — declared once in
# lib/paths.sh as demeter_link_roots, so the two directions cannot drift — and
# removes the symlinks whose target points back into this repo. This is
# layout-agnostic: it reverses whatever install.sh linked, regardless of which
# profile was used.
#
# It also offers to restore the editor settings.json backup install.sh takes.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSUME_YES=false
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# shellcheck source-path=SCRIPTDIR
# shellcheck source=vscode/lib.sh
source "$REPO_DIR/vscode/lib.sh"
# shellcheck source=lib/paths.sh
source "$REPO_DIR/lib/paths.sh"

# ── helpers ───────────────────────────────────────────────────────────────────

info()    { echo -e "${CYAN}${*}${RESET}"; }
success() { echo -e "${GREEN}✓ ${*}${RESET}"; }
warn()    { echo -e "${YELLOW}! ${*}${RESET}"; }
bold()    { echo -e "${BOLD}${*}${RESET}"; }

usage() {
  cat <<EOF
Usage: ${0##*/} [-y|--yes]

  -y, --yes  Answer every prompt with yes instead of reading stdin.
EOF
}

ask() {
  local prompt="$1" default="${2:-y}"
  local yn_display
  [[ "$default" == "y" ]] && yn_display="[Y/n]" || yn_display="[y/N]"
  echo -en "${BOLD}${prompt} ${yn_display} ${RESET}"
  if [[ "$ASSUME_YES" == true ]]; then
    echo "y"
    return 0
  fi
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
REMOVED_LINKS=()

remove_if_ours() {
  local link="$1"
  [[ -L "$link" ]] || return 0
  if points_into_repo "$link"; then
    warn "Removing symlink: $link -> $(readlink "$link")"
    rm -f "$link"
    REMOVED_LINKS+=("$link")
    ((removed++)) || true
  fi
}

was_removed() {
  local needle="$1" seen
  for seen in "${REMOVED_LINKS[@]+"${REMOVED_LINKS[@]}"}"; do
    [[ "$seen" == "$needle" ]] && return 0
  done
  return 1
}

# ── main ──────────────────────────────────────────────────────────────────────

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -y|--yes) ASSUME_YES=true; shift ;;
      -h|--help) usage; exit 0 ;;
      *) warn "Unknown option: $1"; usage >&2; exit 1 ;;
    esac
  done

  bold "\n=== Demeter Dotfile Uninstaller ==="
  echo ""
  info "Repo : $REPO_DIR"
  info "Home : $HOME"
  echo ""
  warn "This removes every symlink pointing into the Demeter repo from the"
  warn "directories install.sh links into. Your repo files are NOT touched."
  echo ""
  bold "Directories to sweep:"
  local root
  while IFS= read -r root; do
    [[ -d "$root" ]] || continue
    if demeter_link_root_is_recursive "$root"; then
      info "  ${root/#$HOME/\~} (recursive)"
    else
      info "  ${root/#$HOME/\~}"
    fi
  done < <(demeter_link_roots)
  echo ""

  if ! ask "Proceed?"; then
    echo "Aborted."
    exit 0
  fi
  echo ""

  # ── sweep every declared link root ───────────────────────────────────────
  # Collect first, then remove: remove_if_ours must not run inside a loop that
  # is itself being fed from a redirect.
  local -a links=()
  while IFS= read -r root; do
    [[ -d "$root" ]] || continue
    local -a depth=(-maxdepth 1)
    demeter_link_root_is_recursive "$root" && depth=()
    while IFS= read -r -d '' link; do
      links+=("$link")
    done < <(find "$root" "${depth[@]+"${depth[@]}"}" -type l -print0 2>/dev/null)
  done < <(demeter_link_roots)

  bold "Removing Demeter symlinks ..."
  local link
  for link in "${links[@]+"${links[@]}"}"; do
    remove_if_ours "$link"
  done
  echo ""

  # ── restore editor settings backups ──────────────────────────────────────
  # install.sh backs the original up alongside it as settings.json.bak.<ts>.
  # Both platforms' directories are checked, as demeter_link_roots does: this
  # script does not detect a machine type. A restore is only offered where the
  # sweep above actually removed our link, so a -y run cannot copy an old
  # backup over a settings.json this repo never owned.
  bold "Checking for VS Code settings backups ..."
  # Collect the paths up front. ask prompts on its own stdin, so it must not
  # run inside a loop that is itself being fed from a redirect.
  local -a backups=()
  local editor_dir
  while IFS= read -r editor_dir; do
    [[ -d "$editor_dir" ]] || continue
    local settings_link="$editor_dir/settings.json"
    was_removed "$settings_link" || continue
    local latest_settings
    latest_settings="$(ls -dt "$settings_link".bak.* 2>/dev/null | head -n1 || true)"
    [[ -n "$latest_settings" && -f "$latest_settings" ]] || continue
    backups+=("$latest_settings")
  done < <(vscode_user_dirs mac; vscode_user_dirs linux)

  local backup settings_target
  for backup in "${backups[@]+"${backups[@]}"}"; do
    settings_target="${backup%.bak.*}"
    if ask "Restore $backup over $settings_target?"; then
      cp "$backup" "$settings_target"
      success "Restored: $settings_target"
    else
      ((kept++)) || true
    fi
  done
  echo ""

  # ── clean up now-empty dirs left behind ──────────────────────────────────
  local claude_dst="$HOME/.claude"
  for dir in "$claude_dst/skills" "$claude_dst/hooks" "$claude_dst/tools"; do
    [[ -d "$dir" ]] || continue
    find "$dir" -mindepth 1 -type d -empty -delete 2>/dev/null || true
    # remove the directory itself if it ended up empty
    rmdir "$dir" 2>/dev/null || true
  done

  echo ""
  success "Done. Removed $removed symlink(s); kept $kept."
  info "Skill data directories were left in place."
  info "You may need to restart your shell for changes to take effect."
}

main "$@"
