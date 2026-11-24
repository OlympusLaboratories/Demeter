---
name: autopilot
description: The automated tail of fix-linear and fix-freeform — it commits, pushes, opens the PR, watches the pipeline and the review bot, addresses every comment, applies infrastructure plans, merges in the right order across stacked PRs, verifies the change actually deployed after the merge, pauses itself gracefully when the session quota runs low and comes back when it resets, and arms the user's phone notifications as it takes over so it can reach them while they are away. It is on by default in every fix run, so it is usually reached by hand-off rather than invoked. Invoke it directly when the user says autopilot, put it on autopilot, auto mode, one-shot this ticket, take this end to end, handle it autonomously, ship this without checking in, drive it to merge, or runs /autopilot — including mid-run, where /autopilot with flags amends the run already in flight (take over the merge, turn on a diagram, hold a merge that was about to happen).
---

# Autopilot — The Automated Tail of a Fix Run

**This is a mode, not a task.** `fix-linear` and `fix-freeform` do the work; this skill adds the part they deliberately refuse to do — commit, push, open the pull request, work the review until it is clean, and merge it at the first moment that is actually safe — and changes nothing else about the run.

**It is on by default.** `fix_autopilot` is `true` on every profile, so the ordinary way to reach this skill is not for a user to type it: a fix skill hands the run over once the implementation, the commit message and the description are done. Being typed is the exception, and there are two of those — a direct `/autopilot <ticket or statement>`, and an `/autopilot <flags>` arriving mid-run to amend what is already happening.

The name is the contract, and it is worth taking literally. An autopilot holds a course somebody else set: it does not re-decide the destination, and it has no opinion about why the route was chosen. Everything from the branch to the description to whether a review swarm runs was settled before this skill was reached — it flies the plan it was handed, and the whole of its judgment goes into the part the fix skills leave undone.

**The standing instruction, scoped precisely: trust your judgment for everything after the code is written, and pull the user in only if absolutely needed.** That scope is the whole of it. Autopilot automates the *tail*; it does not close the fix skill's own gates. A vague ticket still gets a question, an ambiguous requirement still gets `AskUserQuestion`, and a plan worth seeing still gets shown — those happen in the fix skill, before this one is reached, and being unattended later is not a reason to guess earlier. From the commit onwards the user is away from the terminal but **not out of reach** — Remote Control is armed when the session starts and Step 0d arms the notifications, so a question raised mid-run reaches their phone and can be answered from it. Asking is therefore a real option rather than a dead end, and in a few places it is the right one; see **Asking mid-run** below. It is still not the default, because a question stalls the run until somebody answers it, so every judgment call you do make alone gets written down, because the record is what replaces the conversation you would otherwise have had. **Where it gets written down is fixed and narrow** — see **The decision record** below. It is never a comment.

**Parameter:** `$ARGUMENTS` — on a direct invocation, a Linear ticket identifier or a freeform problem statement, plus optional flags. On a mid-run amendment, flags only.

| Argument | Env key | Effect |
|---|---|---|
| A ticket id (`PLAT-123`) | — | Implement via `fix-linear`. |
| Anything else | — | Implement via `fix-freeform`. |
| `--merge [true\|false]` | `fix_merge` | `false` stops after the review is clean and the pull request is ready, without merging. |
| `--max-rounds N` | `fix_max_rounds` | Review rounds with the same reviewer before escalating. |
| `--autopilot [true\|false]` | `fix_autopilot` | `false` arriving here means the user has switched the tail off. See **Amending a run in flight**. |
| `--branch`, `--quick-description`, `--diagram`, `--review` | `fix_*` | The fix skill's. Forward them; do not restate a default for them here. |

**No default is written in this file.** Step 0 reads every one of them out of `skill-env.sh`, and a flag in the invocation wins. A bare flag means `true` — `/autopilot --merge` is `--merge true`, which is exactly how a user releases a merge they had been holding. `--merge` and `--max-rounds` are the two flags this skill owns, and the test is that no fix skill has an opinion on either: they describe **how far the automation goes**, not what the change is.

### What the mode owns, and what it inherits

Autopilot never does the meat of the work. A fix skill does, and by the time either of them has parsed the invocation, every decision a parameter expresses has already been made there.

So **it owns the automation and inherits the change.** It carries no defaults of its own — they all live in `skill-env.sh` alongside the fix skills' — and it never re-decides a question the fix skill already answered. A default this skill restated would be a default it eventually contradicted, so it restates none.

**`--branch` is the fix skill's, and there are no exceptions, including the ones that look like safety.** It is tempting to force `new` on a freeform run so that a pull request exists to review — and it is wrong, because that judgment was already made, and made better, inside the fix skill: its escalation checks force a feature branch when the change touches Terraform, when the default branch is protected, or when the tree is dirty. If `default` survived those checks, it survived them on this repository's own terms, and this skill is not better placed to overrule it than the skill holding the checks. "I would have chosen differently" is never sufficient, and neither is "I would have felt safer". A `default` run is a short run: Step 4a pushes and ends.

### Three ways in

1. **By hand-off — the normal one.** A fix skill finishes its implementation, its commit message and its description, and invokes this skill with the run's resolved flag values. The branch, the worktree and the commits already exist. **Start at Step 2**; do not invoke a fix skill, because the one that just handed over is where you came from.
2. **Directly** — `/autopilot <ticket or statement>`, with no fix skill run yet. A mode has nothing to qualify on its own, so **Step 1** picks `fix-linear` for a ticket id and `fix-freeform` for anything else, and that skill's flow then governs the run exactly as if the user had typed it themselves — including its interactive gates. It will hand back here at Step 2 by itself.
3. **As an amendment** — `/autopilot <flags>` while a fix run is already in flight. See the next section. This is the only route that changes a decision rather than acting on one.

Routes 1 and 2 converge on identical behaviour from Step 2 onwards, and neither is the "real" one. A user who types `/fix-linear PLAT-123 /autopilot` has written a redundancy, not a mistake: autopilot was already on. Strip the token, apply any flags it carries, and say nothing further about it.

### Amending a run in flight

`/autopilot <flags>` during a fix run is an **amendment to that run**. It is not a new run, not a restart, and not a question to put back to the user — they have told you something, and the only thing owed back is one line saying what changed and what it caused to happen now.

Three rules govern every amendment, and a fourth that is easy to forget: **arm the notifications if they are not armed yet** (Step 0d). An amendment is often the first moment the run became unattended, so it is often the first moment arming is owed.

Three rules govern every amendment:

- **Only the flags they named change.** Every other flag keeps its **current run value**, not the machine default. This is the one thing an amendment gets wrong most easily: re-reading `skill-env.sh` and starting from its values would silently revert an earlier amendment, which is worse than ignoring the new one.
- **An amendment never re-does a completed step for its own sake.** It changes what happens from here, plus the specific catch-up each flag names below.
- **Record the new value next to the run state**, the same way Step 0 did. `--merge` in particular is read hours later, at Step 9.

| Flag | Arriving late | What to do |
|---|---|---|
| `--merge true` | any time before the merge | The common case: the user has got their go-ahead. Re-check the Step 9 gates and merge as soon as they pass. If the run has already parked at "ready", resume it — do not wait for anything else. |
| `--merge false` | before the merge | Hold. Do not arm auto-merge, and if it is already armed, **disarm it** — an armed auto-merge fires on green and will beat this instruction. After the merge has landed, say plainly that it is already merged and do not revert it. |
| `--max-rounds N` | any time | Applies to rounds from here. A run already past the new cap escalates at the next round rather than retroactively. |
| `--diagram true` | any time | Generate and attach it now if the code has settled, otherwise at Step 11 as usual. If the pull request is already merged, publish it anyway and put the link in the ticket and the report — a diagram is still worth having after the fact. |
| `--diagram false` | any time | Skip the Step 11 attach. Never delete one already attached. |
| `--review true` | before the merge | Run the swarm now against what is pushed (Step 5b), and feed its confirmed findings through `fix-feedback` as a fresh round. This is the amendment most likely to arrive with `--merge false` beside it, and the pair means *hold on, let me see it reviewed first*. |
| `--review false` | before the merge | Stop starting new swarm rounds. Never discard findings already posted to the pull request — they are the reviewer's now. |
| `--quick-description false` | after the description exists | The user wants the thorough version. Re-run `changes-description` with no flag — the full panel, which yields the turn until it reports — and replace the description on the pull request, then **re-append the decision fold**, which the replacement drops. |
| `--quick-description true` | after the description exists | A no-op. Nobody wants a hand-written rewrite of text a panel already produced; say so in one line. |
| `--branch new` | before the push | This is the fix skill's own escalation path and it is always available: cut the branch, move the commits (its "escalating after work has already started" step), and carry on. |
| `--branch default` | after a feature branch has commits | Refuse, in one line. Escalation is one-way within a run, and the commits live on a branch created for a reason. |
| `--autopilot false` | any time | Stop the automation where it stands and report. Leave the branch, the pull request and the threads exactly as they are — **never delete a pushed branch or close a pull request** to honour this. It means *stop driving*, not *undo*. |
| `--autopilot true` | on a run that had it off | Engage from Step 2: commit if needed, push, and carry on as normal. **Arm the notifications first** (Step 0d) — the tail was off, so nothing has armed them. |

