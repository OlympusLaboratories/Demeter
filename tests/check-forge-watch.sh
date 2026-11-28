#!/usr/bin/env bash
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WATCH="$REPO/tools/forge-watch/watch.sh"

if [[ "${1:-}" == rules ]]; then
  cat <<'EOF'
forge-watch's terminal-state classification

  a check is still running only while its status is not COMPLETED
      so a conclusion GitHub adds later cannot read as "still running"
  a conclusion outside SUCCESS, NEUTRAL and SKIPPED is a failure
      so a conclusion GitHub adds later cannot read as green either
  STARTUP_FAILURE is settled and is a failure
  a status of EXPECTED is still running, not complete
  a merged pull request is terminal immediately
  a closed one is terminal and syncs the checklist on its way out
  checks settling is reported, never terminal, while the request is still open
  the same conclusion on a new head is reported again
  a failed poll emits POLL ERROR carrying stderr, and MAX_ERRORS in a row exits 1

Why this test exists. OLY-35 was a watcher that could not recognise the state it
was in, so it watched a finished pull request forever. The first version of this
tool reproduced it: `terminal_conclusion` enumerated the states it knew, and
GitHub's CheckConclusionState already carried one it did not -- STARTUP_FAILURE --
which would have been counted as pending on every poll. Enumerating the open set
is the bug. Both predicates now enumerate the *benign* set, which is closed, and
treat everything else as terminal and failed: a watch that stops early and says so
is recoverable, and one that never stops is the defect being fixed.

Why green is not terminal. OLY-260 was the other half of the same mistake: the
watch exited the moment every check went green, while the pull request was still
open and unmerged. Green on an open request is the normal mid-run condition of a
request waiting on a review verdict or another push — and a review round is
*expected* to push again, so `green -> push -> green` is the designed happy path
and the watch was guaranteed to have exited before the second push. Nothing
re-armed it. Only the request's own end states end the watch now; the `Monitor`
tool makes every line an event, so reporting green costs nothing and exiting on
it cost the whole run.

That made the dedup map outlive a commit for the first time, which is the second
assertion here: `say_once` keys on the head, so the same conclusion on a new head
is reported again. Keyed on the text alone, a check that failed, was fixed and
failed again would have been silent -- a live watch reporting nothing, which is
the one failure this tool exists to prevent.

The stub replaces `gh` on PATH and prints the unit-separated lines the real
`gh api graphql --jq` would produce, so the classification is tested without a
network call or a token. With `STUB_OUT2` it answers differently from the second
poll on, which is how a push mid-watch is simulated.
EOF
  exit 0
fi

PASS=0
FAIL=0
STUB_DIR="$(mktemp -d)"
trap 'rm -rf "$STUB_DIR"' EXIT

cat >"$STUB_DIR/gh" <<'STUB'
#!/usr/bin/env bash
if [[ -n "${STUB_FAIL:-}" ]]; then
  echo "gh: stubbed failure" >&2
  exit 1
fi
if [[ -n "${STUB_OUT2:-}" && -n "${STUB_COUNT:-}" ]]; then
  n=0
  [[ -f "$STUB_COUNT" ]] && n="$(cat "$STUB_COUNT")"
  n=$((n + 1))
  printf '%s' "$n" > "$STUB_COUNT"
  if [[ $n -ge 2 ]]; then
    printf '%s\n' "$STUB_OUT2"
    exit 0
  fi
fi
printf '%s\n' "$STUB_OUT"
STUB
chmod +x "$STUB_DIR/gh"

cat >"$STUB_DIR/failing-checklist" <<'STUB'
#!/usr/bin/env bash
echo "stubbed checklist failure" >&2
exit 1
STUB
chmod +x "$STUB_DIR/failing-checklist"

run() {
  STUB_OUT="$1" MAX_POLLS="${2:-1}" SLEEP=0 \
    PATH="$STUB_DIR:$PATH" "$WATCH" acme repo 7 2>&1
}

run_twice() {
  rm -f "$STUB_DIR/count"
  STUB_OUT="$1" STUB_OUT2="$2" STUB_COUNT="$STUB_DIR/count" MAX_POLLS=2 SLEEP=0 \
    PATH="$STUB_DIR:$PATH" "$WATCH" acme repo 7 2>&1
}

check() {
  local label="$1" output="$2" expected="$3"
  if grep -qF -- "$expected" <<<"$output"; then
    printf '  ok   — %s\n' "$label"
    PASS=$((PASS + 1))
  else
    printf '  fail — %s\n' "$label"
    printf '         wanted: %s\n' "$expected"
    printf '         got:    %s\n' "$(tr '\n' '|' <<<"$output")"
    FAIL=$((FAIL + 1))
  fi
}

