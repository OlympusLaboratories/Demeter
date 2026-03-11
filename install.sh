#!/usr/bin/env bash
# Demeter dotfile installer
# Symlinks files from your username directory to the appropriate locations.
# Supports per-machine file selection via a skip list.

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

# ── detect username & machine ─────────────────────────────────────────────────

detect_username() {
  local candidates=()
  for dir in "$REPO_DIR"/*/; do
    local name
    name="$(basename "$dir")"
    [[ "$name" == _* ]] && continue   # skip _starter etc.
    candidates+=("$name")
  done

  if [[ ${#candidates[@]} -eq 0 ]]; then
    error "No user directories found in repo."
    exit 1
  elif [[ ${#candidates[@]} -eq 1 ]]; then
    echo "${candidates[0]}"
  else
    bold "\nMultiple user directories found:"
    local i=1
    for c in "${candidates[@]}"; do
      echo "  $i) $c"
      ((i++))
    done
    echo -n "Select your directory (default: 1): "
    read -r choice
    choice="${choice:-1}"
    echo "${candidates[$((choice-1))]}"
  fi
}

detect_machine() {
  # Heuristic: macOS = local machine, Linux = remote dev box
  local os
  os="$(uname -s)"
  if [[ "$os" == "Darwin" ]]; then
    echo "mac"
  else
    echo "linux"
  fi
}

# ── skip list ─────────────────────────────────────────────────────────────────
# Files/dirs to skip on specific machines.
# Format: "filename:machine"  (machine = mac | linux | both)
# "both" means skip everywhere. Add more entries as needed.

SKIP_LIST=(
  # ".bash_profile:linux"   # example: skip bash_profile on linux
)

should_skip() {
  local file="$1" machine="$2"
  for entry in "${SKIP_LIST[@]+"${SKIP_LIST[@]}"}"; do
    local f="${entry%%:*}" m="${entry##*:}"
    if [[ "$f" == "$file" && ( "$m" == "$machine" || "$m" == "both" ) ]]; then
      return 0
    fi
  done
  return 1
}

# ── symlinking ────────────────────────────────────────────────────────────────

link_file() {
  local src="$1" dst="$2"

  if [[ -L "$dst" ]]; then
    local current_target
    current_target="$(readlink "$dst")"
    # Normalize trailing slashes before comparing
    if [[ "${current_target%/}" == "${src%/}" ]]; then
      success "Already linked: $dst"
      return
    fi
    warn "Symlink exists but points elsewhere: $dst -> $current_target"
    if ask "  Replace?"; then
      rm -f "$dst"
      ln -s "$src" "$dst"
      success "Relinked: $dst -> $src"
    fi
  elif [[ -e "$dst" ]]; then
    warn "Real file exists: $dst"
    if ask "  Back up and replace?"; then
      local backup="${dst}.bak.$(date +%Y%m%d%H%M%S)"
      mv "$dst" "$backup"
      warn "  Backed up to $backup"
      ln -s "$src" "$dst"
      success "Linked: $dst -> $src"
    fi
  else
    # Ensure parent directory exists
    mkdir -p "$(dirname "$dst")"
    ln -s "$src" "$dst"
    success "Linked: $dst -> $src"
  fi
}

link_directory_contents() {
  local src_dir="$1" dst_dir="$2" machine="$3"
  # For directories (like .claude/skills), link each item inside individually
  mkdir -p "$dst_dir"
  for item in "$src_dir"/*; do
    [[ -e "$item" ]] || continue
    local name
    name="$(basename "$item")"
    should_skip "$name" "$machine" && { warn "Skipping $name (machine=$machine)"; continue; }
    link_file "$item" "$dst_dir/$name"
  done
}

# ── main ──────────────────────────────────────────────────────────────────────

main() {
  bold "\n=== Demeter Dotfile Installer ==="
  echo ""

  local username machine
  username="$(detect_username)"
  machine="$(detect_machine)"

  info "User directory : $username"
  info "Machine type   : $machine"
  info "Repo           : $REPO_DIR"
  echo ""

  if ! ask "Proceed with this configuration?"; then
    echo "Aborted."
    exit 0
  fi
  echo ""

  local user_dir="$REPO_DIR/$username"
  local home="$HOME"

  # ── standard dotfiles ──────────────────────────────────────────────────────
  bold "Linking dotfiles to $home ..."

  for src in "$user_dir"/.*; do
    local name
    name="$(basename "$src")"

    # skip meta entries
    [[ "$name" == "." || "$name" == ".." || "$name" == ".git" ]] && continue

    # .claude gets special treatment below
    [[ "$name" == ".claude" ]] && continue

    should_skip "$name" "$machine" && { warn "Skipping $name (machine=$machine)"; continue; }

    link_file "$src" "$home/$name"
  done

  echo ""

  # ── .claude skills ─────────────────────────────────────────────────────────
  local claude_src="$user_dir/.claude"
  local claude_dst="$home/.claude"

  if [[ -d "$claude_src" ]]; then
    bold "Linking .claude contents to $claude_dst ..."

    # Top-level files in .claude (e.g. settings.json, CLAUDE.md)
    for src in "$claude_src"/*; do
      [[ -e "$src" ]] || continue
      local name
      name="$(basename "$src")"

      if [[ -d "$src" ]]; then
        # For subdirectories (e.g. skills/), link each item inside
        bold "  Linking $name/ entries..."
        link_directory_contents "$src" "$claude_dst/$name" "$machine"
      else
        link_file "$src" "$claude_dst/$name"
      fi
    done

    # Hidden files inside .claude
    for src in "$claude_src"/.*; do
      local name
      name="$(basename "$src")"
      [[ "$name" == "." || "$name" == ".." ]] && continue
      link_file "$src" "$claude_dst/$name"
    done
  fi

  echo ""
  success "Done! You may need to restart your shell for changes to take effect."
}

main "$@"
