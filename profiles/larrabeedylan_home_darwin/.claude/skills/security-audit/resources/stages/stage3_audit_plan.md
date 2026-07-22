# Stage 3 — Resource Gathering & Audit Plan

Goal: translate the threat model into a concrete, reviewable plan — every check to run, the tool or manual technique that performs it, the threats it covers, and the reason it was selected. The plan is the contract between thinking and doing.

## Entry conditions

- `threat_model.md` is complete and ranked.
- `state.json.stage3.status` is `pending` or `in_progress`.

## Tool selection heuristic

Pick tools by language, framework, and threat class — not by habit. For each candidate tool:

1. Is it already installed? (`which`, `--version`, language-native check). Log the version.
2. If missing, state what you want to install, where from (official registry, pinned version), and why. Ask the user. Proceed only on approval. If declined, record the gap in `coverage_gaps.md` and select a manual-review fallback.
3. Record the exact command line you will run. Prefer JSON/SARIF output for downstream parsing.

Never send source to a cloud-hosted scanner without per-run explicit user confirmation. Local execution only by default.

## SAST / linters — by language

Pick language-appropriate tools. At minimum one general SAST (semgrep) + one language-specific where available.

- **Polyglot**: `semgrep --config p/security-audit --config p/owasp-top-ten --config p/r2c-ci` plus language packs (`p/python`, `p/javascript`, `p/typescript`, `p/golang`, `p/java`, `p/ruby`, `p/php`, `p/kotlin`, `p/swift`, `p/rust`, `p/csharp`, `p/secrets`). Use `--json` for ingestion.
- **Python**: `bandit -r .` (add `-c pyproject.toml` if configured), `ruff check --select=S` (bandit-equivalent), `semgrep p/python`. For Django: `p/django`. For Flask: `p/flask`.
- **JavaScript/TypeScript**: `eslint` with `eslint-plugin-security`, `eslint-plugin-no-unsanitized`, `eslint-plugin-security-node`. Node-specific: `njsscan`. Framework-specific: `p/nextjs`, `p/express`.
- **Go**: `gosec ./...`, `govulncheck ./...`, `staticcheck ./...`.
- **Rust**: `cargo audit`, `cargo clippy -- -W clippy::pedantic -W clippy::suspicious`, `cargo geiger` (unsafe surface).
- **Ruby**: `brakeman` (Rails), `bundler-audit check --update`.
- **Elixir/Phoenix**: `mix sobelow`, `mix deps.audit`.
- **Java/Kotlin**: SpotBugs + Find-Sec-Bugs plugin, `dependency-check` (OWASP), Gradle `dependencyCheckAnalyze`.
- **C#/.NET**: `security-scan`, `dotnet list package --vulnerable --include-transitive`, Roslyn analyzers with `Microsoft.CodeAnalysis.NetAnalyzers` + `SecurityCodeScan`.
- **PHP**: `psalm --taint-analysis`, `phpcs-security-audit`, `composer audit`.
- **Swift/Objective-C**: `swiftlint` with security rules, MobSF for packaged IPA review.
- **Kotlin (Android)**: `detekt` with `detekt-formatting` and custom rule sets, MobSF for APK review.
- **Solidity**: `slither .`, `mythril analyze`, `echidna-test` for property-based fuzzing, `halmos` or `foundry invariant` for symbolic.
- **Shell**: `shellcheck -S style`, `checkbashisms` if targeting POSIX.
- **SQL**: `sqlfluff lint --rules=security` where applicable; otherwise manual.

## IaC / container / Kubernetes

- **Terraform / OpenTofu**: `tfsec`, `checkov -d .`, `trivy config .`, `kics scan -p .`, `terrascan scan`.
- **CloudFormation**: `cfn-nag`, `checkov`, `cfn-lint`.
- **Dockerfile**: `hadolint`, `trivy config Dockerfile`, `dockle` on built images.
- **Docker image**: `trivy image <tag>`, `grype <tag>`, `syft <tag>` for SBOM, `dive` for layer inspection.
- **Kubernetes manifests / Helm**: `kubesec scan`, `checkov`, `trivy config`, `kube-linter`, `polaris audit`, `datree test` (if used).
- **Compose**: `trivy config docker-compose.yml`.
- **Ansible**: `ansible-lint` with security rules.