refute() {
  local label="$1" output="$2" forbidden="$3"
  if grep -qF -- "$forbidden" <<<"$output"; then
    printf '  fail — %s\n' "$label"
    printf '         must not say: %s\n' "$forbidden"
    FAIL=$((FAIL + 1))
  else
    printf '  ok   — %s\n' "$label"
    PASS=$((PASS + 1))
  fi
}

PR_OPEN=$'PR\037OPEN\037false\037NONE\0370\037abc1234'
PR_PUSHED=$'PR\037OPEN\037false\037NONE\0370\037def5678'
PR_MERGED=$'PR\037MERGED\037true\037APPROVED\0370\037abc1234'
PR_CLOSED=$'PR\037CLOSED\037false\037NONE\0370\037abc1234'

echo "forge-watch terminal-state classification"
echo

out="$(run "$PR_OPEN"$'\nCHECK\037build\037COMPLETED\037STARTUP_FAILURE')"
check "STARTUP_FAILURE is settled" "$out" "CHECK build STARTUP_FAILURE"
check "STARTUP_FAILURE is a failure" "$out" "CHECKS finished with failures"
refute "STARTUP_FAILURE is not pending" "$out" "still running"

out="$(run "$PR_OPEN"$'\nCHECK\037build\037COMPLETED\037SOME_FUTURE_STATE')"
check "an unknown conclusion is settled and failed" "$out" "CHECKS finished with failures"
refute "an unknown conclusion never reads as green" "$out" "complete and green"

out="$(run "$PR_OPEN"$'\nCHECK\037a\037COMPLETED\037SUCCESS\nCHECK\037b\037COMPLETED\037NEUTRAL\nCHECK\037c\037COMPLETED\037SKIPPED')"
check "SUCCESS, NEUTRAL and SKIPPED are green" "$out" "CHECKS all 3 check(s) complete and green"
refute "green on an open request is not terminal" "$out" "TERMINAL all"
check "green keeps the watch open to the poll budget" "$out" "poll budget reached after 1 poll(s)"

out="$(run "$PR_OPEN"$'\nCHECK\037a\037COMPLETED\037SUCCESS' 3)"
check "green is still polled after it is reported" "$out" "poll budget reached after 3 poll(s)"
[[ "$(grep -c 'complete and green' <<<"$out")" == "1" ]] \
  && { printf '  ok   — a green that has not changed is said once\n'; PASS=$((PASS + 1)); } \
  || { printf '  fail — a green that has not changed is said once\n'; FAIL=$((FAIL + 1)); }

out="$(run "$PR_OPEN"$'\nCHECK\037a\037COMPLETED\037FAILURE' 2)"
refute "a settled failure on an open request is not terminal either" "$out" "TERMINAL checks"
check "a settled failure keeps the watch open" "$out" "poll budget reached after 2 poll(s)"

out="$(run_twice "$PR_OPEN"$'\nCHECK\037build\037COMPLETED\037FAILURE' \
                 "$PR_PUSHED"$'\nCHECK\037build\037COMPLETED\037FAILURE')"
check "a new head is reported" "$out" "head=def5678"
[[ "$(grep -c 'CHECK build FAILURE' <<<"$out")" == "2" ]] \
  && { printf '  ok   — the same conclusion on a new head is reported again\n'; PASS=$((PASS + 1)); } \
  || { printf '  fail — the same conclusion on a new head is reported again\n'
       printf '         got:    %s\n' "$(tr '\n' '|' <<<"$out")"; FAIL=$((FAIL + 1)); }

out="$(run "$PR_OPEN"$'\nCHECK\037build\037IN_PROGRESS\037')"
check "an unfinished check keeps the watch open" "$out" "WAITING 1 of 1 check(s) still running"
refute "an unfinished check is not terminal" "$out" "TERMINAL all"

out="$(run "$PR_OPEN"$'\nCHECK\037legacy\037IN_PROGRESS\037EXPECTED')"
check "a status of EXPECTED is still running" "$out" "WAITING 1 of 1 check(s) still running"

out="$(run "$PR_OPEN"$'\nCHECK\037a\037COMPLETED\037SUCCESS\nCHECK\037b\037COMPLETED\037FAILURE')"
check "one failure among greens still fails" "$out" "CHECKS finished with failures: b (FAILURE)"

out="$(run "$PR_MERGED"$'\nCHECK\037a\037COMPLETED\037SUCCESS')"
check "a merged pull request is terminal" "$out" "TERMINAL merged"

out="$(run "$PR_OPEN")"
check "no checks yet is reported, not assumed green" "$out" "CHECKS none reported yet"
refute "no checks yet is not green" "$out" "complete and green"

