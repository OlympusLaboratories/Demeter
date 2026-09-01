# MR Description Generator — Adversarial Draft Swarm

Produce a merge request description by making four reviewers with incompatible goals fight over it until they all sign off. A senior engineer argues for accuracy and completeness, an impatient reviewer argues for brevity, a novice argues for plain language, and a hawk-eyed manager hunts sentences that were generated rather than thought about. An editor referees and settles the through-line — the one sentence naming what this MR is about; a composing editor then builds the prose on that spine against a mechanically measured word budget; and a fact-checker confirms the result is true about the diff and lost nothing on the way.

**Parameter:** `$ARGUMENTS` — optional.

| Argument | Effect |
|---|---|
| *(none)* | Debate the changes on the current branch vs. the default branch, plus uncommitted work. |
| A git ref/range (`main`, `origin/main`, `HEAD~3`) | Diff against that base instead. |
| `--rounds N` | Cap the debate at N rounds (default `2`, max `3`). |
| `--quick` | One judging round plus a single repair pass if anyone blocks. Use for small changes — the repair is not re-judged, so the run reports non-unanimous. |

Parse the flags out of `$ARGUMENTS` **first**; whatever remains (if anything) is the git ref. `--rounds` and `--quick` set the `rounds` value passed to the workflow — they are not part of the diff base, and feeding them to `git merge-base` produces a confusing failure.

This skill uses the **Workflow** tool. Invoking it is an explicit opt-in to multi-agent orchestration — proceed without asking for further permission. A run is 15 agents when the panel accepts in one round, 20 at the default two rounds, and 26 at `--rounds 3` with no consensus and a factual correction. `--quick` is 15–16.

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

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
[ -z "$DEFAULT_BRANCH" ] && DEFAULT_BRANCH=$(git branch -r | grep -E 'origin/(main|master)$' | head -1 | sed 's@.*origin/@@')
[ -z "$DEFAULT_BRANCH" ] && DEFAULT_BRANCH=main

# REF = $ARGUMENTS with --rounds N / --quick already stripped out; may be empty
BASE="${REF:-$DEFAULT_BRANCH}"
MERGE_BASE=$(git merge-base HEAD "origin/$BASE" 2>/dev/null || git merge-base HEAD "$BASE" 2>/dev/null || echo "$BASE")

git --no-pager diff --name-status "$MERGE_BASE" -- .   # -> files
git --no-pager diff "$MERGE_BASE" -- .                 # -> diff
git rev-parse --show-toplevel                          # -> repoRoot
```

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

## Step 2: Run the Debate

Call the **Workflow** tool with the script below, passing `args` as a **real JSON object, never a JSON-encoded string**:

```json
{ "diff": "<unified diff>", "files": "<name-status list>", "context": "<the Step 1b digest>",
  "defaultBranch": "<DEFAULT_BRANCH>", "repoRoot": "<REPO_ROOT>", "rounds": 2 }
```

`rounds` is `2` by default, `1` under `--quick`, or the number given to `--rounds` (the script clamps it to 1–3 regardless).

A JSON-encoded string makes every `args.x` lookup `undefined`; the script hard-throws on missing `diff` or `context` rather than letting four drafters write a description of nothing.

**Always pass the script inline via `script`.** Never re-run this skill's workflow with `scriptPath` or `resumeFromRunId` — those replay a frozen snapshot of the script from the run they were taken in, silently discarding any fix made to this file since. The one sanctioned exception is `/workflow-resume`, which pairs `resumeFromRunId` with the script re-read from **this** file, so a run killed by a spend limit keeps its cache without replaying a stale script.

````js
export const meta = {
  name: 'changes-description',
  description: 'Four adversarial personas fight over an MR description; an editor referees',
  phases: [
    { title: 'Draft' },
    { title: 'Cross-examine' },
    { title: 'Synthesize' },
    { title: 'Debate' },
    { title: 'Compose' },
    { title: 'Fact-check' },
  ],
}

// args = { diff, files, context, defaultBranch, repoRoot, rounds }
// A JSON-encoded string yields `undefined` for every lookup, which would send
// the drafters off to invent a description from nothing. Normalise, then refuse.
const A = typeof args === 'string' ? JSON.parse(args) : (args || {})
for (const k of ['diff', 'context']) {
  if (typeof A[k] !== 'string' || !A[k].trim()) {
    throw new Error(
      `changes-description: args.${k} is missing or empty (got ${typeof A[k]}). ` +
      `Refusing to run the debate with no ${k === 'diff' ? 'changes' : 'conversation digest'} — ` +
      `the personas would produce a fluent description of code that does not exist. ` +
      `Pass args as a JSON OBJECT, not a JSON-encoded string.`
    )
  }
}
const ROUNDS = Math.min(Math.max(Number(A.rounds) || 2, 1), 3)

// ─────────────────────────────────────────────────────────────────────────────
// Budgets, measured in code rather than asked of an agent.
//
// The first version of this skill capped Summary at "1-3 sentences" and Changes
// at "~7 bullets" and left it there. A real run came back at 913 words with
// exactly 3 summary sentences — 59, 51 and 33 words each — and ten bullets
// averaging 76 words. Every stated limit was satisfied; the text was a wall.
// Counting units the model can inflate is Goodhart bait, so the limits below are
// about MASS, and the numbers are computed and handed to the agents rather than
// trusted to their own counting.
//
// A later pair of runs exposed the other half of Goodhart: a single fixed cap of 7
// bullets produced exactly 7 bullets for a three-constant timeout fix AND for a new
// subsystem with a runbook. A limit every run reaches is a target, not a ceiling. So
// the caps move with the size of the change, and the run reports when the text landed
// against one.
// ─────────────────────────────────────────────────────────────────────────────
const diffLines = (A.diff.match(/\n/g) || []).length
const filesChanged = (A.files || '').split('\n').filter((l) => l.trim()).length
const size = diffLines > 1200 || filesChanged > 12 ? 'large'
  : diffLines > 300 || filesChanged > 4 ? 'medium'
  : 'small'
const BUDGET = {
  small:  { total: 170, summaryWords: 60, summarySentences: 3, sentenceWords: 30, bullets: 4, bulletWords: 25, changesWords: 100 },
  medium: { total: 250, summaryWords: 80, summarySentences: 3, sentenceWords: 30, bullets: 6, bulletWords: 25, changesWords: 150 },
  large:  { total: 320, summaryWords: 80, summarySentences: 3, sentenceWords: 30, bullets: 8, bulletWords: 25, changesWords: 200 },
}[size]

// Testing and Rollout are paid for out of their own allowance, never out of Changes.
// Without this, the only way to add the Rollout section the senior's checklist demands
// is to cut a bullet — which is exactly how a deploy-ordering requirement ends up as a
// trailing clause on the last bullet instead of as the section it needed to be.
const SECTION_ALLOWANCE = { Testing: 25, Rollout: 30 }

const budgetText = `- whole description: ${BUDGET.total} words max (${size} change — ${diffLines} diff lines, ${filesChanged} files), plus ${SECTION_ALLOWANCE.Testing} more words if a Testing section is warranted and ${SECTION_ALLOWANCE.Rollout} more if a Rollout section is
- Summary: ${BUDGET.summaryWords} words max, ${BUDGET.summarySentences} sentences max, no single sentence over ${BUDGET.sentenceWords} words
- Changes: ${BUDGET.bullets} bullets max, ${BUDGET.changesWords} words max across all of them, no single bullet over ${BUDGET.bulletWords} words

