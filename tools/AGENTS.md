# `tools/` — shared first-party projects

Profile-independent projects, one directory each, symlinked into `~/.claude/tools/` by
`install.sh` step 12. A tool exposing a Makefile `install` target is then offered a build
by step 13 — the symlink alone gives no signal that an installed artefact is older than
the source.

Three of them are VS Code extensions on the same stack (TypeScript, esbuild, vitest):
`agent-watch`, `claude-usage`, `worktree-sync`. `rdev-bootstrap` and `forge-watch` are shell
projects and share none of this — they need no build, so step 13 never offers them one.

`forge-watch/watch.sh` is the watcher autopilot Step 5 points at, and it exists because
every run used to hand-roll its own poll loop. It makes one `gh api graphql` call and uses
**no external `jq` and no `gh <subcommand> --json`**, which is not a style choice: phone
sessions run these same skills on `piserver`, where `jq` is absent and `gh` is old enough
that `gh pr checks --json` does not exist. A loop built from either fails on every poll
there, and a `2>/dev/null` around it makes that look like an empty result.

## The shared scaffold

The three extensions were written at different times and carried byte-identical build
files differing only by the tool name. Nothing kept the copies in step and two had
drifted silently, so the scaffolding now lives here once:

| File | What a tool does with it |
| --- | --- |
| `extension.mk` | `TOOL := <name>` plus one `include`. The tool's whole Makefile. |
| `tsconfig.base.json` | `extends`, plus its own `outDir`, `rootDir` and `include`. |
| `vitest.base.ts` | `defineConfig(vitestConfig(import.meta.dirname))`, plus optional env. |
| `esbuild.base.mjs` | `run(esbuild)`, plus any extra bundle such as a webview. |
| `.gitignore` | Nothing. One file covers `*/node_modules/`, `*/dist/`, `*/*.vsix`. |

Nothing runnable is committed, so every machine builds. A box that skipped step 13 has
the extension id registered with no `dist/extension.js` behind it: it lists as installed
and silently never activates.

## Five things an edit here will otherwise re-discover

**`HERE` uses `$(firstword $(MAKEFILE_LIST))`, never `lastword`.** After an `include` the
last entry is `extension.mk`, so `make link` would point the editor's extension directory
at `tools/` rather than at the tool. Make guarantees the first entry is the primary
makefile.

**The include is makefile-relative**, not cwd-relative. `install.sh` runs
`cd "$tool_dir" && make install`, while its own retry hint is
`make -C tools/<tool> install`. A cwd-relative path survives only one of those.

**`outDir`, `rootDir` and `include` stay in each tool's own tsconfig.** TypeScript rebases
relative paths in an extended config against the file they are written in, so a shared
`"outDir": "dist"` would mean `tools/dist`. Keeping them local is also what keeps
`rootDir` explicit, which TS 6 — the compiler VS Code paints the Problems tab with —
requires rather than inferring from `include`. For the same reason, never put a shared
source file outside a tool's `src/` and import it *from* `src/`: that is `TS6059`.

**Neither shared JS file may import its own package.** There is no `node_modules` at
`tools/` or any parent, so a bare `import 'esbuild'` here does not resolve.
`vitest.base.ts` therefore returns a plain object and leaves `defineConfig` to the tool,
and `esbuild.base.mjs` takes the esbuild module as an argument.

**`install.sh`'s `tool_has_install_target` follows the include.** It decides whether to
offer a tool a build by grepping for `^install:`; reading only the tool's own Makefile
would silently stop step 13 offering any of these three.

## The packaging guards

`make package` refuses to run without a `.vscodeignore`, and fails when the built vsix
exceeds `MAX_VSIX_KB` (120, overridable per tool). Both exist because the absence of a
`.vscodeignore` is invisible from the outside: `agent-watch` shipped 97 files / 239KB
against `claude-usage`'s 6 / 24KB — all of `src/`, every `*.test.ts`, both source maps,
the 64KB `DESIGN.md`, and a production dependency esbuild had already bundled into
`dist/extension.js` — and the installer called it a success.

Pick the ceiling from both ends. The current packages are 38/23/14KB, so 120KB leaves
room to grow; the bloated one measured 239KB, so a generous 400KB would have passed it
and guarded nothing.

`--baseContentUrl` / `--baseImagesUrl` must survive any edit to the `package` recipe.
`vsce` resolves every relative README link against the repository it would be published
from and **errors out** rather than warning when none is detectable;
`--allow-missing-repository` does not cover it. `agent-watch`'s README links `DESIGN.md`,
which is no longer in the package, so the rewritten GitHub URL is the only thing keeping
that link working.

