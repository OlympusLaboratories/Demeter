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
├── lib/                # shell libraries sourced by the installer and its siblings
│   └── paths.sh        # git_excludes_path + demeter_link_roots
├── tests/              # mechanical checks over the installer and its siblings
│   ├── check-link-roots.sh    # every link destination is under a declared root
│   └── uninstall-roundtrip.sh # plant a link under every root, sweep, assert none survive
├── tools/              # first-party projects, shared by every profile
│   ├── claude-usage/   # VS Code extension, synced to ~/.claude/tools/
│   └── worktree-sync/  # VS Code extension, synced to ~/.claude/tools/
├── shell/              # terminal experience, shared by every profile
│   ├── terminal.zsh    # gap-filling zsh fragment, sourced last from each rc
│   ├── starship.toml   # prompt config (a copy of rdev's)
│   ├── tmux.conf       # symlinked to ~/.tmux.conf (~/.tmux.conf.local on rdev)
│   └── install-tools.sh  # installs starship, fzf, fd, bat + the zsh plugins
├── vscode/             # editor settings, shared by every profile
│   ├── lib.sh          # editor CLI + path resolution, shared with install.sh
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
./install.sh [-y|--yes] [profile]   # e.g. ./install.sh larrabeedylan_work_linux
```

`profile` may be a directory name under `profiles/` or a path to a profile
directory. If omitted, the installer auto-selects when only one profile exists
and otherwise prompts you to pick one. Run `./install.sh --help` to list the
available profiles.

`-y` / `--yes` answers yes to every prompt, for a re-run you do not want to sit
through:

```bash
./install.sh --yes larrabeedylan_work_darwin
```

It needs the profile spelled out whenever more than one exists — there is no
safe default for which machine you are, and picking wrong links another
machine's dotfiles over yours. It is also the only prompt `--yes` will not
answer. The flag reads nothing from stdin, so piping into it still works if you
have a script that does; `--yes` is simply the version whose exit status is the
installer's own, rather than `141` from `yes` taking a `SIGPIPE` on the way out.

Everything it says yes to is in the bullet list below. Three of them are slow
rather than dangerous (building the shared tools, installing missing
extensions, installing terminal tools), and one writes outside the repo: the
Peacock sweep strips keys from `.vscode/settings.json` files under `$HOME` (see
[Editor Settings](#editor-settings)). `vscode/strip-stale-peacock-keys.sh`
takes the same `--yes` when run on its own.

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
- Create data directories for skills that accumulate context, only for the skills the selected profile actually ships
- Back up any existing real files before replacing them
- Skip already-correct symlinks

Re-run it anytime after pulling changes — it's idempotent.

## Uninstalling

To un-symlink everything and start fresh:

```bash
./uninstall.sh
```

Add `-y` / `--yes` to answer every prompt instead of reading stdin.

The script will:
- List the directories it is about to sweep, then remove every symlink in them whose target points back into this repo (layout-agnostic — it reverses whatever was linked)
- Offer to restore the editor `settings.json` backup taken at install time
- Clean up now-empty skill directories left behind

The directories it sweeps are declared once, as `demeter_link_roots` in `lib/paths.sh`, and the installer links into nothing else — `tests/check-link-roots.sh` fails CI if that stops being true. Today they are `~/`, `~/.claude` (recursively), `~/.config/zsh`, `~/.config`, whichever directory holds `core.excludesFile`, `~/.vscode-server/data/Machine`, and every editor user directory on both platforms. Only `~/.claude` is swept recursively; the rest are one level deep, which is all the installer writes into.

Two things changed about what it reaches. It now sweeps the four `~/.config` and `~/.vscode-server` roots it used to miss, so an uninstall no longer leaves a machine sourcing repo files. And the `~/` pass now considers **every** symlink there, not only dotfiles — so a convenience link like `~/dotfiles -> ~/Demeter` is removed too, where before it survived. Every removal is printed as it happens.

Your repo files are never touched, and skill data directories are left in place. So
is `~/.claude/.mcp.json`, which holds your MCP tokens — it is a real file rather than
a symlink, so the sweep never sees it.

## Adding Your Dotfiles

```bash
cp -r _starter profiles/<your-profile>
cd profiles/<your-profile>
# add your .zshrc, .bash_profile, .claude/skills, etc.
```

## Machine-Specific Files

If a file should only be linked on some machine types, add it to the `SKIP_LIST` array near the top of `install.sh`:

```bash
SKIP_LIST=(
  ".bash_profile:linux"   # skip on linux, link on mac and pi
  "some-file:mac"         # skip on mac, link on linux and pi
  "vscode:pi"             # skip on the Raspberry Pi, link elsewhere
)
```

`detect_machine` returns one of three values — `mac`, `linux` or `pi`. `both` is
not a machine type but a wildcard in the skip list itself, matching whichever of
the three you are on.

`pi` is detected from `/etc/rpi-issue` and exists because the Raspberry Pi app
host and the rdev box are both Linux while needing opposite treatment — the Pi
runs no editor, and its Claude Code config is owned by another repo. Detection
failing open would be expensive rather than cosmetic, so installing a `*_pi`
profile on a machine that did not detect as `pi` is refused outright.

The list is honoured by the dotfile loop, both `.claude/` loops,
`link_directory_contents`, and the `vscode`, `shell`, `tools` and `gitignore`
step gates. A new installer step that checks none of them will fire on a box
with no editor.

### The MCP token file on rdev

`~/.claude/.mcp.json` is the one file holding every MCP server's token. Nothing in
this repo contains it and nothing ever should, so on an ordinary machine you write
it by hand once and the installer leaves it alone.

An rdev instance cannot work that way. The instances are disposable, so anything
written by hand is gone the next time you are handed a fresh one. rdev carries files
across instances from GCP, but only at an **allowlisted set of paths**, and
`~/.claude/.mcp.json` is not one of them — so the token file is persisted at a path
that is: `~/.config/nvim/mcp.json`. That name is a constraint of the persistence
service and an otherwise unused slot. **There is no nvim integration here, and no
nvim plugin reads or writes it.** `grep -rn nvim` across this repo hits exactly one
line, and it is the installer step below.

The chain, on a fresh instance:

1. rdev's persisted-files service restores the token file from GCP to
   `~/.config/nvim/mcp.json`, before any of this repo runs.
2. Installer step 10 copies it to `~/.claude/.mcp.json` at mode 600.
3. Everything that needs an MCP token reads it there — `gitlab-api.sh` among them,
   which is why a new instance has working forge access without you doing anything.

**The copy is unconditional, and that is the point.** The two seeding steps above it
(`notify.json`, `environment.json`) gate on `[[ -f src && ! -e dst ]]` because their
destinations are files you edit and must never lose. This one is the reverse: the
staged copy is the source of truth, so rotating a token means replacing the staged
file and letting the next run propagate it. Gate this step on `! -e` and the
rotation silently stops working — the installer reports success, the old token stays
in place, and the first thing to notice is a forge call failing much later. `-m 600`
is deliberate too: it hardens a staged file that arrived at a looser mode.

The one residual trap, stated rather than guarded: on a machine that is *not* an
rdev box, anything that creates `~/.config/nvim/mcp.json` would have its contents
copied over a hand-written `~/.claude/.mcp.json`. Nothing writes that path today,
and adding a condition to a step whose whole job is to overwrite is how the
rotation path gets broken by a later reader. If an nvim MCP plugin ever does claim
that filename, move the staged slot rather than gating the copy.

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
writing — pass `--yes` to skip the question — strips only the owned keys, and re-parses each file afterwards to
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
**/.claude/worktrees/
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
is hidden.

`**/.claude/worktrees/` is the one **directory** here, and deliberately so: it is
`WT_ROOT`, where `wt` and `go` put their checkouts, so everything under it is a
working copy of the repo it sits in and none of it is ever committable. Without
it every repo you have ever made a worktree in shows a permanent `?? .claude/`,
which is noise in the one place you look for real unstaged changes — and it is
reachable by a `git add -A`, which would commit a second copy of the repo into
itself. It is scoped to that subdirectory rather than to `.claude/`, so a project
can still track its own `.claude/skills` or agent config.

Two limits are worth knowing:

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

`.claude/CLAUDE.md` is symlinked to `~/.claude/CLAUDE.md`, the user-level instruction file Claude Code loads in **every** repository. It carries three rules: do not add comments to code, spawn subagents freely, and write for a human who will not read a wall of text. Agent-written comments restate the line, go stale, and pad the diff for a human reviewer, so explanation belongs in the commit message and MR/PR description instead — with machine-read directives (linter suppressions, build pragmas, required doc-comments) exempt because they are program input rather than commentary. The code-modifying skills (`fix-linear`, `fix-freeform`, `autopilot`, `fix-feedback`, `review-code`, `review-kludge`, `security-audit`) each restate the rule locally, since a skill's subagents get the skill prompt rather than the user's `CLAUDE.md`.

Any directory under `.claude/skills/` is linked individually into `~/.claude/skills/`. Skills use `~/.claude/scripts/gitlab-api.sh` for GitLab API access (token read from `~/.claude/.mcp.json`, never exposed in conversation context; the GitHub profile uses `github-api.sh` and a `GITHUB_PERSONAL_ACCESS_TOKEN` instead). `fix-feedback` also writes through it: before fixing anything it posts each unique `review-code` finding to the MR as its own comment, anchored to the offending line, so the swarm's output survives the conversation — deduped against what the review bots already said, and gated on one batch approval. Swarm skills (`changes-description`, `docs-humanize`, `review-code`, `review-kludge`) run through the **Workflow** tool; `workflow-resume` rescues a run that died mid-swarm, reading the on-disk run manifests and agent caches through `~/.claude/scripts/workflow-runs.py`.

`docs-humanize` is the one swarm that writes outside the repo: it rebuilds an AI-written Notion page, markdown file or Linear ticket into something a person can read, and the rewrite is only pasted back after an explicit yes — a Notion page the user does not own gets a suggested edit rather than an overwrite, a Linear ticket keeps its title, and the original is saved to the session scratchpad first.

`aidr` is the counterpart to that third rule. The rule asks every response to be scannable; `/aidr` re-renders one that was not — "artificial intelligence; didn't read", after `tl;dr`. It sorts the source into what you have to do, what was already done, facts, and background; puts the exact command at the step that needs it; makes every path and URL clickable; applies the ASD-STE100 Simplified Technical English writing rules; and ends with a short list of things it could expand on so depth is offered rather than dumped. It is a **compression, not a rewrite** — it may drop anything and add nothing, and where the source is silent about who runs a step it says so rather than inventing a chore. Running it never starts the work it describes.

Some skills accumulate user data (weekly reports, Slack context, the `plan-initiative` team roster) that is gitignored and lives in the repo directory but is not tracked. The install script creates the necessary data directories automatically, and creates one only when the profile links the skill that reads it — the `reflect-*` skills are work-only, so a home machine gets no `reflect-*/context` directory.

### Per-machine skill environment

The work machines review merge requests on GitLab with one AI reviewer and publish diagrams to Claude Artifacts. The home machine reviews pull requests on GitHub with a different reviewer and publishes to a self-hosted store. Those differences used to be the kind of thing that gets written into a skill and then quietly breaks everywhere else — a skill looking for the wrong bot username finds no threads and cheerfully reports a clean review.

So they are configuration. `~/.claude/scripts/skill-env.sh` holds the per-profile defaults **in its own code** and merges `~/.claude/environment.json` over the top, which means a missing, empty or malformed config file degrades to working defaults rather than breaking a run:

```bash
~/.claude/scripts/skill-env.sh check        # everything a skill will see
~/.claude/scripts/skill-env.sh get forge    # one value
```

The installer seeds `environment.json` from the profile's committed `environment.json.example` and never overwrites it. The keys cover the forge and its API helper, what to call a change (`MR` vs `PR`), the AI reviewer usernames and the CI job that re-runs them, the operational bots whose comments are plumbing rather than review, the infrastructure bot and the markers of a finished apply, where diagrams get published, whether a human approval is required to merge, and the `fix_*` defaults below.

**An empty value means the machine does not have that thing, never "guess".** No `review_bots` means treat every non-operational bot thread as real feedback. No `iac_bot` disables the apply-before-merge gate outright. No `review_job` means a review cannot be re-triggered, and the skill says so instead of retrying something that is not there.

#### What an unflagged fix run does

`/fix-linear` and `/fix-freeform` take the **same flags with the same meanings** — they differ in where the work comes from, a ticket or a sentence, and in nothing else. Their defaults differ by machine rather than by skill, and they live in `skill-env.sh` for the same reason every other per-machine fact does: written into the skill text they would make the two profiles' copies stop being transforms of each other, and drift would go back to being invisible.

| Key | Flag | Work | Home |
|---|---|---|---|
| `fix_autopilot` | `--autopilot` | `true` | `true` |
| `fix_branch` | `--branch` | `new` | `new` |
| `fix_quick_description` | `--quick-description` | `false` — full panel | `true` — written inline |
| `fix_diagram` | `--diagram` | `true` | `false` |
| `fix_review` | `--review` | `true` | `false` |
| `fix_merge` | `--merge` | `false` — stop at ready | `true` — merge it |
| `fix_max_rounds` | `--max-rounds` | `3` | `3` |

The split is about who else is going to look at the change. At work, three people and two bots will: the full description panel, the diagram and the review swarm all exist to be read by somebody, and the run deliberately stops one step short of the merge so a human presses the button. At home nobody else is going to read any of it, so the ceremony comes off — the description is written on the spot instead of debated, no diagram, no swarm — and the run merges itself, because there is nobody to wait for.

Any flag in the invocation wins, a bare flag means `true`, and `~/.claude/scripts/skill-env.sh check` prints what an unflagged run will actually do on the machine you are sitting at.

**`--quick-description true` launches no swarm at all.** It is a flag about latency rather than about agent count: the point of reaching for it is the change request being *open*, and a workflow of any size prints a run ID and ends the turn, so the description — and the push, the change request, and every autopilot step after them — would all arrive one notification later. Quick has `changes-description` write the description in the same turn and the run carries straight on. It keeps the parts that are arithmetic rather than opinion, because a lone writer needs them more than a panel does: the same template, the same word budget counted by a command rather than eyeballed, and a fact-check against the diff claim by claim. The run says `self fact-checked` rather than `fact-checked`, so you can tell which of the two read the text.

### Change diagrams

`/changes-diagram` turns a branch's diff into a single interactive HTML page: every changed function is a box showing its added and removed lines, grouped into module boxes, with new and dropped calls drawn between them, callers from elsewhere in the repo, functions the change left unused, a separate tests chart, and a click-through review walk with per-function diffs.

The call graph is built from Python's `ast`, which is precise and understands only Python. Most repos here are not Python, and the version this was ported from simply produced **zero boxes** on a Go or Terraform branch — which reads as "this branch changed nothing", not "this language is unsupported". So there is a mechanical guarantee: **a non-empty diff always produces a non-empty chart.** When the AST pass finds nothing, it falls back to a file-level map with import edges resolved per language — Go through the `go.mod` prefix, TypeScript through relative-path probing, Terraform through `module`/`source` and cross-file resource references — and anything else gets grouped boxes with line counts. The page says which mode it is in, and its whole vocabulary follows: "Called by" becomes "Imported by", "new call" becomes "new import".

Where it publishes comes from `skill-env.sh`'s `artifact_store` — the Claude Artifact tool on the work profiles, a self-hosted store at home, falling back to a local file. A local file is a success, not a failure.

The published page embeds the diff of every changed function, so anyone it is shared with can read that code. Worth a thought before sharing one.

### Review swarms in the fix flow

`/review-code` runs an adversarial review swarm over a diff — a fleet of reviewers working from independent angles, then a panel of skeptics attacking every candidate finding, so only what survives refutation is reported. It catches things a single-shot reviewer misses, which is the reason it is wired into the fix flow rather than left to be remembered by hand.

`--review` comes from `fix_review` — on at work, off at home — and **where** the swarm runs depends on whether the run has a change request to post findings to:

| Run | Who fires the swarm | When |
|---|---|---|
| Autopilot on, `--branch new` | `autopilot`, Step 5b | In the turn that arms the pipeline watcher, after the push |
| `--autopilot false` | the fix skill itself | After the description and the commit message |
| `--branch default` | the fix skill itself | After the description — there is never a change request |

The reason the swarm moves rather than always running in the fix skill is `fix-feedback`: it posts every confirmed finding to the change request as an anchored comment, so a swarm that fires before the push has nowhere to put what it found. Where there is going to be a change request, the swarm waits for it. Where there is not, it runs where it is.

Within the fix skill the swarm runs **after** `changes-description` rather than beside it. Both read the same diff, but only one can invalidate the other — a confirmed finding means a code change, and a description written against a diff that is about to move is what goes stale. In `autopilot` the order inverts because the diff is already pushed and the forge's own reviewer is already running on it, so neither gates the other and serialising them would add a full swarm's latency to a run whose whole point is to need nothing from anybody.

Findings do not stop at the transcript. `/fix-feedback` reads the swarm's confirmed findings out of the conversation and posts each one the change request does not already carry as an anchored comment, before fixing any of them.

### Autonomous runs

`/autopilot` is a **mode, not a task**, and it is **on by default** — `fix_autopilot` is `true` on every profile. An ordinary `/fix-linear PLAT-123` ends at a change request, not at a commit message: the fix skill implements, writes the commit message and the description, then hands the run over, and autopilot pushes, opens the change request, works the review until it is clean, applies any infrastructure plan, and merges if `--merge` says so.

So you rarely type it. There are three ways in and they converge:

- **By hand-off** — the normal one. You typed a fix skill; autopilot takes the tail.
- **Directly** — `/autopilot PLAT-123` picks the fix skill for you (`fix-linear` for a ticket id, `fix-freeform` otherwise) and that skill's flow governs the run exactly as if you had typed it.
- **As an amendment** — `/autopilot <flags>` *while a run is in flight*, which changes that run's settings from there on. This is the one worth remembering.

**Automating the tail is not the same as going silent.** The fix skill's own gates stay open: a vague ticket still gets a question, an ambiguous requirement still gets `AskUserQuestion`, and the plan still gets shown. What you asked not to be interrupted for is the pipeline, the review and the merge — the hours of waiting, not the five minutes of deciding. `--autopilot false` turns the tail off entirely and gets you implementation, a commit message and a description with nothing leaving the machine; it is the flag for a spike.

#### Changing your mind mid-run

`/autopilot <flags>` during a run amends it. Only the flags you name change — everything else keeps its *current* value, not the machine default, so an amendment never quietly reverts an earlier one.

```
/autopilot --merge                  # got the go-ahead: merge it when it is green
/autopilot --diagram --merge false  # actually, draw me the diagram and hold the merge
/autopilot --review                 # run the swarm over what is pushed
/autopilot --autopilot false        # stop driving — leave the branch and MR as they are
```

Each flag has a defined catch-up when it arrives late: `--diagram true` publishes one now (even after a merge — it is still worth having), `--review true` runs the swarm against what is pushed and feeds the findings into a fresh review round, `--quick-description false` regenerates the description with the full panel and replaces it on the change request, and `--merge false` **disarms an auto-merge that is already armed**, since an armed auto-merge fires on green and would otherwise beat the instruction. `--autopilot false` means *stop driving*, never *undo*: nothing pushed gets deleted and no change request gets closed.

It composes the ordinary skills (`fix-linear` or `fix-freeform`, `commit-msg`, `changes-description`, `review-code`, `fix-feedback --autonomous`, `changes-diagram`, `ping`) rather than reimplementing them.

What makes it safe to walk away from:

- **It arms your phone as it takes over.** Notifications are opt-in per session and the opt-in is a sent ping, so an unarmed session stays silent when it *finishes* or *fails* — only a session blocked on you speaks up unasked. Autopilot sends one ping as it picks the work up — saying what it took over and where it will stop — which both tells you the hand-off happened and switches the automatic notifications on for everything that follows. Pinging only at the end would arm the session at the exact moment it stopped mattering. Every route in arms, including a mid-run `/autopilot --merge` on work that was never a fix-skill run, which is the route that needs it most.
- **It can ask you something, and you can answer from your phone.** Remote Control is armed when a session starts, so a question raised mid-run is a real option rather than a dead end — which is why the run asks instead of guessing for the calls that are expensive to get wrong: anything irreversible, anything that spends money, a product decision a review thread needs, a merge conflict whose intent is unclear. The last two used to end the run; now they pause it until you tap an answer. Most calls are still made alone and written down, because a question stalls the run until you answer it — asking does not replace the ledger, it just means fewer entries in it.
- **It waits with the `Monitor` tool, never a sleep loop.** A watcher wakes the session when something happens, so the prompt stays free and several runs can be in flight at once. A monitor that only reports success would stay silent through a crashloop, so every terminal state emits a line — a failed poll included, rather than being swallowed by the `|| true` that was meant for one dropped request. The watcher script is run once before it is armed, because the failure this actually prevents is a tool the machine does not have: that reads as a watch which never fires, and it once held a green, approved change request until somebody noticed by hand.
- **Review comments outrank CI, always.** Fixing comments means pushing, and a push restarts the pipeline — waiting on a red or running pipeline first throws away a whole CI run.
- **It overrides nothing you asked for.** Every flag but `--merge` and `--max-rounds` was decided by the fix skill, `--branch` included — so a run that stays on the default branch is pushed and ends there, with no change request to review or merge. That is safe to honour because the fix skill has already escalated to a feature branch if the change touched Terraform, if the default branch was protected, or if the tree was dirty. An amendment you type is the one thing that moves a flag mid-run, and that is an instruction rather than an override.
- **It gets two reviews, not one.** The forge's AI reviewer makes a single pass over the finished diff; the `review-code` swarm attacks it from independent angles and then has a panel of skeptics try to refute each finding, so only what survives refutation is reported. Interactively the swarm is a nice-to-have because a human reads the diff before it lands — on an unattended run there is no such human, and the review is the only thing between the run and the default branch. Both start in the turn that arms the watcher, since neither gates the other.
- **The human approval gate is never waived.** Where `require_human_approval` is set, a bot's approval does not merge the change. Everything else in the skill is a judgment call; this one is not.
- **Every decision made alone is written down, once, where it does not shout.** Calls nobody reviewed are captured to a local ledger at the moment they are made — recalling them at the end of a two-hour run means inventing some of them — and published in a single edit at the end of the run, appended to the change request description inside a collapsed `<details>` fold. Never as a comment: a comment is the first thing a reviewer sees and the worst place for a block they have to expand past. The filter is what keeps it short — an entry earns its place only if a reviewer could reasonably have decided differently, so following an existing pattern or doing what the ticket said never counts. At most eight entries, 25 words each, checked against `docs-humanize`'s mechanical slop list before it goes up, under a fixed `Relevant Decisions (N)` label — the fold carries the judgment calls behind the change, and labelling it with how the run was supervised puts a note about the automation on a surface that belongs to the change.

On infrastructure repositories the `apply` waits on the **review**, never on the plan: a green plan says the configuration is valid and shows what would change, which is no evidence that the change should happen, so the apply sits behind the AI reviewer's verdict and the swarm's findings — both, where both are relevant — and behind every open thread. Where a repository has neither review, the run reviews the diff against the plan itself and records that; what it will not do is apply with nothing but the planning bot behind it. `--merge false` does not switch that off, because landing an infrastructure change means apply *then* merge — the flag holds back the merge. It then merges directly rather than enabling auto-merge, because auto-merge fires the moment the pipeline is green and can beat the `apply`, merging a plan that was never applied. Where the work splits across several changes they share a branch prefix and lead with an ordinal (`dylan/PLAT-3535/01-…`), and each one's auto-merge is armed only once its predecessor has actually merged.

**It deletes the source branch when the merge lands.** Not housekeeping: `wtclean` decides a worktree is finished by its branch's upstream being gone, so a merged branch left on the remote means the worktree, the local branch and the checkout stay forever and `wtc -y` finds nothing to remove. The delete happens once the merged state is read back — which covers a direct merge, an auto-merge the forge performed later, and somebody merging it by hand mid-run — and a branch the forge already deleted counts as done. It never removes the worktree or the local branch: it is standing in that worktree, and reclaiming the disk stays `wtclean`'s job.

- **The merge is not the finish line.** Before the merge gate it works out how this repository actually ships — which jobs fire on a push to the default branch, what they change, and what observable thing would prove the new code is running — and after the merge it watches for exactly that. "Nothing deploys" is a valid answer it will tell you plainly, and so is "merged, could not verify".

It pings you when it finishes, and when it is genuinely stuck — a failed apply, a failed or unverifiable deploy, an unexplained test failure, or the same thread reopening three times. Where what it needs is one decision rather than a pair of eyes, it asks instead of stopping, and carries on the moment you answer.

#### Verifying the deploy

A run that stops at "merged" has reported on the easy half. The hard half is whether the change came up, and that is where an unattended run goes quietly wrong: the merge succeeds, the run says success, and the deploy went red twenty minutes later with nobody watching.

So the deploy path is worked out **contextually, from the repository, before the merge** — never from a baked-in list, because repositories differ, the same repository changes, and a stale expectation keeps passing after it stops being true. Three things get established: what fires on a push to the default branch (as opposed to on a tag or a manual dispatch — a tag-triggered deploy does not fire when you merge), what it actually changes, and what observable signal would prove the new code is running. Plus two facts about the run's own position: whether this session can see that signal at all, and how long the repo's own recent runs take, which becomes the watch budget.

Then after the merge, one rule carries the whole thing: **verify the new revision, not that something succeeded.** Every subtle post-merge failure has the same shape — something went green, about the wrong commit. A pipeline that passed for the commit before yours, a rollout that succeeded because the manifest never changed, a GitOps app Healthy on the revision it synced an hour ago, a mutable image tag that let pods restart onto the same old image. All four look like a good deploy from one step back, so every check is tied to the commit that landed.

It reports one of five outcomes, and the last three are the point: confirmed, failed, waiting on a human, **cannot observe**, or **timed out**. Cannot-observe and timed-out are never upgraded into success — being told a deploy worked when nobody established that is the one outcome worse than not checking, because you stop checking too.

**And it warns rather than fixes.** No rollback, no revert, no re-running a deploy job, no touching the runtime. It gathers the evidence — the failing job's log, the workload's events, the controller's sync status — and pings immediately. A deploy job is not a CI job and its idempotency is unknown, and an agent reverting production unattended is worse than a bad deploy somebody has been told about.

### Pausing and resuming a run

A long `autopilot` run can outlive a 5-hour quota window. Running out mid-flight is not a graceful stop — swarms, watchers and in-flight subagents are left wherever they were, and nothing records what the run was doing or what to do next.

`/pause` parks a run at a safe point and `/unpause` brings it back. Autopilot also pauses itself: it reads the quota at step boundaries and pauses at **85% of the session window**, pings you, arms a return, and resumes when the window resets.

**The name is `/unpause`, not `/resume`,** because `/resume` is already a built-in Claude Code command (the past-session picker) and a skill by that name would be unreachable.

**Quota comes from the `claude-usage` cache, never the API.** `/api/oauth/usage` is rate-limited per account and the CLI already polls it from every open session, so the skills read the shared cache the extension maintains — never taking `usage.lock` (which would make every editor window skip its own refresh) and never writing into that directory (a file-watch there fires in every window). `session` is the meter an autopilot pause reads, and the only one — `weekly`, `scoped:<Model>` and `spend` are read at an `/unpause` wake and are diagnostic in between, since a session at 40% with a model-scoped meter at 100% fails every agent you launch while the headline reads healthy. Worth knowing when something breaks; never a reason for a run to stop.

**The session window auto-resumes; the weekly window does not.** A refreshed 5-hour window is a reasonable thing to start back up on. A spent weekly quota is yours to decide about, so a `/pause` you reach for there pings and waits instead of arming a return. Autopilot never reaches for it on your behalf — `session` is the only meter it pauses on, so it will not park a run, and will not ask you about one, because a wider window is running low.

Three things make it actually work:

- **The state file has to stand alone.** By the time anything resumes, the context may be compacted and the session closed, so anything living only in the conversation is gone. The decision ledger is inlined as text rather than referenced by path, because it lives in the session scratchpad and the OS reaps that.
- **The run journals as it goes.** The moment you need to pause is the moment you have least budget to do it with, and a half-written state file reads as resumable while being useless. So the step, the next action and the ledger are appended at every step boundary, and the pause itself is one atomic write.
- **Resume re-verifies the world; it never replays intentions.** Hours passed. The change request may have merged, CI finished, the reviewer commented, someone pushed, the branch gone. Every recorded value is an input to a diff, never a substitute for looking. Recorded *authority* still stands — a `--merge true` from before the pause still merges — but recorded *evidence* does not, so approvals, pipelines and infrastructure apply markers are all re-read.

Some states are not safe to park in, and the skill either finishes them or unwinds first: a half-applied refactor, a conflicted rebase, an armed auto-merge (it fires on green while you are away), a dangling question whose answer a paused session would swallow, and a merge whose deploy is not yet verified — where a ping saying "paused" would read as "nothing is wrong" while production may be broken. A running infrastructure apply is the exception: it can outlast a window on its own, so pausing is allowed there but the hazard is recorded and leads the ping.

**Swarms come back from cache rather than being re-run.** `/workflow-resume` does that part, and it is cumulative: `workflow-runs.py merge` unions several partial runs' journals, so if a resumed swarm dies again the earlier generation's agents still count. One caveat that decides the cost — a swarm's cache is keyed on each agent's whole prompt and the diff is embedded in it, so if the branch moved while you were paused the cache is void and the swarm re-runs in full. That is deliberate: the cached findings describe code that no longer exists, and a partial review is not a review.

### Worktrees

`fix-linear` and `fix-freeform` both default to `--branch new`, which sets each fix up in its own **git worktree**, so you can work several non-blocking fixes in parallel (one terminal/session per worktree) without branch checkouts colliding. `--branch default` is the other value: no feature branch, no worktree, no change request — the commit lands on the branch every other checkout is cut from, and an autopilot run pushes it and ends. Three conditions force `new` whatever the flag said: the change touches Terraform, the default branch is protected, or the tree is dirty. `fix-feedback` makes a worktree for the branch under review, and `autopilot` creates none of its own and inherits whichever one the fix skill set up.

There is no third branch value and no in-place flag. A repo that cannot host worktrees falls back to a plain checkout automatically, which is a capability fallback rather than something you select. See **[WORKTREES.md](WORKTREES.md)** for the full guide — the mental model, switching between worktrees, dependency setup, and cleanup.

Each profile's shell config also defines `go` (worktree-aware `git checkout` — `cd`s into the worktree when one holds that branch, checks out normally when it doesn't, and passes anything else like `go -b new` or `go .` straight to git), `wt` (jump to the worktree for a branch, creating it if needed), `wtl` (list worktrees with age, upstream state, and dirty flag), and `wtclean` (remove worktrees whose branch is gone from the remote or untouched for 90+ days, then delete merged local branches no worktree holds — dry run unless `-y`).

### Hooks

`.claude/hooks/` is linked into `~/.claude/hooks/`, and each profile's `settings.json` registers the hooks that run from there. Two hooks live there today:

**`link-worktree-session.py`** (`PreToolUse` on `EnterWorktree`, `SessionStart`, `CwdChanged`, `Stop`) — makes every session in a repo visible from the main checkout's window, wherever it runs, so reloading the editor (which on a Remote-SSH box happens on every disconnect) never loses a worktree session.

Claude Code files a transcript under `~/.claude/projects/<slug of the session's directory>/`, and when a session enters a worktree it *moves* the transcript into the worktree's slug. The VS Code panel then rebuilds its list after a reload from the main checkout's slug only (`includeWorktrees: false`), and it opens each transcript with `O_NOFOLLOW`, so a per-file symlink back into that directory is silently dropped — that is what the hook used to do, and why worktree sessions vanished. Instead, the hook turns each worktree's project directory into a **symlink to the main checkout's project directory**. Claude Code checks whether the old and new directories resolve to the same place before moving a transcript, so the move becomes a no-op and every transcript stays a real file under the main checkout's slug.