Every number above is a CEILING, not a quota. Landing exactly on one is not a success
condition; a description well under its limits is not missing anything by definition. Do
not merge bullets to look tighter, and never split or pad to fill the allowance.`

// A free-standing "—" between clauses is punctuation, not a word, and neither is the
// "-" that opens a bullet. Counting them made the real ceiling ~15 words tighter than
// the stated one, and tighter on em-dash prose than on comma prose — a style tax the
// budget was never meant to levy.
const countWords = (s) => (s && s.trim()
  ? s.trim().split(/\s+/).filter((t) => !/^[—–*+\-:;,.]+$/.test(t)).length
  : 0)

// Returns { total, summaryWords, ..., overflows: [ "..." ] }. `overflows` is the
// whole point: a composer told "it is too long" churns, a composer told "bullet 5
// is 114 words, cap is 25" fixes that bullet.
const measure = (text) => {
  const lines = (text || '').split('\n')
  const section = (name) => {
    const i = lines.findIndex((l) => l.trim().toLowerCase() === `## ${name.toLowerCase()}`)
    if (i < 0) return []
    const rest = lines.slice(i + 1)
    const j = rest.findIndex((l) => l.trim().startsWith('## '))
    return j < 0 ? rest : rest.slice(0, j)
  }
  const has = (name) => lines.some((l) => l.trim().toLowerCase() === `## ${name.toLowerCase()}`)
  const totalCap = BUDGET.total
    + (has('Testing') ? SECTION_ALLOWANCE.Testing : 0)
    + (has('Rollout') ? SECTION_ALLOWANCE.Rollout : 0)
  const summary = section('Summary').join(' ').trim()
  const sentences = summary.split(/[.!?]+(?:\s+|$)/).map((s) => s.trim()).filter(Boolean)
  const bullets = []
  for (const l of section('Changes')) {
    if (/^\s*[-*]\s+/.test(l)) bullets.push(l.replace(/^\s*[-*]\s+/, '').trim())
    else if (l.trim() && bullets.length) bullets[bullets.length - 1] += ' ' + l.trim()
  }
  const m = {
    total: countWords((text || '').replace(/^##.*$/gm, '')),
    summaryWords: countWords(summary),
    summarySentences: sentences.length,
    longestSentence: sentences.length ? Math.max(...sentences.map(countWords)) : 0,
    bullets: bullets.length,
    changesWords: bullets.reduce((a, b) => a + countWords(b), 0),
    longestBullet: bullets.length ? Math.max(...bullets.map(countWords)) : 0,
    totalCap,
    hasTesting: has('Testing'),
    hasRollout: has('Rollout'),
    overflows: [],
    // Reported, never blocking. A run that lands exactly on a ceiling is the signal
    // that the ceiling shaped the content rather than merely bounding it — that is a
    // thing for the author to eyeball, not an objection for a persona to raise.
    atCap: [],
  }
  if (m.total > totalCap) m.overflows.push(`whole description is ${m.total} words, cap is ${totalCap} — cut ${m.total - totalCap}`)
  if (m.summaryWords > BUDGET.summaryWords) m.overflows.push(`Summary is ${m.summaryWords} words, cap is ${BUDGET.summaryWords}`)
  if (m.summarySentences > BUDGET.summarySentences) m.overflows.push(`Summary has ${m.summarySentences} sentences, cap is ${BUDGET.summarySentences}`)
  sentences.forEach((s, i) => {
    if (countWords(s) > BUDGET.sentenceWords) m.overflows.push(`Summary sentence ${i + 1} is ${countWords(s)} words, cap is ${BUDGET.sentenceWords}: "${s.slice(0, 60)}..."`)
  })
  if (m.bullets > BUDGET.bullets) m.overflows.push(`Changes has ${m.bullets} bullets, cap is ${BUDGET.bullets} — merge or cut ${m.bullets - BUDGET.bullets}`)
  if (m.changesWords > BUDGET.changesWords) m.overflows.push(`Changes totals ${m.changesWords} words, cap is ${BUDGET.changesWords}`)
  bullets.forEach((b, i) => {
    if (countWords(b) > BUDGET.bulletWords) m.overflows.push(`bullet ${i + 1} is ${countWords(b)} words, cap is ${BUDGET.bulletWords}: "${b.slice(0, 60)}..."`)
  })
  if (m.bullets === BUDGET.bullets) m.atCap.push(`bullets landed exactly on the cap of ${BUDGET.bullets}`)
  if (m.summaryWords <= BUDGET.summaryWords && m.summaryWords > BUDGET.summaryWords - 5) m.atCap.push(`Summary is ${m.summaryWords} words against a ${BUDGET.summaryWords}-word cap`)
  if (m.changesWords <= BUDGET.changesWords && m.changesWords > BUDGET.changesWords - 10) m.atCap.push(`Changes is ${m.changesWords} words against a ${BUDGET.changesWords}-word cap`)
  return m
}

// ─────────────────────────────────────────────────────────────────────────────
// The house rules are the referee, not a persona. Format is NOT up for debate:
// without this, the senior persona reliably reintroduces the design-decisions
// section this skill exists to prevent, and wins the argument on "thoroughness".
// ─────────────────────────────────────────────────────────────────────────────
const HOUSE = `
NON-NEGOTIABLE HOUSE RULES — no persona may argue against these:

Template (markdown, exactly these section names, in this order):

## Summary

1-3 sentences in plain language. Lead with the problem: what breaks or falls short
today, stated concretely and with real numbers or names where they exist. Then say
what this MR does about it.

## Changes

Bulleted list of what a reviewer needs to know to follow the diff — no more. Name the
actual functions, files, and config keys, but explain any concept a newcomer would not
already hold in their head. Skip anything obvious at a glance in the diff.

## Testing

(Exception — usually omit. Include only if a reviewer would otherwise wonder "was this
actually verified?" and the answer is not obvious. One or two lines: what was checked
and that it passed. Fold commands in — "make test, make lint, make build all pass" —
unless a command's OUTPUT is the point, like a terraform plan diff.)

## Rollout

(Exception — usually omit, but RUN THE TRIGGER LIST against the diff before omitting it,
rather than consulting your instinct. Include when the diff contains any of: a new required
config key or env var; a changed helm value or chart default; a changed schedule, cron,
activity or workflow timeout that an already-running deployment must pick up; a migration;
a feature flag, especially one flipped from a different repo; a destructive or irreversible
operation this change makes possible; or a required ordering against another merge. If none
of those fired and rollout is "merge and it's live", say nothing.)

Hard rules:
1. Summary and Changes are the whole description in a normal MR. Testing and Rollout are
   exceptions that must clear the bar above. Never write a section to say "N/A",
   "standard rollout", or "covered by existing tests".
2. NEVER add a section enumerating design decisions — no "key choices", "design notes",
   "decisions worth pushing on", no bullet per branch of the code. That reasoning belongs
   in a comment at the line it explains. The description's job is to make the diff
   legible, not to re-litigate it. A bullet that opens by justifying a choice ("Why X
   exists at all", "The reason we...", "X is not sufficient because...") is that banned
   section wearing a different hat — it is still a design note, and it is still cut.
3. Optimize for JARGON DENSITY, not line count. A short description packed with
   unexplained terms is WORSE than a longer plain-language one. When the text is too
   long, the fix is removing undefined terminology and abstraction, never compressing
   explanations into denser jargon.
4. Every term is either explained inline or dropped. Name the concrete thing: "Google's
   membership API wants a group's internal ID, not its email address" beats "memberships
   are parented on groups/<id>".
5. Spend words on the PROBLEM, not the solution. How the change works is visible in the
   diff. Why it was needed is not.
6. Length tracks the size of the change, never the length of the conversation.
7. No editorializing ("greatly improves", "much cleaner"), no trailing commentary, no
   meta-notes about what was cut or why.
8. Use the real identifiers from the diff. Do not paraphrase names loosely.
9. THE SUBSTITUTION TEST: every sentence must be FALSE of some other merge request. If a
   sentence would survive unchanged in the description of a different change, it carries no
   information about this one — cut it or make it specific. This is the single most reliable
   detector of text that was generated rather than thought about.
10. ONE IDEA PER BULLET, and each bullet opens with the thing that changed. If a bullet
   needs a semicolon, a parenthetical aside, or a subordinate "because..." clause to hold
   everything it is carrying, it is either two bullets or one bullet plus a cut. A bullet
   the reader must re-read is a failed bullet however true it is.
11. THE THROUGH-LINE. Every description has a spine: one sentence naming what this MR is
   about. The Summary expresses it, and every bullet in Changes must visibly serve it —
   a reader should be able to say why each bullet is in the same MR as the others. The
   test: after reading, can the reviewer say why these changes belong together? If the
   honest answer is "they were on the same branch", the description has failed, or the
   MR has. Order the bullets by something real — the order the reviewer will meet them
   in the diff, or the order in which one change makes the next possible — never by
   file listing or by the order you discovered them.
   A Summary sentence shaped like "this MR does A, B and C" is a MANIFEST, not a spine —
   that list is what Changes is for. Three things in one MR are usually three places one
   broken assumption showed up; name the assumption and the list stops being needed.
12. Where the change only makes sense inside a bigger effort, place it in one clause, not
   a paragraph: which initiative it belongs to and which part of it this is. Enough to
   orient, never a recap of the initiative.
13. OPERATIONAL FACTS GO IN THEIR OWN SECTION. A fact about how this must be deployed —
   an ordering, a flag, a required config value, a manual step, a separate MR that must
   land first — belongs in Rollout, never in a Changes bullet's trailing clause. Changes
   tells the reviewer how to read the diff; Rollout tells them what to do on merge day. A
   deploy requirement buried at the end of the last bullet has been written down without
   being communicated. Those words come from Rollout's own allowance, so moving a fact
   there costs the Changes budget nothing.
14. NOT-DONE FACTS. A claim about code that did NOT change, or work deliberately left out
   — a gap this MR does not close, a follow-up, something not wired into the build — earns
   a place only when a reviewer would otherwise assume the opposite. When it does, it must
   READ as a gap from its first words: "Not fixed:", "Not changed:", "Deferred:", "Not
   wired into…". Never an identifier followed by a parenthetical "(unchanged)" — that
   reads as a change until the reader backtracks, and it is the hardest kind of bullet to
   parse. At most ONE such bullet; beyond that it is a scope note, and scope notes live in
   the Summary's last clause or nowhere.
15. CONVENTIONS, held consistent within one description:
   - A ticket identifier appears once, at first mention, as a markdown link when the
     digest supplies a URL — [PLAT-2247](https://…) — and bare when it does not, but the
     same way throughout, and never twice.
   - File paths: annotate a new symbol with its file on first mention, or annotate none of
     them. A half-annotated list reads as an editing accident, because it is one.

BUDGET — these are hard limits, measured mechanically and reported to you:
${budgetText}
A budget breach is not a style opinion; it is a defect, and "the change is complicated" is
not a defence. Complicated changes are exactly when a reviewer needs the short version.
`

// Deliberately lopsided charters. A persona that pre-compromises is useless —
// the editor is the only participant allowed to be balanced.
const PERSONAS = [
  {
    key: 'senior',
    title: 'a senior engineer who owns this service',
    axis: 'thoroughness and accuracy',
    charter: `You have been paged at 2am by things exactly like this. Your fear is the
description that reads beautifully and omits the one fact that would have made the
reviewer look harder: a breaking contract change, a migration that must run first, a
silently changed default, a claim that is subtly untrue. You want every material fact
about this change present and correct. You are NOT arguing for length — you are arguing
that nothing load-bearing is missing and nothing stated is wrong.`,
    veto: `Block ONLY when: (a) the text states something the diff contradicts, (b) a
material fact is missing whose absence would change what a reviewer DOES — a breaking
change, a required deploy ordering, a flag, a migration, a changed default, a security-
relevant behavior change, (c) a claim is unverifiable from the diff or the context
digest and therefore may be invented, (d) THE ROLLOUT CHECKLIST fires, or (e) the change
ships something whose correctness cannot be checked by reading and nothing says it was
verified. Wanting more detail is a preference, not a veto.

(d) is the omission you are most likely to miss, so run it LITERALLY against the diff
every time rather than asking yourself whether rollout "feels" interesting. Does the diff
add a required config key or env var? Change a helm value or chart default? Change a
schedule, cron, or activity/workflow timeout that a running deployment must pick up? Add a
migration? Depend on a feature flag, especially one flipped from another repo? Make a
destructive or irreversible operation possible? Require an ordering against another merge?
If any answer is yes and there is no Rollout section — or the fact is buried in a Changes
bullet — block, and name which trigger fired. Rollout has its own word allowance; "there
was no room" is not a reason it is absent.

(e) covers the tool that deletes production state, the bulk mutation, the data migration:
a reviewer cannot verify those by reading the diff, so a Testing line saying what was
actually run is the only thing standing between them and taking it on faith.`,
  },
  {
    key: 'skimmer',
    title: 'a busy reviewer with eleven tabs open and four minutes',
    axis: 'brevity',
    charter: `You did not write this code and you have three other reviews queued. You
read the first two sentences, and if they do not tell you what this is and why, you
either bounce or rubber-stamp it — both bad outcomes. Every sentence must earn its place.
You despise: restating what the next bullet says, bullets that describe what the diff
already shows at a glance, sections included out of habit, throat-clearing before the
point, and any sentence you could delete without the reviewer losing information.`,
    veto: `Block ONLY when: (a) a sentence or bullet carries no information a reviewer
would act on, (b) two parts of the text say the same thing, (c) the MEASURED BUDGET below
is breached — you are given the real numbers, so this one is arithmetic, not taste, and
you must block on every breach listed, (d) a bullet carries more than one idea, or (e) a
Testing/Rollout section is present without clearing the house-rule bar.
Two things are NOT vetoes. Disliking an explanation that the novice needs — see the
tie-break rules. And a Rollout or Testing section that the senior's trigger list demands:
it clears the bar by definition, its words come from a separate allowance, and it is
therefore never a budget breach. Your win against those sections is making them two lines,
never making them zero.`,
  },
  {
    key: 'novice',
    title: 'a capable engineer who is new here and has read none of the design docs',
    axis: 'comprehensibility',
    charter: `You are going to be asked to review this diff. You are not stupid — you are
unfamiliar. Nobody has told you what this initiative is, what the internal nouns mean, or
which of the five similarly-named services this one is. Explain it to me like I am five:
if a term appears that you cannot define from the description alone, you cannot review the
code, and you will either approve it blindly or waste an hour reconstructing context. Ask
the dumb question out loud every time: what IS that? why does that matter? what breaks if
it is wrong?`,
    veto: `Block ONLY when: (a) a term, acronym, internal noun, or concept appears that a
competent newcomer could not define from this text alone, (b) the description assumes
context from a ticket, design doc, or sibling MR that is not restated here — including a
bare allusion to a limit, cap, quota, or failure whose actual number lives only in that
sibling ("running out of room", "the cap", "the old limit"); the number gets named here or
the allusion goes, (c) after reading it you still cannot say what problem this solves,
(d) THE FIRST SENTENCE fails on its own, or (e) IT DOES NOT HANG
TOGETHER — you cannot say why these changes belong in one MR, a bullet's relation to the
through-line is not evident, or the bullets are ordered by nothing you can detect. That
last one is your most valuable veto and the easiest to under-use: a list of facts you
understand individually is still a list, and you cannot review from it.

(d) exists because position changes the cost of a word. The skimmer reads sentence one and
stops; an undefined noun there taxes every reader, while the same noun in the last bullet
taxes the few who got that far. So weigh sentence one far more heavily than anything after
it, and block when someone who has read nothing else could not follow it — even when the
rest of the description is perfectly clear.

Two things are NOT vetoes: wanting the change explained line-by-line (the diff does that),
and wanting more words. When you block on (e), the fix is almost always ORDERING or
CUTTING, not explaining — say which. A gloss added to a list makes a longer list.`,
  },
  {
    key: 'hawk',
    title: 'a hawk-eyed engineering manager who can smell AI-generated filler',
    axis: 'thought — sentences that could only have been written about this diff',
    charter: `You have read four hundred merge requests this year and you can tell inside two
sentences whether a human thought about this change or a model filled in a template. What
you hunt is prose that pattern-matches to "good writing" while carrying no thought:
confident sentences that would be equally true of a hundred other MRs; benefits asserted
with no fact behind them ("improves maintainability", "more robust", "cleaner", "better
separation of concerns"); bullets that restate the diff one abstraction level up and call it
explanation; tricolons of adjectives; "in order to", "it is worth noting", "leverages",
"utilizes", "seamless", "comprehensive", "ensures", "facilitates"; symmetrical bullets whose
content is not symmetrical; and closing sentences that summarize what was just said. You are
NOT hunting long text or simple text — a short plain sentence packed with specifics is
exactly right. You are hunting text nobody thought about, because a reviewer who smells it
stops trusting every other sentence in the description, including the true ones.`,
    veto: `Block ONLY when: (a) a sentence would survive unchanged in the description of a
DIFFERENT merge request — apply that substitution test literally, it is your sharpest tool;
(b) a benefit or quality is claimed with no concrete fact behind it; (c) a bullet restates
what the diff already shows, one abstraction level up, and adds nothing; (d) formulaic
filler is doing the work a sentence should be doing; or (e) the THROUGH-LINE would fit a
hundred other MRs ("improves the reliability of the grant system"). A generic spine is the
worst case of all, because every sentence downstream inherits it — apply the substitution
test there first and hardest. Plain language is NOT slop — that is
the novice's win and you may not block it. Brevity is not your axis either: a short empty
sentence is your target, a short specific one is not.`,
  },
]

// Tie-breaks. Without these the loop bikesheds: the skimmer and the novice have
// directly opposed instincts and will trade the same sentence back and forth forever.
const REFEREE = `
TIE-BREAK RULES (the editor applies these; personas may not override them):
- Novice vs skimmer: resolve by REMOVING the jargon, not by adding a gloss for it. If the
  concrete thing can simply be named, name it and delete the term. Only when a term is
  genuinely irreducible does it earn an inline explanation — and then it stays.
- Senior vs skimmer: the senior wins only by showing the omission changes what a reviewer
  would DO. If it merely adds completeness, the skimmer wins and it is cut.
- Senior vs novice: accuracy wins over simplicity, but the fix is plainer words for the
  same fact — never dropping the fact, never keeping the jargon.
- Hawk vs novice: an explanation a reviewer needs in order to read the diff is never slop.
  A definition of something obvious is. If the term can be dropped by naming the concrete
  thing instead, that single edit satisfies both of them.
- Hawk vs senior: a hedge with a concrete fact behind it stays. A hedge standing IN PLACE
  of a fact is slop — replace it with the fact, or cut the sentence.
- Hawk vs skimmer: they usually want the same edit for different reasons. When the hawk
  wants a sentence made specific and the skimmer wants it gone, cut it — a sentence not
  worth making specific was never worth keeping.
- Senior's rollout/testing checklist vs skimmer: the checklist wins, and this is not a
  length argument. Whether the section exists is decided by the trigger list; how long it
  is, is the skimmer's to win. The words come from a separate allowance, so the section
  never costs a Changes bullet and can never be a budget breach.
- Not-done bullets vs anyone: at most one survives. When two compete, keep the one whose
  absence would make a reviewer assume the opposite, and cut the other.
- Novice's narrative veto vs anyone: a fact that serves no through-line loses, however
  true. But when the senior shows the fact is reviewer-actionable, the spine is what was
  chosen wrong — go back to it rather than dropping the fact. A description that reads
  beautifully because the awkward fact was cut is the worst failure available here.
- Any objection that would violate a house rule is discarded outright, however senior the
  persona raising it.
- An objection with no minimal concrete fix attached is treated as a preference, not a
  block.
`

const DESC_SCHEMA = {
  type: 'object',
  properties: {
    description: { type: 'string' },
    // The spine: one sentence naming what this MR is about, chosen BEFORE the
    // prose is written and carried through every later stage. Without it,
    // "narrative" is a style note nobody can act on or check.
    throughLine: { type: 'string' },
    rationale: { type: 'string' },
    unresolved: { type: 'array', items: { type: 'string' } },
  },
  required: ['description', 'throughLine', 'rationale'],
  additionalProperties: false,
}

const CRITIQUE_SCHEMA = {
  type: 'object',
  properties: {
    objections: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          target: { type: 'string' },
          quote: { type: 'string' },
          problem: { type: 'string' },
          fix: { type: 'string' },
        },
        required: ['target', 'quote', 'problem', 'fix'],
        additionalProperties: false,
      },
    },
    keep: { type: 'array', items: { type: 'string' } },
  },
  required: ['objections', 'keep'],
  additionalProperties: false,
}

