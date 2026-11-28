# Ultra-Kludge — Refactor Opportunity Swarm

Run a thorough, multi-agent **adversarial refactoring review** of the code that recent large features left behind. Features added incrementally — especially when vibe-coding or bolting on capability without an overarching architecture — accumulate **kludge and AI-slop**: duplicated logic, divergent implementations of the same idea, over-complex control flow, dead scaffolding, leaky abstractions. Often the *ideal* pattern only becomes clear after several features exist, and the earlier code never got refactored to match.

This skill finds that accumulated debt and proposes concrete refactors toward the pattern that has since emerged. A swarm of agents analyzes each feature area, a synthesizer distills the emergent architecture and cross-cutting cleanups, and a panel of skeptics attacks every proposal — so what survives is genuinely simpler, behavior-preserving, and worth the churn (not refactoring for its own sake).

**Parameter:** `$ARGUMENTS` — optional. Narrows what to review. Any of:
- a git range (e.g. `main~50..HEAD`) → review what changed there;
- a number `N` → the last `N` commits;
- a path or paths (e.g. `src/billing src/api`) → review those areas;
- a free-text feature name (e.g. `checkout flow`) → locate its code and review it.
If omitted, the skill auto-detects the recently churned "large features" from git history.

This skill reviews the code **as it currently stands** — history only tells it *where* the recent features live. It uses the **Workflow** tool to orchestrate the swarm; invoking it is an explicit opt-in to multi-agent orchestration, so proceed without asking, but respect the scaling rules so the run stays proportional to the scope.

> **Preflight — confirm the Workflow tool exists.** Before Step 3, verify the `Workflow` tool is actually provisioned (`ToolSearch` with `select:Workflow`). It is **not** available in every session. If it's missing, do **not** abort and do **not** claim the run can't happen — run the identical three-phase pipeline with the **Agent** tool instead, per **Step 3c** below. (`wfwatch` is just a user shell function that tails a journal file; its presence says nothing about whether the `Workflow` tool is provisioned — the two are unrelated.)

## Step 1: Determine the Review Scope

Figure out which "recent large features" to review. Run git with the Bash tool.

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
[ -z "$DEFAULT_BRANCH" ] && DEFAULT_BRANCH=$(git branch -r | grep -E 'origin/(main|master)$' | head -1 | sed 's@.*origin/@@')
[ -z "$DEFAULT_BRANCH" ] && DEFAULT_BRANCH=main
```

Then pick the scope from `$ARGUMENTS`:

- **A git range** (contains `..`): use it directly as the window.
- **A number `N`**: window is `HEAD~N..HEAD`.
- **Path(s)**: review those paths at their current state; use history only to summarize what recently changed there.
- **Free-text feature**: use `git log --oneline --grep`, `Grep`, and `Glob` to locate the files that implement it.
- **Nothing**: auto-detect. Default window is the last ~30 days (fall back to the last ~30 commits if that's empty). Rank churn by directory to find the biggest recent feature areas:

```bash
# Aggregate changed-line churn per top-level-ish directory over the window.
git log --since="30 days ago" --numstat --pretty=tformat: -- . \
  | awk 'NF==3 { added=$(NF-2); deleted=$(NF-1); path=$NF;
                 n=split(path, p, "/"); dir=(n>=2 ? p[1]"/"p[2] : p[1]);
                 if (added=="-") added=0; if (deleted=="-") deleted=0;
                 churn[dir]+=added+deleted }
         END { for (d in churn) print churn[d], d }' \
  | sort -rn | head -20
