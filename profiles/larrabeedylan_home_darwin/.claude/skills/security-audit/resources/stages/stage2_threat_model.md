# Stage 2 — Threat Modeling

Goal: reason about what can go wrong, for whom, and how — so Stages 3–5 know what to test. Tool output does not substitute for this step. If recon missed surface, this stage uncovers it — update `recon.md` before proceeding.

## Entry conditions

- `recon.md` is complete with detected project classes.
- The relevant methodology files (from `recon.md` line "Methodology files to apply:") have been read.
- `state.json.stage2.status` is `pending` or `in_progress`.

## Frames to apply (in order)

### 1. STRIDE per component

For each component in the recon inventory (HTTP surface, CLI, queue consumer, scheduler, storage layer, external integration, admin plane, IaC module):

| Letter | Question |
|--------|----------|
| S — Spoofing | Can an attacker impersonate a user, service, or origin? Check identity issuance, token scope, origin validation, mTLS verification, webhook signature verification. |
| T — Tampering | Can an attacker modify requests, state, stored data, or build artifacts undetected? Check integrity (HMAC, signatures), client-side trust, idempotency, storage ACLs. |
| R — Repudiation | Can an action be performed without an auditable trail? Check logging of sensitive actions, log integrity, admin-action provenance. |
| I — Information disclosure | Can an attacker read data they shouldn't? Check error verbosity, stack traces, timing leaks, cache leakage, authz, PII in logs, public storage buckets. |
| D — Denial of service | Can an attacker exhaust resources disproportionately? Check rate limits, algorithmic complexity, unbounded allocation, connection limits, backpressure. |
| E — Elevation of privilege | Can an attacker gain higher role or tenant access? Check role checks at the object and function level, impersonation features, break-glass paths, SSRF into admin, deserialization sinks. |

### 2. Data-flow trust boundary analysis

For each trust boundary identified in recon, state the invariant that must hold and the code that enforces it. Examples:

- Boundary: **user → HTTP handler**. Invariant: every body field is either explicitly allowed or rejected. Enforcement: schema validator location. Risk if absent: mass assignment / BOPLA.
- Boundary: **app → SQL**. Invariant: every query parameter is bound, never concatenated. Enforcement: ORM or `?`-placeholder; check raw-query escape hatches.
- Boundary: **app → shell**. Invariant: no string-concatenated command lines. Enforcement: `execFile`/`subprocess.run([...], shell=False)`.
- Boundary: **app → fs**. Invariant: path is anchored under a known root; `..` and absolute paths rejected. Enforcement: `realpath` normalization + prefix check.
- Boundary: **app → external HTTP**. Invariant: destination is an allowlisted host; internal RFC1918 / metadata IPs rejected. Enforcement: URL parser + allow-list + DNS re-resolve after redirect.
- Boundary: **tenant A → tenant B**. Invariant: every object fetch and every listing is scoped by tenant. Enforcement: row-level policy or handler-level `where tenant_id = :current`.

### 3. Attacker personas

Enumerate realistic attackers and what each can do:

- **Unauthenticated external.** Can hit public routes, read public data, register if open. Cannot read authenticated responses. Relevant threats: injection, auth bypass, SSRF, enumeration, DoS.
- **Authenticated low-privilege user.** Has a valid session. Relevant threats: IDOR/BOLA, horizontal privilege escalation, mass assignment to elevate role, business-logic abuse.
- **Authenticated admin or privileged user.** Lower prior, but models insider risk. Relevant threats: audit-log evasion, data exfiltration, backup theft.
- **Cross-tenant attacker.** Has an account in tenant B, tries to reach tenant A's data. Relevant threats: multi-tenancy bypass, shared-cache poisoning, shared-secret reuse.
- **Compromised dependency.** A transitive package is hostile. Relevant threats: postinstall scripts, runtime payloads, CI exfil, typosquat swaps.
- **Compromised CI runner.** Attacker controls a build job. Relevant threats: artifact poisoning, secret theft from env, cache poisoning, signed-artifact forgery.
- **Malicious insider / compromised developer machine.** Commits backdoor code. Relevant defensive controls: CODEOWNERS, required reviews, branch protection, signing.
- **Physical/network-adjacent.** For firmware or desktop: local USB, BLE, same-Wi-Fi attacker. For web: captive-portal MITM, browser-extension attacker.
- **LLM prompt attacker.** For LLM pipelines: sends content (directly or via retrieved document / tool output) intending to override system instructions or trigger unauthorized tool calls.

