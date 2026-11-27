# MR Description Generator — Adversarial Draft Swarm

Produce a merge request description by making four reviewers with incompatible goals fight over it until they all sign off. A senior engineer argues for accuracy and completeness, an impatient reviewer argues for brevity, a novice argues for plain language, and a hawk-eyed manager hunts sentences that were generated rather than thought about. An editor referees and settles the through-line — the one sentence naming what this MR is about; a composing editor then builds the prose on that spine against a mechanically measured word budget; and a fact-checker confirms the result is true about the diff and lost nothing on the way.

**Parameter:** `$ARGUMENTS` — optional.

| Argument | Effect |
|---|---|
| *(none)* | Debate the changes on the current branch vs. the default branch, plus uncommitted work. |
| A git ref/range (`main`, `origin/main`, `HEAD~3`) | Diff against that base instead. |
| `--rounds N` | Cap the debate at N rounds (default `2`, max `3`). |
| `--quick` | One judging round plus a single repair pass if anyone blocks. Use for small changes — the repair is not re-judged, so the run reports non-unanimous. |
| `--one-shot [true\|false]` | Default `false`. `true` drops the debate entirely: one writer, then the budget and the fact-check. Bare `--one-shot` means `true`. |
| `--inline [true\|false]` | Default `false`. `true` launches **no workflow at all**: you write the description yourself, in this turn, against the same template, the same measured word budget and a fact-check you run yourself. Bare `--inline` means `true`. |

Parse the flags out of `$ARGUMENTS` **first**; whatever remains (if anything) is the git ref. `--rounds` and `--quick` set the `rounds` value passed to the workflow, and `--one-shot` sets `oneShot` — they are not part of the diff base, and feeding them to `git merge-base` produces a confusing failure. `--inline` sets nothing, because under it there is no workflow to set anything in — see **Step 2-INLINE**.

This skill uses the **Workflow** tool. Invoking it is an explicit opt-in to multi-agent orchestration — proceed without asking for further permission. A run is 15 agents when the panel accepts in one round, 20 at the default two rounds, and 26 at `--rounds 3` with no consensus and a factual correction. `--quick` is 15–16. **`--one-shot` is 4–6**, which is the point of it. **`--inline` is none**: no workflow is launched, nothing runs in the background, and the description exists before the turn ends.

### What `--one-shot` keeps, and why it keeps exactly that

`--one-shot` is not "the same skill with fewer agents". It removes the four-persona contest — the drafts, the cross-examination, and the judging rounds — and keeps the two phases that are **arithmetic rather than opinion**:

- **The budget.** `measure()` counts words and bullets in code. This is deliberate: the one time a writer here was trusted to respect a stated limit it produced 913 words while satisfying every rule it had been given, because "3 summary sentences" says nothing about sentence length. A one-shot description of a large diff is still a 320-word description.
- **The fact-check.** It reads the diff and the checkout and proves the claims are true. A single unopposed writer needs this *more* than a panel does, not less — nobody else read the text.

What you genuinely lose is the adversarial pressure: the skimmer forcing cuts, the novice forcing plain language, the hawk hunting generated prose. The sole writer is handed the veto table and told to apply all four, which is weaker than four reviewers who each actually hold one. So use `--one-shot` for routine work where the diff is small and the stakes are low, and let the panel run when the description is the thing a reviewer will lean on.

### What `--inline` is for, and what it still owes you

`--inline` is the setting for the run where the description is not the deliverable. The user wants the change request **open**, and a workflow of any size sits between the finished code and that open change request: even `--one-shot` returns a run ID and ends the turn, so the description — and the push, and the change request, and everything a caller does after them — arrives one completion notification later. `--inline` writes it in the turn it was asked for and the caller carries straight on.

What it gives up is every agent but you: no four-persona contest, no cross-examination, and **no independent fact-checker**.

What it still owes the reader is the part that is arithmetic rather than opinion, and it owes it *more* than a panel does, not less:

