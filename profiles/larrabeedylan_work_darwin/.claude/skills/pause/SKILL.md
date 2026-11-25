---
name: pause
description: Suspend a complex run — swarms, watchers, subagents and all — so it can be brought back later by /unpause without losing work or repeating it. Use when the user says pause, pause here, I'm running out of tokens, I'm nearly out of quota, stop for now and pick it up later, suspend this, park this, wrap up gracefully, or invokes /pause. Also used by autopilot when it judges its own session quota is nearly gone.
---

# Pause — Suspend a Run So It Can Come Back

Park a complex run at a safe point and write down enough that a **different session, hours later, with no transcript**, can pick it up. The companion skill is `/unpause`.

**The state file has to stand alone.** That is the whole design constraint. By the time anyone resumes, the context may have been compacted or the session closed, so anything that exists only in the conversation is lost. If a fact matters to finishing the work, it goes in the file as text — not as a path to somewhere else, and not as a hint to be reconstructed.

**Pause must be affordable at the moment it is needed.** The usual reason to pause is a nearly-empty quota window, so a pause that composes twelve sections of fresh prose will not finish, and a truncated state file is worse than no pause at all — it reads as resumable and is not. The run therefore **maintains its state continuously** (see *Keeping the journal*), and this skill's job is mostly to flush, stop things cleanly, and write one file.

## Step 1: Is This a Safe Point?

Pause is a **step-boundary** operation. Check where the run is before writing anything.

### Park freely

- After a commit, after a push.
- While parked on a watcher with nothing running.
- Between review rounds.
- Before a swarm launches.

A run parked on a watcher is consuming nothing. **It does not need to pause at all** — pausing is about active work, not wall-clock. Say so and stop rather than performing a pause that buys nothing.

### Never park — finish or unwind first

| State | Why |
|---|---|
| **Mid-file-edit, mid-multi-file refactor** | A half-applied refactor does not survive a handoff. Finish the edit or revert it. |
| **Mid-merge or mid-rebase with conflicts** | The index is in a state only this session understands. |
| **Auto-merge armed, merge not landed** | It fires on green while you are paused. The run would merge unattended with nobody verifying the deploy. **Disarm it**, then pause. |
| **An unanswered `AskUserQuestion` is dangling** | The question lives only in the transcript. A paused session swallows the answer the user is about to give — and `autopilot` now asks mid-run on purpose, answerable from the user's phone, so the answer may already be on its way. Get the answer first. |
| **Merged, deploy not yet verified** | Do not park here. Finish the verification, or take its "merged, unverified" terminal state: say what landed, that nobody confirmed it came up, and name the check a human should run. Parking silently after a merge is the failure where a ping saying "paused" reads as "nothing is wrong" while production may be broken. |
| **Mid-`fix-feedback` posting** | Its posting step comments every finding *before* fixing any of them. Pausing between leaves threads you authored and never addressed. Let the posting finish. |

### Park, but flag the hazard

Two infrastructure states cannot be pushed through or unwound, and a long apply can outlast a whole quota window on its own. Pausing is allowed; **recording the hazard is not optional.**

- **An apply is running, or a plan is posted and unapplied.** Record every planned directory and which ones have reported their apply marker. `/unpause` must re-read those markers per directory *before* it considers re-posting the apply comment — the apply comment is posted once and idempotently, and a resumed run that re-posts it has triggered a second apply.
- **The apply succeeded but the merge has not happened.** Infrastructure now exists that no merged code uses. Say that in the state file and in the ping; it is the state most worth shortening.

### Pausing during implementation is different

If the run is still implementing — interrogating the request, planning, or mid-edit — the plan and the gate answers live in the transcript and this file cannot reconstruct them. **Do not park-and-auto-resume there. Stop and ping instead**, so the user comes back to a live session that still has its context. Say plainly that the work is unfinished and not auto-resumable.

## Step 2: Stop Things, In This Order

Order matters: stop what spends tokens before writing the file, because writing it costs tokens too.