## Tests

`make install` runs the suite, so a test that asserts the kernel did something — an
`fs.watch`/inotify event arriving within a timeout — turns an ordinary install into a
hard failure on containers, overlay and network filesystems, or a box that has exhausted
`fs.inotify.max_user_watches`. Make the code guarantee the behaviour itself and assert
*that*; treat the OS fast path as an optimization allowed to do nothing.

`src/testing/vscodeStub.ts` stays **per-tool**. It must cover the whole `vscode` surface
that tool's `activate()` touches; a missing property throws inside fire-and-forget
background work and surfaces as a vitest *unhandled error*, so the suite reports every
test passing while the process exits non-zero. Converging the three was considered and
rejected — the genuinely shared surface is about 25 lines and the rest was rename churn.

## Verifying a change to the scaffold

```bash
cd tools/<tool> && mise exec -- make check          # typecheck, test, build
cd tools/<tool> && mise exec -- make package        # both guards, and the size
touch tools/<tool>/package-lock.json && cd tools/<tool> && mise exec -- make -n build
```

The last one must print `npm install`. That prerequisite is what had drifted.

Reproduce what the editor's Problems tab sees — not what `npm run typecheck` sees — by
driving `createProgram` against the compiler VS Code bundles at
`/Applications/Visual Studio Code.app/Contents/Resources/app/extensions/node_modules/typescript/lib/typescript.js`.
It ships `typescript.js` and `_tsserver.js` but no `tsc.js`, so there is no binary to run.

---

## The decisions behind the scaffold, the packaging guards and the installer step

Everything above is the current shape. Below is why each piece is that shape — the drift
the shared scaffold ended, the two guards that make a repeat mechanical rather than
remembered, and the three traps an edit to `extension.mk` or a `tsconfig` will otherwise
re-discover.

### Shared tools

First-party projects that are not tied to one machine go in `tools/<name>/` at the repo root rather than being duplicated per profile. Build output (`node_modules/`, `dist/`, `*.vsix`) is ignored by one `tools/.gitignore` — **nothing runnable ships in git**, so every machine must build, and a box that skipped step 13 has the extension id registered with no `dist/extension.js` behind it: it lists as installed and silently never activates. `editor_cli()` is what makes that step reachable on a Remote-SSH box: `code` is only on PATH inside the integrated terminal, so it also globs `~/.vscode-server/{cli/servers/*/server,bin/*}/bin/code-server` (newest first) and **proves** each candidate with `--list-extensions` before using it — `bin/*/bin/remote-cli/code` needs `$VSCODE_IPC_HOOK_CLI` and exits non-zero without a window, which is precisely the case that has to fall through

### The three editor extensions share one scaffold, and the drift it ended had already shipped

`agent-watch`, `claude-usage` and `worktree-sync` were written at different times and carried byte-identical Makefiles, tsconfigs, vitest configs, esbuild configs and `.gitignore`s, differing only by the tool name — with nothing keeping the copies in step, so two had silently diverged. `agent-watch`'s `$(DEPS)` prerequisite read `package.json` where the others read `package.json package-lock.json`, so a pulled lockfile change never re-ran `npm install` there; and `agent-watch` had **no `.vscodeignore` at all**, so `vsce` shipped 97 files / 239KB against `claude-usage`'s 6 / 24KB — all of `src/`, every `*.test.ts`, both source maps, the 64KB `DESIGN.md`, and `node_modules/d3-hierarchy`, **which esbuild had already bundled into `dist/extension.js`**, so the dependency shipped twice. The installer reported success on both. `tools/extension.mk` now holds the whole body behind `TOOL`, and each Makefile is two lines. Five things are load-bearing. **`HERE` must use `$(firstword $(MAKEFILE_LIST))`**, not `lastword`: after an `include` the last entry is `extension.mk`, so `make link` would point the editor's extension directory at `tools/` instead of the tool — make guarantees the first entry is the primary makefile. **The include itself is makefile-relative** (`include $(dir $(lastword $(MAKEFILE_LIST)))../extension.mk`), because the installer runs `cd "$tool_dir" && make install` while its own retry hint is `make -C tools/<tool> install`, and a cwd-relative path only survives one of those. **`outDir`, `rootDir` and `include` cannot move into `tools/tsconfig.base.json`** — TypeScript rebases relative paths in an extended config against the file they are written in, so a shared `"outDir": "dist"` means `tools/dist`; keeping them per-tool is also what satisfies the standing rule that `rootDir` stay explicit. **Neither shared JS file may import its own package**: there is no `node_modules` at `tools/` or any parent, so `vitest.base.ts` returns a plain object and leaves `defineConfig` to the tool, and `esbuild.base.mjs` takes the esbuild module as an argument. And **`install.sh`'s `tool_has_install_target` had to learn to follow the include** — it greps the tool's own Makefile for `^install:`, so hoisting the body silently stopped step 13 offering any of the three a build, which is the failure one line above this one: an extension id registered against a `dist/` nobody rebuilds. The guard against a repeat is mechanical rather than remembered: `package` refuses to run without a `.vscodeignore`, and fails when the vsix exceeds `MAX_VSIX_KB`. That ceiling is **120KB against actuals of 38/23/14KB**, and the number is chosen from both ends — the bloated package measured 239KB, so the generous 400KB first written would have passed it and guarded nothing

