#!/usr/bin/env bash
# redact_secret.sh — produce the redacted form of a discovered secret for markdown output.
#
# Usage: redact_secret.sh <file> <line> <pattern_type> <secret_value>
# Prints: <file>:<line> · <pattern_type> · …<last4>
#
# NEVER log or pass the full secret. Callers must pass it via stdin or an ephemeral file
# that is unlinked immediately — not as an argument (visible in `ps`).
#
# This helper takes the value on stdin to keep it out of argv.

set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <file> <line> <pattern_type>   (secret value via stdin)" >&2
  exit 2
fi

FILE="$1"
LINE="$2"
TYPE="$3"

# Read the secret from stdin
VALUE="$(cat)"

if [[ -z "${VALUE}" ]]; then
  echo "error: secret value required on stdin" >&2
  exit 1
fi

LAST4="${VALUE: -4}"
# Sanity: truncate extremely long "last-4" (if someone piped a binary) — keep exactly 4 chars
LAST4="${LAST4:0:4}"

printf '%s:%s · %s · …%s\n' "${FILE}" "${LINE}" "${TYPE}" "${LAST4}"
