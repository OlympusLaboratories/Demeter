# Feedback — Review Feedback Handler

Work through review feedback on the current changes — present each item for selection, then critically evaluate and address the chosen one, debating the suggestion rather than blindly applying it.

This skill runs in one of two **modes**, chosen automatically from the argument:

- **Mode A — Pull request:** `$ARGUMENTS` is a GitHub pull request URL. Fetch the review threads from that PR.
- **Mode B — Local review output:** no argument is given. Pull the feedback from a **review agent's output earlier in this conversation** — e.g. the `review-code` swarm's confirmed findings, or any code review already produced in the chat. Nothing is fetched from GitHub; the changes are already local.

**Parameter:** `$ARGUMENTS` — optionally, the full URL of a GitHub pull request (e.g., `https://github.com/owner/repo/pull/123`). Omit it to use Mode B.

**Selecting the mode:**
- `$ARGUMENTS` looks like a GitHub PR URL → **Mode A**: do Steps 1, 2, 2b, then continue from Step 3.
- `$ARGUMENTS` is empty → **Mode B**: skip Steps 1, 2, and 2b; start at **Step 1B**, then continue from Step 4.
- `$ARGUMENTS` is empty **and** there is no review output anywhere earlier in the conversation → tell the user there's nothing to work through (ask them to pass a PR URL or run a review first, e.g. `/review-code`) and stop.

## Step 1: Parse the PR URL (Mode A)

Extract `owner`, `repo`, and `pr_number` from the URL.

For a URL like `https://github.com/acme/my-repo/pull/42`:
- `owner` = `acme`
- `repo` = `my-repo`
- `pr_number` = `42`

If the URL doesn't look like a GitHub PR URL, warn the user and stop.

## Step 2: Load the PR Context (Mode A)

### 2a. Fetch PR metadata, reviews, and diff in parallel

Use the `gh` CLI to fetch all data. Make all three calls **in parallel in a single message**:

**PR metadata:**
```bash
gh pr view <pr_number> -R <owner>/<repo> --json title,body,state,author,headRefName,baseRefName,number,isDraft
```

**PR reviews (GraphQL):**
```bash
gh api graphql -f query='
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          originalLine
          comments(first: 50) {
            nodes {
              id
              author { login }
              body
              createdAt
              replyTo { id }
            }
          }
        }
      }
      reviews(first: 50) {
        nodes {
          id
          author { login }
          body
          state
          submittedAt
        }
      }
      comments(first: 100) {
        nodes {
          id
          author { login }
          body
          createdAt
        }
      }
    }
  }
}' -F owner='<owner>' -F repo='<repo>' -F number=<pr_number>
```

**PR file changes:**
```bash
gh api repos/<owner>/<repo>/pulls/<pr_number>/files --paginate
```

Parse each response as JSON.

- **pr-info fields:** `title`, `body` (description), `state`, `author.login`, `headRefName` (source branch), `baseRefName` (target branch), `number`, `isDraft`
- **pr-reviews fields:** The GraphQL response is under `data.repository.pullRequest`. Contains `reviewThreads` (inline comments with `isResolved`, `path`, `line`, and nested `comments`), `reviews` (top-level review bodies with `state`), and `comments` (general PR comments).
- **pr-changes fields:** Array of file objects with `filename`, `previous_filename`, `patch` (diff hunk), and `status`.

Do NOT serialize these calls — run them in parallel.

## Step 2b: Set Up the PR Branch (Mode A)

From the PR metadata output, extract the **source branch name** (`headRefName` field) as `SOURCE_BRANCH`.

By default, isolate the checkout in its own **git worktree** so it doesn't disturb other work in progress. **Escape hatch:** if `$ARGUMENTS` contains `in place`, `--here`, or `no worktree`, or the repo can't host worktrees, use the in-place checkout at the end of this step instead.

1. **Already on it?** Run `git branch --show-current` — if it already equals `SOURCE_BRANCH`, pull latest and skip to Step 3:
   ```bash
   git pull --ff-only
   ```
