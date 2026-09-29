# shell/ — the shared terminal experience

Profile-independent shell configuration, linked by `install.sh` the same way `vscode/` and
`tools/` are. One terminal on every machine: same prompt, same history, same completion and
line-editing behaviour, whether the box is a Mac or an rdev instance.

| File | Linked to | Notes |
|---|---|---|
| `terminal.zsh` | `~/.config/zsh/terminal.zsh` | Sourced **last** from each profile's shell rc |
| `starship.toml` | `~/.config/starship.toml` | Byte-for-byte rdev's own prompt config |
| `tmux.conf` | `~/.tmux.conf`, or `~/.tmux.conf.local` on rdev | rdev owns `~/.tmux.conf` and sources `.local` |
| `install-tools.sh` | — | Installs what `terminal.zsh` needs; `--check` lists what is missing |

## The design rule: fill gaps, never redo

This config was reverse-engineered from rdev's, which lives at
`apps/rdev/internal/homedir/dotfiles/` in the gridmatic-dev repo. On an rdev box, rdev already
loads the plugins, starts starship, wires fzf and sets the history options — and it owns
`~/.zshrc`, refreshing it on every image update. Demeter must not fight that, and must not
double-load anything.

So **every block in `terminal.zsh` is guarded on whether the feature is already active**, and
the guard is per-feature, not per-machine:

- `(( ! $+functions[_zsh_autosuggest_start] ))` — autosuggestions
- `(( ! $+functions[prompt_starship_precmd] ))` — prompt. Note the name: `starship init zsh` defines `prompt_starship_precmd`/`prompt_starship_preexec`, and nothing called `starship_precmd`. Guarding on the wrong name silently loads starship and then overwrites its `PROMPT` with the fallback, which looks exactly like the config never took effect. A function, not `$STARSHIP_SHELL` — that env var is inherited by nested interactive shells, which do need their own init
- `(( ! $+functions[fzf-history-widget] ))` — fzf keybindings
- `(( ! $+functions[compdef] ))` — whether `compinit` has run
- `: "${VAR:=default}"` for every exported setting, so an rdev or user value wins

The upshot: on rdev the file is very nearly a no-op, on a fresh Mac it does everything, and on
a half-configured machine it does exactly the missing part. Never replace these with a single
`is_rdev` switch — that breaks the half-configured case, which is the common one.

## Load order — the three constraints that bite

1. **`fpath` must be extended before `compinit` runs.** `compinit` scans `fpath` once; a
   directory added afterwards contributes nothing. The profile rc files run their own
   `compinit` early (nvm and gcloud completion scripts call `compdef` and need it), so
   `terminal.zsh` re-runs `compinit -C` when — and only when — it actually added
   `zsh-completions` to `fpath`.
2. **`zsh-syntax-highlighting` must be sourced after every widget is defined**, or later
   widgets go unhighlighted. It is therefore loaded from a **one-shot `precmd` hook** rather
   than inline, which puts it after *all* rc files including rdev's. That also makes the
   double-load guard work on rdev, where rdev sources the plugin at `.zshrc:191` — after it
   sources `~/.zshrc.local`, and so after `terminal.zsh` was read but before the first prompt.
   An inline load would fire first and rdev would then load it a second time.
3. **The `source` line must stay last in each profile rc.** Everything above depends on
   widgets and keybindings already existing. If you add a section to a profile `.zshrc`, add
   it above that line.

## Entry points per profile

- `profiles/*_darwin/.zshrc` — Demeter owns the whole file; the source line is the last line.
- `profiles/larrabeedylan_work_linux/.zshrc.local` — rdev owns `~/.zshrc` and sources
  `~/.zshrc.local` near its end, in login and non-login shells alike. The source line is the
  last line there too. Never add this to that profile's `.zshrc`; there isn't one, by design.

## Tools

`terminal.zsh` degrades quietly when a binary is absent — no starship means the fallback
prompt, no fzf means the builtin `^R`. That is deliberate but it also means a missing tool
looks like nothing happened, so `install.sh` runs `install-tools.sh --check` and offers to
install what is missing. The script is idempotent, skips anything already present, and exits
immediately on an rdev box because the image ships all of it.

Plugins are cloned to `~/.local/share/zsh/<name>` — **the same paths rdev uses**, which is
what lets one code path serve both kinds of machine. Override with `$DEMETER_ZSH_PLUGINS`.
Homebrew's own plugin locations (`/opt/homebrew/share/...`) are searched as a fallback, so a
`brew install zsh-autosuggestions` is picked up too.

## When rdev changes

`starship.toml` is a copy, so the prompts match. If rdev's changes, re-copy it rather than
editing ours — a divergence here is the one thing that makes the two machines feel different,
and on the rdev box our copy is not even installed (rdev's file wins; the installer skips the
path when `~/.rdev-managed.json` claims it).

Worth re-checking after an rdev image bump: the plugin list and paths in
`FirstBootSteps()` (`internal/homedir/init.go`), and the zshrc's own ordering around
`compinit` and syntax highlighting.