## Dependency & supply chain

Run at least one SCA per language plus a cross-language scanner.

- `osv-scanner --recursive .` (cross-language, OSV.dev db).
- `trivy fs --security-checks vuln,secret,license .`.
- Language-specific: `npm audit --production`, `pnpm audit`, `yarn npm audit`, `pip-audit`, `safety check`, `bundler-audit`, `cargo audit`, `govulncheck`, `composer audit`, `dotnet list package --vulnerable`.
- Lockfile integrity: verify lockfile present and version-pinned; for npm, `npm ci --dry-run` validates integrity.
- Typosquat / confusion check: compare top-level dep names against popular-package lists; flag single-character substitutions, scope-name confusion (`@acme/foo` vs `acme-foo`).
- Private-vs-public namespace check (dependency confusion): confirm private packages are scoped AND that the registry mirror is configured to resolve private-first.
- Postinstall/scripts audit: `npm` packages with `scripts.postinstall` are worth a look; `pnpm` has `onlyBuiltDependencies` — check configuration.
- Maintainer changes: for the top 10 direct dependencies, note last-publish date and maintainer count (via `npm view`, `pip show`, etc.). Recent ownership change is a smell.
- Unsigned packages / vendored binaries: list any checked-in binaries; ask about provenance.

## Secret scanning

- `gitleaks detect --source . --redact --no-git` for working tree.
- `gitleaks detect --source . --redact` for full git history.
- `trufflehog filesystem .` with verification only on explicit user approval (verification sends tokens to issuing services).
- Manual grep for patterns not caught: service URLs with embedded creds, JWT-shaped strings, PEM blocks, API-key prefixes by vendor (`sk_live_`, `AIza`, `ghp_`, `xoxb-`, `AKIA`, etc.) in `.env*`, `config/**`, fixtures, tests, migrations, and seed data.
- Check git history via `git log -p --all -- <suspect-paths>` if history exists.

## DAST / dynamic (Stage 5 uses these; Stage 3 plans them)

- **Web app**: `zap-baseline.py -t <url>` for passive scan; `nuclei -t cves -t vulnerabilities -t exposures -u <url>`; `ffuf`/`feroxbuster` for content discovery seeded from the recon route list.
- **API**: OpenAPI/GraphQL-aware tooling — `schemathesis run --checks all <spec>` for REST; `graphql-cop`, `inql` for GraphQL. Auto-generate negative tests from the schema.
- **SQLi probing on SAST-flagged endpoints**: `sqlmap -u <url> --batch --level=3 --risk=1` bounded and only on sandboxed targets.
- **Container runtime**: `docker-bench-security` on the running container, CIS checks.
- **TLS**: `testssl.sh --quiet <host>` on sandbox endpoints to spot weak cipher suites, cert issues, HSTS absence.

## Crypto audit checks

Plan manual review of:
- Algorithm choice vs current guidance (no MD5/SHA-1 for security, no DES/3DES, no RC4, no ECB, no RSA PKCS1 v1.5 for encryption).
- Key sizes: RSA ≥ 2048, ECDSA/EdDSA on strong curves, AES ≥ 128 in AEAD mode.
- IV/nonce handling: unique per message for GCM/ChaCha20-Poly1305; never reused with the same key.
- Constant-time comparisons for MACs/tokens (`hmac.compare_digest`, `crypto.timingSafeEqual`, `subtle.ConstantTimeCompare`, `sodium_memcmp`).
- RNG source: platform CSPRNG (`crypto.randomBytes`, `secrets` module, `crypto/rand`, `rand::rngs::OsRng`). Never `Math.random`, `random.random`, `rand::thread_rng` for secrets.
- Password hashing: argon2id with memory ≥ 64 MiB and parallelism ≥ 1; scrypt with N ≥ 2^17; bcrypt with cost ≥ 12. Never straight SHA-256 for passwords.
- JWT: alg allow-list (reject `none`, reject HS variants when RS expected, check `kid` handling), key rotation support, `aud`/`iss` validation, expiry enforcement.
- Insecure deserialization sinks (pickle, yaml.load, Marshal, BinaryFormatter, node-serialize, Jackson default typing).

## Manual review patterns to queue up

