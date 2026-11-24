#!/usr/bin/env bash
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO/profiles/larrabeedylan_home_darwin/.claude/scripts/github-api.sh"

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

if [[ ! -x "$SCRIPT" ]]; then
  echo "  fail — $SCRIPT is not executable"
  exit 1
fi

help_out="$("$SCRIPT" help 2>/dev/null)"

for name in "${REQUIRED[@]}"; do
  checked=$((checked + 1))
  if ! grep -qE "^${name}[[:space:]]" <<<"$help_out"; then
    printf '  fail — help does not list %s\n' "$name"
    failures=$((failures + 1))
    continue
  fi

  checked=$((checked + 1))
  if ! grep -qE "^${name}[[:space:]]+<owner> <repo>" <<<"$help_out"; then
    printf '  fail — %s has no argument list in help (its Usage line is missing or malformed)\n' "$name"
    failures=$((failures + 1))
  fi

  checked=$((checked + 1))
  GITHUB_PERSONAL_ACCESS_TOKEN="" "$SCRIPT" "$name" >/dev/null 2>&1
  if [[ $? -eq 0 ]]; then
    printf '  fail — %s exited 0 with no arguments\n' "$name"
    failures=$((failures + 1))
  fi
done

echo "verdict-clearing subcommands"
echo
if ((failures)); then
  echo "failed ($failures of $checked checks)"
  exit 1
fi
printf '  ok   — %d checks over %d subcommands\n\n' "$checked" "${#REQUIRED[@]}"
echo "passed"
