# Address Comments — PR Review Feedback Handler

Fetch the review threads from a GitHub pull request, present them for selection, and then critically evaluate and address the chosen comment — debating the suggestion rather than blindly applying it.

**Parameter:** `$ARGUMENTS` — the full URL of a GitHub pull request (e.g., `https://github.com/owner/repo/pull/123`).

If no argument is provided, ask the user for the PR URL and stop.

## Step 1: Parse the PR URL

Extract `owner`, `repo`, and `pr_number` from the URL.

For a URL like `https://github.com/acme/my-repo/pull/42`:
- `owner` = `acme`
- `repo` = `my-repo`
- `pr_number` = `42`

If the URL doesn't look like a GitHub PR URL, warn the user and stop.

## Step 2: Load the PR Context

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

## Step 2b: Check Out the PR Branch

From the PR metadata output, extract the **source branch name** (`headRefName` field).

1. **Check the current branch** — run `git branch --show-current`.
2. **If already on the correct branch**, skip ahead to Step 3.
3. **If on a different branch**, check out the PR's source branch:
   - Run `git fetch origin <source_branch>` to ensure the branch is available locally.
   - Run `git checkout <source_branch>` to switch to it.
   - If the checkout fails due to uncommitted changes, warn the user and ask how to proceed (stash, commit, or abort) — do NOT force-checkout or discard changes.
4. **Pull latest changes** — run `git pull --ff-only`. If this fails (e.g., local commits diverge), warn the user but continue.

This ensures the local codebase matches the PR so that file reads and edits target the correct code.

## Step 3: Filter and Enumerate Threads

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

Print a numbered summary of all unresolved discussion threads:

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

If there are **no unresolved threads**, tell the user "No unresolved comment threads found on this PR" and stop.

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

1. Make the code changes using the `Edit` tool.
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

### Step 7b: Offer to Post the Reply

After drafting a reply (for reject or modify decisions), ask the user:

> Would you like me to post this reply to the thread on GitHub? (yes/no)

If the user says yes:

1. Use the **thread ID** from the reviews GraphQL data for the selected thread (the `id` field on `reviewThreads.nodes`).
2. Write the reply body to a temporary file, then post using `-F body=@<file>` to avoid shell encoding issues (em-dashes, quotes, backticks, etc. break `-f body='...'`):
   ```bash
   cat > /tmp/pr-reply-body.txt << 'ENDOFBODY'
   <reply text here>
   ENDOFBODY

   gh api graphql \
     --field query='mutation($threadId: ID!, $body: String!) { addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: $threadId, body: $body}) { comment { id body createdAt } } }' \
     --field threadId='<thread_id>' \
     -F body=@/tmp/pr-reply-body.txt
   ```
   - The `<thread_id>` is the GraphQL node ID from the thread data.
   - **Never** pass the body inline with `-f body='...'` — special characters will cause GraphQL parse errors.
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

## Step 9: Self-Improvement

After the session, reflect on how the execution went. Consider:

- Did URL parsing work correctly for the given GitHub URL?
- Were there issues fetching reviews (pagination, permissions, empty responses)?
- Did the diff context help or was it stale relative to the local code?
- Were the drafted replies well-received or did the user need to heavily edit them?
- Did the critical analysis add value, or was it obvious the reviewer was correct?

If any issues were encountered, **edit this skill file** (`~/.claude/skills/address-comments/SKILL.MD`) to add instructions, warnings, or tips that would prevent the same issue next time. Keep edits surgical. Briefly tell the user what was updated and why.