1. **Stop every armed watcher.** Recording them is not enough — a `persistent: true` monitor will wake the paused session, spend the window you are protecting, and hand control to a step that starts work. Use `TaskStop` on each, and record **what to re-arm and why**, not merely that one existed.
2. **Stop in-flight Workflow swarms.** Every agent that already finished is in the run's journal on disk and replays for free later. Only the handful actually in flight is lost. Record, for each logical swarm, in this shape:
   - the **ordered list** of every `wf_` run id it has accumulated, oldest first. A resumed run writes only its *live* agents to its own journal, so resuming off the newest id alone throws away the first generation. The chain is what `/unpause` merges.
   - the base and head SHA the swarm was launched against, and the owning skill's script hash. A swarm's cache is keyed on each agent's whole prompt, and the diff is embedded in that prompt — so if the branch moved, the cache is void and `/unpause` needs to know that without discovering it by spending a fleet.
   - **Do not record `cleanPrefix`.** It stops at the first gap in launch order, so a 26-agent run missing agent 3 reports `2` while 23 results sit cached. `/unpause` recomputes it.
3. **Stop free-standing subagents** and record their exact prompts — subagents are stateless, so a prompt is the only way back. **Workflow agents are excluded from this**: their prompts are reproduced from the script plus the journal, and writing 26 of them means writing the diff 26 times at the moment you have least budget.
4. **Flush the decision ledger into the state file as text.** The ledger lives in the session scratchpad, which is session-scoped and reaped by the OS — a path to it is worthless after a reboot or from a fresh session. Inline the content.
5. **Flush the run checklist the same way**, and for the same reason: its items file is in the scratchpad too. Inline the items, and record the page's **url and its update hash** beside them. The hash is what lets the resumed run write to the page the user is already holding; without it there is no way back to that link, and the resume publishes a second one. Mark the item the pause interrupted `in-flight`, with the pause itself as what it is waiting on, and write the page one last time before the final state write — a checklist left reading as mid-flight is how a paused run looks like a hung one.

## Step 3: Write the State File

One file, written atomically (write a temp file, then rename), to:

```
~/.claude/pause-state/<repo>--<branch>.json
```

Outside every repository, deliberately. In-repo state is the wrong place — `git/ignore` covers only `**/.claude/settings.local.json`, so a file under a repo's `.claude/` shows up in `git status` and can be committed by accident.

Create `~/.claude/pause-state/` if it does not exist.

### What it carries

**Identity and position**
- repo, repo root, **worktree path**, branch, run id, session id, timestamp, reason (`quota` / `manual`), and the quota snapshot at pause.
- Skill, step and round — `autopilot Step 6, round 2 of 3`.
- **`next_action`**: the single next thing to do, written as an instruction, not a description. This is the item that earns its place; everything else supports it.
- **`goal`**: what the run is trying to achieve, in the user's terms, plus the ticket id or problem statement.

**Authority**
- The resolved flag values, as values. `/unpause` must not re-read machine defaults — that silently reverts a mid-run `/autopilot` amendment.

**Forge state** — recorded as *inputs to a diff*, never as substitutes for looking:
- change request URL and iid, pushed or not, last-seen pipeline state.
- Per thread: id, **author class** (reviewer bot / operational bot / human / self-posted), replied yet, fix committed, fix pushed. A flat list of thread ids cannot tell a finding you posted and never fixed from genuinely new reviewer feedback, and `/unpause` would duplicate both the comment and the fix.
- Approvals: **who** approved and their class, never a bare boolean. `require_human_approval` is the gate autonomy never waives, and "approved: true" recorded when only a bot had approved reads as sufficient five hours later.
- Per CI job: retry count and the classification given. Without it a resumed run blind-retries a failure it already retried, which is the most damaging thing an unattended run can do.

**Work already published** — so `/unpause` does not do it twice:
- `diagram_attached`, `ledger_published`, and the description's pre-append state. Without these, resume appends a second collapsed fold to the description.
- The run checklist: its items, its url, its update hash, and whether the description already carries the link. All four, because they fail differently — losing the items loses what the run owed, and losing the hash loses the only route back to the page the user has open.

