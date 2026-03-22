# skills/ — Agent Instructions

## Structure

Each skill is a subdirectory containing a `SKILL.md` file that defines the skill's behavior. Skills are symlinked into `~/.claude/skills/` by `install.sh` and become available as slash commands in Claude Code.

## Current Skills

| Skill | Purpose |
|---|---|
| `address-comments` | Handle PR review feedback |
| `branch-context` | Load branch context |
| `commit-message` | Generate commit messages |
| `explain` | PR change breakdown |
| `fix` | Linear ticket implementation |
| `pr-description` | Generate PR descriptions |

## Helper Scripts

`../scripts/github_api.py` — GitHub API helper used by PR-related skills (e.g., `explain`, `pr-description`, `address-comments`).

## Adding a New Skill

1. Create a new directory: `<skill-name>/`
2. Add a `SKILL.md` file defining the skill's prompt and behavior
3. If the skill needs helper scripts, add them to `../scripts/`
4. Run `./install.sh` from the repo root to symlink it
5. Update this file with the new skill entry
