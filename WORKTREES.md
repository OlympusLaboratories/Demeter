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
| `fix-linear` | A worktree per ticket, on `--branch new` — the default on every profile. |
| `fix-freeform` | The same, on the same default. `--branch new` is where the flag starts in both skills; they resolve it identically. |
| `fix-feedback` | A worktree for the branch under review, in its merge/pull-request mode. |
| `autopilot` | Creates none of its own — it inherits whichever worktree the fix skill it delegated to set up, and owns that one branch for the whole run. |
| `review-code` | In incoming mode only, a **detached** worktree at `.claude/worktrees/review/<branch>`. It never checks somebody else's branch out over yours. |
| `commit-msg`, `changes-description`, `changes-diagram`, `docs-humanize` | None. They read the current directory. |

`--branch default` is the way to not get a worktree: it commits onto the repository's
default branch, so there is no feature branch to isolate and no change request at the end
of it. There is no separate in-place flag and no third `--branch` value — a repository
that cannot host worktrees falls back to a plain checkout of the feature branch on its own,
which is a capability fallback rather than a mode anybody selects.

Three conditions force `--branch new` whatever the flag said: the change touches Terraform
or other infrastructure-as-code, the default branch is protected, or the working tree is
dirty. Escalation is one-way within a run — once a check has fired, the commits live on a
branch created for exactly that reason.

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
gone, and it is a **dry run unless you pass `-y`**. `autopilot` deletes the source branch from
the remote as part of merging, which is what makes "gone" ever become true — a merged branch
left on the remote reads here as live work, so the worktree never ages out and `wtclean`
reports nothing to do.

```bash
wtclean                  # show what would go
wtclean -y               # actually remove them
wtclean --days 30 -y     # stricter staleness cutoff
wtclean --keep-branches  # remove the worktrees, keep every local branch
```

It then sweeps local branches **no worktree holds**, because the worktree pass can only
ever see a branch some worktree has checked out — so a branch whose worktree went earlier,
or that never had one, is invisible to it and survives every run. A branch goes when it is gone from the
remote, or when the default branch already contains its changes — and "contains" is tested
by merging it into `origin/<default>` in memory and seeing whether the result differs, not
by asking whether its tip is an ancestor. That distinction is the whole thing on a repo that
**squash-merges**: a squash rewrites the commit, so the branch tip is never an ancestor and an
ancestry test calls every squash-merged branch unmerged. The one branch it never touches is
one that was **never pushed** — no upstream and not in the default branch is work in
progress, so it is left alone and not even mentioned. A branch that is gone from the remote
but genuinely absent from the default branch is still deleted, because that is the signal you
asked for, but the line says so and names `git reflog` — the commits survive the delete and
`git branch <name> <sha>` brings them back. `--keep-branches` skips the sweep entirely.

`f` (`freshen`) runs `wtclean --no-fetch -y` as its second-to-last step, so the ordinary
"catch my branch up" command reclaims finished worktrees on its own and `git status` stays
the last thing it prints. `--no-fetch` is deliberate: `update` has just fetched with
`--prune`, which is what makes "gone" accurate, so a second fetch would only cost a round
trip. It skips the worktree you are standing in, so running `f` inside a worktree never
pulls the ground out from under your own shell.

## Cleanup is yours

No skill ever removes a worktree. Cleanup is deliberately manual, because a worktree may
hold uncommitted work and an agent cannot tell whether you still want it. What a skill does
do is delete the **remote** branch once its change request merges — that is the signal
`wtclean` reads, and it is the whole division of labour. When a branch is merged or
abandoned:

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
up than the fix takes. `--branch default` is the escape, and it costs more than the
worktree: no feature branch means no change request, which means nobody reviews the change
before it is on the branch every other checkout is cut from. That trade is worth making
for a typo and almost never otherwise, which is why `new` is the default on both skills and
the three escalation checks can take `default` away but never hand it back.
