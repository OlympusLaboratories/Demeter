# Address Comments — PR Review Feedback Handler

Fetch the review threads from a GitHub pull request, present them for selection, and then critically evaluate and address the chosen comment — debating the suggestion rather than blindly applying it.

**Parameter:** `$ARGUMENTS` — the full URL of a GitHub pull request (e.g., `https://github.com/owner/repo/pull/123`).

If no argument is provided, ask the user for the PR URL and stop.

## Step 1: Parse the PR URL

Extract `owner`, `repo`, and `pr_number` from the URL.

For a URL like `https://github.com/owner/repo/pull/42`:
- `owner` = `owner`
- `repo` = `repo`
- `pr_number` = `42`

If the URL doesn't look like a GitHub PR URL, warn the user and stop.

## Step 2: Load the PR Context

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

## Step 2c: Check Out the PR Branch

From the PR metadata (fetched in Step 2), extract the **source branch name** (`headRefName` field).

1. **Check the current branch** — run `git branch --show-current` to see what branch is currently checked out.
2. **If already on the correct branch**, skip ahead to Step 3.
3. **If on a different branch**, check out the PR's source branch:
  - Run `git fetch origin <source_branch>` to ensure the branch is available locally.
  - Run `git checkout <source_branch>` to switch to it.
  - If the checkout fails due to uncommitted changes, warn the user and ask how to proceed (stash, commit, or abort) — do NOT force-checkout or discard changes.
4. **Pull latest changes** — run `git pull --ff-only` to ensure the local branch is up to date with the remote. If this fails, warn the user but continue.

This ensures the local codebase matches the PR so that file reads and edits target the correct code.

## Step 3: Filter and Enumerate Threads

From the raw reviews response, filter to only **unresolved** threads that contain review feedback.

Exclude inline threads where `isResolved: true` (returned directly from the GitHub GraphQL API).

Exclude also:
- Bot comments that are purely operational (CI status, auto-generated reports). Do NOT exclude AI code-review bots — their feedback is real review feedback.
- Review entries with `state: "APPROVED"` and no actionable body text.
- Threads where the author is the PR author and there are no replies (self-notes).

For each remaining thread, extract:
- **Thread number** (sequential, starting at 1)
- **Author** of the initial comment
- **File path and line(s)** if it's an inline comment (from `position` data)
- **Initial comment body** (full text)
- **Replies** (all subsequent notes in the thread, with author and body)
- **Type** (`inline`, `review`, or `general`)

## Step 4: Display the Threads

Print a numbered summary of all unresolved discussion threads:

```
## Review Threads on #number — "PR Title"

**1.** `src/path/file.py:42` — @reviewer_name
  > "The comment body here (first ~3 lines or 300 chars)..."
  💬 2 replies

**2.** (General comment) — @other_reviewer
  > "This approach seems overly complex..."
  💬 0 replies

**3.** `pkg/handler.go:118-125` — @reviewer_name
  > "Consider using a context.WithTimeout here..."
  💬 1 reply

---
Enter a number to address that comment, or "all" to work through them sequentially.
```

**Do NOT use `AskUserQuestion` here.** Simply print the numbered list above and stop. Wait for the user to reply in chat with a number (e.g., `2`) or `all`.

If there are **no threads**, tell the user "No review threads found on this PR" and stop.

## Step 5: Load Full Context for the Selected Thread

Once the user picks a thread:

1. **Display the full thread** — show the complete initial comment and all replies with authors, so nothing is truncated.
2. **Show the relevant code** — if it's an inline comment, display the surrounding diff hunk from the PR changes fetched in Step 2. If the file exists locally, also read the current local version of the file around the referenced lines using the `Read` tool so you can see the latest state.
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

If the user chooses "Discuss", continue the dialogue. Repeat this step until the user reaches a decision.

## Step 7: Execute the Decision

### If applying changes (fully or with modifications):

1. Make the code changes using `Edit` tool.
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

### If applying with modifications:

Both make the code changes AND draft a reply explaining the partial application:

```
Suggested reply for Thread N:

---
Good catch on [aspect]. I've [describe what was changed].

Regarding [the part not applied] — I opted to keep [current approach] because [reasoning]. [Optional: suggest follow-up or alternative].
---
```

## Step 8: Offer to Continue

After resolving one thread, offer to address the next thread. Loop back to Step 5 with the next thread if the user agrees.

## Important Rules