### A README link to a sibling file fails `vsce package`

vsce resolves every relative link in the README against the repository it would be published from, and with none detectable it **errors out** rather than warning — `--allow-missing-repository` covers the missing `repository` field, not the link. An in-page anchor (`[...](#heading)`) is fine, which is why `claude-usage` packages and `agent-watch`'s `[DESIGN.md](DESIGN.md)` did not. Each tool's `package` target therefore passes `--baseContentUrl`/`--baseImagesUrl` built from `REPO_URL`/`RAW_URL`, so the link keeps working for a human reading the repo and packaging stops depending on what the README happens to link. The failure is loud in the installer's output and invisible afterwards: step 13 prints `Failed to install <tool>` and moves on, leaving a tool that is symlinked into `~/.claude/tools/` and absent from `--list-extensions`.

### Never gate an install on OS-dependent behaviour

`make install` runs the test suite, so a test that asserts the kernel did something — `fs.watch`/inotify delivering an event, a filesystem notification arriving within a timeout — turns an ordinary install into a hard failure on any box where that mechanism is unavailable (containers, overlay and network filesystems, or an exhausted `fs.inotify.max_user_watches`). Make the code guarantee the behaviour itself (a `stat` poll backing a file watch) and assert *that* guarantee; treat the OS fast path as an optimization that is allowed to do nothing. A test simulating the failure (`fs.watch` throwing `ENOSPC`) is worth more than one hoping the platform cooperates

### The editor's tsserver runs ahead of the pinned compiler

VS Code bundles its own TypeScript (6.0.3 today) and paints the Problems tab with it, while `tools/*` pin `typescript: ^5.7.0` and build with esbuild — so a diagnostic from the next major shows up permanently in the editor and never in `npm run typecheck`, `make check` or CI. Fix the config rather than living with it. `rootDir` is the first one: TS 6 requires it to be explicit instead of inferred from `include`, so both tools set `"rootDir": "src"` beside `outDir`, which changes no output and makes a stray file outside `src` an error instead of a silent `dist/` reshuffle. Reproduce what the editor sees with the bundled compiler API at `/Applications/Visual Studio Code.app/Contents/Resources/app/extensions/node_modules/typescript/lib/typescript.js` — it ships `typescript.js` and `_tsserver.js` but no `tsc.js`, so drive `createProgram` directly

### Extension test stubs

`src/testing/vscodeStub.ts` in each tool must cover the whole `vscode` surface `activate()` touches. A missing property (`vscode.extensions`, `window.showWarningMessage`) throws inside fire-and-forget background work, which surfaces as a vitest *unhandled error* — the suite still reports every test passing while the process exits non-zero, so `make check` and `make install` fail with nothing obviously wrong. Add the property to the stub rather than defending in product code, and have `activate()` `.catch()` its background promises so one failure can never take down the run

### rdev bootstrap

`tools/rdev-bootstrap/bootstrap.sh` is started in the background by the first interactive zsh on an rdev box (`.zshrc.local`), so nothing runs until a terminal opens. It clones **every** repo before setting any up, so one slow setup (Demeter's installer) can't keep the others from being cloned, and runs each repo's setup in a child under `timeout` (`RDEV_BOOTSTRAP_SETUP_TIMEOUT`, default 1200s) so a hung step fails that repo and lets the run finish. Failed repos retry on the next shell. A shell opened while it runs prints the last log line instead of staying silent
