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
  STARTUP_FAILURE is terminal and is a failure
  a status of EXPECTED is still running, not complete
  a merged pull request is terminal immediately
  a failed poll emits POLL ERROR carrying stderr, and MAX_ERRORS in a row exits 1

Why this test exists. OLY-35 was a watcher that could not recognise the state it
was in, so it watched a finished pull request forever. The first version of this
tool reproduced it: `terminal_conclusion` enumerated the states it knew, and
GitHub's CheckConclusionState already carried one it did not -- STARTUP_FAILURE --
which would have been counted as pending on every poll. Enumerating the open set
is the bug. Both predicates now enumerate the *benign* set, which is closed, and
treat everything else as terminal and failed: a watch that stops early and says so
is recoverable, and one that never stops is the defect being fixed.

The stub replaces `gh` on PATH and prints the unit-separated lines the real
`gh api graphql --jq` would produce, so the classification is tested without a
network call or a token.
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
printf '%s\n' "$STUB_OUT"
STUB
chmod +x "$STUB_DIR/gh"

run() {
  STUB_OUT="$1" MAX_POLLS="${2:-1}" SLEEP=0 \
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
PR_MERGED=$'PR\037MERGED\037true\037APPROVED\0370\037abc1234'

echo "forge-watch terminal-state classification"
echo

out="$(run "$PR_OPEN"$'\nCHECK\037build\037COMPLETED\037STARTUP_FAILURE')"
check "STARTUP_FAILURE is terminal" "$out" "CHECK build STARTUP_FAILURE"
check "STARTUP_FAILURE is a failure" "$out" "TERMINAL checks finished with failures"
refute "STARTUP_FAILURE is not pending" "$out" "still running"

out="$(run "$PR_OPEN"$'\nCHECK\037build\037COMPLETED\037SOME_FUTURE_STATE')"
check "an unknown conclusion is terminal" "$out" "TERMINAL checks finished with failures"
refute "an unknown conclusion never reads as green" "$out" "complete and green"

out="$(run "$PR_OPEN"$'\nCHECK\037a\037COMPLETED\037SUCCESS\nCHECK\037b\037COMPLETED\037NEUTRAL\nCHECK\037c\037COMPLETED\037SKIPPED')"
check "SUCCESS, NEUTRAL and SKIPPED are green" "$out" "TERMINAL all 3 check(s) complete and green"

out="$(run "$PR_OPEN"$'\nCHECK\037build\037IN_PROGRESS\037')"
check "an unfinished check keeps the watch open" "$out" "WAITING 1 of 1 check(s) still running"
refute "an unfinished check is not terminal" "$out" "TERMINAL all"

out="$(run "$PR_OPEN"$'\nCHECK\037legacy\037IN_PROGRESS\037EXPECTED')"
check "a status of EXPECTED is still running" "$out" "WAITING 1 of 1 check(s) still running"

out="$(run "$PR_OPEN"$'\nCHECK\037a\037COMPLETED\037SUCCESS\nCHECK\037b\037COMPLETED\037FAILURE')"
check "one failure among greens still fails" "$out" "TERMINAL checks finished with failures: b (FAILURE)"

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

echo
if [[ $FAIL -gt 0 ]]; then
  echo "failed ($FAIL of $((PASS + FAIL)))"
  exit 1
fi
echo "passed ($PASS checks)"
