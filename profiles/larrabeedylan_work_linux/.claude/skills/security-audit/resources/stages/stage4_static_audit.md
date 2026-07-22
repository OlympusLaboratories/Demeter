# Stage 4 — Deep Static Audit

Goal: execute the static portion of the audit plan, combine scanner output with human reasoning, and produce triaged findings. "Scanner flagged it" is not a finding; judgment is.

## Entry conditions

- `audit_plan.md` is complete.
- `state.json.stage4.status` is `pending` or `in_progress`.
- Required tools are installed (or gaps recorded).

## Execution discipline

Run each plan item; for each, log its full invocation to `.security-audit/tool-logs/<tool>-<ts>.log`. Capture stderr too. Record the tool version alongside the log.

### For each scanner alert

Triage into one of three buckets:

1. **True positive.** Read the code around `file:line`. Confirm the data-flow claimed by the scanner is real. If the source-to-sink taint is genuine and unsanitized (or sanitized incorrectly), promote to a finding.
2. **False positive.** Common reasons: scanner sees `eval` in a test fixture; taint is broken by framework serializer; the "raw query" is a constant string with no user input. Document the dismissal reason on one line — do **not** silently drop.
3. **Needs dynamic validation.** The static picture is suggestive but not conclusive. Add a marker to `pentest_results.md` Stage 5 queue with the question to answer.

Never promote an alert without reading the surrounding 30–80 lines of real code.

### Manual-review items

Execute them in order. For each file/handler queued in Stage 3:

- Read the handler end-to-end.
- Identify every sink and every source.
- Check the authorization enforcement at this specific handler (middleware claims don't count).
- Check the tenant/ownership scoping.
- Check the input validation and sanitization at each boundary crossing.
- Check error-handling for info leakage (stack traces, internal IDs, path disclosure).
- Check logging for credential or PII exposure.
- Check the happy path AND each failure branch.

Things that often hide:

- **"Validated in middleware" that is only applied to some routes.** Read the router registrations; confirm the middleware is on this route.
- **`next()` without `return`.** The handler continues after the check fails. Bug + security flaw.
- **Authz based on the request body (`body.userId`) instead of the session (`session.userId`).** Trivially spoofable.
- **Ownership check after the mutation.** TOCTOU-adjacent; the mutation already happened.
- **`findById` instead of `findByIdForOwner`.** The first step of most IDOR bugs.
- **"Internal" endpoint with no auth because it's behind a reverse proxy.** The reverse proxy is reachable from the VPC by design; "internal" does not equal "safe".
- **`DEBUG = True` in non-local config, verbose stack traces.** Especially in Django/Flask/Rails prod.
- **Test routes in prod build.** `/test/*`, `/health/dump`, `/debug/pprof`.
- **Crypto wrappers that call the raw primitive.** "our encrypt function" that is AES-ECB with a static IV.
- **JWT libraries with alg-confusion defaults.** Check every decode site for an explicit alg allow-list.

### Config, IaC, container review

- Dockerfiles: `USER` present and non-root, base image pinned by digest, `ADD` only for tarball extraction otherwise `COPY`, no apt cache leakage, no secrets baked in, `HEALTHCHECK` present if long-running, signal-handling correct.
- Kubernetes: `runAsNonRoot: true`, `readOnlyRootFilesystem: true` where feasible, dropped capabilities, no `hostPath`/`hostNetwork`/`hostPID` without justification, `automountServiceAccountToken: false` where not needed, PodSecurity admission ≥ `baseline`, NetworkPolicy present for sensitive namespaces, resource limits set.
- Cloud IaC: no public `0.0.0.0/0` ingress to non-public services, S3 buckets with `BlockPublicAccess` and encryption, RDS with encryption and backups, IAM policies scoped (no `Resource: "*"`, `Action: "*"`), KMS key policies not permissive, secrets not in Terraform state (state encryption + backend lock).
- Application config: `DEBUG`, `APP_ENV`, `NODE_ENV`, framework-specific: correctly set for the target, no `trust proxy` blindly set to `true` unless behind a trusted LB, cookie secrets not defaults (`keyboard cat`, `changeme`).

### Dependency & supply-chain triage

For every SCA finding:
- Confirm the vulnerable version is actually imported (direct vs transitive, prod vs dev dep).
- Confirm the vulnerable code path is reachable (reachability analysis where tooling supports it, else reasoned read).
- Check whether a fix version exists; if not, document the mitigation options (pin, patch, vendor, remove).
- Flag dev-dep findings at lower severity unless the dev dep executes on CI with secrets.

For lockfile issues: `npm ci`/`pnpm install --frozen-lockfile`/`yarn install --immutable` should succeed without modification; if not, the lockfile is drifted.

### Secret scan triage

- Redact to the last 4 characters when writing to `findings.md`.
- Classify: active-looking (high-entropy, matches a vendor prefix) vs placeholder (obvious test key) vs example (clearly documented as such).
- Active-looking secrets = Critical finding, rotation recommended immediately regardless of remediation of surrounding code.
- For git-history leaks, recommend BFG/git-filter-repo + force-push coordination ONLY as a separate explicit request, not as automatic remediation.

## Writing findings

Every true positive becomes an entry in `findings.md` with a stable ID (`SA-001`, `SA-002`, ...). Use the template. Required fields:

- `id`
- `title` (one line, action-oriented: "SQL injection in /api/search `q` parameter")
- `severity` (`critical | high | medium | low | info`) and CVSS v3.1 vector string
- `cwe` (primary CWE ID)
- `asset` (what's protected that this endangers)
- `location` (repo path `:` line; multi-location = bullet list)
- `code` (a short excerpt from the vulnerable site, ≤ 20 lines)
- `attacker_persona` (from threat model)
- `exploit_scenario` (narrative — what the attacker does, step by step)
- `preconditions`
- `blast_radius`
- `proposed_remediation`
- `remediation_complexity` (`trivial | moderate | significant | architectural`)
- `references` (CWE page, vendor advisory, RFC, framework docs)
- `status` (at this stage, always `open`)
- `stage_validated` (`static` now; may become `dynamic` after Stage 5)
- `evidence` (link to evidence folder — populated in Stage 5 for exploited findings)

If a finding deserves dynamic validation, set `validation_next: stage-5-<category>` in the entry so Stage 5 picks it up.

### Severity calibration

Modulate CVSS based on project context:

- Internal-only service behind mTLS → AV:N is still Network, but *Attack Complexity* and *Privileges Required* shift. Do not artificially lower; annotate in the narrative.
- Data sensitivity: PII, health, financial, credentials → C/I/H.
- Public-facing SaaS vs. single-tenant self-hosted → scope (S:C) differs.
- Already-exploited-in-the-wild CVE in a loaded dep → E/F functional on temporal vector.

### Append-only discipline

Findings are never rewritten. If a later stage changes understanding (e.g., Stage 5 proves exploitability you thought was theoretical), append a follow-up entry that references the original:

```markdown
### SA-007-u1 · Follow-up on SA-007 — exploit demonstrated
- **References**: SA-007
- **Update**: Stage 5 PoC test_SA_007_sqli_on_search_q.py confirmed boolean-based extraction in 43s against seeded sandbox DB.
- **New evidence**: .security-audit/evidence/SA-007/
- **Severity**: upgraded from High to Critical (AV:N/AC:L → previously AC:H).
```

## Exit conditions

- Every scanner alert is triaged (TP/FP/defer).
- Every manual-review item has a result (finding OR explicit non-finding note).
- `findings.md` contains all Stage 4 true positives with stable IDs.
- `pentest_results.md` queue section lists all items needing Stage 5 validation.
- `state.json.stage4` is `completed` with a counts snapshot:
  ```json
  "counts": {"critical": 0, "high": 3, "medium": 8, "low": 5, "info": 2,
             "false_positives_dismissed": 14, "deferred_to_stage5": 6}
  ```