- **The template and the house rules.** The sections, their order, and the hard rules in the `HOUSE` block in [`workflow.js`](workflow.js) bind a hand-written description exactly as they bind a persona. The banned design-decisions section is the one that comes back when nobody is refereeing.
- **The budget, measured rather than estimated.** The one time a writer here was trusted to respect a stated limit it produced 913 words while satisfying every rule it had been given. You are that writer on this path. Count the words with the command in Step 2-INLINE; do not eyeball them.
- **A fact-check against the diff.** Nobody else is going to read this text before a reviewer does, so you read it against the hunks yourself, claim by claim.

Reach for it when the diff is small, or when the change request being open is worth more than the description being argued over. Let the panel run when the description is the thing a reviewer will lean on to read the diff.

## Who reads this

Write for a real human reviewer who **did not write this code, does not have full context on the initiative it's part of, and gets overwhelmed by a jargon-y wall of text.** They may not fully understand the architecture being modified. They should be able to read the description top to bottom, once, and come away able to state what the MR does and why — without opening a design doc, a ticket, or a sibling MR.

That reader is the whole point, and they are the reason this skill is a fight rather than a single pass: the four things that reader needs — that it's accurate, that it's short, that it's comprehensible, and that a human actually thought about it — pull against each other, and a single writer quietly trades away three of them without noticing. The personas exist to make each trade explicit and contested.

What that reader needs above all is a **story, not an inventory**. A list of true facts about a diff, each individually defensible, leaves them knowing ten things and understanding none — they cannot tell which three matter or why these files changed together. So the description is built on a through-line: one sentence naming what this MR is about, chosen before any prose is written, with every part of the text earning its place against it. Selecting for that spine is the synthesis editor's job, rendering it is the composing editor's, and the novice persona holds the veto when the result still doesn't hang together.

## Step 1: Assemble the Context Packet

**Subagents cannot see this conversation.** They get exactly what the workflow prompt contains and nothing else. Everything the debate needs must be packed into `args` here — this is the single most important step in the skill, and skipping part of it produces four confident drafts about code nobody changed.

### 1a. Gather the diff

> **Never launch with a stand-in `diff`.** The script's guard only rejects a missing or
> empty string, so `"diff": "PLACEHOLDER"` (or a "…filled in below" note) sails straight
> through and burns a full 15-agent run describing nothing. Assemble the real diff text
> FIRST and paste it into `args` before you write the `context` digest — the digest is the
> long part, and the temptation is to stub the diff and "come back to it". If the diff is
> awkward to transcribe, inline the production files verbatim and pass a `[TRUNCATED: …]`
> marker naming the omitted test file plus its path, so agents can `Read` it. Untracked new
> files do NOT appear in `git diff`, so capture each with
> `git diff --no-index /dev/null <path>` rather than staging them — a worktree-isolated
> session should not touch the index just to build a description.

Resolve the base first, one command at a time, and **write the merge-base commit down**: every command after it takes that SHA literally, in place of `<merge base>`.

```bash
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'
```

Nothing printed means no `origin/HEAD`, so fall back. The `2>/dev/null` is what makes that test true: without it a clone whose `origin/HEAD` was never set prints `fatal: ref refs/remotes/origin/HEAD is not a symbolic ref`, and the exit status says nothing either way because a pipeline takes `sed`'s.

```bash
git branch -r | grep -E 'origin/(main|master)$' | head -1 | sed 's@.*origin/@@'
```

Still nothing and the default branch is `main`. The base is the skill's own argument with `--rounds N` / `--quick` stripped out, or the default branch when that is empty:

```bash
git merge-base HEAD origin/<base>
```

A failure there means `<base>` is not a remote branch — retry it as `git merge-base HEAD <base>`, and use `<base>` itself if that fails too. Then take the three inputs:

```bash
git --no-pager diff --name-status <merge base> -- .
```

```bash
git --no-pager diff <merge base> -- .
```

