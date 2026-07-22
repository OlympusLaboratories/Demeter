# Stage 9 — Final Report

Goal: produce `report.md` — the single deliverable for a reader who was not in the loop. Accurate, grounded, non-alarmist. One-screen summary in chat at the end; everything else in the report.

## Entry conditions

- All prior stages complete (or explicitly marked incomplete with rationale).
- `state.json.stage9.status` is `pending` or `in_progress`.

## Structure of `report.md`

Use the template and fill every section. Keep language plain and specific.

### 1. Executive summary (≤ 1 page, plain-English)

Audience: engineering leadership. No acronym soup. Cover:

- What was audited (project name, commit/branch audited, scope).
- Threats that mattered (2–5 lines): the highest-impact realistic attacks, named in product language, not CWE numbers.
- What was fixed in this audit (counts by severity).
- What is deferred and why.
- Residual risk and confidence level: specific, not "we are now secure". Example: "An authenticated low-privilege user cannot enumerate documents across tenants in the scope tested; OAuth flows and the payment handler were out of scope. Confidence: medium-high for the tested surface."

### 2. Scope

- In-scope paths, services, components.
- Out-of-scope items and the reason (not deployed, third-party, no sandbox, explicit user exclusion).
- Assumptions made during testing (what was mocked; what credentials/sandboxes were used).
- Sandbox limitations.
- Audit window (start and end timestamps).

### 3. Methodology

- Stages executed. Note any stage that was skipped with rationale.
- Tools used, with versions. Include the command line template for each.
- Manual techniques applied (taint tracing, authz matrix, race-condition PoCs, etc.).
- Reviewer: Claude Code `security-audit` skill, iteration N. Human reviewer (if any) and their role.

### 4. Findings list

Tabular summary first (ID, title, severity, CWE, location, status):

| ID | Title | Sev | CWE | Location | Status |
|----|-------|-----|-----|----------|--------|
| SA-001 | … | … | … | … | fixed |

Then a per-finding narrative (one paragraph each):

```markdown
#### SA-007 · SQL injection on `/api/search` `q` parameter — fixed

Discovered via semgrep SQL-concat rule, confirmed by reading `src/api/search.ts:41-68`. An unauthenticated attacker submitting `?q=' OR ...` boolean-based payloads could extract arbitrary data from the `users` table, including bcrypt password hashes. Demonstrated in `tests/security/test_SA_007_sqli_on_search_q.py` with a 43-second extraction against the seeded sandbox DB. Fix: replaced string concatenation with parameterized query via the existing `db.select()` builder; removed the now-unused `escapeSQL` helper. Verification: pre-fix assertion still fails on the snapshot, post-fix assertion passes (400 response), mutation test confirms the PoC is non-vacuous. CWE-89. CVSS v3.1 9.8 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H).
```

Status values: `fixed | deferred | accepted-risk | false-positive-upon-review | blocked`.

For every deferred/accepted-risk item, include the rationale in the narrative — a deferral without a reason should not exist in this document.

### 5. Fix evidence

For each fixed finding: diff summary, test names that prove the fix, mutation-test result. One small block per fix.

### 6. Pen-test evidence appendix

For each exploited finding:

- Payload(s) tried and the one that worked.
- Request/response pair (redacted).
- Observed impact (what the attacker read/wrote/executed).
- Evidence path under `.security-audit/evidence/`.

### 7. Residual risks and follow-ups the skill could not address

Non-code items, explicit:

- Secret rotation at issuers (list which secrets, which vendors, which owner).
- Dependency upgrade cadence recommendation (monthly minor, quarterly major review, weekly advisory sweep).
- Monitoring/alerting additions (which logs, which metric thresholds, which alert destinations).
- Edge/WAF rules (if the architecture includes a WAF).
- Runtime protection (RASP, eBPF policy, admission control, app-layer firewall).
- SBOM generation in CI and artifact signing (cosign, SLSA provenance).
- Branch protection rules (required reviews, required status checks, signed commits).
- CODEOWNERS entries for security-sensitive paths.
- Incident response playbook updates.
- Security header deployment at the edge (CSP, HSTS preload).
- Secret management migration (env file → secrets manager).

### 8. CI integration recommendations

Which of the added security tests belong in CI:

- Every PR: fast SAST (`semgrep --config .semgrep.yml`), lockfile-drift check, secret scan, the security test suite.
- Nightly: full SCA (`osv-scanner`, `trivy fs`), container image scan, DAST baseline against staging.
- Weekly: coverage-guided fuzz harness, dependency-confusion check, typosquat check.
- Fail thresholds: suggest "fail CI on critical or high in new code; warn on medium; inform on low" as a starting policy.

### 9. Re-audit cadence

Recommend based on findings density and change velocity. Starting points:

- Quarterly full re-audit (re-run the skill) for a stable product.
- After any architectural change (auth, data model, tenancy, deployment target).
- After adopting a new framework/major dependency.
- After an incident.

## Chat summary

After writing `report.md`, send the user a single-screen message:

```
Security audit complete.
  Commit:     <short sha or "working tree">
  Findings:   <c> critical · <h> high · <m> medium · <l> low · <i> info
  Fixed:      <n>   Deferred: <d>   Accepted: <a>   Blocked: <b>
  Evidence:   .security-audit/evidence/
  Full report: .security-audit/report.md

Top-3 residual risks:
  1. …
  2. …
  3. …

Recommended next step: <one action item>
```

No more than 15 lines. Do not paste the full report. Do not summarize fixes by repeating the code.

## Exit conditions

- `report.md` is complete and accurate.
- Chat summary delivered.
- `state.json.stage9` is `completed`.
