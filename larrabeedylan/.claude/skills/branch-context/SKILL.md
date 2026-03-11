# Branch Context Loader

Load the diff of the current branch compared to the default branch into chat context, so you can immediately start working with the relevant changes in a fresh conversation.

## Step 1: Identify Branches

Determine the current branch and the default branch (usually `main` or `master`).

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

**IMPORTANT:** If the current branch IS the default branch, warn the user ("You're already on the default branch — there's no feature branch diff to load.") and stop.

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

If any issues were encountered, **edit this skill file** (`~/.claude/skills/branch-context/SKILL.md`) to add instructions, warnings, or tips that would prevent the same issue next time. Keep edits surgical — add a note near the relevant step rather than rewriting sections. Briefly tell the user what was updated and why.

