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

exit 3 is the "no self-hosted store here" answer and must never be confused with a
failure: the callers fall through to the Artifact tool on 3, and report on anything else.
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
done

echo "publish-artifact.sh"
echo
if ((failures)); then
  echo "failed ($failures of $checked checks)"
  exit 1
fi
printf '  ok   — %d checks over %d profile copies\n\n' "$checked" "${#PROFILES[@]}"
echo "passed"
