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
  --folder PATH        file it in an existing folder, e.g. PRtifacts/Plans
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

STORE=$(env_get artifact_store)
case "$STORE" in
  mnemosyne | auto) ;;
  *)
    echo "artifact_store is '${STORE:-unset}', so there is no self-hosted store here." >&2
    exit "$ABSENT"
    ;;
esac

if command -v publish-artifact >/dev/null 2>&1; then
  exec publish-artifact "$@"
fi

HOST=$(env_get mnemosyne_host)
if [[ -z "$HOST" ]]; then
  echo "mnemosyne_host is empty, so the self-hosted store is not reachable from here." >&2
  exit "$ABSENT"
fi

OWNER=$(env_get mnemosyne_user)
remote_publish() {
  if [[ -n "$OWNER" ]]; then
    ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" "sudo -n -u $OWNER publish-artifact $*"
  else
    ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" "publish-artifact $*"
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

cleanup() {
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" "rm -f '$REMOTE_PATH'" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if ! scp -q -o BatchMode=yes -o ConnectTimeout=10 "$SOURCE" "$HOST:$REMOTE_PATH"; then
  echo "Could not copy $SOURCE to $HOST:$REMOTE_PATH." >&2
  exit 1
fi

if [[ -n "$OWNER" ]]; then
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" "chmod a+r '$REMOTE_PATH'" || true
fi

quoted=()
for argument in "$@"; do
  quoted+=("$(printf '%q' "$argument")")
done

remote_publish "$(printf '%q' "$REMOTE_PATH")" "${quoted[@]+${quoted[@]}}"