### Asking mid-run

The premise this skill was written on was that from the commit onwards there is nobody to ask. That is no longer true. Remote Control is armed when the session starts, Step 0d arms the notifications, and `notify.py` fires on `PreToolUse` for `AskUserQuestion` — so a question raised mid-run lights up the user's phone and can be answered from it, as can a permission prompt. **Asking is a real option now, and in a few places it is the right one.**

It is still not the default. A question **stalls the run** until somebody answers it, and the user may be asleep, in a meeting or at dinner — the thing that makes autopilot worth having is that it finishes. So most calls still get the most defensible option and a ledger line. Ask where getting it wrong is the expensive outcome, not where the answer would merely be interesting:

- **Anything irreversible or chargeable.** The Step 10c hazards: a step that interrupts other people, a one-way data migration, anything that spends money, a target the change request never mentioned.
- **A fork where both ways are defensible and one is expensive to undo.** A ledger entry explains a wrong turn; it does not undo one.
- **A decision from the Step 11 escalation list that the run could act on immediately** — a product or policy call, a merge conflict whose intent is unclear. Asking keeps the run alive where stopping would have killed it.
- **The quota gate**, which already worked this way — see **At an interactive gate, just ask**.

Three rules keep the ask usable from a phone rather than theatrical:

- **The question has to stand alone.** It is read on a lock screen and answered in an app, with no diff, no terminal and no scrollback. An option that says "as discussed above", names a file the user would have to open, or needs two paragraphs of context weighed against each other is unanswerable. Restate what is needed inside the question and keep each option to a line.
- **Ask before starting, never halfway through.** A question raised once an apply has begun or a migration is part-done has nothing useful to offer either answer.
- **Never ping alongside it.** The hook already notifies on the question itself. A `ping` on top is the same message twice, and the second one trains the user to stop reading both.

**A question that was asked and answered earns no ledger entry.** That decision was the user's, made on the record, in the session. The ledger is for the calls made alone.

**Never ask and then proceed as though it had been answered.** If the question is worth the stall it is worth the wait; if it is not worth the stall, decide it and record it.

### The decision record

An unattended run makes calls a reviewer never got to weigh in on, and those calls have to survive the run. That record used to be posted as its own comment on the change request, written at the moment each decision was made, with no format and no budget. It was the right information in the wrong place in the wrong shape: a wall of unedited prose, the first thing a reviewer sees, ahead of the diff it is talking about.

**So capture and publication are separate, and they happen at different times for different reasons.**

**Capture as you go, locally.** The instant you make a call nobody reviewed, append one line to a ledger in the session scratchpad — not to the forge. Writing it at the moment is not a style preference: a ledger reconstructed at the end of a two-hour run is reconstructed from memory, and the entries it invents are indistinguishable from the ones it remembers. Nothing about this is visible to anybody yet.

**Publish once, at Step 11.3, into the description.** The ledger is appended to the **end of the already-generated change request description**, inside a collapsed `<details>` fold, in a single edit. That is the only place it goes. It happens at Step 11 because that is the first point at which a description exists to append to — `changes-description` runs at Step 3, long after the first decision is made, so publishing at capture time is exactly what forced it into a comment before.

**Never post the ledger as a comment**, on the change request or on a thread, not even when the description edit fails. If the edit fails, say so in one line, carry the ledger in the Step 11 report, and move on — a comment is the surface this record is specifically not allowed to use, and a failed append is not a reason to use it.

#### What earns an entry

This is the part that decides whether the fold is four useful lines or a wall, and it matters more than the formatting.

**An entry earns its place only if a reviewer could reasonably have decided differently.** Apply that test to every line before it goes in, and delete the ones that fail. These all fail:

- Anything that followed an existing pattern, convention or lint rule. Matching the codebase is the default, not a decision.
- Anything the ticket, the problem statement or the spec already said to do.
- Anything a reader learns faster from the diff — which file was touched, what a function was renamed to, that tests were added.
- Anything that would be equally true of any run: "ran the tests", "kept the change minimal", "followed the no-comments rule".
- Anything already recorded where it belongs. A `fix-feedback` thread reply **is** the record of that decision, sitting on the thread it concerns; repeating it in the fold is duplication, and the thread is the better surface.

What is left is the real set: an ambiguity resolved one way when the other way was defensible, a scope boundary drawn, a failure classified as flaky rather than real, an alternative rejected, something deliberately not done.

**More than about eight entries means the test was not applied.** Do not raise the cap — re-apply the filter and keep the ones a reviewer could argue with.

#### Format

One fold, appended last, after the diagram link if there is one:

```markdown
<details>
<summary>Relevant Decisions (4)</summary>

- **Dropped the retry on 409** — the handler is already idempotent, so a retry duplicates the write. Capping at three was the alternative; it hides the bug rather than fixing it.
- **Left the legacy `v1` path in place** — two callers outside this repo still use it. Removing it belongs in its own change.
- **Treated the `e2e-billing` failure as real** — it failed the same way twice, on the same assertion.
- **Did not backfill historical rows** — the ticket scopes to new writes, and a backfill needs a maintenance window.

</details>
```

Rules, all mechanical:

- **One bullet per decision.** A bolded lead naming the decision in at most eight words, an em dash, then the reason. Name the rejected alternative when there was one, in the same bullet.
- **At most 25 words after the bold.** Over budget means cut, never means run on. Cut the reasoning before the decision — a reviewer who disagrees will ask.
- **No preamble, no heading, no closing sentence.** The `<summary>` is the only label. A sentence introducing the list is a sentence nobody needs.
- **The count goes in the summary**, so the fold can be judged without expanding it.
- **The summary line is exactly `Relevant Decisions (N)`.** Do not reword it per run, and do not describe the list as unreviewed, made alone, made autonomously, or made without review. The reader is being handed the judgment calls behind a change, which is an ordinary thing a change request carries; a label that frames them as a gap in process invites the reviewer to read the diff as something that got less scrutiny than it did, and it is the author of the change who wears that. The run's own autonomy is reported to the user in the Step 11 report, where it is a fact about the run rather than a disclaimer on the change.
- **Zero hard-slop phrases.** The mechanical list lives in `docs-humanize`'s `HARD_SLOP` — `leverage`, `utilize`, `facilitate`, `seamless`, `in order to`, `plays a crucial role`, `it is worth noting`, `empower`, and the rest. Check the ledger against it before publishing, matching a **whitespace-flattened** copy so a line break inside a phrase cannot hide it. These are the phrases that make a generated block unreadable, and they are the reason this record needs a budget at all.
- **Past tense, active, first word a verb.** "Dropped", "Left", "Treated", "Did not" — never "It was decided that".
- **An empty ledger means no fold.** A run that made no unreviewed calls says nothing. Never publish an empty fold, and never pad one to look thorough.

**The fold sits outside the description's word budget.** `changes-description` measures its prose mechanically and the ledger would blow that budget, which is exactly why the fold is appended afterwards rather than handed to that skill as input. Do not ask it to include the ledger, and do not count the fold against its budget.

**A regenerated description loses the fold.** If a `--quick-description false` amendment re-runs `changes-description` and replaces the description, re-append the fold afterwards from the ledger, which is still on disk. The ledger is the source of truth; the fold is a rendering of it.

**On a `--branch default` run there is no description**, so the ledger goes into the Step 11 report and the ticket comment instead — same filter, same budget, same bullets, minus the fold, since there is nothing to collapse it inside.

### `--merge false` is the flag to actually honour

`--merge` decides where the run stops, and it is the one flag whose `true` value does something irreversible. `true` means this run merges as soon as it is genuinely safe. `false` means the change wants a human's eyes before it lands: drive it to a green pipeline, a clean review and a ready change request, then **stop and hand them the link**. Do not arm auto-merge, do not merge because the review came back clean, and do not treat a quiet reviewer as consent. A run that merges under `--merge false` has done the one thing the user explicitly reached for a flag to prevent.

On the work profile `fix_merge` is `false` by default, which means the ordinary run there *always* stops at a ready pull request, and `/autopilot --merge` is how the user releases it. Read the flag early and record it next to the run state, not just at parse time — the merge decision is made hours later, in Step 9, by which point it is easy to have forgotten.

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
| `default_remote` | The remote to push to, and to delete the source branch from at Step 9a. |
| `fix_merge`, `fix_max_rounds` | This skill's two flags, when the invocation did not set them. |
| `fix_branch`, `fix_quick_description`, `fix_diagram`, `fix_review`, `fix_autopilot` | The fix skill's flags. **On a hand-off, take these from the values the fix skill passed, not from here** — it already resolved them and the user may have amended one since. Read them here only on a direct invocation.

