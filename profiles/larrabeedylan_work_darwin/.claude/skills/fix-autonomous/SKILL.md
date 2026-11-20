---
name: fix-autonomous
description: Drive a change all the way from a Linear ticket or a freeform problem statement to a merged merge request, without stopping to ask. Use when the user says one-shot this ticket, take this end to end, handle it autonomously, ship this without checking in, drive it to merge, or invokes /fix-autonomous. Implements, commits, writes the description, opens the MR, watches the pipeline and the review bot, addresses every comment, applies infrastructure plans, merges in the right order across stacked MRs, and pings the user only when finished or genuinely stuck.
---

# Fix Autonomous — Ticket or Statement to Merged, Unattended

Run the whole change end to end while the user is away. Everything `fix-linear` or `fix-freeform` does, plus the part they deliberately refuse to do: push, open the merge request, work the review until it is clean, and merge it at the first moment that is actually safe.

The user's standing instruction for this skill is: **trust your judgment, and pull me in only if absolutely needed.** That is a licence to decide, not a licence to guess. Every judgment call you make alone gets written down somewhere durable — the ticket, the MR description, or a thread reply — because the record is what replaces the conversation you would otherwise have had.

**Parameter:** `$ARGUMENTS` — a Linear ticket identifier, or a freeform problem statement, plus optional flags.

| Argument | Default | Effect |
|---|---|---|
| A ticket id (`PLAT-123`) | — | Implement via `fix-linear`. |
| Anything else | — | Implement via `fix-freeform`. |
| `--one-shot-description true\|false` | `true` | Passed through to the fix skill, and on to `changes-description`. |
| `--changes-diagram true\|false` | `true` | Attach a call-flow diagram to the MR. |
| `--merge true\|false` | `true` | `false` stops after the review is clean and the MR is ready, without merging. |
| `--max-rounds N` | `3` | Review rounds with the same reviewer before escalating. |

Parse the flags out of `$ARGUMENTS` first; whatever remains is the ticket id or the problem statement. A bare `--one-shot-description` means `true`.

## Step 0: Resolve the Environment — do this before anything else

Nothing in this skill may hardcode a forge, a reviewer's name, or an artifact store. Read them:

```bash
~/.claude/scripts/skill-env.sh check
```

The values that matter here:

| Key | Used for |
|---|---|
| `forge`, `api_script` | Which API helper to call for every forge operation. |
| `change_request`, `change_request_short` | What to call the thing in everything you write and say. |
| `review_bots` | Whose threads are AI review feedback. |
| `review_job` | The CI job to re-run to request a fresh review. |
| `operational_bots` | Whose comments are plumbing and must never be treated as review feedback. |
| `iac_bot`, `iac_plan_marker`, `iac_apply_marker` | The infrastructure apply gate. |
| `require_human_approval` | Whether a bot approval alone may merge. |
| `artifact_store` | Where the diagram goes. |

**Every one of these may be empty, and empty means "this machine does not have that".** An empty `review_bots` does not mean there is no review — it means you cannot identify the reviewer by name, so treat every unresolved thread that is not from an `operational_bots` account as real feedback. An empty `iac_bot` disables the apply gate entirely. An empty `review_job` means you cannot re-trigger a review and must say so rather than retrying something that does not exist.

Use `$(~/.claude/scripts/skill-env.sh get api_script)` for the helper path throughout. Read that script's usage before calling a subcommand — **do not assume a subcommand exists on both forges**, because the two helpers are not symmetric and the GitHub one is thinner.

## Step 1: Implement

Invoke `fix-linear` (ticket) or `fix-freeform` (statement) with the `Skill` tool, passing `--one-shot-description` through.

Those skills have interactive gates. Resolve them yourself, as follows, and **write down every call you make**:

- **Ambiguity in the ticket or statement.** Do not ask. Earn the right to decide: read the callers, the tests, the adjacent modules, and the git history of the change sites. Check the ticket's linked issues and recent comments, sibling tickets, and recent merge requests touching the same code. Reproduce the bug or run the failing test where that is cheap. If it is still genuinely undecidable, pick the most defensible option and record the decision with its reasoning.
- **Plan approval.** Self-approved — but hold the plan to the same standard the interactive flow would. Autonomy is not an excuse for a thinner plan. Post the locked plan, every judgment call, and its rationale as a comment on the Linear ticket **before implementation starts**. For a freeform run there is no ticket, so the record goes in as a **comment on the MR** — not the description, which `changes-description` deliberately keeps free of design notes — and it must go in before you request any review. Write it as engineering rationale: the alternative considered and why it lost, the constraint that forced a choice, the risk you want looked at. Never narrate the process that produced it, and never open with who or what wrote it. If a discovery later forces a change of plan, record the revision and the reason **before** you resume.
- **The no-comments rule still applies.** The code you write carries no explanatory comments, no banners, no docstrings that were not already there, no TODOs, no ticket references. The fix skills restate this in full; do not let an autonomous run quietly relax it. Explanation goes in the commit message and the MR description.

`fix-freeform` defaults to committing on the default branch. **Under this skill that default is wrong**: an autonomous run always produces a merge request, because the review is the only thing standing between an unattended agent and the default branch. Pass `--branch new` unless the user explicitly asked otherwise.

## Step 2: Commit

Invoke `commit-msg` with the `Skill` tool and commit with the message it produces. One commit for the implementation.

## Step 3: Describe

Invoke `changes-description` with the `Skill` tool. Pass `--one-shot` when `--one-shot-description` is true.

**Nothing in the description says how it was produced.** No authorship line, no "written autonomously", no robot emoji, no note that a debate or a fact-check ran, and no count of rounds. A human opens a MR with finite attention, and every line that is not about the change competes with the lines that are. How the text was generated is a fact about the process, not about the change.

Announcing that an agent wrote it is worse than merely useless. It invites the reader to discount everything above it, and it reads as a disclaimer rather than as engineering. The work stands or falls on whether the description is accurate and the diff is right.

**The run's provenance goes to the user in your own reply instead** — rounds, unanimity, fact-check status, outstanding objections, anything you overrode. That is where it is actionable. If the fact-check did not complete, tell the **user**, clearly: it is a reason for them to read the description harder, not a caveat to print on the MR.

## Step 4: Push and Open the Merge Request

**This is the point where this skill supersedes `fix-linear`'s and `fix-freeform`'s Important Rule 1**, which forbids pushing and creating merge requests. That rule exists so an interactive session never surprises the user with external state. An autonomous run was explicitly asked for exactly this, so the prohibition is lifted **for the branch this run created and for nothing else**. You still never force-push, never touch another branch, never amend a commit that is already on the remote, and never act on a merge request this run did not open.

Push the branch, then open the MR with the helper's create command. Title from the commit subject; description from Step 3; reference the ticket where there is one so the forge's integration can transition it on merge.

Open it as a normal merge request, not a draft — the review bot runs as a CI job regardless, and a draft cannot be merged or queued, so opening as a draft buys nothing and blocks Step 9.

## Step 5: Arm the Watcher — never poll in-turn

You now need to know when the pipeline finishes and when the reviewer reports. **Use the `Monitor` tool.** Do not use `sleep` loops, do not call `TaskOutput` in a wait loop, and do not hold the turn open. A monitor runs in the background and wakes the session with a notification, which leaves the user's prompt free and is the only approach that works when several of these runs are in flight at once.

Write the monitor script so that **every terminal state produces a line**. Silence must never be indistinguishable from success — a monitor that only reports green stays quiet through a crashloop. Emit a line for success, failure, cancellation, and a blocked or manual pipeline, and for any new unresolved thread.

Poll the forge no more often than every 60 seconds; these are remote APIs with rate limits, and the review bot runs in CI, so the interesting events are minutes apart. Tolerate a failed request (`|| true`) so one blip cannot kill the watch. Set `persistent: true` — a review cycle outlives the default timeout.

When the monitor's notification arrives, continue from Step 6. Between arming it and that notification, the turn is over: answer anything else the user asks normally.

## Step 6: The Review Loop

Each time the watcher wakes you, gather the current state — MR state, pipeline status, approvals, unresolved threads — and then branch **in this priority order**. The ordering is not arbitrary and is the most commonly botched part of this flow:

> **Review comments outrank CI, always.** Addressing comments means pushing, and every push starts a new pipeline. Waiting for a red or running pipeline before handling open threads throws away a complete CI run, every time.

1. **Unresolved threads exist** (whatever the pipeline is doing) → invoke `fix-feedback --autonomous` with the `Skill` tool. If the pipeline has also failed, diagnose it in the same pass and fold the fix into the **same push** — never push twice. Then return to the watcher.
2. **Pipeline failed, no open threads** → Step 7.
3. **Approved and green** → Step 8.
4. **Approved, pipeline still running** → keep waiting.
5. **No verdict yet** → keep waiting. Do not babysit jobs unrelated to the review.

Two facts that look like failures and are not:
- **A push revokes approval and re-triggers the review.** That is the loop working.
- **Replies alone do not trigger a fresh review.** If a round produced only replies and no commits, there is nothing to push and therefore no new pipeline. Re-run the `review_job` to request a new verdict. Assigning the bot as a reviewer in the forge UI does nothing when the review runs as a CI job. If `review_job` is empty, say so and wait for a human instead.

**Cap the loop at `--max-rounds` (default 3) rounds with the same thread.** Ping-ponging with a bot past that point is a sign the disagreement is real; escalate per Step 10 rather than continuing.

## Step 7: CI Failures

Read the actual log before classifying. Do not blind-retry — this is where autonomous runs do the most damage, by retrying a real failure until it looks flaky.

| Class | Evidence | Action |
|---|---|---|
| **Real failure** | The error traces to code this branch changed; reproducible locally | Fix the cause, fold into the next push |
| **Infrastructure flake** | Runner system failure, network or DNS error, image pull failure, 5xx from a dependency, timeout in a step unrelated to the change | Retry the job, keep watching |
| **Flaky by design** | Fails intermittently regardless of this change; same job red on recent default-branch pipelines; passed on retry with no code change | Retry to unblock, record it for the user in the final report, and carry on |

Check whether the same job is failing on recent **default-branch** pipelines before calling anything flaky — scoping that query to this branch biases every answer toward "flaky".

**A job that fails the same way twice is not a flake.** Reclassify it as a real failure and fix it.

Job ids are per-pipeline: after any push, re-resolve the pipeline and its jobs before retrying or fetching a log.

## Step 8: Infrastructure Apply Gate

**Skip this entire step when `iac_bot` is empty.** Otherwise the branch may contain an infrastructure plan that has to be applied from the MR branch *before* the merge, because merging an unapplied plan ships code whose infrastructure was never created.

Detect it: fetch the MR's raw notes (not just discussion threads — the bot usually posts plain notes, which a thread-only fetch discards) and look for notes authored by `iac_bot`. None means this gate does not apply; go to Step 9.

Collect every directory the bot reported a plan for using `iac_plan_marker`. Run the apply by posting the comment the bot expects, once and idempotently. Then wait — via the watcher, not a sleep loop — until **every** planned directory has reported `iac_apply_marker`.

- Every planned directory shows the apply marker → Step 9.
- An apply reported an error → **stop, do not merge, and escalate.** A failed infrastructure apply can leave partial state, and that needs a person.
- Nothing yet → keep waiting.

Run this gate **after** approval, because the bot will usually refuse to apply before the MR meets its approval requirements.

## Step 9: Merge

Check `require_human_approval` first. When it is true, a review bot's approval **is not sufficient** — wait for at least one human approver. The user driving this run counts as a human; other bots do not. This is the one gate autonomy never waives, and it is the reason this skill is safe to leave running.

- **Infrastructure repos** (the Step 8 gate applied): merge **directly**. Never enable auto-merge here — auto-merge fires the instant the pipeline is green and can beat the apply, merging a plan that was never applied.
- **Everywhere else**: enable auto-merge (squash). This is what "as soon as possible but only as soon as appropriate" means in practice — the forge merges the moment its own conditions are met, with no polling and no race.

Then keep watching until the state is actually `merged`. Auto-merge can be cancelled by a failing pipeline or a new push, so arming it is not the same as it having happened.

