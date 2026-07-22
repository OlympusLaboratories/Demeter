# Audit plan — `<project-name>`

> Populated by Stage 3. One entry per check. Each entry covers one or more threats from `threat_model.md`.

## SAST / linters
### AP-001 · <tool + ruleset>
- **Command**: `<exact command line>`
- **Covers threats**: <T-###, T-###>
- **Tool version**: <filled at run time>
- **Rationale**: <why this tool for these threats>
- **Output**: <path in tool-logs/>

<repeat>

## Dependency / supply chain
<AP-0XX entries>

## Secret scanning
<AP-0XX entries>

## Container / image
<AP-0XX entries>

## DAST / dynamic (planned for Stage 5)
<AP-0XX entries>

## Crypto review
<AP-0XX entries>

## Manual review
### AP-0XX · <description>
- **Files**: <glob / list>
- **Covers threats**: <T-###>
- **Technique**: <what to look for and how>
- **Output**: <finding IDs or explicit non-finding notes>

## Install requests (awaiting user approval)
| Tool | Reason | Install command | Decision |
|------|--------|-----------------|----------|
| | | | pending |

## Coverage summary
| Threat | Covered by |
|--------|------------|
| T-001 | AP-003, AP-015 |
| ... | ... |

Threats with zero coverage → either add items above or move to `coverage_gaps.md` with rationale.
