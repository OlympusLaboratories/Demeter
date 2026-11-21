---
name: autopilot
description: A modifier on fix-linear or fix-freeform that takes their work all the way to a merged pull request without stopping to ask. Use when the user says autopilot, put it on autopilot, auto mode, one-shot this ticket, take this end to end, handle it autonomously, ship this without checking in, drive it to merge, or invokes /autopilot — on its own or inside another fix skill's invocation. It overrides none of that skill's flags: it commits, opens the PR, watches the pipeline and the review bot, addresses every comment, applies infrastructure plans, merges in the right order across stacked PRs, and pings the user only when finished or genuinely stuck.
---

# Autopilot — Take a Fix Skill's Work All the Way, Unattended

**This is a mode, not a task.** `fix-linear` and `fix-freeform` do the work; engaging autopilot says *and do not stop to ask me anything.* It adds the part those two deliberately refuse to do — push, open the pull request, work the review until it is clean, and merge it at the first moment that is actually safe — and changes nothing else about the run.

The name is the contract, and it is worth taking literally. An autopilot holds a course somebody else set: it cannot be engaged against nothing, it does not re-decide the destination, and it has no opinion about why the route was chosen. Everything from the branch to the description to whether a review swarm runs was settled before autopilot was engaged — this skill flies the plan it was handed, and the whole of its judgment goes into the part the fix skills leave undone.

The user's standing instruction when autopilot is on is: **trust your judgment, and pull me in only if absolutely needed.** That is a licence to decide, not a licence to guess. Every judgment call you make alone gets written down somewhere durable — the ticket, the PR description, or a thread reply — because the record is what replaces the conversation you would otherwise have had.

**Parameter:** `$ARGUMENTS` — a Linear ticket identifier, or a freeform problem statement, plus optional flags.

| Argument | Default | Effect |
|---|---|---|
| A ticket id (`PLAT-123`) | — | Implement via `fix-linear`. |
| Anything else | — | Implement via `fix-freeform`. |
| `--merge true\|false` | `true` | `false` stops after the review is clean and the PR is ready, without merging. |
| `--max-rounds N` | `3` | Review rounds with the same reviewer before escalating. |

Those two are the only flags this skill owns, and the test is that no fix skill has an opinion on either: they describe **how far the automation goes**, not what the change is. Every other flag in the invocation — `--quick-description`, `--diagram`, `--review`, `--branch`, the in-place escape hatch — belongs to the fix skill. Forward them untouched, read their effect off that skill's defaults, and do not restate a default for them here.

Parse the flags out of `$ARGUMENTS` first; whatever remains is the ticket id or the problem statement. A bare `--quick-description` means `true`.

### What the mode owns, and what it inherits

Autopilot never does the meat of the work. A fix skill does — `fix-linear` or `fix-freeform` — and by the time either of them has parsed the invocation, every decision a parameter expresses has already been made there.

So **it owns the automation and inherits the change.** It carries no defaults of its own beyond `--merge` and `--max-rounds`, and it never re-decides a question the fix skill already answered. That rule has teeth in the direction that costs the user money: reaching for `fix-freeform` is reaching for the cheap path — a one-shot description, no diagram, no review swarm — and being unattended is not a reason to spend a fleet on any of them. A default this skill restates is a default it will eventually contradict, so it restates none.

**There are no exceptions to this, including the ones that look like safety.** It is tempting to force `--branch new` on a freeform run so that a pull request exists to review — but that judgment was already made, and made better, inside `fix-freeform`: its escalation checks force a feature branch when the change touches Terraform, when the default branch is protected, or when the tree is dirty. If `--branch default` survives those checks, it survived them on this repository's own terms, and this skill is not better placed to overrule it than the skill holding the checks. "I would have chosen differently" is never sufficient, and neither is "I would have felt safer".

### Two ways in, one behaviour

Autopilot is reached either **directly** (`/autopilot <ticket or statement>`) or **by delegation**, when the user names it inside another fix skill's invocation — `/fix-linear --merge false /autopilot PLAT-123`, or `/fix-freeform --branch new /autopilot <statement>`.

Those look like different things and are not. A mode has nothing to qualify on its own, so the direct form still runs a fix skill — Step 1 picks `fix-linear` for a ticket id and `fix-freeform` for anything else, and that skill's defaults then govern the run exactly as if the user had typed it themselves. The delegated form only makes the choice explicit, and lets the user set that skill's flags while they are at it. Neither route is the "real" one.