```bash
git rev-parse --show-toplevel
```

`--name-status` is `files`, the plain diff is `diff`, and the toplevel is `repoRoot`.

**One command per call, because the worktree isolation guard refuses a multi-line one naming `git`.** The single-line equivalent of the same work is accepted, so the refusal is about the shape rather than the content, and the block this replaced was nine coupled statements. Shell state does not survive between calls either — only the working directory does — so the merge base cannot be carried in a variable and has to be written into each later command as a literal. That was already true of the block this replaced: it set `MERGE_BASE` here and Step 2-INLINE read it two steps later from a shell that had never seen it.

- **Empty diff, but the conversation contains pasted code or diffs:** use that as `diff` and say so in `context`.
- **Empty diff and nothing in the conversation:** tell the user "No changes found — run `/changes-branch` first or paste the changes you'd like described," and stop.
- **Huge diff** (>4000 lines): pass the name-status list plus the diffs of the most substantive files, and note the truncation in `context`. Agents can `Read` the rest.

### 1b. Distill the conversation into `context`

This is the part only you can do — it is the reason the description isn't just a diff summary. Write a plain-prose digest containing:

- **The problem.** What breaks or falls short today, concretely, with the real numbers or names if they came up. This is the highest-value thing in the packet; the diff cannot supply it.
- **Intent.** What the user said they were trying to achieve.
- **Decisions made in the conversation** and the reasoning behind them — especially where an obvious-looking alternative was rejected.
- **Ticket / initiative context** if any (identifier, **its URL**, title, one line of what the initiative is for). Pass the URL even when it looks obvious — without it the description falls back to a bare `PLAT-1234`, and two MRs from the same week end up formatting the same ticket two different ways.
- **Anything a sibling MR established that this one leans on** — a limit, a cap, a failure mode, a number. The reader of *this* description has not read that one, so the packet must carry the fact itself, not a pointer to it.
- **Deploy-shaped facts**: a new required config key or env var, a changed helm value, a changed schedule or timeout an existing deployment must pick up, a migration, a flag that gets flipped elsewhere, an ordering against another merge. These are the facts most often known only to you and never visible in the diff.
- **Anything already known to be out of scope, deferred, or following in a later MR.**
- **What you are unsure about.** Say it plainly in the packet. A stated gap makes the fact-checker suspicious in the right place; an unstated gap gets confidently invented.

If the conversation is thin, say so in `context` rather than padding it. Never invent rationale to fill the packet — the debate will polish an invention into something that reads exactly like a fact.

## Step 2-INLINE: `--inline` — write it here, no workflow

**This step replaces Steps 2 and 2b.** Do not call the **Workflow** tool, do not print a run ID, and do not end the turn waiting for anything: the flag exists so that the description is in hand before this turn is over. Read the `HOUSE` block in [`workflow.js`](workflow.js) for the template and the hard rules — it is the one copy of them, and this is the only step that reads that file rather than passing its path to the **Workflow** tool.

1. **Fix the through-line first, in one sentence, before writing any prose.** One sentence naming what this change is about. Everything in the text then earns its place against it. Written the other way round — prose first, spine inferred afterwards — produces an inventory of true facts about a diff, which is the failure this skill exists to prevent and the one a lone writer walks into fastest. If you cannot write that sentence, say so to the user: the branch may want splitting.

2. **Write the description against the `HOUSE` block in [`workflow.js`](workflow.js).** `## Summary`, then `## Changes`, then `## Testing` and `## Rollout` only where they clear the bar stated there. Run the Rollout trigger list against the diff rather than consulting your instinct — a new config key, a changed helm value, a changed schedule or timeout a running deployment must pick up, a migration, a feature flag, a destructive operation this change makes possible, or a required ordering against another merge.

3. **Measure it. Do not estimate it.** Write the text to the scratchpad and count it. The tiers and the counter below are a port of `measure()` in Step 2's script — if the tiers there move, move them here too:

Take the two sizes first, as their own commands:

```bash
git --no-pager diff <merge base> -- . | wc -l
```

```bash
git --no-pager diff --name-status <merge base> -- . | grep -c .
```

Then count the text, with those two numbers written in literally where `<diff lines>` and `<files>` stand:

```bash
python3 - <your session scratchpad>/description.md <diff lines> <files> <<'PY'
import re, sys
lines = open(sys.argv[1]).read().split('\n')
diff_lines, files = int(sys.argv[2]), int(sys.argv[3])
size = 'large' if diff_lines > 1200 or files > 12 else 'medium' if diff_lines > 300 or files > 4 else 'small'
total, summary_cap, bullet_cap, changes_cap = {
    'small': (170, 60, 4, 100), 'medium': (250, 80, 6, 150), 'large': (320, 80, 8, 200),
}[size]
count = lambda s: len([t for t in s.split() if not re.fullmatch(r'[—–*+\-:;,.]+', t)])
has = lambda n: any(l.strip().lower() == '## ' + n for l in lines)
def section(name):
    i = next((i for i, l in enumerate(lines) if l.strip().lower() == '## ' + name), -1)
    if i < 0: return []
    rest = lines[i + 1:]
    return rest[:next((j for j, l in enumerate(rest) if l.strip().startswith('## ')), len(rest))]
bullets = []
for l in section('changes'):
    if re.match(r'^\s*[-*]\s+', l): bullets.append(re.sub(r'^\s*[-*]\s+', '', l).strip())
    elif l.strip() and bullets: bullets[-1] += ' ' + l.strip()
summary = ' '.join(section('summary')).strip()
sentences = [s.strip() for s in re.split(r'[.!?]+(?:\s+|$)', summary) if s.strip()]
cap = total + (25 if has('testing') else 0) + (30 if has('rollout') else 0)
body = count('\n'.join(l for l in lines if not l.startswith('##')))
print('%s change · %d diff lines · %d files' % (size, diff_lines, files))
print('total    %d / %d' % (body, cap))
print('summary  %d / %d words, %d / 3 sentences' % (count(summary), summary_cap, len(sentences)))
print('changes  %d / %d bullets, %d / %d words' % (len(bullets), bullet_cap, sum(map(count, bullets)), changes_cap))
for i, s in enumerate(sentences):
    if count(s) > 30: print('OVER: summary sentence %d is %d words, cap 30' % (i + 1, count(s)))
for i, b in enumerate(bullets):
    if count(b) > 25: print('OVER: bullet %d is %d words, cap 25 — %s' % (i + 1, count(b), b[:60]))
PY
```

**Three commands rather than one, because this step runs inside a worktree on most invocations.** The worktree isolation guard refuses a command naming `git` that it cannot statically verify, and a **multi-line** one is exactly that: the single-line equivalent of the same work is accepted, so the refusal is about the shape and not the content. The whole block as one call was refused, which is how a step whose own instruction is *do not estimate it* came to have no runnable way to measure. Shell state does not survive between calls either — only the working directory does — so the counts cannot be held in variables across the split and have to be written into the third command as digits. The `description.md` path is written out for the same reason.

**Over budget means cut, and then measure again.** The caps are ceilings, not quotas: landing well under one is not a description with something missing. When the text will not fit, the fix is removing undefined terminology and abstraction, never compressing explanations into denser jargon.

4. **Fact-check your own claims against the diff.** Go claim by claim and point each one at a hunk, a file, or a line in the checkout. A claim you cannot point at comes out — not softened, out. This is the step with nothing standing behind it on this path, and the one failure mode of `--inline` is a description that reads well and is wrong about the diff, with nobody else having read either.

5. **Present it per Step 3**, with the inline record.

## Step 2: Run the Debate

Call the **Workflow** tool with `scriptPath` set to this skill's `workflow.js`. The tool does not expand `~`, so resolve the absolute path first:

```bash
echo "$HOME/.claude/skills/changes-description/workflow.js"
```