**Every one of these may be empty, and empty means "this machine does not have that".** An empty `review_bots` does not mean there is no review — it means you cannot identify the reviewer by name, so treat every unresolved thread that is not from an `operational_bots` account as real feedback. An empty `iac_bot` disables the apply gate entirely. An empty `review_job` means you cannot re-trigger a review and must say so rather than retrying something that does not exist.

Use `$(~/.claude/scripts/skill-env.sh get api_script)` for the helper path throughout. Run it with `help` before calling a subcommand — that prints every subcommand with the arguments it takes, generated from the script's own source, which is cheaper and more reliable than reading the script. **Do not assume a subcommand exists on both forges**, because the two helpers are not symmetric and the GitHub one is thinner.

## Step 0b: Work out how this change reaches production

Merging is not shipping, and the gap between the two is where an unattended run goes quietly wrong: the merge succeeds, the run reports success, and the change is sitting in a pipeline that went red twenty minutes later with nobody watching. So **before** the merge gate, not after it, work out what happens when this lands and what would prove it worked.

Do this **contextually, from the repository in front of you.** There is no list to match against here on purpose: repositories differ, the same repository changes, and a baked-in expectation is worse than none because it keeps passing after it has gone stale. You are establishing three things, and the third is the one that gets skipped.

1. **The trigger** — what fires when a commit lands on the default branch. The repo's own CI configuration is the first place to look, and the question is narrower than "what CI exists": *which jobs run on a push to the default branch*, as opposed to on a tag, on a schedule, or on a manual dispatch. A repo whose deploy runs on a tag does not deploy when you merge, and reporting that it did would be a lie with a green tick next to it.
2. **The target** — what the trigger actually changes. A job called `deploy` might roll a container workload, hand off to a GitOps controller, apply infrastructure, publish a package, upload a static build, or print a plan and stop. Read the job, not its name.
3. **The observable signal** — the thing you could point at afterwards and say *that proves the new code is running*. This decides whether verification is possible at all, and it has to be specific enough to check: a workload's running revision, a published version, a URL serving the new build, an apply marker. "The pipeline is green" is a signal about the pipeline, not about the deploy.

Then establish two facts about your own position, because both change what you are allowed to claim later:

- **Can this session observe that signal at all?** Credentials, a cluster context, a VPN, a registry token — any of them may be missing. Probe it now, read-only, rather than finding out after the merge. A session that cannot reach the deploy target can still merge; it just cannot afterwards say the deploy worked. Probe **every** tool the signal needs, not the first one: one expired credential often disables several commands at once, and a session that proves `gcloud` is dead still learns nothing about `kubectl` until it tries it. Probing one and assuming the rest pushes the discovery into Step 10b, which is exactly where it is too late to pick a different signal.
- **How long does it normally take?** Read that off the repository's own recent successful default-branch runs rather than inventing it. That number becomes the verification budget in Step 10b, and a budget guessed from nothing is either a false alarm or a watch that never ends.

Record all of it with the run state, and **say it in one line before the merge gate**:

> `On merge: deploy job on the default branch rolls the api workload; observable via the cluster, ~6 min typical.`

**"Nothing deploys" is a complete and common answer.** Libraries, config repos, dotfiles and most internal tooling do not deploy on merge. Record it, say it, and skip Step 10b — a run that invents a deploy to verify will eventually report a failure for something that was never meant to happen.

**"Nothing deploys on merge" is not the same as "nothing left to do."** Plenty of changes reach their target through a command somebody runs afterwards — a bootstrap or setup script, an `scp` and a remote install, a `make deploy`, a config pushed to a box. That is still the deploy, and **Step 10c runs it**. So when the trigger question answers "nothing", ask the follow-up before moving on: *is there a command that makes this change take effect, and can this session run it?* Record the command and whether this session can reach the target, exactly as you recorded the rest.

**Never carry an expectation you did not derive here.** If the deploy path is genuinely unreadable from the repository — a pipeline shelling out to an opaque internal script, a controller configured somewhere else entirely — then *that* is the finding. Record it as unknown and let Step 10b report the change as merged-but-unverified, rather than manufacturing a check that passes for the wrong reason.

On a `--merge false` run this line is still worth producing, and it is arguably worth more: it tells the user what pressing the button is going to set off.

## Step 0c: Know the Budget, and Plan to Pause

A run of this skill can outlive a 5-hour quota window. Running out mid-flight is not a graceful stop: swarms, watchers and in-flight subagents are left wherever they were, and nothing records what the run was doing. So the budget is something to watch, and pausing is a step this skill performs on purpose rather than something that happens to it.

### Reading the quota — never call the API

The `claude-usage` extension already maintains a shared cache, and `/api/oauth/usage` is rate-limited **per account** with the Claude Code CLI itself polling it from every open session. Adding another caller is how a run gets itself throttled.

```bash
cat "${CLAUDE_USAGE_CACHE_DIR:-$HOME/Library/Caches/claude-usage}/usage.json"
```

On Linux the default is `${XDG_CACHE_HOME:-$HOME/.cache}/claude-usage/usage.json`.

- `snapshot.meters[]`, each `{id, percent, severity, resetsAt}`. `percent` is quota **used**, 0–100. `resetsAt` is absolute epoch **milliseconds**.
- Meter ids: `session`, `weekly`, `scoped:<Model>`, `spend`.
- Writes are atomic, so a read needs no lock. **Never take `usage.lock`** — holding it makes every open editor window skip its own refresh, and a dead holder stalls them for a minute. **Never write into that directory**, either: a file-watch there fires in every window.
- `snapshot.fetchedAt` says how old the numbers are. `retryUntil` in the future means the account is already rate-limited — do not fetch.
- Only if the cache is missing or badly stale, fetch **once**: read the token from the macOS keychain service `Claude Code-credentials`, else `~/.claude/.credentials.json` → `claudeAiOauth.accessToken`, and `GET https://api.anthropic.com/api/oauth/usage` with `Authorization: Bearer <token>`, `anthropic-beta: oauth-2025-04-20`, `Accept: application/json`. Never write the result into the cache directory.

**Check all four meter kinds, not just the headline.** A `session` meter at 40% with a `scoped:<Model>` meter at 100% fails every agent you launch while the number you looked at says healthy.

### When to pause

Check at **step boundaries** — it is a local file read, so it is cheap enough to do often, and a step boundary is where pausing is safe anyway.

| Reading | Action |
|---|---|
| `session` at **85% used or more** | Pause. Invoke the `pause` skill. |
| `weekly`, `scoped:*` or `spend` near its limit | Pause, ping, and **do not arm a return.** |
| Anything below that, parked on a watcher | Do nothing. A parked run spends nothing; wall-clock is not the thing being budgeted. |

**85% is a floor, not a suggestion, and "I am nearly finished" does not raise it.** The pause itself costs tokens — stopping watchers, flushing state, writing the file, sending the ping — so the threshold exists to leave enough window to perform it. A run that pushes past the floor because the merge is two minutes away is the run that cannot pause cleanly when those two minutes turn out to be twenty.

**The weekly window is the user's call, and the stricter window always wins.** A session reset is not permission to spend a nearly-dead weekly quota, so a weekly-driven pause pings and waits for a human. `/pause` arms a return only for the session window; see that skill.

### Journal as you go, so the pause is affordable

The usual moment to pause is the moment there is least budget to do it with, and a half-written state file reads as resumable while being useless. So do not compose it from scratch at the end. **Append to the pause state at every step boundary** — one small write, exactly as the decision ledger is already appended to as decisions happen. Three fields are enough to keep current:

- the step and round you are in,
- `next_action` — the single next thing to do, as an instruction,
- the decision ledger text.

Everything else is read from the forge or from `git` at pause time, which is affordable. Prose is not. A run that journals as it goes pauses with one atomic write.

### At an interactive gate, just ask

A blocked `AskUserQuestion` spends nothing while it waits, so the threshold cannot be crossed during the wait. The real case is that the answer arrives and the window has gone in the meantime — and at that exact moment the user is demonstrably at the keyboard. **That is the one point where asking is both cheap and correct**: say the window is nearly out and ask whether to pause here or push on. Deciding it silently from a threshold throws away the only moment the question is free.

**Never pause with an unanswered question dangling.** The question exists only in the transcript, and a paused session swallows the answer the user is in the middle of giving.

## Step 0d: Arm the Notifications — before the first unattended step

**Engaging autopilot is the gesture that says the user is walking away, so it is what arms their phone.**

Notifications are **opt-in per session** and the opt-in is a sent ping: `notify.py` writes `armed_at` only on a successful send, and until then it logs `skip: session not armed` and stays silent however long the turn runs or however stuck the run gets. So an autopilot run that only pings at Step 11 arms the session *after the run is over*, which is the one moment the arming is worth nothing. Everything in between — a permission prompt, an `AskUserQuestion`, a failure — happens into a session that cannot speak.

