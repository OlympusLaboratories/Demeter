# Cryptography methodology

Always-loaded companion. Use when reviewing any code that encrypts, signs, hashes, authenticates, or generates randomness.

## Algorithm selection (2024+ guidance)

| Purpose | Prefer | Avoid |
|---------|--------|-------|
| Symmetric encryption | AES-GCM, ChaCha20-Poly1305, XChaCha20-Poly1305 | AES-ECB, AES-CBC without HMAC, DES, 3DES, RC4 |
| Asymmetric encryption | RSA-OAEP (2048+), ECIES on P-256, X25519 | RSA PKCS#1 v1.5, textbook RSA |
| Signatures | Ed25519, ECDSA P-256/P-384, RSA-PSS (2048+) | DSA, RSA PKCS#1 v1.5 with SHA-1 |
| Hash (general) | SHA-256, SHA-512, SHA-3, BLAKE3, BLAKE2 | MD5, SHA-1 |
| MAC | HMAC-SHA-256, HMAC-SHA-512, BLAKE2-MAC, KMAC | CBC-MAC (unless length-committed), custom MACs |
| Password hashing | Argon2id, scrypt, bcrypt | MD5, SHA-family alone, fast hashes |
| Key derivation | HKDF, Argon2id for passwords, PBKDF2-SHA-256 as fallback | MD5-based, low-iteration PBKDF2 |
| Random | CSPRNG from OS (`crypto.randomBytes`, `secrets`, `crypto/rand`, `OsRng`, `SecRandomCopyBytes`) | `Math.random`, `random.random`, `rand::thread_rng`, time-seeded PRNG |

## Mode gotchas

### AES-ECB
Deterministic per block. Identical plaintext blocks → identical ciphertext blocks. Visible in patterned data (the classic Linux penguin).

Detection: encrypt two messages with identical 32-byte prefix; if the first 32 bytes of ciphertext match, it's ECB.

Replace with AES-GCM.

### AES-CBC
Needs:
- Random IV per message, 16 bytes.
- HMAC over `IV || ciphertext` (Encrypt-then-MAC) because CBC alone is malleable and enables padding-oracle attacks.

Prefer AES-GCM to avoid these pitfalls.

### AES-GCM
- 12-byte IV (96-bit) nonce.
- NEVER reuse nonce with the same key. Reuse breaks confidentiality of both messages AND reveals the authentication subkey.
- Nonce can be a counter (safe if monotonic and not rolled over).
- For random nonces with 96 bits, birthday bound at ≈2^32 messages — safe for most apps, but not for "encrypt every user every request for a decade".
- AAD field: use it to bind context (recipient, purpose, timestamp).

### ChaCha20-Poly1305 / XChaCha20-Poly1305
- ChaCha20-Poly1305: 96-bit nonce, same reuse constraints as GCM.
- XChaCha20-Poly1305: 192-bit nonce, safe for random nonces indefinitely. Prefer for random-nonce scenarios.

## Key sizes

- RSA: ≥ 2048 bits. 3072 for long-term.
- ECDSA / EdDSA: curve choice is the input; P-256, P-384, Ed25519 all good. No `secp256k1` for general-purpose (it's for Bitcoin/Ethereum and perfectly fine there, but don't reuse for general signing without reason).
- AES: 128+ sufficient; 256 for long-term.

## Password hashing parameters

Tune to ≈ 250–500ms on your server. 2024 starting points:

- **Argon2id**: `m=65536 (64 MiB)`, `t=3`, `p=4` (or calibrated to your RAM/cpu).
- **scrypt**: `N=2^17, r=8, p=1` (or higher N if your hardware allows).
- **bcrypt**: cost 12+ (cost 10 is 2010-era; re-hash on login).
- **PBKDF2-SHA-256**: ≥ 600k iterations (OWASP 2023).

Store parameters with the hash (modular crypt format, `$argon2id$v=19$m=...`). Support migration: detect old params on login and rehash.

## Random

- OS CSPRNG is the default. Everything else needs strong justification.
- Seed any userland PRNG from CSPRNG if it must be used (rare).
- UUID v4 is CSPRNG-backed in most libraries; UUID v1 / v3 / v5 are not secret.
- Token length: ≥ 128 bits of entropy. Use `secrets.token_urlsafe(32)` / `crypto.randomBytes(32).toString("base64url")`.

## Constant-time comparison

Any MAC, token, or key comparison must be constant-time. Non-constant-time compare enables byte-at-a-time timing attacks even over the network (measurable with enough samples).