Not every persona applies to every project — select based on recon.

### 4. Project-specific risk classes

Pull from the loaded methodology files. Common clusters:

- **Payments / billing.** Idempotency, replay, TOCTOU on balance, rounding, currency confusion, negative quantities, discount stacking, refund abuse.
- **Auth/identity provider features.** Password reset oracle, account linking confusion, email verification bypass, OAuth redirect_uri flaws, JWT misuse.
- **Multi-tenant SaaS.** Tenant isolation in DB, in cache keys, in event topics, in storage buckets, in logs.
- **Upload/download.** Zip slip, MIME sniffing, served-as-HTML from same origin, polyglot files, SSRF via image parsers, image-library CVEs.
- **Admin surface.** Forced browsing to `/admin`, same auth as user routes, debug endpoints (`/debug/pprof`, `/_profiler`, `/actuator/**`), undocumented impersonation features.
- **Scheduled/background work.** Unauthenticated callback endpoints for "internal" triggers, SSRF via job URLs, job-argument injection.
- **LLM app.** Direct + indirect prompt injection, tool-call abuse, markdown exfil via rendered links/images, system-prompt leakage, training-data or embedding leakage.
- **Smart contract.** Reentrancy, oracle manipulation, access control on upgrade/initializer, signature replay, tx.origin auth, unchecked calls.
- **IaC.** Public exposure of storage/DB, overly permissive IAM, secrets in state, bucket logging off, no encryption at rest, missing backups, no audit trail.
- **Mobile.** Insecure storage, cert pinning, WebView bridge, deep-link hijack, tapjacking, reverse-engineering resilience for integrity-critical checks.
- **Firmware.** Secure boot, debug interfaces, OTA authenticity, rollback protection, side-channels for sensitive operations.

### 5. Business-logic abuse cases

Read what the product actually promises. For each user-facing capability, ask: "what would an attacker do if they wanted to abuse this specific behavior?" Examples:

- Signup flow → rate-limit evasion via IP rotation, email alias tricks (`+tag`, unicode homoglyphs), disposable-email acceptance.
- Coupon/promo → stacking, negative multipliers, replay after expiry, race to apply multiple coupons concurrently.
- Inventory/limited drop → concurrent purchase to exceed per-user cap, reserve-and-abandon to starve others.
- Password reset → token reuse, token leakage via Referer, link predictability, out-of-band email change right before reset.
- Referral → self-referral via alt account, bot-driven referral farming, reward issuance without referee retention.
- File sharing → unguessable URL that is also unrevocable, link enumeration, expiring link that doesn't actually expire on server side.
- Export / "download my data" → exfiltration channel, timing amplification, side-channel for data the user shouldn't see.
- Impersonation feature ("view as user") → persistence of impersonation session, audit gap, privilege retention on switch-back.

## Writing `threat_model.md`

Use the template. Each threat entry is a short, structured block:

```markdown
### T-014 · Cross-tenant IDOR on /api/documents/:id
- **Frame**: STRIDE-I (Information disclosure) + BOLA
- **Persona**: authenticated low-privilege user in tenant B
- **Asset**: tenant A documents and their metadata
- **Vector**: enumerate or guess document IDs; handler fetches by ID without tenant scoping
- **Prerequisites**: valid account in any tenant; knowledge of ID format (UUID vs int)
- **Expected impact**: confidentiality breach across tenants; GDPR-relevant
- **Evidence hooks**: `src/documents/handler.ts:84` fetches by ID; tenant-scoping not visible in surrounding code
- **Planned validation**: Stage 4 — verify every document-handler; Stage 5 — PoC as user-A vs user-B
```

Rank the threat list. Suggested rubric:

- **Critical**: unauthenticated RCE, authz bypass that exposes cross-tenant or admin data, credential theft at scale.
- **High**: authenticated privilege escalation, SQLi with data impact, CSRF on state-change with real effect, SSRF to metadata, signed-artifact forgery.
- **Medium**: XSS with session access, auth weaknesses requiring preconditions, information disclosure of non-PII, CSRF with limited impact.
- **Low**: info disclosure of innocuous data, missing defense-in-depth headers, verbose errors without secrets.

## Exit conditions

- `threat_model.md` contains a ranked list covering every trust boundary and every entry point.
- Every threat names the persona, asset, vector, prerequisites, and planned validation approach.
- If new surface was discovered during threat modeling, `recon.md` has been updated.
- `state.json.stage2` is `completed`.
