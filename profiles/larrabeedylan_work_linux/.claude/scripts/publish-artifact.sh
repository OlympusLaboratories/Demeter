#!/usr/bin/env bash
set -euo pipefail

ENV_SCRIPT="${SKILL_ENV:-${HOME}/.claude/scripts/skill-env.sh}"
ABSENT=3

usage() {
  cat <<'USAGE'
usage: publish-artifact.sh <file.html> [options]
       publish-artifact.sh --list-folders

Publish an HTML file to the self-hosted artifact store and print its URL.

options:
  --purpose KIND       file it where this machine keeps that kind of page, and
                       publish it public: 'plan' uses plan_folder, 'diagram'
                       uses diagram_folder, 'tasks' uses tasks_folder, and an
                       empty key files it nowhere. a page that declares no
                       icon of its own is published with that kind's glyph,
                       from a copy - the file you pass is never written to
  --folder PATH        file it in an existing folder, e.g. PRtifacts/Plans
  --public             anyone with the link may read it, and the printed link
                       is the one they can open; implied by --purpose
  --expires WHEN       1h, 1d, 7d, 30d, 90d, 1y, a YYYY-MM-DD date, or never
  --title TEXT         overrides the page's <title>
  --description TEXT   one line shown in the index
  --update HASH        revise an existing artifact in place, keeping its URL
  --list-folders       print the folder tree, one path per line, and exit

exit status:
  0   published, URL on stdout
  3   this machine has no self-hosted store - use the Artifact tool instead
  1   the store is configured but the publish failed
USAGE
}

env_get() {
  [[ -x "$ENV_SCRIPT" ]] || return 0
  "$ENV_SCRIPT" get "$1" 2>/dev/null || true
}

NOTIFY_HOOK="${NOTIFY_HOOK:-${HOME}/.claude/hooks/notify.py}"

ICON_PLAN='data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064%2064%22%3E%3Crect%20width%3D%2264%22%20height%3D%2264%22%20rx%3D%2214%22%20fill%3D%22%230b0e11%22%2F%3E%3Cg%20transform%3D%22translate(32%2032)%20scale(0.86)%20translate(-32%20-32)%22%3E%3Crect%20x%3D%2214%22%20y%3D%2210%22%20width%3D%2236%22%20height%3D%2244%22%20rx%3D%225%22%20fill%3D%22none%22%20stroke%3D%22%235ef2a0%22%20stroke-width%3D%224%22%2F%3E%3Cpath%20d%3D%22M23%2025h18M23%2034h18M23%2043h11%22%20stroke%3D%22%232f8f5f%22%20stroke-width%3D%224%22%20stroke-linecap%3D%22round%22%2F%3E%3C%2Fg%3E%3C%2Fsvg%3E'
ICON_DIAGRAM='data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064%2064%22%3E%3Crect%20width%3D%2264%22%20height%3D%2264%22%20rx%3D%2214%22%20fill%3D%22%230b0e11%22%2F%3E%3Cg%20transform%3D%22translate(32%2032)%20scale(0.86)%20translate(-32%20-32)%22%3E%3Cpath%20d%3D%22M32%2020%2018%2042M32%2020%2046%2042%22%20stroke%3D%22%232f8f5f%22%20stroke-width%3D%224%22%20stroke-linecap%3D%22round%22%2F%3E%3Ccircle%20cx%3D%2232%22%20cy%3D%2214%22%20r%3D%227%22%20fill%3D%22%235ef2a0%22%2F%3E%3Ccircle%20cx%3D%2216%22%20cy%3D%2248%22%20r%3D%227%22%20fill%3D%22%235ef2a0%22%2F%3E%3Ccircle%20cx%3D%2248%22%20cy%3D%2248%22%20r%3D%227%22%20fill%3D%22%235ef2a0%22%2F%3E%3C%2Fg%3E%3C%2Fsvg%3E'
ICON_TASKS='data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064%2064%22%3E%3Crect%20width%3D%2264%22%20height%3D%2264%22%20rx%3D%2214%22%20fill%3D%22%230b0e11%22%2F%3E%3Cg%20transform%3D%22translate(32%2032)%20scale(0.86)%20translate(-32%20-32)%22%3E%3Cpath%20d%3D%22M16%2014h26l8%208v28a4%204%200%200%201-4%204H16a4%204%200%200%201-4-4V18a4%204%200%200%201%204-4z%22%20fill%3D%22none%22%20stroke%3D%22%235ef2a0%22%20stroke-width%3D%224%22%20stroke-linejoin%3D%22round%22%2F%3E%3Cpath%20d%3D%22M22%2034l6%206%2014-14%22%20fill%3D%22none%22%20stroke%3D%22%232f8f5f%22%20stroke-width%3D%224%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%2F%3E%3C%2Fg%3E%3C%2Fsvg%3E'

ICON_DIR=""
HOST=""
REMOTE_PATH=""

cleanup() {
  if [[ -n "$HOST" && -n "$REMOTE_PATH" ]]; then
    ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" "rm -f '$REMOTE_PATH'" >/dev/null 2>&1 || true
  fi
  if [[ -n "$ICON_DIR" ]]; then
    rm -rf "$ICON_DIR"
  fi
  return 0
}
trap cleanup EXIT

