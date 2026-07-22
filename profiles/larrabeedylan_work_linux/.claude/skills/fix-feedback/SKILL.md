# Feedback — Review Feedback Handler

Work through review feedback on the current changes — present each item for selection, then critically evaluate and address the chosen one, debating the suggestion rather than blindly applying it.

This skill runs in one of two **modes**, chosen automatically from the argument:

- **Mode A — Merge request:** `$ARGUMENTS` is a GitLab merge request URL. Fetch the review discussion threads from that MR.
- **Mode B — Local review output:** no argument is given. Pull the feedback from a **review agent's output earlier in this conversation** — e.g. the `review-code` swarm's confirmed findings, or any code review already produced in the chat. Nothing is fetched from GitLab; the changes are already local.

**Parameter:** `$ARGUMENTS` — optionally, the full URL of a GitLab merge request (e.g., `https://gitlab.com/group/project/-/merge_requests/123`). Omit it to use Mode B.

**Selecting the mode:**
- `$ARGUMENTS` looks like a GitLab MR URL → **Mode A**: do Steps 1, 2, 2c, then continue from Step 3.
- `$ARGUMENTS` is empty → **Mode B**: skip Steps 1, 2, and 2c; start at **Step 1B**, then continue from Step 4.
- `$ARGUMENTS` is empty **and** there is no review output anywhere earlier in the conversation → tell the user there's nothing to work through (ask them to pass an MR URL or run a review first, e.g. `/review-code`) and stop.

## Step 1: Parse the MR URL (Mode A)

Extract `project_id` (slash-separated path) and `merge_request_iid` from the URL.

For a URL like `https://gitlab.com/group/subgroup/project/-/merge_requests/42`:
- `project_id` = `group/subgroup/project`
- `merge_request_iid` = `42`

If the URL doesn't look like a GitLab MR URL, warn the user and stop.

## Step 2: Load the MR Context (Mode A)

Use `~/.claude/scripts/gitlab-api.sh` to fetch MR data. This script reads the GitLab token securely from `~/.claude/.mcp.json` and keeps it out of conversation context.

The script accepts a **URL-encoded** project path (e.g., `gridmatic%2Ftlaloc-env`). URL-encode the `project_id` by replacing `/` with `%2F`.

Make all three calls **in parallel in a single message**:
```bash
~/.claude/scripts/gitlab-api.sh mr-info "<project_id_urlencoded>" <mr_iid>
~/.claude/scripts/gitlab-api.sh mr-discussions "<project_id_urlencoded>" <mr_iid>
~/.claude/scripts/gitlab-api.sh mr-changes "<project_id_urlencoded>" <mr_iid>
```

Each command outputs one JSON object per line.

## Step 2c: Check Out the MR Branch (Mode A)

From the MR metadata (fetched in Step 2), extract the **source branch name**.

1. **Check the current branch** — run `git branch --show-current` to see what branch is currently checked out.
2. **If already on the correct branch**, skip ahead to Step 3.
3. **If on a different branch**, check out the MR's source branch:
   - Run `git fetch origin <source_branch>` to ensure the branch is available locally.
   - Run `git checkout <source_branch>` to switch to it.
   - If the checkout fails due to uncommitted changes, warn the user and ask how to proceed (stash, commit, or abort) — do NOT force-checkout or discard changes.
4. **Pull latest changes** — run `git pull --ff-only` to ensure the local branch is up to date with the remote. If this fails (e.g., local commits diverge), warn the user but continue — the branch is still usable.

This ensures the local codebase matches the MR so that file reads and edits target the correct code.

## Step 1B: Gather Feedback from Earlier Review Output (Mode B)

When no MR URL was given, look back through the current conversation for output produced by a review agent or skill — for example the `review-code` adversarial swarm's confirmed findings, or any code-review comments generated earlier in the chat. Use the most recent such review if there are several.

Treat each distinct review finding as one feedback "thread":
- **File path and line** — from the finding's location.
- **Comment body** — the finding's summary plus its failure scenario / rationale.
- **Author** — the review source, for display only (e.g. `review-code: correctness`).
- **Replies** — none (local findings have no thread history).
- **Resolved status** — always unresolved.

Collect these into the same numbered structure used in Step 4. Keep findings that target the same file/line as separate items unless they are clearly duplicates. Then go straight to **Step 4** to display them.

In Mode B there is no branch to check out (the changes are already local) and no external thread to post replies to, so **Steps 2c and 7b do not apply** — skip them. Everything else (critical evaluation, applying changes, drafting a reply for the user to reuse) works the same.

## Step 3: Filter and Enumerate Threads (Mode A)

From the raw discussions response, filter to only **unresolved** discussion threads that contain review feedback.

