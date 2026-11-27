# Feedback — Review Feedback Handler

Work through review feedback on the current changes — present each item for selection, then critically evaluate and address the chosen one, debating the suggestion rather than blindly applying it.

This skill runs in one of two **modes**, chosen automatically from the argument:

- **Mode A — Merge request:** `$ARGUMENTS` is a GitLab merge request URL. Fetch the review discussion threads from that MR.
- **Mode B — Feedback already in the conversation:** no argument is given. Pull the feedback from **every unaddressed source already in this conversation** — the `review-code` swarm's confirmed findings, any code review produced in the chat, *and* any MR threads fetched by an earlier Mode A run that the user has not yet worked through. Nothing new is fetched from GitLab; the changes are already local. Findings that are not already on the MR are posted to it as comments (**Step 3b**) before any of them are fixed, so the swarm's work outlives the conversation.

**Parameter:** `$ARGUMENTS` — optionally, the full URL of a GitLab merge request (e.g., `https://gitlab.com/group/project/-/merge_requests/123`), plus optional flags. Omit the URL to use Mode B.

| Argument | Default | Effect |
|---|---|---|
| A GitLab merge request URL | — | Selects **Mode A**. Omit it for Mode B. |
| `--autonomous [true\|false]` | **`false`** | The user trusts the agent's judgment and wants to be pulled in only if absolutely necessary. Bare `--autonomous` means `true`. |
| `in place`, `--here`, `no worktree` | off | Work in the current checkout instead of cutting a worktree for the branch under review (**Step 2c**). Matched case-insensitively. |

`--autonomous` composes with Mode A, with Mode B, and with the in-place tokens. See **Autonomous Mode** below for exactly which gates it opens, which it leaves shut, and when it stops anyway.

**This skill has no `--branch` flag, and that is not an inconsistency with `fix-linear` and `fix-freeform`.** Those two decide *which branch the work lands on*, which is a question only an unstarted change has. Here the branch is already chosen — it is whatever the merge request under review was opened from — so the only question left is whether to check it out in a worktree or in place, which is what the tokens above answer.

**Selecting the mode:**
- `$ARGUMENTS` looks like a GitLab MR URL → **Mode A**: do Steps 1, 2, 2c, then continue from Step 3. (`--autonomous` in the same argument string does not change the mode; strip the flag before parsing the URL.)
- `$ARGUMENTS` is empty, or holds only flags → **Mode B**: skip Steps 1, 2, and 2c; start at **Step 1B**, then continue from **Step 3b**.
- `$ARGUMENTS` holds no MR URL **and** the conversation holds neither review output nor an unaddressed MR thread from an earlier Mode A run → tell the user there's nothing to work through (ask them to pass an MR URL or run a review first, e.g. `/review-code`) and stop. Check both before concluding this. **`--autonomous` does not relax this** — there is nothing to be autonomous about.

## Autonomous Mode (`--autonomous`)

Under this flag the user has **pre-authorized this invocation's batch of writes** before it ran. That is a standing grant for this run, and it is a different thing from the agent deciding on its own that writing to GitLab is fine. Every write an autonomous run makes traces back to the flag; nothing here licenses a write of a kind the flag does not name.

**What it relaxes.** Each one is restated inline at its own step, and that inline copy is what governs:

| Gate | Autonomous behaviour |
|---|---|
| Step 2c, item 6 — install dependencies in a fresh worktree | Detect the package manager and install. Do not ask. |
| Step 3b.1 — several open MRs match the branch | Pick the one whose source branch equals `HEAD`. Still ambiguous → escalate. |
| Step 3b.3 — post the unique swarm findings | Post all of them. Do not ask. |
| Step 4 — queue selection | Implicit `all`; work every item in order. |
| Step 6c — Apply / Modify / Reject / Discuss | Step 6b's **Recommendation** is the decision. Agree → Apply, Partially agree → Modify, Disagree → Reject. Discuss is unavailable. |
| Step 7b — post the drafted reply | Post it, via `reply-to-thread-stdin`. |
| Step 7c — resolve the thread | Resolve on Apply and Modify. Never on Reject. |
| Step 8 — continue to the next thread | Continue until the queue is empty. |

**What it does NOT relax.** These stop an autonomous run exactly as they stop an interactive one:

- **Nothing to work through** — no MR URL and no feedback in the conversation (mode selection above).
- **The argument is not a valid GitLab MR URL** (Step 1).
- **An in-place checkout fails because of uncommitted changes** (Step 2c, escape hatch). Never force-checkout, never stash, never discard. This is the only gate here that can destroy work the user has not committed, and it is the whole reason this flag is not simply "yes to everything".
- **No unresolved threads at all** (Step 4).

