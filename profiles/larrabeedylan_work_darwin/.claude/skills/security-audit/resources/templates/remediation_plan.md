# Remediation plan — `<project-name>`

> Populated by Stage 6. Presented to the user. Stage 7 executes only items approved here.

## Summary
- Findings in scope for remediation consideration: <n>
- By severity: <c critical / h high / m medium / l low / i info>
- Architectural items requiring decision: <n>
- Top-3 highest-impact: <list IDs>

## Fix plan

### Fix SA-XXX — <one-line fix title>
- **Targets**: `<path:line>`, `<path:line>`
- **Fixes finding(s)**: SA-XXX (supersedes/relates: SA-YYY)
- **Threat(s) realized**: T-###
- **Proposed change**: <bullet list, describing the change — not the patch>
- **Fix complexity**: <trivial | moderate | significant | architectural>
- **Fix risk**: <low | medium | high> — reason
- **Order**: batch <N> (<before | after> SA-ZZZ)
- **Root-cause vs symptomatic**: <root-cause | mitigating | symptomatic>
- **Tests that must pass post-fix**:
  - <test name> — <purpose>
- **Affected dependents**: <other code paths touched>
- **Rollback**: <how to revert>

<repeat>

## Architectural items
Items that cannot be fixed locally — require design discussion:
- <e.g., "move authorization from per-handler to central policy layer">
- <e.g., "migrate secrets from .env to AWS Secrets Manager">

Document proposed migration shape for each.

## Ordering

Batch 1 (root-cause / authz / authn): SA-XXX, SA-YYY
Batch 2 (injection / input validation): SA-ZZZ, ...
Batch 3 (defense-in-depth): ...
Deferred (low or architectural): ...

## Approval

Ask user for explicit scope. Options:
- `all`
- `severity ≥ <level>`
- `by id: <list>`
- `by category: <list>`
- `none` (report only)

### User decision
- **Approved at**: <timestamp>
- **Scope**: <user's verbatim reply or parsed equivalent>
- **In scope IDs**: <SA-XXX, SA-YYY, ...>
- **Deferred IDs**: <SA-ZZZ, ...>
- **Deferral rationale per ID**: <if the user provided one>
