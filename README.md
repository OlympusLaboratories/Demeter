# Demeter

A shared dotfile repo. Each machine setup lives in its own profile directory under `profiles/`. An interactive install script symlinks everything to the right places on any machine.

## Structure

```
Demeter/
├── install.sh          # interactive symlink installer
├── uninstall.sh        # removes symlinks / restores a clean state
├── _starter/           # copy this to get started
│   └── .bash_profile
├── _vendor/            # vendor packages — skills + tools (git submodules)
├── tools/              # first-party projects, shared by every profile
│   ├── claude-usage/   # VS Code extension, synced to ~/.claude/tools/
│   └── worktree-sync/  # VS Code extension, synced to ~/.claude/tools/
├── shell/              # terminal experience, shared by every profile
│   ├── terminal.zsh    # gap-filling zsh fragment, sourced last from each rc
│   ├── starship.toml   # prompt config (a copy of rdev's)
│   ├── tmux.conf       # symlinked to ~/.tmux.conf (~/.tmux.conf.local on rdev)
│   └── install-tools.sh  # installs starship, fzf, fd, bat + the zsh plugins
├── vscode/             # editor settings, shared by every profile
│   ├── settings.json   # symlinked over VS Code's user settings.json
│   ├── extensions.txt  # extensions the installer keeps present
│   └── sync-extensions.sh  # refresh that list from this machine
└── profiles/           # one directory per machine profile
    └── <profile>/      # e.g. larrabeedylan_work_linux
        ├── .bash_profile
        ├── .zshrc
        ├── .zshrc.local  # rdev: sourced by rdev's managed ~/.zshrc
        └── .claude/
            ├── CLAUDE.md   # global instructions, synced to ~/.claude/CLAUDE.md
            ├── settings.json  # permissions + hook registrations
            ├── skills/     # Claude Code skills, synced to ~/.claude/skills/
            ├── hooks/      # hook scripts, synced to ~/.claude/hooks/
            └── scripts/    # helper scripts used by skills
```

## Setup

1. Clone the repo somewhere permanent (e.g. `~/Demeter`)
2. Add your dotfiles in a profile directory under `profiles/`
3. Run the installer, optionally naming the profile to install:

```bash
./install.sh [profile]          # e.g. ./install.sh larrabeedylan_work_linux
```

`profile` may be a directory name under `profiles/` or a path to a profile
directory. If omitted, the installer auto-selects when only one profile exists
and otherwise prompts you to pick one. Run `./install.sh --help` to list the
available profiles.

