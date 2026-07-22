#!/usr/bin/env bash
# evidence_capture.sh — capture an exploit's request/response/logs into .security-audit/evidence/<finding-id>/
#
# Designed to be used from inside a Stage 5 PoC test.
#
# Usage:
#   evidence_capture.sh <audit_dir> <finding_id> <kind> <path-to-file>
#
#   kind: request | response | log | db-diff | stack | notes
#
# Multiple calls accumulate inside the finding's evidence folder. Each artifact is
# stored with a monotonic prefix so ordering is obvious.

set -euo pipefail

AUDIT_DIR="${1:-}"
FINDING="${2:-}"
KIND="${3:-}"
SRC="${4:-}"

if [[ -z "${AUDIT_DIR}" || -z "${FINDING}" || -z "${KIND}" || -z "${SRC}" ]]; then
  echo "Usage: $0 <audit_dir> <finding_id> <kind> <path-to-file>" >&2
  exit 2
fi

if [[ ! -d "${AUDIT_DIR}" ]]; then
  echo "error: ${AUDIT_DIR} not a directory" >&2
  exit 1
fi

if [[ ! -f "${SRC}" ]]; then
  echo "error: source file ${SRC} not found" >&2
  exit 1
fi

DEST_DIR="${AUDIT_DIR%/}/evidence/${FINDING}"
mkdir -p "${DEST_DIR}"

# Monotonic index within this finding folder
NEXT=$(printf "%03d" "$(find "${DEST_DIR}" -maxdepth 1 -type f | wc -l | tr -d ' ')")

BASENAME="$(basename "${SRC}")"
DEST="${DEST_DIR}/${NEXT}-${KIND}-${BASENAME}"

cp "${SRC}" "${DEST}"

# Append a manifest line
MANIFEST="${DEST_DIR}/manifest.tsv"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\t%s\t%s\t%s\n' "${TS}" "${KIND}" "${SRC}" "${DEST}" >> "${MANIFEST}"

echo "captured: ${DEST}"
