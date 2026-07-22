# Stage 7 — Remediation

Goal: apply the approved fixes. Root-cause fixes preferred. Preserve style and conventions. No git operations beyond local edits.

## Entry conditions

- `remediation_plan.md` contains an `## Approval` section with an explicit in-scope list.
- `state.json.stage7.status` is `pending` or `in_progress`.

## Execution rules

1. **Only touch approved findings.** The in-scope set is in `state.json.stage7.approved_ids`. Do not drift.
2. **Root cause first.** Parameterize, don't blacklist. Enforce authorization in policy, don't patch one handler. Replace weak crypto, don't add a warning.
3. **Preserve code style and conventions.** Match existing formatter config, import order, naming, comment style. Do not reformat unrelated code.
4. **Minimize diff.** Fix the bug. Do not "improve" adjacent code, add docstrings, or rename variables that were fine.
5. **Comment only when non-obvious.** If the fix protects a subtle invariant, add one line referencing the finding ID: `// SA-007: keep parameterization — see audit.` Do NOT add verbose explanatory paragraphs.
6. **Defense in depth is a separate change** from the root cause. Land the root-cause fix first; if the plan includes defense-in-depth, commit to both but order them.
7. **Update `findings.md`** — append a remediation entry referencing the original finding ID with a diff summary (paths touched, line counts added/removed, behavior change one-liner).
8. **Re-run the flagging scanner on touched files.** If semgrep flagged it, re-run semgrep on the touched paths only. If the flag persists, the fix may not have addressed the scanner's concern — investigate before marking done.
9. **No auto-commit, no auto-push, no PR creation, no branch creation.** Remediation = local edits only. If the user separately asks to commit, that is a distinct request the user must make explicitly.
10. **Never use `--no-verify`, `git reset --hard`, or any destructive shortcut.** If pre-commit hooks exist, run them; fix failures properly.

## What each fix looks like

- **Injection fixes**: parameterization (SQL, shell via `execFile`, LDAP escaping via library, XPath via library, template via context-escaped render, JSON parsing without type hints). Remove any custom sanitization the fix makes obsolete; do not leave dead escape helpers.
- **Authn fixes**: switch JWT to explicit alg allow-list, add key rotation support if needed, adopt `hmac.compare_digest` / `crypto.timingSafeEqual` / `subtle.ConstantTimeCompare`, add rate limits on sensitive endpoints (login, reset, MFA, OTP), reduce session lifetime, rotate session on privilege change.
- **Authz fixes**: prefer a policy layer (OPA/Cedar/oso, or a single `authorize(user, action, resource)` helper called at every handler). For IDOR/BOLA: fetch-by-owner (`findByIdForUser(id, userId)`) rather than post-hoc checks. For BOPLA/mass assignment: explicit field allow-list per action.
- **Crypto fixes**: replace ECB with AES-GCM/ChaCha20-Poly1305; replace HMAC with constant-time compare; switch password hash to argon2id with calibrated parameters; replace MD5/SHA-1 on security paths.
- **Deserialization fixes**: switch pickle to JSON + schema; `yaml.load` to `yaml.safe_load`; Jackson disable default typing or pin allowed classes; Java: avoid `ObjectInputStream` for untrusted input; Node: never `eval` JSON.
- **SSRF fixes**: URL parse → allow-list hosts → re-resolve DNS to check final IP → disallow RFC1918 / link-local / metadata / `::/0`; disable redirect following or re-check per hop; use a per-outbound-call HTTP client with these controls baked in.
- **XSS fixes**: context-aware escaping at the template layer; CSP with nonces (not `unsafe-inline`); `X-Content-Type-Options: nosniff`; `HTML sanitizer` (DOMPurify with strict config) for rich text; serve uploads from a separate origin or with `Content-Disposition: attachment`.
- **CSRF fixes**: SameSite=Lax or Strict cookies + double-submit or synchronizer-token for mutations; JSON-body requests with custom headers also defense-in-depth.
- **CORS fixes**: allow-list of exact origins; never reflect `Origin` with credentials; disallow `*` with credentials; do not match origin with a naive regex.
- **Headers**: add `Content-Security-Policy`, `Strict-Transport-Security` with preload, `X-Frame-Options: DENY` or CSP `frame-ancestors`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` reducing feature surface.
- **Upload fixes**: allow-list MIME after magic-byte sniff; content-disposition: attachment OR separate origin for untrusted content; randomized filenames; size cap; explicit extraction root with realpath+prefix check; reject symlinks.
- **Container/K8s fixes**: non-root user, pinned base image digest, capabilities dropped, `readOnlyRootFilesystem`, resource limits, NetworkPolicy, `automountServiceAccountToken: false` where possible.
- **IaC fixes**: close public exposure, enable encryption, tighten IAM (no `*`), move state to encrypted backend with locking, enable logging/audit.
- **LLM fixes**: sanitize rendered output (strip `javascript:`, external images), add tool-call authorization per tool, validate tool arguments via schema, segregate system prompts in a way that user input cannot concatenate, add retrieval filters.
- **Smart contract fixes**: checks-effects-interactions, OpenZeppelin `ReentrancyGuard`, `AccessControl` modifiers, initializer protection on upgradeable proxies, replace `tx.origin`, use `SafeERC20`/`SafeCast`, chainId-bound signatures.

## Dealing with structural surprises

If a fix reveals a broader issue (e.g., "this handler is one of twenty with the same pattern"):

- Stop the fix.
- Note the broader finding in `findings.md` as a new entry (`SA-0XX`) with `validation_next: stage-4-or-5` to round-trip it through the normal triage.
- Bring it to the user before expanding the remediation scope. Don't unilaterally grow the blast radius of a remediation session.

## Secret rotation

Remediation of leaked-secret findings is a two-part action:

1. Remove the secret from the codebase (commit to the working tree; do NOT rewrite git history automatically).
2. Recommend rotation at the issuer (vendor console, KMS, etc.). The skill does not rotate secrets itself.

Document in `findings.md` remediation entry: "secret removed from source; rotation at issuer required (not performed by skill)".

## Exit conditions

- Each approved finding has a remediation entry in `findings.md` with a diff summary.
- Scanner re-run on touched files shows the flagged pattern is gone (or the scanner's continuing complaint is documented as a non-issue with reasoning).
- `state.json.stage7` is `completed` with `fixed_ids: [...]`, `deferred_ids: [...]` (for items that turned out to need Stage 6 re-planning).