### Escalating

**Discuss is not available to an autonomous run** — there is nobody on the other side of it. When the code genuinely will not settle a question, that is an escalation, not a conversation.

To escalate: invoke the **`ping` skill** (the `Skill` tool, name `ping`) with one line naming the MR, the thread, and the decision you need. It reaches the user's phone, which is the point — an autonomous run was started precisely because the user is not watching the terminal, so a chat message reaches nobody. If the `ping` skill is unavailable, say so plainly and leave the same one-line request as a chat message instead. Ping **immediately**, not at the end of the run: an escalation held back until the queue drains is a question the user could have answered half an hour earlier.

Escalate when, and only when:

1. **A thread turns on a product or policy decision the code cannot settle** — which behaviour is correct, not which implementation expresses it.
2. **The fix would require changing something outside this repository** — another service, a shared config, an infra repo, a dashboard.
3. **The reviewer has reopened the same thread three times.** A ping-pong cap: three rounds means the disagreement is not going to converge by reply.
4. **Applying the fix would conflict with another unmerged change** the branch has not absorbed.
5. **A test the fix should satisfy fails for a reason you cannot explain.** A fix landing on an unexplained red test is worse than no fix.

Anything not on that list is a decision to make, not a question to ask. After pinging, leave the escalated thread unreplied and unresolved — it is the user's now — and carry on with the queue items that are independent of it; stop the run when none are.

## Step 1: Parse the MR URL (Mode A)

Extract `project_id` (slash-separated path) and `merge_request_iid` from the URL.

For a URL like `https://gitlab.com/group/subgroup/project/-/merge_requests/42`:
- `project_id` = `group/subgroup/project`
- `merge_request_iid` = `42`

If the URL doesn't look like a GitLab MR URL, warn the user and stop. **`--autonomous` does not relax this** — a malformed URL is not a judgment call, and guessing at the project or iid would aim every later write at the wrong MR.

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
   - **Under `--autonomous`: just install it.** Detect the package manager the same way and run its install command without asking. The install is confined to the worktree, is undone by deleting it, and nothing downstream works without it — there is no judgment here worth a round trip.

Worktrees are cleaned up manually — remove with `git worktree remove <path>` once the MR is merged. See `WORKTREES.md` in the Demeter repo for the full guide.

**In-place checkout (escape hatch):** after `git fetch origin <SOURCE_BRANCH>`, run `git checkout <SOURCE_BRANCH>` in the current tree. If checkout fails due to uncommitted changes, warn the user and ask how to proceed (stash, commit, or abort) — do NOT force-checkout or discard changes. Then `git pull --ff-only`.

**`--autonomous` does not relax the dirty-tree stop.** An autonomous run that hits uncommitted changes here does exactly what an interactive one does: it stops. It never force-checks-out, never stashes, never discards, and never "saves" the work to a branch of its own invention. This is the one failure in the whole skill that can destroy work the user never committed, and it is why the flag is not "yes to everything" — ping the user (Autonomous Mode → Escalating) and wait.

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
- **Discussion ID** — only for a carried-over MR thread, plus the project path and MR iid needed to reply. A review-agent finding has none **until Step 3b posts it to the MR**, and that absence is what tells Step 3b which items to post and Step 7b which treatment each one gets.
- **Resolved status** — always unresolved.

Collect these into the same numbered structure used in Step 4. Keep findings that target the same file/line as separate items unless they are clearly duplicates. Then go to **Step 3b** to persist the ones the MR does not already carry, and on to **Step 4** to display them.

In Mode B there is no branch to check out — the changes are already local — so **Step 2c never applies**.

**Step 7b applies per item, not per mode.** An item that came from a review agent and was not posted in Step 3b has no external thread: present its reply in chat and stop. One that Step 3b did post now carries a discussion ID and takes the full treatment. An item that came from an MR thread carried over from an earlier Mode A run still has a live discussion ID, so it takes the full Step 7b treatment — offer to post, and post only on an explicit yes (under `--autonomous`, post it without the offer; see Step 7b). Deciding this once for the whole run is the bug: it either strands MR replies in the chat or offers to post a swarm finding that has nowhere to go.

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

## Step 3b: Persist Unique Swarm Findings to the MR

