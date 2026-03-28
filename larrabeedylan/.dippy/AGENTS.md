# .dippy/ — Agent Instructions

## Contents

| File | Purpose |
|---|---|
| `config` | Dippy allow/deny rules for Claude Code Bash commands |

## Testing Config Changes

After modifying `config`, verify the rule works by piping a mock hook payload into the Dippy hook binary:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"<the command to test>"}}' | /Users/dylanlarrabee/Demeter/_vendor/dippy/bin/dippy-hook
```

The response JSON will clearly show the decision:

**Allowed:**
```json
{"hookSpecificOutput": {"permissionDecision": "allow", "permissionDecisionReason": "🐤 mkdir (mkdir *)"}}
```

**Not matched (will prompt the user):**
```json
{"hookSpecificOutput": {"permissionDecision": "ask", "permissionDecisionReason": "🐤 no matching rule"}}
```

Always test both before and after adding a rule to confirm it takes effect.