The script will:
- Install the profile you selected (by argument, auto-detected, or chosen from the menu)
- Detect whether you're on macOS or Linux
- Symlink each dotfile to `~/`
- On an rdev box, skip anything rdev manages (`~/.rdev-managed.json`, e.g. `~/.zshrc`, `~/.tmux.conf`) — customize those through `~/.zshrc.local` and `~/.tmux.conf.local` instead
- Symlink `.claude/` contents (including skills) to `~/.claude/`
- Symlink vendor skills from `_vendor/` into `~/.claude/skills/`
- Symlink shared tools from `tools/` into `~/.claude/tools/`
- Offer to build and install any shared tool that has an `install` target (prompted, skippable)
- Symlink the shared shell config from `shell/` and offer to install the terminal tools it needs (see [Terminal](#terminal))
- Symlink `vscode/settings.json` over VS Code's user settings (see [Editor Settings](#editor-settings))
- Install any extensions in `vscode/extensions.txt` that are missing (prompts first)
- Clean stale skill symlinks (e.g. after a skill is renamed or removed from the repo)
- Create data directories for skills that accumulate context
- Back up any existing real files before replacing them
- Skip already-correct symlinks

Re-run it anytime after pulling changes — it's idempotent.

## Uninstalling

To un-symlink everything and start fresh:

```bash
./uninstall.sh
```

The script will:
- Remove every symlink in `~/` and `~/.claude` whose target points back into this repo (layout-agnostic — it reverses whatever was linked)
- Remove the templated `~/.claude/settings.json` copy (prompts first)
- Remove the VS Code `settings.json` symlink and offer to restore the backup taken at install time
- Clean up now-empty skill directories left behind

Your repo files are never touched, and skill data directories are left in place.

## Adding Your Dotfiles

```bash
cp -r _starter profiles/<your-profile>
cd profiles/<your-profile>
# add your .zshrc, .bash_profile, .claude/skills, etc.
```

## Machine-Specific Files

If a file should only be linked on one machine type (macOS vs Linux), add it to the `SKIP_LIST` array near the top of `install.sh`:

```bash
SKIP_LIST=(
  ".bash_profile:linux"   # skip on linux, link on mac only
  "some-file:mac"         # skip on mac, link on linux only
)
```

## Editor Settings

`vscode/settings.json` is profile-independent, like `tools/`, and is symlinked
**wholesale** over VS Code's user settings so every machine renders identically:

| Platform | Link target |
| --- | --- |
| macOS | `~/Library/Application Support/Code/User/settings.json` |
| Linux | `~/.config/Code/User/settings.json` |

Insiders and VSCodium are linked too when their directories already exist. A
directory is only created by the editor's first launch, so on a fresh machine
launch VS Code once and re-run the installer. To opt a machine out entirely, add
`"vscode:linux"` (or `:mac`) to `SKIP_LIST`.

Two consequences of linking wholesale are worth knowing:

- **VS Code writes through the symlink.** Changing the zoom level or picking a
  theme from the UI edits the repo file, and shows up as a tracked diff. Commit
  it or `git checkout` it, but don't be surprised by it.
- **Machine-specific keys are shared.** `window.zoomLevel` and
  `claudemeter.debugLogFile` are the two that genuinely differ per machine. They
  are kept last in the file so they're easy to spot in a diff.

Over Remote-SSH the theme comes from the **client** machine, so linking on a
Linux dev box has no effect on how the editor looks — install on the laptop you
actually sit in front of.

### Why the color settings are there

VS Code's High Contrast themes signal state with borders rather than background
fills, so the registry leaves many background colors as `null` (the CSS variable
is never emitted) or as solid black. Webviews that paint backgrounds — the Claude
Code panel among them — then render those elements with no background at all:
the selected row in the slash-command list, backtick badges, and fenced code
blocks all disappear. `workbench.colorTheme` is pinned to Default Dark Modern,
and `window.autoDetectHighContrast` is off so an OS contrast setting can't drag
the editor back into an unrepaired High Contrast theme.

The `workbench.colorCustomizations` blocks pin the specific tokens the Claude
Code webview consumes (`list.activeSelection*`, `textPreformat.*`,
`textCodeBlock.background`, `badge.*`, `editorSuggestWidget.*`) to matching
values in each theme, so light and dark differ in palette but not in which
elements are visible.

### Why modern UI is off

`workbench.experimental.modernUI` defaults to **on** in current VS Code, and it
takes the workbench chrome's colors away from the theme.

The tab strip stops reading the theme's `tab.*` entries:
`modernEditorTab.activeForeground` falls back through
`modernTab.activeForeground` to **`list.inactiveSelectionForeground`**, and the
theme's own `tab.activeForeground` is consulted only when that key is explicitly
customized in settings. Light themes near-universally set white list-selection
text — right on their accent-colored selection bar, invisible on a near-white
tab. Every light theme installed here lands between 1.00:1 and 1.23:1 on the
active tab label; every dark theme passes, which is why this only ever showed up
in light mode.

Modern UI also renders the command center as the agent-status pill, which forces
`background-color: transparent`. `commandCenter.background` is never painted, so
the scrim described under [Peacock](#peacock) silently stops working and its
white text lands directly on the title bar — at 1.3:1 in a window with no
Peacock color.

Customizing colors per theme fixes one theme at a time, and the next light theme
starts out broken again. `workbench.experimental.modernUI` is set to `false`
instead: every theme gets its own tab colors back (2.5–4.0:1 across the light
themes here — softer than AA, but what the theme author intended), and the scrim
paints again. Both hold for any theme installed later. The cost is the rounded,
editor-connected tab look; `workbench.experimental.modernUIEditorTabStyle` only
chooses between `connected` and `pill`, so there is no way to keep modern UI and
opt out of the color reroute.

`window.autoDetectColorScheme` is **off**, because it and manual theme switching
are mutually exclusive: the *Toggle between Light/Dark Themes* command bails out
with "Cannot toggle between light and dark themes when `window.autoDetectColorScheme`
is enabled in settings" whenever it's on.

With it off, that command reads `workbench.preferredLightColorTheme` and
`workbench.preferredDarkColorTheme` — the two keys pinned above — so toggling
flips between Default Light Modern and Default Dark Modern and nothing else.
Turn `autoDetectColorScheme` back on only if you'd rather the OS appearance drive
the theme and you give up the toggle.

### Extensions

`settings.json` can *name* a theme, but the theme only exists once its extension
is installed — VS Code falls back silently otherwise, which is how a shared
settings file still ends up looking different on two machines. `vscode/extensions.txt`
closes that gap: one extension id per line, and the installer offers to install
whatever is missing.

Installing is **additive**. An extension you have locally but that isn't in the
list is never removed, so a machine can keep its own extras.

After installing something from the Marketplace that you want everywhere:

```bash
vscode/sync-extensions.sh     # rewrites extensions.txt from this machine
git commit -am 'add <extension>'
```

The script shows what it's about to add or drop and asks before writing. If an
entry is in the list but not installed here it warns before removing it, since
that would stop your *other* machines getting it — run `./install.sh` first if
you simply haven't installed it on this machine yet.

Extensions built from `tools/` are excluded automatically. They aren't on the
Marketplace, so asking to install them by id would fail; their own `make install`
target handles them. The exclusion is derived from each tool's `package.json`,
so a new tool needs no change to the script.

The editor CLI is resolved from `PATH` first, then from the macOS app bundle, so
it works even without running *Shell Command: Install 'code' command in PATH*.

### Peacock

Peacock colors the title bar per repo and writes `commandCenter.foreground` and
`commandCenter.border` beside it, picking the foreground from two hardcoded
values by a luminance threshold.

Its pick clears 4.5:1 on most hues but not on saturated mid-tones (`#fd0bf2`
lands at 2.6:1), and it never writes `commandCenter.background`, so on those the
repo name in the title bar ends up unreadable.

The fix is `peacock.excludedSettings`, which Peacock documents as keys it must
never modify or delete. Every `commandCenter.*` key is listed there, and they're
pinned instead in `workbench.colorCustomizations` to white text on a 65% black
scrim — readable over any hue Peacock picks, in either theme. That scrim depends
on [modern UI being off](#why-modern-ui-is-off); with modern UI on,
`commandCenter.background` is never painted and the white text is left sitting on
the bare title bar.

Peacock writes into a repo's **workspace** `.vscode/settings.json`, which
outranks user settings, and a repo colored before the exclusions were added
still carries `commandCenter.foreground` and `commandCenter.border` from that
earlier write. On a light hue Peacock's pick is `#15202b`, and dark ink on the
65% black scrim is unreadable (1.3:1 on `#f97316`).

`Peacock: Remove All Colors` does **not** clear them — `peacock.excludedSettings`
means "never modify or delete", so the excluded keys are exactly the ones it
leaves behind. `vscode/strip-stale-peacock-keys.sh` removes them:

```bash
vscode/strip-stale-peacock-keys.sh
```

`install.sh` runs it on every install, so a machine repairs itself rather than
presenting a dim title bar with no obvious cause. It reads the key list from
`peacock.excludedSettings` rather than hardcoding it, so excluding a new key is
enough to have the sweep enforce it everywhere.

The sweep searches `$HOME` five levels deep, skipping `node_modules`, `.git`,
`Library` and similar; `PEACOCK_SCAN_ROOT` and `PEACOCK_SCAN_DEPTH` override
that if your repos live elsewhere. It lists what it found and asks before
writing, strips only the owned keys, and re-parses each file afterwards to
confirm nothing else changed — a file that packs several settings onto one line
is reported and left alone rather than rewritten.

With the keys gone the user-level pins apply and every hue lands between 8:1 and
18:1. Repos colored from here on never grow them, because the exclusions are in
place before Peacock writes.

#### Favorite colors

`peacock.favoriteColors` carries 24 colors — twelve hues at 30° apart (red,
orange, yellow, lime, green, spring, cyan, azure, blue, violet, magenta, rose)
in two families. **Neon** is full saturation at mid lightness, for repos that
should be impossible to miss; **Dusk** is the same twelve hues darkened and
muted (40% saturation, ~32% lightness), for everything else. Naming them
`Neon <hue>` and `Dusk <hue>` means `Peacock: Change to a Favorite Color`
filters to one family by typing its prefix.

Setting the key **replaces** Peacock's shipped favorites (Angular Red, Node
Green and the rest) rather than adding to them. `Peacock: Save Current Color to
Favorites` appends here, and because the file is a symlink that write lands in
the repo.

Every value is picked so Peacock's own foreground choice stays readable on it.
Peacock selects between `#15202b` and `#e7e7e7` by a brightness threshold, and a
saturated mid-tone can land just past it with nothing behind the text — pure
neon red, azure, magenta and rose all measured 2.5–3.1:1 that way. Each hue uses
instead the lightness closest to its family's target that clears 4.5:1 against
whichever foreground the threshold picks, which moved four neons and three dusks
by a few percent and left the rest untouched. The palette now spans 4.5:1 to
15.4:1 for Peacock's text, and 7.4:1 to 18.5:1 for the white-on-65%-black
command center scrim above.

### Global git ignore

Peacock writes its color into a repo's workspace `.vscode/settings.json`, which
leaves every repo dirty. `git/ignore` is the shared answer: it is linked to the
file git reads for machine-wide ignores, so no repo needs a committed
`.gitignore` change and nothing about it is per-profile.

```
**/.claude/settings.local.json
.vscode/settings.json
```

The destination is `core.excludesFile` when that is set, and otherwise
`$XDG_CONFIG_HOME/git/ignore` (`~/.config/git/ignore`) — the path git reads by
default, so nothing has to be configured to make it take effect. The installer
links whichever of the two applies, then proves it by running `check-ignore`
inside a throwaway repo, because a `core.excludesFile` pointing somewhere else
would otherwise leave the file silently inert. On an rdev box that lists the
path in `~/.rdev-managed.json` the step steps aside and says so.

The pattern is `.vscode/settings.json`, not `.vscode/`, so a repo can still
commit `extensions.json` or `launch.json` normally; only the file Peacock writes
is hidden. Two limits are worth knowing:

- **A gitignore never applies to a tracked file.** A repo that already commits
  `.vscode/settings.json` keeps showing Peacock's edit. Either commit the color
  or `git update-index --skip-worktree .vscode/settings.json` — and remember
  it's set, since `git ls-files -v | grep '^S'` is the only way to spot it and a
  pull that touches the file will error rather than merge.
- **Adding a real one later needs `git add -f`.**

## Terminal

Every machine gets the same terminal: the same prompt, history, completion and line editing.
The config is profile-independent and lives in `shell/`, linked by the installer.

What you get, once `shell/install-tools.sh` has run:

- **starship prompt** — directory, git branch and status, language versions, a green `❯` that
  turns red when the last command failed
- **zsh-autosuggestions** — the rest of the line in grey as you type, from history and
  completions; `→` accepts it, `Ctrl-→` accepts one word
- **zsh-completions** with a selectable menu and case-insensitive matching
- **↑/↓ prefix history search** — type `git co`, press `↑`, and walk only the matching history
- **fzf** — `Ctrl-R` fuzzy history, `Ctrl-T` files, `Alt-C` cd, backed by `fd`
- **zsh-syntax-highlighting** — commands colored valid/invalid as you type
- 50 000 lines of shared, deduplicated history; `bat` in place of `cat`; a tmux config that
  lets Claude Code's notifications and progress bar through and makes Shift+Enter work

All of it is borrowed from the rdev box's shell, which is where this started.

### How it stays consistent without fighting rdev

rdev builds its own terminal — it owns `~/.zshrc`, `~/.config/starship.toml` and
`~/.tmux.conf`, and rewrites them on image updates. Doing the same work again there would
double-load plugins and lose the argument with the next image bump. So `shell/terminal.zsh`
**fills gaps only**: each block checks whether the feature is already active
(`$+functions[prompt_starship_precmd]`, `$+functions[_zsh_autosuggest_start]`, …) and does nothing if
it is. On rdev it is nearly a no-op; on a fresh Mac it does everything.

The installer follows the same principle: `starship.toml` is skipped where
`~/.rdev-managed.json` claims the path, and `tmux.conf` is linked to `~/.tmux.conf.local` —
the hook rdev's own config sources — instead of over rdev's file.

Three load-order rules make it work, and `shell/AGENTS.md` explains them in full: `fpath`
before `compinit`, syntax highlighting after every widget (it loads from a one-shot `precmd`
hook, which is also what keeps rdev from loading it twice), and the `source` line staying last
in each profile rc. **If you add a section to a profile `.zshrc`, add it above that line.**

### VS Code shell integration is loaded by `terminal.zsh`, not injected

`vscode/settings.json` sets `terminal.integrated.shellIntegration.enabled: false` — and so
does `vscode/machine-settings.json`, the Remote-SSH machine settings, so an rdev box gets it
whichever client connects — and
`terminal.zsh` sources VS Code's `shellIntegration-rc.zsh` itself when `TERM_PROGRAM` is
`vscode`. You still get command decorations, the sticky scroll and the terminal cwd that
worktree-sync pairs on — only the delivery changes.

Automatic injection works by pointing `ZDOTDIR` at a temporary directory whose `.zshrc` sources
yours from `$USER_ZDOTDIR`. VS Code writes those variables into the environment it saves for
the terminal, and when it **revives** a terminal whose process died — every reload after an
rdev disconnect — it injects again on that saved environment, computing
`USER_ZDOTDIR=$ZDOTDIR`: its own directory. Its `.zshrc` then sources itself and returns, so
your rc never runs. The tell is a revived terminal (`History restored`) showing zsh's bare
`host%` prompt with no starship, writing history to `/tmp/<user>-code-zsh/.zsh_history`.
With injection off, VS Code never touches `ZDOTDIR` and there is nothing to loop on.

The script is found from `$VSCODE_GIT_ASKPASS_MAIN`, which points into the running VS Code
install on both the Mac app bundle and an rdev `~/.vscode-server`, so no CLI is spawned per
shell; `code --locate-shell-integration-path zsh` is the fallback. A terminal that was already
broken before this change keeps its saved environment — close it once.

### Tools

`terminal.zsh` degrades quietly when something isn't installed — no starship means a plain
git-aware prompt, no fzf means the builtin `Ctrl-R`. Convenient, but it also means a missing
tool looks like nothing happened, so the installer runs `shell/install-tools.sh --check` and
lists what's absent before offering to install it:

```bash
./shell/install-tools.sh --check   # print what's missing, one per line
./shell/install-tools.sh           # install it (brew, else apt, else direct download)
```

Plugins are cloned to `~/.local/share/zsh/<name>` — the same paths rdev uses, so one code path
serves both kinds of machine. On an rdev box the script exits immediately: the image ships
everything already.

## Claude Skills

`.claude/CLAUDE.md` is symlinked to `~/.claude/CLAUDE.md`, the user-level instruction file Claude Code loads in **every** repository. It currently carries one rule: do not add comments to code. Agent-written comments restate the line, go stale, and pad the diff for a human reviewer, so explanation belongs in the commit message and MR/PR description instead — with machine-read directives (linter suppressions, build pragmas, required doc-comments) exempt because they are program input rather than commentary. The code-modifying skills (`fix-linear`, `fix-feedback`, `review-code`, `review-kludge`, `security-audit`) each restate the rule locally, since a skill's subagents get the skill prompt rather than the user's `CLAUDE.md`.

Any directory under `.claude/skills/` is linked individually into `~/.claude/skills/`. Skills use `~/.claude/scripts/gitlab-api.sh` for GitLab API access (token read from `~/.claude/.mcp.json`, never exposed in conversation context; the GitHub profile uses `github-api.sh` and a `GITHUB_PERSONAL_ACCESS_TOKEN` instead). `fix-feedback` also writes through it: before fixing anything it posts each unique `review-code` finding to the MR as its own comment, anchored to the offending line, so the swarm's output survives the conversation — deduped against what the review bots already said, and gated on one batch approval. Swarm skills (`changes-description`, `review-code`, `review-kludge`) run through the **Workflow** tool; `workflow-resume` rescues a run that died mid-swarm, reading the on-disk run manifests and agent caches through `~/.claude/scripts/workflow-runs.py`.

Some skills accumulate user data (weekly reports, Slack context, the `plan-initiative` team roster) that is gitignored and lives in the repo directory but is not tracked. The install script creates necessary data directories automatically.

### Worktrees

The `fix-linear` and `fix-feedback` skills set up each fix in its own **git worktree** by default, so you can work several non-blocking fixes in parallel (one terminal/session per worktree) without branch checkouts colliding. See **[WORKTREES.md](WORKTREES.md)** for the full guide — the mental model, switching between worktrees, dependency setup, and cleanup. Pass `in place` to a skill (e.g. `/fix-linear ENG-123 in place`) to fall back to a plain in-place checkout.

Each profile's shell config also defines `go` (worktree-aware `git checkout` — `cd`s into the worktree when one holds that branch, checks out normally when it doesn't, and passes anything else like `go -b new` or `go .` straight to git), `wt` (jump to the worktree for a branch, creating it if needed), `wtl` (list worktrees with age, upstream state, and dirty flag), and `wtclean` (remove worktrees whose branch is gone from the remote or untouched for 90+ days — dry run unless `-y`).

### Session Hook

`.claude/hooks/` is linked into `~/.claude/hooks/`, and each profile's `settings.json` registers the hooks that run from there. One hook lives there today:

**`link-worktree-session.py`** (`PreToolUse` on `EnterWorktree`, `SessionStart`, `CwdChanged`, `Stop`) — makes every session in a repo visible from the main checkout's window, wherever it runs, so reloading the editor (which on a Remote-SSH box happens on every disconnect) never loses a worktree session.

Claude Code files a transcript under `~/.claude/projects/<slug of the session's directory>/`, and when a session enters a worktree it *moves* the transcript into the worktree's slug. The VS Code panel then rebuilds its list after a reload from the main checkout's slug only (`includeWorktrees: false`), and it opens each transcript with `O_NOFOLLOW`, so a per-file symlink back into that directory is silently dropped — that is what the hook used to do, and why worktree sessions vanished. Instead, the hook turns each worktree's project directory into a **symlink to the main checkout's project directory**. Claude Code checks whether the old and new directories resolve to the same place before moving a transcript, so the move becomes a no-op and every transcript stays a real file under the main checkout's slug.

`PreToolUse` creates that alias before `EnterWorktree` runs, so the common case never moves anything. The other events, and the backfill, migrate any worktree directory that is already real: they hard-link its contents into the main directory, swap the directory for the symlink atomically (`renameat2`/`renamex_np`), then drain what is left — a session writing during the migration loses nothing. A worktree whose transcripts collide with a different transcript of the same id in the main directory is left alone, and leftovers go to `~/.claude/backups/worktree-project-dirs/`. `install.sh` runs the backfill for you; run it by hand after importing transcripts from elsewhere:

```bash
~/.claude/hooks/link-worktree-session.py --backfill
```

Claude Code spawns hooks with a **bare `PATH`**, not the one your shell builds, so a `#!/usr/bin/env python3` hook that works perfectly when you run it yourself can still fail on every real session — and it fails invisibly, with no session ever appearing where you expect it. The installer therefore probes the hook under `env -i PATH=/usr/bin:/bin` and tells you when a system `python3` is missing, rather than assuming that linking the file was enough. A python3 that exists only under mise or a venv will not do.

### Claude Usage Extension

`tools/claude-usage/` is a VS Code extension that shows your Claude session and weekly quota in the status bar, so you don't have to run the usage skill to find out how close you are to a limit:

```
Session ●●○○○○ 33% 1h20m   Weekly ●●●○○○ 53% 5d20h   ⟳ now
```

Each meter is a label, a bar, the percent used, and the time until that window resets. Bar glyphs are configurable — run **Claude Usage: Choose Bar Style** to preview them live, since the status bar is drawn in the UI font and which glyphs look right depends on it. The chip on the end is the age of the reading; it turns yellow with a retry countdown when a fetch is failing or rate limited, so a percentage that has quietly stopped moving is obvious rather than silently wrong. It reads `https://api.anthropic.com/api/oauth/usage` — the endpoint behind Claude Code's `/usage` — once a minute while the window is focused, and not at all while it isn't.

Claude Code itself polls that same endpoint from every running session, and the rate limit is per account — so the extension is deliberately frugal. It compares each reading with the last and eases off when your quota is flat (60s → 120 → 240 → 480 → 600, snapping back to 60s the moment a percentage moves), because a fixed poll spends most of its requests re-reading identical numbers.

Easing off never costs you the reset, though: `resets_at` is absolute, so countdowns are recomputed locally and stay exact with no network at all, and the next poll is never scheduled past the soonest reset — so the new window is picked up the moment it opens.

That is also once a minute *in total*, not per window. Every window runs its own copy of the extension, so they coordinate through a cache in `~/Library/Caches/claude-usage/` (`$XDG_CACHE_HOME/claude-usage/` on Linux): whichever window is due first takes a lock file and fetches, the rest read what it wrote and update together through a directory watch. Six open windows still make one request a minute.

By default it borrows the login Claude Code already has: the `Claude Code-credentials` keychain item on macOS, `~/.claude/.credentials.json` elsewhere. That read is one-way — it never writes to or refreshes Claude Code's token, so it can't disturb your CLI session. Claude Code's access token only lasts a day, though, and only Claude Code renews it. If you'd rather the meters not depend on that, run **Claude Usage: Sign In With Browser** once: the extension does its own PKCE login in your real default browser (never a webview, so Okta SSO works), keeps the tokens in VS Code's `SecretStorage`, and refreshes them itself.

Installed the same way as any tool here, and configurable down to the bar glyphs. See [tools/claude-usage/README.md](tools/claude-usage/README.md) for the full settings table and the copy-paste sign-in fallback.

### Agent Watch Extension

`tools/agent-watch/` renders every Claude Code session on the machine — and the agents
each one spawns — as a live node-and-edge graph in an editor tab. It reads the JSONL
transcripts under `~/.claude/projects` and never writes to them. See its `README.md` and
`DESIGN.md` for the data model and the worktree scoping rules.

#### Seeing what agents were thinking (opt-in)

Thinking blocks are empty on disk by default: the API returns them that way, because
`thinking.display` defaults to `"omitted"`. agent-watch renders those as `thought · not
recorded` rather than inventing content.

`vscode/claude-wrapper.sh` launches Claude Code with `--thinking-display summarized`,
which makes the API return a readable summary of the reasoning that then persists to the
transcript and shows up in agent-watch. It resolves the binary the editor would have used
(newest `anthropic.claude-code-*` extension bundle, else `claude` on PATH), **probes the
flag before using it**, and launches normally if the installed build does not accept it —
the flag is undocumented and its accepted values already changed between 2.1.250 and
2.1.304.

It is **enabled**, via `claudeCode.claudeProcessWrapper`. That setting is declared
`"scope": "machine"` by the Claude Code extension, which is what makes this safe to commit:
machine-scoped settings are never synced between machines, and over Remote-SSH they are
read from the **remote** machine rather than the client. So each machine gets its own
correct absolute path:

| Machine | File | Value |
|---|---|---|
| macOS | `vscode/settings.json` | `/Users/dylanlarrabee/Demeter/vscode/claude-wrapper.sh` |
| Linux / rdev | `vscode/machine-settings.json` → `~/.vscode-server/data/Machine/settings.json` | `/home/dylanlarrabee/Demeter/vscode/claude-wrapper.sh` |

Get the path wrong and **Claude Code does not launch at all** in the editor — a far worse
failure than the other machine-specific absolute path in that file
(`claudemeter.debugLogFile`, where a wrong value merely costs a log). If the repo ever
moves, update both values. Delete the line on either side to revert that machine.

The flag applies to Claude Code sessions started after the change; existing sessions keep
the display mode they launched with.

The raw chain of thought is never available on any model; `summarized` is the ceiling.

### Worktree Sync Extension

`tools/worktree-sync/` is a VS Code extension that keeps the active **Claude Code tab** and the active **terminal** on the same worktree in both directions, so you can't type a prompt into one worktree's session while running commands in another. It is shared by every profile.

`install.sh` links every tool's source into `~/.claude/tools/` and then offers to build and install the ones exposing a Makefile `install` target. Answer yes and there is nothing else to do; the prompt exists because the build takes a couple of minutes. To do one by hand, or after editing the source:

```bash
make -C ~/.claude/tools/worktree-sync install
```

The build runs through `mise exec` when the tool has a `.mise.toml`, so it works from a shell where the pinned toolchain isn't activated.

A VS Code extension installs into `~/.vscode/extensions`, which every **profile** on the machine shares — but each profile chooses whether to enable it, so enable it once per profile.

**Over Remote-SSH it belongs on the remote, not the client.** It reads the transcript corpus under `~/.claude/projects`, which lives wherever your sessions actually run — install it on the client and it indexes the wrong machine's history and resolves nothing. The catch is that `code` is only on PATH inside VS Code's integrated terminal, so an installer run from a plain SSH shell used to skip the build without comment; it now also finds the CLIs under `~/.vscode-server/` and checks afterwards that the extension id really registered. Nothing runnable is committed — `dist/` and `*.vsix` are gitignored — so a box where that build never ran has the extension listed and no bundle behind it: it looks installed and silently never activates. `Worktree Sync: Show Diagnostics` names the failure when sync goes quiet.

`make link` is the development alternative: it symlinks the source into `~/.vscode/extensions/` so a rebuild picks up on a window reload. `make check` runs typecheck, tests, and build. See [tools/worktree-sync/README.md](tools/worktree-sync/README.md) for how tabs and terminals are matched and which settings it exposes.
