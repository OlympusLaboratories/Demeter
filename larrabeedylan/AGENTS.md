# larrabeedylan/ — Agent Instructions

## Contents

This is Dylan's dotfile directory. Files here get symlinked to `~/` by `install.sh`.

| File | Purpose | Symlink target |
|---|---|---|
| `.zshrc` | Zsh config — aliases, prompt, completions | `~/.zshrc` |
| `.claude/skills/` | Claude Code skills (each skill is a subdirectory with `SKILL.md`) | `~/.claude/skills/<name>/` |
| `.claude/scripts/` | Helper scripts used by skills | `~/.claude/scripts/` |

## Shell Config Conventions

- Secrets are sourced from `~/.secrets` (not committed) — never add secrets here
- `direnv` is used for per-project environment setup
- `a-cli` (Apollo) tab completion is loaded via `eval "$(_A_COMPLETE=zsh_source a)"`
- Git aliases are short mnemonics (`gs`, `ga`, `gc`, `gpsh`, etc.)
- `update` and `freshen` aliases handle branch sync workflows

## Adding a New Dotfile

1. Add the file to this directory (must be a dotfile, prefixed with `.`)
2. Run `./install.sh` to symlink it
3. If the file is machine-specific, add it to `SKIP_LIST` in `install.sh`

## Adding a New Skill

1. Create `<skill-name>/SKILL.md` under `.claude/skills/`
2. If the skill needs helper scripts, add them to `.claude/scripts/`
3. Run `./install.sh` to symlink the new skill into `~/.claude/skills/`
