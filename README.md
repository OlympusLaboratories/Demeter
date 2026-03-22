# Demeter

A shared dotfile repo. Each contributor keeps their config in a directory named after their username. An interactive install script symlinks everything to the right places on any machine.

## Structure

```
Demeter/
├── install.sh          # interactive symlink installer
├── _starter/           # copy this to get started
│   └── .bash_profile
├── _vendor/            # vendor skill sets (git submodules)
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
- Symlink `.claude/` contents (including skills) to `~/.claude/`
- Symlink vendor skills from `_vendor/` into `~/.claude/skills/`
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

Any directory under `.claude/skills/` is linked individually into `~/.claude/skills/`. This means your remote dev machine and MacBook both get the same skills after running `./install.sh` on each, and neither machine's existing skills are clobbered.
