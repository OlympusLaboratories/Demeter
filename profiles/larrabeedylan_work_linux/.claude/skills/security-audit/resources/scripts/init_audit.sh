#!/usr/bin/env bash
# init_audit.sh — initialize a security audit working directory in a target project.
#
# Usage: init_audit.sh <target_dir> [--skill-dir <path>]
#
# Creates <target_dir>/.security-audit/, copies template files, seeds state.json,
# and (if a .gitignore exists) adds /.security-audit/ to it.
#
# Safe to re-run: refuses to overwrite an existing .security-audit/ directory.

set -euo pipefail

TARGET_DIR=""
SKILL_DIR="${HOME}/.claude/skills/security-audit"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skill-dir) SKILL_DIR="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 <target_dir> [--skill-dir <path>]" >&2
      exit 2 ;;
    *) TARGET_DIR="$1"; shift ;;
  esac
done

if [[ -z "${TARGET_DIR}" ]]; then
  echo "error: target_dir required" >&2
  echo "Usage: $0 <target_dir> [--skill-dir <path>]" >&2
  exit 2
fi

if [[ ! -d "${TARGET_DIR}" ]]; then
  echo "error: ${TARGET_DIR} is not a directory" >&2
  exit 1
fi

AUDIT_DIR="${TARGET_DIR%/}/.security-audit"

if [[ -d "${AUDIT_DIR}" ]]; then
  echo "error: ${AUDIT_DIR} already exists — use --restart via the skill to archive it" >&2
  exit 1
fi

if [[ ! -d "${SKILL_DIR}/resources/templates" ]]; then
  echo "error: skill templates not found at ${SKILL_DIR}/resources/templates" >&2
  exit 1
fi

mkdir -p "${AUDIT_DIR}/evidence" "${AUDIT_DIR}/sandbox" "${AUDIT_DIR}/tool-logs"

# Copy all markdown templates
for f in "${SKILL_DIR}/resources/templates/"*.md; do
  cp "${f}" "${AUDIT_DIR}/"
done

# Seed state.json, with timestamps and target_dir filled
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
AUDIT_ID="audit-$(date -u +%Y%m%d-%H%M%S)"

python3 - "$SKILL_DIR" "$AUDIT_DIR" "$TARGET_DIR" "$TIMESTAMP" "$AUDIT_ID" <<'PY'
import json, sys, pathlib
skill_dir, audit_dir, target_dir, ts, audit_id = sys.argv[1:6]
tmpl = pathlib.Path(skill_dir) / "resources" / "templates" / "state.json"
out = pathlib.Path(audit_dir) / "state.json"
state = json.loads(tmpl.read_text())
state["audit_id"] = audit_id
state["target_dir"] = str(pathlib.Path(target_dir).resolve())
state["created_at"] = ts
state["updated_at"] = ts
out.write_text(json.dumps(state, indent=2) + "\n")
PY

# Append .security-audit/ to .gitignore if the file exists and it's not already there
GITIGNORE="${TARGET_DIR%/}/.gitignore"
if [[ -f "${GITIGNORE}" ]]; then
  if ! grep -qE '^\s*/?\.security-audit/?\s*$' "${GITIGNORE}"; then
    printf '\n# added by security-audit skill\n/.security-audit/\n' >> "${GITIGNORE}"
    echo "added /.security-audit/ to ${GITIGNORE}"
  fi
fi

echo "initialized audit at ${AUDIT_DIR}"
echo "audit_id: ${AUDIT_ID}"