Use:
- Python: `hmac.compare_digest(a, b)`, `secrets.compare_digest`.
- Node: `crypto.timingSafeEqual(bufA, bufB)`.
- Go: `subtle.ConstantTimeCompare(a, b)`.
- Java: `MessageDigest.isEqual(a, b)`.
- Rust: `subtle::ConstantTimeEq`, `constant_time_eq` crate.
- C: `CRYPTO_memcmp` (OpenSSL), `sodium_memcmp` (libsodium).

Do NOT use `==`, `strcmp`, `bytes.Equal`, `Array.equals`.

## JWT hardening

Every decode site must:
- **Allow-list** `alg` values (e.g., `["RS256", "RS384", "RS512"]`) — never accept `none`, never accept `HS*` when your tokens are `RS*` (alg confusion).
- **Validate `aud`** is this service.
- **Validate `iss`** is your issuer.
- **Validate `exp` / `nbf`** with your clock, plus a small skew.
- **Validate `kid`** against a known key set. If `kid` lookups hit a DB/filesystem, input-validate (path traversal, SQLi).
- **Pin algorithm to key material** — don't blindly trust the header.
- **Support key rotation** via a JWKs fetch + cache with TTL.

Replay on logout: JWTs are stateless; if you need revocation, keep a short-lived access token + revocation list on a refresh-token authority.

## TLS

- Minimum version 1.2; prefer 1.3.
- Cipher suites: no export, no RC4, no NULL, no DES, no 3DES, no MD5 suites.
- HSTS on HTTPS sites; preload if first-party.
- OCSP stapling where supported.
- Certificate validation: platform trust store + hostname verification. Pinning for mobile apps (see `mobile.md`).
- mTLS for service-to-service.

## Password reset / token design

- Tokens: CSPRNG, ≥ 128 bits, URL-safe base64.
- Stored as `HMAC-SHA256(server_key, token)` or `Argon2id(token)` so a DB leak doesn't expose reset links.
- Single-use — mark consumed on first verify.
- Short TTL (15–60 min typical).
- Bind to the account; a token minted for user A cannot be used for user B.
- Rate-limit minting to prevent enumeration / spam.

## API-key / access-token design

- CSPRNG, prefixed with a visible vendor marker (`sk_live_`, `acme_api_`) so users recognize accidentally-leaked keys.
- Store hashed (`HMAC-SHA256(server_key, key)`), look up by hash.
- Displayed once at creation; after that only a prefix.
- Scopes (fine-grained): what can this token do?
- Revocation path.
- Last-used and created-at tracked for user-visible management.

## Signing webhook payloads (outbound)

```
body_bytes = canonical_serialize(payload)
ts = now_unix()
sig = hmac_sha256(secret, ts || "." || body_bytes)
header = f"t={ts},v1={sig}"
```

Receiver verifies:
- Timestamp within ± 5 min (replay window).
- HMAC valid (constant-time compare).
- Nonce cache for 5 min to block exact replays.
- Webhook secret rotated on a schedule or on any leak.

## Signing webhook payloads (inbound — your app receiving)

Same check. Additionally:
- Size cap on body.
- Parse only after signature validation.
- Idempotency by provider's event ID (attacker-controllable IDs are not idempotency keys).

## Secret storage

- **Never** in source.
- **Never** in env for anything long-lived (env leaks via `/proc/<pid>/environ` to other processes of the same user, appears in crash dumps, ends up in logs).
- **Never** in process args (visible in `ps`).
- **Prefer**: OS keyring, cloud secrets manager, HSM, KMS-encrypted sealed secrets with decryption at boot.
- **Encryption at rest** for any persisted secret.
- **Rotation** is a design requirement — if rotating requires manual intervention, you won't.

## Common crypto anti-patterns

- "Encrypted" with `base64`.
- MD5 used as a MAC.
- CBC without MAC.
- HMAC with user-controlled key.
- Using a public key as a shared HMAC secret.
- Home-rolled crypto primitives.
- "Constant-time" string compare written by hand, not using a library helper.
- Password hashing: `sha256(password + salt)` — not a password hash.
- Encryption key derived by `sha256(user_password)` — needs a proper KDF.
- "Encrypt" vs "sign" confusion (encrypting with a private key is not signing).
- Signing JSON without canonicalization — different serializations → different signatures.
- Reusing a key for multiple purposes (encryption AND signing with same RSA key).