`PreToolUse` creates that alias before `EnterWorktree` runs, so the common case never moves anything. The other events, and the backfill, migrate any worktree directory that is already real: they hard-link its contents into the main directory, swap the directory for the symlink atomically (`renameat2`/`renamex_np`), then drain what is left — a session writing during the migration loses nothing. A worktree whose transcripts collide with a different transcript of the same id in the main directory is left alone, and leftovers go to `~/.claude/backups/worktree-project-dirs/`. `install.sh` runs the backfill for you; run it by hand after importing transcripts from elsewhere:

```bash
~/.claude/hooks/link-worktree-session.py --backfill
```

Claude Code spawns hooks with a **bare `PATH`**, not the one your shell builds, so a `#!/usr/bin/env python3` hook that works perfectly when you run it yourself can still fail on every real session — and it fails invisibly, with no session ever appearing where you expect it. The installer therefore probes the hook under `env -i PATH=/usr/bin:/bin` and tells you when a system `python3` is missing, rather than assuming that linking the file was enough. A python3 that exists only under mise or a venv will not do.

### Notifications

**`notify.py`** (`Stop`, `StopFailure`, `Notification`, `PreToolUse` on `AskUserQuestion|ExitPlanMode`) — pushes a message to Slack or Telegram when a session finishes, gets stuck, or needs you. With a dozen sessions open across three machines, there is otherwise no way to know one is waiting without going and looking at it.