```

Also capture, for context, the recent feature-ish commit subjects:

```bash
git log --since="30 days ago" --oneline --no-merges | head -40
```

## Step 2: Build the Feature Map

Turn the raw churn into a small set of **coherent feature areas** — don't just pass raw directories. Use judgment (read the tree, group related modules) to produce 3–8 areas, each large enough to be worth reviewing. For each area collect:
- **name** — a short human label (e.g. `checkout`, `ingestion-pipeline`).
- **paths** — the files/dirs that make up the area.
- **summary** — 1–2 sentences on what recently landed there and why it's a candidate for accumulated kludge (from the commit subjects / your reading).

Skip areas that are trivial, generated, or vendored. If the user narrowed the scope, honor it — the areas come from within that scope only.

Briefly tell the user the areas you'll review before launching.

## Step 3: Run the Refactor Swarm

Size the swarm to the scope:

| Scope | `scale` | Skeptics on the critique panel |
|---|---|---|
| Small (1–2 areas) | `1` | 3 |
| Medium (3–5 areas) | `2` | 3 |
| Large (6+ areas / "be exhaustive") | `3` | 5 |

Call the **Workflow** tool with the script below, passing `args` as a JSON object:

```json
{ "scopeDescription": "<what you're reviewing + the window>", "areas": [ { "name": "checkout", "paths": "src/checkout, src/api/checkout.ts", "summary": "..." } ], "scale": <1|2|3> }
```

Use this script verbatim. The one barrier (pattern synthesis) is deliberate — distilling the emergent architecture and merging cross-cutting duplicates genuinely needs every area's findings at once.

**The critique panel is batched, not per-proposal.** Each skeptic votes on every consolidated proposal, so a run costs `areas + 1 + VOTES` agents rather than `areas + 1 + proposals × VOTES`. The saving is not the main reason. A skeptic holding the whole list is the only one that can see that two proposals contradict each other, collide in the same file, or are the same refactor described twice — a skeptic handed one proposal in isolation cannot, however many of them there are. Each gets a distinct emphasis, because identical prompts over an identical list produce one opinion counted several times.

`review-code`'s per-finding panel is the deliberate exception rather than an inconsistency to tidy up: a point defect at one `file:line` is confirmed by tracing a single code path, so isolating each skeptic there is what stops cross-contamination between unrelated findings. A refactor proposal is the opposite — it is only judgeable against the whole set.

**Always pass the script inline via `script`** — never the `scriptPath` a previous run snapshotted, which replays whatever version of this pipeline was current then. To rescue a run killed by a spend limit, use `/workflow-resume`: it pairs `resumeFromRunId` with the script re-read from this file.

````js
export const meta = {
  name: 'review-kludge',
  description: 'Adversarial swarm that finds accumulated kludge and proposes refactors',
  phases: [
    { title: 'Analyze' },
    { title: 'Patterns' },
    { title: 'Critique' },
  ],
}

// args = { scopeDescription, areas: [{name, paths, summary}], scale }
const scale = (args && args.scale) || 1
const VOTES = scale >= 3 ? 5 : 3
const areas = (args && args.areas) || []

if (!areas.length) {
  log('review-kludge: no feature areas provided — nothing to review')
  return { proposals: [], patterns: [], areas: [], raw: 0, consolidatedCount: 0, orphans: 0, synthesisFailed: false, skeptics: 0, underVoted: 0 }
}

const LENSES = [
  'Duplication: copy-pasted or near-identical logic across the area that should become one shared abstraction.',
  'Divergent patterns: the same concept implemented several different ways — identify the best emergent one and converge on it.',
  'Over-complexity: deep nesting, god functions/files, tangled control flow, needless indirection that can be flattened.',
  'Dead / vestigial code: unused params, dead branches, flags and scaffolding left over from removed or changed features.',
  'Leaky or wrong abstractions: wrong layering, modules reaching across boundaries, abstractions that leak their internals.',
  'AI-slop signatures: redundant restating comments, defensive checks that can never fire, boilerplate that should be shared or generated, inconsistent naming.',
  'Config / flag sprawl: proliferating options, feature flags, or env toggles that could be consolidated or retired.',
]

const EMPHASES = [
  { key: 'dead-code', text: 'Grep rigor on dead code. Where a proposal calls something unused, vestigial or unreachable, prove it with your own search before you accept it. The usual miss is a caller behind a test helper, a string-keyed lookup, a reflective call, or another copy of the same file elsewhere in the tree.' },
  { key: 'payoff', text: 'Effort against payoff. Weigh the churn, the review burden and the regression risk against what the change actually buys. A restructure that nets ten fewer lines has not earned a reviewer reading it.' },
  { key: 'layering', text: 'Layering and correctness. Whether the proposed shape puts the logic at the right level, and whether it quietly alters error handling, ordering, or who owns a piece of state.' },
  { key: 'convention', text: 'Whole-codebase convention. Whether the ideal_pattern is genuinely what this codebase is converging toward, or an invention imported from elsewhere. What already exists here wins.' },
  { key: 'behavior', text: 'Behavior preservation. Hunt the proposals that cannot be done without changing what callers observe and do not say so. A refactor whose risk is understated is worse than one that is honestly risky.' },
]

const CATEGORY_ENUM = ['duplication', 'inconsistent-pattern', 'over-complex', 'dead-code', 'leaky-abstraction', 'ai-slop', 'layering', 'config-sprawl', 'other']
const IMPACT_ENUM = ['critical', 'high', 'medium', 'low']
const RISK_ENUM = ['low', 'medium', 'high']
const EFFORT_ENUM = ['small', 'medium', 'large']

const PROPOSAL_ITEM = {
  type: 'object',
  properties: {
    title: { type: 'string' },
    area: { type: 'string' },
    category: { type: 'string', enum: CATEGORY_ENUM },
    locations: { type: 'array', items: { type: 'string' } },
    problem: { type: 'string' },
    ideal_pattern: { type: 'string' },
    refactor: { type: 'string' },
    impact: { type: 'string', enum: IMPACT_ENUM },
    risk: { type: 'string', enum: RISK_ENUM },
    effort: { type: 'string', enum: EFFORT_ENUM },
  },
  required: ['title', 'area', 'category', 'locations', 'problem', 'ideal_pattern', 'refactor', 'impact', 'risk', 'effort'],
  additionalProperties: false,
}

const PROPOSALS_SCHEMA = {
  type: 'object',
  properties: { proposals: { type: 'array', items: PROPOSAL_ITEM } },
  required: ['proposals'],
  additionalProperties: false,
}

const SYNTHESIS_SCHEMA = {
  type: 'object',
  properties: {
    patterns: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          description: { type: 'string' },
          where_diverges: { type: 'string' },
        },
        required: ['name', 'description', 'where_diverges'],
        additionalProperties: false,
      },
    },
    consolidated: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          ref_ids: { type: 'array', items: { type: 'string' } },
          title: { type: 'string' },
          area: { type: 'string' },
          category: { type: 'string', enum: CATEGORY_ENUM },
          locations: { type: 'array', items: { type: 'string' } },
          problem: { type: 'string' },
          ideal_pattern: { type: 'string' },
          refactor: { type: 'string' },
          impact: { type: 'string', enum: IMPACT_ENUM },
          risk: { type: 'string', enum: RISK_ENUM },
          effort: { type: 'string', enum: EFFORT_ENUM },
        },
        required: ['ref_ids'],
        additionalProperties: false,
      },
    },
  },
  required: ['patterns', 'consolidated'],
  additionalProperties: false,
}

const CRITIQUE_SCHEMA = {
  type: 'object',
  properties: {
    votes: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          keep: { type: 'boolean' },
          reason: { type: 'string' },
        },
        required: ['id', 'keep', 'reason'],
        additionalProperties: false,
      },
    },
  },
  required: ['votes'],
  additionalProperties: false,
}

const lensText = LENSES.map((l) => `- ${l}`).join('\n')

// Stage 1 (barrier): analyze each feature area for accumulated kludge + local refactor proposals.
const perArea = await parallel(areas.map((a) => () =>
  agent(
    `You are one reviewer in an adversarial refactoring swarm. Analyze the CURRENT code of the feature area "${a.name}" for accumulated kludge and AI-slop, and propose concrete refactors.\n\nArea paths: ${a.paths}\nWhat recently landed here: ${a.summary}\nOverall review scope: ${args.scopeDescription}\n\nRead the actual code with Read/Grep/Glob — do not guess. Look for:\n${lensText}\n\nFor each proposal give: a short title, the area, a category, the specific locations (file:line), the problem (what the kludge is and why it hurts maintenance), the ideal_pattern to move toward (prefer a pattern already emerging elsewhere in THIS codebase over inventing a new one), a concrete refactor (the steps), and impact / risk / effort ratings.\n\nPropose refactors that make the code genuinely simpler and preserve behavior. Do NOT propose churn-for-churn, speculative generality, or new abstractions the code doesn't yet need. If the area is already clean, return an empty list.`,
    { label: `analyze:${a.name}`, phase: 'Analyze', schema: PROPOSALS_SCHEMA }
  ).then((r) => ({ area: a.name, proposals: (r && r.proposals) || [] }))
))