These are not tool runs; they are code-read patterns. Assign each to a specific file list so Stage 4 can execute.

- **Taint tracing.** For each source (request body, query param, header, env, file upload, webhook payload, queue message, RPC arg, LLM tool-call arg), follow the data to every sink (SQL, shell, fs, HTTP client, template render, `eval`, deserializer, logger, response writer). Check sanitization at every branch.
- **Authorization at every handler.** Do not trust middleware. Open each handler and ask: "what role/tenant/ownership does this assume, and where is that enforced?" Missing enforcement → finding.
- **Multi-tenant scoping.** For each ORM fetch, confirm the tenant filter is applied. For each list endpoint, confirm the query is tenant-scoped. For each cache key, confirm it contains tenant identifier.
- **Rate limiting on sensitive endpoints.** Login, signup, password reset, MFA challenge, OTP send, webhook receiver, expensive compute (ML inference, report generation). Absence is a finding.
- **CSRF / SameSite.** For cookie-auth apps, verify SameSite=Lax or Strict + CSRF tokens on state-change. For token-auth apps via `Authorization` header, CSRF is inherently mitigated; still verify cookie is not ALSO auth.
- **CORS.** Look for `Access-Control-Allow-Origin: *` with credentials, Origin reflection, trailing-dot bypass in regex, null origin acceptance.
- **SSRF sinks.** Enumerate every `fetch`/`requests`/`http.Get`/`HttpClient`/`axios`/`curl` call whose URL is user-influenced. Check for allow-lists and redirect-following behavior.
- **XXE.** XML parsing calls; check DTD disabling and external-entity resolution settings.
- **Path traversal / zip slip / tar slip.** File-write and archive-extract paths.
- **SSTI.** Template render calls with user-controlled string; differentiate "render this template with this data" (safe) from "render this user string as a template" (injection).
- **ORM injection / raw queries.** Search for raw-query escape hatches: `.raw(`, `.query(`, `sequelize.query`, `db.exec`, `execute(`, string concatenation in SQL.
- **Log injection / PII in logs.** Grep for logger calls that include request data, tokens, passwords, card numbers, SSNs, addresses, emails.
- **Open redirects / HTTP response splitting.** `redirect(<user-input>)`, `res.setHeader(key, user-input)` with `\r\n`.
- **Prototype pollution.** `Object.assign`, `_.merge`, `_.set`, `$.extend`, `Object.setPrototypeOf` with user-controlled keys.
- **Mass assignment / BOPLA.** Spread of request body into model constructor or update. Pair with authorization: is the user allowed to set this field?
- **Race conditions on critical resources.** Coupon redemption, balance transfer, unique-per-user action, file creation before a permission check. Queue these for Stage 5 concurrent-request PoCs.

## Writing `audit_plan.md`

Use the template. Group by category. Each entry:

```markdown
### AP-023 · SAST — Semgrep OWASP Top 10 + Python pack
- **Command**: `semgrep --config p/security-audit --config p/owasp-top-ten --config p/python --sarif -o .security-audit/tool-logs/semgrep-<ts>.sarif .`
- **Covers threats**: T-003, T-005, T-009, T-011, T-017
- **Tool version**: semgrep X.Y.Z (recorded at run time)
- **Rationale**: Broad coverage of injection, crypto, and auth patterns; language-specific rules for Python/Flask detected in recon
- **Output**: SARIF → triage in Stage 4
```

For manual-review items:

```markdown
### AP-041 · Manual — Tenant scoping at every `/api/documents/*` handler
- **Files**: src/documents/*.ts (6 files)
- **Covers threats**: T-014 (cross-tenant IDOR)
- **Technique**: Read each handler; confirm `where tenantId = currentTenantId` present; confirm list endpoints don't rely only on UI filters; check object-returning endpoints enforce ownership, not just existence
- **Output**: finding(s) with file:line or explicit non-finding note per handler
```

Close `audit_plan.md` with a **Coverage summary**: for each threat in `threat_model.md`, list the audit-plan items covering it. Any threat with zero items is a gap — either add items or note in `coverage_gaps.md` with rationale.

## Exit conditions

- `audit_plan.md` covers every threat in `threat_model.md`.
- Tool install requests have been posed to the user and either approved or recorded as gaps.
- `state.json.stage3` is `completed`.
