# Mobile methodology

Loaded for `mobile` project class (iOS, Android, React Native, Flutter, hybrid).

Map to OWASP MASVS v2.

## Storage (MASVS-STORAGE)

- **iOS Keychain**: accessibility level — prefer `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`. Default is often `kSecAttrAccessibleAlways` which backs up and syncs.
- **Android Keystore**: use `AndroidKeyStore` provider; `setUserAuthenticationRequired(true)` for biometric-gated keys; `setInvalidatedByBiometricEnrollment(true)` so enrolled fingerprint change invalidates.
- **Shared Preferences / UserDefaults**: never for secrets. Tokens live in Keystore/Keychain.
- **SQLite** with SQLCipher when storing sensitive data.
- **Plaintext files**: `/sdcard` on Android is world-readable by apps with storage permission.
- **WebView localStorage**: cleared/segregated per origin.
- **Logs**: `Log.d` / `print` with sensitive data — filter for PII, tokens, card numbers, session identifiers.

## Crypto (MASVS-CRYPTO)

- No hard-coded keys.
- No ECB; AES-GCM or AES-CBC+HMAC (Encrypt-then-MAC).
- RSA-OAEP (not PKCS1v1.5) for encryption.
- Proper random: `SecureRandom` (Android), `SecRandomCopyBytes` (iOS), not `java.util.Random` / `arc4random` (arc4random is OK on modern systems but prefer platform secure RNG).
- PBKDF2 / scrypt / argon2 for derived keys.

## Network (MASVS-NETWORK)

- TLS required; app should reject cleartext by default (Android: `cleartextTrafficPermitted=false`; iOS: ATS enforced).
- **Certificate pinning** (static or dynamic) for sensitive endpoints; pin SPKI, not cert (cert rotates).
- Hostname verification enabled.
- TrustManagers that accept all certs → finding.
- `HostnameVerifier { _ -> true }` → finding.
- Network Security Config XML (Android) reviewed — no debug overrides shipped.

## Platform (MASVS-PLATFORM)

### Android
- Exported components: `<activity android:exported="true">` without matching intent filter justification.
- Implicit intents with sensitive payloads (use explicit).
- Deep links / app links: verify the `<intent-filter>` includes `<data android:scheme="https">` with `android:autoVerify="true"` and the `/.well-known/assetlinks.json` is served.
- Content providers: `android:exported="false"` unless intended public; if public, `android:readPermission`/`writePermission`.
- Broadcast receivers: permission guards.
- `android:allowBackup="false"` for apps holding sensitive data; `fullBackupContent` rules to exclude specific files.
- `android:debuggable="false"` in release.
- `taskAffinity` and `launchMode` — prevent task-hijacking (StrandHogg-style).
- Pending intents: use `FLAG_IMMUTABLE`, never blanket `FLAG_MUTABLE` without specific reason.

### iOS
- URL schemes registered — any app can invoke them; validate all input.
- Universal Links: entitlement + apple-app-site-association hosting check.
- Keyboard caches for sensitive text fields: `isSecureTextEntry = true`.
- Screenshot on backgrounding: obscure sensitive views (override `applicationWillResignActive`).
- Pasteboard usage — avoid pasting sensitive data, or use `UIPasteboard.generalPasteboard` scope carefully.
- App Transport Security exceptions in `Info.plist` require justification.

## WebView bridges

`addJavascriptInterface` on Android — exposes methods to any JS on any loaded page. Load only trusted URLs; validate inputs; `@JavascriptInterface` annotation required since API 17.

Bridge to native code with `postMessage` must validate origin.

iOS `WKWebView` message handlers: validate `WKScriptMessage.body` source and shape.

Auto-following `http://` → `https://` redirect in WebView bypasses ATS if misconfigured.

## Code (MASVS-CODE)

- Third-party SDKs pinned by integrity checksums where possible (gradle `dependencyVerification`, CocoaPods lockfile, Swift Package Manager Package.resolved).
- Native libs shipped: architecture-specific, signed? Stripped of debug symbols in release.
- JavaScript / native module boundary in React Native: any bridge method callable from JS can be called by injected JS in a malicious RN bundle — pin the bundle.
- JavaScript loaded from network (`WebView.loadUrl("http://...")`) → network-based RCE.

## Resilience (MASVS-RESILIENCE)

Context-dependent — apps handling high-value operations may require:
- Root / jailbreak detection (not a defense in itself, but a signal).
- Emulator / debugger detection.
- Tamper detection (signature check, class-integrity check).
- SSL pinning bypass detection.

None of these are invincible. For security-critical flows, always enforce server-side.

## Deep-link hijacking

Scenario: your app registers `myapp://reset?token=...`. Another app registers the same scheme. When user taps the link, Android shows a picker (or silently picks). iOS without Universal Links has no safety.

Fix: Universal Links (iOS) / App Links (Android) with domain verification.

## Tapjacking

Malicious overlay over your consent dialog. Fix: `android:filterTouchesWhenObscured="true"` on sensitive controls. iOS: less of an issue but similar via screen mirroring / screen sharing — for payment/auth, dismiss overlays on detection.

## Tooling

- **MobSF**: decompile + static + dynamic (on emulator) — `mobsfscan` for CI-friendly static scan.
- **apkleaks / apkanalyzer**: secrets in APK.
- **objection / Frida**: dynamic introspection on a rooted sandbox device (NEVER on user devices).
- **r2frida**, **ghidra**: reverse engineering.
- **drozer**: Android component testing.

## Threat model additions

- Physical adversary with device access — iOS and Android both protect against offline brute-force on strong passcodes via hardware-backed rate limits (Secure Enclave / TEE). Do not try to re-implement this in app code.
- Shared-device scenarios — multi-user phones and kiosks.
- Stalker attacker with one-time device access (installs tracker). Defensive measures are limited.
