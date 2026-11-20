# Feedback — Review Feedback Handler

Work through review feedback on the current changes — present each item for selection, then critically evaluate and address the chosen one, debating the suggestion rather than blindly applying it.

This skill runs in one of two **modes**, chosen automatically from the argument:

- **Mode A — Pull request:** `$ARGUMENTS` is a GitHub pull request URL. Fetch the review threads from that PR.
- **Mode B — Feedback already in the conversation:** no argument is given. Pull the feedback from **every unaddressed source already in this conversation** — the `review-code` swarm's confirmed findings, any code review produced in the chat, *and* any PR threads fetched by an earlier Mode A run that the user has not yet worked through. Nothing new is fetched from GitHub; the changes are already local. Findings that are not already on the PR are posted to it as comments (**Step 3b**) before any of them are fixed, so the swarm's work outlives the conversation.

**Parameter:** `$ARGUMENTS` — optionally, the full URL of a GitHub pull request (e.g., `https://github.com/owner/repo/pull/123`). Omit it to use Mode B.

**Flag:** `--autonomous` (default **off**) — anywhere in `$ARGUMENTS`, with or without a URL. It says, in the user's own words, that **they trust the agent's judgment and want to be pulled in only if absolutely necessary.** It composes with Mode A, with Mode B, and with the `in place` / `--here` / `no worktree` escape hatch. See **Autonomous Mode** below for exactly which gates it opens, which it leaves shut, and when it stops anyway.

**Selecting the mode:**
- `$ARGUMENTS` looks like a GitHub PR URL → **Mode A**: do Steps 1, 2, 2b, then continue from Step 3. (`--autonomous` in the same argument string does not change the mode; strip the flag before parsing the URL.)
- `$ARGUMENTS` is empty, or holds only flags → **Mode B**: skip Steps 1, 2, and 2b; start at **Step 1B**, then continue from **Step 3b**.
- `$ARGUMENTS` holds no PR URL **and** the conversation holds neither review output nor an unaddressed PR thread from an earlier Mode A run → tell the user there's nothing to work through (ask them to pass a PR URL or run a review first, e.g. `/review-code`) and stop. Check both before concluding this. **`--autonomous` does not relax this** — there is nothing to be autonomous about.

## Autonomous Mode (`--autonomous`)

Under this flag the user has **pre-authorized this invocation's batch of writes** before it ran. That is a standing grant for this run, and it is a different thing from the agent deciding on its own that writing to GitHub is fine. Every write an autonomous run makes traces back to the flag; nothing here licenses a write of a kind the flag does not name.

**What it relaxes.** Each one is restated inline at its own step, and that inline copy is what governs:

| Gate | Autonomous behaviour |
|---|---|
| Step 2b, item 6 — install dependencies in a fresh worktree | Detect the package manager and install. Do not ask. |
| Step 3b.1 — several open PRs match the branch | Pick the one whose source branch equals `HEAD`. Still ambiguous → escalate. |
| Step 3b.3 — post the unique swarm findings | Post all of them. Do not ask. |
| Step 4 — queue selection | Implicit `all`; work every item in order. |
| Step 6c — Apply / Modify / Reject / Discuss | Step 6b's **Recommendation** is the decision. Agree → Apply, Partially agree → Modify, Disagree → Reject. Discuss is unavailable. |
| Step 7b — post the drafted reply | Post it. |
| Step 7c — resolve the thread | Resolve on Apply and Modify. Never on Reject. |
| Step 8 — continue to the next thread | Continue until the queue is empty. |

**What it does NOT relax.** These stop an autonomous run exactly as they stop an interactive one:

- **Nothing to work through** — no PR URL and no feedback in the conversation (mode selection above).
- **The argument is not a valid GitHub PR URL** (Step 1).
- **An in-place checkout fails because of uncommitted changes** (Step 2b, escape hatch). Never force-checkout, never stash, never discard. This is the only gate here that can destroy work the user has not committed, and it is the whole reason this flag is not simply "yes to everything".
- **No unresolved threads at all** (Step 4).

### Escalating

