#!/usr/bin/env bash
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILES=(
  larrabeedylan_work_darwin
  larrabeedylan_work_linux
  larrabeedylan_home_darwin
)

if [[ "${1:-}" == "rules" ]]; then
  cat <<'RULES'
publish-artifact.sh, checked over every profile copy:

  --help                                      exits 0
  artifact_store=claude                       exits 3 (capability absent)
  artifact_store=auto, mnemosyne_host empty   exits 3 (capability absent)
  publish-artifact on PATH                    runs it locally, forwards every argument
  a missing source file                       exits 1, never 3
  no arguments                                exits 1
  no publish-artifact on PATH                 scp the file, then run it over ssh
  mnemosyne_user set                          the remote command is sudo -n -u <user>
  mnemosyne_user empty                        no sudo in the remote command
  an argument containing spaces               arrives at the remote argv intact
  after publishing                            the remote temp file is removed
  --purpose plan, plan_folder set             --folder <value> reaches the remote argv
  --purpose plan, plan_folder empty           no --folder at all
  --purpose diagram                           uses diagram_folder, not plan_folder
  --purpose nonsense                          exits 1
  --purpose under zsh and under bash          identical remote argv
  --purpose on the local path                 --folder reaches the local argv too
  --purpose anything                          --public reaches the argv as well
  --purpose plan, plan_folder empty           --public still reaches the argv
  no --purpose                                no --public anywhere
  --purpose plan, publish succeeded           notify.py --gate-pending <url> is called
  --purpose plan on the local path            the same, with the local url
  --purpose diagram                           no gate call
  no --purpose                                no gate call
  --purpose plan, publish failed              no gate call
  --purpose plan, no notify.py present        still exits 0

exit 3 is the "no self-hosted store here" answer and must never be confused with a
failure: the callers fall through to the Artifact tool on 3, and report on anything else.

The gate call is what stops a published plan stranding the run. A plan is published so it
can be approved, so the hook records the url and notifies even on an unarmed session when
the turn ends without the approval question being asked. Marking must never be able to fail
a publish, and must never fire for a page nobody is waiting on.
RULES
  exit 0
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fake_env() {
  local dir="$1" store="$2" host="$3"
  mkdir -p "$dir"
  cat >"$dir/skill-env.sh" <<ENVSCRIPT
#!/usr/bin/env bash
[[ "\$1" == "get" ]] || exit 1
case "\$2" in
  artifact_store) echo '$store' ;;
  mnemosyne_host) echo '$host' ;;
  mnemosyne_user) echo 'someuser' ;;
  *) echo '' ;;
esac
ENVSCRIPT
  chmod +x "$dir/skill-env.sh"
}

failures=0
checked=0

check() {
  local label="$1" want="$2" got="$3"
  checked=$((checked + 1))
  if [[ "$want" != "$got" ]]; then
    printf '  fail — %s\n      want exit %s, got %s\n' "$label" "$want" "$got"
    failures=$((failures + 1))
  fi
}

for profile in "${PROFILES[@]}"; do
  script="$REPO/profiles/$profile/.claude/scripts/publish-artifact.sh"
  if [[ ! -x "$script" ]]; then
    printf '  fail — %s has no executable publish-artifact.sh\n' "$profile"
    failures=$((failures + 1))
    continue
  fi

  page="$WORK/page.html"
  echo '<title>t</title>' >"$page"

  "$script" --help >/dev/null 2>&1
  check "$profile: --help" 0 $?

  fake_env "$WORK/claude" claude ""
  SKILL_ENV="$WORK/claude/skill-env.sh" "$script" "$page" >/dev/null 2>&1
  check "$profile: artifact_store=claude" 3 $?

  fake_env "$WORK/nohost" auto ""
  SKILL_ENV="$WORK/nohost/skill-env.sh" "$script" "$page" >/dev/null 2>&1
  check "$profile: no mnemosyne_host" 3 $?

  fake_env "$WORK/reachable" auto somehost
  SKILL_ENV="$WORK/reachable/skill-env.sh" "$script" "$WORK/absent.html" >/dev/null 2>&1
  check "$profile: missing source file" 1 $?

  "$script" >/dev/null 2>&1
  check "$profile: no arguments" 1 $?

  mkdir -p "$WORK/bin"
  cat >"$WORK/bin/publish-artifact" <<'LOCAL'
