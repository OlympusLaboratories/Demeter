# CLI / library methodology

Loaded when recon classifies target as `cli` or `library`.

## Argument handling

- **Flag injection**: when a CLI builds subprocess commands from user-controlled strings, an attacker controlling a filename or argument can sneak `--` flags:
  - `git clone --upload-pack=<command>` — RCE via clone of an attacker-named path.
  - `ssh -o ProxyCommand=<command> host` — RCE.
  - `curl -K <file>` reads config.
  - `find . -exec <command> \;` attacker-controlled paths inject.
  - `wget --use-askpass=<command>`.
  - `rsync -e <command>`.
- **Argument boundary**: tools should pass `--` after flags before variadic args to cap flag parsing.
- **Environment-variable injection**: some tools consume `GIT_SSH_COMMAND`, `LD_PRELOAD`, `LD_LIBRARY_PATH`, `PATH` — a library call that forks a child without sanitizing env inherits these.

## File handling

- **Path handling in user-provided paths**: `os.path.join(base, user)` — if `user` starts with `/`, `join` discards `base` (Python behavior). Same on Go `filepath.Join` (cleaned) — but `os.Chdir` then open relative is a classic trap.
- **Symlink attacks**: TOCTOU on `stat` then `open`. Prefer `openat` with `O_NOFOLLOW` or validate via `realpath` + prefix check.
- **World-writable temp**: `/tmp/my-app.log` → symlink attack. Use `mkstemp` / `TempDir::new()` / OS-appropriate temp API.
- **Home-directory handling**: `~` expansion happens in shell, not in most language APIs. If the CLI accepts `~/foo`, expand explicitly and safely.

## Secrets handling

- Don't read secrets from command-line arguments (`ps` exposes them). Use env, stdin, or config file with strict perms (0600).
- Env-var secrets are visible in `/proc/<pid>/environ` to the same user; not a leak across users unless proc perms are lax, but a leak to any child process unless cleared.
- Config files: check permissions at read time; refuse to load if world-readable and the file contains sensitive fields.
- Keyring integration: prefer OS keyrings for persistent secrets.

## Update / self-update

- Binaries that self-update MUST verify signatures of the new binary.
- No blindly-exec'd downloaded scripts (`curl | sh` pattern; if your install doc is that, the attack is the supply chain).
- Pin CA trust store; don't disable TLS verification on fetch.
- Rollback: keep the old binary; check it can roll back.

## Library API surface

When auditing a library (not a CLI):

- Identify the public API (exports). This is the entry-point set.
- For each public function that handles untrusted input (parses, evals, executes, networks), threat-model as if it's an HTTP handler.
- Document memory safety expectations (for C/C++/Rust `unsafe`): buffer-length validation, integer overflow, UAF.
- Serialization / deserialization entry points are high risk.
- Default configurations: do they fail closed? A library that defaults to "don't verify TLS" is a finding.
- Public headers / types may leak internal invariants.

## CLI-specific tests

- **Arg fuzzing**: `cargo-fuzz`/`go test -fuzz`/`atheris` on the arg parser, especially for CLIs that take positional paths and many flags.
- **Env fuzzing**: randomize and long env values to check for buffer issues in older C code.
- **stdin**: large inputs, null bytes, binary data, invalid UTF-8.
- **TTY vs pipe behavior**: tools that print differently on TTY can have ANSI-escape injection through log data to a user's terminal (CWE-150).

## ANSI-escape injection

If the CLI logs user-provided data to a terminal without filtering:
```
\x1b]2;evil\x07            sets window title
\x1b]8;;file:///etc/passwd\x07text\x1b]8;;\x07    clickable link
\x1b[?1049h                 alternate screen buffer
```
CVE examples: CVE-2023-2449 (git), historical `less`, various terminal multiplexers. Fix: strip escapes from untrusted input before printing, or log to files rather than TTY for untrusted sources.

## Distribution

- Checksums published over the same channel as the binary are weak (channel compromise → both change).
- Prefer detached GPG/cosign signatures with the signing key in a separate trust channel.
- Release hashes in the source repo (`SHA256SUMS`) signed.
- For npm/PyPI/crates.io/etc.: check the publish config — 2FA on the publish account, scoped tokens for CI, no long-lived tokens.
