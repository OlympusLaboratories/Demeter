# Worktrees

A git worktree is a second working directory attached to the same repository. It has its
own checkout on its own branch and shares the one `.git`, so switching between two pieces
of work costs nothing and neither can disturb the other's files.

That property is the whole reason the fix skills use them. Several fixes run at once here,
one session per worktree, and a plain `git checkout` would have them fighting over a single
working directory — one session's half-finished edits sitting in the tree another session is
about to commit.

## The layout

Skills create worktrees under the repository's own `.claude/worktrees/<branch>`:

```
~/code/myrepo/                              main checkout, on the default branch
~/code/myrepo/.claude/worktrees/dylan/ENG-1  a worktree on dylan/ENG-1
~/code/myrepo/.claude/worktrees/dylan/ENG-2  a worktree on dylan/ENG-2
```

Keeping them inside the repository rather than beside it means they travel with the
checkout, they are covered by the same ignore rules, and `git worktree list` is the only
index that matters.

## Which skills make one

| Skill | Behaviour |
|---|---|
| `fix-linear` | A worktree per ticket, by default. |
| `fix-freeform` | Only when it escalates to `--branch new`. Its default (`--branch default`) works in place on the default branch and makes no worktree. |
| `fix-feedback` | A worktree for the branch under review, in its merge/pull-request mode. |
| `fix-autonomous` | Creates none of its own — it inherits whichever worktree the fix skill it delegated to set up, and owns that one branch for the whole run. |
| `review-code` | In incoming mode only, a **detached** worktree at `.claude/worktrees/review/<branch>`. It never checks somebody else's branch out over yours. |
| `commit-msg`, `changes-description`, `changes-diagram`, `docs-humanize` | None. They read the current directory. |

Pass `in place`, `--here`, or `no worktree` in the skill argument to skip the worktree and
use a plain checkout instead. A repository that cannot host worktrees falls back to that
automatically.

Skills enter a worktree with the `EnterWorktree` tool rather than by `cd`-ing, because the
session's working directory has to move with it. A fresh worktree has no installed
dependencies, so the skill detects the package manager from the lockfile and offers to run
the install.

## Moving between them

Each profile's shell config defines four helpers.

**`wt [query]`** — jump to a worktree. With no argument it goes to the main checkout.
With one it matches an exact branch name first, then an exact directory name, then a
case-insensitive substring of either, and asks when more than one matches.

**`wtl`** — list every worktree with its branch, how long ago it was last committed to, its
upstream state, and its path. The current one is marked `*`.

```
   BRANCH                   LAST COMMIT      STATE          PATH
 * dylan/ENG-1              2 hours ago      ahead 3        .claude/worktrees/dylan/ENG-1
   dylan/ENG-2              6 days ago       gone           .claude/worktrees/dylan/ENG-2
```

**`go <branch>`** — worktree-aware `git checkout`. If a worktree already holds that branch
it `cd`s there instead of failing the way plain `git checkout` would; otherwise it checks
out normally. Anything that is not a single bare word (`go -b new`, `go .`, `go -- file`)
is passed straight through to git untouched.

**`wtclean`** — remove worktrees whose branch is gone from the remote or whose last commit
is older than `WT_STALE_DAYS` (default 90). It fetches with `--prune` first so "gone" means
gone, and it is a **dry run unless you pass `-y`**.

```bash
wtclean                  # show what would go
wtclean -y               # actually remove them
wtclean --days 30 -y     # stricter staleness cutoff
wtclean --keep-branches  # remove the worktrees, keep the local branches
```

## Cleanup is yours

No skill ever removes a worktree. Cleanup is deliberately manual, because a worktree may
hold uncommitted work and an agent cannot tell whether you still want it. When a branch is
merged or abandoned:

```bash
git worktree remove .claude/worktrees/<branch>
```

Add `--force` only if you are certain the uncommitted changes in it are disposable. If the
directory was already deleted by hand, `git worktree prune` clears the stale entry.

## Sessions follow the worktree

Two pieces of tooling keep worktrees from fragmenting the editor.

**`link-worktree-session.py`** makes every session in a repository visible from the main
checkout's window, wherever it actually runs. Claude Code files a transcript under a slug
derived from the session's directory and *moves* it when a session enters a worktree, while
the panel rebuilds its list from the main checkout's slug alone — so worktree sessions used
to simply vanish after a reload. The hook turns each worktree's project directory into a
symlink to the main checkout's, which makes Claude Code's own move a no-op and leaves every
transcript a real file in one place. See the Hooks section of [README.md](README.md).

**`tools/worktree-sync/`** keeps the active Claude Code tab and the active terminal on the
same worktree in both directions, so you cannot type a prompt into one worktree's session
while running commands in another. It pairs them by absolute worktree path, never by name.

## When not to use one

A worktree is overhead when the change is small and you are not running anything else: a
fresh checkout with no `node_modules`, no `.venv`, and no build cache can cost more to set
up than the fix takes. That is why `fix-freeform` defaults to working in place and only
escalates when the change genuinely needs isolation — and why every skill takes `in place`.