**Swarms, subagents, watchers** — as gathered in Step 2.

**Git state**
- HEAD sha, clean or dirty, and `git status --porcelain` verbatim when dirty. Filter out `.claude/autopilot/**` — the stack file already lives there untracked and is noise in this diff, not a change the user made.

**Stack** — when the run spans several change requests: the ordering, and which members have already merged. Without it, "never arm auto-merge on a change request whose predecessor has not merged" breaks on resume. Reconcile with the existing stack file rather than duplicating it.

## Step 4: Arm the Return, If It Should Be Armed

Only for the **session** window. A weekly exhaustion is the user's call: ping and stop.

Launch a detached background poll — not a `Monitor`, whose deadline is capped at 30 minutes and would need re-arming roughly ten times across a window, each wake spending the budget this exists to protect. A detached background command keeps running across turns and re-invokes the session once, when it exits.

Four rules for that poller, each one a way it silently fails:

- **Condition on wall-clock against `resetsAt`, not on the usage percentage.** Once the editor windows are closed, nothing refreshes the usage cache — a poller waiting for the percentage to drop waits forever, with no notification. Compare `date +%s` against the recorded reset time; treat the percentage as corroboration only.
- **Compare timestamps; never count iterations.** A `sleep` loop stops accumulating while the laptop is suspended, so counting sleeps fires late by however long the lid was shut.
- **Emit on every terminal state, not just a clean reset.** Cache missing, cache far too old, `retryUntil` still in the future, max-wait backstop reached — each gets a line. Silence must never be indistinguishable from success. Age the cache off `snapshot.fetchedAt`, falling back to the top-level `updatedAt`, against the file's own `intervalMs`: the top-level field is when the file was last written, not how old the numbers are.
- **Keep any single-shot API fallback outside the loop.** Inside it, a poller hammers the usage endpoint every iteration while the account is already rate-limited.

Record in the file whether the return is armed and the reset timestamp it is waiting for.

## Step 5: Ping and Report

Invoke the `ping` skill. Level `progress` when the return is armed, `blocked` when it needs the user.

The body says what the run was doing, how far it got, and whether anything is needed. **If a hazard from Step 1 applies — an unapplied plan, applied infrastructure with no merge, a merge with no verified deploy — that is the thing the ping leads with.** A ping that says "paused, will resume" while infrastructure sits half-applied has actively misled the user.

Then say in chat, in one line, where the state file is and what `/unpause` will do with it.

## Keeping the journal — what makes this affordable

Pause is cheap only if the state is already on disk. During a long run, append to the state file at every step boundary — it is one small write, the same way the decision ledger is already appended to as decisions happen. Four fields are enough to keep current: **step and round**, **`next_action`**, the **ledger text**, and the **run checklist's items, url and hash**. Everything else is read from the forge or from `git` at pause time, which is affordable; prose is not.

A run that journals as it goes can pause with one atomic write. A run that does not has to compose the whole file from an almost-empty window, which is the failure this skill exists to prevent.

## Important Rules

1. **A truncated state file is worse than none.** Write identity, `next_action` and the ledger first; enrich only if budget remains. Write by temp-file-and-rename so a partial write never replaces a good file.
2. **Stop watchers and swarms; do not merely list them.** An armed monitor un-pauses the pause.
3. **Never park in a "never park" state**, and never park during implementation — stop and ping instead.
4. **Inline anything that lives in the scratchpad.** It is session-scoped and gets reaped — the decision ledger and the run checklist's items both.
5. **Record the checklist's update hash, not just its url.** The url says where the page is; the hash is the only way to write to it again.
6. **Never record `cleanPrefix`** as authoritative, and never record Workflow agent prompts.
7. **Disarm auto-merge before pausing.** It fires on green whether or not you are there.
8. **Never discard or stash the user's uncommitted work** to make the tree tidy for a pause. Record it instead.
9. **The ping leads with the hazard**, if there is one.
