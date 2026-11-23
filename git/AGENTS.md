# `git/` — the machine-wide gitignore

`git/ignore` is linked to the ignore file git actually reads: `core.excludesFile` when it
is set, else `$XDG_CONFIG_HOME/git/ignore`. `git_excludes_path()` in `lib/paths.sh`
resolves that. The installer then proves the link took with `git check-ignore` inside a
throwaway `git init`, because every failure mode on this path is silent.

An ignore belongs here only when it is true of **every repo on every machine**. Anything
repo-specific belongs in that repo's own `.gitignore`.

## What it is for, and the one sanctioned directory

### Global git ignore

`git/ignore` hides what tooling writes into a repo without touching that repo — Peacock's `.vscode/settings.json` above all. It is machine-wide and profile-independent, so an ignore belongs there only when it is true of every repo on every machine; anything repo-specific belongs in that repo's `.gitignore`. Ignore the **file** (`.vscode/settings.json`), never the directory, so a project can still commit `extensions.json` or `launch.json`. The one sanctioned directory is `**/.claude/worktrees/`, and the reason it is the exception is that it is not a file tooling writes but `WT_ROOT` itself — every byte under it is a working copy of the repo it sits inside, so nothing there is ever committable, and a `git add -A` that reached it would commit a second copy of the repo into itself. Unignored it also costs the thing `git status` is for: a permanent `?? .claude/` in every repo a worktree was ever cut in, sitting exactly where real unstaged changes are read. It stays scoped to that subdirectory rather than to `.claude/`, so a project can still track its own skills or agent config. It cannot help a repo that already tracks the file — that needs `git update-index --skip-worktree` or a commit
