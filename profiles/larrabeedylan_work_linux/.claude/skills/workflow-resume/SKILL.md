---
name: workflow-resume
description: Bring a dead Workflow swarm back from its on-disk cache, re-running only the agents that never finished. Use when a review-code, changes-description, review-kludge or other Workflow run was cut off by a usage limit, a TaskStop, a crash or a closed session, and the user says resume the workflow, restart the swarm, pick up where it left off, don't re-run it from scratch, or invokes /workflow-resume. Also used by the resume skill to restore the swarms a paused run had in flight.
---

# Workflow Resume — Restart a Killed Swarm from Cache

A `Workflow`-based skill — `review-code`, `changes-description`, `review-kludge`, `docs-humanize` — launches 4 to 26 agents. When the run is cut off by a usage limit, a `TaskStop`, a crash or a closed session, **every agent that finished before the cut is still on disk.** This skill finds that run, says what it lost, and then either resumes it from cache or harvests what completed.

**The point is to not pay twice.** Restarting a swarm from scratch costs the full fleet again and throws away work that is sitting in a journal file. If re-running everything were acceptable, the user would have re-invoked the original skill. Treat a from-scratch re-run as a failure of this skill, not as a safe fallback.

**Never present a partial swarm's output as a finished result.** A review that got through 9 of 20 agents has not reviewed the diff; it has reviewed part of it. Say which agents are missing and what that leaves uncovered, and never let a resumed-but-incomplete run be read as a complete one.

**Parameter:** `$ARGUMENTS` — optional.

| Argument | Effect |
|---|---|
| *(none)* | Use the most recent resumable run. If several are plausible, list them and ask which. |
| A run id (`wf_6d84b309-15d`) | Act on that run. |
| `--harvest` | Skip the resume decision: take the finished results and complete the job without a new fleet. |
| `--all` | Include healthy completed runs when listing, for harvesting something that already finished. |

## Step 1: Find the Run

```bash
python3 ~/.claude/scripts/workflow-runs.py list --json
```

Without `--all` this lists only runs worth resuming. The fields that decide everything:

| Field | Why it matters |
|---|---|
| `runId` | What every later command takes. |
| `workflow` | Which skill owns it — you need that skill's own rules to finish the job. |
| `health` | `INTERRUPTED` means cut off mid-flight. |
| `launched` / `finished` / `failed` / `dead` | How much of the fleet actually completed. |
| `finished` vs `cleanPrefix` | `finished` is how many results are cached and eligible to replay — **this is the resume value**. `cleanPrefix` is only the contiguous run from the start, so it is a lower bound, not the answer. |
| `journalExists` | `false` means there is nothing to resume from at all — say so and stop. |
| `totalTokens` | What the run has already cost, which is the argument against re-running it. |
| `session`, `slug` | Which session wrote it. A different session is normal and is what Step 3 handles. |
| `scriptPath`, `manifest` | For **diffing** in Step 4 — never for resending. |
| `repoRoot` | Check this matches where you are. Resuming another repository's run reviews the wrong diff. |

Report, in two or three lines before doing anything: which run, which workflow, how far it got, what it cost, and why it stopped. `logs` and `failureReasons` carry the reason.

## Step 2: Resume or Harvest

This is the one judgment in the skill.

**Resume** when the run never produced its deliverable and the missing agents are a meaningful fraction of it. Resuming replays every cached agent whose key still matches and runs only what is missing.

**Harvest** when nearly every agent finished and the deliverable can be assembled from what is there. Harvesting spends no agents at all.

```bash
python3 ~/.claude/scripts/workflow-runs.py harvest <run_id>
```

Two things make this decision concrete rather than a feel:

- **Judge by `finished`, not by `cleanPrefix`.** `cleanPrefix` stops at the first gap in launch order, so a 26-agent run that lost agent 3 reports `2` while 23 results sit cached and eligible — read literally it would argue for a full re-run of a run that is nearly complete. `resumeFromRunId` reuses every completed agent whose `(prompt, opts)` still matches, not just a contiguous prefix, so `finished` is the number that predicts the saving. Quote both when they disagree.
- **A swarm's later phases usually depend on its earlier ones.** In an adversarial skill the judges or skeptics read the drafters' output, so a run that died before the judging phase cannot be harvested into a finished verdict — the phase that gives the output its value never ran. Resume that one. A run that died *during* the final phase can often be harvested.

When neither is clearly right, say what each would cost and ask.