const JUDGE_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['accept', 'revise'] },
    blocking: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          quote: { type: 'string' },
          problem: { type: 'string' },
          fix: { type: 'string' },
        },
        required: ['quote', 'problem', 'fix'],
        additionalProperties: false,
      },
    },
    note: { type: 'string' },
  },
  required: ['verdict', 'blocking'],
  additionalProperties: false,
}

const FACT_SCHEMA = {
  type: 'object',
  properties: {
    accurate: { type: 'boolean' },
    errors: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          problem: { type: 'string' },
          correction: { type: 'string' },
        },
        required: ['claim', 'problem', 'correction'],
        additionalProperties: false,
      },
    },
    dropped: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          fact: { type: 'string' },
          why_it_matters: { type: 'string' },
        },
        required: ['fact', 'why_it_matters'],
        additionalProperties: false,
      },
    },
  },
  required: ['accurate', 'errors'],
  additionalProperties: false,
}

const scope = A.repoRoot
  ? `\nThe checkout is rooted at ${A.repoRoot}. Your shell's working directory is NOT necessarily that root — issue any Read/Grep against absolute paths under it, and never describe code found outside it.\n`
  : ''

const CONTEXT = `Default branch: ${A.defaultBranch}${scope}
CONVERSATION DIGEST (what the author was doing and why — the diff cannot tell you this):
${A.context}

CHANGED FILES:
${A.files || '(not provided)'}

UNIFIED DIFF:
${A.diff}`

