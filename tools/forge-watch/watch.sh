#!/usr/bin/env bash
set -uo pipefail

OWNER="${OWNER:-}"
REPO="${REPO:-}"
PR="${PR:-}"
SLEEP="${SLEEP:-60}"
MAX_POLLS="${MAX_POLLS:-0}"
MAX_ERRORS="${MAX_ERRORS:-3}"

usage() {
  cat >&2 <<'EOF'
Usage: watch.sh <owner> <repo> <pr-number>
   or: OWNER=<owner> REPO=<repo> PR=<number> watch.sh

  SLEEP        seconds between polls (default 60)
  MAX_POLLS    stop after this many polls; 0 means until a terminal state (default 0)
  MAX_ERRORS   consecutive failed polls before giving up (default 3)

Smoke test before arming a Monitor:
  MAX_POLLS=1 SLEEP=0 watch.sh <owner> <repo> <pr-number>
EOF
  exit 2
}

if [[ $# -eq 3 ]]; then
  OWNER="$1"
  REPO="$2"
  PR="$3"
elif [[ $# -ne 0 ]]; then
  usage
fi
[[ -n "$OWNER" && -n "$REPO" && -n "$PR" ]] || usage
[[ "$PR" =~ ^[0-9]+$ ]] || { echo "POLL ERROR pr-number must be numeric, got '$PR'"; exit 2; }

if ! command -v gh >/dev/null 2>&1; then
  echo "TERMINAL gh is not installed, so this watch cannot see anything"
  exit 1
fi

QUERY='query($owner:String!,$repo:String!,$number:Int!){repository(owner:$owner,name:$repo){pullRequest(number:$number){state merged reviewDecision reviewThreads(first:100){nodes{isResolved}} commits(last:1){nodes{commit{oid statusCheckRollup{contexts(first:100){nodes{__typename ... on CheckRun{name status conclusion} ... on StatusContext{context state}}}}}}}}}}'

JQ='.data.repository.pullRequest as $pr
| (["PR", ($pr.state // ""), ($pr.merged | tostring), ($pr.reviewDecision // "NONE"),
    ([$pr.reviewThreads.nodes[] | select(.isResolved == false)] | length | tostring),
    ($pr.commits.nodes[0].commit.oid[0:7] // "unknown")] | join("\u001f")),
  (($pr.commits.nodes[0].commit.statusCheckRollup.contexts.nodes // [])[]
   | if .__typename == "CheckRun"
     then ["CHECK", .name, .status, (.conclusion // "")]
     else ["CHECK", .context,
           (if .state == "PENDING" or .state == "EXPECTED"
            then "IN_PROGRESS" else "COMPLETED" end),
           (.state // "")]
     end
   | join("\u001f"))'

declare -A SAID=()
polls=0
errors=0

say() {
  printf '%s\n' "$1"
}

say_once() {
  [[ -n "${SAID[$1]:-}" ]] && return 0
  SAID[$1]=1
  say "$1"
}

still_running() {
  [[ "$1" != COMPLETED ]]
}

benign_conclusion() {
  case "$1" in
    SUCCESS|NEUTRAL|SKIPPED) return 0 ;;
    *) return 1 ;;
  esac
}

poll() {
  local raw stderr_file status
  stderr_file="$(mktemp)"
  raw="$(gh api graphql \
    -f query="$QUERY" \
    -F owner="$OWNER" -F repo="$REPO" -F number="$PR" \
    --jq "$JQ" 2>"$stderr_file")"
  status=$?
  if [[ $status -ne 0 ]]; then
    say "POLL ERROR gh exit=$status $(tr '\n' ' ' < "$stderr_file" | cut -c1-200)"
    rm -f "$stderr_file"
    return 1
  fi
  rm -f "$stderr_file"
  if [[ -z "$raw" ]]; then
    say "POLL ERROR gh returned no bytes, which is not an empty result"
    return 1
  fi

  local pending=0 failed=() checks=0
  local state merged decision unresolved head
  IFS=$'\037' read -r _ state merged decision unresolved head <<<"$(head -1 <<<"$raw")"

  if [[ -z "$state" || -z "$merged" ]]; then
    say "POLL ERROR the response carried no pull-request state, so $OWNER/$REPO#$PR may not exist"
    return 1
  fi

  say_once "STATUS state=$state merged=$merged review=$decision head=$head"
  [[ "$decision" != "NONE" ]] && say_once "REVIEW decision=$decision"
  [[ "${unresolved:-0}" != "0" ]] && say_once "THREADS unresolved=$unresolved"

  while IFS=$'\037' read -r kind a b c; do
    [[ "$kind" == "CHECK" ]] || continue
    checks=$((checks + 1))
    if still_running "$b"; then
      pending=$((pending + 1))
    else
      say_once "CHECK $a ${c:-NO_CONCLUSION}"
      benign_conclusion "$c" || failed+=("$a (${c:-NO_CONCLUSION})")
    fi
  done <<<"$raw"

  if [[ "$merged" == "true" ]]; then
    say "TERMINAL merged"
    return 0
  fi
  if [[ "$state" == "CLOSED" ]]; then
    say "TERMINAL closed without merging"
    return 0
  fi
  if [[ $checks -eq 0 ]]; then
    say_once "CHECKS none reported yet"
    return 2
  fi
  if [[ $pending -gt 0 ]]; then
    say_once "WAITING $pending of $checks check(s) still running"
    return 2
  fi
  if [[ ${#failed[@]} -gt 0 ]]; then
    say "TERMINAL checks finished with failures: ${failed[*]}"
  else
    say "TERMINAL all $checks check(s) complete and green"
  fi
  return 0
}

while :; do
  polls=$((polls + 1))
  poll
  case $? in
    0) exit 0 ;;
    1) errors=$((errors + 1)) ;;
    *) errors=0 ;;
  esac
  if [[ $errors -ge $MAX_ERRORS ]]; then
    say "TERMINAL $errors consecutive failed polls, so this watch cannot see — giving up"
    exit 1
  fi
  if [[ $MAX_POLLS -gt 0 && $polls -ge $MAX_POLLS ]]; then
    say "TERMINAL poll budget reached after $polls poll(s)"
    exit 0
  fi
  sleep "$SLEEP"
done