1. **NEVER auto-apply suggestions.** Always analyze and present your assessment first.
2. **NEVER post replies to GitHub.** Only draft replies and print them in chat. The user decides whether and when to post them.
3. **NEVER resolve threads.** Thread resolution is the user's action after they've posted their reply or pushed changes.
4. **Be honest in your assessment.** If the reviewer is right, say so. If they're wrong, explain why clearly.
5. **Consider codebase context.** When evaluating suggestions, look at how similar patterns are handled elsewhere in the codebase using `Grep` and `Read`. Consistency matters.
6. **Keep replies concise.** Drafted replies should be 2-5 sentences.
7. **Use the local codebase.** Use `Read`, `Grep`, and `Glob` to explore the actual code — don't rely solely on the diff from the API.

## Step 9: Self-Improvement

After the session, reflect on how the execution went. Consider:

- Did URL parsing work correctly?
- Were there issues fetching reviews (pagination, permissions, empty responses)?
- Did the diff context help or was it stale relative to the local code?
- Were the drafted replies well-received or did the user need to heavily edit them?
- Did the critical analysis add value, or was it obvious the reviewer was correct?

If any issues were encountered, **edit this skill file** (`~/.claude/skills/pr-description/SKILL.md`) to add instructions, warnings, or tips that would prevent the same issue next time. Keep edits surgical. Briefly tell the user what was updated and why.

# PR Description Generator

Generate a succinct yet clear pull request description based on the changes already discussed in the current chat context.

## Prerequisites

This command expects that the current conversation already contains context about the branch changes — typically loaded via `/branch-context` or by the user pasting diffs/discussing code changes. If no changes have been discussed, tell the user: "No changes found in the current conversation. Run `/branch-context` first or describe/paste the changes you'd like summarized."

## Step 1: Analyze the Conversation Context

Review all changes discussed in the current chat:
- Diffs, code snippets, and file modifications
- The user's stated intent or goals for the changes
- Any bug fixes, features, refactors, or config changes mentioned
- Decisions made during the conversation (e.g., why a particular approach was chosen)

## Step 2: Write the PR Description

**Output the PR description inside a single markdown code block** (triple backticks with no language tag) so the user can copy the raw markdown and paste it directly into GitHub's PR description field, where it will render correctly with headings, bullets, and links intact. The content inside the code block must be valid, well-formatted markdown.

Use this template inside the code block. The **Summary** and **Changes** sections are always required. The remaining sections are optional — only include them when the conversation contains relevant context.

```
## Summary

1-3 sentences explaining what this PR does and why. Be specific about the concrete change — name the components, services, or files affected. Reference the problem, ticket, or goal that prompted the change.

## Changes

Bulleted list of the key implementation details — only include items that a reviewer needs to know to understand the approach. Skip obvious or trivial changes. If there are notable trade-offs or alternatives that were considered, mention them briefly.

## Testing

(Optional — include only if tests were added or modified.)
Brief description of what tests were added/changed and what they cover.

## Verification

(Optional — include only if commands were run during the conversation to verify correctness, e.g., linting, dry-runs, syntax checks, `terraform plan`, `helm template`, etc.)
List the commands used and their outcomes.

## Rollout

(Optional — include only if there are deployment steps, feature flags, migration considerations, or sequencing requirements.)
Bullet the rollout steps or considerations a reviewer/deployer should be aware of.
```

**IMPORTANT:** The description MUST be wrapped in a code block so the user copies raw markdown, not rendered markdown.

### Guidelines

- **Be concise.** Reviewers skim PR descriptions. Prefer short sentences and bullets over paragraphs.
- **Be precise.** Use the actual names of functions, files, services, and config keys from the diff. Don't paraphrase loosely.
- **Don't pad.** If the change is simple, the description should be short. Only include Testing, Verification, and Rollout when there's real content for them — never add placeholder text like "N/A".
- **Don't editorialize.** Stick to what the code does. Avoid subjective claims like "greatly improves" or "much cleaner".
- **Respect what was discussed.** If the user explained their reasoning during the chat, reflect that in the description.

## Step 3: Self-Improvement

After generating the description, reflect on how the execution went. Consider:

- Was there enough context in the conversation to write a good description, or were there gaps?
- Did the user need to correct or adjust the output?
- Were there edge cases (multiple unrelated changes in one branch, unclear intent)?

If any issues were encountered, **edit this skill file** (`~/.claude/skills/pr-description/SKILL.md`) to add instructions or tips that would prevent the same issue next time. Keep edits surgical. Briefly tell the user what was updated and why.
