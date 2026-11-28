#!/usr/bin/env bash
set -uo pipefail

OWNER="${OWNER:-}"
REPO="${REPO:-}"
PR="${PR:-}"
SLEEP="${SLEEP:-60}"
CHECKLIST="${CHECKLIST:-}"
STAGE="${STAGE:-}"
RUN_CHECKLIST="${RUN_CHECKLIST:-$HOME/.claude/scripts/run-checklist.py}"
MAX_POLLS="${MAX_POLLS:-0}"
MAX_ERRORS="${MAX_ERRORS:-3}"

usage() {
  cat >&2 <<'EOF'
Usage: watch.sh <owner> <repo> <pr-number>
   or: OWNER=<owner> REPO=<repo> PR=<number> watch.sh

  SLEEP        seconds between polls (default 60)
  MAX_POLLS    stop after this many polls; 0 means until a terminal state (default 0)
  MAX_ERRORS   consecutive failed polls before giving up (default 3)
  CHECKLIST    an items.json; every poll syncs its forge-observable items
               (open, pipeline, threads, merge) from what this poll saw, so the
               published page tracks the change request with nobody ticking it
  STAGE        which stack member on that page these facts belong to; one
               watcher runs per change request, so a stacked run needs it or
               every member writes onto the same items
  RUN_CHECKLIST  path to run-checklist.py (default ~/.claude/scripts/run-checklist.py)

Smoke test before arming a Monitor:
  MAX_POLLS=1 SLEEP=0 watch.sh <owner> <repo> <pr-number>
EOF
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --checklist)
      [[ $# -ge 2 && -n "${2:-}" ]] || { echo "POLL ERROR --checklist needs a path" >&2; exit 2; }
      CHECKLIST="$2"
      shift 2
      ;;
    --checklist=*)
      CHECKLIST="${1#*=}"
      [[ -n "$CHECKLIST" ]] || { echo "POLL ERROR --checklist needs a path" >&2; exit 2; }
      shift
      ;;
    --stage)
      [[ $# -ge 2 && -n "${2:-}" ]] || { echo "POLL ERROR --stage needs an id" >&2; exit 2; }
      STAGE="$2"
      shift 2
      ;;
    --stage=*)
      STAGE="${1#*=}"
      [[ -n "$STAGE" ]] || { echo "POLL ERROR --stage needs an id" >&2; exit 2; }
      shift
      ;;
    *) break ;;
  esac
done

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

QUERY='query($owner:String!,$repo:String!,$number:Int!){repository(owner:$owner,name:$repo){pullRequest(number:$number){state merged reviewDecision body reviewThreads(first:100){nodes{isResolved}} commits(last:1){nodes{commit{oid statusCheckRollup{contexts(first:100){nodes{__typename ... on CheckRun{name status conclusion} ... on StatusContext{context state}}}}}}}}}}'

JQ='.data.repository.pullRequest as $pr
| (["PR", ($pr.state // ""), ($pr.merged | tostring), ($pr.reviewDecision // "NONE"),
    ([$pr.reviewThreads.nodes[] | select(.isResolved == false)] | length | tostring),
    ($pr.commits.nodes[0].commit.oid[0:7] // "unknown"),
    (($pr.body // "") | @base64)] | join("\u001f")),
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
HEAD_KEY=""
polls=0
errors=0

say() {
  printf '%s\n' "$1"
}

sync_checklist() {
  [[ -n "$CHECKLIST" ]] || return 0
  local out body_file=""
  if [[ -n "${8:-}" ]]; then
    body_file="$(mktemp)"
    printf '%s' "$8" | base64 -d > "$body_file" 2>/dev/null || : > "$body_file"
  fi
  if ! out="$("$RUN_CHECKLIST" reconcile "$CHECKLIST" \
      ${STAGE:+--stage "$STAGE"} \
      --state "$1" --merged "$2" --review "$3" --unresolved "$4" \
      --checks-pending "$5" --checks-failed "$6" --checks-total "$7" \
      ${body_file:+--body-file "$body_file"} \
      --publish 2>&1)"; then
    [[ -n "$body_file" ]] && rm -f "$body_file"
    say_once "CHECKLIST ERROR $(printf '%s' "$out" | tr '\n' ' ' | cut -c1-200)"
    return 0
  fi
  [[ -n "$body_file" ]] && rm -f "$body_file"
  case "$out" in
    unchanged:*) return 0 ;;
    *) say "CHECKLIST $(printf '%s' "$out" | head -1 | cut -c1-200)" ;;
  esac
}

say_once() {
  local key="$HEAD_KEY|$1"
  [[ -n "${SAID[$key]:-}" ]] && return 0
  SAID[$key]=1
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
  local state merged decision unresolved head body64
  IFS=$'\037' read -r _ state merged decision unresolved head body64 <<<"$(head -1 <<<"$raw")"

  if [[ -z "$state" || -z "$merged" ]]; then
    say "POLL ERROR the response carried no pull-request state, so $OWNER/$REPO#$PR may not exist"
    return 1
  fi

  HEAD_KEY="$head"

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
    sync_checklist "$state" "$merged" "$decision" "${unresolved:-0}" "$pending" "${#failed[@]}" "$checks" "${body64:-}"
    say "TERMINAL merged"
    return 0
  fi
  if [[ "$state" == "CLOSED" ]]; then
    sync_checklist "$state" "$merged" "$decision" "${unresolved:-0}" "$pending" "${#failed[@]}" "$checks" "${body64:-}"
    say "TERMINAL closed without merging"
    return 0
  fi
  if [[ $checks -eq 0 ]]; then
    sync_checklist "$state" "$merged" "$decision" "${unresolved:-0}" "$pending" "${#failed[@]}" "$checks" "${body64:-}"
    say_once "CHECKS none reported yet"
    return 2
  fi
  if [[ $pending -gt 0 ]]; then
    sync_checklist "$state" "$merged" "$decision" "${unresolved:-0}" "$pending" "${#failed[@]}" "$checks" "${body64:-}"
    say_once "WAITING $pending of $checks check(s) still running"
    return 2
  fi
  sync_checklist "$state" "$merged" "$decision" "${unresolved:-0}" "$pending" "${#failed[@]}" "$checks" "${body64:-}"

  if [[ ${#failed[@]} -gt 0 ]]; then
    say_once "CHECKS finished with failures: ${failed[*]}"
  else
    say_once "CHECKS all $checks check(s) complete and green"
  fi
  return 2
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