Pass `args` as a **real JSON object, never a JSON-encoded string**:

```json
{ "diff": "<unified diff>", "files": "<name-status list>", "context": "<the Step 1b digest>",
  "defaultBranch": "<DEFAULT_BRANCH>", "repoRoot": "<REPO_ROOT>", "rounds": 2, "oneShot": false }
```

`rounds` is `2` by default, `1` under `--quick`, or the number given to `--rounds` (the script clamps it to 1–3 regardless).

`oneShot` is `false` unless `--one-shot` was passed. Pass it as a real **boolean**, not the string `"true"` — the script tests `A.oneShot === true`, so a string silently runs the full debate and the user gets a 20-agent run they asked not to have. When it is `true` the script forces `rounds` to `0` itself; do not also pass `--quick`.

A JSON-encoded string makes every `args.x` lookup `undefined`; the script hard-throws on missing `diff` or `context` rather than letting four drafters write a description of nothing.

**Pass the script by `scriptPath`, pointed at `workflow.js` beside this file. Never point `scriptPath` at a Workflow snapshot, and never pass `resumeFromRunId`.** The distinction is a directory, and it is the whole rule:

| Path | Verdict |
|---|---|
| `$HOME/.claude/skills/changes-description/workflow.js` | the live script — **this is the one to pass** |
| `…/<session>/workflows/scripts/changes-description-wf_<id>.js` | a frozen snapshot — **never** |

A snapshot is what a call that passed `script` inline leaves behind, and it is frozen at the moment it was taken. Replaying it silently runs whatever version of this pipeline was current *then*, discarding any correction made since, while the run looks entirely normal. That has already happened once: a fixed skill bypassed by a `scriptPath` pointing at the pre-fix snapshot from the very run it was fixing.

`workflow.js` is the opposite of that, and the difference is not a matter of care. It is the only copy of the script, it is the one under version control, and the tool **re-reads it on every invocation** — editing the file and re-invoking the same path is the documented way to iterate on a workflow. So the failure the old ban existed to prevent is prevented *by construction*: there is no pre-fix copy to replay, because there is no copy. A `scriptPath` invocation also writes no snapshot of its own, so it cannot manufacture the thing being banned.

**The diff still has to be re-sent on every launch, and that cost is real and unavoidable.** `args` must be inlined into the prompt: the Workflow tool has no file-based form for it, and workflow scripts have **no filesystem access at all**, so there is no way to hand the swarm a path to read the diff from. Measured on a real run, a 16KB diff is about 4k tokens per launch. Carrying the diff behind a path and letting each agent read it would remove that, and it is **deliberately not done** — the resume cache is content-addressed over each agent's whole prompt, which is exactly what makes a branch that moved while paused void the cache instead of replaying findings about code that no longer exists. Behind a path the cache would stop noticing.

So a re-run pays for its `args` and nothing else, and `/workflow-resume` is the route: it pairs `resumeFromRunId` with this skill's live `workflow.js` and recovers the original `args` from disk with `workflow-runs.py args <run_id>`. Resuming any other way is the bug above.

## Step 2b: Surface the Run ID for `wfwatch`

**Skip this step under `--inline`** — no workflow was launched, so there is no run ID, nothing to watch, and nothing to wait for. Never print a `wf_` block for a run that did not happen.

The **Workflow** tool runs the debate in the background and its tool result includes a **run ID** (`wf_…`). The user has a shell function, **`wfwatch`** (defined in their `.zshrc` / `.bashrc`), that live-tails a workflow's progress by that ID — the debate is worth watching, since the round-by-round objections show exactly which persona forced which sentence.

**In the same turn that launches the workflow — before you yield — print the run ID in a copyable form with the exact command:**

```
🥊  changes-description debate launched — run ID: wf_ab12cd34
    Watch it live in another terminal:  wfwatch wf_ab12cd34
    Single snapshot instead:            wfwatch wf_ab12cd34 --once
```

