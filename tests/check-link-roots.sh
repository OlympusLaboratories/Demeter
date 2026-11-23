#!/usr/bin/env bash
# Asserts that every destination install.sh links into falls under a root
# demeter_link_roots declares.
#
# This is the drift guard. The uninstaller sweeps declared roots, so a new
# link_file destination outside all of them is unreachable from the other
# direction — which is the defect this check exists to stop recurring, and the
# one that went unnoticed from September to November.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<EOF
Usage: tests/check-link-roots.sh [rules]

  rules   Print what this check asserts, and exit.
EOF
}

rules() {
  cat <<EOF
check-link-roots asserts, statically over install.sh:

  1. every link_file / link_directory_contents destination resolves to a
     directory under a root demeter_link_roots declares
  2. every shell variable used as a destination's leading component is known
     to this check, so a new one fails rather than being skipped silently
  3. install.sh still assigns those variables what this check resolves them
     to, so the map here cannot go stale behind the installer

It resolves \$home, \$claude_dst, \$dst_dir, \$editor_dir and \$git_ignore_dst
against what install.sh assigns them. A destination built from any other
variable is reported, not assumed safe.
EOF
}

main() {
  if [[ "${1:-}" == "rules" ]]; then
    rules
    exit 0
  fi
  if [[ $# -gt 0 ]]; then
    usage >&2
    exit 2
  fi

  local roots
  roots="$(source "$REPO_DIR/lib/paths.sh"; demeter_link_roots)"

  local recursive_roots
  recursive_roots="$(
    source "$REPO_DIR/lib/paths.sh"
    while IFS= read -r r; do
      if demeter_link_root_is_recursive "$r"; then
        echo "$r"
      fi
    done <<<"$roots"
  )"

  ROOTS="$roots" RECURSIVE_ROOTS="$recursive_roots" HOME="$HOME" \
    python3 "$REPO_DIR/tests/check_link_roots.py" "$REPO_DIR/install.sh"
}

main "$@"