#!/usr/bin/env bash
printf '%s\n' "$@" >"$LOCAL_ARGS"
exit 0
LOCAL
  chmod +x "$WORK/bin/publish-artifact"
  LOCAL_ARGS="$WORK/args.txt" PATH="$WORK/bin:$PATH" \
    SKILL_ENV="$WORK/reachable/skill-env.sh" "$script" "$page" --folder 'A/B' --expires 7d >/dev/null 2>&1
  check "$profile: local publish-artifact is used" 0 $?
  if [[ "$(tr '\n' ' ' <"$WORK/args.txt" 2>/dev/null)" != "$page --folder A/B --expires 7d " ]]; then
    printf '  fail — %s: arguments not forwarded verbatim\n      got: %s\n' \
      "$profile" "$(tr '\n' ' ' <"$WORK/args.txt" 2>/dev/null)"
    failures=$((failures + 1))
  fi
  checked=$((checked + 1))
  rm -f "$WORK/args.txt"

  mkdir -p "$WORK/fake"
  cat >"$WORK/fake/scp" <<'FAKESCP'
#!/usr/bin/env bash
target=""
for a in "$@"; do target="$a"; done
printf '%s\n' "$target" >>"$SCP_LOG"
printf '%s\n' "$@" | tail -2 | head -1 >"$SCP_SOURCE"
exit 0
FAKESCP
  cat >"$WORK/fake/ssh" <<'FAKESSH'
#!/usr/bin/env bash
command=""
for a in "$@"; do command="$a"; done
printf '%s\n' "$command" >>"$SSH_LOG"
case "$command" in
  rm\ -f*) exit 0 ;;
esac
remote=${command#sudo -n -u * }
if [[ "$command" == "$remote" ]]; then remote="$command"; fi
PATH="$FAKE_REMOTE_BIN:$PATH" bash -c "$remote"
FAKESSH
  chmod +x "$WORK/fake/scp" "$WORK/fake/ssh"

  mkdir -p "$WORK/remotebin"
  cat >"$WORK/remotebin/publish-artifact" <<'REMOTE'
#!/usr/bin/env bash
printf '%s\n' "$@" >"$REMOTE_ARGS"
echo "https://example.invalid/abc"
REMOTE
  chmod +x "$WORK/remotebin/publish-artifact"

  rm -f "$WORK/ssh.log" "$WORK/scp.log" "$WORK/remote-args.txt"
  out=$(
    SCP_LOG="$WORK/scp.log" SCP_SOURCE="$WORK/scp-source.txt" \
    SSH_LOG="$WORK/ssh.log" REMOTE_ARGS="$WORK/remote-args.txt" \
    FAKE_REMOTE_BIN="$WORK/remotebin" \
    PATH="$WORK/fake:/usr/bin:/bin" \
    SKILL_ENV="$WORK/reachable/skill-env.sh" \
    "$script" "$page" --folder 'A/B' --title 'My Plan' --description "it's fine" 2>/dev/null
  )
  check "$profile: remote publish exits 0" 0 $?

  if [[ "$out" != "https://example.invalid/abc" ]]; then
    printf '  fail — %s: remote URL not printed (got %s)\n' "$profile" "${out:-<empty>}"
    failures=$((failures + 1))
  fi
  checked=$((checked + 1))

  if ! grep -q 'sudo -n -u someuser publish-artifact' "$WORK/ssh.log"; then
    printf '  fail — %s: remote command is not run as mnemosyne_user\n      %s\n' \
      "$profile" "$(head -1 "$WORK/ssh.log" 2>/dev/null)"
    failures=$((failures + 1))
  fi
  checked=$((checked + 1))

  want_argv="--folder
A/B
--title
My Plan
--description
it's fine"
  got_argv=$(tail -n +2 "$WORK/remote-args.txt" 2>/dev/null)
  if [[ "$got_argv" != "$want_argv" ]]; then
    printf '  fail — %s: remote argv mangled\n      want: %s\n      got:  %s\n' \
      "$profile" "$(printf '%s' "$want_argv" | tr '\n' '|')" "$(printf '%s' "$got_argv" | tr '\n' '|')"
    failures=$((failures + 1))
  fi
  checked=$((checked + 1))

  if ! head -1 "$WORK/remote-args.txt" 2>/dev/null | grep -q '^/tmp/demeter-'; then
    printf '  fail — %s: remote path is not the copied temp file\n' "$profile"
    failures=$((failures + 1))
  fi
  checked=$((checked + 1))

  if ! grep -q '^rm -f ' "$WORK/ssh.log"; then
    printf '  fail — %s: remote temp file is never removed\n' "$profile"
    failures=$((failures + 1))
  fi
  checked=$((checked + 1))

  purpose_env() {
    local dir="$1" plan="$2" diagram="$3"
    mkdir -p "$dir"
    cat >"$dir/skill-env.sh" <<ENVSCRIPT
#!/usr/bin/env bash
[[ "\$1" == "get" ]] || exit 1
case "\$2" in
  artifact_store) echo 'auto' ;;
  mnemosyne_host) echo 'somehost' ;;
  mnemosyne_user) echo 'someuser' ;;
  plan_folder) echo '$plan' ;;
  diagram_folder) echo '$diagram' ;;
  *) echo '' ;;
