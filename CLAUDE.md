# Demeter — Shared Dotfiles

## Project Overview

Demeter is a shared dotfile repo. Each contributor keeps their config in a directory named after their system username. An interactive install script symlinks everything to the right places on any machine (macOS or Linux).

## Repo Structure

```
Demeter/
  install.sh              # Interactive symlink installer (idempotent)
  _starter/               # Template for new contributors — copy to get started
    .bash_profile
  _vendor/                # Vendor packages (skills + tools) — linked/installed by installer
  <username>/             # Per-user dotfile directory
    .zshrc
    .bash_profile
    .claude/
      skills/             # Claude Code skills, synced to ~/.claude/skills/
        <skill-name>/
          SKILL.md
      scripts/            # Helper scripts used by skills
```

## Context Discovery

Before planning or making changes in a directory, **read the `README.md` and `AGENTS.md`** at the root of that directory (and any parent directories up to the repo root) if they exist. These files contain important context about the directory's purpose, conventions, constraints, and how components interact. This applies to research, planning, and implementation — not just code changes.

## Install Script (`install.sh`)

The installer does the following in order:

1. Detects user directory (auto if only one, prompts if multiple)
2. Detects machine type (macOS = `mac`, Linux = `linux`)
3. Initializes git submodules if `.gitmodules` exists
4. Symlinks dotfiles from `<username>/` to `~/` (skipping `.claude/`)
5. Symlinks `.claude/` contents individually (skills linked per-directory into `~/.claude/skills/`)
6. Symlinks vendor skills from `_vendor/*/` into `~/.claude/skills/`
7. Configures Claude Code hooks in `~/.claude/settings.json` for vendor tools (e.g. Dippy)

Key behaviors:
- Backs up existing real files before replacing
- Skips already-correct symlinks
- Respects `SKIP_LIST` for machine-specific files (format: `"filename:machine"`)
- Idempotent — safe to re-run after pulling changes

## When Making Changes

- **Shell scripts**: Use `shellcheck` on any changed `.sh` files if available
- **README**: Keep `README.md` up to date when adding features or changing the installer workflow
- **AGENTS.md**: Keep `AGENTS.md` files up to date when directory structure, patterns, or conventions change
- **CLAUDE.md**: Keep this file up to date when repo structure, installer behavior, or conventions change
- **Test the installer**: After modifying `install.sh`, verify it still works on a clean run — the script must remain idempotent

## Conventions

- **One directory per contributor**, named after their system username
- **Dotfiles only**: Files in user directories should be dotfiles (prefixed with `.`) or inside `.claude/`
- **No secrets in repo**: Sensitive values (API keys, tokens) belong in `~/.secrets` or similar, sourced from shell config — never committed
- **Machine-specific skipping**: Use the `SKIP_LIST` array in `install.sh` to control per-platform linking
- **Skills**: Each skill gets its own directory under `.claude/skills/` with a `SKILL.md` file
- **Vendor packages**: Third-party skill sets and tools go in `_vendor/<name>/` as git submodules
- **Vendor tools**: Packages in `_vendor/` that need CLI installation (e.g. Dippy) are handled by `install_vendor_tools()` in `install.sh`