icon_for() {
  case "$1" in
    plan) printf '%s' "$ICON_PLAN" ;;
    diagram) printf '%s' "$ICON_DIAGRAM" ;;
    tasks) printf '%s' "$ICON_TASKS" ;;
    *) printf '' ;;
  esac
}

declares_icon() {
  grep -qiE '<link[^>]+rel=("|'"'"')?(shortcut +)?(apple-touch-)?icon' "$1"
}

anchor_line() {
  local found=""
  found=$(grep -niE -m1 '<head[ >]|<head$' "$1" 2>/dev/null | cut -d: -f1) || true
  if [[ -z "$found" ]]; then
    found=$(grep -niE -m1 '<!doctype|<html[ >]|<html$' "$1" 2>/dev/null | cut -d: -f1) || true
  fi
  printf '%s' "${found:-0}"
}

with_icon() {
  local source="$1" href="" target=""
  href=$(icon_for "$2")
  [[ -n "$href" && -f "$source" ]] || return 1
  if declares_icon "$source"; then
    return 1
  fi
  ICON_DIR=$(mktemp -d 2>/dev/null) || return 1
  target="$ICON_DIR/$(basename "$source")"
  awk -v after="$(anchor_line "$source")" \
      -v tag="<link rel=\"icon\" type=\"image/svg+xml\" href=\"$href\">" '
    BEGIN { if (after + 0 == 0) print tag }
    { print }
    NR == after + 0 { print tag }
  ' "$source" >"$target" || return 1
  printf '%s' "$target"
}

mark_gate() {
  local url="$1"
  [[ "$PURPOSE" == "plan" && -n "$url" ]] || return 0
  [[ -f "$NOTIFY_HOOK" ]] || return 0
  python3 "$NOTIFY_HOOK" --gate-pending "$url" >/dev/null 2>&1 || true
}

published_url() {
  local last
  last=$(printf '%s\n' "$1" | tail -1 | awk '{$1=$1; print}')
  [[ "$last" =~ ^https?://[^[:space:]]+$ ]] || return 0
  printf '%s\n' "$last"
}

publish_and_report() {
  local output status
  set +e
  output=$("$@")
  status=$?
  set -e
  if [[ -n "$output" ]]; then
    printf '%s\n' "$output"
  fi
  if [[ "$status" -eq 0 ]]; then
    mark_gate "$(published_url "$output")"
  fi
  return "$status"
}

if [[ $# -eq 0 ]]; then
  usage >&2
  exit 1
fi

case "${1:-}" in
  -h | --help)
    usage
    exit 0
    ;;
esac

PURPOSE=""
PASSTHROUGH=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --purpose)
      PURPOSE="${2:-}"
      shift 2 || true
      ;;
    --purpose=*)
      PURPOSE="${1#--purpose=}"
      shift
      ;;
    *)
      PASSTHROUGH+=("$1")
      shift
      ;;
  esac
done
set -- "${PASSTHROUGH[@]+${PASSTHROUGH[@]}}"

case "$PURPOSE" in
  "" | plan | diagram | tasks) ;;
  *)
    echo "--purpose takes 'plan', 'diagram' or 'tasks', not '$PURPOSE'." >&2
    exit 1
    ;;
esac

STORE=$(env_get artifact_store)
case "$STORE" in
  mnemosyne | auto) ;;
  *)
    echo "artifact_store is '${STORE:-unset}', so there is no self-hosted store here." >&2
    exit "$ABSENT"
    ;;
esac

if [[ -n "$PURPOSE" ]]; then
  FOLDER=$(env_get "${PURPOSE}_folder")
  if [[ -n "$FOLDER" ]]; then
    set -- "$@" --folder "$FOLDER"
  fi
  set -- "$@" --public

  ICONISED=$(with_icon "${1:-}" "$PURPOSE") || ICONISED=""
  if [[ -n "$ICONISED" ]]; then
    shift
    set -- "$ICONISED" "$@"
  fi
fi

if command -v publish-artifact >/dev/null 2>&1; then
  publish_and_report publish-artifact "$@"
  exit $?
fi

HOST=$(env_get mnemosyne_host)
if [[ -z "$HOST" ]]; then
  echo "mnemosyne_host is empty, so the self-hosted store is not reachable from here." >&2
  exit "$ABSENT"
fi

OWNER=$(env_get mnemosyne_user)
remote_publish() {
  local command="publish-artifact"
  local argument
  for argument in "$@"; do
    command+=" $(printf '%q' "$argument")"
  done
  if [[ -n "$OWNER" ]]; then
    ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" "sudo -n -u $OWNER $command"
  else
    ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" "$command"
  fi
}

if [[ "${1:-}" == "--list-folders" ]]; then
  remote_publish --list-folders
  exit $?
fi

SOURCE="$1"
shift
if [[ ! -f "$SOURCE" ]]; then
  echo "No such file: $SOURCE" >&2
  exit 1
fi

REMOTE_NAME="demeter-$(date +%s)-$$-$(basename "$SOURCE")"
REMOTE_PATH="/tmp/$REMOTE_NAME"

if ! scp -q -o BatchMode=yes -o ConnectTimeout=10 "$SOURCE" "$HOST:$REMOTE_PATH"; then
  echo "Could not copy $SOURCE to $HOST:$REMOTE_PATH." >&2
  exit 1
fi

if [[ -n "$OWNER" ]]; then
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" "chmod a+r '$REMOTE_PATH'" || true
fi

publish_and_report remote_publish "$REMOTE_PATH" "$@"