**Discuss is not available to an autonomous run** — there is nobody on the other side of it. When the code genuinely will not settle a question, that is an escalation, not a conversation.

To escalate: invoke the **`ping` skill** (the `Skill` tool, name `ping`) with one line naming the PR, the thread, and the decision you need. It reaches the user's phone, which is the point — an autonomous run was started precisely because the user is not watching the terminal, so a chat message reaches nobody. If the `ping` skill is unavailable, say so plainly and leave the same one-line request as a chat message instead. Ping **immediately**, not at the end of the run: an escalation held back until the queue drains is a question the user could have answered half an hour earlier.

Escalate when, and only when:

1. **A thread turns on a product or policy decision the code cannot settle** — which behaviour is correct, not which implementation expresses it.
2. **The fix would require changing something outside this repository** — another service, a shared config, an infra repo, a dashboard.
3. **The reviewer has reopened the same thread three times.** A ping-pong cap: three rounds means the disagreement is not going to converge by reply.
4. **Applying the fix would conflict with another unmerged change** the branch has not absorbed.
5. **A test the fix should satisfy fails for a reason you cannot explain.** A fix landing on an unexplained red test is worse than no fix.

Anything not on that list is a decision to make, not a question to ask. After pinging, leave the escalated thread unreplied and unresolved — it is the user's now — and carry on with the queue items that are independent of it; stop the run when none are.

## Step 1: Parse the PR URL (Mode A)

Extract `owner`, `repo`, and `pr_number` from the URL.

For a URL like `https://github.com/acme/my-repo/pull/42`:
- `owner` = `acme`
- `repo` = `my-repo`
- `pr_number` = `42`

If the URL doesn't look like a GitHub PR URL, warn the user and stop. **`--autonomous` does not relax this** — a malformed URL is not a judgment call, and guessing at the owner, repo, or number would aim every later write at the wrong PR.

## Step 2: Load the PR Context (Mode A)

### 2a. Fetch PR metadata, reviews, and diff in parallel

Use `~/.claude/scripts/github-api.sh` for all three. It reads the token from `GITHUB_PERSONAL_ACCESS_TOKEN` and keeps it out of conversation context. Make all three calls **in parallel in a single message**:

```bash
~/.claude/scripts/github-api.sh pr-info <owner> <repo> <pr_number>
~/.claude/scripts/github-api.sh pr-reviews <owner> <repo> <pr_number>
~/.claude/scripts/github-api.sh pr-changes <owner> <repo> <pr_number>
```

Do NOT serialize these calls — run them in parallel.

Each command prints JSON, one object per line — `pr-info` a single object, the other two one object per item. There is no response envelope to unwrap and no `nodes` arrays to walk.

- **`pr-info`** — `title`, `description`, `state`, `author`, `web_url`, `source_branch`, `target_branch`, `number`, `draft`. Step 2b takes `SOURCE_BRANCH` from `source_branch`.
- **`pr-reviews`** — every thread, review and comment flattened into one stream of objects sharing the fields `id`, `type`, `resolved`, `resolvable`, `author`, `body`, `created_at`, `position`, `replies`:
  - `type: "inline"` is a review thread. Its `id` is the GraphQL thread node id — the one Step 7b replies to and Step 7c resolves — `resolved` is the thread's real state, `resolvable` is `true`, and `position` holds `new_path`, `old_path`, `new_line`, `old_line`. `replies` lists the rest of the thread in order, each with `author`, `body`, `created_at`.
  - `type: "review"` is a review summary body, with `review_state` (`APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`). `type: "general"` is a PR-level comment. Both carry `resolved: null`, `resolvable: false`, `position: null` and an `id` prefixed `review-`/`issue-` that is **not** a thread id — there is nothing to reply into or resolve, which is exactly what Step 7b and Step 7c key off.
  - Reviews with an empty body are already dropped.
- **`pr-changes`** — `old_path`, `new_path`, `diff` (the patch hunk), `status`. It pages to the end, so this is every changed file, not the first 100.

The script does the flattening, the pagination and the empty-review filtering. Do not redo any of that.

## Step 2b: Set Up the PR Branch (Mode A)