esac
ENVSCRIPT
    chmod +x "$dir/skill-env.sh"
  }

  run_remote() {
    local env_file="$1"
    shift
    rm -f "$WORK/remote-args.txt"
    SCP_LOG="$WORK/scp.log" SCP_SOURCE="$WORK/scp-source.txt" \
    SSH_LOG="$WORK/ssh.log" REMOTE_ARGS="$WORK/remote-args.txt" \
    FAKE_REMOTE_BIN="${REMOTE_BIN:-$WORK/remotebin}" \
    GATE_CALLS="$WORK/gate-calls.txt" NOTIFY_HOOK="$WORK/fake-notify.py" \
    PATH="$WORK/fake:/usr/bin:/bin" \
    SKILL_ENV="$env_file" \
    "$script" "$@" >/dev/null 2>&1
  }

  cat >"$WORK/fake-notify.py" <<'NOTIFY'
import os
import sys
with open(os.environ["GATE_CALLS"], "a", encoding="utf-8") as handle:
    handle.write(" ".join(sys.argv[1:]) + "\n")
NOTIFY

  mkdir -p "$WORK/binurl"
  cat >"$WORK/binurl/publish-artifact" <<'LOCALURL'
#!/usr/bin/env bash
printf '%s\n' "$@" >"$LOCAL_ARGS"
echo "https://example.invalid/local"
LOCALURL
  chmod +x "$WORK/binurl/publish-artifact"

  mkdir -p "$WORK/remotefail"
  cat >"$WORK/remotefail/publish-artifact" <<'REMOTEFAIL'