Use the **actual** `runId` from the Workflow tool result verbatim — `wfwatch` resolves the journal by exact ID.

**Then end your turn — never block the session on the swarm.** The `Workflow` tool has already returned: the run continues in the background and a task notification re-invokes you when it finishes. So print the block above, say the debate is running, and yield, which leaves the user free to keep submitting prompts for the whole run. Do not hold the turn open to wait for it — no `TaskOutput` on the workflow's task, no `Monitor`, no `ScheduleWakeup`, no reading the journal or running `wfwatch` yourself on a loop, no sleep, and no filler tool calls to pass the time. None of that makes the result arrive sooner, and all of it costs the user their session for the length of a full swarm. If they send other prompts meanwhile, answer them normally and stay responsive. The completion notification is the **only** thing that resumes this skill; when it arrives, continue with Step 3.

## Step 3: Present the Result

**Output `description` inside a single markdown code block** (triple backticks, no language tag) so the user copies raw markdown straight into GitLab's description field. Nothing else goes inside that block — no preamble, no notes, no debate.

Under the code block, print at most five lines of debate record, and only what is true:

```
through-line: the 250-binding cap is what blocks new BigQuery grants; this ships the tool that measures the move off it
large change · 2 rounds · not unanimous · 4 of 4 judges reported · 187 words, 5 of 8 bullets · within budget · 1 factual correction
  r1 · skimmer blocked "Testing" · novice blocked "resource-set"
  r2 · senior blocked "runs on every deploy" — outstanding
  unresolved: senior wanted the flag-flip ordering spelled out; cut as not reviewer-actionable
```

Rules for that record: it is a log, not a defense. Do not justify the text, do not offer to lengthen it, and do not surface non-blocking notes — they were ignored on purpose.

**Print `throughLine` first**, on its own line above the record. It is the one-sentence spine the whole description was built on, and it is the fastest way for you to catch a run that went wrong: if the spine is not what this MR is about, nothing below it will be either, and re-running beats editing. If it says there is no single spine, that is the workflow telling you this branch may want splitting.

**When `oneShot` is true, print a one-shot record instead of a debate record.** There was no debate, so every field that describes one is meaningless and printing it is a lie about how the text was produced. Print the through-line, then a single line of the form:

```
one-shot · medium change · 212 words, 4 of 6 bullets · within budget · 1 factual correction
```

Drawn only from `size`, `words`, `budget`, `overBudget`, `atCap`, `factErrors`, `factChecked` and `dropped`. Never print `rounds`, `unanimous`, `repaired`, `judgesReported`, `history` or `outstanding` on a one-shot run — `unanimous: false` and `0 of 4 judges reported` are artifacts of a panel that never sat, and reporting them as if a panel had disagreed is exactly the fabricated provenance this skill's fact-check exists to prevent. The `factChecked` rule below still applies in full: a one-shot run that could not fact-check is **more** dangerous than a debated one, because no other agent read the text.

**When the description was written `--inline`, print an inline record.** No workflow ran, so every field one returns is unavailable and printing one is fabricated provenance. Print the through-line, then a single line:

```
inline · medium change · 212 words, 4 of 6 bullets · within budget · self fact-checked against the diff
```

Drawn only from what you measured in Step 2-INLINE and checked yourself. Never print `rounds`, `unanimous`, `repaired`, `judgesReported`, `history`, `outstanding`, `dropped` or a correction count: no panel sat and no independent checker ran. Say **`self fact-checked`**, never `fact-checked` — the difference between a claim you verified and a claim another agent verified is the whole difference between this path and the other two, and the user is entitled to know which one produced the text in front of them. Where you could not verify a claim and cut it, say that in one line too.