From the `pr-info` output, extract the **source branch name** (`source_branch` field) as `SOURCE_BRANCH`.

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
   - **Under `--autonomous`: just install it.** Detect the package manager the same way and run its install command without asking. The install is confined to the worktree, is undone by deleting it, and nothing downstream works without it — there is no judgment here worth a round trip.

Worktrees are cleaned up manually — remove with `git worktree remove <path>` once the PR is merged. See `WORKTREES.md` in the Demeter repo for the full guide.

**In-place checkout (escape hatch):** after `git fetch origin <SOURCE_BRANCH>`, run `git checkout <SOURCE_BRANCH>` in the current tree. If checkout fails due to uncommitted changes, warn the user and ask how to proceed (stash, commit, or abort) — do NOT force-checkout or discard changes. Then `git pull --ff-only`.

**`--autonomous` does not relax the dirty-tree stop.** An autonomous run that hits uncommitted changes here does exactly what an interactive one does: it stops. It never force-checks-out, never stashes, never discards, and never "saves" the work to a branch of its own invention. This is the one failure in the whole skill that can destroy work the user never committed, and it is why the flag is not "yes to everything" — ping the user (Autonomous Mode → Escalating) and wait.

This ensures the local codebase matches the PR so that file reads and edits target the correct code.

## Step 1B: Gather Feedback from the Conversation (Mode B)

When no PR URL was given, sweep the whole conversation for feedback that is **still unaddressed**, and gather ALL of it into one queue. There are two kinds and you must collect both:

1. **Review-agent output** — the `review-code` adversarial swarm's confirmed findings, or any code review produced in the chat. Use the most recent such review if there are several.
2. **PR threads already fetched earlier in this conversation** — if an earlier Mode A run listed unresolved threads and the user never picked one, those threads are still open and belong in this queue. Do **not** re-fetch them; reuse what is already in context, thread IDs included, so replies can still be posted in Step 7b.

**Never present one source while silently dropping the other.** The user invoking this skill with no argument is saying "work through my feedback", not "work through one of the two piles you happen to be holding" — they should not have to name where a finding came from to get it fixed. A queue that omits live PR threads costs them a round trip to ask for the obvious, and risks the omitted threads being forgotten entirely. If an earlier Mode A run is in context, say in one line which of its threads are still open and fold them in.

This matters most when the two sources **overlap**: a bot comment and a swarm finding about the same function want one fix and one test, not two. Say so when you see it, and order the queue so dependent items are adjacent.

When Mode B carries PR threads, Steps 2b and 7b are **not** uniformly skipped — see the note after the field list.

Treat each distinct review finding as one feedback "thread":
- **File path and line** — from the finding's location.
- **Comment body** — the finding's summary plus its failure scenario / rationale.
- **Author** — the review source, for display only (e.g. `review-code: correctness`, or the bot/human handle for a carried-over PR thread).
- **Replies** — none for a review-agent finding; a carried-over PR thread keeps whatever reply history was fetched.
- **Thread ID** — only for a carried-over PR thread: the GraphQL node ID needed to reply. A review-agent finding has none **until Step 3b posts it to the PR**, and that absence is what tells Step 3b which items to post and Step 7b which treatment each one gets.
- **Resolved status** — always unresolved.

Collect these into the same numbered structure used in Step 4. Keep findings that target the same file/line as separate items unless they are clearly duplicates. Then go to **Step 3b** to persist the ones the PR does not already carry, and on to **Step 4** to display them.

In Mode B there is no branch to check out — the changes are already local — so **Step 2b never applies**.

**Step 7b applies per item, not per mode.** An item that came from a review agent and was not posted in Step 3b has no external thread: present its reply in chat and stop. One that Step 3b did post now carries a thread ID and takes the full treatment. An item that came from a PR thread carried over from an earlier Mode A run still has a live thread ID, so it takes the full Step 7b treatment — offer to post, and post only on an explicit yes (under `--autonomous`, post it without the offer; see Step 7b). Deciding this once for the whole run is the bug: it either strands PR replies in the chat or offers to post a swarm finding that has nowhere to go.

