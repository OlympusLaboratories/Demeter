# Findings — `<project-name>`

> Populated by Stages 4 (static), 5 (dynamic), 7 (remediation), 8 (verification).
> **Append-only**. Never rewrite existing entries — add a follow-up entry referencing the prior ID.

## Index
| ID | Title | Severity | CWE | Location | Status |
|----|-------|----------|-----|----------|--------|
| SA-001 | | | | | open |

## Findings

### SA-001 · <title>
- **Severity**: <critical | high | medium | low | info>
- **CVSS v3.1**: `<vector>` → <score>
- **CWE**: CWE-<id>
- **Asset**: <what's at risk>
- **Location**:
  - `<path>:<line>` — <note>
- **Code**:
  ```<lang>
  <≤ 20 lines, unmodified>
  ```
- **Attacker persona**: <from threat model>
- **Exploit scenario**: <step-by-step narrative>
- **Preconditions**: <account, knowledge, network position>
- **Blast radius**: <what does success give the attacker>
- **Proposed remediation**: <approach, not the patch itself>
- **Remediation complexity**: <trivial | moderate | significant | architectural>
- **References**: <CWE page, CVE, RFC, framework docs, OWASP>
- **Status**: open
- **Stage validated**: static
- **Validation next**: <stage-5-category | n/a>
- **Evidence**: <.security-audit/evidence/SA-001/ — populated in Stage 5>

---

<!-- Follow-up entries reference the original ID. Example: -->

### SA-001-u1 · Follow-up on SA-001 — exploit demonstrated
- **References**: SA-001
- **Update**: <what changed in understanding>
- **New evidence**: <path>
- **Severity change**: <if any, with CVSS delta>
- **Status**: <open | fixed | accepted-risk | deferred | blocked | false-positive>

### SA-001-r1 · Remediation of SA-001
- **References**: SA-001
- **Patch summary**: <paths touched, line counts, one-liner on behavior change>
- **Scanner re-run on touched files**: <clean | alert persists with reason>
- **Tests added**: <test names>
- **Status**: fixed

### SA-001-v1 · Verification of SA-001 fix
- **References**: SA-001
- **Pre-fix assertion**: <pass/fail> — <explanation>
- **Post-fix assertion**: <pass/fail> — <explanation>
- **Mutation test**: <pass/fail> — <explanation>
- **Regression**: <project suite status>
- **SAST on touched files**: <clean/alerts>
- **Outcome**: <verified | needs re-fix | blocked>