**Detecting resolved status:** The discussion API may not always include an explicit `resolved` field. If present, use it. Otherwise, look for a "resolved all threads" system note and treat threads created **after** that timestamp as unresolved. Threads with reply notes from the MR author saying "agreed", "fixed", etc. followed by a system "resolved all threads" note are likely resolved.

Exclude:
- System notes (status changes, label additions, pipeline results, merge status updates, approvals)
- Already-resolved threads
- Threads authored solely by the MR author with no replies (self-notes)
- Comments from **operational** bots (e.g., `atlantis` — Terraform plan/apply output, merge conflict reports, pipeline status). Do NOT exclude AI code-review bots (e.g., `gemini-mr-reviewer`) — their feedback is real review feedback that should be presented.

For each remaining thread, extract:
- **Thread number** (sequential, starting at 1)
- **Author** of the initial comment
- **File path and line(s)** if it's an inline/diff comment (from the position data)
- **Initial comment body** (full text)
- **Replies** (all subsequent notes in the thread, with author and body)
- **Resolved status**

## Step 4: Display the Threads

Print a numbered summary of all unresolved items. In **Mode A** use the MR heading below; in **Mode B** use a heading like `## Review Feedback on Local Changes` and list the findings gathered in Step 1B (there are no reply counts for local findings — omit the 💬 line).

```
## Unresolved Comment Threads on !IID — "MR Title"

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

**Do NOT use `AskUserQuestion` here.** Simply print the numbered list above and stop. Wait for the user to reply in chat with a number (e.g., `2`) or `all`. This is faster and less intrusive than a modal prompt.

If there are **no unresolved threads** (Mode A) or no findings in the review output (Mode B), tell the user there's nothing to work through and stop.

## Step 5: Load Full Context for the Selected Thread

Once the user picks a thread:

1. **Display the full thread** — show the complete initial comment and all replies with authors, so nothing is truncated.
2. **Show the relevant code** — if it's an inline comment, display the surrounding diff hunk from the MR changes fetched in Step 2c. If the file exists locally, also read the current local version of the file around the referenced lines using the `Read` tool so you can see the latest state (the MR diff may be outdated if commits were pushed since the comment was written).
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

After drafting a reply (for **Reject** or **Modify** decisions), ask the user:

> Would you like me to post this reply to the thread on GitLab? (yes/no)

If the user says **yes**, post the reply using the discussion thread ID saved from Step 3.

Use the `gitlab-api.sh` script to reply directly to the discussion thread:

```bash
~/.claude/scripts/gitlab-api.sh reply-to-thread "<project_id_urlencoded>" <mr_iid> "<discussion_id>" "<reply_text>"
```

The `discussion_id` is the thread ID from the discussions fetched in Step 2. Make sure to properly escape/quote the reply text — pass it as a single shell argument.

After posting, confirm to the user that the reply was posted successfully and show the note ID.

If the user says **no**, skip posting and continue to Step 8.

## Step 8: Offer to Continue

After resolving one thread, offer to address the next unresolved thread. Loop back to Step 5 with the next thread if the user agrees.

## Important Rules

1. **NEVER auto-apply suggestions.** Always analyze and present your assessment first. The whole point of this skill is to think critically, not to blindly accept reviewer feedback.
2. **NEVER post replies to GitLab.** Only draft replies and print them in chat. The user decides whether and when to post them.
3. **NEVER resolve threads.** Thread resolution is the user's action in the GitLab UI after they've posted their reply or pushed changes.
4. **Be honest in your assessment.** If the reviewer is right, say so. If they're wrong, explain why clearly. Don't just side with the MR author.
5. **Consider codebase context.** When evaluating suggestions, look at how similar patterns are handled elsewhere in the codebase using `Grep` and `Read`. Consistency matters.
6. **Keep replies concise.** Drafted replies should be 2-5 sentences. Long replies in code review threads are rarely read.
7. **Use the local codebase.** The user is expected to have the MR branch checked out locally. Use `Read`, `Grep`, and `Glob` to explore the actual code — don't rely solely on the diff from the API.

## Step 9: Self-Improvement

After the session, reflect on how the execution went. Consider:

- Did URL parsing work correctly for the given GitLab instance/path?
- Were there issues fetching discussions (pagination, permissions, empty responses)?
- Did the diff context help or was it stale relative to the local code?
- Were the drafted replies well-received or did the user need to heavily edit them?
- Did the critical analysis add value, or was it obvious the reviewer was correct?

If any issues were encountered, **edit this skill file** (`~/.claude/skills/fix-feedback/SKILL.md`) to add instructions, warnings, or tips that would prevent the same issue next time. Keep edits surgical. Briefly tell the user what was updated and why.
