#!/usr/bin/env bash

set -uo pipefail

PLUGIN_DIR="${DEMETER_ZSH_PLUGINS:-$HOME/.local/share/zsh}"
LOCAL_BIN="$HOME/.local/bin"

PLUGINS=(
  "zsh-autosuggestions|https://github.com/zsh-users/zsh-autosuggestions"
  "zsh-syntax-highlighting|https://github.com/zsh-users/zsh-syntax-highlighting"
  "zsh-completions|https://github.com/zsh-users/zsh-completions"
)

BREW_PKGS=(starship fzf fd bat direnv tmux ripgrep jq)
APT_PKGS=(fd-find bat direnv tmux ripgrep jq)

YELLOW='\033[1;33m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; RESET='\033[0m'
info()    { echo -e "${CYAN}${*}${RESET}"; }
success() { echo -e "${GREEN}✓ ${*}${RESET}"; }
warn()    { echo -e "${YELLOW}! ${*}${RESET}"; }

is_rdev() { [[ -n "${RDEV_CLASS:-}" || -f "$HOME/.rdev-env" ]]; }

missing_tools() {
  local tool
  for tool in starship fzf fd bat direnv tmux rg jq; do
    command -v "$tool" >/dev/null 2>&1 || printf '%s\n' "$tool"
  done
}

missing_plugins() {
  local entry name
  for entry in "${PLUGINS[@]}"; do
    name="${entry%%|*}"
    [[ -d "$PLUGIN_DIR/$name" ]] || printf '%s\n' "$name"
  done
}

install_plugins() {
  local entry name url
  mkdir -p "$PLUGIN_DIR"
  for entry in "${PLUGINS[@]}"; do
    name="${entry%%|*}"
    url="${entry##*|}"
    if [[ -d "$PLUGIN_DIR/$name" ]]; then
      success "$name already present"
      continue
    fi
    info "Cloning $name ..."
    if git clone --depth 1 --quiet "$url" "$PLUGIN_DIR/$name"; then
      success "Installed $name"
    else
      warn "Failed to clone $name from $url"
    fi
  done
}

install_starship_standalone() {
  command -v starship >/dev/null 2>&1 && return 0
  info "Installing starship into $LOCAL_BIN ..."
  mkdir -p "$LOCAL_BIN"
  if curl -fsSL https://starship.rs/install.sh | sh -s -- --yes --bin-dir "$LOCAL_BIN" >/dev/null; then
    success "Installed starship"
  else
    warn "Failed to install starship — see https://starship.rs"
  fi
}

install_fzf_standalone() {
  command -v fzf >/dev/null 2>&1 && return 0
  info "Installing fzf into $LOCAL_BIN ..."
  mkdir -p "$LOCAL_BIN"
  local version arch os
  version="$(curl -fsSL https://api.github.com/repos/junegunn/fzf/releases/latest | sed -n 's/.*"tag_name": *"v\([^"]*\)".*/\1/p' | head -1)"
  if [[ -z "$version" ]]; then
    warn "Could not resolve the latest fzf release"
    return 1
  fi
  case "$(uname -m)" in
    x86_64|amd64) arch=amd64 ;;
    arm64|aarch64) arch=arm64 ;;
    *) warn "Unsupported architecture for the fzf binary release"; return 1 ;;
  esac
  case "$(uname -s)" in
    Darwin) os=darwin ;;
    Linux)  os=linux ;;
    *) warn "Unsupported OS for the fzf binary release"; return 1 ;;
  esac
  if curl -fsSL "https://github.com/junegunn/fzf/releases/download/v${version}/fzf-${version}-${os}_${arch}.tar.gz" \
      | tar -xz -C "$LOCAL_BIN" fzf; then
    success "Installed fzf $version"
  else
    warn "Failed to install fzf"
  fi
}

install_with_brew() {
  local pkg wanted=()
  for pkg in "${BREW_PKGS[@]}"; do
    case "$pkg" in
      fd) command -v fd >/dev/null 2>&1 && continue ;;
      ripgrep) command -v rg >/dev/null 2>&1 && continue ;;
      *) command -v "$pkg" >/dev/null 2>&1 && continue ;;
    esac
    wanted+=("$pkg")
  done
  if [[ "${#wanted[@]}" -eq 0 ]]; then
    success "All Homebrew tools already installed"
    return 0
  fi
  info "brew install ${wanted[*]}"
  brew install "${wanted[@]}" || warn "brew install reported an error"
}

install_with_apt() {
  local pkg wanted=()
  for pkg in "${APT_PKGS[@]}"; do
    case "$pkg" in
      fd-find) command -v fd >/dev/null 2>&1 || command -v fdfind >/dev/null 2>&1 && continue ;;
      bat) command -v bat >/dev/null 2>&1 || command -v batcat >/dev/null 2>&1 && continue ;;
      ripgrep) command -v rg >/dev/null 2>&1 && continue ;;
      *) command -v "$pkg" >/dev/null 2>&1 && continue ;;
    esac
    wanted+=("$pkg")
  done
  if [[ "${#wanted[@]}" -gt 0 ]]; then
    info "sudo apt-get install ${wanted[*]}"
    sudo apt-get update -qq && sudo apt-get install -y --no-install-recommends "${wanted[@]}" \
      || warn "apt-get install reported an error"
  fi
  mkdir -p "$LOCAL_BIN"
  command -v fdfind >/dev/null 2>&1 && [[ ! -e "$LOCAL_BIN/fd" ]] && ln -s "$(command -v fdfind)" "$LOCAL_BIN/fd"
  command -v batcat >/dev/null 2>&1 && [[ ! -e "$LOCAL_BIN/bat" ]] && ln -s "$(command -v batcat)" "$LOCAL_BIN/bat"
  install_starship_standalone
  install_fzf_standalone
}

if [[ "${1:-}" == "--check" ]]; then
  if is_rdev; then
    exit 0
  fi
  missing_tools
  missing_plugins
  exit 0
fi

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<USAGE
Usage: ${0##*/} [--check]

  Installs what shell/terminal.zsh needs and nothing it already has:
  starship, fzf, fd, bat, direnv, tmux, ripgrep, jq, and the three zsh
  plugins under \$DEMETER_ZSH_PLUGINS (default ~/.local/share/zsh).

  --check   Print what is missing, one per line, and exit. Prints nothing
            on an rdev box, which ships all of it.
USAGE
  exit 0
fi

if is_rdev; then
  success "rdev box — the image already ships these tools and plugins."
  exit 0
fi

if command -v brew >/dev/null 2>&1; then
  install_with_brew
elif command -v apt-get >/dev/null 2>&1; then
  install_with_apt
else
  warn "No brew or apt-get — installing what can be fetched directly."
  install_starship_standalone
  install_fzf_standalone
  warn "Install fd, bat, direnv, tmux, ripgrep and jq with your package manager."
fi

install_plugins

echo ""
remaining="$( { missing_tools; missing_plugins; } | tr '\n' ' ')"
if [[ -n "${remaining// /}" ]]; then
  warn "Still missing: $remaining"
else
  success "Everything terminal.zsh uses is installed."
fi