const vetoTable = PERSONAS.map((p) => `- ${p.key} (${p.axis}): ${p.veto}`).join('\n')

// ── Phase 1: one lopsided draft per persona ─────────────────────────────────
// Barrier is correct here: every cross-examination reads all of the drafts.
phase('Draft')
const drafts = (await parallel(PERSONAS.map((p) => () =>
  agent(
    `You are ${p.title}. You are one of ${PERSONAS.length} drafters in an adversarial contest to write the merge request description for the change below.

Write it YOUR way. Argue your corner and do not pre-compromise — an editor downstream is responsible for balance, and a draft that already hedges gives them nothing to weigh. Your axis is ${p.axis}.

${p.charter}

${HOUSE}

${CONTEXT}

Before writing a word, decide the THROUGH-LINE: one sentence naming what this MR is about, the spine every part of the description serves. Your persona shapes it — the senior's spine is the risk, the skimmer's is the headline, the novice's is the concept you have to hold to follow the diff, the hawk's is the one thing that could only be said about this change.

Return the complete description as markdown in \`description\` (no code fence around it), your one-sentence spine in \`throughLine\`, and two sentences in \`rationale\` on what your persona forced that a neutral writer would have missed.`,
    { label: `draft:${p.key}`, phase: 'Draft', schema: DESC_SCHEMA }
  ).then((d) => (d ? { persona: p.key, ...d } : null))
))).filter(Boolean)

