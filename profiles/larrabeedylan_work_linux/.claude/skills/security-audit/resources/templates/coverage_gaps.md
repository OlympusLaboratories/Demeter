# Coverage gaps — `<project-name>`

> Populated whenever a planned check couldn't be executed. Surfaced in the final report.

## Format

### CG-001 · <short title>
- **Stage**: <1-9>
- **Audit-plan item(s)**: <AP-XXX>
- **Threat(s) not covered**: <T-###>
- **Reason**: <missing tool declined; sandbox unavailable; external system; read-only filesystem; etc.>
- **Mitigation taken**: <fallback applied, e.g., "manual review of same pattern">
- **Recommendation**: <what to do to close the gap>
- **Owner**: <if the user owns the follow-up>

<repeat>

## Summary
- Total gaps: <n>
- By stage: <1: n>, <2: n>, ...
- Gaps that leave a threat uncovered: <n>
