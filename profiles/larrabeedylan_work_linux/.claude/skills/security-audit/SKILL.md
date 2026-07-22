---
name: security-audit
description: Perform a deep, adaptive, end-to-end security audit and active penetration test of a project directory. Use when the user asks for a security review, vulnerability assessment, pen test, hardening sweep, or threat model of any codebase (web, API, CLI, library, IaC, mobile, firmware, ML/LLM pipeline, browser extension, smart contract, data pipeline). Multi-stage pipeline — recon, threat model, SAST, PoC-driven pen test, remediation with user gate, adversarial verification, final report — with resumable state and explicit safety boundaries.
---

# security-audit

Opinionated, reasoning-driven security audit of an arbitrary project. Tool output is input to judgment, never a substitute. Every finding is either exploited via an executable PoC test or explicitly justified as non-exploitable.

## Invocation

```
/security-audit [target_dir] [flags]
```

If `target_dir` is omitted, audit the current working directory.

### Flags

| Flag | Effect |
|------|--------|
| `--resume` | Default. Detect existing audit state and continue from the next incomplete stage. |
| `--restart` | Archive any prior audit directory (`.security-audit/`) to `.security-audit.archive-<ts>/` and start fresh. Requires explicit user confirmation before archiving. |
| `--stage <n>` | Force execution to begin at stage `n` (1–9). Later stages still run sequentially. |
| `--only-category <name>` | Restrict Stage 4/5 work to a category (e.g. `authz`, `injection`, `crypto`, `supply-chain`, `llm`, `iac`, `container`). |
| `--severity-threshold <level>` | `critical|high|medium|low|info`. Findings below the threshold are recorded but not remediated by default. |
| `--no-install` | Never offer to install missing tools. Document gaps in `coverage_gaps.md` and continue. |
| `--sandbox <kind>` | `docker|compose|venv|process|none`. Hint how to stand up the target for dynamic testing. If `none`, Stage 5 does static-only PoCs (payload construction + review) and records coverage gaps. |
| `--dry-run` | Stages 1–5 only; Stage 6 presents the plan and exits without touching code. |

## Working directory layout

All audit state lives under `<target_dir>/.security-audit/`. Do **not** commit this directory — add `/.security-audit/` to `.gitignore` during init if a `.gitignore` exists. The directory contains:

```
.security-audit/
├── state.json              # machine-readable stage completion, flags, tool versions
├── recon.md
├── threat_model.md
├── audit_plan.md
├── findings.md
├── pentest_results.md
├── remediation_plan.md
├── report.md
├── coverage_gaps.md
├── blockers.md
├── evidence/<finding-id>/  # request/response, stack traces, DB diffs, logs
├── sandbox/                # ephemeral target spin-up artifacts (compose files, seeds)
└── tool-logs/              # raw stdout of each scanner run, named <tool>-<ts>.log
```

The skill ships templates for every markdown file in `resources/templates/`. On first run in a project, copy templates into `.security-audit/` to initialize. Thereafter, update in place.

## Stages

Execute sequentially. Each stage is idempotent: check whether its output artifact is present and marked complete in `state.json` before running. Detailed instructions for each stage live in a dedicated file that MUST be loaded only when that stage runs (to conserve context).

| # | Name | Load this file before starting |
|---|------|--------------------------------|
| 1 | Reconnaissance & Fingerprinting | `resources/stages/stage1_recon.md` |
| 2 | Threat Modeling | `resources/stages/stage2_threat_model.md` |
| 3 | Resource Gathering & Audit Plan | `resources/stages/stage3_audit_plan.md` |
| 4 | Deep Static Audit | `resources/stages/stage4_static_audit.md` |
| 5 | Active Penetration Testing | `resources/stages/stage5_pentest.md` |
| 6 | Remediation Plan & User Gate | `resources/stages/stage6_remediation_plan.md` |
| 7 | Remediation | `resources/stages/stage7_remediation.md` |
| 8 | Adversarial Verification Loop | `resources/stages/stage8_verification.md` |
| 9 | Final Report | `resources/stages/stage9_report.md` |

After recon, also load the relevant methodology files from `resources/methodology/` based on the detected project class (e.g. `web.md` + `api.md` + `supply-chain.md` + `crypto.md` for a web service). `generic.md` applies to every project and is always loaded.

## Safety boundaries (non-negotiable)