const rawProposals = perArea.filter(Boolean).flatMap((x) =>
  x.proposals.map((p) => ({ ...p, area: p.area || x.area }))
)

if (!rawProposals.length) {
  log('review-kludge: no kludge surfaced across the reviewed areas')
  return { proposals: [], patterns: [], areas: areas.map((a) => a.name), raw: 0, consolidatedCount: 0, orphans: 0, synthesisFailed: false, skeptics: 0, underVoted: 0 }
}

const rawIndexed = rawProposals.map((p, i) => ({ ...p, raw_id: `R${String(i + 1).padStart(3, '0')}` }))
const byRaw = new Map(rawIndexed.map((p) => [p.raw_id, p]))

// Stage 2 (barrier — needs ALL areas): distill emergent patterns + cross-cutting refactors, dedupe.
log(`review-kludge: synthesizing ${rawIndexed.length} observations from ${areas.length} areas — Patterns is one long turn with no intermediate output`)

const synthesis = await agent(
  `You are the architecture synthesizer for a refactoring swarm. Below are ${rawIndexed.length} kludge observations gathered independently from every feature area of: ${args.scopeDescription}. Each carries a raw_id.\n\nDo two things:\n\n1. patterns — describe the IDEAL PATTERNS that have emerged across these features: the conventions the codebase is converging toward, and where current code diverges from them. Aim for 5-10 patterns.\n\n2. consolidated — the consolidated proposal list, expressed by REFERENCE so you never retype a proposal body. Every entry is an object with ref_ids plus only the fields you want to change:\n   - PASSTHROUGH (the common case): {"ref_ids": ["R007"]} and nothing else. The proposal is carried through verbatim. Do not restate its fields.\n   - MERGE (two or more areas raised the same thing): {"ref_ids": ["R007","R041","R088"], "title": "...", "problem": "...", "ideal_pattern": "...", "refactor": "...", "impact": "...", "risk": "...", "effort": "...", "area": "cross-cutting"}. Supply only the fields that need rewriting for the merged scope; locations are unioned automatically if you omit them.\n   - NEW cross-cutting proposal that no single-area reviewer could see: {"ref_ids": [], ...all fields...}.\n\nEVERY raw_id must appear in exactly one entry's ref_ids. Any id you omit will be appended as a passthrough anyway, so omitting one buys you nothing — reference it.\n\nDo not invent problems to pad the list. Prefer converging on patterns that already exist in the codebase over introducing novel architecture.\n\nObservations (JSON):\n${JSON.stringify(rawIndexed)}`,
  { label: 'synthesize-patterns', phase: 'Patterns', schema: SYNTHESIS_SCHEMA }
)

