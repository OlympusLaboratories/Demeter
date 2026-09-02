# Worktree Sync

Keeps the active **Claude Code tab** and the active **terminal** on the same git worktree,
in both directions, so you can't type a prompt into one worktree's session while running
commands in another.

## How it decides what pairs with what

Both sides resolve to the same key — an **absolute worktree path**. Nothing is matched by
name similarity.

**Terminal → worktree.** Reads `terminal.shellIntegration.cwd`, then picks the *longest*
known worktree path that contains it. Longest-match matters: worktrees live under the repo
root, so a shorter match would collapse every worktree onto `~/gridmatic-dev`.

**Claude tab → worktree.** A session's transcript at
`~/.claude/projects/<dir>/<sessionId>.jsonl` records both the titles it can display and the
worktree it runs in, so the tab label is an exact key into an index built from those files —
tail-read (256KB per file, with a 4MB retry), cached for 5s, rebuilt on a lookup miss.

A tab label can come from more than one place, so each session is indexed under **every
alias it might present**, in this precedence:

1. `custom-title` — set when you rename a tab by hand
2. `ai-title` — the generated title
3. `worktreeName` from `worktree-state`
4. the worktree directory's basename

When two sessions claim the same alias, the more **specific worktree** wins: if one
candidate's path contains the other's, the deeper one is taken. A repo-root session titled
`PLAT-2472` therefore loses to the actual `PLAT-2472` worktree — which matters because the
repo root is a key shared by dozens of sessions, and resolving there is almost never what
you meant. Only when the paths are unrelated does title outrank name, then newest mtime.

Renaming a tab writes a ~100-byte stub transcript containing just the `custom-title` and no
location, so those are skipped; the rename is still matched through the real session's own
aliases. Indexing only
`ai-title` is not enough in practice: a renamed tab has *no* `ai-title` record at all, and a
generated title often drifts from the worktree name (`"PLAT-2406 fix"` for the `PLAT-2406`
worktree). Both cases now match on another alias.

Worktree path is taken from the newest of:

1. `worktree-state` → `worktreeSession.worktreePath` (a `null` session means the run left
   its worktree, and older `worktree-state` records are then ignored)
2. `relocated` → `relocatedCwd`
3. the newest message record's `cwd` — last resort only

A session that *entered* a worktree mid-run still carries the original repo root in its
message `cwd` fields, which is why the first two win.

## What it deliberately does not do

- **Never guesses.** A tab or terminal that doesn't resolve is skipped, not fuzzy-matched.
- **Never creates a terminal.** A Claude tab whose worktree has no open terminal is a no-op.
- **Skips ambiguity.** If several open Claude tabs resolve to one worktree — common for the
  repo root — terminal → tab does nothing rather than jumping you somewhere arbitrary.
  Unless one of them is already active, in which case it's already correct.

## Focus behaviour

- **Claude tab → terminal** uses `terminal.show(preserveFocus: true)`. Focus stays in the
  Claude prompt.
- **Terminal → Claude tab** has to focus the editor group before
  `workbench.action.openEditorAtIndex` will act on it (that command operates on the *active*
  group), so it focuses the group, switches the tab, then calls
  `workbench.action.terminal.focus` to hand focus back. If the bounce is visually
  distracting, set `worktreeSync.direction` to `tabToTerminal`.

## Commands

| Command | Purpose |
|---|---|
| `Worktree Sync: Toggle` | Enable/disable without touching settings by hand |
| `Worktree Sync: Show Diagnostics` | Every tab and terminal, what it resolved to, and why not |
| `Worktree Sync: Rebuild Session Index` | Force a rescan of the transcript corpus |

Run diagnostics first whenever sync goes quiet — it names the reason.

## Settings

| Setting | Default | |
|---|---|---|
| `worktreeSync.enabled` | `true` | |
| `worktreeSync.direction` | `both` | `both`, `tabToTerminal`, `terminalToTab` |
| `worktreeSync.projectsDir` | `~/.claude/projects` | |
| `worktreeSync.debounceMs` | `50` | |

## Development

```bash
make setup        # npm install
make check        # typecheck + tests + build
make install      # package a .vsix and install it into VS Code
make link         # symlink into ~/.vscode/extensions instead (faster iteration)
make unlink       # remove the symlink
```

Either way, run **Developer: Reload Window** afterwards. Or press F5 for an Extension
Development Host without installing anything.

## Coupling to Claude Code

Two things here are Claude Code internals and could change on an extension update: the
`claudeVSCodePanel` webview viewType, and the transcript record shapes (`ai-title`,
`custom-title`, `worktree-state`, `relocated`). Both fail soft — you get no sync rather than
a wrong one — and `Show Diagnostics` says which one broke, including which alias each tab
matched on. Verified against `anthropic.claude-code` 2.1.247 and VS Code 1.134.