if (!drafts.length) throw new Error('changes-description: every drafter failed; nothing to debate.')

const draftBlock = drafts.map((d) => `--- DRAFT BY ${d.persona.toUpperCase()} ---\n${d.description}`).join('\n\n')

// ── Phase 2: each persona attacks the others' drafts ────────────────────────
phase('Cross-examine')
const critiques = (await parallel(PERSONAS.map((p) => () =>
  agent(
    `You are ${p.title}, cross-examining in an adversarial writing contest.

${p.charter}

Below are ${PERSONAS.length} candidate MR descriptions — one from each persona, including yours. Attack the ones you did not write, and name what your own gets wrong if you can see it. You are deciding what must survive into the final text and what must die.

For each objection give: \`target\` (which draft), \`quote\` (the exact offending phrase), \`problem\` (one sentence), \`fix\` (the minimal change that resolves it). In \`keep\`, quote the phrases that must survive into the final description and say why in a few words.

${HOUSE}

${draftBlock}

${CONTEXT}`,
    { label: `cross:${p.key}`, phase: 'Cross-examine', schema: CRITIQUE_SCHEMA }
  ).then((c) => (c ? { persona: p.key, ...c } : null))
))).filter(Boolean)

const critiqueBlock = critiques.map((c) =>
  `--- ${c.persona.toUpperCase()} SAYS ---\nObjections:\n${(c.objections || []).map((o) => `  * [${o.target}] "${o.quote}" — ${o.problem} → ${o.fix}`).join('\n') || '  (none)'}\nMust keep:\n${(c.keep || []).map((k) => `  * ${k}`).join('\n') || '  (nothing flagged)'}`
).join('\n\n')