**Every other line must come from a field the workflow returned** — `rounds`, `unanimous`, `repaired`, `judgesReported`, `words`, `budget`, `overBudget`, `atCap`, `size`, `caps`, `sections`, `composePasses`, `factErrors`, `factChecked`, `dropped`, `unresolved`, `outstanding`, and `history[].blockers` (round, persona, quote, problem). Never state how an objection was *resolved*: the workflow does not return that, and inferring it from the final text fabricates a provenance log — the exact failure this skill's fact-check phase exists to prevent. Never reconstruct a debate line you were not handed; if the field is empty, print fewer lines.

Then, specifically:

- **`unanimous` false** → say so plainly and list `outstanding`. The user should know which reviewer's bar the text does not meet.
- **`repaired` true** → note that the last round's objections were applied but never re-judged, so `outstanding` lists what was *fixed-but-unverified*, not what was ignored.
- **`judgesReported` below the full panel of 4** → print `N of 4 judges reported` on the header line and never print "unanimous accept". A short vote is not consent.
- **`factChecked` false** → print `fact-check did not complete — text is unverified against the diff` on its own line, and report no correction count. Otherwise, if `factErrors` was non-empty, say how many claims were corrected; that is the single most useful signal in the run.
- **`overBudget` non-empty** → the composing editor could not get the text inside its limits in two passes. Print the breaches verbatim. This means the description is longer than a reviewer will read, and the honest move is to offer to cut it further or to point out that the diff may be doing too many things to describe in one MR.
- **`dropped` non-empty** → say which facts the composing pass lost and the fact-checker put back. A repeat offender there is a signal the budget is too tight for this change, not that the fact was unimportant.
- **`atCap` non-empty** → print it as one line, phrased as an observation and never as a defect: the text landed exactly on a ceiling, which is worth a glance to confirm nothing was merged or trimmed purely to fit. Two consecutive runs at cap on the same dimension means the tier for that `size` is wrong — that is a script edit, not something to work around.

If the workflow returns no usable `description`, say the debate failed and write the description yourself from the Step 1 packet using the house rules. Do not present a fallback as a debate result.

## Important Rules

1. **The packet is the run.** Subagents see only `args`. A thin `context` digest produces a fluent description of the wrong thing — and it will read well, which is what makes it dangerous.
2. **Never invent rationale.** If the conversation didn't say why, the description doesn't say why. The fact-checker exists because three rounds of polishing turn a hedge into a confident falsehood.
3. **Format is not up for debate.** The house rules bind every persona. A "thorough" description with a design-decisions section is a failed run, not a thorough one.
4. **Respect what was discussed.** Where the user explained their reasoning in the chat, that reasoning goes in the packet and wins over anything a persona invents.
5. **Match the tool to the change.** A one-line fix does not need a fifteen-agent debate. For a trivial diff, run `--one-shot` (4–6 agents) or `--quick` (15–16); where the description is not the deliverable and the change request wants opening now, run `--inline` and launch nothing. **Never write a description by hand *outside* this skill**: freehand loses the mechanical word count and the fact-check, which are the two things this skill has evidence a lone writer gets wrong. `--inline` is how a hand-written description keeps both — the prose is yours, the budget and the fact-check are still compulsory, and Step 2-INLINE is where they are spelled out.
6. **The description ships alone.** Everything outside the code block is for the user's eyes, never for pasting into the MR.
7. **Report the debate honestly.** A non-unanimous result is a real signal about the change, not a formatting problem to smooth over.
8. **The budget is arithmetic, not taste.** It is measured in code and handed to the agents precisely because "1–3 sentences" was satisfied by three 50-word sentences. If the text cannot fit, say so — do not quietly widen the limit.
9. **Ceilings, not targets.** The caps scale with the size of the diff for the opposite failure: a fixed cap of 7 bullets produced exactly 7 bullets for both a three-constant timeout fix and a new subsystem. If a run keeps landing on its ceiling, the tier is wrong; fix the tier rather than letting the number pick how much gets said.
10. **Content is settled before shape.** The debate decides which facts appear; the composing editor decides how they read and may not change what is claimed. Keep those two jobs apart — an editor allowed to do both will trade away facts for flow and call it tightening.
