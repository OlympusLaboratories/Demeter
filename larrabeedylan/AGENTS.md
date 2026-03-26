# larrabeedylan/ — Agent Instructions

## Contents

This is Dylan's dotfile directory. Files here get symlinked to `~/` by `install.sh`. Targets a Linux dev environment with GitLab-based workflows.

| File | Purpose | Symlink target |
|---|---|---|
| `.bashrc` | Bash config — aliases, prompt, completions, env setup | `~/.bashrc` |
| `.claude/skills/` | Claude Code skills (each skill is a subdirectory with `SKILL.md`) | `~/.claude/skills/<name>/` |
| `.claude/scripts/` | Helper scripts — `gitlab-api.sh` for GitLab API access | `~/.claude/scripts/` |
| `.claude/settings.json` | Claude Code permissions and hooks (copied with path templating) | `~/.claude/settings.json` |
| `.claude/.claude/settings.local.json` | Local permission overrides | `~/.claude/.claude/settings.local.json` |

## Shell Config Conventions

- Secrets are sourced from `~/.secrets` (not committed) — includes DB credentials, API keys, tokens
- `direnv` is used for per-project environment setup
- `a-cli` (Apollo) tab completion is loaded via `eval "$(_A_COMPLETE=bash_source a)"`
- Git aliases are short mnemonics (`gs`, `ga`, `gc`, `gpsh`, etc.)
- `go` is aliased to `git checkout`; use `gol` for the Go language binary
- `update` and `freshen` aliases handle branch sync workflows (auto-detects default branch)
- Kubectl aliases (`k`, `kwest`, `kcent`, etc.) switch GKE cluster contexts
- NVM, Go, tfenv, and GCP SDK are loaded from standard paths
- Platform-aware ls coloring (dircolors on Linux, CLICOLOR on macOS)

## Adding a New Dotfile

1. Add the file to this directory (must be a dotfile, prefixed with `.`)
2. Run `./install.sh` to symlink it
3. If the file is machine-specific, add it to `SKIP_LIST` in `install.sh`

## Adding a New Skill

1. Create `<skill-name>/SKILL.md` under `.claude/skills/`
2. If the skill needs helper scripts, add them to `.claude/scripts/`
3. Run `./install.sh` to symlink the new skill into `~/.claude/skills/`