The delegated form is a composition, not a mistake and not an ambiguity: it says *run that skill's flow, and take it all the way.* `fix-linear` and `fix-freeform` each strip the token and hand the invocation here with their own flags and the ticket or statement intact, so by the time you are reading this there is nothing left to clarify. Behave identically on both routes, and never re-ask a question the delegating skill was told not to ask.

### `--merge false` is the flag to actually honour

`--merge` decides where the run stops, and it is the one flag whose default does something irreversible. `true` (the default) means this run merges as soon as it is genuinely safe. `false` means the user has already decided this change wants a human's eyes before it lands: drive it to a green pipeline, a clean review and a ready change request, then **stop and hand them the link**. Do not arm auto-merge, do not merge because the review came back clean, and do not treat a quiet reviewer as consent. A run that merges under `--merge false` has done the one thing the user explicitly reached for a flag to prevent.

Read it early and record it next to the run state, not just at parse time — the merge decision is made hours later, in Step 9, by which point the flag is easy to have forgotten.

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

Invoke `fix-linear` (ticket) or `fix-freeform` (statement) with the `Skill` tool, passing `--quick-description` through.

Those skills have interactive gates. Resolve them yourself, as follows, and **write down every call you make**:

- **Ambiguity in the ticket or statement.** Do not ask. Earn the right to decide: read the callers, the tests, the adjacent modules, and the git history of the change sites. Check the ticket's linked issues and recent comments, sibling tickets, and recent pull requests touching the same code. Reproduce the bug or run the failing test where that is cheap. If it is still genuinely undecidable, pick the most defensible option and record the decision with its reasoning.
- **Plan approval.** Self-approved — but hold the plan to the same standard the interactive flow would. Autonomy is not an excuse for a thinner plan. Post the locked plan, every judgment call, and its rationale as a comment on the Linear ticket **before implementation starts**. For a freeform run there is no ticket, so the record goes in as a **comment on the PR** — not the description, which `changes-description` deliberately keeps free of design notes — and it must go in before you request any review. Write it as engineering rationale: the alternative considered and why it lost, the constraint that forced a choice, the risk you want looked at. Never narrate the process that produced it, and never open with who or what wrote it. If a discovery later forces a change of plan, record the revision and the reason **before** you resume.
- **The no-comments rule still applies.** The code you write carries no explanatory comments, no banners, no docstrings that were not already there, no TODOs, no ticket references. The fix skills restate this in full; do not let an autonomous run quietly relax it. Explanation goes in the commit message and the PR description.

**`--branch` is the fix skill's too — do not force `new`.** A freeform run that stays on the default branch produces no pull request, and that is a coherent thing to have asked for: the automation this skill adds to it is the push, and Steps 5 through 10 have nothing to drive. Step 4 has both paths. The safety argument for overriding does not survive contact with `fix-freeform`'s Step 2b, which has already escalated the run to a feature branch if the change touched Terraform, if the default branch was protected, or if the tree was dirty — so a `--branch default` that reaches this skill is one those checks deliberately let through.

**Every flag but `--merge` and `--max-rounds` is the fix skill's, so forward the invocation and read the result.** `--quick-description`, `--diagram` and `--review` are decided there and this skill does not second-guess any of them. In particular `--review` resolves to `true` through `fix-linear` and `false` through `fix-freeform`, and an unattended run is not grounds to turn a swarm on that the user left off — the forge's own reviewer runs either way, so inheriting a `false` degrades the review rather than removing it, and a fleet of agents is a cost the user notices.

**`--review false` is then passed down — but only on a run that will open a pull request.** This is about *where* the swarm runs, not whether. The delegated skill would otherwise fire it at the end of its own flow, before the push, and `fix-feedback`'s posting step needs a pull request that does not exist yet at that point, so those findings would have nowhere to land. This skill owns the swarm at Step 5b instead, the same way it owns the commit and the description.

On a `--branch default` run there is never going to be a pull request, so that reasoning inverts: leave `--review` alone, let `fix-freeform` run its own Step 5e, and skip Step 5b. Taking the swarm away from the skill that can still act on its findings, to run it later in a place that cannot, is strictly worse than not moving it.

## Step 2: Commit

Invoke `commit-msg` with the `Skill` tool and commit with the message it produces. One commit for the implementation.

