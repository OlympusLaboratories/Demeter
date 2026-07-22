#!/usr/bin/env bash
# Demeter dotfile installer
# Symlinks files from a profile directory (profiles/<name>/) to the appropriate locations.
# Supports per-machine file selection via a skip list.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILES_DIR="$REPO_DIR/profiles"
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

# ── profile selection & machine ───────────────────────────────────────────────

# Usage / help text. Enumerates the available profiles under profiles/.
usage() {
  cat <<EOF
Usage: ${0##*/} [profile]

  profile   Profile to install. Either the name of a directory under
            profiles/ (e.g. larrabeedylan_work_linux) or a path to a
            profile directory. If omitted, auto-selects when only one
            profile exists, otherwise prompts interactively.

Available profiles:
EOF
  local found=0
  for dir in "$PROFILES_DIR"/*/; do
    [[ -d "$dir" ]] || continue
    echo "  - $(basename "$dir")"
    found=1
  done
  [[ "$found" -eq 0 ]] && echo "  (none found in $PROFILES_DIR)"
}

# Resolve the profile directory to install.
#   - With an argument: accept a bare profile name (under profiles/) or a path.
#   - Without one: auto-select if a single profile exists, else prompt.
# Prints the absolute profile directory to stdout; all prompts go to stderr so
# they don't pollute the captured value.
resolve_profile() {
  local arg="${1:-}"

  if [[ -n "$arg" ]]; then
    local candidate=""
    if [[ -d "$arg" ]]; then
      candidate="$arg"                    # explicit path to a profile dir
    elif [[ -d "$PROFILES_DIR/$arg" ]]; then
      candidate="$PROFILES_DIR/$arg"      # bare name under profiles/
    else
      error "Profile not found: $arg" >&2
      usage >&2
      exit 1
    fi
    ( cd "$candidate" && pwd )            # normalize to absolute, no trailing slash
    return
  fi

  local candidates=()
  for dir in "$PROFILES_DIR"/*/; do
    [[ -d "$dir" ]] || continue
    candidates+=("$(basename "$dir")")
  done

  if [[ ${#candidates[@]} -eq 0 ]]; then
    error "No profiles found in $PROFILES_DIR." >&2
    exit 1
  elif [[ ${#candidates[@]} -eq 1 ]]; then
    echo "$PROFILES_DIR/${candidates[0]}"
  else
    bold "\nAvailable profiles:" >&2
    local i=1
    for c in "${candidates[@]}"; do
      echo "  $i) $c" >&2
      ((i++))
    done
    echo -en "${BOLD}Select your profile (default: 1): ${RESET}" >&2
    read -r choice
    choice="${choice:-1}"
    if ! [[ "$choice" =~ ^[0-9]+$ ]] || (( choice < 1 || choice > ${#candidates[@]} )); then
      error "Invalid selection: $choice" >&2
      exit 1
    fi
    echo "$PROFILES_DIR/${candidates[$((choice-1))]}"
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

# Vendor packages whose skills should NOT be linked.
# Use this for vendors that provide dev-only skills not relevant to your workflow.
SKIP_VENDOR_SKILLS=(
  # "some-vendor"   # example: don't link this vendor's skills
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
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
  fi

  bold "\n=== Demeter Dotfile Installer ==="
  echo ""

  local profile_dir profile machine
  profile_dir="$(resolve_profile "${1:-}")"
  profile="$(basename "$profile_dir")"
  machine="$(detect_machine)"

  info "Profile        : $profile"
  info "Profile dir    : $profile_dir"
  info "Machine type   : $machine"
  info "Repo           : $REPO_DIR"
  echo ""

  if ! ask "Proceed with this configuration?"; then
    echo "Aborted."
    exit 0
  fi
  echo ""

  # ── init submodules if needed ───────────────────────────────────────────────
  if [[ -f "$REPO_DIR/.gitmodules" ]]; then
    git -C "$REPO_DIR" submodule update --init --recursive 2>/dev/null
  fi

  local user_dir="$profile_dir"
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

  # ── .claude setup ──────────────────────────────────────────────────────────
  local claude_src="$user_dir/.claude"
  local claude_dst="$home/.claude"

  # Back up existing .claude before modifying
  if [[ -d "$claude_dst" ]]; then
    local backup_dir="${claude_dst}.bak.$(date +%Y%m%d%H%M%S)"
    info "Backing up $claude_dst to $backup_dir ..."
    cp -a "$claude_dst" "$backup_dir"
    success "Backup created: $backup_dir"
  fi

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
      elif [[ "$name" == "settings.json" ]]; then
        # settings.json is copied (not symlinked) so we can template paths
        bold "  Installing $name (with path templating)..."
        sed "s|__DEMETER_REPO__|$REPO_DIR|g" "$src" > "$claude_dst/$name"
        success "Installed: $claude_dst/$name"
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

  # ── vendor skills (e.g. impeccable) ────────────────────────────────────────
  local vendor_dir="$REPO_DIR/_vendor"
  if [[ -d "$vendor_dir" ]]; then
    for vendor in "$vendor_dir"/*/; do
      local vendor_skills="$vendor.claude/skills"
      [[ -d "$vendor_skills" ]] || continue
      local vendor_name
      vendor_name="$(basename "$vendor")"

      # Check if this vendor's skills should be skipped
      local skip_skills=false
      for sv in "${SKIP_VENDOR_SKILLS[@]+"${SKIP_VENDOR_SKILLS[@]}"}"; do
        [[ "$sv" == "$vendor_name" ]] && { skip_skills=true; break; }
      done
      if [[ "$skip_skills" == true ]]; then
        info "Skipping skills for $vendor_name (in SKIP_VENDOR_SKILLS)"
        continue
      fi

      bold "Linking vendor skills from $vendor_name ..."
      link_directory_contents "$vendor_skills" "$claude_dst/skills" "$machine"
    done
  fi

  # ── clean stale skill symlinks ───────────────────────────────────────────
  # Remove symlinks in ~/.claude/skills that point into this repo but whose
  # target no longer exists (e.g. a skill was renamed or deleted). Iterate over
  # ALL entries — not just ones that resolve to a directory — so that BROKEN
  # symlinks (whose target was renamed away) are caught too. A trailing-slash
  # glob (*/) would silently skip them.
  if [[ -d "$claude_dst/skills" ]]; then
    bold "Cleaning stale skill symlinks..."
    for existing in "$claude_dst/skills"/*; do
      # Only touch symlinks — never real files/dirs the user created.
      [[ -L "$existing" ]] || continue

      local link_target
      link_target="$(readlink "$existing")"

      # Remove only if it points into our repo AND the target no longer exists.
      # For a symlink, `-e` follows the link, so `! -e` is true when it dangles.
      if [[ "$link_target" == "$REPO_DIR/"* && ! -e "$existing" ]]; then
        warn "Removing stale symlink: $existing -> $link_target"
        rm -f "$existing"
      fi
    done
  fi

  # ── ensure data directories for skills that accumulate context ───────────
  for data_dir in \
    "$claude_dst/skills/reflect-self/context" \
    "$claude_dst/skills/reflect-peer/context" \
  ; do
    if [[ ! -d "$data_dir" ]]; then
      mkdir -p "$data_dir"
      success "Created data directory: $data_dir"
    fi
  done

  echo ""
  success "Done! You may need to restart your shell for changes to take effect."
}

main "$@"
