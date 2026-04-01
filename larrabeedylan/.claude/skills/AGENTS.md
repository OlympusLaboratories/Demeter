# skills/ — Agent Instructions

## Structure

Each skill is a subdirectory containing a `SKILL.md` file that defines the skill's behavior. Skills are symlinked into `~/.claude/skills/` by `install.sh` and become available as slash commands in Claude Code.

## Current Skills

| Skill | Purpose |
|---|---|
| `address-comments` | Handle MR review feedback |
| `branch-context` | Load branch context |
| `commit-message` | Generate commit messages |
| `document` | Audit and update README.md and AGENTS.md to reflect current repo state |
| `eng-snippet` | Generate weekly engineering snippets |
| `explain` | MR change breakdown |
| `fix` | Linear ticket implementation |
| `mr-description` | Generate MR descriptions |
| `performance-review-self` | Self-assessment generator (stub) |
| `performance-review-peer` | Peer assessment generator (stub) |

## GitLab Data

MR-related skills (`explain`, `mr-description`, `address-comments`, `eng-snippet`) use `~/.claude/scripts/gitlab-api.sh` for all GitLab API access. The script reads the GitLab token from `~/.claude/.mcp.json` so tokens never enter conversation context.

## User Data

Some skills accumulate context data that is NOT tracked in git:
- `eng-snippet/slack-context.md` — ephemeral Slack threads pasted before each run
- `performance-review-self/context/` — weekly self-reports
- `performance-review-peer/context/` — per-peer collaboration profiles
- `performance-review-*/prompts.md` — review questions pasted per cycle

These files are gitignored. The install script creates necessary directories.

## Adding a New Skill

1. Create a new directory: `<skill-name>/`
2. Add a `SKILL.md` file defining the skill's prompt and behavior
3. If the skill needs helper scripts, add them to `../scripts/`
4. Run `./install.sh` from the repo root to symlink it
5. Update this file with the new skill entry