**Record the commit state before you edit anything.** Run `git log --oneline -3` and `git status --porcelain` and note which of the reviewed changes are committed. **Check whether the branch is pushed in the same breath** — `git rev-list --left-right --count origin/<branch>...HEAD` — and do it BEFORE you recommend anything, not after the user accepts. A finding about a name, a message, or a typo invites "amend the commit too", and that recommendation is only safe on unpublished work; offering it and then withdrawing it costs the user a decision they already made. When the branch is pushed, the fix is a follow-up commit, and a wrong commit subject that GitHub has not yet turned into a PR title is a field the user edits at PR-creation time rather than anything to force-push over. The user may have committed between turns — the reviewed work then lives in `HEAD` and a later `git status` shows those files clean, which reads exactly like an edit that silently failed to apply. Establish the baseline up front so you don't misdiagnose it, and diff against the branch's merge-base rather than the working tree when you need to see the whole change.

## Step 3: Filter and Enumerate Threads (Mode A)

`pr-reviews` emits one object per item, already carrying `type` (`inline`, `review`, `general`), `author`, `body`, `resolved`, `position` and `replies` — so this step is a filter over those lines, not a traversal.

**Filter out:**
- Items with `resolved: true` (an inline thread already dealt with). `resolved: null` means "not a thread", not "unresolved" — do not filter those out on this rule.
- Empty bodies (body is blank or whitespace only)
- Bot/automation comments (e.g., from `github-actions`, `dependabot`, `atlantis`). Do NOT exclude AI code-review bots — their feedback is real review feedback.
- Items with `type: "review"` whose `review_state` is `APPROVED` and whose body says nothing substantive

Number what survives sequentially from 1. Everything Step 4 prints is already on the object — `type`, `author`, `body`, `replies`, `resolved`, and `position.new_path` / `position.new_line` for the file and line of an inline thread. Keep each item's `id` with it: for an `inline` item that is the thread id Step 7b and Step 7c need.

## Step 3b: Persist Unique Swarm Findings to the PR

A swarm finding exists only in this conversation. One the user accepts turns into a commit; one they reject or defer leaves **no trace at all** once the session ends, and the next reviewer re-derives it from scratch. So before working through the queue, put every unique finding onto the PR as its own comment, anchored to the code it is about.

This step runs **once**, after the queue is assembled (Mode A: after Step 3; Mode B: after Step 1B) and **before** Step 4 lists it. It applies only to queue items with **no thread ID** — the review-agent findings. Items that came from the PR are already on the PR; never re-post them.

### 3b.1 Find the PR to post to

- **Mode A** — the PR from the URL. Already known, nothing to look up.
- **Mode B carrying PR threads** from an earlier Mode A run — that PR. Reuse the owner, repo, and number already in context.
- **Otherwise** — look it up from the branch:
  ```bash
  ~/.claude/scripts/github-api.sh pr-for-branch - - -
  ```
  The `-` arguments mean "derive it": owner and repo from the `origin` remote, the branch from `HEAD`. One open PR → that is the target. Several → list them and ask which; **under `--autonomous`, do not ask** — pick the one whose `source_branch` equals the current `HEAD` branch, and if that still leaves more than one candidate, escalate (Autonomous Mode → Escalating) rather than guessing, because posting a batch of findings onto the wrong PR is not something a later run can tidy up. **None → say so in one line** (`no open PR for <branch>, so these findings stay in this conversation`) and go straight to Step 4. Do not offer to open the PR, and do not stall the fixes on it — re-running this skill once the PR exists will post them.

**Anchors attach to the pushed head.** Check `git rev-list --left-right --count origin/<branch>...HEAD` before posting: if there are local-only commits, a finding about a line that exists only locally cannot anchor and will land as a file-level or general comment. Say that in the same breath as the count, so the user can push first if they want clean anchors.

### 3b.2 Drop findings the PR already makes

Fetch the PR's existing threads unless this run already has them:
```bash
~/.claude/scripts/github-api.sh pr-reviews <owner> <repo> <pr_number>
```
Do this even when the conversation seems to hold the bot's comments — "what is in the chat" is not the same as "what is on the PR", and a duplicate posted next to a review bot's identical point makes the PR worse, not more durable.

