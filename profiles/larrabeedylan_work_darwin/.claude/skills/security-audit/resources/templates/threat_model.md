# Threat model — `<project-name>`

> Populated by Stage 2. Threats ranked critical → low. Each entry drives Stage 3 audit-plan items.

## Attacker personas in scope
- [ ] Unauthenticated external
- [ ] Authenticated low-privilege user
- [ ] Privileged / admin insider
- [ ] Cross-tenant attacker
- [ ] Compromised dependency
- [ ] Compromised CI runner
- [ ] Malicious insider / compromised developer
- [ ] Physical / network-adjacent
- [ ] LLM prompt attacker (if applicable)

Mark applicable and justify any that's skipped.

## Trust-boundary invariants
| Boundary | Invariant | Enforcement location | Risk if broken |
|----------|-----------|----------------------|----------------|
| user → HTTP handler | every field explicitly allowed or rejected | schema validator | mass assignment / BOPLA |
| app → SQL | every parameter bound, never concatenated | ORM / parameter placeholders | SQL injection |
| app → shell | no string-concatenated command lines | `execFile` with argv | command injection |
| app → fs | path anchored under known root | `realpath` + prefix check | path traversal |
| app → external HTTP | destination allowlisted; internal/metadata rejected | URL parser + allow-list | SSRF |
| tenant A → tenant B | object fetches scoped by tenant | RLS or handler `where tenantId=` | cross-tenant breach |

## Ranked threats

### T-001 · <title>
- **Frame**: <STRIDE letter(s) + e.g. BOLA>
- **Persona**: <attacker>
- **Asset**: <what's at risk>
- **Vector**: <how the attack proceeds>
- **Prerequisites**: <account needed? knowledge required?>
- **Expected impact**: <confidentiality/integrity/availability>
- **Evidence hooks**: <file:line pointers that motivate this threat>
- **Planned validation**: <stage 4 checks + stage 5 PoC plan>

<repeat for each threat>

## Business-logic abuse cases
<list abuse cases derived from product behavior — coupon stacking, negative quantities, replay, etc.>

## Gaps / unknowns
<things you can't threat-model without user input — e.g. "unclear whether the `/admin` endpoint is network-isolated in prod">
