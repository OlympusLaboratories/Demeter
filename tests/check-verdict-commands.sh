#!/usr/bin/env bash
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Every profile that ships the GitHub adapter, discovered rather than named. It
# lives in one profile today because the work profiles ship gitlab-api.sh, which
# is a separate implementation and not its transform -- check-transform.py has
# both in PRESENCE_EXEMPT for that reason. Globbing means a second copy is
# covered the day it appears, and that no copy at all is a failure rather than a
# silent pass. The pi profile's scripts/ is a symlink into home_darwin, so it
# ships the same file and is verified under its own name.
SCRIPTS=()
for candidate in "$REPO"/profiles/*/.claude/scripts/github-api.sh; do
  [[ -e "$candidate" ]] || continue
  SCRIPTS+=("$candidate")
done

REQUIRED=(
  pr-review-list
  dismiss-review
  request-review
  rerun-workflow
)

if [[ "${1:-}" == "rules" ]]; then
  cat <<'RULES'
the subcommands autopilot needs to clear a blocking review verdict:

  pr-review-list   <owner> <repo> <pr_number>
  dismiss-review   <owner> <repo> <pr_number> <review_id> [message]
  request-review   <owner> <repo> <pr_number> <reviewer>
  rerun-workflow   <owner> <repo> <run_id>

checked for each one:

  it is registered in COMMANDS, so `help` lists it
  `help` prints its argument list, which is parsed out of its own Usage line
  it exits non-zero on too few arguments, rather than calling the API
  it needs no token to fail that way, so this test runs unauthenticated

Why they have to exist. A run that cannot clear a stale verdict stops and asks a
human to press a button, which is the one outcome an unattended run must never
produce. pr-review-list is separate from pr-reviews because a reviewer can block
with an empty-bodied review and pr-reviews drops those by design -- leaving the
block visible only as review_decision on the status call.
RULES
  exit 0
fi

failures=0
checked=0

if ((${#SCRIPTS[@]} == 0)); then
  echo "  fail — no profile ships .claude/scripts/github-api.sh"
  exit 1
fi

for script in "${SCRIPTS[@]}"; do
  profile="$(basename "$(dirname "$(dirname "$(dirname "$script")")")")"

  checked=$((checked + 1))
  if [[ ! -x "$script" ]]; then
    printf '  fail — %s: github-api.sh is not executable\n' "$profile"
    failures=$((failures + 1))
    continue
  fi

  help_out="$("$script" help 2>/dev/null)"

  for name in "${REQUIRED[@]}"; do
    checked=$((checked + 1))
    if ! grep -qE "^${name}[[:space:]]" <<<"$help_out"; then
      printf '  fail — %s: help does not list %s\n' "$profile" "$name"
      failures=$((failures + 1))
      continue
    fi

    checked=$((checked + 1))
    if ! grep -qE "^${name}[[:space:]]+<owner> <repo>" <<<"$help_out"; then
      printf '  fail — %s: %s has no argument list in help (Usage line missing or malformed)\n' \
        "$profile" "$name"
      failures=$((failures + 1))
    fi

    checked=$((checked + 1))
    if GITHUB_PERSONAL_ACCESS_TOKEN="" "$script" "$name" >/dev/null 2>&1; then
      printf '  fail — %s: %s exited 0 with no arguments\n' "$profile" "$name"
      failures=$((failures + 1))
    fi
  done
done

echo "verdict-clearing subcommands"
echo
if ((failures)); then
  echo "failed ($failures of $checked checks)"
  exit 1
fi
printf '  ok   — %d checks over %d subcommands in %d profile(s)\n\n' \
  "$checked" "${#REQUIRED[@]}" "${#SCRIPTS[@]}"
echo "passed"