Compare each review-agent finding against:
- threads already on the PR, whoever wrote them — a review bot or a human;
- comments a **previous run of this skill** posted — they carry the header from 3b.4, which is what makes them recognisable.

**Judge by substance, not wording.** The same defect in the same code is a duplicate even when one calls it a nil dereference and the other a missing guard. The same file with a different defect is not. When it is genuinely unclear, post it and name the thread it resembles in the summary — a reviewer resolves a near-duplicate in seconds, while a dropped finding costs them the bug.

### 3b.3 Show what will be posted and ask once

Print the list and wait for a chat reply. **Do NOT use `AskUserQuestion`.**

```
### Posting 3 of 5 findings to #965 — 2 are already on the PR

**1.** `src/api/handler.go:118` — nil map write when `opts` is empty   [review-code: correctness]
**2.** `src/api/handler.go:204` — retry loop has no backoff            [review-code: reliability]
**3.** `tests/test_api.py` (file-level) — the new branch is untested   [review-code: tests]

Already covered: the `:118` bounds check (@copilot-review, thread 2) and the logging nit (thread 4).

Post these 3 as PR comments? (yes / no / a subset like "1,3")
```

One approval covers the whole batch. On **no**, post nothing, say in one line that the findings stay in this conversation, and continue to Step 4 — never re-ask per finding.

**Under `--autonomous`, post them all and do not ask.** Still print the list above, unchanged — an autonomous run's transcript is the only audit trail it leaves, and a batch posted silently is one the user cannot check afterwards. Then go straight to 3b.4. Asking here is precisely the gate the flag exists to open: the user pre-authorized the batch when they invoked the skill.

### 3b.4 Post each approved finding

One comment per finding — a thread is resolved as a unit, so batching several findings into one comment makes them unresolvable. The body is read from stdin, so use a heredoc:

```bash
~/.claude/scripts/github-api.sh create-diff-comment <owner> <repo> <pr_number> "<file_path>" <line> << 'ENDOFBODY'
🤖 **review-code — <dimension>**

<one-sentence statement of the defect>

**Failure scenario:** <concrete inputs or state → wrong output or crash>

<optional: the direction a fix would take, 1-2 sentences>
ENDOFBODY
```

- `<line>` is the line in the file **as it stands now**, not the line the review quoted if the file has moved since. Pass `-` for a file-level comment.
- Keep the `🤖 **review-code — <dimension>**` header exactly as written. It is how 3b.2 recognises this skill's own comments on a later run.
- The script anchors to the diff when that line is inside it; when GitHub rejects the anchor (a line outside the diff, an unpushed commit) it retries as a file-level comment and finally as a general PR comment prefixed with `` `path:line` ``. It reports which in the `anchored` and `fallback_reason` fields. **Report the fallback to the user**; do not describe a comment as anchored to the code when it landed as a general comment.
- Do not write the finding into the source as a comment while doing this. The PR thread is the record.

### 3b.5 Record the thread IDs

The REST call returns a comment id, **not** the GraphQL thread ID that Step 7b needs to reply. After the batch is posted, re-run `pr-reviews <owner> <repo> <pr_number>` once and match each new thread to its finding by the `🤖 review-code` header, capturing the thread `id`. One extra call for the whole batch.

With the thread ID attached, the item behaves like any other PR thread: Step 4 shows it with its thread link, and **Step 7b now applies to it** — a reject or modify reply goes back into the thread this step opened, which is what leaves the finding, the decision, and the reasoning in one place for whoever reads the PR later.

## Step 4: Display the Threads

Print a numbered summary of all unresolved items. In **Mode A** use the PR heading below; in **Mode B** use a heading like `## Review Feedback on Local Changes` and list everything gathered in Step 1B (omit the 💬 line for review-agent findings, which have no thread history).

**One numbered list, whatever the sources.** When a Mode B queue mixes review-agent findings with carried-over PR threads, do not split it into two lists — the user picks by number and should not have to think about provenance to do it. Tag each item's source inline instead (`— @dependabot, #965` vs `— review-code: tests`), order by what a reviewer would fix together rather than by source, and note any overlap in one line under the list. Splitting the list re-creates exactly the problem this mode exists to avoid.