// ── Phase 3: the editor referees a single candidate ─────────────────────────
phase('Synthesize')
let current = await agent(
  `You are the editor. You are not a persona — you are the referee, and you are the only participant allowed to be balanced.

Produce ONE description that satisfies every persona's binding constraints at once: accurate and complete on what matters (senior), short enough to read in under a minute (skimmer), comprehensible to someone who has read no design doc (novice), and specific enough that no sentence could belong to a different MR (hawk). Where they conflict, apply the tie-break rules exactly.

You are CHOOSING, not accumulating. A synthesis that keeps every defensible sentence from every draft is a failed synthesis — the union of four thorough drafts is a wall of text, and every sentence in it can be justified individually while the whole is unreadable. Start from the smallest description that would let a reviewer read this diff, and add only what they would be worse off not knowing. The budget below is the test.

DO THIS FIRST, BEFORE WRITING ANY PROSE: settle the THROUGH-LINE. Read the four drafts' spines above, then write the one sentence that names what this MR is actually about — the thing that makes these files change together. It is usually the concept the change turns on, not the list of things done. Then select content by asking of every candidate fact: does a reviewer need this to follow the spine? Facts that serve no spine are the laundry list you are here to prevent, and they get cut even when true and even when a persona liked them.

Two honest outcomes are worth naming rather than papering over. If the change only makes sense as part of a larger effort, the spine may reach for it in one clause — "the third of four steps that move X off Y" — never a recap. And if this branch genuinely does several unrelated things, say so in \`throughLine\` ("no single spine: this branch does A, B and C") rather than inventing a theme that ties them; that is a real signal the MR should be split, and it belongs in front of the author.

${REFEREE}

${HOUSE}

${draftBlock}

CROSS-EXAMINATION:
${critiqueBlock}

${CONTEXT}

Return the merged description in \`description\`, a two-sentence \`rationale\`, and any tension you could not resolve in \`unresolved\`.`,
  { label: 'editor:synthesize', phase: 'Synthesize', schema: DESC_SCHEMA }
)

if (!current || !current.description) {
  // Fall back to the draft the cross-examination liked most rather than dying.
  current = { description: drafts[0].description, rationale: 'editor failed; fell back to first surviving draft', unresolved: ['editor agent failed'] }
  log('changes-description: editor failed at synthesis — fell back to a raw draft')
}

// ── Phase 4: the personas judge, the editor revises, until unanimous ────────
phase('Debate')
const history = []
let unanimous = false
let round = 0
let lastBlockers = []
let judgesReported = 0
let repaired = false

while (round < ROUNDS) {
  round++
  const verdicts = (await parallel(PERSONAS.map((p) => () =>
    agent(
      `You are ${p.title}, judging round ${round} of an adversarial contest over this MR description.

${p.charter}

YOUR VETO CONDITIONS — you may block on nothing else:
${p.veto}

The other judges block on their own conditions, and the editor must satisfy all of them at once. Any fix you propose must not violate theirs:
${vetoTable}

${REFEREE}

${HOUSE}

CANDIDATE:
${current.description}

THROUGH-LINE the editor is working to: ${current.throughLine || '(none recorded)'}

MEASURED BUDGET FOR THIS CANDIDATE (computed, not estimated):
${measure(current.description).overflows.length ? measure(current.description).overflows.map((o) => `- OVER: ${o}`).join('\n') : '- within every budget'}

${CONTEXT}

Set \`verdict\` to "accept" if nothing in your veto list is triggered — accepting a text you merely would have written differently is the correct outcome. Otherwise "revise", with each blocking objection carrying an exact \`quote\`, a one-sentence \`problem\`, and a minimal \`fix\`. Use \`note\` for non-blocking preferences; they will be ignored, which is the point.`,
      { label: `judge:r${round}:${p.key}`, phase: 'Debate', schema: JUDGE_SCHEMA }
    ).then((v) => (v ? { persona: p.key, ...v } : null))
  ))).filter(Boolean)

  // parallel() yields null for a failed thunk, so a short vote is possible.
  // Without the count check below, dead judges would read as silent accepts
  // and the run would report a consensus nobody voted on.
  const voted = verdicts.length
  judgesReported = voted

  const blockers = verdicts
    .filter((v) => v.verdict === 'revise')
    .flatMap((v) => (v.blocking || []).map((b) => ({ ...b, from: v.persona })))

  history.push({
    round,
    voted,
    verdicts: verdicts.map((v) => ({ persona: v.persona, verdict: v.verdict, blocking: (v.blocking || []).length })),
    blockers: blockers.map((b) => ({ persona: b.from, quote: b.quote, problem: b.problem })),
  })
  lastBlockers = blockers

  if (!blockers.length) {
    if (voted === PERSONAS.length) {
      unanimous = true
      log(`changes-description: unanimous accept in round ${round}`)
    } else {
      log(`changes-description: round ${round} — no blocking objections, but only ${voted}/${PERSONAS.length} judges reported; not calling this unanimous`)
    }
    break
  }

  log(`changes-description: round ${round} — ${blockers.length} blocking objection(s) from ${[...new Set(blockers.map((b) => b.from))].join(', ')}`)

  // ROUNDS >= 2 deliberately ends on a judge-only confirmation pass. ROUNDS === 1
  // (`--quick`) has no later round to repair in, so its objections are applied
  // here instead of being filed and discarded; the loop condition ends the run.
  const finalRound = round >= ROUNDS
  if (finalRound && ROUNDS > 1) break

  const revised = await agent(
    `You are the editor. Round ${round} produced these BLOCKING objections. Apply the minimal set of edits that clears every one without triggering a different persona's veto.

${blockers.map((b) => `- [${b.from}] "${b.quote}" — ${b.problem} → ${b.fix}`).join('\n')}

${REFEREE}

${HOUSE}

CURRENT TEXT:
${current.description}

${CONTEXT}

Rewrite minimally — do not restructure text nobody objected to, and do not "improve" while you are in there; churn loses the parts the cross-examination said to keep. Structure and reading order are NOT your job: a composing editor owns those in a later phase, so a flow objection is satisfied by fixing the content it names, not by reorganising. Carry \`throughLine\` forward unchanged unless an objection is specifically about the spine — if one is, say so in \`rationale\`. If two objections are genuinely irreconcilable, apply the tie-break rules and record the losing one in \`unresolved\` with one line on why it lost.`,
    { label: `editor:r${round}`, phase: 'Debate', schema: DESC_SCHEMA }
  )

  if (revised && revised.description) {
    current = { ...revised, unresolved: [...(current.unresolved || []), ...(revised.unresolved || [])] }
    if (finalRound) repaired = true
  } else {
    log(`changes-description: editor failed in round ${round}; keeping the previous candidate`)
    break
  }
}