**So send one ping here, before Step 1**, via the `ping` skill with the `Skill` tool. Level `progress`: the work is starting and continues. The body says what is being taken over and where the run will stop, because that is the thing the user wants to confirm as they leave:

> `Taking PLAT-3276 from here: open the PR, work the review, stop before the merge. Nothing needed unless I get stuck.`

That single send does both jobs — it tells them the hand-off happened, and it arms the session for every automatic notification that follows.

**It is also what makes asking possible at all.** An `AskUserQuestion` raised later in the run notifies the phone only because the hook is armed here — `notify.py` is registered on `PreToolUse` for `AskUserQuestion`. Unarmed, the run stalls on a question nothing ever told the user about, which is the worst of both behaviours.

**Skip it when the session is already armed.** Read `~/.claude/notify-state/sessions/<session-id>.json`; an `armed_at` already present means the user has pinged this session before and the automatic notifications are live. Say so in one line and move on rather than sending a second announcement.

**Never arm when `--autopilot false`.** There is no unattended tail to notify about, and the user is at the keyboard by definition.

**A failed send never fails the run.** A missing or unconfigured `~/.claude/notify.json` makes the ping a no-op, and the `ping` skill deliberately does not write `armed_at` on a failed send. Report what it said in one line and carry on — the work is not contingent on the notification.

### Every route in arms, including the amendment

All three ways into this skill mean the same thing, so all three arm:

- **By hand-off** from a fix skill — arm here, before Step 1.
- **Directly** (`/autopilot <ticket>`) — same.
- **As a mid-run amendment** (`/autopilot --merge` on work that was never a fix-skill run) — **arm at the moment the amendment lands.** This is the route that most needs it and the easiest to miss: the run is already in flight, Step 0d is behind it, and the user has just said *take it from here* in the clearest possible terms. Check `armed_at` and send the opening ping if it is absent, before acting on the flags.

## Step 1: Implement — direct invocations only

**Skip this step entirely when you were reached by hand-off.** A fix skill that invokes this skill has already done everything in it, and invoking one back would restart the work that just finished. Go to Step 2.

On a direct invocation, invoke `fix-linear` (ticket id) or `fix-freeform` (anything else) with the `Skill` tool, forwarding every flag from the invocation. That skill resolves the defaults, sets up the branch, plans, implements, produces the commit message and the description, and hands the run back here. You do not re-do any of it.

**Its interactive gates stay open, and that is deliberate.** This is the part of the old behaviour that changed: autopilot no longer self-resolves the fix skill's questions. The automation starts after the code is written, so a vague ticket gets a question, an ambiguous requirement gets `AskUserQuestion`, and the plan gets shown — because the user who typed `/autopilot` is, at that moment, still at the keyboard. What they asked not to be interrupted for is the pipeline, the review and the merge, which is hours of waiting they should not have to sit through. Suppressing the questions as well would buy nothing and cost a whole implementation when a reading was wrong.

Two things hold on every route:

- **Start the decision ledger, and append to it as you go.** Every call nobody reviewed gets one line in the scratchpad ledger at the moment you make it, the locked plan's own judgment calls included. Nothing is published to the forge here — the ledger stays local until Step 11.3 appends it to the description. See **The decision record**.
- **The no-comments rule still applies.** The code carries no explanatory comments, no banners, no docstrings that were not already there, no TODOs, no ticket references. The fix skills restate this in full; do not let an unattended run be the reason it slips.

**Every flag but `--merge` and `--max-rounds` belongs to the fix skill.** `--branch`, `--quick-description`, `--diagram` and `--review` are resolved there, against this machine's defaults, and this skill does not second-guess any of them. In particular, an unattended run is not grounds to turn a swarm on that the machine's default left off, nor to spend the full description panel where it left the inline write.

**The swarm and the diagram are this skill's to run, and that is about *where*, not whether.** The fix skill deliberately does not run either on an autopilot run. `review-code` fires at **Step 5b**, in the turn that arms the watcher, because the branch is pushed by then and `fix-feedback` needs a pull request to anchor each confirmed finding to — fired before the push, those findings would have nowhere to land. `changes-diagram` runs at **Step 11**, once the code has stopped moving. On a `--branch default` run neither reasoning survives, because there is never going to be a pull request: the fix skill runs its own diagram and its own swarm there, and Steps 5b and 11's attach are skipped.

## Step 2: Commit

Invoke `commit-msg` with the `Skill` tool and commit with the message it produces. One commit for the implementation.

## Step 3: Describe

**On a hand-off the description already exists** — the fix skill produced it before handing over. Use it as it stands; do not regenerate it, and do not run a second panel over the same diff. Regenerate only on an explicit `--quick-description false` amendment (see **Amending a run in flight**).

On a direct invocation the fix skill you called in Step 1 produced it, the same way. If for any reason there is no description in hand, invoke `changes-description` with the `Skill` tool, passing `--inline` when `--quick-description` is true — it then writes the description in that same turn, with no workflow, no run ID and no yielded turn — and no flag at all when it is false.

**On a `--branch default` run there is no description field to fill**, so the text is the change summary that goes into the Step 11 report and, where it is short enough to belong there, the commit body. Everything below still governs it: a summary nobody will read on a pull request is not licence to write it carelessly, because it is the only account of the change a reader will ever get.

**Nothing in the description says how it was produced.** No authorship line, no "written autonomously", no robot emoji, no note that a debate or a fact-check ran, and no count of rounds. A human opens a PR with finite attention, and every line that is not about the change competes with the lines that are. How the text was generated is a fact about the process, not about the change.

Announcing that an agent wrote it is worse than merely useless. It invites the reader to discount everything above it, and it reads as a disclaimer rather than as engineering. The work stands or falls on whether the description is accurate and the diff is right.

**The run's provenance goes to the user in your own reply instead** — rounds, unanimity, fact-check status, outstanding objections, anything you overrode. That is where it is actionable. If the fact-check did not complete, tell the **user**, clearly: it is a reason for them to read the description harder, not a caveat to print on the PR.

## Step 4: Push and Open the Pull Request

**This is the point where this skill supersedes `fix-linear`'s and `fix-freeform`'s Important Rule 1**, which forbids pushing and creating pull requests. That rule exists so an interactive session never surprises the user with external state. An autonomous run was explicitly asked for exactly this, so the prohibition is lifted **for the branch this run worked on and for nothing else**. You still never force-push, never touch another branch, never amend a commit that is already on the remote, and never act on a pull request this run did not open.

### 4a. `--branch default` — push, then verify, then the run is over

The fix skill committed onto the default branch and no pull request is coming. Push that branch, **verify the deploy per Step 10b**, report per Step 11, and stop. The deploy matters more here than anywhere else in this skill: nobody reviewed this change and it is already on the branch every other checkout is cut from, so whether it actually came up is the only safety net left. Steps 5 through 10 are about driving a pull request to merge; with none in existence there is nothing for them to watch, review, approve or merge, and inventing a branch at this point to give them something to do would be making the user's decision over again at the last possible moment.

**Fast-forward only, and never force.** Someone else may have pushed since the fix skill cut its base. `git pull --ff-only` and push again; if that fails the history has diverged and this run no longer knows what it would be writing on top of — stop and report it per Step 11's stop conditions. Do not merge, do not rebase, do not force.

**Say plainly in the report that the change is on the default branch and was not reviewed by anybody.** That is the trade `--branch default` makes, and it is the user's to make, but it is the one fact they need back from a run they were not watching. If `--review` was on and `fix-freeform`'s Step 5e produced findings, those findings now describe code that is already live — lead with them.

### 4b. Everything else — open the pull request

Push the branch, then open the PR with the helper's create command. Description from Step 3. Where there is a ticket the title is `TICKET_ID: <commit subject>`; with no ticket it is the commit subject alone.

**The identifier in the title is what links the pull request to the ticket.** The forge integration matches it literally — in the pull request title and in the branch name — and on a match it attaches the pull request to the ticket and moves the ticket's state as the pull request opens, enters review and merges. `BRANCH_NAME` already carries the identifier, so the branch alone is usually enough; putting it in the title too costs nothing and stops the link depending on which of the two matchers fires. A paraphrase or an abbreviation matches neither, and it fails in the direction that matters: the pull request looks entirely normal, and the ticket sits in its pre-review state with the work already merged.

**The user may land the change themselves while the run is still working.** It is not a conflict and not a race to recover from — a human merging is strictly stronger than the gate this skill was going to apply. Most often the run invited it — see Step 5b on never reporting a change request as ready while a review is still running. What it breaks is the assumption that the branch is still the place to put work: a squash merge rewrites the commit, so a later push onto that branch no longer shares history with the default branch, and the forge may have deleted the branch under you so the push silently recreates it. Observed exactly that way — a review round finished after the merge and pushed a fix onto a branch with no open pull request, where it would have sat unnoticed.

So before pushing anything at Step 6 or later, **re-read the pull request's state**. Found merged: do not push to the old branch, do not reopen anything. Cut a fresh branch from the updated default branch, cherry-pick only the commits that did not land, and open a second pull request for them. Say in the report who merged the first one and which commits the follow-up carries, because the user's mental model is that everything went in together.