**Tag the items Step 3b posted with their thread link.** A finding that is now a live PR thread reads `— review-code: correctness, #965 thread` rather than as a chat-only finding. That is the user's confirmation it was persisted, and it tells them a reply to it will land on the PR rather than in the transcript.

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

**Under `--autonomous`, treat the selection as an implicit `all`.** Print the same numbered list — it is what makes the rest of the run readable afterwards — then start at item 1 and work through every item in order without waiting for anything. Do not re-order by how easy the items look; the order you built in Step 1B/Step 3 already groups the ones a reviewer would fix together.

If there are **no unresolved threads** (Mode A), or neither a review output nor a carried-over PR thread anywhere in the conversation (Mode B), tell the user there's nothing to work through and stop. In Mode B, say which sources you checked — "no review output and no unaddressed PR threads in this conversation" — so an empty queue reads as a search that came up empty rather than a source you forgot to look at. **`--autonomous` does not relax this**: an empty queue ends the run, and there is nothing to ping about.

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

**Under `--autonomous`, do not print these options and do not wait.** Step 6b has already done the work: it produced an **Assessment** and a **Recommendation**. Under this flag the Recommendation *is* the decision, and the mapping is fixed:

| Step 6b Assessment | Autonomous decision |
|---|---|
| **Agree** | **Apply** |
| **Partially agree** | **Modify** |
| **Disagree** | **Reject** |

Still print the whole Step 6b block before acting. The reasoning is what the user reads later to judge whether the run was any good, and a decision that appears without it is indistinguishable from guessing.

**"Discuss" is not available to an autonomous run.** There is nobody to discuss with. If you cannot reach one of the three verdicts from the code itself, that is an **escalation**, not a discussion — ping the user (Autonomous Mode → Escalating) with the specific question, and leave the thread unreplied and unresolved. Do not quietly downgrade an unsettled question into a **Reject** to keep the queue moving: a Reject is an assertion that the reviewer is wrong, and asserting it because you could not tell is worse than asking.

## Step 7: Execute the Decision

### If applying changes (fully or with modifications):

1. Make the code changes using the `Edit` tool. **Add no comments while doing it** — not the reviewer's point, not why the code now looks this way; that goes in the drafted reply, not the source.
   - **When the change is to a test, re-prove the test.** A green run says nothing about whether an assertion still fires. Temporarily reintroduce the defect the test guards, confirm it fails, then restore — and if the finding was that the assertion was weak or vacuous, also demonstrate the assertion now executes (flip the guard to its negation and read the real count out of the failure message). Report both results; "tests pass" alone is the weakest possible evidence for a change whose entire purpose is making a test stronger.
   - **Never `cd` inside a Bash call.** The working directory persists between calls, so a `cd sub/dir && …` leaves every later command resolving paths against that subdirectory, and the next one fails with a bare "No such file or directory" that reads like a missing file. Use repo-relative paths from where the session already is.
2. Show the user what was changed.
3. **Run the repo's own checker for whatever you touched** before reporting done — a docs change that adds cross-page links can break an anchor checker that CI runs. Prefer invoking the underlying tool directly: `pnpm`/`npx` are often not on `PATH` in this shell, while `mise exec -- node …` is.
   - **When the change defines what runs inside a container, run it in that image.** A validator checks the manifest, not the thing it launches: `terraform validate` passes happily on a CronJob whose entrypoint does not exist in its base image, and a script that works on your machine proves nothing about an image you have not looked inside. This bit on a job written against `google/cloud-sdk:slim`, which ships neither `python` nor `kubectl` — the job could never have started, the review comment was about the slow install rather than the missing interpreter, and local testing hid it completely. Execute the real entrypoint in the real image, as the real ServiceAccount, and exercise the failure path too: an alerting job that only ever runs clean has demonstrated nothing about whether it can alert.
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

### Step 7b: Offer to Post the Reply (any item with a thread ID)

