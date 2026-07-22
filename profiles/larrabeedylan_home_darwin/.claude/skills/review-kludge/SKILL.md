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
  | awk 'NF==3 { added=$1; deleted=$2; path=$3;
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

| Scope | `scale` | Critique votes per proposal |
|---|---|---|
| Small (1–2 areas) | `1` | 3 |
| Medium (3–5 areas) | `2` | 3 |
| Large (6+ areas / "be exhaustive") | `3` | 5 |

Call the **Workflow** tool with the script below, passing `args` as a JSON object:

```json
{ "scopeDescription": "<what you're reviewing + the window>", "areas": [ { "name": "checkout", "paths": "src/checkout, src/api/checkout.ts", "summary": "..." } ], "scale": <1|2|3> }
```

Use this script verbatim. The one barrier (pattern synthesis) is deliberate — distilling the emergent architecture and merging cross-cutting duplicates genuinely needs every area's findings at once.

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
  return { proposals: [], patterns: [], areas: [], raw: 0 }
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

const PROPOSAL_ITEM = {
  type: 'object',
  properties: {
    title: { type: 'string' },
    area: { type: 'string' },
    category: { type: 'string', enum: ['duplication', 'inconsistent-pattern', 'over-complex', 'dead-code', 'leaky-abstraction', 'ai-slop', 'layering', 'config-sprawl', 'other'] },
    locations: { type: 'array', items: { type: 'string' } },
    problem: { type: 'string' },
    ideal_pattern: { type: 'string' },
    refactor: { type: 'string' },
    impact: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
    risk: { type: 'string', enum: ['low', 'medium', 'high'] },
    effort: { type: 'string', enum: ['small', 'medium', 'large'] },
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
    proposals: { type: 'array', items: PROPOSAL_ITEM },
  },
  required: ['patterns', 'proposals'],
  additionalProperties: false,
}

const CRITIQUE_SCHEMA = {
  type: 'object',
  properties: {
    keep: { type: 'boolean' },
    reason: { type: 'string' },
  },
  required: ['keep', 'reason'],
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
  return { proposals: [], patterns: [], areas: areas.map((a) => a.name), raw: 0 }
}

// Stage 2 (barrier — needs ALL areas): distill emergent patterns + cross-cutting refactors, dedupe.
const synthesis = await agent(
  `You are the architecture synthesizer for a refactoring swarm. Below are kludge observations gathered independently from every feature area of: ${args.scopeDescription}.\n\nDo two things:\n1. Describe the IDEAL PATTERNS that have emerged across these features — the conventions the codebase is converging toward — and note where current code diverges from them.\n2. Produce a consolidated proposal list: merge duplicate/overlapping proposals from different areas into one, and ADD cross-cutting refactors that no single-area reviewer could see (e.g. three areas each reinventing the same helper). Keep every proposal's fields intact and honest about impact/risk/effort.\n\nDo not invent problems to pad the list. Prefer converging on patterns that already exist in the codebase over introducing novel architecture.\n\nObservations (JSON):\n${JSON.stringify(rawProposals)}`,
  { label: 'synthesize-patterns', phase: 'Patterns', schema: SYNTHESIS_SCHEMA }
)

const consolidated = (synthesis && synthesis.proposals && synthesis.proposals.length) ? synthesis.proposals : rawProposals
const patterns = (synthesis && synthesis.patterns) || []

// Stage 3 (parallel): adversarially critique every consolidated proposal.
const judged = await parallel(consolidated.map((p) => () =>
  parallel(Array.from({ length: VOTES }, (_unused, i) => () =>
    agent(
      `You are skeptic #${i + 1} on a refactor-critique panel. Challenge the proposal below. Default to keep=false unless it clearly earns its place.\n\nInspect the real code with Read/Grep before judging. Set keep=false if ANY of these hold: it does not actually reduce complexity; it changes observable behavior without the proposal acknowledging it; it is over-engineering / premature abstraction / speculative generality; the churn and risk outweigh the benefit; or it contradicts a pattern the codebase already follows. Set keep=true only if it is a real simplification, behavior-preserving (or with risk honestly scoped), and worth doing.\n\nProposal: ${p.title}\nArea: ${p.area} | category: ${p.category} | impact: ${p.impact} | risk: ${p.risk} | effort: ${p.effort}\nLocations: ${(p.locations || []).join(', ')}\nProblem: ${p.problem}\nIdeal pattern: ${p.ideal_pattern}\nRefactor: ${p.refactor}\n\nScope: ${args.scopeDescription}`,
      { label: `critique:${p.area}`, phase: 'Critique', schema: CRITIQUE_SCHEMA }
    )
  )).then((votes) => {
    const clean = votes.filter(Boolean)
    const keeps = clean.filter((v) => v.keep).length
    return {
      ...p,
      kept: keeps > clean.length / 2,
      votes_keep: keeps,
      votes_total: clean.length,
      concerns: clean.filter((v) => !v.keep).map((v) => v.reason).slice(0, 3),
    }
  })
))

