#!/usr/bin/env bash
set -uo pipefail

REPOS=(
  "Demeter|https://github.com/OlympusLaboratories/Demeter.git"
  "gridmatic-dev|https://gitlab.com/gridmatic/foundation/gridmatic-dev.git"
  "tlaloc|https://gitlab.com/gridmatic/tlaloc.git"
  "tlaloc-env|https://gitlab.com/gridmatic/tlaloc-env.git"
)

MISE_CONFIGS=(
  mise.toml .mise.toml
  mise/config.toml .mise/config.toml
  .config/mise.toml .config/mise/config.toml
  .tool-versions
)

STATE_DIR="$HOME/.rdev-bootstrap"
FAILED_FILE="$STATE_DIR/failed"
DONE_FILE="$STATE_DIR/done"

force=0
[[ "${1:-}" == "--force" ]] && force=1

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

rdev_setup_done() {
  local dir="$1" hash
  hash="$(printf '%s' "$dir" | sha256sum | cut -c1-16)"
  [[ -f "$HOME/.rdev-project-state/$hash.postcreate" ]]
}

has_mise_config() {
  local dir="$1" f
  for f in "${MISE_CONFIGS[@]}"; do
    [[ -e "$dir/$f" ]] && return 0
  done
  return 1
}

read_post_create() {
  local dir="$1" f
  for f in rdev.yaml rdev.yml; do
    [[ -f "$dir/$f" ]] || continue
    MISE_YES=1 mise exec yq@latest -- yq '[.postCreate] | flatten | .[] | select(. != null)' "$dir/$f" 2>/dev/null
    return
  done
}

run_hook_script() {
  local dir="$1" script
  script="set -e"$'\n'"cd $(printf '%q' "$dir")"$'\n'"$2"
  bash -c "$script"
}

setup_repo() {
  local name="$1" dir="$2" commands
  if has_mise_config "$dir"; then
    log "$name: mise install"
    ( cd "$dir" && MISE_YES=1 mise trust >/dev/null && mise install ) || {
      log "$name: mise install FAILED"
      return 1
    }
  fi
  commands="$(read_post_create "$dir")"
  if [[ -z "$commands" ]]; then
    log "$name: no rdev.yaml postCreate hooks"
    return 0
  fi
  log "$name: running rdev.yaml postCreate hooks"
  run_hook_script "$dir" "$commands" || {
    log "$name: postCreate hooks FAILED"
    return 1
  }
}

handle_repo() {
  local name="$1" url="$2" dir="$HOME/$1"
  local marker="$STATE_DIR/$name.done"

  if [[ -f "$marker" && $force -eq 0 ]]; then
    log "$name: already bootstrapped, skipping"
    return 0
  fi

  if [[ ! -d "$dir/.git" ]]; then
    log "$name: cloning $url"
    git clone --progress "$url" "$dir" || {
      log "$name: clone FAILED"
      return 1
    }
  elif rdev_setup_done "$dir"; then
    log "$name: already cloned and set up by rdev, skipping"
    : > "$marker"
    return 0
  else
    log "$name: already cloned, running setup"
  fi

  setup_repo "$name" "$dir" || return 1
  : > "$marker"
  log "$name: done"
}

main() {
  mkdir -p "$STATE_DIR"
  : > "$FAILED_FILE"
  rm -f "$DONE_FILE"

  log "rdev bootstrap starting (${#REPOS[@]} repos)"
  local entry name url
  for entry in "${REPOS[@]}"; do
    name="${entry%%|*}"
    url="${entry#*|}"
    handle_repo "$name" "$url" || echo "$name" >> "$FAILED_FILE"
  done

  if [[ -s "$FAILED_FILE" ]]; then
    log "finished with failures: $(tr '\n' ' ' < "$FAILED_FILE")"
    log "these retry on the next login; force everything with: $0 --force"
  else
    log "finished, all repos ready"
    : > "$DONE_FILE"
  fi
  return 0
}

main "$@"