**This step is decided per item, by whether the item carries a thread ID** (Step 1B records it). A review-agent finding has none: there is nothing to post to, so present the drafted reply in chat for the user to reuse and move on. A PR thread — reached through Mode A, or carried into a Mode B queue from an earlier Mode A run — does have one, and gets the full treatment below regardless of which mode is running.

After drafting a reply (for reject or modify decisions), ask the user:

> Would you like me to post this reply to the thread on GitHub? (yes/no)

If the user says yes:

1. Use the **thread ID** for the selected thread — the `id` field on its `pr-reviews` item, which is a thread id only when that item's `type` is `inline`.
2. Post the reply using the `github-api.sh` script, piping the body via heredoc to stdin to avoid shell encoding issues:
   ```bash
   ~/.claude/scripts/github-api.sh reply-to-thread '<thread_id>' << 'ENDOFBODY'
   <reply text here>
   ENDOFBODY
   ```
   - The `<thread_id>` is that item's `id`, the GraphQL node id of the thread.
   - **Always** use a heredoc piped to stdin for the body — never pass it as a CLI argument or use temp files with redirects.
3. Confirm to the user that the reply was posted successfully, or report any errors.

If the user says no, continue to Step 8 as normal.

**Note:** This only applies to **inline** threads (which have a thread ID). For `general` or `review` type comments, the `reply-to-thread` command won't work — in those cases, skip this step and just present the drafted reply for the user to copy.

#### Under `--autonomous`: post it

Do not ask. Post the drafted reply using exactly the command above — `reply-to-thread` with its body piped in through a quoted heredoc, which is already the only sanctioned form on this profile:

```bash
~/.claude/scripts/github-api.sh reply-to-thread '<thread_id>' << 'ENDOFBODY'
<reply text here>
ENDOFBODY
```

`github-api.sh reply-to-thread` takes the body as an optional second argument and **reads stdin when that argument is omitted**, so the quoted heredoc passes the reply through byte for byte — apostrophes, backticks, `$`, all of it. Write the reply as it should read and change nothing for the shell's benefit. That matters more here than interactively: nobody is proofreading an autonomous draft, so a silent rewording would never be caught.

An item with **no thread ID** — a review-agent finding Step 3b could not post, or a `general`/`review` comment — still has nowhere to reply. Print the draft in the transcript and move on; that is not an escalation.

### Step 7c: Resolve the Thread (`--autonomous` only)

**Interactive runs never resolve a thread** — Important Rule 3 is absolute there, and this step does not exist for them. Under `--autonomous` only, resolve a thread once the outcome has fully landed:

- **Apply** — the edit is made, the repo's own checker (Step 7, item 3) passed on it, and any drafted reply is posted → **resolve**.
- **Modify** — the edit is made, the checker passed, and the reply explaining the partial application is posted → **resolve**.
- **Reject** — **never resolve.** No code changed; the only artefact is an argument that the reviewer is wrong, and the reviewer is the one entitled to decide whether it holds. Resolving it would collapse the thread over the reasoning the human most needs to read, and close an argument the agent is one side of.
- **Escalated** — do not resolve and do not reply. The thread belongs to the user now.

Resolve through `~/.claude/scripts/github-api.sh`, the same script Step 3b and Step 7b write through. Never shell out to a third-party CLI for this:

```bash
~/.claude/scripts/github-api.sh resolve-thread <owner> <repo> <thread_id>
```

It prints `{"id": "<thread_id>", "resolved": true}` and exits 0, or `{"error": "<GitHub's own message>"}` and exits non-zero. **Read what comes back** — confirm `resolved: true` and report any thread that did not resolve, rather than assuming it did. `unresolve-thread` is the counterpart, taking the same three arguments. `<owner>` and `<repo>` are not needed by the underlying mutation — a thread node id is global — and are taken only so this command is shaped like every other one in the script; pass them anyway.

