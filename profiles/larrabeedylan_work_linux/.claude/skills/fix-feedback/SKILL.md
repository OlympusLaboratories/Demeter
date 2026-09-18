# Feedback — Review Feedback Handler

Work through review feedback on the current changes — present each item for selection, then critically evaluate and address the chosen one, debating the suggestion rather than blindly applying it.

This skill runs in one of two **modes**, chosen automatically from the argument:

- **Mode A — Merge request:** `$ARGUMENTS` is a GitLab merge request URL. Fetch the review discussion threads from that MR.
- **Mode B — Feedback already in the conversation:** no argument is given. Pull the feedback from **every unaddressed source already in this conversation** — the `review-code` swarm's confirmed findings, any code review produced in the chat, *and* any MR threads fetched by an earlier Mode A run that the user has not yet worked through. Nothing new is fetched from GitLab; the changes are already local.

**Parameter:** `$ARGUMENTS` — optionally, the full URL of a GitLab merge request (e.g., `https://gitlab.com/group/project/-/merge_requests/123`). Omit it to use Mode B.

**Selecting the mode:**
- `$ARGUMENTS` looks like a GitLab MR URL → **Mode A**: do Steps 1, 2, 2c, then continue from Step 3.
- `$ARGUMENTS` is empty → **Mode B**: skip Steps 1, 2, and 2c; start at **Step 1B**, then continue from Step 4.
- `$ARGUMENTS` is empty **and** the conversation holds neither review output nor an unaddressed MR thread from an earlier Mode A run → tell the user there's nothing to work through (ask them to pass an MR URL or run a review first, e.g. `/review-code`) and stop. Check both before concluding this.

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

## Step 2c: Set Up the MR Branch (Mode A)

From the MR metadata (fetched in Step 2), extract the **source branch name** (`SOURCE_BRANCH`).

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

Worktrees are cleaned up manually — remove with `git worktree remove <path>` once the MR is merged. See `WORKTREES.md` in the Demeter repo for the full guide.

**In-place checkout (escape hatch):** after `git fetch origin <SOURCE_BRANCH>`, run `git checkout <SOURCE_BRANCH>` in the current tree. If checkout fails due to uncommitted changes, warn the user and ask how to proceed (stash, commit, or abort) — do NOT force-checkout or discard changes. Then `git pull --ff-only`.

This ensures the local codebase matches the MR so that file reads and edits target the correct code.

## Step 1B: Gather Feedback from the Conversation (Mode B)

When no MR URL was given, sweep the whole conversation for feedback that is **still unaddressed**, and gather ALL of it into one queue. There are two kinds and you must collect both:

1. **Review-agent output** — the `review-code` adversarial swarm's confirmed findings, or any code review produced in the chat. Use the most recent such review if there are several.
2. **MR threads already fetched earlier in this conversation** — if an earlier Mode A run listed unresolved threads and the user never picked one, those threads are still open and belong in this queue. Do **not** re-fetch them; reuse what is already in context, discussion IDs included, so replies can still be posted in Step 7b.

**Never present one source while silently dropping the other.** The user invoking this skill with no argument is saying "work through my feedback", not "work through one of the two piles you happen to be holding" — they should not have to name where a finding came from to get it fixed. A queue that omits live MR threads costs them a round trip to ask for the obvious, and risks the omitted threads being forgotten entirely. If an earlier Mode A run is in context, say in one line which of its threads are still open and fold them in.

This matters most when the two sources **overlap**: a bot comment and a swarm finding about the same function want one fix and one test, not two. Say so when you see it, and order the queue so dependent items are adjacent.

When Mode B carries MR threads, Steps 2c and 7b are **not** uniformly skipped — see the note after the field list.

Treat each distinct review finding as one feedback "thread":
- **File path and line** — from the finding's location.
- **Comment body** — the finding's summary plus its failure scenario / rationale.
- **Author** — the review source, for display only (e.g. `review-code: correctness`, or the bot/human handle for a carried-over MR thread).
- **Replies** — none for a review-agent finding; a carried-over MR thread keeps whatever reply history was fetched.
- **Discussion ID** — only for a carried-over MR thread, plus the project path and MR iid needed to reply. A review-agent finding has none, and that absence is what tells Step 7b which treatment the item gets.
- **Resolved status** — always unresolved.

Collect these into the same numbered structure used in Step 4. Keep findings that target the same file/line as separate items unless they are clearly duplicates. Then go straight to **Step 4** to display them.

In Mode B there is no branch to check out — the changes are already local — so **Step 2c never applies**.

**Step 7b applies per item, not per mode.** An item that came from a review agent has no external thread: present its reply in chat and stop. An item that came from an MR thread carried over from an earlier Mode A run still has a live discussion ID, so it takes the full Step 7b treatment — offer to post, and post only on an explicit yes. Deciding this once for the whole run is the bug: it either strands MR replies in the chat or offers to post a swarm finding that has nowhere to go.

**Record the commit state before you edit anything.** Run `git log --oneline -3` and `git status --porcelain` and note which of the reviewed changes are committed. **Check whether the branch is pushed in the same breath** — `git rev-list --left-right --count origin/<branch>...HEAD` — and do it BEFORE you recommend anything, not after the user accepts. A finding about a name, a message, or a typo invites "amend the commit too", and that recommendation is only safe on unpublished work; offering it and then withdrawing it costs the user a decision they already made. When the branch is pushed, the fix is a follow-up commit, and a wrong commit subject that GitLab has not yet turned into an MR title is a field the user edits at MR-creation time rather than anything to force-push over. The user may have committed between turns — the reviewed work then lives in `HEAD` and a later `git status` shows those files clean, which reads exactly like an edit that silently failed to apply. Establish the baseline up front so you don't misdiagnose it, and diff against the branch's merge-base rather than the working tree when you need to see the whole change.

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