#!/usr/bin/env bash
echo "the store refused it" >&2
exit 1
REMOTEFAIL
  chmod +x "$WORK/remotefail/publish-artifact"

  gate_calls() {
    cat "$WORK/gate-calls.txt" 2>/dev/null | tr '\n' '|'
  }

  no_gate_call() {
    local label="$1"
    checked=$((checked + 1))
    if [[ -s "$WORK/gate-calls.txt" ]]; then
      printf '  fail — %s: %s\n      got: %s\n' "$profile" "$label" "$(gate_calls)"
      failures=$((failures + 1))
    fi
  }


  purpose_env "$WORK/purpose" 'P/Plans' 'P/Diagrams'
  purpose_env "$WORK/nofolders" '' ''

  rm -f "$WORK/args.txt"
  LOCAL_ARGS="$WORK/args.txt" PATH="$WORK/bin:$PATH" \
    SKILL_ENV="$WORK/purpose/skill-env.sh" "$script" "$page" --purpose plan >/dev/null 2>&1
  check "$profile: --purpose plan on the local path" 0 $?
  if ! grep -qx -- '--folder' "$WORK/args.txt" 2>/dev/null \
    || ! grep -qx 'P/Plans' "$WORK/args.txt" 2>/dev/null; then
    printf '  fail — %s: --purpose plan did not reach the local argv\n      got: %s\n' \
      "$profile" "$(tr '\n' '|' <"$WORK/args.txt" 2>/dev/null)"
    failures=$((failures + 1))
  fi
  checked=$((checked + 1))
  if ! grep -qx -- '--public' "$WORK/args.txt" 2>/dev/null; then
    printf '  fail — %s: --purpose plan did not send --public to the local argv\n      got: %s\n' \
      "$profile" "$(tr '\n' '|' <"$WORK/args.txt" 2>/dev/null)"
    failures=$((failures + 1))
  fi
  checked=$((checked + 1))
  rm -f "$WORK/args.txt"

  run_remote "$WORK/purpose/skill-env.sh" "$page" --purpose plan --expires 7d
  check "$profile: --purpose plan publishes" 0 $?
  if ! grep -qx -- '--folder' "$WORK/remote-args.txt" 2>/dev/null \
    || ! grep -qx 'P/Plans' "$WORK/remote-args.txt" 2>/dev/null; then
    printf '  fail — %s: --purpose plan did not send --folder P/Plans\n      got: %s\n' \
      "$profile" "$(tr '\n' '|' <"$WORK/remote-args.txt" 2>/dev/null)"
    failures=$((failures + 1))
  fi
  checked=$((checked + 1))
  if ! grep -qx -- '--public' "$WORK/remote-args.txt" 2>/dev/null; then
    printf '  fail — %s: --purpose plan did not send --public\n      got: %s\n' \
      "$profile" "$(tr '\n' '|' <"$WORK/remote-args.txt" 2>/dev/null)"
    failures=$((failures + 1))
  fi
  checked=$((checked + 1))

  run_remote "$WORK/purpose/skill-env.sh" "$page" --purpose diagram
  if ! grep -qx 'P/Diagrams' "$WORK/remote-args.txt" 2>/dev/null; then
    printf '  fail — %s: --purpose diagram did not use diagram_folder\n' "$profile"
    failures=$((failures + 1))
  fi
  checked=$((checked + 1))

  run_remote "$WORK/nofolders/skill-env.sh" "$page" --purpose plan
  if grep -qx -- '--folder' "$WORK/remote-args.txt" 2>/dev/null; then
    printf '  fail — %s: an empty plan_folder still sent --folder\n' "$profile"
    failures=$((failures + 1))
  fi
  checked=$((checked + 1))
  if ! grep -qx -- '--public' "$WORK/remote-args.txt" 2>/dev/null; then
    printf '  fail — %s: an empty plan_folder suppressed --public\n' "$profile"
    failures=$((failures + 1))
  fi
  checked=$((checked + 1))

  run_remote "$WORK/purpose/skill-env.sh" "$page" --expires 7d
  if grep -qx -- '--public' "$WORK/remote-args.txt" 2>/dev/null; then
    printf '  fail — %s: a publish with no --purpose sent --public\n      got: %s\n' \
      "$profile" "$(tr '\n' '|' <"$WORK/remote-args.txt" 2>/dev/null)"
    failures=$((failures + 1))
  fi
  checked=$((checked + 1))

  rm -f "$WORK/gate-calls.txt"
  run_remote "$WORK/purpose/skill-env.sh" "$page" --purpose plan
  checked=$((checked + 1))
  if [[ "$(gate_calls)" != "--gate-pending https://example.invalid/abc|" ]]; then
    printf '  fail — %s: --purpose plan did not record the gate\n      got: %s\n' \
      "$profile" "$(gate_calls)"
    failures=$((failures + 1))
  fi

  rm -f "$WORK/gate-calls.txt"
  run_remote "$WORK/purpose/skill-env.sh" "$page" --purpose diagram
  no_gate_call "--purpose diagram recorded a gate"

  rm -f "$WORK/gate-calls.txt"
  run_remote "$WORK/purpose/skill-env.sh" "$page" --expires 7d
  no_gate_call "a publish with no --purpose recorded a gate"

  rm -f "$WORK/gate-calls.txt"
  REMOTE_BIN="$WORK/remotefail" run_remote "$WORK/purpose/skill-env.sh" "$page" --purpose plan
  no_gate_call "a failed publish recorded a gate"

  rm -f "$WORK/gate-calls.txt" "$WORK/args.txt"
  LOCAL_ARGS="$WORK/args.txt" PATH="$WORK/binurl:$PATH" \
    GATE_CALLS="$WORK/gate-calls.txt" NOTIFY_HOOK="$WORK/fake-notify.py" \
    SKILL_ENV="$WORK/purpose/skill-env.sh" "$script" "$page" --purpose plan >/dev/null 2>&1
  check "$profile: --purpose plan on the local path still exits 0" 0 $?
  checked=$((checked + 1))
  if [[ "$(gate_calls)" != "--gate-pending https://example.invalid/local|" ]]; then
    printf '  fail — %s: the local path did not record the gate\n      got: %s\n' \
      "$profile" "$(gate_calls)"
    failures=$((failures + 1))
  fi

  rm -f "$WORK/gate-calls.txt"
  GATE_CALLS="$WORK/gate-calls.txt" NOTIFY_HOOK="$WORK/absent-notify.py" \
    PATH="$WORK/binurl:$PATH" LOCAL_ARGS="$WORK/args.txt" \
    SKILL_ENV="$WORK/purpose/skill-env.sh" "$script" "$page" --purpose plan >/dev/null 2>&1
  check "$profile: a missing notify.py never fails the publish" 0 $?
  rm -f "$WORK/gate-calls.txt"

  run_remote "$WORK/purpose/skill-env.sh" "$page" --purpose nonsense
  check "$profile: --purpose nonsense" 1 $?

  for shell in zsh bash; do
    command -v "$shell" >/dev/null 2>&1 || continue
    rm -f "$WORK/remote-args.txt"
    "$shell" -c "
      SCP_LOG='$WORK/scp.log' SCP_SOURCE='$WORK/scp-source.txt'
      SSH_LOG='$WORK/ssh.log' REMOTE_ARGS='$WORK/remote-args.txt'
      FAKE_REMOTE_BIN='$WORK/remotebin'
      export SCP_LOG SCP_SOURCE SSH_LOG REMOTE_ARGS FAKE_REMOTE_BIN
      PATH='$WORK/fake:/usr/bin:/bin' SKILL_ENV='$WORK/purpose/skill-env.sh' \
        '$script' '$page' --purpose plan --expires 7d >/dev/null 2>&1
    "
    if ! grep -qx -- '--folder' "$WORK/remote-args.txt" 2>/dev/null \
      || ! grep -qx 'P/Plans' "$WORK/remote-args.txt" 2>/dev/null \
      || ! grep -qx -- '--public' "$WORK/remote-args.txt" 2>/dev/null; then
      printf '  fail — %s: --purpose plan is wrong under %s\n      got: %s\n' \
        "$profile" "$shell" "$(tr '\n' '|' <"$WORK/remote-args.txt" 2>/dev/null)"
      failures=$((failures + 1))
    fi
    checked=$((checked + 1))
  done

  fake_env "$WORK/nouser" auto somehost
  sed -i.bak "s/echo 'someuser'/echo ''/" "$WORK/nouser/skill-env.sh" && rm -f "$WORK/nouser/skill-env.sh.bak"
  rm -f "$WORK/ssh.log"
  SCP_LOG="$WORK/scp.log" SCP_SOURCE="$WORK/scp-source.txt" \
  SSH_LOG="$WORK/ssh.log" REMOTE_ARGS="$WORK/remote-args.txt" \
  FAKE_REMOTE_BIN="$WORK/remotebin" \
  PATH="$WORK/fake:/usr/bin:/bin" \
  SKILL_ENV="$WORK/nouser/skill-env.sh" \
  "$script" "$page" >/dev/null 2>&1
  check "$profile: empty mnemosyne_user still publishes" 0 $?
  if grep -q 'sudo' "$WORK/ssh.log"; then
    printf '  fail — %s: sudo used even though mnemosyne_user is empty\n' "$profile"
    failures=$((failures + 1))
  fi
  checked=$((checked + 1))
done

echo "publish-artifact.sh"
echo
if ((failures)); then
  echo "failed ($failures of $checked checks)"
  exit 1
fi
printf '  ok   — %d checks over %d profile copies\n\n' "$checked" "${#PROFILES[@]}"
echo "passed"
