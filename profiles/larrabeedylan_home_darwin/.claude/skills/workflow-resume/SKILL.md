# Workflow Resume — Restart a Killed Swarm from Cache

Bring a dead swarm back. When a `Workflow`-based skill — `review-code`, `changes-description`, `review-kludge` — is cut off by a spend/usage limit, a `TaskStop`, or a CLI exit, every agent that finished before the cut is still on disk. This skill finds that run, says what it lost and why, and then either **resumes** it (replaying the cached agents, running only what is missing) or **harvests** the finished results and completes the job without a new fleet.

**Parameter:** `$ARGUMENTS` — optional. A run id (`wf_a8e39f0a-5c4`), a workflow name (`review-code` — picks its newest broken run), or nothing (list and choose). Flags: `--harvest` / `--resume` force the Step 4 decision, `--list` stops after Step 1.

Everything on disk is read through one helper:

```bash
python3 ~/.claude/scripts/workflow-runs.py --help
```

## How the cache actually works

Read this before deciding anything — it is what makes a resume cheap or pointless.

Every run writes `journal.jsonl` to `~/.claude/projects/<slug>/<session>/subagents/workflows/<runId>/`, one `started` line per agent followed by a `result` or a `failed` line, each tagged with a cache key. `resumeFromRunId` loads that file and replays matching agents for free.

Four properties decide everything downstream:

1. **The cache is a prefix, not a set.** The key of agent N is a hash of *(key of agent N-1, prompt, opts)* — a chain. Replay walks the chain and stops dead at the first key with no `result`. Every agent after that point runs live, **including ones that succeeded last time**. A run that finished 80 of 96 agents can still have only 33 replayable ones if the failures started early. That number is `cleanPrefix` in Step 1.
2. **The journal is looked up under the *current* session id.** A new terminal is a new session, and a new session sees no cache at all — until Step 3 links it in.
3. **A resumed run records only its live agents.** Replayed agents are not re-written to the new run's journal, so the new run's journal is *not* a superset of the old one. Chain further resumes off the **original** run id, or merge first (Step 6).
4. **Changing `args` changes every key.** The args are interpolated into agent prompts, so editing `scale`, the diff, or anything else is a full re-run wearing a resume's clothes. Resume with the args the run actually used, or do not call it a resume.

## Step 1: Find the Run

```bash
python3 ~/.claude/scripts/workflow-runs.py list
```

Broken runs only, newest first; `--all` adds the healthy ones, `--json` for machine reading. If `$ARGUMENTS` already names a run id, skip to Step 2.

| HEALTH | What it means | Usual cause |
|---|---|---|
| `LIMIT-HIT` | at least one agent died with a spend/usage-limit message | the case this skill exists for |
| `INTERRUPTED` | the workflow never returned a result | Ctrl-C, `TaskStop`, CLI exit, crash |
| `HOLES` | it returned, but agents died on terminal errors | API errors, overload |
| `SUSPECT` | it returned an empty or degenerate result | usually a bad `args` payload, not a limit — resuming will not fix it |
| `OK` | every launched agent returned | nothing to recover |

**A `LIMIT-HIT` run whose status is `completed` is the dangerous one, and it is the common one.** When an agent dies, `agent()` returns `null` and the script keeps going, so the workflow completes, post-processing runs over the survivors, and the origin skill prints a confident report that never mentions the third of its fleet that never spoke. Status `completed` does not mean finished. If the user is here because a report looked thin, lead with this.

If several runs match, show the candidates and let the user pick rather than guessing — `changes-description` and `review-code` are often run minutes apart on the same branch.

## Step 2: Diagnose It

```bash
python3 ~/.claude/scripts/workflow-runs.py show <runId>
```

Read four things:

- **`why failed`** — the verbatim message the dying agents got, including the reset time ("your session limit resets 7:50pm"). This is pulled from the last synthetic message in the agent's own transcript; the journal's `failed` events carry no reason.
- **`done` / `failed` / `dead` / `cleanPrefix`** — `failed` died on an error, `dead` were still in flight when the process went away, `cleanPrefix` is how many agents replay before the chain breaks.
- **`repoRoot`** — the tree the run was actually reading. Step 3 depends on it.
- **`session`** — where the cache lives. If it is not this session, Step 5 has to link it.

**Then check the limit has actually reset.** Compare the reset time in `why failed` against `date`. If it has not reset, stop here and say so: relaunching replays the prefix for free and then kills every live agent on contact, leaving a second broken journal to merge later and no report either way. Offer to wait, or go to Step 5B, which spends nothing.

