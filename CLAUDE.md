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
  tools/                  # First-party projects shared by every profile
    worktree-sync/        # VS Code extension, linked into ~/.claude/tools/
  vscode/                 # Editor settings shared by every profile
    settings.json         # symlinked over VS Code's user settings.json
    extensions.txt        # extension ids the installer keeps present
    sync-extensions.sh    # rewrites extensions.txt from the current machine
  profiles/               # One directory per machine profile
    <profile>/            # e.g. larrabeedylan_work_linux
      .zshrc
      .bash_profile
      .claude/
        CLAUDE.md         # global agent instructions, synced to ~/.claude/CLAUDE.md
        settings.json     # permissions + hook registrations
        skills/           # Claude Code skills, synced to ~/.claude/skills/
          <skill-name>/
            SKILL.md
        hooks/            # Hook scripts, synced to ~/.claude/hooks/
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
5. Symlinks `.claude/` contents individually (skills linked per-directory into `~/.claude/skills/`)
6. Symlinks vendor skills from `_vendor/*/` into `~/.claude/skills/`
7. Symlinks shared tools from `tools/*` into `~/.claude/tools/`
8. Prompts to build and install shared tools exposing an `install` target in their Makefile. Runs through `mise exec` when the tool has a `.mise.toml`, so a pinned toolchain resolves in a non-interactive shell. Skipped without prompting when no `code`/`codium` CLI is present. Honours `SKIP_LIST` by tool directory name.
9. Symlinks `vscode/settings.json` over VS Code's user settings, on every editor user directory that already exists
10. Prompts to install any extension in `vscode/extensions.txt` missing from the editor
11. Cleans stale skill symlinks (removes symlinks pointing to deleted repo paths)
12. Creates data directories for skills that accumulate context

Key behaviors:
- Never copies `~/.claude` aside; it only replaces symlinks, leaving your session data in place
- Backs up existing real files before replacing
- Skips already-correct symlinks
- Removes stale skill symlinks that point into the repo but whose target no longer exists
- Respects `SKIP_LIST` for machine-specific files (format: `"filename:machine"`)
- `.claude/CLAUDE.md` is symlinked to `~/.claude/CLAUDE.md` — the user-level instruction file loaded in every repository (no installer change was needed; the top-level `.claude/` file loop already handles it)
- `settings.json` is copied (not symlinked) with `__DEMETER_REPO__` path templating
- `settings.local.json` lives at `.claude/.claude/` and is symlinked normally
- `.mcp.json` is NOT managed by the repo (contains tokens) — configure manually
- `.claude/hooks/` is linked per-file into `~/.claude/hooks/` by the same `.claude/` directory loop; the hooks that run from there are registered in each profile's `settings.json`
- `tools/` is profile-independent and linked per-directory into `~/.claude/tools/`. Linking only makes the source available, so a tool exposing a Makefile `install` target is then offered a build (step 8) — the symlink alone gives no signal that an installed artefact is older than the source
- `vscode/extensions.txt` is the companion to `settings.json`: a theme named in settings does nothing until its extension exists, and VS Code falls back silently. The installer only ever **adds** — a locally-installed extension missing from the list is left alone. `vscode/sync-extensions.sh` writes the list back from a machine; it excludes extension ids published from `tools/*/package.json`, which are not on the Marketplace and are installed by their own make target. `editor_cli()` resolves the CLI (PATH, then the macOS app bundle) and `read_extension_list()` parses the file (`#` comments and blanks ignored)
- `vscode/settings.json` is profile-independent and symlinked **wholesale** over the editor's user settings (`~/Library/Application Support/Code/User/` on mac, `~/.config/Code/User/` on linux, plus Insiders and VSCodium when present). Because it is a symlink, VS Code writes UI changes back into the repo — machine-specific keys (`window.zoomLevel`, `claudemeter.debugLogFile`) are kept last in the file so they stand out in a diff. `vscode_user_dirs()` resolves the paths; `should_skip "vscode" "$machine"` opts a platform out
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
- **Shared tools**: First-party projects that are not tied to one machine go in `tools/<name>/` at the repo root rather than being duplicated per profile. Build output (`node_modules/`, `dist/`, `*.vsix`) is ignored by the tool's own nested `.gitignore`
- **Theme ids**: `workbench.colorTheme`, the `workbench.preferred*ColorTheme` keys, and the `[Theme Name]` scopes in `workbench.colorCustomizations` all take a theme's **settingsId** — `contributes.themes[].id` falling back to `label`, which is often not the display name (`Dark Modern`, not `Default Dark Modern`; only the High Contrast themes carry the `Default` prefix). A wrong id fails silently: the scope matches nothing, and the light/dark toggle no-ops. Scopes match by exact id or a `*` glob at either or both ends, on the name only — there is no scope for "every dark theme"
- **Editor settings**: `vscode/` holds one shared `settings.json`, not a per-profile copy — the point is an identical editor everywhere. Color fixes belong in its `workbench.colorCustomizations` (theme-scoped, so light and dark each get correct values), never in a per-repo `.vscode/settings.json`. Anything Peacock also writes must be listed in `peacock.excludedSettings`, or Peacock's workspace-level write will outrank the user-level pin. See the Editor Settings section of `README.md` for why the High Contrast themes broke the Claude Code webview
- **Hooks**: One script per hook under `.claude/hooks/`, duplicated across profiles like `scripts/`. Register it in every profile's `settings.json` using `$HOME/.claude/hooks/<name>` so the path resolves on any machine
