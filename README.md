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
            ├── CLAUDE.md   # global instructions, synced to ~/.claude/CLAUDE.md
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

`.claude/CLAUDE.md` is symlinked to `~/.claude/CLAUDE.md`, the user-level instruction file Claude Code loads in **every** repository. It currently carries one rule: do not add comments to code. Agent-written comments restate the line, go stale, and pad the diff for a human reviewer, so explanation belongs in the commit message and MR/PR description instead — with machine-read directives (linter suppressions, build pragmas, required doc-comments) exempt because they are program input rather than commentary. The code-modifying skills (`fix-linear`, `fix-feedback`, `review-code`, `review-kludge`, `security-audit`) each restate the rule locally, since a skill's subagents get the skill prompt rather than the user's `CLAUDE.md`.

Any directory under `.claude/skills/` is linked individually into `~/.claude/skills/`. Skills use `~/.claude/scripts/gitlab-api.sh` for GitLab API access (token read from `~/.claude/.mcp.json`, never exposed in conversation context). Swarm skills (`changes-description`, `review-code`, `review-kludge`) run through the **Workflow** tool; `workflow-resume` rescues a run that died mid-swarm, reading the on-disk run manifests and agent caches through `~/.claude/scripts/workflow-runs.py`.

Some skills accumulate user data (weekly reports, Slack context, the `plan-initiative` team roster) that is gitignored and lives in the repo directory but is not tracked. The install script creates necessary data directories automatically.

### Worktrees

The `fix-linear` and `fix-feedback` skills set up each fix in its own **git worktree** by default, so you can work several non-blocking fixes in parallel (one terminal/session per worktree) without branch checkouts colliding. See **[WORKTREES.md](WORKTREES.md)** for the full guide — the mental model, switching between worktrees, dependency setup, and cleanup. Pass `in place` to a skill (e.g. `/fix-linear ENG-123 in place`) to fall back to a plain in-place checkout.

Each profile's shell config also defines `go` (worktree-aware `git checkout` — `cd`s into the worktree when one holds that branch, checks out normally when it doesn't, and passes anything else like `go -b new` or `go .` straight to git), `wt` (jump to the worktree for a branch, creating it if needed), `wtl` (list worktrees with age, upstream state, and dirty flag), and `wtclean` (remove worktrees whose branch is gone from the remote or untouched for 90+ days — dry run unless `-y`).
