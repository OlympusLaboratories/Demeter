# Reconnaissance — `<project-name>`

> Populated by Stage 1. Every claim evidence-backed (`file:line`).

## Summary
<1–5 lines: what this project is and what it promises to do.>

## Classification
<one or more of: web | api | cli | library | iac | mobile | desktop | embedded | ml-llm | browser-ext | smart-contract | data-pipeline | hybrid>

## Methodology files to apply
<comma-separated list — drives which methodology/*.md files are loaded in Stage 2+>
Always: generic.md, supply-chain.md, crypto.md
Also:   <web.md | api.md | cli.md | iac.md | mobile.md | llm.md | smart-contract.md | firmware.md>

## Languages & runtimes
| Language | Version | Evidence |
|----------|---------|----------|
| | | |

## Frameworks & key libraries
| Library | Version | Role | Evidence |
|---------|---------|------|----------|
| | | | |

## Dependency graph
- Direct: `<n>`
- Transitive: `<m>`
- Known-CVE count (at scan time): `<k>`
- Lockfile status: `<present/pinned/drifted/missing>`

## Build & packaging
<build system, package manager, monorepo tooling, notable scripts>

## Deployment targets
<Docker, Kubernetes, serverless, PaaS, edge, bare metal — evidence>

## Authn / authz patterns
- Session/token: <kind, library, storage>
- Roles/permissions: <RBAC table, policy engine, hardcoded>
- Other: <OAuth flows, SAML, mTLS, API keys, HMAC, WebAuthn>

## Data stores
| Store | Role | Tenancy | PII? |
|-------|------|---------|------|
| | | | |

## External integrations
| Vendor | Purpose | Auth mechanism | Webhook? |
|--------|---------|----------------|----------|
| | | | |

## Entry points
| Path/Name | Kind | Auth | Inputs | Sinks | Notes |
|-----------|------|------|--------|-------|-------|
| | | | | | |

Kinds include: HTTP route, CLI command, queue consumer, scheduled job, IPC endpoint, public library function, webhook, deep link, smart-contract external, hardware interface.

## Trust boundaries
<bullet list of boundaries and the invariants that must hold at each crossing>

## Observations shaping threat model
<free text: surprises, smells, concerns, "rolled their own crypto", "middleware not applied to /admin", etc.>

## Tooling run in recon
| Tool | Version | Output |
|------|---------|--------|
| | | |