`wfwatch` counts `started` against `result` and knows nothing about `failed`, so a limit-killed run reads as "running 16" forever in a watch window. That is a symptom of this failure, not a run still working.

## Step 3: Stand in the Right Place, and Check Nothing Moved

Two preconditions. Both produce confident garbage when skipped, which is worse than an error.

**cwd must be the run's `repoRoot`.** Subagents inherit the *session's* working directory, not the workflow's. Resume `review-code` from the wrong checkout and the live agents will `Grep` this tree, find code that merely shares vocabulary with the diff, and review it cleanly and wrongly — the exact failure `review-code` Step 1 warns about, except now half the findings come from cache and look consistent with it. If cwd is not `repoRoot`, do not resume: tell the user to run this skill from a session started in `repoRoot`.

**The code must not have moved.** Cached results describe the tree as it was at the run's `timestamp`.

```bash
git -C <repoRoot> log -1 --format='%H %cI'
git -C <repoRoot> status --porcelain
```

If HEAD advanced or tracked files changed after that timestamp, the replayed agents are describing code that no longer exists, and the live agents will describe code that does — one report, two different versions of the file, no marker saying which is which. Do not resume. Say the tree moved and re-run the origin skill fresh; that is the only correct answer, and it is cheaper than a wrong one.

## Step 4: Resume or Harvest

| Choose | When | Why |
|---|---|---|
| **Resume** (5A) | `cleanPrefix` is most of `launched` — the failures cluster at the end | The run finishes itself and returns a real result object, so the origin skill's presentation step works unchanged |
| **Harvest** (5B) | `finished` is large but `cleanPrefix` is small — failures scattered early | Resume would re-run most of the fleet; harvest recovers every finished agent regardless of position |
| **Harvest** (5B) | limits are still tight, or the origin script changed since the run | Costs nothing and spawns nothing |
| **Neither** | `SUSPECT`, or Step 3 failed | The inputs were wrong or are now stale; re-run the origin skill instead |

`cleanPrefix` is measured in journal order, which approximates the invocation order the chain uses but is not guaranteed to equal it. Treat it as an estimate and confirm against the resumed run's own cached count in Step 5A.

State the choice and the numbers in one line before acting, e.g. `wf_a8e39f0a-5c4: 80/96 finished, 16 killed by the spend limit, ~33 replayable — harvesting rather than resuming.`

## Step 5A: Resume the Run

```bash
python3 ~/.claude/scripts/workflow-runs.py link <runId>          # make the cache visible to this session
python3 ~/.claude/scripts/workflow-runs.py args <runId> --pretty  # the exact args to re-pass
```

`link` symlinks the run's journal directory into this session so `resumeFromRunId` can find it; it is idempotent, it never replaces a real directory, and it is a no-op when the run is already this session's. Undo with `unlink`.

Then **read the origin skill's current `SKILL.md`** — `~/.claude/skills/<workflow name>/SKILL.md` — and take the workflow script from its fenced `js` workflow block — the one opened with four backticks — **verbatim, as it reads today**.

Call `Workflow` with:

- `script` — that block, inline.
- `resumeFromRunId` — the run id (or the merged id from Step 6).
- `args` — the object from `args <runId>`, passed as a **real JSON object, never a JSON-encoded string**. `review-code` and `changes-description` both hard-throw on a stringified payload precisely because a run that receives one looks healthy and reviews the wrong code.

**Never pass the run's own `scriptPath`.** That snapshot is frozen at the version of the pipeline that was current when the run started — and a run that had to be rescued is exactly the run whose skill was most likely fixed afterwards. Resending the script from the skill file is what makes this skill a sanctioned exception to the "never `resumeFromRunId`" rule in `review-code`, `changes-description`, and `review-kludge`: the prohibition is about stale scripts, not about the cache. If the harness refuses `script` together with `resumeFromRunId`, write today's block to a **new** file in the scratchpad and pass that as `scriptPath` — never the run's snapshot.

Worth doing before you launch, when the origin skill has been edited recently:

```bash
python3 ~/.claude/scripts/workflow-runs.py script <runId> > /tmp/old-workflow.js
# diff /tmp/old-workflow.js against the js workflow block in the skill file
```

A difference is not a reason to use the old script. It tells you where the chain will break — the cache holds up to the first changed `agent()` call and nothing after it — so you can predict a thin replay instead of being surprised by one.

Print the new run id and the watch command as soon as `Workflow` returns, the same way the origin skills do:

```
🛰  review-code resumed from wf_a8e39f0a-5c4 — new run ID: wf_…
   Watch it live:  wfwatch wf_…
```