1. **Scope is local.** Only audit files in `target_dir`. Only attack instances of the target spun up in an isolated sandbox you control. Refuse to scan, probe, or attack any external system the user does not own. If recon reveals hardcoded production URLs or API keys, redact them, flag for rotation, and do not connect to them.
2. **No destructive DoS.** Demonstrate algorithmic-complexity or resource-exhaustion issues with bounded PoCs that assert on the measurement (time, memory, descriptors) rather than crashing a real service.
3. **No live third-party traffic.** External integrations (payment processors, email providers, OAuth IdPs, cloud APIs, LLM APIs) are mocked during pen tests unless the user explicitly names a sandbox tenant they own and authorizes testing against it. Record the authorization in `state.json`.
4. **No exfiltration.** Do not send source, findings, secrets, or generated payloads to cloud SaaS scanners or remote LLM endpoints without the user's explicit, per-run confirmation. Local tools only by default.
5. **Secrets are redacted everywhere.** Any discovered secret appears in markdown as `<file>:<line> · <pattern-type> · …<last4>`. Never the literal value. Flag that rotation is required.
6. **No auto-git.** No commit, push, branch creation, tag, PR, or force-anything. All remediation lands as local edits. If the user asks you to commit at the end, that is a separate, explicit request.
7. **No hook bypass.** Do not use `--no-verify`, `--no-gpg-sign`, `git reset --hard`, or equivalent destructive shortcuts.
8. **Ask before installing.** If a scanner or fuzzer is missing, state what you want to install, why, and how (package manager, version, checksum if available). Proceed only on explicit approval, or skip the check and record the gap.
9. **Every finding is earned.** Raw scanner output is not a finding. Triage each alert. True positives are reproduced or reasoned to exploitability. False positives are documented with the reason they were dismissed. Needs-dynamic-validation items defer to Stage 5.
10. **No silent failure.** If a stage cannot run (missing tool, unsandboxable target, read-only filesystem), write the reason to `coverage_gaps.md` and surface it in the final report. Do not skip quietly.

## Orchestration algorithm

On every invocation:

1. Determine `target_dir` (argument or cwd). Verify it exists and is readable.
2. Read `<target_dir>/.security-audit/state.json` if present. If absent, create the audit directory, copy templates from `resources/templates/`, initialize `state.json`, and add `/.security-audit/` to `.gitignore` (if a `.gitignore` exists and does not already contain it).
3. If `--restart`, confirm with the user, then archive prior state.
4. Honor `--stage <n>` by setting the next-stage pointer; otherwise use the first stage with `status != "completed"` in `state.json`.
5. Announce the stage plan to the user in one short paragraph. Do not dump the whole stage file; load it with `Read` into your own context only.
6. Execute the stage. After each stage:
   - Update the corresponding markdown artifact.
   - Mark the stage `completed` in `state.json` with timestamp and tool versions.
   - For stages 1, 2, 4, 5: if the stage discovered new attack surface, loop back and update `recon.md` before advancing.
7. Between stages 6 and 7, stop and require explicit approval from the user. Support granular approval (`all` / by severity / by category / by ID list).
8. After Stage 9, surface the one-screen summary in chat and point the user to `report.md`.

## Resumability rules

- Never edit `findings.md` history. Findings are append-only with stable IDs (`SA-001`, `SA-002`, …). Re-triage adds a follow-up entry that references the earlier ID.
- Every tool invocation is logged to `tool-logs/<tool>-<ts>.log` with the exact command line so it can be reproduced.
- `state.json` records tool versions at time of use. On resume, re-check versions; if they changed materially, note it in `coverage_gaps.md`.
- Evidence files under `evidence/<finding-id>/` are immutable. If a PoC is updated, append a new evidence subdirectory (`evidence/SA-007/v2/`).

## Reasoning posture

Prefer understanding over breadth. A well-understood, exploited finding with a working PoC outweighs ten speculative scanner alerts. When taint-tracing, read the actual code — do not rely on scanner path claims. When evaluating authorization, verify every handler, not just the middleware. When evaluating crypto, read RFC-level behavior, not just library names. When evaluating business logic, enumerate abuse cases against what the app promises to do.

## Output to the user

- Short status lines between stages ("Stage 3 complete: 47 checks selected, 12 require user-approved install. Proceeding to Stage 4.").
- Do not paste large file contents into chat — link the user to `.security-audit/<file>.md`.
- Do not fabricate severity. CVSS vectors must be grounded in the actual exploit conditions you verified.
- The final chat message is a one-screen summary of Stage 9. Everything else is in the report.

## References

- OWASP ASVS v4.0.3 for verification-level calibration.
- CWE for finding categorization.
- OWASP API Security Top 10 (2023) for API work.
- OWASP LLM Top 10 for LLM pipeline work.
- CIS Benchmarks for container/Kubernetes hardening.
- SLSA for supply-chain provenance recommendations.