**If a pull request for this branch is already open, this step is already done.** A previous run of this skill can be killed between Step 4b and Step 9 — a rate limit, a dropped session — leaving a pushed branch, an open PR, a written description and a green pipeline, none of which this run produced and all of which it owns. Resume from state rather than re-running the flow: read the PR's diff, description and checks, treat whatever they already contain as complete, and re-enter at Step 6. Do not open a second PR, do not regenerate a description that is already on the PR, and do not re-commit a change the diff already carries. Steps 1 through 4 are skipped in that case, and Rule 5's "this run owns exactly one branch" extends to the branch and PR the interrupted run left behind.

Open it as a normal pull request, not a draft — the review bot runs as a CI job regardless, and a draft cannot be merged or queued, so opening as a draft buys nothing and blocks Step 9.

## Step 5: Arm the Watcher — never poll in-turn

**Steps 5 through 10 apply only to a run that opened a pull request.** A `--branch default` run ended at Step 4a — go to **Step 10b**, because pushing the default branch fires the same deploy a merge would, and then to Step 11.

You now need to know when the pipeline finishes and when the reviewer reports. **Use the `Monitor` tool.** Do not use `sleep` loops, do not call `TaskOutput` in a wait loop, and do not hold the turn open. A monitor runs in the background and wakes the session with a notification, which leaves the user's prompt free and is the only approach that works when several of these runs are in flight at once.

Write the monitor script so that **every terminal state produces a line**. Silence must never be indistinguishable from success — a monitor that only reports green stays quiet through a crashloop. Emit a line for success, failure, cancellation, and a blocked or manual pipeline, and for any new unresolved thread.

Poll the forge no more often than every 60 seconds; these are remote APIs with rate limits, and the review bot runs in CI, so the interesting events are minutes apart. Tolerate a failed request (`|| true`) so one blip cannot kill the watch. Set `persistent: true` — a review cycle outlives the default timeout.

When the monitor's notification arrives, continue from Step 6. Between arming it and that notification, the turn is over: answer anything else the user asks normally.

## Step 5b: The Review Swarm — launched with the watcher, not after it

When `--review` resolved to `true` — off this machine's `fix_review`, or off the invocation, or off a mid-run amendment — invoke the `review-code` skill using the `Skill` tool **in the same turn that arms the monitor**, with no arguments — the branch is pushed, so its Local mode diffs exactly what the pull request contains.

Arm the monitor first and launch the swarm second, then yield once for both. Neither is a precondition for the other: CI and the forge's reviewer are already running on the push, and the swarm reads the diff from disk. Waiting for one before starting the other adds a full swarm's latency to a run whose entire purpose is to need nothing from anybody.

**Why an unattended run wants both reviews.** The forge's reviewer makes a single pass over the finished diff. The swarm attacks it from independent angles and then has a panel of skeptics try to refute every candidate finding, so what it reports has already survived a filter the bot never applies. Interactively that is a nice-to-have, because a human reads the diff before it lands. Here there is no such human: the review *is* the only thing standing between this run and the default branch, which is the same reason Step 1 forces a pull request in the first place.

The swarm's completion notification wakes you exactly as the monitor's does. When it is the swarm that woke you, its confirmed findings are a new source of review feedback — go to Step 6 and let them enter the loop where a bot's threads do.

**The swarm runs once per run, not once per round.** It reviews the diff as first pushed, and re-running it after every round would spend a fleet re-reviewing code it has already passed. One re-run is justified when a round changed the shape of the change rather than patching it — a redesign, not a fix. More than one is not.

**Never report a change request as ready while a review you commissioned is still running.** The user reads "green, mergeable, no reviewer configured" as "this is waiting on me" — and on a repository with no reviewer of its own they are right to read it that way. So they merge it, and the review's findings land afterwards with nowhere to go.

That is not a hypothetical. A run reported a pull request as `MERGEABLE/CLEAN`, said the forge's reviewer could not run in that repository, and then yielded the turn with the substitute review still in flight. The user merged it, which was the correct reading of what they had been told, and the findings then needed a second change request. **The run caused that, not the user.**

So while a review is outstanding: either say nothing about mergeability, or say in the same breath that it is not ready and why. One line is enough — *"holding this until the review I started comes back."* And never describe an absent reviewer without naming what is standing in for it and when that will report.

If `review-code` errors or is not installed, record that in the run notes and continue on the forge's reviewer alone. A missing swarm degrades the review; it never stops the run.

When `--review` resolves to `false`, skip this step in silence — do not mention the swarm you did not run, do not offer it, and do not treat the forge's reviewer as a lesser substitute in the run notes. It is the review this run was asked for.

## Step 6: The Review Loop

Each time the watcher wakes you, gather the current state — PR state, pipeline status, approvals, unresolved threads — and then branch **in this priority order**. The ordering is not arbitrary and is the most commonly botched part of this flow:

> **Review comments outrank CI, always.** Addressing comments means pushing, and every push starts a new pipeline. Waiting for a red or running pipeline before handling open threads throws away a complete CI run, every time.

1. **Unresolved threads exist, or the Step 5b swarm has reported confirmed findings** (whatever the pipeline is doing) → invoke `fix-feedback --autonomous` with the `Skill` tool. It takes both sources as one queue: its Mode B reads the swarm's findings out of the conversation, and its Step 3b posts every finding the pull request does not already carry as an anchored comment *before* fixing any of them — so a swarm finding becomes a thread on the pull request like any other, and survives this run. If the pipeline has also failed, diagnose it in the same pass and fold the fix into the **same push** — never push twice. Then return to the watcher.
2. **Pipeline failed, no open threads** → Step 7.
3. **Approved and green, with every review this run commissioned already reported** → Step 8. Approved and green while the Step 5b swarm is still in flight is **not** this branch — that is branch 5, keep waiting. On a repository with no infrastructure plan this distinction costs one wait; on one with a plan, Step 8's gate depends on it.
4. **Approved, pipeline still running** → keep waiting.
5. **No verdict yet** → keep waiting. Do not babysit jobs unrelated to the review.

**Before waiting on a verdict, confirm the reviewer can actually run in *this* repository.** Step 0's values are read from one machine-wide config, so `review_bots` and `review_job` are whatever the user's main repo uses and say nothing about the repo this run is in. Check that the job exists here — look for `review_job` by name in the repository's own CI configuration, and confirm the pipeline running on this PR lists it among its jobs — before branch 5 can ever be correct. A configured reviewer with no such job in the repository produces a verdict that *cannot arrive*, and branch 5 then waits forever on it. The same goes for the forge's own approval verdict: where the repository has no approval rule configured it stays permanently empty, so an empty verdict is not evidence that review is outstanding. When the reviewer cannot run here, say so once and substitute a review you perform yourself, sized to what the change actually contains — then merge on green CI plus that review. Never report a reviewer as silent when it was never installed.

Two facts that look like failures and are not:
- **A push revokes approval and re-triggers the review.** That is the loop working.
- **Replies alone do not trigger a fresh review.** If a round produced only replies and no commits, there is nothing to push and therefore no new pipeline. Re-run the `review_job` to request a new verdict. Assigning the bot as a reviewer in the forge UI does nothing when the review runs as a CI job. If `review_job` is empty, say so and wait for a human instead.

**Cap the loop at `--max-rounds` rounds with the same thread** — the value Step 0 resolved, which an amendment may have moved since. Ping-ponging with a bot past that point is a sign the disagreement is real; escalate per Step 10 rather than continuing.

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

### A green plan is not a reviewed change

**The review has to have passed before the apply comment goes up.** A successful plan says the configuration is valid and shows what would change; it says nothing about whether that change should happen. The apply is the step that touches real infrastructure and the least reversible thing this run does — a destroyed resource, a recreated database or a rotated credential is not undone by closing the pull request afterwards. So the apply waits on the same review the merge waits on, and it waits on it **first**, not alongside it.

Posting the apply comment requires all of these. Check them in order, and check them again after any push, since a push revokes the approval and re-triggers the review:

1. **Every review this run commissioned has reported.** The forge's reviewer has produced a verdict, and — where `--review` resolved to `true` — the Step 5b swarm has finished. Both where both are relevant. A swarm still in flight is a review that has not reported, however green the plan and the pipeline are.
2. **The verdict is a pass**, not silence. An approval, or a review whose findings are all resolved. A verdict that cannot arrive is not a pass either: where Step 6 established that the configured reviewer is not installed in this repository, that review does not exist and condition 4 governs.
3. **No open feedback is left on the change.** No unresolved reviewer threads, and every confirmed swarm finding either fixed or answered on its thread. An open finding is feedback that may change what the plan does, and applying first spends the review.
4. **Where no review of any kind was available, review it yourself before applying.** Both absent — no reviewer installed here and `--review false` — means nothing has read this change but the bot that planned it. Do the review yourself, as Step 6 already requires when the configured reviewer cannot run: read the plan output directory by directory, read the diff against what the plan says it will create, change and destroy, and record in the run notes that it was your own review and what you checked. Then apply. **Never apply on a green plan with no review of any kind behind it** — that is the case this gate exists for.