**If `journalExists` is false, or `dead` accounts for everything launched, there is nothing to recover.** Say so plainly and ask whether to run the original skill fresh. Do not quietly start a new swarm.

## Step 3: Make the Cache Visible to This Session

The `Workflow` tool resolves a resume cache **under the current session id**, which is why a run from an earlier session will not be found by `resumeFromRunId` on its own.

```bash
python3 ~/.claude/scripts/workflow-runs.py link <run_id>
```

This symlinks the run's journal directory into this session and prints where. It needs the session id, taken from `CLAUDE_CODE_SESSION_ID`; if that is unset, pass `--session <uuid>`, which is the UUID directory in this session's scratchpad path.

Two behaviours worth knowing: linking is idempotent and says so if the cache is already visible, and it **refuses** to replace a real directory rather than overwriting one. A refusal means this session already has its own run under that id — do not force it.

**Several partial runs of the same workflow can be combined.** If an earlier resume also died, `merge <id> <id> ...` unions their journals into one resumable cache, so the second attempt's agents count toward the third:

```bash
python3 ~/.claude/scripts/workflow-runs.py merge <id-1> <id-2> --into <new-id>
```

## Step 4: Resume It

Re-invoke the `Workflow` tool with:

- `resumeFromRunId` set to the run id (the merged id, if Step 3 merged).
- `script` passed **inline, re-read from the owning skill's live `SKILL.md`**.
- `args` from the original run when HEAD has not moved:
  ```bash
  python3 ~/.claude/scripts/workflow-runs.py args <run_id>
  ```

**Never pass `scriptPath`, and this is the one rule here with scar tissue behind it.** Every Workflow call snapshots its script to disk and offers the path back for a cheap re-run, but that snapshot is frozen at the moment it was taken. Resuming through it silently replays whatever version of the pipeline was current *then*, discarding any correction made to the skill since — while the run looks entirely normal. It has already happened in this repo once: a fixed skill was bypassed by a `scriptPath` pointing at the pre-fix snapshot **from the very run it was fixing**. `review-code` names this skill as the one sanctioned user of `resumeFromRunId` precisely because it pairs it with the live script.

**The cache survives that, which is why both halves work.** `resumeFromRunId` keys each agent on its own `(prompt, opts)`. A skill-file edit that does not touch an agent's prompt leaves that agent's key intact and it still replays for free; only the agents whose prompts genuinely moved re-run — and those are exactly the ones the fix was for. So the cache is reused *and* the fix is not discarded.

Two consequences follow:

- **Use the `script` subcommand only to diff**, snapshot against the live file, so you can say what moved and what it will cost before spending anything. Its own help text says diff only, never resend.
- **Do not change `args` by hand.** The packet the agents read is in there and a reformatted arg is a changed prompt. Take them from `args <run_id>` when HEAD has not moved; when it has, the run is a full re-run against a freshly derived packet anyway and there is nothing to preserve.

**Stop the prior run first if it is somehow still live** (`TaskStop` with its task id). Resuming alongside a running copy of itself is two fleets on one journal.

Then yield. A resumed workflow is still a background workflow: it returns a `wf_` run id and hands the turn back. No `TaskOutput`, no `Monitor`, no poll loop.

## Step 5: Finish the Job

Resuming restores the swarm; it does not finish the work the swarm was for. When the run completes, go back to the **owning skill's** own rules for what to do with the output — `review-code` presents confirmed findings and names `/fix-feedback`, `changes-description` prints the description against its word budget, and so on. Do not invent a presentation of your own.

State in one line what the resume actually cost: how many agents replayed from cache and how many ran. That number is the whole justification for this skill, and it is the thing the user wants to know.

## Important Rules

1. **Never re-run a swarm from scratch as a fallback.** If it cannot be resumed or harvested, say that and ask. A silent full-price re-run is the exact outcome this skill exists to prevent.
2. **Never pass `scriptPath`.** Re-read the script from the owning skill's live `SKILL.md` and pass it inline, so a correction made since the run is not silently discarded by a frozen snapshot. Do not hand-edit `args`.
3. **Never read a partial run as a complete one.** Name the missing agents and what they would have covered.
4. **Never link over a real directory**, and never force a refused link.
5. **Check `repoRoot` before resuming.** A run from another repository reviews the wrong diff and will look entirely plausible doing it.
6. **Yield after launching.** It is a background workflow like any other.
