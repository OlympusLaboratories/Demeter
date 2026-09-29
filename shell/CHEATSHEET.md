# Terminal Cheat Sheet

Everything `shell/terminal.zsh` sets up. Same on every machine — Mac or rdev box.

## The prompt

```
Demeter  main !? ❯
└─ dir   └─ branch
                └─ repo state
                    └─ green if the last command succeeded, red if it failed
```

Directory shows at most 3 segments and truncates to the repo root. Python, Go and Node
versions appear when the directory uses them (`py 3.12`, `go 1.27`, `node 22`).

### Repo state symbols

Concatenated with no separator — `!?` means modified **and** untracked.

| | Meaning |
|---|---|
| `?` | untracked files |
| `!` | tracked files modified, not staged |
| `+` | staged changes |
| `✘` | deleted files |
| `$` | a stash exists |
| `=` | merge conflicts |
| `⇡` | ahead of the remote |
| `⇣` | behind the remote |
| `⇕` | diverged — commits on both sides |
| *(blank)* | clean and in sync |

## Autosuggestions

The rest of the line appears in grey as you type, from your history first and the completion
system second — so it suggests commands you have never run, not only ones you have.

| Key | Action |
|---|---|
| `→` / `End` | Accept the whole suggestion |
| `Ctrl-→` | Accept one word of it |
| Keep typing | Re-matches as you go |

Nothing is ever submitted unless you accept it and press Enter.

## Completion

| Key | Action |
|---|---|
| `Tab` | Open a menu — walk it with arrow keys, Enter to pick |
| `Tab` (case-insensitive) | `cd dem⇥` finds `Demeter` |
| `Tab` (partial words) | `f/b/ba⇥` → `foo/bar/baz` |
| `**` then `Tab` | Fuzzy-find the candidates (`vim src/**⇥`) |

## History

50 000 lines, shared live between open terminals, duplicates and leading whitespace stripped.

| Key | Action |
|---|---|
| `↑` / `↓` | **Prefix search** — type `git co` first, then `↑`, to walk only matching entries |
| `Ctrl-P` / `Ctrl-N` | Same as `↑` / `↓` |
| `Ctrl-R` | Fuzzy-search all history (fzf) |
| `!!`, `!$` | Expand onto the line for you to confirm — press Enter twice |

## fzf

| Key | Action |
|---|---|
| `Ctrl-R` | Fuzzy history |
| `Ctrl-T` | Fuzzy-pick file paths, insert onto the line |
| `Alt-C` | Fuzzy-pick a directory and `cd` into it |

Backed by `fd`, so `.gitignore` is respected and `.git` is skipped.

> **macOS:** `Alt-C` needs Option-as-Meta — Terminal.app: Settings → Profiles → Keyboard →
> "Use Option as Meta key"; iTerm2: Profiles → Keys → Left Option = `Esc+`. Otherwise press
> `Esc` then `c`.

## Line editing

| Key | Action |
|---|---|
| `Ctrl-←` / `Ctrl-→` | Move by word |
| `Ctrl-W` | Delete previous word — stops at `/` `.` `-` `_`, so one path segment at a time |
| `Home` / `End` | Start / end of line |
| `Ctrl-U` / `Ctrl-K` | Delete to start / end of line |

## Syntax highlighting

Commands color as you type: **green** when the command exists, **red** when it does not — a
typo is visible before you press Enter. Quotes, paths and options get their own colors.

## Other

- `cat` is `bat --paging=never` — highlighted with line numbers, but still plain text when
  piped or redirected. `command cat` forces the real one.
- **tmux**: mouse on, 100 000 lines of scrollback, windows numbered from 1 and renumbered on
  close, truecolor. Plus `allow-passthrough` so Claude Code's notifications and progress bar
  survive tmux, and `extended-keys` so `Shift+Enter` inserts a newline instead of submitting.

## Customizing

| Want to change | Edit |
|---|---|
| Shell aliases, functions, exports | Your profile's `.zshrc`, **above** the last line that sources `terminal.zsh` |
| tmux settings | `~/.tmux.conf.user` (sourced at the end) |
| The prompt | `shell/starship.toml` — but it is a byte-for-byte copy of rdev's so both machines match; editing it makes them diverge |

## If something is missing

```bash
./shell/install-tools.sh --check   # list what is absent
./shell/install-tools.sh           # install it
```

`terminal.zsh` degrades quietly: no starship means a plain git-aware prompt, no fzf means the
builtin `Ctrl-R`. A missing tool therefore looks like nothing happened — check first.
