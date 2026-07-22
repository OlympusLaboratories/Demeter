# Stage 6 — Remediation Plan & User Gate

Goal: translate validated findings into a precise, prioritized, approvable fix plan. **STOP** after presenting it. No code changes before explicit user approval.

## Entry conditions

- `findings.md` and `pentest_results.md` are complete for this iteration.
- `state.json.stage6.status` is `pending` or `in_progress`.

## Authoring the plan

Open `remediation_plan.md` (from template) and for each open finding write a block:

```markdown
### Fix SA-007 — Parameterize SQL in search handler
- **Targets**: `src/api/search.ts:41-68`
- **Fixes finding(s)**: SA-007 (and supersedes deferred SA-019 in threat model)
- **Threat(s) realized**: T-003, T-017
- **Proposed change**:
  - Replace string-concatenated `SELECT ... '${q}'` with parameterized query via the existing query builder.
  - Drop the now-unused `escapeSQL()` helper that gave false confidence.
  - Reject non-string `q` before the query (defense in depth).
- **Fix complexity**: moderate (touches one handler + its unit tests; adds one helper param)
- **Fix risk**: low — parameterization is semantically equivalent; behavior changes only on previously-exploitable inputs.
- **Order**: batch 1 (before any XSS fix in the same response path)
- **Root-cause vs symptomatic**: root-cause (query builder API), not a WAF rule or sanitizer patch.
- **Tests that must pass post-fix**:
  - `tests/security/test_SA_007_sqli_on_search_q.py::test_boolean_extraction` — post-fix assertion path
  - `tests/security/test_SA_007_sqli_on_search_q.py::test_fuzz_q_never_reaches_db_string_concat` — property test
  - existing `tests/api/test_search.py` — regression
- **Affected dependents**: none beyond the handler.
- **Rollback**: revert the handler change; tests will fail.
```

### Ordering heuristic

- **Root cause before symptom.** A parameterized query replaces the need for blacklist sanitization.
- **Authz before output encoding.** An IDOR that returns unsanitized HTML is not fixed by XSS filtering.
- **Authn before authz.** If auth is bypassable, per-resource checks are moot.
- **Signing/integrity before input validation.** If payloads can be forged, validating contents is secondary.
- **Supply-chain and secret rotation have independent critical paths** — plan them in parallel.
- **Defer low-severity, architectural-fix items** unless they block other fixes.

### Architectural vs local fixes

Flag items that cannot be fixed in-place. Examples:

- Authorization logic that must be moved from per-handler to a policy layer.
- Secret storage that must move from `.env` file to a secrets manager.
- JWT verification that must gain a key rotation / JWKs pull mechanism.
- Tenant isolation that must become row-level policy in the DB rather than app-layer filters.

For these, describe the migration shape, not just the patch. Propose: immediate mitigation (e.g., rate limit + audit log) + longer-term architectural fix.

## The user gate

After the plan is written, present in chat:

1. A one-paragraph summary: counts by severity, the 3 highest-impact findings, architectural items that require decision.
2. A link to `remediation_plan.md` for full detail.
3. The approval options:
   - `all` — proceed to remediate every fix.
   - `severity ≥ high` — remediate critical and high, defer medium/low.
   - `severity ≥ critical` — critical only.
   - `by id: SA-001, SA-007, ...` — explicit list.
   - `by category: authz, injection` — categories.
   - `none` — stop; produce report only.

Record the exact approval in `remediation_plan.md` under an `## Approval` section with timestamp and verbatim user reply. If the user approves a subset, list which finding IDs are **in scope** and which are **deferred**.

## Must-nots

- Do not modify code in this stage.
- Do not assume approval from previous runs. Always re-ask.
- Do not accept an approval that is ambiguous. Ask for a specific scope.
- Do not expand the plan beyond what the findings justify. No "while we're there" refactors.
- Do not include cosmetic changes (reformatting, renaming, type annotations) in a security plan unless they are the fix.

## Exit conditions

- `remediation_plan.md` is complete with one block per finding.
- An `## Approval` section records the user's decision and the in-scope set.
- `state.json.stage6` is `completed` with `approved_ids: [...]` and `deferred_ids: [...]`.