A swarm finding exists only in this conversation. One the user accepts turns into a commit; one they reject or defer leaves **no trace at all** once the session ends, and the next reviewer re-derives it from scratch. So before working through the queue, put every unique finding onto the MR as its own comment, anchored to the code it is about.

This step runs **once**, after the queue is assembled (Mode A: after Step 3; Mode B: after Step 1B) and **before** Step 4 lists it. It applies only to queue items with **no discussion ID** — the review-agent findings. Items that came from the MR are already on the MR; never re-post them.

### 3b.1 Find the MR to post to

- **Mode A** — the MR from the URL. Already known, nothing to look up.
- **Mode B carrying MR threads** from an earlier Mode A run — that MR. Reuse the project path and iid already in context.
- **Otherwise** — look it up from the branch:
  ```bash
  ~/.claude/scripts/gitlab-api.sh mr-for-branch - -
  ```
  Both `-` arguments mean "derive it": the project from the `origin` remote, the branch from `HEAD`. One open MR → that is the target. Several → list them and ask which; **under `--autonomous`, do not ask** — pick the one whose `source_branch` equals the current `HEAD` branch, and if that still leaves more than one candidate, escalate (Autonomous Mode → Escalating) rather than guessing, because posting a batch of findings onto the wrong MR is not something a later run can tidy up. **None → say so in one line** (`no open MR for <branch>, so these findings stay in this conversation`) and go straight to Step 4. Do not offer to open the MR, and do not stall the fixes on it — re-running this skill once the MR exists will post them.

**Anchors attach to the pushed head.** Check `git rev-list --left-right --count origin/<branch>...HEAD` before posting: if there are local-only commits, a finding about a line that exists only locally cannot anchor and will land as an unanchored note. Say that in the same breath as the count, so the user can push first if they want clean anchors.

### 3b.2 Drop findings the MR already makes

Fetch the MR's existing threads unless this run already has them:
```bash
~/.claude/scripts/gitlab-api.sh mr-discussions "<project_id_urlencoded>" <mr_iid>
```
Do this even when the conversation seems to hold the bot's comments — "what is in the chat" is not the same as "what is on the MR", and a duplicate posted next to `@griddy-bot`'s identical point makes the MR worse, not more durable.

Compare each review-agent finding against:
- threads already on the MR, whoever wrote them — a review bot (`@griddy-bot`, `gemini-mr-reviewer`) or a human;
- comments a **previous run of this skill** posted — they carry the hidden marker from 3b.4, which is what makes them recognisable.

**Judge by substance, not wording.** The same defect in the same code is a duplicate even when one calls it a nil dereference and the other a missing guard. The same file with a different defect is not. When it is genuinely unclear, post it and name the thread it resembles in the summary — a reviewer resolves a near-duplicate in seconds, while a dropped finding costs them the bug.

### 3b.3 Show what will be posted and ask once

Print the list and wait for a chat reply. **Do NOT use `AskUserQuestion`.**

```
### Posting 3 of 5 findings to !965 — 2 are already on the MR

**1.** `src/api/handler.go:118` — nil map write when `opts` is empty   [review-code: correctness]
**2.** `src/api/handler.go:204` — retry loop has no backoff            [review-code: reliability]
**3.** `tests/test_api.py` (file-level) — the new branch is untested   [review-code: tests]

Already covered: the `:118` bounds check (@griddy-bot, thread 2) and the logging nit (thread 4).

Post these 3 as MR comments? (yes / no / a subset like "1,3")
```

One approval covers the whole batch. On **no**, post nothing, say in one line that the findings stay in this conversation, and continue to Step 4 — never re-ask per finding.

**Under `--autonomous`, post them all and do not ask.** Still print the list above, unchanged — an autonomous run's transcript is the only audit trail it leaves, and a batch posted silently is one the user cannot check afterwards. Then go straight to 3b.4. Asking here is precisely the gate the flag exists to open: the user pre-authorized the batch when they invoked the skill.

### 3b.4 Post each approved finding

One comment per finding — a thread is resolved as a unit, so batching several findings into one comment makes them unresolvable. The body never travels as a shell argument on this call: the last parameter is a `<body_file|->`, so it is either a path or `-` for stdin. Pass `-` with a quoted heredoc:

```bash
~/.claude/scripts/gitlab-api.sh create-diff-comment "<project_id_urlencoded>" <mr_iid> "<file_path>" <line> - << 'ENDOFBODY'
<!-- review-note:<dimension> -->
**<dimension>**

<one-sentence statement of the defect>

**Failure scenario:** <concrete inputs or state → wrong output or crash>

<optional: the direction a fix would take, 1-2 sentences>
ENDOFBODY
```