// ── Phase 5: shape ──────────────────────────────────────────────────────────
// The debate converges on CONTENT and only ever makes local, quoted edits — the
// revise prompt forbids restructuring on purpose, so nobody in Phase 4 can fix a
// text whose every sentence is defensible and whose whole is a data dump. This
// phase owns shape, is the only participant allowed to restructure, and is not
// allowed to change what the description claims.
phase('Compose')
const beforeCompose = current.description
let budget = measure(beforeCompose)
let composePasses = 0

while (composePasses < 2) {
  composePasses++
  const composed = await agent(
    `You are the composing editor, the last person to touch this description before it ships. You own SHAPE. You do not own content: you may not add a fact, remove a fact, or change what any sentence claims. Every fact in the text below survived a four-persona debate and earned its place.

The THROUGH-LINE has already been settled — it is below, and it is not yours to change. Your job is to make the text visibly serve it, so a reviewer reads once, top to bottom, and comes away knowing what changed and why.

- Build the narrative on the spine: what was broken, what this MR does about it, what a reviewer needs to know to read the diff. Each bullet must earn its place against the spine, and its relation to the spine should be evident from its first few words.
- Order the bullets by something real — the order a reviewer meets them in the diff, or the order in which one change makes the next possible. Never by file listing, never by the order the author discovered them. If you cannot find a real order, that is worth saying in \`rationale\`.
- Connect, do not merely sequence. Where one change exists BECAUSE of another, the reader should be able to tell — but carry that in the ordering and in a few words of the bullet itself, never in an appended "because..." clause justifying a design decision.
- If a bullet cannot be tied to the spine at all, it is either the wrong bullet or evidence the spine is wrong. Prefer cutting it; say so in \`rationale\` if it looked load-bearing.
- Break long sentences. A 59-word sentence with two em-dash asides is three sentences.
- One idea per bullet, and lead the bullet with the thing that changed, not with a justification. Merge bullets that are facets of the same change; split bullets carrying two ideas.
- Cut subordinate "because..." clauses that explain a design decision — that is a banned design note however interesting it is.
- Prefer the reviewer's reading order over the author's discovery order.
- Fix ambiguous attachment. A clause after an em-dash attaches to the thing immediately before it; if it was meant to attach to something earlier in the sentence, rewrite the sentence rather than repunctuating it. Nobody downstream of you re-reads for this.
- Keep the tense honest about what is already true. Today's behavior written in the plain present ("every grant becomes a conditional binding") reads for a beat as something this MR introduces — "today, every grant is a conditional binding" costs one word and removes the double-take.
- The caps are ceilings, not quotas. If the text is already inside every limit, leave it there: do not merge bullets to look tighter, and never split or pad to reach the allowance. If you DO merge or cut a bullet purely to fit the budget, name which in \`rationale\` — a pipeline whose output always lands exactly on its cap is one where the cap is writing the description.
- Operational facts (ordering, flags, required config, a manual step, a separate MR that must land first) move OUT of Changes bullets and into Rollout. That is a move you are allowed and expected to make: it is shape, not content, the fact itself is unchanged, and Rollout is paid for from its own allowance.
${composePasses > 1 ? '\nYour previous attempt was still over budget. Fix exactly the overflows listed below; do not restyle anything else.' : ''}

THROUGH-LINE (fixed — keep it, return it unchanged in \`throughLine\`):
${current.throughLine || '(none recorded — infer the spine from the text and record it)'}

MEASURED BUDGET (computed, not estimated) — every line here is a defect to fix:
${budget.overflows.length ? budget.overflows.map((o) => `- ${o}`).join('\n') : '- within every budget; if the text already reads as a narrative, return it unchanged and say so in rationale'}

Limits:
${budgetText}

${HOUSE}

TEXT TO COMPOSE:
${current.description}

${CONTEXT}`,
    { label: `compose:${composePasses}`, phase: 'Compose', schema: DESC_SCHEMA }
  )

  if (!composed || !composed.description) {
    log(`changes-description: compose pass ${composePasses} failed; keeping the debated text`)
    break
  }
  current = { ...current, description: composed.description }
  budget = measure(current.description)
  if (!budget.overflows.length) {
    log(`changes-description: composed to ${budget.total} words, ${budget.bullets} bullets — within budget`)
    break
  }
  log(`changes-description: after compose pass ${composePasses}, ${budget.overflows.length} budget breach(es) remain`)
}

// ── Phase 6: is any of it actually true — and is any of it now missing? ─────
// Adversarial rewriting drifts. Three rounds of "make it plainer" is exactly how
// a hedged, accurate sentence becomes a clean, confident, wrong one.
phase('Fact-check')
const fact = await agent(
  `You are the fact-checker on an MR description. You are not a stylist and you have no opinion about length or tone — do not raise any.

For every factual claim in the description below, verify it against the diff, the conversation digest, and the code itself (Read/Grep as needed). Flag a claim when it is: contradicted by the diff, describes behavior the diff does not implement, names an identifier that does not exist, overstates scope (says "all X" when the diff handles some), or asserts a motivation that appears nowhere in the digest and cannot be inferred from the code — invented rationale reads exactly like real rationale and is the most dangerous output of this pipeline.

Set \`accurate\` false if any error is found. Each error needs the \`claim\` quoted, the \`problem\`, and a \`correction\` that keeps the same plain language.

SECOND JOB — NOT-DONE CLAIMS. A bullet asserting that something did NOT change, was left out, or is not wired up somewhere cannot be verified from the diff hunks: those show only what did change, so an absent thing is absent from your evidence either way. Verify each such claim against the checkout with Read/Grep, and list it as an error when you cannot confirm it. An unverifiable claim about work not done is worse than no claim at all — on the page it reads exactly as authoritative as the ones you checked.

THIRD JOB — did the composing editor lose anything? The text was restructured for readability after the debate agreed its content. That editor was told not to change facts, but shortening is exactly when a load-bearing fact goes missing. Compare the two versions below and list in \`dropped\` any fact present BEFORE and absent AFTER whose loss would change what a reviewer does — a breaking change, a required ordering, a flag, a migration, a limit, a number. Do NOT list prose that was merely tightened, reordered, or said more briefly; only facts that are now simply gone. Cutting bloat was the point, so an empty \`dropped\` list is the expected result.

BEFORE COMPOSING:
${beforeCompose}

AFTER COMPOSING (this is what ships — verify its claims):
${current.description}

${CONTEXT}`,
  { label: 'fact-check', phase: 'Fact-check', schema: FACT_SCHEMA }
)