const patterns = (synthesis && synthesis.patterns) || []

function materialize(entry) {
  const refs = (entry.ref_ids || []).map((id) => byRaw.get(id)).filter(Boolean)
  const base = refs[0] || {}
  const locations = (entry.locations && entry.locations.length)
    ? entry.locations
    : Array.from(new Set(refs.flatMap((r) => r.locations || [])))
  const areaLabel = entry.area
    || (refs.length > 1 ? Array.from(new Set(refs.map((r) => r.area))).join(' + ') : base.area)
    || 'cross-cutting'
  const out = {
    title: entry.title || base.title,
    area: areaLabel,
    category: entry.category || base.category || 'other',
    locations,
    problem: entry.problem || base.problem,
    ideal_pattern: entry.ideal_pattern || base.ideal_pattern || '(not stated)',
    refactor: entry.refactor || base.refactor,
    impact: entry.impact || base.impact || 'medium',
    risk: entry.risk || base.risk || 'medium',
    effort: entry.effort || base.effort || 'medium',
    merged_from: refs.map((r) => r.raw_id),
  }
  return (out.title && out.problem && out.refactor) ? out : null
}

const entries = (synthesis && synthesis.consolidated) || []
const materialized = entries.map(materialize).filter(Boolean)
const covered = new Set(materialized.flatMap((p) => p.merged_from))
const orphans = rawIndexed.filter((p) => !covered.has(p.raw_id)).map((p) => ({ ...p, merged_from: [p.raw_id] }))
const synthesisFailed = !materialized.length
const consolidated = synthesisFailed
  ? rawIndexed.map((p) => ({ ...p, merged_from: [p.raw_id] }))
  : materialized.concat(orphans)

