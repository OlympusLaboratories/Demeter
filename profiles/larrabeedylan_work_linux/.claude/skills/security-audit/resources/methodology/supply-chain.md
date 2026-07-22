# Supply chain methodology

Always applicable. Load for every project. Addresses OWASP A06:2021 and adjacent concerns.

## Dependency integrity

- **Lockfile present?** `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `poetry.lock`, `Pipfile.lock`, `Cargo.lock`, `go.sum`, `Gemfile.lock`, `composer.lock`.
- **Lockfile pinned to specific versions** (not ranges).
- **`install --frozen-lockfile` works** (no drift). `go mod verify` returns clean.
- **Hashes in lockfile** match registry (npm has `integrity`, Python `poetry.lock` has hashes, yarn has integrity).
- **Lockfile committed** (yes — even for libraries, for development reproducibility).

## Direct vs transitive

Map direct → transitive. Vulnerabilities in transitive-only deps are common; reachability often matters (the vuln code must be reachable from your code path).

## Typosquatting

For each direct dep:
- Known package? (top-downloads list, well-known vendor.)
- Single-character substitution from popular package? (`requests` vs `reqeusts`, `axios` vs `axois`, `colors` vs `color`.)
- Scope confusion (`@acme/utils` vs `acme-utils`, `@angularjs/core` vs `@angular/core`).
- Dash-swap (`event-stream` → various).

Tools: `snyk-typosquat`, manual comparison against top-N downloads list.

## Dependency confusion

For private packages (internal org scope):
- Is the private scope registered publicly too? If a public package with the same name exists and the install resolver lists the public registry first, npm/pip/etc. may pull the public one.
- **Scoped packages** (`@yourorg/...`) with registry config explicitly pointing that scope to the private registry.
- **pip**: use `--index-url` (private) not `--extra-index-url` (adds to list — confusion possible).
- **Maven**: repository order, resolver preferring public vs private.
- Proactive: claim your package name on public registries even if you never publish there.

## Postinstall / prepack scripts

- `npm` packages with `scripts.postinstall`, `preinstall`, `install`: these run arbitrary code on install.
- `pip` `setup.py` runs on `pip install` — some packages have offensive code here.
- Gradle `buildscript { }` and `apply from:` can pull remote scripts.

Mitigations:
- `npm install --ignore-scripts` in CI, with allow-list via `onlyBuiltDependencies` (pnpm).
- Review scripts on version bumps.
- Containers during install ops.

## Maintainer compromise

- Top-N direct deps: check last-publish, maintainer count, recent ownership changes.
- Look for:
  - New maintainer added right before a release.
  - Release with no changelog.
  - Release with huge delta compared to prior cadence.
  - GPG-signed releases going unsigned.
- CVE feeds / advisory databases surface confirmed cases (event-stream, ua-parser-js, coa, rc, colors, faker.js, xz backdoor, etc.).

## SCA tools

- `osv-scanner --recursive .` — cross-language, OSV.dev.
- `trivy fs --security-checks vuln,secret,license .`.
- `grype .`.
- Language-specific: `npm audit --production`, `pip-audit`, `safety check`, `bundler-audit`, `cargo audit`, `govulncheck`, `composer audit`, `dotnet list package --vulnerable`.

Triage:
- Confirm reachability from your code.
- Prod vs dev dep.
- Fix-version available?
- If no fix: pin, patch (fork), vendor, or remove.

## SBOM

Generate and ship an SBOM for releases:
- `syft packages <target> -o cyclonedx-json` (CycloneDX).
- `syft packages <target> -o spdx-json` (SPDX).

Store SBOM alongside release artifacts. Consumers can check against CVE feeds without rebuilding.

## Provenance (SLSA)

SLSA levels describe increasingly trustworthy build provenance:
- L1 — build process documented.
- L2 — build service is hosted and generates provenance.
- L3 — provenance is non-falsifiable (signed by build service, not dev).
- L4 — two-person review, hermetic builds, reproducible.

Targets:
- CI produces attestations (GitHub Actions supports via `actions/attest-build-provenance`).
- Release artifacts are signed (cosign) and verifiable by end users.
- Container images pushed with signed provenance.

## Checked-in binaries

- Precompiled artifacts (`.so`, `.dll`, `.dylib`, `.jar`, `.class`, `.exe`, `.pyd`, `.node`) checked into the repo are red flags.
- If present, demand provenance: source repo + build script + SBOM + signature.
- Consider extracting to `vendor/` with `VENDORED.md` describing each.

## Unsigned tarball / script installs

- `curl https://... | sh` → install relies entirely on TLS and domain safety.
- Tarballs distributed over HTTP or HTTPS without signatures.
- Installer scripts that fetch more scripts at runtime.

For critical software: distribute signed artifacts, publish the signing key through a separate channel, document verification steps.

## Pre-commit / CI hooks

Hooks themselves are dependencies. A malicious pre-commit config can exfiltrate the repo. Review:
- `.pre-commit-config.yaml` hook repos and revisions (pin SHAs, not branches).
- CI action versions (`uses: some/action@v1` → tag can move; use SHA).
- Self-hosted actions on ephemeral runners only.

## Git submodules / vendored sources

- Submodule pinned to SHA (not branch).
- No submodule that fetches from mutable tags.
- `git-crypt` / `git-secret` stored ciphertexts are fine; keys are not.

## Base images

- Pinned by digest: `FROM python:3.12-slim@sha256:abcd…`, not `FROM python:3.12-slim`.
- Minimal / distroless base images prefer — less attack surface.
- Multi-stage build to avoid shipping build tools.
- Patched on known-CVE cadence: `trivy image <tag>` regularly.

## Registries

- Private registries enforce auth.
- Pull-through caches for reproducibility.
- Image signing (cosign, Notary v2).
- Admission controllers (Kyverno, OPA Gatekeeper) enforce signed-only.

## Publishing side

If this project itself publishes packages:
- Publish account protected by 2FA.
- No long-lived tokens in CI; use OIDC-based trust (npm provenance, PyPI trusted publishers, crates.io tokens scoped to repo).
- Signing keys in HSM / KMS, not local disks.
- Release tag signed (`git tag -s`).
- Reproducible builds where feasible.
- Security contact + `SECURITY.md` in repo.
