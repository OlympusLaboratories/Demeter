---
name: unpause
description: Bring back a run that /pause suspended — re-verify the world, restore swarms from cache, re-arm watchers, and carry on from where it stopped. Use when the user says unpause, resume the run, pick the run back up, carry on with that ticket, my quota reset, start it back up, or invokes /unpause. Also fires automatically when the session-quota watcher armed by /pause wakes the session.
---

# Unpause — Bring a Paused Run Back

Pick up a run that `/pause` suspended. The state file says what it was doing; **the world says what is true now**, and those are not the same thing after a few hours.

**The governing rule: re-verify the world, never replay intentions.** While the run was paused the change request may have merged, the pipeline may have finished, the reviewer may have commented, somebody may have pushed, the branch may have been deleted and the worktree removed. Every recorded value is an *input to a diff*, never a substitute for looking. A resumed run that acts on what it remembers is confidently acting on a world that moved.

**Parameter:** `$ARGUMENTS` — optional.

| Argument | Effect |
|---|---|
| *(none)* | Find the paused run for the current repository. If several, list them and ask. |
| A branch or repo name | Use that run's state file. |
| A path to a state file | Use it directly. |

## Step 1: Load, and Check It Is Still Real

State files live in `~/.claude/pause-state/`. Read the one that matches, then **before anything else, check the run still exists**:

- Is the branch still on the remote? Is the recorded HEAD still reachable?
- Has the change request already merged, or been closed?
- Does the recorded worktree path still exist?

**If the run was superseded — merged by someone else, branch deleted, HEAD unreachable — do not act on it.** Say what happened, archive the state file rather than deleting it, and stop. A state file nothing expires is a loaded gun: it describes a run that was real once, and acting on it does damage that looks like diligence.

If the file is older than a few days, say so and confirm before continuing.

## Step 2: Get Into the Right Place

**Enter the recorded worktree before doing anything else**, with `EnterWorktree` on the recorded path.

This is not housekeeping. The wake may land while the session's working directory is somewhere else entirely, and **subagents inherit the session's working directory** — so a swarm launched from the wrong place reviews the wrong repository and looks entirely plausible doing it. If the worktree is gone, say so and ask; do not re-create it silently, because its uncommitted state is not reproducible.

## Step 3: If This Wake Was an Interruption

The watcher can fire while the user is mid-conversation about something completely unrelated. The wake is an event, not a user turn, and it is not permission.

- Say in one line that the paused run's window has reset.
- **Do read-only re-verification freely** — it is cheap and it is what Step 4 needs anyway.
- **Do not take an irreversible action on an interleaved wake without announcing it first.** No push, no merge, no apply, no comment. The user is in the middle of something else and a merge arriving unannounced is indistinguishable from a bug.

If several runs were paused, several pollers may fire at once. Handle them one at a time and say which you are on.

## Step 4: Check There Is Budget To Resume Into

Read the usage cache — `$CLAUDE_USAGE_CACHE_DIR`, else `~/Library/Caches/claude-usage/usage.json` on macOS, else `${XDG_CACHE_HOME:-~/.cache}/claude-usage/usage.json`. Read it; never take `usage.lock`, and never write into that directory. Freshness is `snapshot.fetchedAt`, falling back to the top-level `updatedAt`; the top-level field is when the file was last written, not how old the numbers are, and the cadence to judge it against is the file's own `intervalMs`.

**A reset session window is necessary, not sufficient.** Check all of it:

- `session` — the window that reset. `percent` is quota **used**.
- `weekly` — **re-read it now, not at pause time.** It may have been at 70% when the watcher was armed and 99% by the time it fired, spent by other sessions. Resuming into a dead weekly quota buys one round and a second pause, which is a net loss.
- `scoped:<Model>` — a session at 40% with a model-scoped meter at 100% fails every agent while the headline number looks healthy.
- `spend` — same reasoning.

If headroom is thin, **downgrade rather than refusing**: do the cheap, high-value parts — the forge-state diff, the merge gate, a pending apply confirmation — and leave the expensive swarm restoration for later. Say which parts you are deferring and why. If there is no useful headroom at all, re-pause and ping; do not start work that will die halfway.

## Step 5: Diff the World Against the File

Produce one short block — this is the most useful thing the whole skill outputs:

