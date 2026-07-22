# API methodology

Loaded when recon classifies target as `api` (REST, GraphQL, gRPC, JSON-RPC, Thrift, etc.).

## Follows OWASP API Security Top 10 (2023)

1. BOLA (broken object-level authz)
2. Broken authentication
3. BOPLA (broken object-property-level authz)
4. Unrestricted resource consumption
5. BFLA (broken function-level authz)
6. Unrestricted access to sensitive business flows
7. SSRF
8. Security misconfiguration
9. Improper inventory management
10. Unsafe consumption of APIs

## BOLA — systematic negative tests

For every endpoint accepting an object ID, generate:

| User | Action | Object | Expect |
|------|--------|--------|--------|
| Anonymous | GET | any object | 401 |
| User A | GET | own object | 200 |
| User A | GET | User B's object | 403 or 404 |
| User A in Tenant 1 | GET | Tenant 2's object | 403 or 404 |
| User A | PATCH | User B's object | 403 or 404 |
| User A | DELETE | User B's object | 403 or 404 |

The "found but forbidden" vs "not found" decision: prefer 404 when disclosing existence leaks info; prefer 403 when the object class is enumerable and the real protection is the ownership check.

**Anti-pattern**: `findById(id)` in the handler. **Pattern**: `findByIdForUser(id, currentUser)` or policy-layer check.

Collection endpoints: `?filter=userId:123` or `?owner=victim@example.com` — verify listing is also scoped to the caller.

## BOPLA — mass assignment + over-read

Over-write:
```json
POST /api/users
{ "email": "me@x", "password": "…", "role": "admin", "tenantId": "victim" }
```
Over-read:
```
GET /api/users/me
→ { "email": …, "passwordHash": "…", "mfaSecret": "…" }   <- serializer leaks sensitive fields
```

Fix: explicit DTO per endpoint. Never use the ORM model as both request and response type.

## BFLA — function-level authz

Forced browsing to admin/internal routes:
- `/admin/**`, `/internal/**`, `/_debug/**`, `/graphql?debug=true`, `/api/v0/...`.
- Methods not advertised: try `PUT`, `PATCH`, `DELETE` on GET-only endpoints.
- Versioned routes with weaker authz: `/api/v1/...` might be auth-gated but `/api/v2-beta/...` isn't.

Construct a spider from the recon inventory, then test each route against every persona.

## Rate limiting / unrestricted consumption

Targets:
- Login, signup, password reset, MFA challenge — per-account, per-IP, globally.
- Expensive endpoints — report generation, ML inference, batch processing, large exports.
- Webhook receivers — can attacker flood them?

Test methodology:
- Send N requests/minute and observe enforcement.
- Rotate IPs (if you have a pool) to test IP-only rate limits.
- Vary account identifiers (emails) to test per-account limits.
- Measure cost: what is the server resource per rejected request? Attacker can still DoS via rejection cost if auth is expensive.

Good rate-limit design: token bucket per account AND per IP, with reject cost = constant.

## Schema-based fuzzing

- **REST with OpenAPI**: `schemathesis run --checks all --hypothesis-max-examples 200 <spec>`. Catches: 5xx on input at boundaries, schema violations on responses, auth gaps on declared-public endpoints.
- **GraphQL**: `graphql-cop <url>`, `inql`, introspection-based fuzz.

## GraphQL

### Introspection
```graphql
{ __schema { types { name fields { name args { name } } } } }
```
Should be disabled in prod. If enabled: Stage 4 finding (info disclosure); Stage 5 use the schema to drive everything else.

### Depth / complexity DoS
```graphql
{ user { friends { user { friends { user { friends { ... } } } } } } }
```
Fix: depth limit + cost limit (`graphql-cost-analysis`).

### Batching auth bypass
```json
[
  {"query":"mutation { login(u:\"admin\",p:\"a\") { token } }"},
  {"query":"mutation { login(u:\"admin\",p:\"b\") { token } }"},
  ...
]
```
If rate limit is per-request instead of per-operation, 100 login attempts in one request pass the limit.

### Alias-based rate-limit bypass
```graphql
{
  a1: login(u:"admin", p:"a") { token }
  a2: login(u:"admin", p:"b") { token }
  ...
}
```
Aliases are multiple operations on one request.

### Field-level authz
```graphql
{ user(id: 1) { name ssn email } }
```
`ssn` should be gated; `name` isn't. If the resolver doesn't check per-field, BOPLA is alive.

### Introspection via aliasing against "disabled" introspection
Some stacks disable `__schema` but not individual `__type` probing. Check.

## gRPC

- Reflection: disabled in prod? `grpcurl -plaintext <host> list`.
- TLS: required in prod; mTLS for service-to-service.
- Message confusion: same method ID receiving wrong message type can crash or mis-interpret.
- Metadata: auth token in metadata (Authorization header analogue), not in message body.
- Streaming: backpressure and time limits; an open stream is cheap for the attacker and expensive for the server.

## REST specifics

- **Content negotiation**: server honors `Content-Type: application/xml` and parses XML (XXE) when the API is "JSON-only"? Whitelist.
- **HTTP method override**: `X-HTTP-Method-Override: DELETE` over a POST; is it honored? Often a bug.
- **Proxy header trust**: `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host` — trust only behind a trusted LB.
- **Version drift**: `/v1` and `/v2` coexist; is `/v1` still auth-checked the same way after a refactor?

## Webhook receivers

For each webhook endpoint:
- Signature verification present and using constant-time compare?
- Replay-protection: timestamp check, nonce tracking.
- Source IP allow-list (if provider publishes a list).
- Size cap.
- Idempotency by event ID (provider's ID, not one the attacker controls).
- Authenticated-but-anonymized: webhook receivers often auth via shared secret; if that leaks, anyone can post.

## API inventory management

- Deprecated versions still running?
- Shadow APIs (endpoints not in the docs) accessible?
- Staging/dev endpoints reachable from prod network?
- Debug endpoints (`/debug/pprof`, `/_profiler`, `/actuator/**`, `/admin`) exposed?
