#!/usr/bin/env bash
# Editor path and CLI resolution, shared by install.sh, uninstall.sh and
# sync-extensions.sh. Sourced, never executed.
#
# Every function here is pure: none prints through info/warn/success/error/bold
# and none calls ask. Those helpers are defined separately in each sourcing
# script, so a lib that reached for one would work in some callers and break in
# others.

if [[ -n "${__DEMETER_VSCODE_LIB:-}" ]]; then
  return 0
fi
__DEMETER_VSCODE_LIB=1

# Editor user-settings directories, most-preferred first. Only ones that already
# exist get linked: the directory is created on an editor's first launch, and a
# dev box driven over Remote-SSH keeps its UI settings on the client machine.

vscode_user_dirs() {
  local machine="$1"
  if [[ "$machine" == "mac" ]]; then
    printf '%s\n' \
      "$HOME/Library/Application Support/Code/User" \
      "$HOME/Library/Application Support/Code - Insiders/User" \
      "$HOME/Library/Application Support/VSCodium/User"
  else
    printf '%s\n' \
      "$HOME/.config/Code/User" \
      "$HOME/.config/Code - Insiders/User" \
      "$HOME/.config/VSCodium/User"
  fi
}

# PATH first, then the macOS app bundle — present even when the user never ran
# "Shell Command: Install 'code' command in PATH" — then the CLIs a Remote-SSH
# box unpacks under ~/.vscode-server, which are never on PATH outside the
# integrated terminal. Newest first within each layout.
editor_cli_candidates() {
  command -v code 2>/dev/null || true
  command -v codium 2>/dev/null || true
  local bundle="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
  [[ -x "$bundle" ]] && echo "$bundle"
  local candidate found=()
  for candidate in \
    "$HOME"/.vscode-server/cli/servers/*/server/bin/code-server \
    "$HOME"/.vscode-server/bin/*/bin/code-server \
    "$HOME"/.vscode-server/bin/*/bin/remote-cli/code \
    "$HOME"/.vscode-server-insiders/cli/servers/*/server/bin/code-server; do
    [[ -x "$candidate" ]] && found+=("$candidate")
  done
  [[ "${#found[@]}" -gt 0 ]] && ls -t -- "${found[@]}"
  return 0
}

EDITOR_CLI_CACHE="${EDITOR_CLI_CACHE:-}"

editor_cli() {
  if [[ -n "$EDITOR_CLI_CACHE" ]]; then
    echo "$EDITOR_CLI_CACHE"
    return 0
  fi
  local candidate
  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    if "$candidate" --list-extensions >/dev/null 2>&1; then
      EDITOR_CLI_CACHE="$candidate"
      echo "$candidate"
      return 0
    fi
  done < <(editor_cli_candidates)
  return 1
}

editor_cli_available() {
  editor_cli >/dev/null 2>&1
}

tool_extension_id() {
  local pkg="$1/package.json"
  [[ -f "$pkg" ]] || return 1
  python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
pub, name = d.get('publisher'), d.get('name')
if not (pub and name):
    sys.exit(1)
print(f'{pub}.{name}'.lower())
" "$pkg" 2>/dev/null
}

editor_has_extension() {
  local id="$1" editor_bin
  editor_bin="$(editor_cli)" || return 1
  "$editor_bin" --list-extensions 2>/dev/null | tr '[:upper:]' '[:lower:]' | grep -qxF "$id"
}

# One extension id per line; `#` comments and blank lines are ignored.
read_extension_list() {
  local list_file="$1"
  [[ -f "$list_file" ]] || return 0
  sed -e 's/#.*//' -e 's/[[:space:]]//g' "$list_file" | grep -v '^$' || true
}