It is **off in every session until you ask for a ping** — see [Opting a session in](#opting-a-session-in) below. Once a session is opted in, it notifies on five things:

| | fires when |
|---|---|
| **finished** | a turn ends |
| **needs permission** | Claude is sitting on a permission prompt |
| **asking you a question** | `AskUserQuestion` or `ExitPlanMode` — the question text itself is in the message |
| **waiting on you** | 60s idle after a turn ended |
| **stopped** | the session died on a rate limit, an overload, or an auth failure |

Subagents never notify, only the session that spawned them.

#### Opting a session in

Automatic notifications are off in every session until you ask for one. The gesture that switches them on is asking for a ping:

```bash
/ping                 # or "ping me when you're done", "let me know if you get stuck"
```

That sends the message you asked for and, in the same move, **arms the session** — `armed_at` in `~/.claude/notify-state/sessions/<id>.json`. From then on that session notifies on everything its `events` config allows, with no turn-length floor, because you have already said you are not watching it.

The reason it works this way round rather than notifying by default: a hook that fires on every turn longer than a minute is indistinguishable from no notifications at all once a dozen sessions are live, because you stop reading them. Asking for a ping is the same gesture as walking away from that session, so it is the thing worth triggering on.

**One exception, and it is the difference between news and stuck.** A session that is *blocked on you* — a permission prompt, an `AskUserQuestion`, a plan waiting for approval — notifies whether or not it was armed. The latch is the right gate for "this session has something to tell you", because a finished turn keeps until you get back. It is the wrong gate for "this session will do nothing at all until you act": staying quiet there costs an unbounded wait, while speaking up when you are sitting right there costs one buzz you ignore. The log says which path it took, so a message from a session you never armed reads as `unarmed: blocking gate` rather than as a mystery.

It notifies but it does **not** arm. Only you clear or set the latch, so the session's eventual "finished" stays silent until you ask for it. `idle` is deliberately not in this set — it is a timer that fires on any session left at a prompt, not a gate the session ran into. `notify_when_blocked: false` switches the exception off; `events.question`/`events.permission` remain real off switches above it, and quiet hours still apply.

**It stays armed until you switch it off.** It is a latch, not a timer:

```bash
/ping off             # or quiet, disarm, mute — this session stops notifying
```

Nothing else clears it — not your next prompt, not `back`, not time passing, not the session going idle. Replying in chat and then walking away again is the normal way to use this, so a prompt arriving is not evidence you are back for the rest of the run. Anything that guessed otherwise would go quiet exactly when you were relying on it, and would not tell you it had.

It stops the notifications and nothing else. In particular it does not disconnect Remote Control, which is a separate channel armed when the session starts — see [Replies](#replies).

From the shell, `notify.py --disarm <session-id>` does the same thing, and `--disarm all` clears every session.

Sending is the same one owner: `notify.py --ping --level <level> --title <title> --body -` composes the envelope, resolves the repo and the session's title and thread, sends, and arms the session — which is what the `/ping` skill runs. The body comes in on stdin so prose with quotes and newlines survives, and a failed send exits non-zero with the sender's stderr and leaves the session unarmed.

Arming is per-session: three sessions running and a ping from one opts in only that one. `away` is the global override.

Setting `only_when_armed` to `false` restores the old always-on behaviour, where any turn longer than `min_turn_seconds` notifies whether or not you asked for it.

#### Away mode

```bash
away          # notify me about everything, I'm not at my desk
away 90m      # ... until it expires on its own
away status
back
```

Away mode is the global override: it notifies for **every** session, opted in or not, and drops the turn-length floor. That is the difference between the two gestures — a ping opts in the one session you asked, `away` opts in all of them at once. The per-session rate limit and the `events` switches apply either way. `away status` also reports how many sessions are currently opted in.

The switch is a file (`~/.claude/notify-state/away.json`), not an environment variable, because hooks do not inherit your shell's environment. `away` and `back` are defined in `shell/terminal.zsh` and only appear once the hook is installed.

#### What the message says

Every session's notifications form **one thread**, and the shape differs between the message that starts it and the ones that answer it:

```
Demeter · Demeter ping skill setup and testing
Notifications now opt-in via /ping. 11 files ready to commit.
  └─ ✅ Branch pushed, pr-checks green, ai-review running.
  └─ 🔥 Apply failed on the staging workspace; needs a look.
```

The **first message** carries the repo and this session's chat title, then its body — and no glyph. The **replies** carry a glyph and the body, and nothing else. Every reply quotes the first message, so the repo and the title are already on screen; repeating them in each one spent roughly a third of a 140-character lock screen saying what was directly above it.

The glyph carries the class: ✅ finished, ❓ a question, 🔐 needs permission, 🔄 in progress, 💤 waiting, 🔥 failed. It used to spell that out in words on a line of its own, above a second line that repeated the repo name — so a 140-character lock screen spent a third of its budget restating what the emoji already said.

What follows the glyph is the repo and then **this session's chat title** — the name on the editor tab, either the one Claude Code generated or one you typed over it. That is the field that tells you *which* of a dozen live sessions is talking. It is read straight out of the transcript, where Claude Code writes `ai-title` and `custom-title` records, so it needs no editor API and nothing installed; a title you set yourself wins over the generated one. The read widens the same way `handoff_at` does, because the record is written early and scrolls out of a fixed tail — only 38 of 139 local sessions had one in their last 256KB.

The branch is now only a **fallback** for a session too new to have earned a title. Most work here happens in worktrees, where the branch is the least surprising thing about a session and says nothing about what it is doing. The session id used to be there too and is gone: it looked like a commit hash, identified nothing a human recognises, and cost characters the body needed.

A turn's closing chat message is written for someone sitting in front of a terminal with the diff open — headings, tables, file links, backticks, and routinely several hundred words. None of that survives a push notification, and a phone shows you roughly the first 140 characters. Sending it raw produces a wall of markdown whose first line is often a sentence ending in a colon, pointing at a table you cannot see.

So the body goes through a model on the way out. `notify.py` shells out to the `claude` CLI — your Claude Code subscription, not API credit — and asks for one lock-screen line of at most 45 words: outcome first in concrete nouns, then what you have to do or an explicit "nothing needed". A 497-word message with tables and file links comes out as:

```
Built & tested: Notifications now opt-in via /ping — arms session, auto-disarms
next prompt. 11 files ready to commit.
```

Four things about it are deliberate:

- **It degrades, never fails.** If the CLI is missing, not logged in, slow, or errors, the body falls back to a mechanical condense — markdown stripped, first sentence or two, 240 characters. A notification always goes out. The log says which path ran, so a silently-degraded setup is visible rather than guessed at.
- **The budgets are generous on purpose.** The summarizer gets 180 seconds and the hook 240. The alternative to waiting is a truncated markdown dump, and if you are away from the keyboard — which is the only state in which any of this fires — waiting costs you nothing while degrading costs you the whole feature. Tight timeouts optimise the wrong thing here.
- **It runs with a neutral working directory and no MCP, hooks or plugins.** Otherwise the summarizer loads this repo's `CLAUDE.md` and every skill before answering, and a hook that spawns a session that fires hooks recurses. `NOTIFY_SUMMARIZING=1` in the child's environment is the backstop that breaks any recursion in one step.
- **Long messages are windowed head-and-tail**, not truncated. The outcome is at the top of a message and the ask is usually at the bottom, so cutting the end would reliably discard the one thing you need to see.

Check it on any machine with `notify.py --test`, which prints the CLI it resolved, the model, the budget, and a live sample run with its timing.

#### Setup

The installer creates `~/.claude/notify.json` from your profile's `notify.json.example` at mode 600 and tells you which fields still need filling. Until they are filled the hook is **dormant** — it runs, logs why it did nothing, and sends nothing. Nothing in the repo ever holds a token.

**Work and home_darwin profiles (Slack).** Two routes, and which you want depends on where the messages should land.

*An incoming webhook* is the quickest: create one at <https://api.slack.com/messaging/webhooks>, paste the URL into `slack.webhook_url`, done — no scopes to request. The channel picker does let you choose your own DM, so this can be private. The catch is that a webhook is permanently bound to the conversation you picked and ignores `thread_ts`, so every session's messages land flat in one stream.

*A bot token* is the better end state with many sessions open, because each session gets its own **thread**. Set `slack.bot_token` and `slack.channel`, leave `webhook_url` empty, and give the app `chat:write` plus `im:write`.

That threading has one consequence worth knowing before it bites you: **only the first message of a session is a top-level DM; everything after is a threaded reply.** Slack treats thread replies as second-class — they do not surface as a new message and are easy to miss on a phone unless you are following the thread, and Slack only auto-follows threads *you* started or replied in, never a bot's. So the session that notified you it had a question at 08:31 can quietly tell you it finished at 09:20 and you will never see it.

The fix is `slack.mention`: put your member ID there and the sender prefixes `<@U…>` to the message, which notifies regardless of thread subscription. It defaults to `slack.channel` when that is already a `U…` id, so the common setup needs no extra configuration.

**The mention has to go in the `blocks`, not in `text`.** When `chat.postMessage` is given both, Slack renders the blocks and keeps `text` only as the notification fallback — so a mention that lives solely in `text` is never displayed, never registers as a mention, and never notifies. It fails exactly like no mention at all, with the API still answering `ok: true`. The sender therefore puts `<@U…>` at the head of the rendered section block *and* in `text` (where it drives the lock-screen preview). This was gotten wrong once here, and the symptom was a message that arrived in the thread looking completely normal. `slack.mention_levels` controls which levels get it — `stop`, `question`, `permission` and `failure` by default, deliberately **not** `progress` or `idle`, so a mention keeps meaning "this wants you". The alternative, `reply_broadcast`, also works but copies the reply to the top level and undoes the grouping the thread was for.

To have it DM **only you**, put your own member ID (`U…`, from your Slack profile's ⋮ menu → *Copy member ID*) in `slack.channel`. The sender resolves it to a DM conversation with `conversations.open` and caches the result in `~/.claude/notify-state/slack-dm.json`, so there is one extra API call the first time and none after.

Do not skip that resolution by hand: passing a `U…` id straight to `chat.postMessage` is accepted but posts to that user's DM with **Slackbot**, not with your app — the message arrives somewhere you are not looking, and nothing errors. The `D…` conversation id is what `chat.postMessage` needs, and `conversations.open` is what turns one into the other. Putting a `D…` or `C…` id in `slack.channel` skips the lookup entirely.

**Pi profile (Telegram).** Message [@BotFather](https://t.me/BotFather), `/newbot`, and put the token in `telegram.bot_token`. Send your new bot a message, then read your chat id out of `https://api.telegram.org/bot<token>/getUpdates` and put it in `telegram.chat_id`.

The Pi is the only Telegram profile left, and it is the reason the home sender speaks both transports rather than only Slack. Its `scripts/` is a symlink into `home_darwin`, so a Slack-only sender there would read a `slack` section its config does not have and mute the box on every send — a box whose sessions run unattended, which is the one place a silent transport costs most. `notify-send.sh` therefore dispatches on `transport`, and the Slack half of it is byte-for-byte the work profiles' behaviour.

On a machine that already holds that bot's credential for its own alerting, use `telegram.bot_token_file` and `telegram.chat_id_file` instead and point them at the existing files. The `_file` form is read only when the direct key is empty, so there is one owner per credential and no second copy to rotate. The Pi profile ships configured this way, which is why notifications there are live on the first install rather than dormant.

Then check it:

```bash
~/.claude/hooks/notify.py --test
```

#### Tuning

| key | default | |
|---|---|---|
| `host_label` | `""` | what to call a session that is not inside a checkout, in place of the directory name. Set it on a box whose sessions all start in one fixed directory, or every ping from it carries the same uninformative word |
| `only_when_armed` | `true` | notify only in sessions a ping has opted in; `false` restores always-on |
| `notify_when_blocked` | `true` | a session blocked on you (`question`, `permission`) notifies even unarmed; `false` makes the latch absolute |
| `min_turn_seconds` | 60 | shortest turn that earns a "finished" ping, and only when `only_when_armed` is `false` |
| `min_interval_seconds` | 30 | floor between two messages from the same session |
| `quiet_hours` | `null` | `[22, 7]` to stay silent overnight |
| `events` | all `true` | switch off any of `stop`, `permission`, `question`, `idle`, `failure` |
| `summarize.command` | probe | path to the `claude` CLI; empty searches the usual install locations |
| `summarize.model` | `claude-haiku-4-5-20251001` | model that writes the notification line |
| `summarize.max_words` | 45 | hard word budget, enforced after the model answers |
| `summarize.timeout` | 180 | seconds the summarizer may take before falling back to a condense |
| `summarize.enabled` | `true` | `false` skips the model and always condenses mechanically |
| `slack.mention` | `slack.channel` when it is a `U…` id | member ID to `<@…>` so a threaded reply still notifies |
| `slack.mention_levels` | `stop`, `question`, `permission`, `failure` | which levels earn the mention |
| `telegram.bot_token_file` | — | path to read the token from, when the box already has one |
| `telegram.chat_id_file` | — | path to read the chat id from, likewise |

Telegram needs none of this. Its `reply_to_message_id` renders inline in the chat rather than collapsing into a thread, so every message stays top-level and notifies on its own.

#### When it is not working

A hook that fails is invisible from inside Claude Code, so this one writes a line for every invocation — including the ones where it deliberately stayed quiet:

```bash
tail ~/.claude/notify-state/notify.log
```

```
2026-11-12T11:29:42 Stop sent stop for Demeter
2026-11-12T11:29:42 Stop skip: rate limited (0s ago)
2026-11-12T11:29:27 Stop skip: turn 11s < 60s
2026-11-12T11:29:27 Stop skip: slack section still has REPLACE_ME
```

The hook never fails a session: every error path logs and exits 0, and a dead Slack costs a turn about five seconds, never the full hook timeout.

#### Replies

The notification itself is one-way. You cannot answer from Slack or Telegram — a permission prompt and an `AskUserQuestion` are blocking UI that only the session can clear.

Answering from a phone is Claude Code's [Remote Control](https://code.claude.com/docs/en/remote-control.md), which forwards the live session to claude.ai and the Claude app and *can* clear both. Every profile that ships a `settings.json` sets `remoteControlAtStartup` to `true`, so a session is reachable from the moment it starts. The Pi profile ships none, and needs none — its sessions are spawned by a `claude remote-control` server and are reachable by construction.

It is armed at startup rather than when a ping goes out because there is no other way: Remote Control is established by the `/remote-control` slash command, a slash command is typed by you, and the agent sending the ping has no way to run one in its own session. Writing the setting reaches only sessions started afterwards. The alternative — a line in the ping telling you to run `/remote-control` — fails in exactly the case the feature exists for, because the ping that matters most arrives hours after you left the terminal, where nothing printed in it will be read.

So the two halves stay separate. The notification tells you to come and look; Remote Control is how you act on it without walking back to the desk. Neither depends on the other, and `/ping off` does not disconnect anything — toggle that with `/remote-control`.


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