If the merge is refused, report the exact blocker. Rebase if the forge says the branch is behind; surface anything else.

## Step 10: Several Merge Requests, In Order

When the work splits across more than one MR:

**Name them so the relationship is obvious at a glance.** Share a prefix and lead with an ordinal:

```
dylan/PLAT-3535/01-add-registry-loader
dylan/PLAT-3535/02-migrate-call-sites
dylan/PLAT-3535/03-delete-legacy-path
```

A reader scanning the branch list must be able to tell these three belong together, and in what order, without opening any of them. Cross-link them in each description: what it depends on, and what depends on it.

**Arm them in order, and as early as possible.** Record the intended order and each MR's dependencies in `.claude/autonomous/<run>/stack.json` so the sequence survives a session restart. Then:

- Only the head of the stack is eligible to merge. Take it through Steps 6–9 normally.
- For each successor, arm a watcher on its predecessor's merge state. When that fires: rebase the successor onto the updated target, let its pipeline re-run, and only then take it through the merge gate.
- **Never arm auto-merge on an MR whose predecessor has not merged.** Auto-merge fires on the forge's conditions, which do not know about your ordering, so arming early merges things in the wrong order.

The principle: a step is armed the instant its precondition is genuinely satisfied, and not one moment before. Waiting longer wastes the user's time; arming earlier breaks the ordering.

## Step 11: Close the Loop and Ping

When the MR merges, or when you stop for any reason:

1. **Record it where the work lives.** On a ticket run, comment the MR URL, what shipped, and anything noteworthy. Work you deliberately did not do becomes its own ticket, linked back — never a buried bullet in a closing comment. Check whether the forge integration already moved the ticket before moving it by hand; that integration is asynchronous.
2. **Attach the diagram** when `--changes-diagram` is true. Invoke `changes-diagram` with the `Skill` tool and append its link to the MR description. Do this once the code has settled — a diagram of a branch that changed three more times is worse than none. **A failed or unavailable diagram never fails the run**: say so in one line and carry on.
3. **Ping the user.** Invoke the `ping` skill with the `Skill` tool. This is the only message the user may see, so it carries what happened and whether anything is needed — a ping that says "done" wastes it.

### When to stop and ping instead of continuing

Escalate — ping with a level of `question` or `blocked`, saying precisely what you need — when:

- A thread needs a product or policy decision the code cannot settle.
- An infrastructure apply failed, or would destroy something.
- A merge conflict needs judgment about intent rather than mechanics.
- The same thread has reopened `--max-rounds` times.
- A fix would require changing a repository this run cannot reach.
- A test fails for a reason you cannot explain, and retrying has not settled it.
- `require_human_approval` is true and no human has approved after the pipeline has been green for a long time.

Stopping is reserved for these. Everything else — surprising test failures, undecidable details, awkward trade-offs — gets the most defensible option, recorded, and the run continues.

## Important Rules

1. **Never hold the turn open.** Every wait is a `Monitor`, never a sleep or a poll loop. Several of these runs may be live at once, and each one that blocks costs the user a session.
2. **The approval gate is never waived.** When `require_human_approval` is true, a bot approval alone does not merge. Everything else in this skill is a judgment call; this one is not.
3. **Never blind-retry a failing job.** Read the log and classify it first. Twice the same way is a real failure.
4. **Comments before CI.** Always.
5. **This run owns exactly one branch** (or one named stack). Never force-push, never amend a pushed commit, never act on a merge request this run did not open.
6. **Record every decision you made alone**, at the time you made it — on the ticket, or as a MR comment on a freeform run. The record is what replaces the conversation, so it carries the reasoning and nothing about the process that produced it.
7. **No comments in the code.** Autonomy does not relax it.
8. **An empty config value means the capability is absent, not that you should guess at it.** Never substitute a name you saw in an example for one the machine did not supply.

## Step 12: Self-Improvement

After the run, reflect on what actually happened: where the watcher missed an event, where a gate fired that should not have, where a decision you recorded turned out wrong, whether the review loop converged or ping-ponged. Edit this skill file surgically — a note near the relevant step, not a rewrite — and tell the user in one line what you changed and why.
