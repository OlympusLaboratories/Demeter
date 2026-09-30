#!/usr/bin/env bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SETTINGS="$REPO_DIR/vscode/settings.json"
SCAN_ROOT="${PEACOCK_SCAN_ROOT:-$HOME}"
SCAN_DEPTH="${PEACOCK_SCAN_DEPTH:-5}"

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}${*}${RESET}"; }
success() { echo -e "${GREEN}✓ ${*}${RESET}"; }
warn()    { echo -e "${YELLOW}! ${*}${RESET}"; }
error()   { echo -e "${RED}✗ ${*}${RESET}"; }
bold()    { echo -e "${BOLD}${*}${RESET}"; }

ask() {
  local prompt="$1" default="${2:-y}"
  local yn_display
  [[ "$default" == "y" ]] && yn_display="[Y/n]" || yn_display="[y/N]"
  echo -en "${BOLD}${prompt} ${yn_display} ${RESET}"
  read -r reply
  reply="${reply:-$default}"
  [[ "$reply" =~ ^[Yy]$ ]]
}

owned_keys() {
  [[ -f "$SETTINGS" ]] || return 0
  python3 -c '
import json, re, sys
src = re.sub(r"(?m)//.*$", "", open(sys.argv[1]).read())
src = re.sub(r",(\s*[}\]])", r"\1", src)
try:
    data = json.loads(src)
except Exception:
    sys.exit(0)
for key in data.get("peacock.excludedSettings", []) or []:
    print(key)
' "$SETTINGS"
}

workspace_settings_files() {
  { find "$SCAN_ROOT" -maxdepth "$SCAN_DEPTH" \
    \( -name node_modules -o -name .git -o -name Library -o -name .Trash \
       -o -name .cache -o -name .npm -o -name .nvm -o -name .rustup \
       -o -name .cargo -o -name go -o -name vendor -o -name target \
       -o -name dist -o -name .venv -o -name venv \) -prune -o \
    -path '*/.vscode/settings.json' -type f -print 2>/dev/null || true; } | sort
}

SWEEP_PY='
import json, os, re, sys

keys = set(json.loads(os.environ["OWNED_KEYS"]))
apply_changes = "--apply" in sys.argv


def parse(text):
    stripped = re.sub(r"(?m)//.*$", "", text)
    stripped = re.sub(r",(\s*[}\]])", r"\1", stripped)
    return json.loads(stripped)


for path in (line for line in sys.stdin.read().splitlines() if line):
    try:
        src = open(path, encoding="utf-8").read()
        data = parse(src)
    except Exception:
        continue
    colors = data.get("workbench.colorCustomizations")
    if not isinstance(colors, dict):
        continue
    hits = sorted(k for k in colors if k in keys)
    if not hits:
        continue
    if not apply_changes:
        print("FOUND\t%s\t%s" % (path, ",".join(hits)))
        continue
    pattern = re.compile(r"\s*\"(%s)\"\s*:" % "|".join(re.escape(h) for h in hits))
    out = "\n".join(l for l in src.splitlines() if not pattern.match(l))
    if not out.endswith("\n"):
        out += "\n"
    out = re.sub(r",(\s*[}\]])", r"\1", out)
    expected = dict(data)
    expected["workbench.colorCustomizations"] = {
        k: v for k, v in colors.items() if k not in hits
    }
    try:
        if parse(out) != expected:
            raise ValueError("rewrite changed more than the owned keys")
    except Exception:
        print("SKIP\t%s\t%s" % (path, ", ".join(hits)))
        continue
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(out)
    print("FIXED\t%s\t%s" % (path, ",".join(hits)))
'

main() {
  local quiet=false
  [[ "${1:-}" == "--quiet" ]] && quiet=true

  [[ "$quiet" == true ]] || bold "\n=== Strip stale workspace color keys ==="

  local keys
  keys="$(owned_keys)"
  if [[ -z "$keys" ]]; then
    [[ "$quiet" == true ]] || info "No keys claimed in peacock.excludedSettings — nothing to enforce."
    return 0
  fi

  local files found
  files="$(workspace_settings_files)"
  if [[ -z "$files" ]]; then
    info "No workspace settings files under ${SCAN_ROOT/#$HOME/\~} (depth $SCAN_DEPTH)."
    return 0
  fi

  OWNED_KEYS="$(python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().split()))' <<<"$keys")"
  export OWNED_KEYS

  found="$(python3 -c "$SWEEP_PY" <<<"$files" || true)"
  if [[ -z "$found" ]]; then
    success "No stale keys in $(grep -c . <<<"$files") workspace settings file(s)."
    return 0
  fi

  bold "Workspace settings overriding keys this repo owns:"
  while IFS=$'\t' read -r _ path hit_keys; do
    echo "  ${path/#$HOME/\~}"
    echo "      $hit_keys"
  done <<<"$found"
  echo ""
  info "A workspace .vscode/settings.json outranks user settings, so these keys"
  info "silently win over the pins in vscode/settings.json. Peacock wrote them"
  info "before they were excluded, and it never deletes an excluded key."
  echo ""

  if ! ask "Strip them from $(grep -c . <<<"$found") file(s)?"; then
    info "Left unchanged."
    return 0
  fi

  local result
  result="$(python3 -c "$SWEEP_PY" --apply <<<"$files" || true)"
  while IFS=$'\t' read -r status path detail; do
    case "$status" in
      FIXED) success "${path/#$HOME/\~} — removed $detail" ;;
      SKIP)  warn "${path/#$HOME/\~} — remove $detail by hand; it shares a line with other settings" ;;
    esac
  done <<<"$result"
  info "Reload VS Code (Developer: Reload Window) in those windows."
}

main "$@"
