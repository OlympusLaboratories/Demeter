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

# Vendor packages whose skills should NOT be linked.
# Use this for vendors that provide dev-only skills not relevant to your workflow.
SKIP_VENDOR_SKILLS=(
  "dippy"
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

# ── hook configuration ────────────────────────────────────────────────────────

configure_dippy_hook() {
  local vendor_dir="$REPO_DIR/_vendor"
  local dippy_hook_bin="$vendor_dir/dippy/bin/dippy-hook"
  local settings_file="$HOME/.claude/settings.json"

  if [[ ! -x "$dippy_hook_bin" ]]; then
    warn "Dippy hook script not found at $dippy_hook_bin — skipping hook config"
    return
  fi

  bold "Configuring Dippy hook in settings.json..."

  mkdir -p "$HOME/.claude"

  python3 - "$settings_file" "$dippy_hook_bin" <<'PYEOF'
import json, sys, os

settings_path = sys.argv[1]
hook_command = sys.argv[2]

if os.path.exists(settings_path):
    with open(settings_path, "r") as f:
        settings = json.load(f)
else:
    settings = {}

dippy_hook = {"type": "command", "command": hook_command}
dippy_matcher = "Bash"

hooks = settings.setdefault("hooks", {})
pre_tool_use = hooks.setdefault("PreToolUse", [])

already_configured = False
for entry in pre_tool_use:
    if entry.get("matcher") == dippy_matcher:
        entry_hooks = entry.get("hooks", [])
        if any("dippy" in h.get("command", "") for h in entry_hooks):
            # Update existing dippy hook to current path
            entry["hooks"] = [
                {**h, "command": hook_command} if "dippy" in h.get("command", "") else h
                for h in entry_hooks
            ]
            already_configured = True
        else:
            entry["hooks"] = entry_hooks + [dippy_hook]
            already_configured = True
        break

if not already_configured:
    pre_tool_use.append({
        "matcher": dippy_matcher,
        "hooks": [dippy_hook]
    })

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
PYEOF

  if [[ $? -eq 0 ]]; then
    success "Dippy hook configured in $settings_file"
  else
    error "Failed to configure Dippy hook. Check python3 availability."
  fi
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

  # ── init submodules if needed ───────────────────────────────────────────────
  if [[ -f "$REPO_DIR/.gitmodules" ]]; then
    git -C "$REPO_DIR" submodule update --init --recursive 2>/dev/null
  fi

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

  # ── vendor tool hooks (e.g. dippy) ──────────────────────────────────────
  echo ""
  configure_dippy_hook

  echo ""
  success "Done! You may need to restart your shell for changes to take effect."
}

main "$@"