**A worktree-isolated session refuses that command whenever the finding is about `git`, and then the file form is the one that works.** Write the body with the Write tool and name it in place of `-`:

```bash
~/.claude/scripts/gitlab-api.sh create-diff-comment "<project_id_urlencoded>" <mr_iid> "<file_path>" <line> <scratchpad>/finding-<n>.md
```

Both forms are correct, because the script reads the body itself either way and neither lets the shell touch the text. Pick the file when the heredoc is refused, and see Rule 10 for why.

- `<line>` is the line in the file **as it stands now**, not the line the review quoted if the file has moved since. Pass `-` for a file-level note.
- Keep the `<!-- review-note:<dimension> -->` marker as the body's first line, byte for byte. GitLab strips an HTML comment out of the rendered view and hands it back verbatim from the API, so it is invisible to everyone reading the merge request and still exact to match on — which is how 3b.2 recognises this skill's own comments on a later run. The visible `**<dimension>**` line is a plain categorisation and deliberately nothing more: see Rule 9.
- The script anchors to the diff when that line is inside it, and otherwise falls back to a plain note prefixed with `` `path:line` `` — a line outside the MR's hunks, a file the MR does not touch, or a commit that is not pushed. It reports which in the `anchored` and `fallback_reason` fields. **Report the fallback to the user**; do not describe a comment as anchored to the code when it landed as a general note.
- Do not write the finding into the source as a comment while doing this. The MR thread is the record.

### 3b.5 Record the discussion IDs

Each posted finding comes back with a `discussion_id`. Attach it to its queue item. From here the item behaves like any other MR thread: Step 4 shows it with its thread link, and **Step 7b now applies to it** — a reject or modify reply goes back into the thread this step opened, which is what leaves the finding, the decision, and the reasoning in one place for whoever reads the MR later.

## Step 4: Display the Threads

Print a numbered summary of all unresolved items. In **Mode A** use the MR heading below; in **Mode B** use a heading like `## Review Feedback on Local Changes` and list everything gathered in Step 1B (omit the 💬 line for review-agent findings, which have no thread history).

**One numbered list, whatever the sources.** When a Mode B queue mixes review-agent findings with carried-over MR threads, do not split it into two lists — the user picks by number and should not have to think about provenance to do it. Tag each item's source inline instead (`— @griddy-bot, !965` vs `— review-code: tests`), order by what a reviewer would fix together rather than by source, and note any overlap in one line under the list. Splitting the list re-creates exactly the problem this mode exists to avoid.

**Tag the items Step 3b posted with their thread link.** A finding that is now a live MR thread reads `— review-code: correctness, !965 thread` rather than as a chat-only finding. That is the user's confirmation it was persisted, and it tells them a reply to it will land on the MR rather than in the transcript.

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

**Under `--autonomous`, treat the selection as an implicit `all`.** Print the same numbered list — it is what makes the rest of the run readable afterwards — then start at item 1 and work through every item in order without waiting for anything. Do not re-order by how easy the items look; the order you built in Step 1B/Step 3 already groups the ones a reviewer would fix together.

If there are **no unresolved threads** (Mode A), or neither a review output nor a carried-over MR thread anywhere in the conversation (Mode B), tell the user there's nothing to work through and stop. In Mode B, say which sources you checked — "no review output and no unaddressed MR threads in this conversation" — so an empty queue reads as a search that came up empty rather than a source you forgot to look at. **`--autonomous` does not relax this**: an empty queue ends the run, and there is nothing to ping about.

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
- **Unattributed** — it never says where the point being answered came from: no review swarm, no review skill, no automated reviewer, no "AI" (Rule 9)

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

### Step 7b: Offer to Post the Reply (any item with a discussion ID)

**This step is decided per item, by whether the item carries a discussion ID** (Step 1B records it). A review-agent finding has none: there is nothing to post to, so present the drafted reply in chat for the user to reuse and move on. An MR thread — reached through Mode A, or carried into a Mode B queue from an earlier Mode A run — does have one, and gets the full treatment below regardless of which mode is running.

After drafting a reply (for **Reject** or **Modify** decisions), ask the user:

> Would you like me to post this reply to the thread on GitLab? (yes/no)

If the user says **yes**, post the reply using the discussion thread ID saved from Step 3.

Use the `gitlab-api.sh` script to reply directly to the discussion thread, and use the **`reply-to-thread-stdin`** subcommand, which reads the body from standard input:

```bash
~/.claude/scripts/gitlab-api.sh reply-to-thread-stdin "<project_id_urlencoded>" <mr_iid> "<discussion_id>" << 'ENDOFBODY'
<reply text here>
ENDOFBODY
```

The `discussion_id` is the thread ID from the discussions fetched in Step 2.

**The body reaches the script on stdin, by either a quoted heredoc or a redirect from a file.** Both pass the reply through byte for byte — apostrophes, backticks, `$`, all of it — so write the reply as it should read and change nothing for the shell's benefit. Reach for the redirect when the heredoc is refused, which a worktree-isolated session does whenever the reply mentions `git`:

```bash
~/.claude/scripts/gitlab-api.sh reply-to-thread-stdin "<project_id_urlencoded>" <mr_iid> "<discussion_id>" < <scratchpad>/reply-<n>.md
```

Write the file with the Write tool. Rule 10 has the mechanism.

**The plain `reply-to-thread` subcommand takes the body as a shell argument, and this step does not use it.** It needs the reply wrapped in single quotes, which cannot contain an apostrophe, so it forced a choice between rewording a draft the user had just approved and letting a backtick run as a command substitution. Neither belongs in a reply somebody has already read and agreed to. The stdin subcommand removes the choice, so no apostrophe rule applies on any path any more.

After posting, confirm to the user that the reply was posted successfully and show the note ID.

If the user says **no**, skip posting and continue to Step 8.

#### Under `--autonomous`: post it

Do not ask. Post the drafted reply with either stdin form from the step above:

```bash
~/.claude/scripts/gitlab-api.sh reply-to-thread-stdin "<project_id_urlencoded>" <mr_iid> "<discussion_id>" << 'ENDOFBODY'
<reply text here>
ENDOFBODY
```

**Do not fall back to the plain `reply-to-thread` subcommand when the heredoc is refused** — take the redirect instead. Its body argument would need the reply rewritten to survive single-quoting, and that matters more here than interactively: nobody is proofreading an autonomous draft, so a silent rewording would never be caught.

An item with **no discussion ID** still has nowhere to post, autonomous or not: print the reply in the transcript and move on.

### Step 7c: Resolve the Thread (`--autonomous` only)

**Interactive runs never resolve a thread** — Important Rule 3 is absolute there, and this step does not exist for them. Under `--autonomous` only, resolve a thread once the outcome has fully landed:

- **Apply** — the edit is made, the repo's own checker (Step 7, item 3) passed on it, and any drafted reply is posted → **resolve**.
- **Modify** — the edit is made, the checker passed, and the reply explaining the partial application is posted → **resolve**.
- **Reject** — **never resolve.** No code changed; the only artefact is an argument that the reviewer is wrong, and the reviewer is the one entitled to decide whether it holds. Resolving it would collapse the thread over the reasoning the human most needs to read, and close an argument the agent is one side of.
- **Escalated** — do not resolve and do not reply. The thread belongs to the user now.

```bash
~/.claude/scripts/gitlab-api.sh resolve-thread "<project_id_urlencoded>" <mr_iid> "<discussion_id>"
```

A fourth argument `unresolve` reopens one. The command prints `{"resolved": true}` on success and `{"error": ...}` otherwise — **read what comes back** and report any thread that did not resolve, rather than assuming it did.

Resolve only *after* the checker has run. A resolved thread is a claim that the point is dealt with, and making that claim about a fix you have not verified is the same mistake as reporting "tests pass" without looking.

**This skill still does not commit and does not push** (Important Rule 2), under this flag or any other. So an autonomous run resolves threads whose fixes are sitting in the working tree and are not yet on the MR. Say that plainly in the closing summary: until the caller commits and pushes, the reviewer sees resolved threads whose code has not arrived.

## Step 8: Offer to Continue

After resolving one thread, offer to address the next unresolved thread. Loop back to Step 5 with the next thread if the user agrees.

**Under `--autonomous`, do not offer — continue.** Move straight to the next item in the Step 4 queue and keep going until it is empty. Then stop and write one closing summary: every thread, the decision taken on it, whether a reply was posted, whether it was resolved, anything escalated, and the reminder that the fixes are uncommitted and unpushed. That summary is the whole report the user gets, so it is worth more than the running commentary was.

**Name every finding that landed as an unanchored note.** Step 3b warned which ones were at risk; this says which ones it actually happened to, and why — local-only commits, a line the diff does not touch, a defect the finding described too vaguely to place. An unanchored note is the one outcome the author of the change will notice and the user will not, because it reads as posted either way.