const withIds = consolidated.map((p, i) => ({ ...p, id: `P${String(i + 1).padStart(2, '0')}` }))

const proposalText = withIds.map((p) => [
  `${p.id} — ${p.title}`,
  `area: ${p.area} | category: ${p.category} | impact: ${p.impact} | risk: ${p.risk} | effort: ${p.effort}`,
  `locations: ${(p.locations || []).join(', ')}`,
  `problem: ${p.problem}`,
  `ideal pattern: ${p.ideal_pattern}`,
  `refactor: ${p.refactor}`,
].join('\n')).join('\n\n')

// Stage 3 (parallel): one skeptic per emphasis, each voting on every consolidated proposal.
const ballots = await parallel(Array.from({ length: VOTES }, (_unused, i) => () => {
  const emphasis = EMPHASES[i % EMPHASES.length]
  return agent(
    `You are skeptic #${i + 1} of ${VOTES} on a refactor-critique panel, and you hold the WHOLE consolidated proposal list at once. Vote keep/drop on EVERY proposal below. Default to keep=false unless a proposal clearly earns its place.\n\nYour emphasis — apply it on top of the shared bar, do not substitute it for the bar:\n${emphasis.text}\n\nShared bar. Inspect the real code with Read/Grep before judging; these proposals were written by other agents and may be wrong about the code. Set keep=false if ANY of these hold: it does not actually reduce complexity; it changes observable behavior without the proposal acknowledging it; it is over-engineering / premature abstraction / speculative generality; the churn and risk outweigh the benefit; or it contradicts a pattern the codebase already follows. Set keep=true only if it is a real simplification, behavior-preserving (or with risk honestly scoped), and worth doing.\n\nBecause you hold every proposal at once, you can see what a reviewer judging one in isolation cannot: two proposals that contradict each other, that would collide in the same file, or that are the same refactor described twice. When that is why you drop one, name the other proposal's id in your reason.\n\nThere are ${withIds.length} proposals, so you have a hard output budget: keep every reason under 25 words, and spend your reading time on the proposals you are least sure about. Return exactly one vote for each of the ${withIds.length} ids below — no omissions, no duplicates, and no ids that are not listed. Completing the ballot matters more than elaborating any single reason.\n\n${proposalText}\n\nScope: ${args.scopeDescription}`,
    { label: `critique:${emphasis.key}`, phase: 'Critique', schema: CRITIQUE_SCHEMA }
  )
}))

