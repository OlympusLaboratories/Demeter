# Demeter

A shared dotfile repo. Each contributor keeps their config in a directory named after their username. An interactive install script symlinks everything to the right places on any machine.

## Structure

```
Demeter/
├── install.sh          # interactive symlink installer
├── _starter/           # copy this to get started
│   └── .bash_profile
├── _vendor/            # vendor packages — skills + tools (git submodules)
└── <username>/         # your directory — named after your system username
    ├── .bash_profile
    ├── .zshrc
    └── .claude/
        ├── skills/     # Claude Code skills, synced to ~/.claude/skills/
        └── scripts/    # helper scripts used by skills
```

## Setup

1. Clone the repo somewhere permanent (e.g. `~/Demeter`)
2. Add your dotfiles in a directory named after your username
3. Run the installer:

```bash
./install.sh
```

The script will:
- Detect your username directory automatically
- Detect whether you're on macOS or Linux
- Symlink each dotfile to `~/`
- Back up `~/.claude` before modifying (timestamped copy)
- Symlink `.claude/` contents (including skills) to `~/.claude/`
- Symlink vendor skills from `_vendor/` into `~/.claude/skills/`
- Clean stale skill symlinks (e.g. after a skill is renamed or removed from the repo)
- Create data directories for skills that accumulate context
- Install vendor tools (e.g. [Dippy](https://github.com/OlympusLabs-Forks/Dippy) — a PreToolUse hook that auto-approves safe bash commands)
- Configure Claude Code hooks in `~/.claude/settings.json`
- Back up any existing real files before replacing them
- Skip already-correct symlinks

Re-run it anytime after pulling changes — it's idempotent.

## Adding Your Dotfiles

```bash
cp -r _starter <your-username>
cd <your-username>
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