- **Pipeline**: recorded state → actual state now.
- **Threads**: which are new since the pause, which you had already replied to, which carry a fix that was committed but never pushed. The recorded author class matters here: a finding this run posted and never fixed is not new reviewer feedback, and treating it as such duplicates both the comment and the fix.
- **Approvals**: who has approved now, and their class. Re-read them regardless of what was recorded.
- **Git**: HEAD then → HEAD now. Whether the tree is still dirty in the same way.
- **Infrastructure**: for every recorded planned directory, whether its apply marker is now present.

Then say what changed in plain terms before acting on any of it.

## Step 6: Restore the Swarms

Delegate to the **`workflow-resume`** skill rather than driving the Workflow tool yourself — it owns the cache mechanics and the resume-versus-harvest judgment.

What this skill is responsible for handing it:

- **The whole chain of run ids for each logical swarm, oldest first.** A resumed run journals only its own live agents, so resuming off the newest id alone discards the first generation's work. The chain gets merged into one cache; the generations are cumulative.
- **Both ids, kept separate**: the original run id, which is what `show`, `args` and `harvest` can resolve, and the merged id, which is what `resumeFromRunId` takes. A merged id has no manifest, so the cheap harvest path disappears if the original is lost.
- **Whether HEAD moved**, from Step 5.

### HEAD unchanged — the ordinary case

Nothing happened while you were paused, so the diff is byte-identical and the cache is fully valid. Every finished agent replays for free and only the agents that never ran are launched. This is the common case and it is cheap.

### HEAD moved — the cache is void

A swarm's cache is keyed on each agent's whole prompt, and the diff is embedded in that prompt, so a single changed line changes every agent's key. There is no per-file partial reuse to exploit; the granularity does not exist.

**Re-run the swarm in full against the current diff.** Two reasons it is not a choice: a partial review is not a review, and the cached findings describe code that no longer exists — reusing them produces a confidently-worded review of lines that are gone. Say that the cache was void, why, and what the re-run costs. **Never stop at a harvested partial and present it as the finished review.**

Before spending anything, verify the cache is actually reachable: pass `--session` explicitly to `workflow-runs.py` rather than relying on the environment, and confirm `journalExists` is true. A worktree's project directory is unified into the main checkout's by a hook that leaves aliases behind, so a link can resolve to an alias the harness does not follow, and the resume then finds nothing after you have already paid. If the session directory does not exist yet in a fresh session, create it before linking.

Recompute the resumable prefix; do not trust any figure the state file carries.

## Step 7: Re-arm and Re-spawn

- **Watchers**: re-arm from the recorded re-arm instructions, recomputing the condition. The thing each was waiting for may already have happened, in which case handle it instead of watching for it.
- **Free-standing subagents**: re-spawn from their recorded prompts. They are stateless; the prompt is the whole state.
- **Flags**: take them from the file as values. Do not re-read machine defaults — that silently reverts an amendment the user made mid-run.

## Step 8: Carry On

Resume at the recorded `next_action`, with the Step 5 diff overriding it wherever the two disagree.

**The recorded authority still stands.** A `--merge true` from before the pause still authorises the merge — the user chose that deliberately, and an unattended run that stops to re-ask has failed at being unattended. What does not carry over is the *evidence*: re-read the approvals, re-read the pipeline, and re-read the apply markers, then apply the ordinary gates to what you find. `require_human_approval` is unchanged by a pause, and so is every other gate.

Two things a resumed run must not do twice:

- **Re-post an infrastructure apply comment.** It is posted once and idempotently. Re-read the markers per directory first; a directory that already reported its apply is done, and re-posting triggers a second apply.
- **Re-publish the diagram or the decision ledger.** The file records whether each already happened. Appending a second collapsed fold to the description is the visible version of this mistake; a second apply is the expensive one.

The decision ledger continues from the text in the state file. Decisions made before the pause are already in it.

## Step 9: Clean Up and Say So

Archive the state file once the run is genuinely back under way — not before, because a resume that dies halfway should still be resumable. Then ping: the run is back, what it is doing, and whether anything is needed.

## Important Rules

1. **Re-verify, never replay.** Every recorded value is an input to a diff.
2. **Enter the worktree first.** Subagents inherit the session's working directory, so this decides which repository gets reviewed.
3. **A superseded run is archived, never acted on.**
4. **An interleaved wake authorises nothing irreversible** without announcing it.
5. **Re-read weekly, scoped and spend quota**, not just the window that reset.
6. **A partial review is never the answer.** Resume cheaply when the diff held still, re-run in full when it moved, and say which happened.
7. **Never re-post an apply comment or re-publish a published artifact.**
8. **Recorded authority stands; recorded evidence does not.** Merge if the flag said so and the re-read gates pass.