## Step 3: Describe

Invoke `changes-description` with the `Skill` tool. Pass `--one-shot` when `--quick-description` is true.

**On a `--branch default` run there is no description field to fill**, so the text is the change summary that goes into the Step 11 report and, where it is short enough to belong there, the commit body. Everything below still governs it: a summary nobody will read on a pull request is not licence to write it carelessly, because it is the only account of the change a reader will ever get.

**Nothing in the description says how it was produced.** No authorship line, no "written autonomously", no robot emoji, no note that a debate or a fact-check ran, and no count of rounds. A human opens a PR with finite attention, and every line that is not about the change competes with the lines that are. How the text was generated is a fact about the process, not about the change.

Announcing that an agent wrote it is worse than merely useless. It invites the reader to discount everything above it, and it reads as a disclaimer rather than as engineering. The work stands or falls on whether the description is accurate and the diff is right.

**The run's provenance goes to the user in your own reply instead** — rounds, unanimity, fact-check status, outstanding objections, anything you overrode. That is where it is actionable. If the fact-check did not complete, tell the **user**, clearly: it is a reason for them to read the description harder, not a caveat to print on the PR.

## Step 4: Push and Open the Pull Request

**This is the point where this skill supersedes `fix-linear`'s and `fix-freeform`'s Important Rule 1**, which forbids pushing and creating pull requests. That rule exists so an interactive session never surprises the user with external state. An autonomous run was explicitly asked for exactly this, so the prohibition is lifted **for the branch this run worked on and for nothing else**. You still never force-push, never touch another branch, never amend a commit that is already on the remote, and never act on a pull request this run did not open.

### 4a. `--branch default` — push, and the run is over

The fix skill committed onto the default branch and no pull request is coming. Push that branch, report per Step 11, and stop. Steps 5 through 10 are about driving a pull request to merge; with none in existence there is nothing for them to watch, review, approve or merge, and inventing a branch at this point to give them something to do would be making the user's decision over again at the last possible moment.

**Fast-forward only, and never force.** Someone else may have pushed since the fix skill cut its base. `git pull --ff-only` and push again; if that fails the history has diverged and this run no longer knows what it would be writing on top of — stop and report it per Step 11's stop conditions. Do not merge, do not rebase, do not force.

**Say plainly in the report that the change is on the default branch and was not reviewed by anybody.** That is the trade `--branch default` makes, and it is the user's to make, but it is the one fact they need back from a run they were not watching. If `--review` was on and `fix-freeform`'s Step 5e produced findings, those findings now describe code that is already live — lead with them.

### 4b. Everything else — open the pull request

Push the branch, then open the PR with the helper's create command. Title from the commit subject; description from Step 3; reference the ticket where there is one so the forge's integration can transition it on merge.

Open it as a normal pull request, not a draft — the review bot runs as a CI job regardless, and a draft cannot be merged or queued, so opening as a draft buys nothing and blocks Step 9.

## Step 5: Arm the Watcher — never poll in-turn

**Steps 5 through 10 apply only to a run that opened a pull request.** A `--branch default` run ended at Step 4a; go straight to Step 11.

You now need to know when the pipeline finishes and when the reviewer reports. **Use the `Monitor` tool.** Do not use `sleep` loops, do not call `TaskOutput` in a wait loop, and do not hold the turn open. A monitor runs in the background and wakes the session with a notification, which leaves the user's prompt free and is the only approach that works when several of these runs are in flight at once.

Write the monitor script so that **every terminal state produces a line**. Silence must never be indistinguishable from success — a monitor that only reports green stays quiet through a crashloop. Emit a line for success, failure, cancellation, and a blocked or manual pipeline, and for any new unresolved thread.

Poll the forge no more often than every 60 seconds; these are remote APIs with rate limits, and the review bot runs in CI, so the interesting events are minutes apart. Tolerate a failed request (`|| true`) so one blip cannot kill the watch. Set `persistent: true` — a review cycle outlives the default timeout.

When the monitor's notification arrives, continue from Step 6. Between arming it and that notification, the turn is over: answer anything else the user asks normally.

## Step 5b: The Review Swarm — launched with the watcher, not after it

When `--review` resolved to `true` — off the fix skill, so `fix-linear` runs it and `fix-freeform` does not — invoke the `review-code` skill using the `Skill` tool **in the same turn that arms the monitor**, with no arguments — the branch is pushed, so its Local mode diffs exactly what the pull request contains.