When it finishes, **report how much actually replayed** — the new run's manifest marks replayed agents `cached: true`:

```bash
python3 -c "
import json,glob,collections
m=json.load(open(sorted(glob.glob('$HOME/.claude/projects/*/*/workflows/<newRunId>.json'))[0]))
p=[a for a in m['workflowProgress'] if a.get('type')=='workflow_agent']
print(collections.Counter(bool(a.get('cached')) for a in p))"
```

If almost nothing was cached, say so plainly — the resume was a re-run, and the user paid for it.

## Step 5B: Harvest the Finished Results

```bash
python3 ~/.claude/scripts/workflow-runs.py harvest <runId> --out <scratchpad>/harvest.json
```

Every agent the run completed, with its `label` (`review:security`, `verify:concurrency:path/to/file.go`), its `state` (`done` / `failed` / `never-returned`), its structured `result`, and the failure reason where there is one. Labels come from the run manifest and are occasionally missing on very large runs; a result's own shape identifies it when the label does not.

Then finish the origin skill's job by hand, from that file:

- **`review-code`** — the `review:*` results are complete findings lists; the `verify:*` results are `{real, reason}` verdicts attributable through their labels. Apply the origin skill's own rules: drop out-of-scope files, keep findings whose surviving verdicts are a majority, and **re-verify only the findings whose panel died**, with a few `Agent` calls rather than a new swarm.
- **`changes-description`** — the debate rounds are self-contained; a missing final round means writing that synthesis yourself from the round below it.
- **`review-kludge`** — same shape as `review-code`.

**Say what is missing.** A harvested report is assembled from a fleet that was cut short, and the honest line is which lenses or panels never returned, not a summary that reads like a complete run. If a whole lens died, that lens did not happen — do not let its absence read as "found nothing".

## Step 6: When the Resume Also Dies

Two partial runs, two partial journals, and neither is a complete cache on its own — because a resumed run records only the agents it ran live. Union them into a fresh cache and resume from that:

```bash
python3 ~/.claude/scripts/workflow-runs.py merge <originalRunId> <resumedRunId> --into wf_<something>-m
```

Then repeat Step 5A with `resumeFromRunId: wf_<something>-m`. Keys are content-addressed, so the union is always a better cache than either input, and merging is non-destructive — the original journals are untouched. Merge only runs of the **same script and the same args**; journals from different inputs share no keys, so a wrong merge is silent and simply caches nothing.

## Step 7: Hand Back to the Origin Skill

This skill recovers a run; it does not reinterpret one. Present the result with the origin skill's own presentation step — `review-code` Step 4 (and Steps 4b/5 in incoming mode), `changes-description` Step 3, `review-kludge` Step 4 — including its cross-checks, which matter more here than usual: a rescued `review-code` run must still be checked against `discarded`, `reviewedFiles`, and the diff's own file list.

Open the report by naming the recovery: which run it came from, how many agents replayed, how many ran live, and how many never returned at all.

## Important Rules

1. **Never relaunch into a limit that has not reset.** You will spend the prefix and get a second broken journal.
2. **Never edit `args` or `scale` on a resume.** Every key changes; nothing replays; the run is a full-price re-run that you have told the user was cheap.
3. **Never pass the run's snapshot `scriptPath`.** Today's skill file, inline, every time.
4. **Never resume from a session whose cwd is not the run's `repoRoot`.** Half-cached, half-wrong is the worst report this toolchain can produce.
5. **Never resume onto code that moved after the run.** Re-run instead.
6. **Never present a rescued run as complete.** Count the agents that are still missing and name them.
7. **`completed` is not `finished`.** A status of `completed` with non-zero `failed` is a partial run, and the origin skill already printed a report that did not know it.
8. **Never delete or rewrite an original journal.** `merge` writes somewhere new; `link` is a symlink; `unlink` removes only what `link` made.
9. **This skill runs workflows — it does not edit code.** Fixes are the origin skill's next step, and any code it writes carries no comments.

## Step 8: Self-Improvement

After the run, reflect:

- Did `list` classify the failure correctly, or did the health heuristic mislabel it?
- Was the Step 4 call right — did a resume replay roughly what `cleanPrefix` predicted, or did the chain break much earlier?
- Did `link` put the cache where `resumeFromRunId` looked for it, or did the harness's layout move?
- Did the origin skill's script drift from the snapshot, and did the diff check catch it before launch?

If anything was wrong, **edit this skill file** (`~/.claude/skills/workflow-resume/SKILL.md`), or `~/.claude/scripts/workflow-runs.py` when the fault is in the helper, and tell the user what changed and why.
