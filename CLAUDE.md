# Demeter — Shared Dotfiles

## Project Overview

Demeter is a shared dotfile repo. Each machine setup lives in its own profile directory under `profiles/`. An interactive install script symlinks everything to the right places on any machine (macOS or Linux).

## Repo Structure

```
Demeter/
  install.sh              # Interactive symlink installer (idempotent)
  _starter/               # Template for new contributors — copy to get started
    .bash_profile
  _vendor/                # Vendor packages (skills + tools) — linked/installed by installer
  profiles/               # One directory per machine profile
    <profile>/            # e.g. larrabeedylan_work_linux
      .zshrc
      .bash_profile
      .claude/
        CLAUDE.md         # global agent instructions, synced to ~/.claude/CLAUDE.md
        skills/           # Claude Code skills, synced to ~/.claude/skills/
          <skill-name>/
            SKILL.md
        scripts/          # Helper scripts used by skills
```

## Context Discovery

Before planning or making changes in a directory, **read the `README.md` and `AGENTS.md`** at the root of that directory (and any parent directories up to the repo root) if they exist. These files contain important context about the directory's purpose, conventions, constraints, and how components interact. This applies to research, planning, and implementation — not just code changes.

## Install Script (`install.sh`)

The installer does the following in order:

1. Selects the profile to install — from the first CLI argument (a `profiles/` subdirectory name or a path), else auto if only one profile exists, else prompts. `install.sh --help` lists available profiles.
2. Detects machine type (macOS = `mac`, Linux = `linux`)
3. Initializes git submodules if `.gitmodules` exists
4. Symlinks dotfiles from `profiles/<profile>/` to `~/` (skipping `.claude/`)
5. Backs up existing `~/.claude` directory (timestamped copy)
6. Symlinks `.claude/` contents individually (skills linked per-directory into `~/.claude/skills/`)
7. Symlinks vendor skills from `_vendor/*/` into `~/.claude/skills/`
8. Cleans stale skill symlinks (removes symlinks pointing to deleted repo paths)
9. Creates data directories for skills that accumulate context

Key behaviors:
- Creates a full backup of `~/.claude` before modifying it
- Backs up existing real files before replacing
- Skips already-correct symlinks
- Removes stale skill symlinks that point into the repo but whose target no longer exists
- Respects `SKIP_LIST` for machine-specific files (format: `"filename:machine"`)
- `.claude/CLAUDE.md` is symlinked to `~/.claude/CLAUDE.md` — the user-level instruction file loaded in every repository (no installer change was needed; the top-level `.claude/` file loop already handles it)
- `settings.json` is copied (not symlinked) with `__DEMETER_REPO__` path templating
- `settings.local.json` lives at `.claude/.claude/` and is symlinked normally
- `.mcp.json` is NOT managed by the repo (contains tokens) — configure manually
- Idempotent — safe to re-run after pulling changes

## When Making Changes

- **Shell scripts**: Use `shellcheck` on any changed `.sh` files if available
- **README**: Keep `README.md` up to date when adding features or changing the installer workflow
- **AGENTS.md**: Keep `AGENTS.md` files up to date when directory structure, patterns, or conventions change
- **CLAUDE.md**: Keep this file up to date when repo structure, installer behavior, or conventions change
- **Test the installer**: After modifying `install.sh`, verify it still works on a clean run — the script must remain idempotent

## Conventions

- **One profile directory per machine setup**, under `profiles/` (e.g. `larrabeedylan_work_linux`)
- **Dotfiles only**: Files in profile directories should be dotfiles (prefixed with `.`) or inside `.claude/`
- **No secrets in repo**: Sensitive values (API keys, tokens) belong in `~/.secrets` or similar, sourced from shell config — never committed
- **Machine-specific skipping**: Use the `SKIP_LIST` array in `install.sh` to control per-platform linking
- **Skills**: Each skill gets its own directory under `.claude/skills/` with a `SKILL.md` file
- **No comments in code**: `.claude/CLAUDE.md` forbids agent-written code comments globally. Any skill that writes or edits code must restate the rule in its own prompt — subagents spawned by a skill receive the skill's text, not the user's `CLAUDE.md`. The only sanctioned exception is `security-audit`'s PoC and verification tests, where the write-up is the deliverable
- **Vendor packages**: Third-party skill sets go in `_vendor/<name>/` as git submodules