Print a numbered summary of all unresolved items. In **Mode A** use the MR heading below; in **Mode B** use a heading like `## Review Feedback on Local Changes` and list everything gathered in Step 1B (omit the 💬 line for review-agent findings, which have no thread history).

**One numbered list, whatever the sources.** When a Mode B queue mixes review-agent findings with carried-over MR threads, do not split it into two lists — the user picks by number and should not have to think about provenance to do it. Tag each item's source inline instead (`— @griddy-bot, !965` vs `— review-code: tests`), order by what a reviewer would fix together rather than by source, and note any overlap in one line under the list. Splitting the list re-creates exactly the problem this mode exists to avoid.

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

If there are **no unresolved threads** (Mode A), or neither a review output nor a carried-over MR thread anywhere in the conversation (Mode B), tell the user there's nothing to work through and stop. In Mode B, say which sources you checked — "no review output and no unaddressed MR threads in this conversation" — so an empty queue reads as a search that came up empty rather than a source you forgot to look at.

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
- **Does it depend on a repo you cannot reach?** A worktree-isolated session refuses `git -C <other-repo>`, so a finding whose truth lives in a sibling checkout cannot be settled from here. Say so explicitly and convert it into a named pre-merge check rather than leaving it as an open question or softening the code to route around the gap — the docs or code are usually right and the verification is what is missing.

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

1. Make the code changes using `Edit` tool. **Add no comments while doing it** — not the reviewer's point, not why the code now looks this way; that goes in the drafted reply, not the source.
   - **When the change is to a test, re-prove the test.** A green run says nothing about whether an assertion still fires. Temporarily reintroduce the defect the test guards, confirm it fails, then restore — and if the finding was that the assertion was weak or vacuous, also demonstrate the assertion now executes (flip the guard to its negation and read the real count out of the failure message). Report both results; "tests pass" alone is the weakest possible evidence for a change whose entire purpose is making a test stronger.
   - **Never `cd` inside a Bash call.** The working directory persists between calls, so a `cd sub/dir && …` leaves every later command resolving paths against that subdirectory, and the next one fails with a bare "No such file or directory" that reads like a missing file. Use repo-relative paths from where the session already is.
2. Show the user what was changed.
3. **Run the repo's own checker for whatever you touched** before reporting done — a docs change that adds cross-page links can break an anchor checker that CI runs (in this repo, `node apps/portal/scripts/check-docs-links.mjs`). Prefer invoking the underlying tool directly: `pnpm`/`npx` are often not on `PATH` in this shell, while `mise exec -- node …` is.
4. If the change was modified from the original suggestion, draft a reply for the comment thread explaining what was done differently and why.

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

**This step is decided per item, by whether the item carries a discussion ID** (Step 1B records it). A review-agent finding has none: there is nothing to post to, so present the drafted reply in chat for the user to reuse and move on. An MR thread — reached through Mode A, or carried into a Mode B queue from an earlier Mode A run — does have one, and gets the full treatment below regardless of which mode is running.

After drafting a reply (for **Reject** or **Modify** decisions), ask the user:

> Would you like me to post this reply to the thread on GitLab? (yes/no)

If the user says **yes**, post the reply using the discussion thread ID saved from Step 3.

Use the `gitlab-api.sh` script to reply directly to the discussion thread:

```bash
~/.claude/scripts/gitlab-api.sh reply-to-thread "<project_id_urlencoded>" <mr_iid> "<discussion_id>" "<reply_text>"
```

The `discussion_id` is the thread ID from the discussions fetched in Step 2. Make sure to properly escape/quote the reply text — pass it as a single shell argument.

**Quote the reply in SINGLE quotes, and write the draft so it contains no apostrophe.**
A good reply names identifiers, so it is full of backticks — inside double quotes the
shell runs everything between them as a command substitution, which mangles the reply or
executes something. Single quotes are the only safe wrapper, and they cannot contain an
apostrophe, so decide that at drafting time: prefer "you would" to "you'd", "it is" to
"it's". If the drafted text already has one, reword it rather than escaping, and say so
when you confirm the post — the user approved an exact string and is entitled to know
the posted one differs, however trivially.

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
8. **No comments in the code.** When you apply a change, add no explanatory comment, docstring, or note recording what the reviewer asked for — a reviewer reading the next diff does not need the last review narrated back at them. That belongs in the drafted reply. Machine-read directives (linter suppressions, build pragmas, a doc-comment CI requires) are program input, not commentary, and stay allowed.

## Step 9: Self-Improvement

After the session, reflect on how the execution went. Consider:

- Did URL parsing work correctly for the given GitLab instance/path?
- Were there issues fetching discussions (pagination, permissions, empty responses)?
- Did the diff context help or was it stale relative to the local code?
- Were the drafted replies well-received or did the user need to heavily edit them?
- Did the critical analysis add value, or was it obvious the reviewer was correct?

If any issues were encountered, **edit this skill file** (`~/.claude/skills/fix-feedback/SKILL.md`) to add instructions, warnings, or tips that would prevent the same issue next time. Keep edits surgical. Briefly tell the user what was updated and why.
