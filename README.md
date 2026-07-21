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
└── profiles/           # one directory per machine profile
    └── <profile>/      # e.g. larrabeedylan_work_linux
        ├── .bash_profile
        ├── .zshrc
        └── .claude/
            ├── skills/     # Claude Code skills, synced to ~/.claude/skills/
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
- Back up `~/.claude` before modifying (timestamped copy)
- Symlink `.claude/` contents (including skills) to `~/.claude/`
- Symlink vendor skills from `_vendor/` into `~/.claude/skills/`
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
- Clean up now-empty skill directories left behind
- Optionally restore the most recent `~/.claude.bak.*` backup that `install.sh` created

Your repo files are never touched, and existing backups and skill data directories are left in place.

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

## Claude Skills

Any directory under `.claude/skills/` is linked individually into `~/.claude/skills/`. Skills use `~/.claude/scripts/gitlab-api.sh` for GitLab API access (token read from `~/.claude/.mcp.json`, never exposed in conversation context).

Some skills accumulate user data (weekly reports, Slack context) that is gitignored and lives in the repo directory but is not tracked. The install script creates necessary data directories automatically.