Arm the monitor first and launch the swarm second, then yield once for both. Neither is a precondition for the other: CI and the forge's reviewer are already running on the push, and the swarm reads the diff from disk. Waiting for one before starting the other adds a full swarm's latency to a run whose entire purpose is to need nothing from anybody.

**Why an unattended run wants both reviews.** The forge's reviewer makes a single pass over the finished diff. The swarm attacks it from independent angles and then has a panel of skeptics try to refute every candidate finding, so what it reports has already survived a filter the bot never applies. Interactively that is a nice-to-have, because a human reads the diff before it lands. Here there is no such human: the review *is* the only thing standing between this run and the default branch, which is the same reason Step 1 forces a pull request in the first place.

The swarm's completion notification wakes you exactly as the monitor's does. When it is the swarm that woke you, its confirmed findings are a new source of review feedback — go to Step 6 and let them enter the loop where a bot's threads do.

**The swarm runs once per run, not once per round.** It reviews the diff as first pushed, and re-running it after every round would spend a fleet re-reviewing code it has already passed. One re-run is justified when a round changed the shape of the change rather than patching it — a redesign, not a fix. More than one is not.

If `review-code` errors or is not installed, record that in the run notes and continue on the forge's reviewer alone. A missing swarm degrades the review; it never stops the run.

When `--review` resolves to `false`, skip this step in silence — do not mention the swarm you did not run, do not offer it, and do not treat the forge's reviewer as a lesser substitute in the run notes. It is the review this run was asked for.

## Step 6: The Review Loop

Each time the watcher wakes you, gather the current state — PR state, pipeline status, approvals, unresolved threads — and then branch **in this priority order**. The ordering is not arbitrary and is the most commonly botched part of this flow:

> **Review comments outrank CI, always.** Addressing comments means pushing, and every push starts a new pipeline. Waiting for a red or running pipeline before handling open threads throws away a complete CI run, every time.

1. **Unresolved threads exist, or the Step 5b swarm has reported confirmed findings** (whatever the pipeline is doing) → invoke `fix-feedback --autonomous` with the `Skill` tool. It takes both sources as one queue: its Mode B reads the swarm's findings out of the conversation, and its Step 3b posts every finding the pull request does not already carry as an anchored comment *before* fixing any of them — so a swarm finding becomes a thread on the pull request like any other, and survives this run. If the pipeline has also failed, diagnose it in the same pass and fold the fix into the **same push** — never push twice. Then return to the watcher.
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

**Skip this entire step when `iac_bot` is empty.** Otherwise the branch may contain an infrastructure plan that has to be applied from the PR branch *before* the merge, because merging an unapplied plan ships code whose infrastructure was never created.

Detect it: fetch the PR's raw notes (not just discussion threads — the bot usually posts plain notes, which a thread-only fetch discards) and look for notes authored by `iac_bot`. None means this gate does not apply; go to Step 9.

Collect every directory the bot reported a plan for using `iac_plan_marker`. Run the apply by posting the comment the bot expects, once and idempotently. Then wait — via the watcher, not a sleep loop — until **every** planned directory has reported `iac_apply_marker`.

- Every planned directory shows the apply marker → Step 9.
- An apply reported an error → **stop, do not merge, and escalate.** A failed infrastructure apply can leave partial state, and that needs a person.
- Nothing yet → keep waiting.

Run this gate **after** approval, because the bot will usually refuse to apply before the PR meets its approval requirements.

## Step 9: Merge

**Check `--merge` before anything else in this step.** When it is `false`, this step is where the run ends: the pull request stays open and unarmed, and you go straight to Step 11 to report. Do not merge, do not enable auto-merge, and do not ask whether they have changed their mind — the flag was set before the run started precisely so that nobody has to be available now. Say in one line that the pull request is green, reviewed and ready, held unmerged per `--merge false`, and give the link.

Everything below applies only when `--merge` is `true`.

Check `require_human_approval` first. When it is true, a review bot's approval **is not sufficient** — wait for at least one human approver. The user driving this run counts as a human; other bots do not. This is the one gate autonomy never waives, and it is the reason this skill is safe to leave running.

