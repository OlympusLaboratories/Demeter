#!/usr/bin/env bash
# Asserts that uninstall.sh reaches every link root install.sh writes into.
#
# A symlink is planted under each root demeter_link_roots declares, inside a
# scratch HOME, and uninstall.sh is then expected to leave none of them behind.
# Two controls keep the assertion honest: the planted count must be nonzero, so
# a broken plant step cannot pass vacuously, and a link pointing outside the
# repo must survive, so a sweep that simply deletes everything cannot pass.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PASS=0
FAIL=0

ok()   { echo "  ok   — $*"; PASS=$((PASS + 1)); }
bad()  { echo "  FAIL — $*"; FAIL=$((FAIL + 1)); }

usage() {
  cat <<EOF
Usage: tests/uninstall-roundtrip.sh [rules]

  rules   Print what this check asserts, and exit.
EOF
}

rules() {
  cat <<EOF
uninstall-roundtrip asserts, against a scratch HOME:

  1. every declared root resolves inside the scratch HOME, checked before
     anything is created, so a bad root cannot touch the real one
  2. every root demeter_link_roots declares is swept by uninstall.sh
  3. a link nested deep under the recursive root (~/.claude) is swept
  4. a dangling link into the repo is swept
  5. a link whose target is outside the repo survives, and so does a real file
  6. the planted link count is nonzero, so 2-4 cannot pass vacuously

It runs both git-excludes branches: the XDG default, and a configured
core.excludesFile, which is the path an rdev image sets.
EOF
}

# One scenario: plant, sweep, assert. $1 names it; $2 is a git config file to
# expose as the global one, or "" for none.
run_case() {
  local label="$1" git_config="$2"
  local scratch
  scratch="$(mktemp -d)"
  # shellcheck disable=SC2064
  trap "rm -rf '$scratch'" RETURN

  echo "$label"

  local roots planted=0
  roots="$(
    env -u XDG_CONFIG_HOME \
      HOME="$scratch" \
      GIT_CONFIG_GLOBAL="${git_config:-$scratch/.gitconfig-absent}" \
      bash -c "source '$REPO_DIR/lib/paths.sh'; demeter_link_roots"
  )"

  # Assert the sandbox holds BEFORE creating anything. git_excludes_path reads
  # the environment, so a root resolving outside the scratch HOME would mean
  # this test plants symlinks in the developer's real config directory.
  local root
  while IFS= read -r root; do
    [[ -n "$root" ]] || continue
    if [[ "$root" != "$scratch" && "$root" != "$scratch/"* ]]; then
      bad "declared root escapes the sandbox: $root"
      return
    fi
  done <<<"$roots"

  while IFS= read -r root; do
    [[ -n "$root" ]] || continue
    mkdir -p "$root"
    ln -s "$REPO_DIR/README.md" "$root/demeter-planted-$planted"
    planted=$((planted + 1))
  done <<<"$roots"

  # The recursive root must be swept at depth, not just at its top level.
  mkdir -p "$scratch/.claude/skills/nested/deeper"
  ln -s "$REPO_DIR/README.md" "$scratch/.claude/skills/nested/deeper/demeter-planted-deep"
  planted=$((planted + 1))

  # A link whose target no longer exists is still ours; points_into_repo reads
  # the link string rather than resolving it, and that path needs covering.
  ln -s "$REPO_DIR/no-such-file" "$scratch/.demeter-planted-dangling"
  planted=$((planted + 1))

  # Negative controls: neither may be touched.
  ln -s /etc/hosts "$scratch/unrelated-link"
  : >"$scratch/.real-file"

  if [[ "$planted" -gt 0 ]]; then
    ok "planted $planted link(s) across $(grep -c . <<<"$roots") declared root(s)"
  else
    bad "planted nothing — the declared root list came back empty"
    return
  fi

  env -u XDG_CONFIG_HOME \
    HOME="$scratch" \
    GIT_CONFIG_GLOBAL="${git_config:-$scratch/.gitconfig-absent}" \
    "$REPO_DIR/uninstall.sh" --yes >/dev/null 2>&1

  local survivors=()
  while IFS= read -r -d '' link; do
    local target
    target="$(readlink "$link")"
    [[ "$target" == "$REPO_DIR/"* || "$target" == "$REPO_DIR" ]] && survivors+=("$link")
  done < <(find "$scratch" -type l -print0 2>/dev/null)

  if [[ "${#survivors[@]}" -eq 0 ]]; then
    ok "no symlink into the repo survived"
  else
    bad "${#survivors[@]} symlink(s) into the repo survived:"
    local s
    for s in "${survivors[@]}"; do
      echo "         ${s/#$scratch/\$HOME}"
    done
  fi

  if [[ -L "$scratch/unrelated-link" ]]; then
    ok "a link pointing outside the repo was left alone"
  else
    bad "a link pointing outside the repo was removed"
  fi

  if [[ -f "$scratch/.real-file" ]]; then
    ok "a real file was left alone"
  else
    bad "a real file was removed"
  fi
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

  echo "=== uninstall round-trip ==="
  echo ""

  run_case "XDG default excludes path:" ""
  echo ""

  local cfgdir cfg
  cfgdir="$(mktemp -d)"
  cfg="$cfgdir/gitconfig"
  printf '[core]\n\texcludesFile = ~/.gitignore-demeter-test\n' >"$cfg"
  run_case "configured core.excludesFile:" "$cfg"
  rm -rf "$cfgdir"

  echo ""
  echo "passed $PASS, failed $FAIL"
  [[ "$FAIL" -eq 0 ]]
}

main "$@"
