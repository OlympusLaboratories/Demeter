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
├── vscode/             # editor settings, shared by every profile
│   ├── settings.json   # symlinked over VS Code's user settings.json
│   ├── extensions.txt  # extensions the installer keeps present
│   └── sync-extensions.sh  # refresh that list from this machine
└── profiles/           # one directory per machine profile
    └── <profile>/      # e.g. larrabeedylan_work_linux
        ├── .bash_profile
        ├── .zshrc
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
- Symlink `.claude/` contents (including skills) to `~/.claude/`
- Symlink vendor skills from `_vendor/` into `~/.claude/skills/`
- Symlink shared tools from `tools/` into `~/.claude/tools/`
- Offer to build and install any shared tool that has an `install` target (prompted, skippable)
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

Peacock colors the title bar per repo, but it only ever writes
`commandCenter.foreground` and `commandCenter.border` — never
`commandCenter.background` — and it picks its foreground from two hardcoded
values by a luminance threshold. On mid-tone colors the repo name in the title
bar ends up unreadable.

The fix is `peacock.excludedSettings`, which Peacock documents as keys it must
never modify or delete. Every `commandCenter.*` key is listed there, and they're
pinned instead in `workbench.colorCustomizations` to white text on a 65% black
scrim — readable over any hue Peacock picks, in either theme.

Peacock writes into a repo's **workspace** `.vscode/settings.json`, which
outranks user settings. A repo colored before this change still carries stale
`commandCenter.*` keys; run `Peacock: Remove All Colors` and re-apply the color
to clear them.

## Claude Skills

`.claude/CLAUDE.md` is symlinked to `~/.claude/CLAUDE.md`, the user-level instruction file Claude Code loads in **every** repository. It currently carries one rule: do not add comments to code. Agent-written comments restate the line, go stale, and pad the diff for a human reviewer, so explanation belongs in the commit message and MR/PR description instead — with machine-read directives (linter suppressions, build pragmas, required doc-comments) exempt because they are program input rather than commentary. The code-modifying skills (`fix-linear`, `fix-feedback`, `review-code`, `review-kludge`, `security-audit`) each restate the rule locally, since a skill's subagents get the skill prompt rather than the user's `CLAUDE.md`.

Any directory under `.claude/skills/` is linked individually into `~/.claude/skills/`. Skills use `~/.claude/scripts/gitlab-api.sh` for GitLab API access (token read from `~/.claude/.mcp.json`, never exposed in conversation context). Swarm skills (`changes-description`, `review-code`, `review-kludge`) run through the **Workflow** tool; `workflow-resume` rescues a run that died mid-swarm, reading the on-disk run manifests and agent caches through `~/.claude/scripts/workflow-runs.py`.

Some skills accumulate user data (weekly reports, Slack context, the `plan-initiative` team roster) that is gitignored and lives in the repo directory but is not tracked. The install script creates necessary data directories automatically.

### Worktrees

The `fix-linear` and `fix-feedback` skills set up each fix in its own **git worktree** by default, so you can work several non-blocking fixes in parallel (one terminal/session per worktree) without branch checkouts colliding. See **[WORKTREES.md](WORKTREES.md)** for the full guide — the mental model, switching between worktrees, dependency setup, and cleanup. Pass `in place` to a skill (e.g. `/fix-linear ENG-123 in place`) to fall back to a plain in-place checkout.

Each profile's shell config also defines `go` (worktree-aware `git checkout` — `cd`s into the worktree when one holds that branch, checks out normally when it doesn't, and passes anything else like `go -b new` or `go .` straight to git), `wt` (jump to the worktree for a branch, creating it if needed), `wtl` (list worktrees with age, upstream state, and dirty flag), and `wtclean` (remove worktrees whose branch is gone from the remote or untouched for 90+ days — dry run unless `-y`).

### Session Hook

`.claude/hooks/` is linked into `~/.claude/hooks/`, and each profile's `settings.json` registers the hooks that run from there. One hook lives there today:

**`link-worktree-session.py`** (`SessionStart`, `CwdChanged`, `Stop`) — a session started inside a worktree writes its transcript to that worktree's own `~/.claude/projects/<slug>/` directory, so `claude --resume` run from the main checkout cannot see it. The hook symlinks each worktree session's transcript back into the main checkout's project directory, which makes every worktree's history resumable and searchable from one place. Run it with `--backfill` to link transcripts recorded before the hook was installed:

```bash
~/.claude/hooks/link-worktree-session.py --backfill
```

### Claude Usage Extension

`tools/claude-usage/` is a VS Code extension that shows your Claude session and weekly quota in the status bar, so you don't have to run the usage skill to find out how close you are to a limit:

```
Session ●●○○○○ 33% 1h20m   Weekly ●●●○○○ 53% 5d20h   ⟳ now
```

Each meter is a label, a bar, the percent used, and the time until that window resets. Bar glyphs are configurable — run **Claude Usage: Choose Bar Style** to preview them live, since the status bar is drawn in the UI font and which glyphs look right depends on it. The chip on the end is the age of the reading; it turns yellow with a retry countdown when a fetch is failing or rate limited, so a percentage that has quietly stopped moving is obvious rather than silently wrong. It reads `https://api.anthropic.com/api/oauth/usage` — the endpoint behind Claude Code's `/usage` — once a minute while the window is focused, and not at all while it isn't.

That is once a minute *in total*, not per window. Every window runs its own copy of the extension, so they coordinate through a cache in `~/Library/Caches/claude-usage/` (`$XDG_CACHE_HOME/claude-usage/` on Linux): whichever window is due first takes a lock file and fetches, the rest read what it wrote and update together through a directory watch. Six open windows still make one request a minute.

By default it borrows the login Claude Code already has: the `Claude Code-credentials` keychain item on macOS, `~/.claude/.credentials.json` elsewhere. That read is one-way — it never writes to or refreshes Claude Code's token, so it can't disturb your CLI session. Claude Code's access token only lasts a day, though, and only Claude Code renews it. If you'd rather the meters not depend on that, run **Claude Usage: Sign In With Browser** once: the extension does its own PKCE login in your real default browser (never a webview, so Okta SSO works), keeps the tokens in VS Code's `SecretStorage`, and refreshes them itself.

Installed the same way as any tool here, and configurable down to the bar glyphs. See [tools/claude-usage/README.md](tools/claude-usage/README.md) for the full settings table and the copy-paste sign-in fallback.

### Worktree Sync Extension

`tools/worktree-sync/` is a VS Code extension that keeps the active **Claude Code tab** and the active **terminal** on the same worktree in both directions, so you can't type a prompt into one worktree's session while running commands in another. It is shared by every profile.

`install.sh` links every tool's source into `~/.claude/tools/` and then offers to build and install the ones exposing a Makefile `install` target. Answer yes and there is nothing else to do; the prompt exists because the build takes a couple of minutes. To do one by hand, or after editing the source:

```bash
make -C ~/.claude/tools/worktree-sync install
```

The build runs through `mise exec` when the tool has a `.mise.toml`, so it works from a shell where the pinned toolchain isn't activated.

A VS Code extension installs into `~/.vscode/extensions`, which every **profile** on the machine shares — but each profile chooses whether to enable it, so enable it once per profile. On Linux the installer skips the build when no `code` CLI is on PATH: over Remote-SSH the extension belongs on the client machine.

`make link` is the development alternative: it symlinks the source into `~/.vscode/extensions/` so a rebuild picks up on a window reload. `make check` runs typecheck, tests, and build. See [tools/worktree-sync/README.md](tools/worktree-sync/README.md) for how tabs and terminals are matched and which settings it exposes.