A plan that would **destroy or recreate** anything is a Step 10 escalation whatever the review said. Raise the question there rather than settling it inside your own review.

**`--merge false` does not switch this step off.** The gate is the review, not the merge: on an infrastructure change, landing it means apply *then* merge, so once the review has passed the apply happens and Step 9 then holds the merge for a human. What `--merge false` holds back is the merge.

In a stack, each member clears its own gate. A predecessor's review says nothing about this change.

### Running the apply

Collect every directory the bot reported a plan for using `iac_plan_marker`. Run the apply by posting the comment the bot expects, once and idempotently. Then wait — via the watcher, not a sleep loop — until **every** planned directory has reported `iac_apply_marker`.

- Every planned directory shows the apply marker → Step 9.
- An apply reported an error → **stop, do not merge, and escalate.** A failed infrastructure apply can leave partial state, and that needs a person.
- Nothing yet → keep waiting.

The gate also sits after the forge's own approval requirements for a practical reason on top of the review one: the bot will usually refuse to apply before the PR meets them.

## Step 9: Merge

**Check `--merge` before anything else in this step.** When it is `false`, this step is where the run ends: the pull request stays open and unarmed, and you go straight to Step 11 to report. Do not merge, do not enable auto-merge, and do not ask whether they have changed their mind — the flag was set before the run started precisely so that nobody has to be available now. Say in one line that the pull request is green, reviewed and ready, held unmerged per `--merge false`, and give the link.

Everything below applies only when `--merge` is `true`.

### Re-read the verdict here, as late as possible

**The state Step 6 gathered is already stale.** A reviewer can report between your last read and the merge call, and that window is exactly as long as this step takes. Observed on this repo: the reviewer requested changes 77 seconds before the merge, after the last state read, and the merge went through anyway. Nothing in Step 6 could have caught that, because the event had not happened yet when Step 6 ran.

So read the review verdict and the open threads **again, in this step**, in the last call before the one that merges. Two fields, and conflating them is what went wrong:

- **A review job going green is not an approval.** `review_job` passing means the reviewer *ran*. The verdict is a separate field — ask the helper's `help` for the one this forge uses — and a green check beside a rejecting verdict is the shape this failure takes. It looks like consent and is not.
- **Changes-requested blocks the merge outright**, however green the checks and however long the run has waited. An *empty* verdict is a different thing and is not blocking where the repository configures no approval rule (Step 6). Those two readings must never collapse into "no approval yet, carry on".

A verdict that blocks sends you to **Step 6 branch 1** — it is review feedback and goes through `fix-feedback` — never to Step 11 and never to the merge. If the merge has already landed when you notice, say so plainly and do not revert it; the recovery is a follow-up change, per Step 4b.

**Read the verdict from the status call, not from the thread list.** A reviewer can submit a blocking review with an **empty body**, and `pr-reviews` drops empty-bodied reviews by design — so the thread list shows one ordinary inline comment, `mergeable_state` reads `clean`, and the only trace of the block is the `review_decision` field. Observed exactly that way on this repo. Use the helper's review-list subcommand (`pr-review-list`) when you need the reviews themselves with their ids and states; `pr-reviews` is for threads.

### A blocking verdict is a problem to clear, not a reason to stop

**Handing the user a button to press is not an escalation — it is the run giving up one step from the end.** This went wrong exactly once and must not again: a run drove a change to three green checks, got a single review finding that was *provably false*, rejected it with the evidence, then stopped and asked the user to dismiss the review by hand. Everything hard was already done. The user was away from the terminal, which is the entire premise of this skill, and the thing they came back to do took one click.

So when a verdict blocks, first decide whether the **finding** is right, because that is the only question that matters:

- **The finding is right, or you cannot show it is wrong** → it is review feedback. Step 6 branch 1, through `fix-feedback`, and fix the code. A finding you merely dislike is a finding you fix.
- **The finding is wrong, and you can prove it** — the claim is contradicted by the repository, by the diff, or by this change's own CI — then the verdict is stale and clearing it is yours to do. Answer it on the thread first, with the evidence, so the reasoning is on the record where a human reads it. Then work down the ladder below and keep going until one rung works.

Ask the helper's `help` for what this forge actually offers, and take the first rung it has:

1. **Re-run the review job** (`rerun-check`). Often answers `not rerequestable`, which is not the end of the ladder.
2. **Re-run the whole workflow run** (`rerun-workflow`). A check run and its workflow run are different objects, and the second is re-runnable when the first is not.
3. **Re-request the review** (`request-review`). This fires a reviewer whose workflow triggers on `review_requested` — check the repository's own trigger list rather than assuming it does not.
4. **Dismiss the stale review** (`dismiss-review`), with a message naming the evidence that disproves it. The thread, your reply and the dismissal message all stay on the change request, so the judgment is auditable rather than hidden.

Three hard limits on that ladder:

- **Never dismiss a finding you have not disproved.** Dismissal is the assertion that the reviewer is factually wrong about this code, and making it because the verdict is inconvenient is the one abuse of this section that would be worse than stopping. If you cannot point at the repository, the diff or a CI log, you do not have the proof, and it is an escalation.
- **Never push an empty or no-op commit to shake the verdict loose.** It pollutes the history of a change that did not need it, and rung 2 or 4 does the same job honestly.
- **Where the helper has no rung at all** — no re-run, no re-request, no dismissal — the capability is absent on this forge and *that* is the escalation. Say which subcommands you looked for, per the empty-value rule in Step 0.

Record the clearing in the decision ledger either way: which rung worked, and the evidence the finding was wrong.


Check `require_human_approval` first. When it is true, a review bot's approval **is not sufficient** — wait for at least one human approver. The user driving this run counts as a human; other bots do not. This is the one gate autonomy never waives, and it is the reason this skill is safe to leave running.

- **Infrastructure repos** (the Step 8 gate applied): merge **directly**. Never enable auto-merge here — auto-merge fires the instant the pipeline is green and can beat the apply, merging a plan that was never applied.
- **Everywhere else**: enable auto-merge (squash). This is what "as soon as possible but only as soon as appropriate" means in practice — the forge merges the moment its own conditions are met, with no polling and no race.

Then keep watching until the state is actually `merged`. Auto-merge can be cancelled by a failing pipeline or a new push, so arming it is not the same as it having happened.

If the merge is refused, report the exact blocker. Rebase if the forge says the branch is behind; surface anything else.

### 9a. Delete the source branch

Once the state reads back as `merged`, delete the branch from the remote:

```bash
git push "$DEFAULT_REMOTE" --delete "$BRANCH_NAME"
```

**This is part of merging, not tidying up afterwards.** A merged branch left on the remote is not cosmetic. `wtclean` decides a worktree is finished by its branch's upstream being **gone**, and that is its only signal — so a surviving remote branch means the worktree, the local branch and the whole checkout sit there indefinitely, and the user ends up pruning by hand the thing the run was supposed to finish. Observed exactly that way: three merged change requests, three branches still on the remote, and `wtc -y` reporting nothing to remove.

Five rules:

- **Only after the merged state has been read back.** Never alongside arming auto-merge, and never on a refused, cancelled or still-pending merge. Until the merge actually lands, that branch is the only copy of the work.
- **Already gone is the goal, not a failure.** The forge may have done it first — a change request here is opened with its remove-source-branch flag set where the forge has one, and a repository may carry its own delete-on-merge setting. `remote ref does not exist` means the job is done; report it that way rather than as an error.
- **Only this run's own branch.** Never the default branch, never a branch belonging to another change request, never a branch this run did not push. Rule 5's one-branch scope covers the delete exactly as it covers the push.
- **In a stack, one member's branch is the next member's base.** Delete it only once no open change request targets it. Where one still does, retarget that change request at the default branch first: some forges do that themselves when a base branch is deleted and some leave the dependent change request pointing at nothing, and *some* is not a thing to rely on. Step 10 merges in order, so in the normal case the successor has already merged or been retargeted by the time this runs.
- **The worktree you are standing in is not yours to remove here.** Deleting the remote branch is what lets `wtclean` see it; **Step 10d** then runs that cleanup from the main working tree, where the finished worktree is no longer the one under your feet. Never remove it from inside it.

**A human who merges mid-run leaves the same branch behind.** Where Step 4b finds the change request already merged by somebody else, delete the source branch the same way, under the same five rules.

**On `--merge false` nothing is deleted**, because nothing was merged. Say in the Step 11 report that the branch stays until whoever merges it deletes it — and where the forge has no per-change-request flag for this, name its repository-level delete-on-merge setting as the fix, so the user changes one setting once rather than deleting a branch per change request.

