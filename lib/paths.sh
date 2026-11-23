#!/usr/bin/env bash
# Path families the installer writes into, shared by install.sh and
# uninstall.sh. Sourced, never executed.
#
# Pure, for the reason given in vscode/lib.sh: the output helpers are defined
# per-script, so a lib may not print.

if [[ -n "${__DEMETER_PATHS_LIB:-}" ]]; then
  return 0
fi
__DEMETER_PATHS_LIB=1

# shellcheck source-path=SCRIPTDIR
# shellcheck source=../vscode/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../vscode" && pwd)/lib.sh"

# The file git reads for machine-wide ignores: core.excludesFile when set,
# otherwise git's XDG default, which needs no configuration at all.

git_excludes_path() {
  local configured
  configured="$(git config --global --get core.excludesFile 2>/dev/null || true)"
  if [[ -n "$configured" ]]; then
    configured="${configured/#\~/$HOME}"
    configured="${configured/#\$HOME/$HOME}"
    echo "$configured"
  else
    echo "${XDG_CONFIG_HOME:-$HOME/.config}/git/ignore"
  fi
}

# Every directory install.sh links into, deduplicated, one per line. The
# uninstaller sweeps these rather than guessing at trees, so a link root added
# to the installer and not declared here is unreachable from the other
# direction — which is what tests/check-link-roots.sh exists to catch.
#
# Both platforms' editor directories are emitted, not this machine's: the
# uninstaller does not detect a machine type, and a path that does not exist is
# simply skipped.

demeter_link_roots() {
  {
    echo "$HOME"
    echo "$HOME/.claude"
    echo "$HOME/.config/zsh"
    echo "$HOME/.config"
    dirname "$(git_excludes_path)"
    echo "$HOME/.vscode-server/data/Machine"
    vscode_user_dirs mac
    vscode_user_dirs linux
  } | awk '!seen[$0]++'
}

# ~/.claude holds skills, hooks, scripts and tools as per-item links nested
# several levels down; every other root is linked into flatly.

demeter_link_root_is_recursive() {
  [[ "$1" == "$HOME/.claude" ]]
}