out="$(STUB_FAIL=1 MAX_POLLS=9 SLEEP=0 PATH="$STUB_DIR:$PATH" "$WATCH" acme repo 7 2>&1)"
check "a failed poll emits with stderr" "$out" "POLL ERROR gh exit=1 gh: stubbed failure"
check "repeated failures give up" "$out" "consecutive failed polls"

out="$(run $'PR\037\037\037NONE\0370\037' )"
check "a response with no state is a failed poll" "$out" "POLL ERROR the response carried no pull-request state"

out="$(MAX_POLLS=1 SLEEP=0 PATH="$STUB_DIR:$PATH" timeout 10 "$WATCH" --checklist 2>&1)"
check "a value-less --checklist is refused" "$out" "POLL ERROR --checklist needs a path"
refute "and does not fall through to the watch" "$out" "STATUS"

out="$(MAX_POLLS=1 SLEEP=0 PATH="$STUB_DIR:$PATH" timeout 10 "$WATCH" --checklist= acme repo 7 2>&1)"
check "an empty --checklist= is refused" "$out" "POLL ERROR --checklist needs a path"

out="$(MAX_POLLS=1 SLEEP=0 PATH="$STUB_DIR:$PATH" timeout 10 "$WATCH" --stage 2>&1)"
check "a value-less --stage is refused" "$out" "POLL ERROR --stage needs an id"
refute "and does not fall through to the watch" "$out" "STATUS"

out="$(MAX_POLLS=1 SLEEP=0 PATH="$STUB_DIR:$PATH" timeout 10 "$WATCH" --stage= acme repo 7 2>&1)"
check "an empty --stage= is refused" "$out" "POLL ERROR --stage needs an id"

cat >"$STUB_DIR/echo-checklist" <<'ECHOCL'
#!/usr/bin/env bash
printf 'saw %s\n' "$*"
ECHOCL
chmod +x "$STUB_DIR/echo-checklist"

out="$(STUB_OUT="$PR_OPEN" MAX_POLLS=1 SLEEP=0 \
  RUN_CHECKLIST="$STUB_DIR/echo-checklist" \
  PATH="$STUB_DIR:$PATH" timeout 10 "$WATCH" --checklist /dev/null --stage 2 acme repo 7 2>&1)"
check "--stage reaches the reconcile call" "$out" "--stage 2"

out="$(STUB_OUT="$PR_OPEN" MAX_POLLS=1 SLEEP=0 \
  RUN_CHECKLIST="$STUB_DIR/echo-checklist" \
  PATH="$STUB_DIR:$PATH" timeout 10 "$WATCH" --checklist /dev/null acme repo 7 2>&1)"
refute "no --stage sends no stage at all" "$out" "--stage"

out="$(STUB_OUT="$PR_CLOSED" MAX_POLLS=1 SLEEP=0 \
  RUN_CHECKLIST="$STUB_DIR/echo-checklist" \
  PATH="$STUB_DIR:$PATH" timeout 10 "$WATCH" --checklist /dev/null acme repo 7 2>&1)"
check "a closed request is terminal" "$out" "TERMINAL closed without merging"
check "and syncs the checklist on the way out" "$out" "--state CLOSED"

out="$(STUB_OUT="$PR_MERGED" MAX_POLLS=1 SLEEP=0 \
  RUN_CHECKLIST="$STUB_DIR/echo-checklist" \
  PATH="$STUB_DIR:$PATH" timeout 10 "$WATCH" --checklist /dev/null acme repo 7 2>&1)"
check "a merged request syncs the checklist too" "$out" "--merged true"

out="$(STUB_OUT="$PR_OPEN" MAX_POLLS=1 SLEEP=0 CHECKLIST="" RUN_CHECKLIST=/nonexistent \
  PATH="$STUB_DIR:$PATH" timeout 10 "$WATCH" acme repo 7 2>&1)"
refute "no --checklist means no sync is attempted" "$out" "CHECKLIST"

out="$(STUB_OUT="$PR_OPEN" MAX_POLLS=2 SLEEP=0 \
  RUN_CHECKLIST="$STUB_DIR/failing-checklist" \
  PATH="$STUB_DIR:$PATH" timeout 10 "$WATCH" --checklist /dev/null acme repo 7 2>&1)"
check "a failing sync is reported" "$out" "CHECKLIST ERROR"
check "a failing sync does not kill the watch" "$out" "poll budget reached after 2 poll(s)"
[[ "$(grep -c 'CHECKLIST ERROR' <<<"$out")" == "1" ]] \
  && { printf '  ok   — a repeated sync error is said once\n'; PASS=$((PASS + 1)); } \
  || { printf '  fail — a repeated sync error is said once\n'; FAIL=$((FAIL + 1)); }

echo
if [[ $FAIL -gt 0 ]]; then
  echo "failed ($FAIL of $((PASS + FAIL)))"
  exit 1
fi
echo "passed ($PASS checks)"