Then go to **Step 10b**. The merge is not the end of the run: the change has not reached anything yet, and the local checkout still holds the worktree and branch it was built on — Step 10d reclaims those once the deploy question is settled.

## Step 10: Several Pull Requests, In Order

When the work splits across more than one PR:

**Name them so the relationship is obvious at a glance.** Share a prefix and lead with an ordinal:

```
dylan/PLAT-3535/01-add-registry-loader
dylan/PLAT-3535/02-migrate-call-sites
dylan/PLAT-3535/03-delete-legacy-path
```

A reader scanning the branch list must be able to tell these three belong together, and in what order, without opening any of them. Cross-link them in each description: what it depends on, and what depends on it.

**Arm them in order, and as early as possible.** Record the intended order and each PR's dependencies in `~/.claude/autopilot/<run>/stack.json` so the sequence survives a session restart. **That path is outside the repository on purpose:** the machine-wide ignore file covers only `**/.claude/settings.local.json`, so an in-repo `.claude/autopilot/` file shows up as untracked in `git status` and a run that stages broadly can commit it. It also sits beside the pause state, so a resumed run finds both kinds of run state in one place. Then:

- Only the head of the stack is eligible to merge. Take it through Steps 6–9 normally.
- For each successor, arm a watcher on its predecessor's merge state. When that fires: rebase the successor onto the updated target, let its pipeline re-run, and only then take it through the merge gate.
- **Never arm auto-merge on a PR whose predecessor has not merged.** Auto-merge fires on the forge's conditions, which do not know about your ordering, so arming early merges things in the wrong order.

The principle: a step is armed the instant its precondition is genuinely satisfied, and not one moment before. Waiting longer wastes the user's time; arming earlier breaks the ordering.

**`--merge false` applies to the whole stack, not just its head.** Take every PR to green and reviewed, cross-linked and in order, then leave all of them open and unarmed. A stack is exactly where this is easiest to get wrong: merging the head "to unblock the rest" is still a merge the user asked you not to make, and it is the one that cannot be undone.

## Step 10b: Verify the Deploy

Runs once the change has actually landed on the default branch — by merge, or by a `--branch default` run's push. Skip it when Step 0b established that nothing deploys.

**The rule that carries this whole step: verify the new revision, not that something succeeded.** Every subtle post-merge failure has the same shape — something went green, about the wrong commit. A default-branch pipeline that passed for the commit before yours. A rollout that reported success because the manifest never changed. A GitOps application sitting Healthy on the revision it synced an hour ago. A mutable image tag that let the workload restart onto the same old image. Every one of those is indistinguishable from a good deploy if you are standing one step back from it.

So **every check is tied to the commit that landed.** Resolve that SHA once, and make each check answer *is this SHA what is now running* rather than *did a job pass*. Where a signal cannot be tied back to the SHA, say so and treat the result as unverified — not as confirmation.

Arm a `Monitor` in the turn the merge confirms. Never a sleep loop, never an in-turn poll, exactly as Step 5. Poll remote APIs no faster than every 60 seconds, tolerate a failed request so one blip cannot kill the watch, and bound the watch with the budget from Step 0b. **Every terminal state emits a line** — same reason as Step 5: a watch that only speaks on success is indistinguishable from a watch that died.

Five terminal states, and the difference between the last three is most of this step's value:

| State | What it means | What to do |
|---|---|---|
| **Confirmed** | The signal names the commit that landed, and the target is healthy | Report it in the ping with the evidence, not just the word |
| **Failed** | The deploy ran and did not work — pipeline red, rollout stuck, workload not becoming ready, image pull failing, apply errored | **Ping immediately** with what failed and where to look |
| **Waiting on a human** | The deploy is gated: a protected environment, a manual job, an approval step | Ping with what to click. This is not a failure and must not be reported as one |
| **Cannot observe** | No access to the signal — no cluster context, no token, no VPN, or Step 0b recorded the path as unknown | Ping saying the change is merged and the deploy is **unverified**, naming the check a human should run |
| **Timed out** | The budget expired with no terminal answer | As cannot-observe: merged, unverified, and say how long you waited |

**Never report a deploy as successful because you could not watch it fail.** Cannot-observe and timed-out are not success. Collapsing either into "done" is the single outcome that makes this step worse than not having it, because the user stops checking on the strength of something that was never established.

### Never remediate — warn

A failed deploy gets a ping and nothing else.

- **No rollback, no revert, no re-deploy.** Reverting a merge is itself a production change, with its own blast radius, decided by something that has just demonstrated it does not understand the current state.
- **Never re-run a deploy job.** Step 7's retry classification is about CI jobs, which are expected to be idempotent. A deploy job is not, and a half-applied deploy run a second time can do what neither run would have done alone.
- **Never touch the runtime.** No restarting or deleting workloads, no scaling, no editing a live manifest, no forcing a sync.
- **Do gather evidence thoroughly**, since that is the part that actually helps: the failing job's log, the workload's recent events, the controller's sync status. The specifics go in the Step 11 report; the diagnosis goes in the ping.

### In a stack

Verify after **each** merge, not only after the last one. Every merge to the default branch fires its own deploy, so an intermediate failure is a real failure. **If an intermediate deploy fails, stop the stack** — do not merge the next change onto a default branch that is currently broken — and say that is why you stopped.

## Step 10c: Run the Deploy Yourself

Step 0b established whether a command is what makes this change take effect. If one is, and this session can reach the target, **run it.**

Do not end a run by handing the user a block of commands they could have watched you execute. This is the most common way an unattended run fails at being unattended, and the shape of the failure is particular: everything hard is already done, the report reads like completion, and the user discovers at the bottom that they have been given homework by something which had the credentials, the access and the authority to do the job. A merge is irreversible and this skill performs it without asking. A scripted, idempotent deploy is almost always *less* consequential than the merge that preceded it, so stopping short of it is backwards.

Run it when all of these hold, which is the normal case:

- Step 0b identified the command, and a read-only probe showed this session can reach the target.
- It is the repository's own documented deploy path, not one you composed for the occasion.
- It is idempotent, or this is its first run.
- It destroys nothing beyond what this change replaces.

Then verify per Step 10b, and report what you **ran** rather than what they should run.

**Ask first only for the specific hazards**: a step that interrupts other people, a one-way data migration, anything that spends money, or a target the change request never mentioned. **Ask with `AskUserQuestion` and wait for the answer.** This used to say to ask by pinging, which was incoherent — a notification cannot carry a yes, so the run either stalled on an answer that had nowhere to arrive or pushed on having merely announced itself. Say exactly what you intend to run, inside the question. Never hand over the commands and call it a hand-off.

**Report the side effects, because they are the part the diff does not show.** A restarted service and what it dropped, a cache cleared, a window where something was unavailable. "Restarted the server; no sessions were live" is the sentence that makes a deploy auditable.

If the command fails, that is Step 10b's **failed** state: gather the evidence, ping, and change nothing else. Never remediate.

## Step 10d: Reclaim the Local Checkout

**Runs only when `--merge` resolved true and the merge actually landed.** Nothing merged means nothing to reclaim: skip it in silence on `--merge false`, on a refused merge, and on a `--branch default` run that never had a change request.

The merge deleted the source branch from the remote (Step 9a), which is the signal `wtclean` reads — but reading it is somebody's job, and leaving it to the user means the worktree, the local branch and the checkout sit there until they next think to look. So the run finishes the job it started:

```bash
zsh -ic 'cd "$(git -C <main-working-tree> rev-parse --show-toplevel)" && freshen'
```

`freshen` pulls the default branch up to date and then runs `wtclean --no-fetch -y`, which removes every worktree whose branch is gone from the remote and deletes the merged local branches. A branch that was never pushed and is not in the default branch is left alone, so work in progress is never collected.

Four things about that command are load-bearing, and three of them are easy to get wrong:

- **Run it from the main working tree, never from the run's own worktree.** `wtclean` deliberately skips the worktree you are standing in — and on this run that is precisely the finished one. Resolve the main root first (`git worktree list` names it first, or `_wt_main_root` in the shell config) and `cd` there.
- **`freshen` is an interactive alias, so a plain `zsh -c` cannot see it.** `zsh -c 'freshen'` exits with `command not found`; it needs `zsh -ic` so the rc that defines it is read. An interactive zsh with no tty also prints `can't change option: zle` to stderr — that is noise, not a failure, and it is not worth suppressing the whole stream to hide.
- **Your working directory can be deleted underneath you.** If this run worked in a worktree, that worktree is what gets removed. `cd` to the main root *before* running the cleanup and stay there for the rest of the run; never `cd` back to the path you started in, and do not read a file from it afterwards.
- **It never fails the run.** A dirty worktree, a shell without the alias, a `freshen` that is not defined on this machine: report what happened in one line and go to Step 11. The change is already merged, so nothing here is on the critical path.

**Two failure modes have real workarounds, so reach for them before reporting a failure.** `freshen` is `pull --rebase` plus `wtclean`, and each half fails independently.