- **Infrastructure repos** (the Step 8 gate applied): merge **directly**. Never enable auto-merge here — auto-merge fires the instant the pipeline is green and can beat the apply, merging a plan that was never applied.
- **Everywhere else**: enable auto-merge (squash). This is what "as soon as possible but only as soon as appropriate" means in practice — the forge merges the moment its own conditions are met, with no polling and no race.

Then keep watching until the state is actually `merged`. Auto-merge can be cancelled by a failing pipeline or a new push, so arming it is not the same as it having happened.

If the merge is refused, report the exact blocker. Rebase if the forge says the branch is behind; surface anything else.

## Step 10: Several Pull Requests, In Order

When the work splits across more than one PR:

**Name them so the relationship is obvious at a glance.** Share a prefix and lead with an ordinal:

```
dylan/PLAT-3535/01-add-registry-loader
dylan/PLAT-3535/02-migrate-call-sites
dylan/PLAT-3535/03-delete-legacy-path
```

A reader scanning the branch list must be able to tell these three belong together, and in what order, without opening any of them. Cross-link them in each description: what it depends on, and what depends on it.

**Arm them in order, and as early as possible.** Record the intended order and each PR's dependencies in `.claude/autopilot/<run>/stack.json` so the sequence survives a session restart. Then:

- Only the head of the stack is eligible to merge. Take it through Steps 6–9 normally.
- For each successor, arm a watcher on its predecessor's merge state. When that fires: rebase the successor onto the updated target, let its pipeline re-run, and only then take it through the merge gate.
- **Never arm auto-merge on a PR whose predecessor has not merged.** Auto-merge fires on the forge's conditions, which do not know about your ordering, so arming early merges things in the wrong order.

The principle: a step is armed the instant its precondition is genuinely satisfied, and not one moment before. Waiting longer wastes the user's time; arming earlier breaks the ordering.

**`--merge false` applies to the whole stack, not just its head.** Take every PR to green and reviewed, cross-linked and in order, then leave all of them open and unarmed. A stack is exactly where this is easiest to get wrong: merging the head "to unblock the rest" is still a merge the user asked you not to make, and it is the one that cannot be undone.

## Step 11: Close the Loop and Ping

When the PR merges, when a `--branch default` run has pushed, or when you stop for any reason:

1. **Record it where the work lives.** On a ticket run, comment the PR URL, what shipped, and anything noteworthy. A `--branch default` run has no PR, so record the pushed commit SHA and its forge URL instead. Work you deliberately did not do becomes its own ticket, linked back — never a buried bullet in a closing comment. Check whether the forge integration already moved the ticket before moving it by hand; that integration is asynchronous.
2. **Attach the diagram** when `--diagram` is true. Invoke `changes-diagram` with the `Skill` tool and append its link to the PR description — or, on a `--branch default` run, carry the link in the report and the ticket comment, since there is no description to append to. Do this once the code has settled — a diagram of a branch that changed three more times is worse than none. **A failed or unavailable diagram never fails the run**: say so in one line and carry on.
3. **Ping the user.** Invoke the `ping` skill with the `Skill` tool. This is the only message the user may see, so it carries what happened and whether anything is needed — a ping that says "done" wastes it. **A `--branch default` run says so in the ping**: the change is on the default branch, unreviewed, and already live. That is what the user chose, and it is also the single fact most worth knowing on a phone.

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
5. **This run owns exactly one branch** (or one named stack) — including when that branch is the default one. Never force-push, never amend a pushed commit, never act on a pull request this run did not open.
6. **Never override the fix skill's flags.** `--merge` and `--max-rounds` are this skill's; every other flag was decided before this skill was reached, `--branch` included. Automation is what this skill adds, not a second opinion on what the change should be.
7. **Record every decision you made alone**, at the time you made it — on the ticket, as a PR comment on a freeform run, or in the Step 11 report when the run produced neither. The record is what replaces the conversation, so it carries the reasoning and nothing about the process that produced it.
8. **No comments in the code.** Autonomy does not relax it.
9. **An empty config value means the capability is absent, not that you should guess at it.** Never substitute a name you saw in an example for one the machine did not supply.

## Step 12: Self-Improvement

After the run, reflect on what actually happened: where the watcher missed an event, where a gate fired that should not have, where a decision you recorded turned out wrong, whether the review loop converged or ping-ponged. Edit this skill file surgically — a note near the relevant step, not a rewrite — and tell the user in one line what you changed and why.