const panel = ballots.filter(Boolean).map((b) => {
  const byId = new Map()
  for (const v of (b.votes || [])) {
    if (v && typeof v.id === 'string' && !byId.has(v.id)) byId.set(v.id, v)
  }
  return byId
})

const judged = withIds.map((p) => {
  const cast = panel.map((b) => b.get(p.id)).filter(Boolean)
  const keeps = cast.filter((v) => v.keep).length
  return {
    ...p,
    kept: cast.length > 0 && keeps > cast.length / 2,
    votes_keep: keeps,
    votes_total: cast.length,
    concerns: cast.filter((v) => !v.keep).map((v) => v.reason).slice(0, 3),
  }
})

const underVoted = judged.filter((p) => p.votes_total < panel.length).length

// Rank survivors: highest impact first, then lowest risk, then lowest effort.
const IMP = { critical: 0, high: 1, medium: 2, low: 3 }
const RISK = { low: 0, medium: 1, high: 2 }
const EFF = { small: 0, medium: 1, large: 2 }
const survivors = judged.filter((p) => p.kept)
  .sort((a, b) => (IMP[a.impact] - IMP[b.impact]) || (RISK[a.risk] - RISK[b.risk]) || (EFF[a.effort] - EFF[b.effort]))

log(`review-kludge: ${areas.length} areas, ${rawProposals.length} raw -> ${withIds.length} consolidated -> ${survivors.length} survived a ${panel.length}-skeptic panel${orphans.length && !synthesisFailed ? `; ${orphans.length} raw proposal(s) the synthesizer omitted were carried through` : ''}${underVoted ? `; ${underVoted} proposal(s) drew fewer than ${panel.length} votes` : ''}${synthesisFailed ? `; SYNTHESIS FAILED — the raw list was used un-merged and ${patterns.length} pattern(s) came back` : ''}`)

return {
  proposals: survivors,
  patterns,
  areas: areas.map((a) => a.name),
  raw: rawProposals.length,
  consolidatedCount: withIds.length,
  orphans: synthesisFailed ? 0 : orphans.length,
  synthesisFailed,
  skeptics: panel.length,
  underVoted,
}
````

## Step 3b: Surface the Run ID for `wfwatch`

The **Workflow** tool runs the swarm in the background and its tool result includes a **run ID** (of the form `wf_…`). The user has a shell function, **`wfwatch`** (defined in their `.zshrc` / `.bashrc`), that live-tails a workflow's progress by that ID.

**In the same turn that launches the workflow — before you yield — print the run ID to the user in a copyable form, with the exact command to watch it.** For example:

```
🧹 review-kludge swarm launched — run ID: wf_ab12cd34
   Watch it live in another terminal:  wfwatch wf_ab12cd34
   One-shot snapshot instead:          wfwatch wf_ab12cd34 --once
```

