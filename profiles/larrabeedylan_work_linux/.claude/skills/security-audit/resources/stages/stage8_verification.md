# Stage 8 — Adversarial Verification Loop

Goal: prove each fix works, catch vacuous tests, catch regressions, catch new findings introduced by the fix. Do not hand back to the user until the loop converges.

## Entry conditions

- Stage 7 has produced remediation edits for approved findings.
- `state.json.stage8.status` is `pending` or `in_progress`.

## Verification checklist per finding

For each finding fixed in Stage 7:

### 1. Pre-fix assertion still fails on unpatched code

The PoC test has two assertion branches: pre-fix (against a snapshot of the unpatched behavior) and post-fix (against current code).

- If the pre-fix branch is backed by a **snapshot fixture** (recorded HTTP trace of the unpatched run), verify the fixture is still present and hashes match.
- If the pre-fix branch is a **live-against-old-code** run, spin up a separate worktree/container on the pre-remediation commit/snapshot and execute the PoC there.
- Either path must produce the exploit outcome.
- Purpose: prove the PoC is meaningful. A test that always passes (because the attack "sort of worked" even unpatched) is vacuous.

### 2. Post-fix assertion passes on current code

Run the PoC against the current, post-remediation code. The exploit must fail cleanly:

- Correct error status (typically 400, 401, 403, or 422 — not 500).
- No partial state change (DB diff clean).
- No secret in response.
- No stack trace or verbose error disclosing internals.
- No 200 OK with a weasel error body.

If post-fix asserts fail, the fix is wrong or incomplete. Return to Stage 7 for this finding.

### 3. Mutation test

This is the key anti-vacuous-test check. Flip the fix and confirm the post-fix test now fails:

- In-memory revert: apply a single-line mutation that undoes the fix (re-concatenate the SQL, remove the constant-time compare, revert the JWT alg allow-list). Run the PoC. It must now fail (detect the attack again).
- If the PoC still passes under the reverted fix, the test is vacuous — the PoC didn't actually exercise the vulnerability the fix addresses. Rewrite the PoC.

For language ecosystems with mutation-testing frameworks (`mutmut`, `stryker`, `pitest`), optionally run them on the fix region as an additional signal.

### 4. Existing tests still pass

Run the project's existing test suite (unit, integration, e2e as applicable). Any regression → return to Stage 7.

### 5. No new static findings on touched files

Re-run the relevant SAST tools on the touched paths only (not the whole repo). Any new alert is either:
- A true new issue introduced by the fix (return to Stage 7),
- A false positive (document in `findings.md` follow-up with reasoning), or
- A previously-suppressed pattern that is now live (evaluate on merit).

### 6. No other finding made worse

Some fixes interact: tightening CSP may break an XSS payload the fix for a different finding depended on. Cross-check the full security test suite — every PoC post-fix assertion must still hold.

## The loop

For each finding:

```
iteration = 0
while iteration < 5:
    run pre-fix check
    run post-fix check
    run mutation check
    run regression check
    run SAST on touched files
    if all green: break
    return to Stage 7 for this finding
    iteration += 1

if iteration == 5:
    record in blockers.md with precise reason
    escalate to user
```

Cap iterations per finding (default 5). Do not silently mark something as fixed if the loop didn't converge.

## When mutation is hard

Some fixes are structural and can't be cleanly reverted one line at a time (e.g., replacing pickle with JSON). For those:

- Use a feature-flag-style in-memory switch during testing that routes requests back through the old path.
- Or assert the **behavior** the fix guarantees (e.g., "the deserializer only accepts a specific schema; any other input is rejected with 400 and no parser state mutation"), and test the negation directly.

Document the alternative approach in the test docstring.

## Writing results

Append a verification block per finding to `findings.md`:

```markdown
### SA-007-v1 · Verification of SA-007 fix
- **References**: SA-007
- **Pre-fix assertion**: pass (exploit succeeded against snapshot `evidence/SA-007/pre/` — admin hash extracted in 47 s)
- **Post-fix assertion**: pass (exploit fails with 400 "invalid search term"; no DB access; 14 ms response)
- **Mutation**: reverted parameterization → post-fix assertion fails as expected
- **Regression**: project suite green (437 tests, 0 failures)
- **SAST on touched files**: semgrep clean, gosec clean
- **Outcome**: fix verified. Status → fixed.
```

Update `findings.md` status of the original `SA-007` to `fixed` via a follow-up entry (append-only). The `state.json` stage 8 progress tracks each finding.

## Exit conditions

- Every approved-and-fixed finding has a verification block and status `fixed`.
- Every finding that could not be verified (within iteration cap) has an entry in `blockers.md` with precise diagnostic detail.
- `state.json.stage8` is `completed` with `verified_ids`, `blocker_ids`.
