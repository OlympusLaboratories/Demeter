#!/bin/sh
# Launches Claude Code with summarized thinking display when the installed build
# supports it. Referenced from vscode/settings.json as claudeCode.claudeProcessWrapper.
#
# --thinking-display is undocumented and its accepted values have changed between
# releases, so the flag is probed before use and dropped if unsupported. Any failure
# here must still launch Claude normally: this script sits in front of every
# Claude Code session in the editor.

set -eu

find_claude() {
    if [ -n "${AGENT_WATCH_CLAUDE_BIN:-}" ] && [ -x "${AGENT_WATCH_CLAUDE_BIN}" ]; then
        printf '%s\n' "${AGENT_WATCH_CLAUDE_BIN}"
        return 0
    fi

    # The editor normally launches the binary bundled with its own extension
    # version; prefer the newest of those so the wrapper does not downgrade.
    for candidate in $(ls -d "$HOME"/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude 2>/dev/null | sort -rV); do
        [ -x "$candidate" ] && { printf '%s\n' "$candidate"; return 0; }
    done

    command -v claude 2>/dev/null && return 0
    return 1
}

supports_summarized() {
    "$1" --thinking-display __probe__ 2>&1 | grep -q 'summarized'
}

claude_bin="$(find_claude)" || {
    echo "claude-wrapper: no claude binary found" >&2
    exit 127
}

if supports_summarized "$claude_bin"; then
    exec "$claude_bin" --thinking-display summarized "$@"
fi

exec "$claude_bin" "$@"