2. **Existing worktree?** Run `git worktree list --porcelain` — if `SOURCE_BRANCH` is already checked out in a worktree, enter it with the `EnterWorktree` tool (`path:` = that worktree's path) and skip to step 5 (no dependency install needed — it already has them).
3. **Fetch the branch:** `git fetch origin <SOURCE_BRANCH>`
4. **Add and enter a worktree** at `.claude/worktrees/<SOURCE_BRANCH>` (run from the repo root):
   ```bash
   git worktree add .claude/worktrees/<SOURCE_BRANCH> <SOURCE_BRANCH>
   ```
   If the branch only exists on the remote, use `git worktree add .claude/worktrees/<SOURCE_BRANCH> origin/<SOURCE_BRANCH>` to create a local tracking branch. Then call the `EnterWorktree` tool with `path: .claude/worktrees/<SOURCE_BRANCH>` to move this session into it.
5. **Update to latest:** `git pull --ff-only`. If this fails (local commits diverge), warn the user but continue — the branch is still usable.
6. **Offer to install dependencies** — a fresh worktree has none. Detect the package manager (npm/yarn/pnpm/bun/uv/poetry/pip/go/bundler/cargo) from the lockfile present and offer to run its install command; wait for the user's approval before running it. Skip this if you reused an existing worktree in step 2.

Worktrees are cleaned up manually — remove with `git worktree remove <path>` once the PR is merged. See `WORKTREES.md` in the Demeter repo for the full guide.

**In-place checkout (escape hatch):** after `git fetch origin <SOURCE_BRANCH>`, run `git checkout <SOURCE_BRANCH>` in the current tree. If checkout fails due to uncommitted changes, warn the user and ask how to proceed (stash, commit, or abort) — do NOT force-checkout or discard changes. Then `git pull --ff-only`.

This ensures the local codebase matches the PR so that file reads and edits target the correct code.

## Step 1B: Gather Feedback from Earlier Review Output (Mode B)

When no PR URL was given, look back through the current conversation for output produced by a review agent or skill — for example the `review-code` adversarial swarm's confirmed findings, or any code-review comments generated earlier in the chat. Use the most recent such review if there are several.

Treat each distinct review finding as one feedback "thread":
- **File path and line** — from the finding's location.
- **Comment body** — the finding's summary plus its failure scenario / rationale.
- **Author** — the review source, for display only (e.g. `review-code: correctness`).
- **Replies** — none (local findings have no thread history).
- **Resolved status** — always unresolved.

Collect these into the same numbered structure used in Step 4. Keep findings that target the same file/line as separate items unless they are clearly duplicates. Then go straight to **Step 4** to display them.

In Mode B there is no branch to check out (the changes are already local) and no external thread to post replies to, so **Steps 2b and 7b do not apply** — skip them. Everything else (critical evaluation, applying changes, drafting a reply for the user to reuse) works the same.

## Step 3: Filter and Enumerate Threads (Mode A)

The GraphQL reviews response contains three collections under `data.repository.pullRequest`:
- `reviewThreads.nodes` — inline diff comments attached to a file and line; have `isResolved`, `path`, `line` fields, with nested `comments.nodes` (first comment is root, rest are replies)
- `reviews.nodes` — top-level review bodies (approval/request-changes summary); have `state` and `body`
- `comments.nodes` — general PR comments not attached to a line

**Filter out:**
- Inline threads where `isResolved: true`
- Empty bodies (body is blank or whitespace only)
- Bot/automation comments (e.g., from `github-actions`, `dependabot`, `atlantis`). Do NOT exclude AI code-review bots — their feedback is real review feedback.
- Review entries with `state: "APPROVED"` and no substantive body

For each remaining thread, extract:
- **Thread number** (sequential, starting at 1)
- **Type** (`inline`, `review`, or `general`)
- **Author** of the initial comment (from `author.login`)
- **File path and line** if inline (from `path` and `line` on the thread node)
- **Initial comment body** (full text)
- **Replies** (subsequent entries in `comments.nodes` after the first, each with `author.login` and `body`)
- **Resolved status** (`isResolved` for inline threads)

## Step 4: Display the Threads

Print a numbered summary of all unresolved items. In **Mode A** use the PR heading below; in **Mode B** use a heading like `## Review Feedback on Local Changes` and list the findings gathered in Step 1B (there are no reply counts for local findings — omit the 💬 line).

```
## Unresolved Comment Threads on #<pr_number> — "PR Title"

**1.** `src/path/file.py:42` — @reviewer_name
  > "The comment body here (first ~3 lines or 300 chars)..."
  💬 2 replies

**2.** (General comment) — @other_reviewer
  > "This approach seems overly complex..."
  💬 0 replies

**3.** `pkg/handler.go:118` — @reviewer_name
  > "Consider using a context.WithTimeout here..."
  💬 1 reply

---
Enter a number to address that comment, or "all" to work through them sequentially.
```

**Do NOT use `AskUserQuestion` here.** Simply print the numbered list above and stop. Wait for the user to reply in chat with a number (e.g., `2`) or `all`.

If there are **no unresolved threads** (Mode A) or no findings in the review output (Mode B), tell the user there's nothing to work through and stop.

## Step 5: Load Full Context for the Selected Thread

Once the user picks a thread:

1. **Display the full thread** — show the complete initial comment and all replies with authors, untruncated.
2. **Show the relevant code** — if it's an inline comment, display the surrounding diff hunk from `pr-changes` for that file. Also read the current local version of the file around the referenced lines using the `Read` tool so you can see the latest state (the diff may be outdated if commits were pushed after the comment was written).
3. **Identify what the reviewer is asking for** — summarize the reviewer's request/suggestion in one sentence.

## Step 6: Critically Evaluate the Feedback

**Do NOT immediately apply the suggestion.** Instead, engage in critical analysis:

### 6a. Assess the suggestion

Consider and present your analysis to the user:

- **Is the reviewer correct?** Does their suggestion actually improve the code? Are there factual errors in their reasoning?
- **Is it complete?** Does the suggestion account for edge cases, or would applying it naively introduce bugs?
- **Is it the best approach?** Even if the reviewer's concern is valid, is their proposed solution the best one? Are there better alternatives?
- **What are the trade-offs?** Would applying this change affect performance, readability, consistency with the rest of the codebase, or other code?
- **Is it subjective?** Is this a matter of style/preference, or a genuine correctness/quality concern?

### 6b. Present your assessment

Lay out your analysis clearly:

```
### Analysis of Thread N

**Reviewer's request:** [one-sentence summary]

**Assessment:** [Agree / Partially agree / Disagree]

**Reasoning:**
- [Point 1]
- [Point 2]
- ...

**Recommendation:** [What you think should be done, and why]
```

### 6c. Ask the user for a decision

**Do NOT use `AskUserQuestion`.** Print the options as text and wait for the user to reply in chat:

> How would you like to proceed?
> - **Apply** — implement the reviewer's suggestion as-is
> - **Modify** — implement a modified version (I'll describe what I'd change)
> - **Reject** — do not make code changes; I'll draft a reply explaining why
> - **Discuss** — talk through it more before deciding

If the user chooses "Discuss", continue the dialogue — ask clarifying questions, explore alternatives, or dig deeper into the code. Repeat this step until the user reaches a decision.

## Step 7: Execute the Decision

### If applying changes (fully or with modifications):

1. Make the code changes using the `Edit` tool. **Add no comments while doing it** — not the reviewer's point, not why the code now looks this way; that goes in the drafted reply, not the source.
2. Show the user what was changed.
3. If the change was modified from the original suggestion, draft a reply for the comment thread explaining what was done differently and why.

### If rejecting the feedback:

Draft a reply that the user can post in the comment thread. The reply should be:
- **Professional and respectful** — acknowledge the reviewer's point
- **Substantive** — explain the reasoning clearly, not just "I disagree"
- **Specific** — reference concrete code, behavior, or constraints that support the decision
- **Constructive** — if applicable, suggest what alternative concern you did address or offer a compromise

Print the reply in a fenced code block so the user can copy it:

```
Suggested reply for Thread N:

---
[reply text here]
---
```

Then proceed to **Step 7b** to offer posting the reply.

### If applying with modifications:

Both make the code changes AND draft a reply explaining the partial application:

```
Suggested reply for Thread N:

---
Good catch on [aspect]. I've [describe what was changed].

Regarding [the part not applied] — I opted to keep [current approach] because [reasoning]. [Optional: suggest follow-up or alternative].
---
```

Then proceed to **Step 7b** to offer posting the reply.

### Step 7b: Offer to Post the Reply (Mode A only)

In Mode B there is no external thread to post to — skip this step and simply present the drafted reply in chat for the user to reuse if they want.

After drafting a reply (for reject or modify decisions), ask the user:

> Would you like me to post this reply to the thread on GitHub? (yes/no)

If the user says yes:

1. Use the **thread ID** from the reviews GraphQL data for the selected thread (the `id` field on `reviewThreads.nodes`).
2. Post the reply using the `github_api.py` script, piping the body via heredoc to stdin to avoid shell encoding issues:
   ```bash
   python3 ~/.claude/scripts/github_api.py reply-to-thread '<thread_id>' << 'ENDOFBODY'
   <reply text here>
   ENDOFBODY
   ```
   - The `<thread_id>` is the GraphQL node ID from the thread data.
   - **Always** use a heredoc piped to stdin for the body — never pass it as a CLI argument or use temp files with redirects.
3. Confirm to the user that the reply was posted successfully, or report any errors.

If the user says no, continue to Step 8 as normal.

**Note:** This only applies to **inline** threads (which have a thread ID). For `general` or `review` type comments, the `reply-to-thread` command won't work — in those cases, skip this step and just present the drafted reply for the user to copy.

## Step 8: Offer to Continue

After resolving one thread, offer to address the next unresolved thread. Loop back to Step 5 with the next thread if the user agrees.

## Important Rules

1. **NEVER auto-apply suggestions.** Always analyze and present your assessment first. The whole point of this skill is to think critically, not to blindly accept reviewer feedback.
2. **NEVER post replies to GitHub.** Only draft replies and print them in chat. The user decides whether and when to post them.
3. **NEVER resolve threads.** Thread resolution is the user's action in the GitHub UI after they've posted their reply or pushed changes.
4. **Be honest in your assessment.** If the reviewer is right, say so. If they're wrong, explain why clearly. Don't just side with the PR author.
5. **Consider codebase context.** When evaluating suggestions, look at how similar patterns are handled elsewhere in the codebase using `Grep` and `Read`. Consistency matters.
6. **Keep replies concise.** Drafted replies should be 2-5 sentences. Long replies in code review threads are rarely read.
7. **Use the local codebase.** The user is expected to have the PR branch checked out locally. Use `Read`, `Grep`, and `Glob` to explore the actual code — don't rely solely on the diff from the API.
8. **No comments in the code.** When you apply a change, add no explanatory comment, docstring, or note recording what the reviewer asked for — a reviewer reading the next diff does not need the last review narrated back at them. That belongs in the drafted reply. Machine-read directives (linter suppressions, build pragmas, a doc-comment CI requires) are program input, not commentary, and stay allowed.

## Step 9: Self-Improvement

After the session, reflect on how the execution went. Consider:

- Did URL parsing work correctly for the given GitHub URL?
- Were there issues fetching reviews (pagination, permissions, empty responses)?
- Did the diff context help or was it stale relative to the local code?
- Were the drafted replies well-received or did the user need to heavily edit them?
- Did the critical analysis add value, or was it obvious the reviewer was correct?

If any issues were encountered, **edit this skill file** (`~/.claude/skills/fix-feedback/SKILL.md`) to add instructions, warnings, or tips that would prevent the same issue next time. Keep edits surgical. Briefly tell the user what was updated and why.