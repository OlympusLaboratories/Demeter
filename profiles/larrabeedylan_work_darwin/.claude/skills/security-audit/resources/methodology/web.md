# Web application methodology

Loaded when recon classifies the target as `web`.

## XSS

### Contexts
- **HTML body**: `"><svg onload=alert(1)>`.
- **Attribute (double-quoted)**: `" autofocus onfocus=alert(1) x="`.
- **Attribute (unquoted)**: `/ onmouseover=alert(1) x=`.
- **URL context (`href`, `src`)**: `javascript:alert(1)`; also `data:text/html,<script>alert(1)</script>`.
- **JS string**: `';alert(1);//`.
- **JSON-in-script**: `</script><script>alert(1)//`.
- **CSS**: `expression(alert(1))` (IE legacy), `background:url('javascript:...')`, or modifier `--var:</style><script>...`.

### Polyglots
```
jaVasCript:/*-/*`/*\`/*'/*"/**/(/* */oNcliCk=alert() )//%0D%0A%0d%0a//</stYle/</titLe/</teXtarEa/</scRipt/--!>\x3csVg/<sVg/oNloAd=alert()//>\x3e
```
Useful for single-shot reflected XSS testing across multiple contexts.

### Mutation XSS (mXSS)
DOMPurify historical bypasses via namespace confusion (`<math><mglyph>`, `<svg><style>`, `<noscript>`). When the output is reparsed (e.g., `.innerHTML = sanitize(x)`), benign-looking markup becomes executable. Include a DOMPurify-version check — `window.DOMPurify.version` — in the PoC and cite the CVE if fixable.

### Stored XSS surfaces
Anywhere user input eventually renders to another user: profile bios, comments, filenames, display names, admin views of user data, error messages (admin reads user-submitted data that contains a payload), support tickets, email templates, PDF exports.

### DOM XSS sinks
`innerHTML`, `outerHTML`, `document.write`, `document.writeln`, `insertAdjacentHTML`, `eval`, `Function(...)`, `setTimeout(str)`, `setInterval(str)`, `location`, `location.href`, `location.assign`, `location.replace`, `jQuery.html`, `element.setAttribute("src", ...)` (for script/style/img/iframe).

Sources: `location.*`, `document.referrer`, `document.cookie`, `window.name`, `localStorage`, `sessionStorage`, `postMessage` data, fragment identifiers.

## CSP

Evaluate with `Content-Security-Policy` header. Check:

- No `unsafe-inline` unless paired with nonce/hash.
- No `unsafe-eval` unless strictly required.
- No `*` on `script-src` / `default-src` / `frame-ancestors`.
- `script-src` does not include script-gadget CDNs (AngularJS, old jQueryUI, etc.).
- `object-src 'none'` unless Flash/Java is required (not in 2024+).
- `base-uri 'self'` to prevent `<base>` injection pivot.
- `frame-ancestors 'none'` or explicit allow-list — replaces `X-Frame-Options`.
- `form-action` restricted.
- Report URI / Report-To configured.

Nonce hygiene: nonce is unique per response and unguessable (≥ 128-bit CSPRNG). Not reused across requests.

## Cookies

Required flags per cookie class:
- **Session / auth**: `HttpOnly; Secure; SameSite=Lax` (or `Strict` if cross-site flows aren't needed). Domain scoped as tight as possible (no parent-domain bleed).
- **CSRF token (double-submit)**: `Secure; SameSite=Strict` (not HttpOnly, JS must read it to send in header).
- **Preferences**: at minimum `Secure`.

Common issues:
- `Path=/` is fine, but `Domain=.example.com` broadens unnecessarily — stick to host-only where possible.
- Session cookie without `__Host-` prefix on single-origin apps (prefix enforces Secure + Path=/ + no Domain).
- Session ID predictable (framework should handle; verify it's not a counter or a user-id-based string).

## CSRF

For cookie-auth:
- SameSite=Lax prevents most cross-site POST navigations, but not cross-site navigations of the same-site attacker — still want a token.
- Double-submit CSRF: cookie holds a random value, client JS copies it into a header; server compares.
- Synchronizer token: server-side session state tracks per-user token.
- Critical: CSRF protection must apply to JSON endpoints too. Some frameworks skip CSRF on `Content-Type: application/json` — this is a bug if a cookie auths the request.

PoC shape:
```html
<form action="https://target/api/change-email" method="POST">
  <input name="email" value="attacker@evil.com">