**`<thread_id>` must be the node id of a review *thread*.** That is the `id` of a `pr-reviews` item whose `type` is `inline`, the same id Step 7b replies with. It is **not** what `create-diff-comment` returns: that emits `comment_id` (a REST comment id) and `node_id` (the node id of the *comment*), and neither one resolves. So for a finding this run posted in Step 3b, use the thread id **Step 3b.5 captured by re-running `pr-reviews`** — and if you do not have it, re-run `pr-reviews <owner> <repo> <pr_number>` and match on the `🤖 review-code` header before resolving. Passing a comment id fails with `Could not resolve to a node with the global id of '…'`, which reads like a thread that has vanished rather than the wrong kind of id, so check the id before you believe the error.

The mutation only works on **inline** review threads; a `general` or `review` comment has nothing to resolve, which is not a failure. A thread that is already resolved succeeds unchanged. The other realistic failure is a token without write access to the repository — report GitHub's message as printed and move on, rather than retrying.

Resolve only *after* the checker has run. A resolved thread is a claim that the point is dealt with, and making that claim about a fix you have not verified is the same mistake as reporting "tests pass" without looking.

**This skill still does not commit and does not push** (Important Rule 2), under this flag or any other. So an autonomous run resolves threads whose fixes are sitting in the working tree and are not yet on the PR. Say that plainly in the closing summary: until the caller commits and pushes, the reviewer sees resolved threads whose code has not arrived.

## Step 8: Offer to Continue

After resolving one thread, offer to address the next unresolved thread. Loop back to Step 5 with the next thread if the user agrees.

**Under `--autonomous`, do not offer — continue.** Move straight to the next item in the Step 4 queue and keep going until it is empty. Then stop and write one closing summary: every thread, the decision taken on it, whether a reply was posted, whether it was resolved, anything escalated, and the reminder that the fixes are uncommitted and unpushed. That summary is the whole report the user gets, so it is worth more than the running commentary was.

## Important Rules

1. **NEVER auto-apply suggestions — `--autonomous` is the single sanctioned exception.** By default, always analyze and present your assessment first and let the user decide; the whole point of this skill is to think critically, not to blindly accept reviewer feedback. The flag does not suspend the thinking, it only removes the user from the loop: Step 6b's assessment and Recommendation are still produced in full and still printed, and under the flag that Recommendation becomes the decision instead of a proposal awaiting approval. An autonomous run that applies a reviewer's suggestion without first arguing it through has broken this rule exactly as badly as an interactive one would.
2. **Never write to GitHub unasked — `--autonomous` is the single sanctioned exception.** Interactively there are exactly two writes and both are gated on an explicit yes in chat: Step 3b posts unique swarm findings as new comments (one approval for the batch), and Step 7b posts a drafted reply into a thread (one approval per reply). Under the flag the user **pre-authorized the batch** when they invoked the skill — a grant they gave, which is a different thing from the agent concluding on its own that a write is fine. The flag opens Step 3b, Step 7b, and the resolutions in Step 7c, and **nothing else**: never edit the PR description, never post a reply you have not written into the transcript, and — autonomous or not — **never commit and never push**. This skill fixes and replies; committing and pushing belong to whoever called it. That boundary erodes silently, so treat any urge to "just commit it so the thread can be resolved" as the bug it is.
3. **NEVER resolve threads — except under `--autonomous`, and never on a Reject.** Interactively, thread resolution is the user's action in the GitHub UI after they've posted their reply or pushed changes, and this skill never performs it. Under `--autonomous`, Step 7c resolves a thread once the fix is in place and the reply is posted — the **Apply** and **Modify** outcomes only. A **Reject** stays open, always: nothing changed in the code, and the human reviewer has to see the disagreement and decide whether it stands. An escalated thread stays open too.
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
- Did Step 3b's duplicate detection hold up — anything posted that a review bot had already said, or dropped that it had not?
- Did the posted comments anchor to the right lines, or did they fall back to file-level or general comments? If a fallback was avoidable, record why.
- If the run was autonomous: did anything stop it that is not on the escalation list, or pass unchallenged that should have stopped it? Did the Step 6b → Step 6c mapping produce a decision the user later overturned, and if so, what in the assessment should have flagged it?

If any issues were encountered, **edit this skill file** (`~/.claude/skills/fix-feedback/SKILL.md`) to add instructions, warnings, or tips that would prevent the same issue next time. Keep edits surgical. Briefly tell the user what was updated and why.