- **`freshen` refuses outright when the *main* checkout has any unstaged change** — `cannot pull with rebase: You have unstaged changes`. On a repo whose `vscode/settings.json` is symlinked into it that is the *normal* state, because the editor writes UI changes back as a tracked diff, so this fires on an ordinary run and it is never the run's change. Do not commit it, do not stash it: it is the user's. `git merge --ff-only origin/<default>` gets the pull done anyway, because ff-only refuses only when the incoming commits would overwrite the dirty file — and where the merged change did not touch it, it succeeds. Run the three parts separately: `git fetch origin --prune`, then `git merge --ff-only origin/<default>`, then `wtclean --no-fetch -y`. **The prune is not optional.** `freshen` inherits it from the `update` alias, so a fallback that drops it leaves every remote-tracking ref in place — `_wt_upstream_state` never reports `gone`, and the sweep reports `0 worktree(s) removed` while the finished worktree and its branch both stay.
- **`wtclean` cannot remove a worktree whose submodules were ever initialised** — `fatal: working trees containing submodules cannot be moved or removed`, and it aborts the whole sweep rather than skipping that one. `git submodule deinit --all -f` does **not** clear it: the gitlink stays in the worktree's index, so `git worktree remove` keeps refusing even with the submodule directory empty. The way out is `rm -rf <worktree>` then `git worktree prune` then `git branch -D <branch>` — but **only after confirming the work actually landed**, by grepping `git log origin/<default>` for the commit rather than trusting the merge reply. Anything that runs the repo's own installer or build inside the worktree can cause this, so expect it on a run that verified its change by executing it.

**Report what it reclaimed, not that it ran.** "Removed 2 finished worktrees and their branches; main up to date" is the useful line; "ran cleanup" is not. Where it removed nothing, say so — on a run whose branch never had a worktree that is the correct and common outcome.

## Step 11: Close the Loop and Ping

When the PR merges, when a `--branch default` run has pushed, or when you stop for any reason:

1. **Record it where the work lives.** On a ticket run, comment the PR URL and what shipped — **not the decision ledger**, which belongs in the description fold at 11.3 and must not be duplicated as a wall of text on the ticket as well. Anything noteworthy beyond those two is a line, not a section. A `--branch default` run has no PR, so record the pushed commit SHA and its forge URL instead. Work you deliberately did not do becomes its own ticket, linked back — never a buried bullet in a closing comment. Check whether the forge integration already moved the ticket before moving it by hand; that integration is asynchronous.
2. **Attach the diagram** when `--diagram` is true and the run opened a pull request. On a `--branch default` run the fix skill already produced it at its own diagram step, so do not produce a second one — carry the link it gave you into the report and the ticket comment. Invoke `changes-diagram` with the `Skill` tool and append its link to the PR description — or, on a `--branch default` run, carry the link in the report and the ticket comment, since there is no description to append to. Do this once the code has settled — a diagram of a branch that changed three more times is worse than none. **A failed or unavailable diagram never fails the run**: say so in one line and carry on.
3. **Append the decision record.** Take the scratchpad ledger, apply the filter and the budget from **The decision record**, and append it to the end of the change request description inside the collapsed `<details>` fold — one edit, after the diagram link. An empty ledger publishes nothing. **Never post it as a comment**: if the description edit fails, say so in one line and carry the ledger in the report instead.
4. **Ping the user.** Invoke the `ping` skill with the `Skill` tool. This is the **closing** ping — Step 0d already sent the opening one and armed the session, so this is a report rather than an announcement. It is the only message the user is guaranteed to read, so it carries what happened and whether anything is needed — a ping that says "done" wastes it. **It carries Step 10b's verdict in Step 10b's own words**: deployed and verified, deploy failed, waiting on a human, or merged and unverified. "Merged" alone is the one word that reads as finished while leaving out whether the change is actually running. **A `--branch default` run says so in the ping**: the change is on the default branch, unreviewed, and already live. That is what the user chose, and it is also the single fact most worth knowing on a phone.
5. **Name any signal that did not prove what it was meant to.** Where Step 0b's reading of the deploy path did not match what Step 10b actually observed, say so in the report in one line — the path you expected, the path it took, and which check turned out not to answer *is this SHA running*. A signal that looks authoritative and is not is the thing most likely to make the next run report a deploy it never saw, so it is worth naming even on a run that ended confirmed.

### When to stop and ping instead of continuing

Escalate — ping with a level of `question` or `blocked`, saying precisely what you need — when:

- A thread needs a product or policy decision the code cannot settle.
- An infrastructure apply failed, or would destroy something.
- **The deploy failed, or could not be verified** (Step 10b). A change that merged and did not come up is the most urgent thing this skill can discover, and it is never something to fix unattended.
- A merge conflict needs judgment about intent rather than mechanics.
- The same thread has reopened `--max-rounds` times.
- A fix would require changing a repository this run cannot reach.
- A test fails for a reason you cannot explain, and retrying has not settled it.
- `require_human_approval` is true and no human has approved after the pipeline has been green for a long time.

**Three of those are a question now, not an end.** Where you need one decision and the run could carry straight on with the answer — a product or policy call from a thread, a merge conflict whose intent is unclear, an apply that *would* destroy something — raise an `AskUserQuestion` and wait, per **Asking mid-run**. An answer given in thirty seconds from a phone beats a run that stopped and has to be restarted from a cold session.

**The rest genuinely end the run**, because asking does not help: a failed deploy, a failed apply, a test failing for a reason nobody can explain, a thread that has reopened `--max-rounds` times, a repository this run cannot reach. Each of those needs the user to *look* at something rather than choose between two options, and a question pretending otherwise stalls on a worse surface than a ping. Ping and stop. `require_human_approval` with nobody having approved yet is neither — it is a wait, and Step 9 governs it.

Stopping and asking are both reserved for this list. Everything else — surprising test failures, undecidable details, awkward trade-offs — gets the most defensible option, recorded, and the run continues.

## Important Rules

1. **Never hold the turn open.** Every wait is a `Monitor`, never a sleep or a poll loop. Several of these runs may be live at once, and each one that blocks costs the user a session.
2. **The approval gate is never waived.** When `require_human_approval` is true, a bot approval alone does not merge. Everything else in this skill is a judgment call; this one is not.
3. **Never blind-retry a failing job.** Read the log and classify it first. Twice the same way is a real failure.
4. **Comments before CI.** Always.
5. **This run owns exactly one branch** (or one named stack) — including when that branch is the default one. Never force-push, never amend a pushed commit, never act on a pull request this run did not open.
6. **Never override the fix skill's flags — but always honour an amendment.** `--merge` and `--max-rounds` are this skill's; every other flag was decided before this skill was reached, `--branch` included, and automation is what this skill adds rather than a second opinion on what the change should be. The one thing that does change a flag mid-run is the user saying so with `/autopilot <flags>`, and that is not an override, it is an instruction. When one arrives, change only what they named and leave the rest at its current run value.
7. **Capture every decision you made alone at the time you made it, and publish it exactly once.** The capture is a line in the local ledger; the publication is the collapsed fold appended to the description at Step 11.3. Never a comment, on the change request or on a thread. The record is what replaces the conversation, so it carries the reasoning and nothing about the process that produced it — see **The decision record** for what earns an entry and the budget it has to fit in.
8. **No comments in the code.** Autonomy does not relax it.
9. **An empty config value means the capability is absent, not that you should guess at it.** Never substitute a name you saw in an example for one the machine did not supply.
10. **The merge is not the finish line, and "merged" is not "deployed".** Step 0b works out how the change reaches production and Step 10b confirms it got there, tied to the commit that landed rather than to a job going green. Unverified is a reportable outcome — **never** upgrade cannot-observe or timed-out into success.
11. **Arm the notifications before the first unattended step.** A ping is the only thing that writes `armed_at`, and an unarmed session is silent through every permission prompt, question and failure in the run. Step 0d sends it once, on every route in — hand-off, direct, or a mid-run `/autopilot` amendment. Pinging only at the end arms the session at the exact moment it stops mattering.
12. **Pause on purpose; never run out mid-flight.** Read the quota from the `claude-usage` cache at step boundaries, never from the API, and pause at 85% of the session window. Journal the step, the next action and the ledger as you go, so the pause costs one write. A weekly, scoped or spend limit pauses and pings and **never** arms its own return — that window is the user's to spend.
14. **Never hand the user a command you can run yourself.** If Step 0b found the deploy and this session can reach the target, Step 10c runs it. A run that finishes with a block of commands for the user to paste has failed at the one thing it was for, and it fails in the worst way — looking finished. The same goes for anything else in reach: pulling a repo, restarting a service, installing a file on a box you already have access to, and reclaiming the worktree and branch the merge just finished with (**Step 10d**).
13. **A broken deploy is warned about, never fixed.** No rollback, no revert, no re-run of a deploy job, no touching the runtime. Gather the evidence, ping immediately, and stop. An unattended agent reverting production at 2am is worse than a bad deploy somebody has been told about.