Use the **actual** `runId` string from the Workflow tool result verbatim (do not fabricate or abbreviate it — `wfwatch` resolves the run's journal by exact ID).

**Say that the Patterns phase is one long turn with no intermediate output**, because otherwise a working synthesis is indistinguishable from a hang and the only way to find out is to poll `journal.jsonl` by hand. The script logs the observation count as it enters the phase, so the journal carries one event between `started Patterns` and the next phase — but a single `agent()` call cannot report progress from inside, so there is nothing further to emit until it returns. Minutes of silence there is the expected shape, not a stall.

**Then end your turn — never block the session on the swarm.** The `Workflow` tool has already returned: the run continues in the background and a task notification re-invokes you when it finishes. So print the block above, say the sweep is running, and yield, which leaves the user free to keep submitting prompts for the whole run. Do not hold the turn open to wait for it — no `TaskOutput` on the workflow's task, no `Monitor`, no `ScheduleWakeup`, no reading the journal or running `wfwatch` yourself on a loop, no sleep, and no filler tool calls to pass the time. None of that makes the result arrive sooner, and all of it costs the user their session for the length of a full swarm. If they send other prompts meanwhile, answer them normally and stay responsive. The completion notification is the **only** thing that resumes this skill; when it arrives, continue with Step 4.

## Step 3c: Fallback when the Workflow tool isn't available

If the preflight found no `Workflow` tool, run the **same** Analyze → Patterns → Critique pipeline manually with the **Agent** tool. This is a supported path, not a degraded guess: the three phases, the agent counts and the batched critique panel are the same ones the script runs, so what it loses is the harness's structured schema-enforcement and true live-streaming and nothing else. Do **not** ask permission first: the user already opted in by invoking the skill.

**Phase 1 — Analyze (parallel):** launch one background `Agent` per feature area (subagent_type `general-purpose`, a cheap model like `sonnet` for the fan-out). Give each the Step-3 analysis prompt for its area (the `LENSES`, the "prefer a pattern already in THIS codebase", the "don't pad / return empty if clean" rules) and ask it to return a JSON array of proposal objects with the `PROPOSAL_ITEM` fields plus concrete `file:line` locations. Collect each result on its completion notification.

**Phase 2 — Patterns (you do it):** you have every area's findings, so synthesize yourself — describe the emergent patterns and produce **one consolidated list**, merging duplicate/overlapping proposals that multiple areas raised (e.g. the same helper reinvented in three places) and keeping each proposal's fields intact. Write the consolidated list to a scratch JSON file (ids `P01…`) so the critique agents can read it without you re-pasting it N times.

**Consolidate by reference here too, exactly as the script does** — tag the raw proposals `R001…` in the scratch file first, then express the consolidated list as `ref_ids` plus only the fields a merge rewrites, and build the full bodies from the references afterwards. Re-emitting every proposal body is what blows the output cap in the script, and your own output has the same ceiling: this phase is the one place in the fallback where the whole list passes through a single turn.

**Phase 3 — Critique (parallel):** launch **`VOTES` skeptic agents** (5 for scale 3, else 3) — the same panel the script runs. Each reads the whole consolidated file and votes keep/drop **on every proposal**, returning a JSON array of `{id, keep, reason}`. Give them the Step-3 skeptic prompt (default keep=false; kill over-engineering/premature-abstraction/behavior-changing/churn; verify claims against real code with Read/Grep — the proposals were written by other agents and may be wrong), including the contradiction check: a proposal dropped because another one conflicts with it, collides in the same file, or duplicates it must name that other id. Give each skeptic one of the script's five emphases (dead-code grep rigor, effort-vs-payoff, layering/correctness, whole-codebase convention, behavior preservation) so they aren't redundant. Tally each proposal over the ballots that actually name it: **majority keeps**. Count the proposals that drew fewer votes than there were skeptics and report that in Step 4 — a batched skeptic can skip a proposal, and a proposal dropped for want of a vote must not read as one the panel rejected. Rank survivors by impact → risk → effort, exactly as the script does.

**Emit a `wfwatch`-compatible journal** so the user can still watch progress. Create `~/.claude/projects/<project-slug>/<session-id>/subagents/workflows/<runId>/journal.jsonl` (any `runId` of the form `wf_…`; the `*/*` in `wfwatch`'s glob matches the project/session dirs). Append one JSONL event per phase step — `{"type":"started","agentId":"<short-label>","phase":"Analyze","label":"…"}` when you launch each area/skeptic, and `{"type":"result","agentId":"<same-label>","phase":"…","label":"…","result":"<short summary string>"}` when it returns. `wfwatch` counts `started` vs `result` and previews the `result` string, so use readable `agentId` labels (e.g. `eng-quests`, `skeptic-3`), keep `started`/`result` counts paired, and print the run id + `wfwatch <runId>` to the user right after Phase 1 launches. Note honestly that it advances **stepwise** (each time you regain control on a completion), not truly live mid-agent.

**Gotcha — interrupts cancel background agents.** If the user interrupts the parent session while area/skeptic agents are in flight, those agents are **hard-cancelled** and cannot be resumed (`SendMessage` returns "stopped by the user"). Detect stalls (their task ids stop being found / transcripts stop growing) and **relaunch** the cancelled ones fresh — the user re-invoking or pushing the skill forward is your authorization to relaunch. Never fabricate or predict a cancelled agent's findings.

Then continue to Step 4 exactly as written (present the report, offer next steps). In Step 4's honesty line, state that the run used the Agent-based fallback because the Workflow tool wasn't provisioned.

## Step 4: Present the Refactor Report

When the workflow returns, present its results — do **not** invent proposals.

Lead with the **emergent patterns** the synthesizer found (a short paragraph or bullet list): the conventions the code is converging toward, and where it diverges. This frames the refactors.

Then list the surviving **refactor proposals**, ranked highest-impact/lowest-risk first. For each:
- A header: `P<nn> [IMPACT · risk · effort] Title — area`. Keep the id: a skeptic's concern may drop one proposal by naming another, and the reference is unreadable if the ids are stripped.
- **Problem** — the kludge and why it costs maintainers.
- **Move toward** — the ideal pattern.
- **Refactor** — the concrete steps, with `file:line` locations as clickable links.
- The critique vote (e.g. "kept 3/3").

Close with a one-line summary: areas reviewed, raw proposals raised, how many survived adversarial critique (the churn-for-churn and over-engineering the panel filtered out is a feature — say so). If nothing survived, say so plainly and note the areas reviewed — clean code is a valid result.

**If `underVoted` came back above zero, name it in that line.** Those proposals were dropped because part of the panel never voted on them, which is a skeptic running out of attention rather than a verdict on the proposal — and it is the one way this pipeline can report a thin result that looks like a clean codebase.

**If `synthesisFailed` came back true, lead with it and never present the run as clean.** Say plainly, before the proposals: the synthesis stage produced nothing, so there are **no emergent patterns** — the headline deliverable is missing, not absent because the code has no patterns — and the proposals below are the **raw, un-merged, un-deduplicated** list, in which the same refactor may appear several times under different ids. A degraded run is a partial result to re-run, and the one thing it must never look like is a verdict on the codebase. Recommend re-running, at a narrower scope or a lower `scale` if the area count was large.

**If `orphans` came back above zero, name the count in the summary line.** Those are raw proposals the synthesizer did not reference, carried through as passthroughs rather than dropped. A handful is ordinary — the synthesizer lost track of a few ids — and over-inclusion is safe because the panel filters. A number close to `raw` means the synthesis barely consolidated anything, which is worth saying even though `synthesisFailed` is false.

Do not refactor anything in this step — this skill reviews and proposes, it does not edit.

## Step 5: Offer Next Steps

After the report, offer (as plain text, not `AskUserQuestion`):
- Implement one or more of the proposals (you can do the refactor if the user picks some — smallest-risk first). Add no comments while refactoring: no note marking an extracted helper, a converged pattern, or what the old shape was. A refactor's whole claim is that the code now reads for itself.
- Re-run at a higher `scale`, or on a specific area, for a deeper pass.
- Dive deeper into any single proposal (show the full before/after shape).

## Important Rules

1. **Behavior-preserving by default.** Refactors should not change observable behavior. If a proposal can't avoid it, that must be called out explicitly, not buried.
2. **No refactoring for its own sake.** Reject churn-for-churn, speculative generality, and premature abstraction — the critique panel enforces this; honor it when presenting.
3. **Converge on emergent patterns, don't invent.** Prefer the best pattern already present in the codebase over a novel architecture.
4. **Scope to recent features.** Review the areas identified in Steps 1–2. Don't sprawl into unrelated subsystems.
5. **Review only, by default.** Do not modify code, commit, push, or touch external state unless the user explicitly asks in Step 5.
6. **Never fabricate or pad.** Report only what survived critique. "Nothing worth changing" is a valid, good outcome.
7. **Report honestly.** If scope detection was uncertain, an area was skipped, or a stage errored, say so.