// A dead fact-checker must never present as a clean bill of health — that turns
// the phase guarding against invented claims into a source of false assurance.
const factErrors = (fact && fact.errors) || []
const factCheckOk = Boolean(fact) && !(fact.accurate === false && !factErrors.length)
if (!fact) {
  log('changes-description: fact-check agent failed — the description was NOT verified against the diff')
} else if (!factCheckOk) {
  log('changes-description: fact-checker reported accurate=false but listed no errors — treating the check as incomplete')
}

const dropped = (fact && fact.dropped) || []

if (factErrors.length || dropped.length) {
  log(`changes-description: fact-checker flagged ${factErrors.length} wrong claim(s) and ${dropped.length} dropped fact(s); correcting`)
  const corrected = await agent(
    `You are the editor. Fix ONLY what is listed below, in place. Do not restyle anything else, and do not undo the composing editor's structure — it is what makes this readable.

${factErrors.length ? `WRONG — correct each in place:\n${factErrors.map((e) => `- "${e.claim}" — ${e.problem} → ${e.correction}`).join('\n')}` : ''}
${dropped.length ? `\nMISSING — restore each, in the shortest form that carries the fact:\n${dropped.map((d) => `- ${d.fact} (matters because: ${d.why_it_matters})`).join('\n')}\nYou are still bound by the budget, so pay for each restored fact by cutting something less load-bearing. Do not simply append.` : ''}

Limits:
${budgetText}

${HOUSE}

CURRENT TEXT:
${current.description}

${CONTEXT}`,
    { label: 'editor:fact-fix', phase: 'Fact-check', schema: DESC_SCHEMA }
  )
  if (corrected && corrected.description) {
    current = { ...current, description: corrected.description }
    budget = measure(current.description)
  }
}

// The same number the budget was judged against — counting the headings here and not
// there produced a reported word count that disagreed with the cap it was measured on.
const wordCount = budget.total
log(`changes-description: ${size} change, ${round} round(s), unanimous=${unanimous}, ${judgesReported}/${PERSONAS.length} judges reported, ${wordCount} words in ${budget.bullets}/${BUDGET.bullets} bullet(s), ${budget.overflows.length ? `${budget.overflows.length} BUDGET BREACH(ES) REMAIN` : 'within budget'}${budget.atCap.length ? `, ${budget.atCap.length} dimension(s) at cap` : ''}, ${factCheckOk ? `${factErrors.length} factual correction(s), ${dropped.length} restored` : 'FACT-CHECK DID NOT COMPLETE'}`)

return {
  description: current.description,
  throughLine: current.throughLine || '',
  unanimous,
  repaired,
  judgesReported,
  rounds: round,
  history,
  unresolved: current.unresolved || [],
  outstanding: unanimous ? [] : lastBlockers.map((b) => `[${b.from}] ${b.problem}`),
  factErrors,
  factChecked: factCheckOk,
  dropped,
  budget,
  overBudget: budget.overflows,
  atCap: budget.atCap,
  size,
  caps: BUDGET,
  sections: { testing: budget.hasTesting, rollout: budget.hasRollout },
  composePasses,
  words: wordCount,
}
````

## Step 2b: Surface the Run ID for `wfwatch`

The **Workflow** tool runs the debate in the background and its tool result includes a **run ID** (`wf_…`). The user has a shell function, **`wfwatch`** (defined in their `.zshrc` / `.bashrc`), that live-tails a workflow's progress by that ID — the debate is worth watching, since the round-by-round objections show exactly which persona forced which sentence.

**Immediately after launching the workflow — before waiting for it to finish — print the run ID in a copyable form with the exact command:**

```
🥊  changes-description debate launched — run ID: wf_ab12cd34
    Watch it live in another terminal:  wfwatch wf_ab12cd34
    One-shot snapshot instead:          wfwatch wf_ab12cd34 --once
```

Use the **actual** `runId` from the Workflow tool result verbatim — `wfwatch` resolves the journal by exact ID. Then wait for the workflow and continue to Step 3.

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
5. **Match the tool to the change.** A one-line fix does not need a fifteen-agent debate. For a trivial diff, say so and offer to write it directly instead — or run `--quick`.
6. **The description ships alone.** Everything outside the code block is for the user's eyes, never for pasting into the MR.
7. **Report the debate honestly.** A non-unanimous result is a real signal about the change, not a formatting problem to smooth over.
8. **The budget is arithmetic, not taste.** It is measured in code and handed to the agents precisely because "1–3 sentences" was satisfied by three 50-word sentences. If the text cannot fit, say so — do not quietly widen the limit.
9. **Ceilings, not targets.** The caps scale with the size of the diff for the opposite failure: a fixed cap of 7 bullets produced exactly 7 bullets for both a three-constant timeout fix and a new subsystem. If a run keeps landing on its ceiling, the tier is wrong; fix the tier rather than letting the number pick how much gets said.
10. **Content is settled before shape.** The debate decides which facts appear; the composing editor decides how they read and may not change what is claimed. Keep those two jobs apart — an editor allowed to do both will trade away facts for flow and call it tightening.

## Step 4: Self-Improvement

After the run, reflect:

- Did the packet have what the personas needed, or did the fact-checker catch invented claims that trace back to a thin `context` digest?
- Did the debate converge, or did the same objection ping-pong between skimmer and novice? If so, the tie-break rules need sharpening — that is a script edit, not a prompt tweak.
- Did a persona block on something outside its veto list? Tighten that persona's veto wording.
- Did the user still have to cut the result? Whatever they cut is a missing veto condition — add it.

If anything would have gone better with different instructions, **edit this skill file** (`~/.claude/skills/changes-description/SKILL.md`) surgically. Briefly tell the user what changed and why.
