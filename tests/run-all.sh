#!/usr/bin/env bash
set -uo pipefail

SELF="$(basename "${BASH_SOURCE[0]}")"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

HELPERS=(
  check_link_roots.py
)

usage() {
  printf 'usage: tests/%s [rules|list]\n' "$SELF"
}

cmd_rules() {
  cat <<'RULES'
tests/run-all.sh runs every checker in tests/. It is the single entry point CI
calls, so adding a checker never needs a workflow edit.

What it runs
  every tests/*.py and tests/*.sh, sorted, except run-all.sh itself and the
  declared helpers below. .github/workflows/shell-checks.yml used to list all
  sixteen checkers as their own step, which meant a new checker ran only if
  somebody remembered to add it. Discovery is what removes that.

Declared helpers, which are not run directly
RULES
  local helper
  for helper in "${HELPERS[@]}"; do
    printf '  %s\n' "$helper"
  done
  cat <<'RULES'

  check_link_roots.py is reached from check-link-roots.sh, which passes it
  install.sh as an argument. A file added to tests/ and not declared above is
  run as a checker. Forgetting to declare one is usually loud: a new file is not
  executable, so the precheck names it and says to declare it, and an
  argv-driven helper like check_link_roots.py exits non-zero when run with no
  arguments. What neither catches is an executable library defining only
  functions, which runs, exits 0 and is counted as a checker asserting nothing.
  So declare a helper when you add one; nothing here can infer it.

What it guarantees
  every discovered checker is executable, else the run fails before any of them
  starts; every checker runs even after an earlier one fails, so one red checker
  cannot hide the rest; the exit status is 1 when any failed, and the failures
  are named last.

Output
  one ::group:: fold per checker, then a roster of ok/FAIL with per-checker
  seconds. With GITHUB_STEP_SUMMARY set, the same roster is appended there as a
  markdown table.
RULES
}

is_helper() {
  local name="$1" helper
  for helper in "${HELPERS[@]}"; do
    if [ "$name" = "$helper" ]; then
      return 0
    fi
  done
  return 1
}

discover() {
  local path name
  for path in "$REPO_DIR"/tests/*.py "$REPO_DIR"/tests/*.sh; do
    [ -e "$path" ] || continue
    name="$(basename "$path")"
    [ "$name" = "$SELF" ] && continue
    is_helper "$name" && continue
    printf '%s\n' "$name"
  done | LC_ALL=C sort -u
}

main() {
  case "${1:-}" in
    rules) cmd_rules; return 0 ;;
    list) discover; return 0 ;;
    -h | --help | help) usage; return 0 ;;
    '') ;;
    *) usage >&2; return 2 ;;
  esac

  cd "$REPO_DIR" || return 1

  local names=() name
  while IFS= read -r name; do
    names+=("$name")
  done < <(discover)

  if [ "${#names[@]}" -eq 0 ]; then
    printf 'run-all.sh: no checkers found in %s/tests\n' "$REPO_DIR" >&2
    return 1
  fi

  local not_executable=()
  for name in "${names[@]}"; do
    [ -x "tests/$name" ] || not_executable+=("$name")
  done
  if [ "${#not_executable[@]}" -gt 0 ]; then
    printf 'run-all.sh: not executable, so the suite cannot be trusted:\n' >&2
    for name in "${not_executable[@]}"; do
      printf '  tests/%s\n' "$name" >&2
    done
    printf 'run chmod +x on each, or declare it a helper in tests/run-all.sh\n' >&2
    return 1
  fi

  printf 'running %d checkers from tests/\n\n' "${#names[@]}"

  local states=() seconds=() failed=()
  local started rc elapsed total_started
  total_started=$SECONDS

  for name in "${names[@]}"; do
    printf '::group::%s\n' "$name"
    started=$SECONDS
    "tests/$name"
    rc=$?
    elapsed=$((SECONDS - started))
    printf '::endgroup::\n'
    seconds+=("$elapsed")
    if [ "$rc" -eq 0 ]; then
      states+=("ok")
    else
      states+=("FAIL")
      failed+=("$name")
    fi
  done

  local total=$((SECONDS - total_started))
  local passed=$((${#names[@]} - ${#failed[@]}))
  local i

  printf '\n'
  for i in "${!names[@]}"; do
    printf '  %-4s %4ds  %s\n' "${states[$i]}" "${seconds[$i]}" "${names[$i]}"
  done
  printf '\n  %d of %d passed in %ds\n' "$passed" "${#names[@]}" "$total"

  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    {
      printf '## tests/\n\n'
      printf '%d of %d checkers passed in %ds.\n\n' "$passed" "${#names[@]}" "$total"
      printf '| | checker | time |\n|---|---|---:|\n'
      for i in "${!names[@]}"; do
        if [ "${states[$i]}" = "ok" ]; then
          printf '| ok | `%s` | %ds |\n' "${names[$i]}" "${seconds[$i]}"
        else
          printf '| **FAIL** | `%s` | %ds |\n' "${names[$i]}" "${seconds[$i]}"
        fi
      done
      printf '\n'
    } >>"$GITHUB_STEP_SUMMARY"
  fi

  if [ "${#failed[@]}" -gt 0 ]; then
    printf '\nfailed:\n' >&2
    for name in "${failed[@]}"; do
      printf '  tests/%s\n' "$name" >&2
    done
    return 1
  fi

  printf '\npassed\n'
  return 0
}

main "$@"
