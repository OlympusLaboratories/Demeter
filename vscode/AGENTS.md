# `vscode/` — the shared editor settings

One `settings.json` serves every machine. It is symlinked **wholesale** over the editor's
user settings on every editor user directory that exists, so VS Code writes UI changes
back into this repo and a `/config` edit lands here as a tracked diff. `vscode/lib.sh`
owns the resolvers (`editor_cli`, `vscode_user_dirs`, `editor_has_extension`,
`tool_extension_id`, `read_extension_list`) and is shared with `install.sh` and
`uninstall.sh`; nothing here may print, because those three scripts define their own
`info`/`warn`/`ask`.

The root `CLAUDE.md` carries the invariants. This file carries why each one is the way it
is — four of the five sections below exist because a wrong value here **fails silently**:
the scope matches nothing, the pin loses to a workspace file, or the toggle no-ops, and
nothing reports any of it.

## What an edit here has to know

### Editor settings

`vscode/` holds one shared `settings.json`, not a per-profile copy — the point is an identical editor everywhere. Color fixes belong in its `workbench.colorCustomizations` (theme-scoped, so light and dark each get correct values), never in a per-repo `.vscode/settings.json`. Anything Peacock also writes must be listed in `peacock.excludedSettings`, or Peacock's workspace-level write will outrank the user-level pin — but an exclusion only stops *future* writes, and it means "never modify or delete", so `Peacock: Remove All Colors` leaves the excluded keys behind. Adding a key to that list is only half a fix: the stale copies already in each repo's `.vscode/settings.json` have to be stripped by hand (see the Peacock section of `README.md`). Prefer a fix that holds for **any** theme over one scoped to the theme in use — a `[Theme Name]` block only ever fixes the theme you have today, and the light/dark toggle is there to be repointed. See the Editor Settings section of `README.md` for why the High Contrast themes broke the Claude Code webview

### Peacock favorites

`peacock.favoriteColors` replaces Peacock's shipped list rather than extending it, so the whole palette lives in `vscode/settings.json` — 12 hues 30° apart in a `Neon` and a `Dusk` family, the prefix being what lets the favorites quick pick filter to one family. Peacock paints the title, activity and status bars with the chosen color and picks the text between `#15202b` and `#e7e7e7` on a brightness threshold, so a saturated mid-tone can sit just past the boundary at 2.5:1 — every value is therefore the lightness nearest its family target that still clears 4.5:1 against the foreground that threshold picks, checked rather than eyeballed. Keep that check when adding a hue; the white-on-65%-black command center scrim is a separate guarantee and does not cover the bars

### `workbench.experimental.modernUI` is off on purpose

it defaults to *on* and reroutes the chrome away from the theme. Tabs resolve `modernEditorTab.activeForeground` → `modernTab.activeForeground` → **`list.inactiveSelectionForeground`**, consulting the theme's `tab.*` only when that key is *explicitly customized* in `workbench.colorCustomizations`, and the command center becomes the agent-status pill, which forces a transparent background so `commandCenter.background` is never painted. Light themes almost all use white list-selection text, so under modern UI the active tab label is invisible (every light theme installed here measures 1.00–1.23:1) and the Peacock scrim silently stops working. Turning it off restores both for every theme at once; per-theme `[Theme Name]` pins would have to be written again for each new theme. Don't re-enable it without re-checking those two

### Theme ids

`workbench.colorTheme`, the `workbench.preferred*ColorTheme` keys, and the `[Theme Name]` scopes in `workbench.colorCustomizations` all take a theme's **settingsId** — `contributes.themes[].id` falling back to `label`, which is often not the display name (`Dark Modern`, not `Default Dark Modern`; only the High Contrast themes carry the `Default` prefix). A wrong id fails silently: the scope matches nothing, and the light/dark toggle no-ops. Scopes match by exact id or a `*` glob at either or both ends, on the name only — there is no scope for "every dark theme"

### `comm` needs one case and one collation, and it reports a difference that is not there rather than complaining

`vscode/sync-extensions.sh` fed it two `sort -f` outputs, which is wrong twice over. `--list-extensions` reports a publisher's **registered case** while the list on disk is lowercase, so a mixed-case id shows up as both an add and a drop — measured at two spurious adds and two spurious drops over a two-id list. And plain `sort` is **locale-collated**: glibc at `en_US.UTF-8` ignores punctuation at primary strength, so `ms-vscode.makefile-tools` and `ms-vscode-remote.remote-ssh` order one way on the rdev box and the other on macOS, which would rewrite the whole 41-line file on the first sync from the other machine and flip-flop forever after. The fix is `tr '[:upper:]' '[:lower:]'` plus **`LC_ALL=C` on every `sort` and every `comm`**, narrow prefixes rather than an exported `LC_ALL` so the glyph output and `grep` behaviour are untouched. The reason it must be pinned on both sides rather than merely made consistent is that **`comm` does not validate its input**: verified here, `comm -13` over unsorted input printed a line that was in neither difference and exited `0`, so a collation disagreement between `sort` and `comm` is undetectable from the output. It is a free fix today — the committed list is all-lowercase and byte-identical under `LC_ALL=C sort`, so nothing churns. One guard comes with it: `tool_extension_id` shells out to `python3` and reports a missing interpreter the same way it reports a `package.json` with no publisher, so a machine without `python3` would compute an empty exclusion set and write the locally-built `dylanlarrabee.*` ids into the shared list, sending every other machine to the Marketplace for extensions that are not there — the script now refuses to run rather than recording that