// Rank survivors: highest impact first, then lowest risk, then lowest effort.
const IMP = { critical: 0, high: 1, medium: 2, low: 3 }
const RISK = { low: 0, medium: 1, high: 2 }
const EFF = { small: 0, medium: 1, large: 2 }
const survivors = judged.filter(Boolean).filter((p) => p.kept)
  .sort((a, b) => (IMP[a.impact] - IMP[b.impact]) || (RISK[a.risk] - RISK[b.risk]) || (EFF[a.effort] - EFF[b.effort]))

log(`review-kludge: ${areas.length} areas, ${rawProposals.length} raw -> ${consolidated.length} consolidated -> ${survivors.length} survived ${VOTES}-vote critique`)

return { proposals: survivors, patterns, areas: areas.map((a) => a.name), raw: rawProposals.length }
````

## Step 3b: Surface the Run ID for `wfwatch`

The **Workflow** tool runs the swarm in the background and its tool result includes a **run ID** (of the form `wf_…`). The user has a shell function, **`wfwatch`** (defined in their `.zshrc` / `.bashrc`), that live-tails a workflow's progress by that ID.

**Immediately after launching the workflow — before waiting for it to finish — print the run ID to the user in a copyable form, with the exact command to watch it.** For example:

```
🧹 review-kludge swarm launched — run ID: wf_ab12cd34
   Watch it live in another terminal:  wfwatch wf_ab12cd34
   One-shot snapshot instead:          wfwatch wf_ab12cd34 --once
```

Use the **actual** `runId` string from the Workflow tool result verbatim (do not fabricate or abbreviate it — `wfwatch` resolves the run's journal by exact ID). Then proceed to wait for the workflow to complete and continue with Step 4.

## Step 4: Present the Refactor Report

When the workflow returns, present its results — do **not** invent proposals.

Lead with the **emergent patterns** the synthesizer found (a short paragraph or bullet list): the conventions the code is converging toward, and where it diverges. This frames the refactors.

Then list the surviving **refactor proposals**, ranked highest-impact/lowest-risk first. For each:
- A header: `[IMPACT · risk · effort] Title — area`.
- **Problem** — the kludge and why it costs maintainers.
- **Move toward** — the ideal pattern.
- **Refactor** — the concrete steps, with `file:line` locations as clickable links.
- The critique vote (e.g. "kept 3/3").

Close with a one-line summary: areas reviewed, raw proposals raised, how many survived adversarial critique (the churn-for-churn and over-engineering the panel filtered out is a feature — say so). If nothing survived, say so plainly and note the areas reviewed — clean code is a valid result.

Do not refactor anything in this step — this skill reviews and proposes, it does not edit.

## Step 5: Offer Next Steps

After the report, offer (as plain text, not `AskUserQuestion`):
- Implement one or more of the proposals (you can do the refactor if the user picks some — smallest-risk first).
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

## Step 6: Self-Improvement

After the run, reflect on how it went:

- Did scope detection find the right "recent large features," or did it miss/over-include areas?
- Was the feature grouping coherent, or too coarse/fine?
- Did the synthesizer surface genuine emergent patterns, or generic advice?
- Did the critique panel correctly kill over-engineering while keeping real wins? Tune the votes or the critique prompt if not.

If any issue was encountered, **edit this skill file** (`~/.claude/skills/review-kludge/SKILL.md`) with a surgical fix so the next run is better. Briefly tell the user what you changed and why.
