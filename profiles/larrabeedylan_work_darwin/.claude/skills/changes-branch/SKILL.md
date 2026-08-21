# Branch Context Loader

Load the diff of the current branch compared to the default branch into chat context, so you can immediately start working with the relevant changes in a fresh conversation.

## Step 1: Identify Branches

**If an argument was passed, it names the target branch — switch to it before doing anything else.** The rest of the conversation will be working with that branch's code, so the session must actually be on it, not just diffing it from elsewhere. Verify it exists (`git branch -a --list '*<arg>*'`), then:

- **Already checked out in another worktree** (a `+` prefix in `git branch`, or a row in `git worktree list`): switch the session into that worktree with `EnterWorktree({path: "<worktree path>"})`. Do NOT `git checkout` — git refuses, since the branch is claimed elsewhere. `EnterWorktree` is often a *deferred* tool with no loaded schema; load it first with `ToolSearch({query: "select:EnterWorktree"})`, otherwise the call fails validation. Run the `git branch -a --list`, `git worktree list`, `git rev-parse --abbrev-ref HEAD`, and `git status --short` probes together in one batch — they're independent, and their combined output tells you which of the two cases you're in.
- **Not checked out anywhere:** `git checkout <branch>` in place. Stash or surface uncommitted work first if the checkout would conflict.

Then continue with the steps below, treating the now-current branch as the target. The "current branch is the default branch" note below still applies, but evaluate it *after* switching. If both a local and a remote ref exist, compare `git rev-parse <branch> origin/<branch>` and mention it if they've diverged.

With no argument, determine the current branch and the default branch (usually `main` or `master`).

```bash
git rev-parse --abbrev-ref HEAD
```

```bash
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'
```

If `symbolic-ref` fails, fall back to checking whether `main` or `master` exists:

```bash
git branch -r | grep -E 'origin/(main|master)$' | head -1 | sed 's@.*origin/@@'
```

Store the result as `DEFAULT_BRANCH`.

**IMPORTANT:** If the current branch IS the default branch, warn the user ("You're already on the default branch — there's no feature branch diff to load.") and stop. Before stopping, run `git status --short` and surface any uncommitted/untracked work — the user may still want that loaded as context, and offering to show it (or to switch/create a feature branch) is more useful than a bare stop.

**In a worktree-isolated session, run every git command on its own.** Compound commands — `;`-chained, `$(…)` substitution, pipes, redirects — are refused outright, because the guard can't verify they stay inside the worktree. So no `MB=$(git merge-base …); git diff $MB..HEAD`: run `git merge-base` alone, read the SHA from its output, and paste it literally into the next command. This also applies to the two default-branch probes above: drop the `| sed` / `2>/dev/null` and run bare `git symbolic-ref refs/remotes/origin/HEAD`, then strip the `refs/remotes/origin/` prefix yourself when reading the output.

## Step 2: Fetch Latest Default Branch

Fetch the latest remote state so the diff is accurate:

```bash
git fetch origin <DEFAULT_BRANCH> --quiet
```

## Step 3: Find the Merge Base

Use the merge base to get only the changes introduced on this branch, excluding unrelated commits on the default branch:

```bash
git merge-base origin/<DEFAULT_BRANCH> HEAD
```

Store the result as `MERGE_BASE`.

## Step 4: Generate and Display the Diff

Generate the diff from the merge base to HEAD:

```bash
git diff <MERGE_BASE>..HEAD
```

If the diff is extremely large (over 20,000 lines), use `--stat` first to give an overview, then ask the user if they want the full diff or specific files only:

```bash
git diff --stat <MERGE_BASE>..HEAD
```

**ALWAYS print the diff, even if you already have it in context.** This skill exists to put the diff in the *user's window*, and the most common reason for re-running it is that they reloaded the window and lost the scrollback — the one situation where "it's already loaded, here's just the summary" is exactly the wrong answer. Never skip or abbreviate the diff on the grounds that a previous invocation already loaded it; re-verify state (branch, merge base, status) and print it again in full.

**Large output gets persisted instead of displayed.** A single tool result over ~30KB is saved to a scratch file rather than shown, which means the user never sees it. Split it: one `git diff` per file, and for a file whose diff alone exceeds that, use `Read` with `offset`/`limit` in halves (for a newly-added file the contents are the diff body, so this loses nothing but the `+` prefixes).

Decide the split *before* running the diff, not after a result vanishes: `git diff --numstat <MERGE_BASE>..HEAD` gives per-file line counts, and `wc -c <path>` gives bytes for a new file. A file near 30KB is over the limit once diff prefixes and the `+++`/`@@` header are added, so treat ~28KB as the cutoff and halve it.

**Edge case — no committed changes yet:** If `git rev-list --count <MERGE_BASE>..HEAD` returns `0` but `git status --short` shows modifications, the work-in-progress lives in the working tree, not in commits. Show `git diff HEAD` (or `git diff` plus `git diff --cached` if there are staged changes too) instead, and note in the summary that changes are uncommitted with 0 commits ahead. Do not stop — uncommitted work is the actual branch context in this case.

## Step 5: Summarize the Branch Context

**IMPORTANT:** You MUST always end your response with this summary — it is the final output the user sees. Do not skip it or place it before the diff. After all git commands and diff output are complete, print the following summary block:

- **Branch:** current branch name
- **Base:** default branch name
- **Commits:** number of commits ahead (`git rev-list --count <MERGE_BASE>..HEAD`)
- **Files changed:** count and list from `--stat` output
- **Summary:** 2-3 sentence description of what the changes do at a high level

Then tell the user: "Branch context loaded. What would you like to do with these changes?"

## Step 6: Self-Improvement

After completing the above steps, reflect on how the execution went. Consider:

- Did any git commands fail (e.g., not in a repo, detached HEAD, remote not configured)?
- Was the diff too large and needed truncation?
- Did default branch detection work correctly?
- Were there any edge cases (uncommitted changes, merge conflicts, shallow clones)?

If any issues were encountered, **edit this skill file** (`~/.claude/skills/changes-branch/SKILL.md`) to add instructions, warnings, or tips that would prevent the same issue next time. Keep edits surgical — add a note near the relevant step rather than rewriting sections. Briefly tell the user what was updated and why.
