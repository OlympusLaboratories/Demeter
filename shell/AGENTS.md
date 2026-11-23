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

## VS Code shell integration

`vscode/settings.json` turns automatic injection off and `terminal.zsh` sources
`shellIntegration-rc.zsh` itself, guarded on `TERM_PROGRAM == vscode` and on
`$VSCODE_SHELL_INTEGRATION` being unset (a terminal still running on an old injected
environment already has it). Injection rewrites `ZDOTDIR` into the environment VS Code saves
for terminal revival, and a revive re-injects on that environment with
`USER_ZDOTDIR=$ZDOTDIR` — VS Code's own temp directory — so the user rc never runs. Read the
README's Terminal section before turning injection back on.

Two rules for the block:

- **Source at top level, never inside a function.** The script relies on global assignments; a
  function body would scope some of them away. Only the path lookup is a function.
- **Unset `VSCODE_INJECTION` and `USER_ZDOTDIR` first.** They are meaningless in manual mode
  but can be inherited from a saved environment, and with `VSCODE_INJECTION=1` the script
  points `HISTFILE` at the temp directory and sources `~/.zshrc` a second time.

## When rdev changes

`starship.toml` is a copy, so the prompts match. If rdev's changes, re-copy it rather than
editing ours — a divergence here is the one thing that makes the two machines feel different,
and on the rdev box our copy is not even installed (rdev's file wins; the installer skips the
path when `~/.rdev-managed.json` claims it).

Worth re-checking after an rdev image bump: the plugin list and paths in
`FirstBootSteps()` (`internal/homedir/init.go`), and the zshrc's own ordering around
`compinit` and syntax highlighting.

---

## The reasoning behind the fragment and the shell rcs

The root `CLAUDE.md` states the invariants — fill gaps only, per-feature guards, the
`source` line last. The full reasoning for each is below: the guard names that were gotten
wrong, what rdev owns and how a profile customizes around it, and why `wtclean` sweeps
branches rather than worktrees. The last of those lives in the rcs rather than in
`terminal.zsh`, and the sections here repeat some of what is above in longer form, because
this is the account the root file used to carry.

### Shared terminal

`shell/` holds one terminal experience for every machine — starship, zsh-autosuggestions/completions/syntax-highlighting, fzf, prefix history search — sourced as the **last** line of each profile's shell rc (`.zshrc` on Darwin, `.zshrc.local` on rdev). It **fills gaps only**: every block is guarded on whether the feature is already active (`$+functions[prompt_starship_precmd]` — that exact name; starship defines no `starship_precmd`, and the wrong guard loads starship then clobbers its prompt with the fallback, which reads as the config doing nothing — `$+functions[_zsh_autosuggest_start]`, `$+functions[compdef]`), verified against each tool's real init output rather than assumed, because rdev already builds this on its own boxes and owns the files it does it in. Per-feature guards, never one `is_rdev` switch — the half-configured machine is the common case. Three ordering rules are load-bearing and explained in `shell/AGENTS.md`: `fpath` before `compinit`, syntax highlighting from a one-shot `precmd` hook (after every widget, and after rdev's own load, so it can never double-load), and the `source` line staying last. Plugins live at `~/.local/share/zsh/<name>`, the same paths rdev clones to, which is what lets one code path serve both

### rdev boxes

rdev regenerates `~/.zshrc` and `~/.tmux.conf` from its image and lists them in `~/.rdev-managed.json`; `is_rdev_managed` keeps the installer from linking over them. The login shell there is zsh, so `.bashrc` is never read — a profile customizes rdev through `~/.zshrc.local` (sourced near the end of rdev's `.zshrc`, in login and non-login shells alike, unlike `~/.zlogin`), `~/.zshrc.pre` (before `compinit`), and `~/.tmux.conf.local`. `larrabeedylan_work_linux/.zshrc.local` is the zsh port of its `.bashrc`; it leaves history, completion, direnv, mise and the starship prompt to rdev

### VS Code shell integration is manual

`terminal.integrated.shellIntegration.enabled` is `false` (in both `vscode/settings.json` and `vscode/machine-settings.json`, since over Remote-SSH the user settings come from the client) and `shell/terminal.zsh` sources `shellIntegration-rc.zsh` itself (path derived from `$VSCODE_GIT_ASKPASS_MAIN`, `code --locate-shell-integration-path zsh` as fallback). Automatic injection breaks revived terminals: VS Code saves the injected `ZDOTDIR` into the terminal's launch environment and re-injects on revive with `USER_ZDOTDIR=$ZDOTDIR`, so its `.zshrc` sources itself and the user rc never runs — a revived terminal shows zsh's bare `host%` prompt. Source the script at top level, and unset `VSCODE_INJECTION`/`USER_ZDOTDIR` before it, or a stale saved environment re-sources `~/.zshrc` and moves `HISTFILE`

### A cleanup command is only as complete as the thing it iterates

`wtclean` walked `git worktree list`, so it could only ever see a branch some worktree had checked out — and a branch whose worktree was removed earlier, or that never had one, was invisible to it and survived every run. `dylan/pi-profile` sat merged and unreferenced that way. The sweep that fixes it must not use the two obvious tests, and the second one shipped broken for a day. `git branch -d` is wrong because it compares against **HEAD**, so it refuses a branch that is merged upstream whenever the local default is behind — the normal state after somebody else merges. And **ancestry** (`merge-base --is-ancestor`) is wrong because a **squash merge rewrites the commit**, so the branch tip is never an ancestor of the default branch: on a squash-only repo, which is every repo here, an ancestry test calls *every* merged branch unmerged and the sweep cleans nothing it was built for. The test that works is `git merge-tree --write-tree origin/<default> <branch>` compared against the default branch's own tree — merging in memory and asking whether the result differs, which sees a squash, a rebase and a plain merge alike. It needs git 2.38, so ancestry stays as the fallback and that machine degrades to the old behaviour rather than to a wrong answer. Only one shape is refused outright: a branch with **no upstream** that the default branch does not contain is work in progress, so it is left alone and unmentioned. A branch gone from the remote that is genuinely absent from the default branch *is* deleted, because that is the signal the whole feature is built on, but its line says so and names `git reflog` — verified that the commit and its file contents survive the `-D` and come back with `git branch <name> <sha>`. The block lives byte-identical in four shell rcs across three profiles, so an edit that patches three of them is a silent divergence; `md5` over the `_wt_in_repo`-to-`alias wtc=` span is the check, and one of the four is `.bashrc`, which is why nothing in it may be zsh-only
