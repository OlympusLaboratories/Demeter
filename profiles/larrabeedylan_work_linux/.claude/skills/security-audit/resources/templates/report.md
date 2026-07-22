# Security audit report — `<project-name>`

**Audit ID**: <stable id>
**Commit / branch**: <sha or "working tree">
**Start — End**: <timestamp — timestamp>
**Reviewer**: Claude Code `security-audit` skill (+ any human reviewers)

---

## 1. Executive summary

<≤ one page, plain-English. Name the threats that mattered. Name the fixes. Name the residuals. State confidence specifically.>

## 2. Scope

### In scope
- <paths / services / components>

### Out of scope
- <explicit exclusions with reason>

### Assumptions
- <what was mocked>
- <what credentials or sandboxes were used>
- <what external services were not contacted>

### Sandbox limitations
<e.g., "no AWS sandbox available; IAM findings are code-only">

## 3. Methodology

### Stages executed
- [ ] Recon
- [ ] Threat model
- [ ] Audit plan
- [ ] Static audit
- [ ] Active pen test
- [ ] Remediation plan + user gate
- [ ] Remediation
- [ ] Adversarial verification
- [ ] Final report

### Tools used
| Tool | Version | Purpose |
|------|---------|---------|
| | | |

### Manual techniques
<taint tracing; authz matrix; race-condition PoCs; etc.>

## 4. Findings

### Summary
| ID | Title | Sev | CWE | Location | Status |
|----|-------|-----|-----|----------|--------|
| SA-001 | | | | | fixed |

### Per-finding narrative
<one paragraph per finding, suitable for a non-auditor reader>

## 5. Fix evidence

For each fixed finding:

### SA-XXX fix evidence
- **Diff summary**: <paths touched, line counts, behavior change>
- **Tests**: <test names, all green post-fix>
- **Mutation test**: <pass — reverting the fix causes post-fix test to fail>
- **SAST re-run**: <clean>

## 6. Pen-test evidence appendix

For each exploited finding:

### SA-XXX exploit evidence
- Payload: <verbatim>
- Request: <short>
- Response: <short, redacted>
- Observed impact: <what the attacker got>
- Evidence path: `.security-audit/evidence/SA-XXX/`

## 7. Residual risks and follow-ups

Items the skill cannot fix in code:
- **Secret rotation**: <which secrets, which vendors, which owner>
- **Dependency cadence**: <recommendation>
- **Monitoring / alerting**: <what to add>
- **WAF / edge rules**: <what to add>
- **Runtime protection**: <RASP / eBPF policy / admission control>
- **SBOM in CI**: <command template, where to store>
- **Artifact signing / SLSA**: <target level, migration outline>
- **Branch protection**: <required reviews, status checks, signed commits>
- **CODEOWNERS**: <security-sensitive paths>
- **Security headers at edge**: <list>
- **Secret manager migration**: <target, scope>
- **Incident response playbook**: <what to update>

## 8. CI integration recommendations

### Every PR
- <tool/test suite>
- <expected runtime>
- <fail threshold>

### Nightly
- <tool/test suite>

### Weekly
- <tool/test suite>

### Suggested fail policy
- Fail CI on: critical, high in new code.
- Warn on: medium.
- Inform on: low.

## 9. Re-audit cadence

Recommend: <quarterly | on architectural change | event-driven> — with reasoning.

## 10. Appendix

### A. Tool invocations (reproducibility)
| Tool | Version | Command line |
|------|---------|--------------|
| | | |

### B. Redacted secrets discovered
| Location | Pattern type | Last-4 | Rotation owner |
|----------|--------------|--------|----------------|
| | | | |

### C. Coverage gaps
<refer to coverage_gaps.md>

### D. Blockers
<refer to blockers.md>
