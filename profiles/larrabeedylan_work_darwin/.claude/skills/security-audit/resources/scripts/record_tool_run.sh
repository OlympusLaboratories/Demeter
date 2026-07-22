#!/usr/bin/env bash
# record_tool_run.sh — run a security tool, capture stdout+stderr to tool-logs/,
# and emit a one-line JSON record that the skill can append to state.json.
#
# Usage:
#   record_tool_run.sh <audit_dir> <tool_name> -- <command ...>
#
# Example:
#   record_tool_run.sh .security-audit semgrep -- semgrep --config p/owasp-top-ten .

set -euo pipefail

AUDIT_DIR="${1:-}"
TOOL="${2:-}"
SEP="${3:-}"

if [[ -z "${AUDIT_DIR}" || -z "${TOOL}" || "${SEP}" != "--" ]]; then
  echo "Usage: $0 <audit_dir> <tool_name> -- <command ...>" >&2
  exit 2
fi

shift 3

if [[ ! -d "${AUDIT_DIR}" ]]; then
  echo "error: ${AUDIT_DIR} not a directory" >&2
  exit 1
fi

mkdir -p "${AUDIT_DIR}/tool-logs"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${AUDIT_DIR}/tool-logs/${TOOL}-${TS}.log"

# Capture the version of the tool where possible
VERSION_OUT="$("${1}" --version 2>/dev/null || true)"
VERSION_LINE="$(echo "${VERSION_OUT}" | head -n1 | tr -d '"')"

START="$(date -u +%s)"
set +e
"$@" > "${LOG}" 2>&1
EXIT=$?
set -e
END="$(date -u +%s)"

CMDLINE="$(printf '%q ' "$@")"

printf '{"tool":"%s","version":"%s","log":"%s","exit":%d,"started":%s,"ended":%s,"cmd":"%s"}\n' \
  "${TOOL}" "${VERSION_LINE}" "${LOG}" "${EXIT}" "${START}" "${END}" "${CMDLINE//\"/\\\"}"
