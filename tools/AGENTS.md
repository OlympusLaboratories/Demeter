# `tools/` — shared first-party projects

Profile-independent projects, one directory each, symlinked into `~/.claude/tools/` by
`install.sh` step 11. A tool exposing a Makefile `install` target is then offered a build
by step 12 — the symlink alone gives no signal that an installed artefact is older than
the source.

Three of them are VS Code extensions on the same stack (TypeScript, esbuild, vitest):
`agent-watch`, `claude-usage`, `worktree-sync`. `rdev-bootstrap` is a shell project and
shares none of this.

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

Nothing runnable is committed, so every machine builds. A box that skipped step 12 has
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
would silently stop step 12 offering any of these three.

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