## Important Rules

1. **NEVER auto-apply suggestions — `--autonomous` is the single sanctioned exception.** By default, always analyze and present your assessment first and let the user decide; the whole point of this skill is to think critically, not to blindly accept reviewer feedback. The flag does not suspend the thinking, it only removes the user from the loop: Step 6b's assessment and Recommendation are still produced in full and still printed, and under the flag that Recommendation becomes the decision instead of a proposal awaiting approval. An autonomous run that applies a reviewer's suggestion without first arguing it through has broken this rule exactly as badly as an interactive one would.
2. **Never write to GitLab unasked — `--autonomous` is the single sanctioned exception.** Interactively there are exactly two writes and both are gated on an explicit yes in chat: Step 3b posts unique swarm findings as new comments (one approval for the batch), and Step 7b posts a drafted reply into a thread (one approval per reply). Under the flag the user **pre-authorized the batch** when they invoked the skill — a grant they gave, which is a different thing from the agent concluding on its own that a write is fine. The flag opens Step 3b, Step 7b, and the resolutions in Step 7c, and **nothing else**: never edit the MR description, never post a reply you have not written into the transcript, and — autonomous or not — **never commit and never push**. This skill fixes and replies; committing and pushing belong to whoever called it. That boundary erodes silently, so treat any urge to "just commit it so the thread can be resolved" as the bug it is.
3. **NEVER resolve threads — except under `--autonomous`, and never on a Reject.** Interactively, thread resolution is the user's action in the GitLab UI after they've posted their reply or pushed changes, and this skill never performs it. Under `--autonomous`, Step 7c resolves a thread once the fix is in place and the reply is posted — the **Apply** and **Modify** outcomes only. A **Reject** stays open, always: nothing changed in the code, and the human reviewer has to see the disagreement and decide whether it stands. An escalated thread stays open too.
4. **Be honest in your assessment.** If the reviewer is right, say so. If they're wrong, explain why clearly. Don't just side with the MR author.
5. **Consider codebase context.** When evaluating suggestions, look at how similar patterns are handled elsewhere in the codebase using `Grep` and `Read`. Consistency matters.
6. **Keep replies concise.** Drafted replies should be 2-5 sentences. Long replies in code review threads are rarely read.
7. **Use the local codebase.** The user is expected to have the MR branch checked out locally. Use `Read`, `Grep`, and `Glob` to explore the actual code — don't rely solely on the diff from the API.
8. **No comments in the code.** When you apply a change, add no explanatory comment, docstring, or note recording what the reviewer asked for — a reviewer reading the next diff does not need the last review narrated back at them. That belongs in the drafted reply. Machine-read directives (linter suppressions, build pragmas, a doc-comment CI requires) are program input, not commentary, and stay allowed.
9. **Nothing this skill posts says where the feedback came from.** Not in a finding body, not in a drafted reply, not in a resolution note: no robot glyph, no skill name, no "automated review", no "AI", no "swarm", and no agent referring to itself. A finding on a merge request is a review note from the account that posted it, and that account is who is accountable for it to whoever reads the thread — a body that hands the point off to a tool invites the reader to discount it and tells them nothing they can act on. The single exception is 3b.4's `<!-- review-note:<dimension> -->` marker, which exists because 3b.2 and 3b.5 have to find the comment again on a later run and which no reader ever sees. **The chat side is not covered**: Step 4 still tags an item `— review-code: correctness` in the terminal, where provenance is the user's own record of their own run.
10. **A body never travels as a shell argument. A heredoc and a file are equally correct.** `create-diff-comment` takes a `<body_file|->` and `reply-to-thread-stdin` reads standard input, so on both calls the script collects the text itself and the shell never touches it; there is nothing to choose between the two forms on safety. What there is to choose between them on is the worktree isolation guard, and that is why both have to stay available: **the guard reads the text of the whole command, heredoc body included**, and refuses one that feeds a script outside the worktree any text naming `git` — even though nothing in that text executes. A review of a repository whose subject is `git` is almost entirely comments about `git`, so on those repositories the heredoc is refused for most findings and most replies, and the file is accepted. This rule used to ban temp files outright and mandate the heredoc, which left a worktree-isolated autonomous run with no sanctioned way to post at all; one did it with a file five times in direct violation of the file it was following, and was right to. The ban it replaced had the correct reason attached to the wrong form. The plain `reply-to-thread` subcommand is the form the rule is actually about, and no step calls it.