</form>
<script>document.forms[0].submit()</script>
```

## CORS

Common misconfigs:
- `Access-Control-Allow-Origin: *` with `Access-Control-Allow-Credentials: true` — browsers block, but some custom clients do not.
- Origin reflection without allow-list, with credentials — bug, credentials go to attacker.
- `Access-Control-Allow-Origin: null` with credentials — sandboxed iframes have null origin.
- Regex allow-lists with:
  - `\.example\.com$` matching `attackerexample.com` (missing leading separator).
  - Not escaping `.` so it matches any char.
  - Missing anchors.
- Trusting `X-Forwarded-Host` / `Host` header for origin computation.

## Clickjacking

Missing `frame-ancestors 'none'` or `X-Frame-Options: DENY` → build a PoC:
```html
<iframe src="https://target/account/delete" style="opacity:0.0001;position:absolute;top:0;left:0;width:100%;height:100%"></iframe>
<button style="position:absolute;top:200px;left:200px">Click for prize</button>
```

## Cache poisoning

Key-header reflection: `X-Forwarded-Host`, `X-Original-URL`, `X-Rewrite-URL`, `X-Forwarded-Proto`, `X-Forwarded-Scheme`. If the page reflects these and the cache key excludes them, one attacker request poisons the CDN cache for all users.

PoC: GET `/` with `X-Forwarded-Host: evil.com`; check response body for `evil.com`; then make unprimed GET; if cached, reflects for everyone.

Fat-GET: GET with body that causes state change. Some CDNs cache GETs regardless of body.

## Request smuggling

CL.TE / TE.CL / TE.TE / H2.CL. Test via:
- `smuggler.py` against a sandbox that includes the real reverse proxy.
- Only meaningful with a multi-hop stack (CDN/LB + app).

## HPP (HTTP Parameter Pollution)

`?role=user&role=admin` — frameworks differ:
- Express: gets last → `admin`.
- PHP: gets last.
- Python Flask: first via `args.get`, list via `args.getlist`.
- Rails: last.
- JSP/Spring: array.

Check parsers on both sides (proxy + app) — disagreement is the vuln.

## Auth specifics for web

### Password reset
- Token is random ≥ 128-bit, single-use, expires (15–60 min typical).
- Token invalidated on use.
- Token invalidated on password change from a different session.
- Reset email does not contain the token in the URL of an analytics pixel (token leaks to 3rd party).
- Change of email/phone during a reset window requires re-auth or invalidates pending reset.

### MFA
- Enrollment rate-limited per account.
- Backup codes single-use and hashed at rest.
- Total-count of backup codes rotates on full-use regeneration.
- Downgrade paths: ensure there's no way to skip `/verify-mfa`.
- "Remember this device" cookie is bound to IP/UA or at least rotated.

### OAuth/OIDC
- `state` required and server-validated (ties back to session).
- PKCE required for public (SPA/mobile) clients.
- `redirect_uri` exact-match (not prefix).
- `response_mode=form_post` for implicit (or better, don't use implicit).
- `nonce` validated on ID tokens.
- Tokens not in URL fragments visible to frontend JS for longer than needed.

### Session
- Regenerate on login and privilege change.
- Idle timeout and absolute timeout.
- Invalidation on password change, MFA rotation, logout (server-side).
- Device list management for the user.

## Security headers checklist

```
Content-Security-Policy: <tight policy>
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), camera=(), microphone=(), ...
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp        (if you need crossOriginIsolated)
Cross-Origin-Resource-Policy: same-origin
X-Frame-Options: DENY                             (if CSP frame-ancestors isn't set)
```

## File upload

Defensive checklist:
- MIME sniffed by magic bytes (not client-supplied `Content-Type`).
- Allow-list, not deny-list.
- Randomize filename on server; never preserve user filename as storage key.
- Size cap enforced before full read.
- For archive uploads (zip/tar/7z): extraction to a temp dir with realpath+prefix check; reject symlinks; cap expansion ratio.
- Images: parse in a fork/container, not in the web process. Re-encode (strip metadata) before storing.
- SVG: render as a raster and discard, OR sanitize with a real SVG sanitizer, OR serve with `Content-Disposition: attachment`.
- Served out of a separate origin (`usercontent.example.com` vs `app.example.com`) to isolate CSP.
- `Content-Disposition: attachment` for non-inline types.
- `X-Content-Type-Options: nosniff` on the serving response.
