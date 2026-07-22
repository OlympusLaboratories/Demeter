# Ultra-Review — Adversarial Review Swarm

Run a thorough, multi-agent **adversarial review** of the changes currently being proposed locally. A fleet of reviewers examines the diff from independent angles; every candidate finding is then attacked by a panel of skeptics, and only findings that survive refutation are reported. The goal is a high-signal, low-noise review that catches real defects a single pass would miss.

**Parameter:** `$ARGUMENTS` — optional. A git ref/range to review against (e.g. `main`, `origin/main`, `HEAD~3`). If omitted, the skill reviews everything that differs from the repository's default branch, including uncommitted work.

This skill uses the **Workflow** tool to orchestrate the swarm. Invoking it is an explicit opt-in to multi-agent orchestration — proceed without asking for further permission, but do respect the scaling rules below so the run stays proportional to the diff.

## Step 1: Gather the Proposed Changes

Determine what "the changes being proposed locally" means and collect the diff. Run these with the Bash tool:

```bash
# Default branch (fall back to main/master if origin/HEAD isn't set)
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
[ -z "$DEFAULT_BRANCH" ] && DEFAULT_BRANCH=$(git branch -r | grep -E 'origin/(main|master)$' | head -1 | sed 's@.*origin/@@')
[ -z "$DEFAULT_BRANCH" ] && DEFAULT_BRANCH=main

# Base to diff against: the argument if given, else the merge-base with the default branch
BASE="${ARGUMENTS:-$DEFAULT_BRANCH}"
MERGE_BASE=$(git merge-base HEAD "origin/$BASE" 2>/dev/null || git merge-base HEAD "$BASE" 2>/dev/null || echo "$BASE")

# The full set of proposed changes = committed-on-branch + staged + unstaged, vs the base.
git --no-pager diff --stat "$MERGE_BASE" -- . ; echo "--- names ---"; git --no-pager diff --name-status "$MERGE_BASE" -- .
```

Then capture the **full unified diff** (with a few lines of context) for the workflow:

```bash
git --no-pager diff "$MERGE_BASE" -- .
```

**Handle these cases before proceeding:**
- **No changes** (empty diff): tell the user there's nothing to review and stop.
- **Huge diff** (say, >4000 changed lines or >40 files): note it to the user. Pass the **file list** plus per-file diffs to the workflow rather than one giant blob, and let reviewers `Read`/`Grep` files directly for context. Reviewers always have file-system access, so the diff is a map, not the whole territory.

## Step 2: Choose the Scale

Size the swarm to the change so a one-line fix doesn't summon a fleet:

| Diff size | `scale` | Verifier votes per finding |
|---|---|---|
| Small (≤ ~150 lines, ≤ 5 files) | `1` | 3 |
| Medium | `2` | 3 |
| Large / "be exhaustive" / user asks for thorough | `3` | 5 |

If the user explicitly asks to be exhaustive or comprehensive, use `scale: 3` regardless of size.

## Step 3: Run the Review Swarm

Call the **Workflow** tool with the script below, passing `args` as a JSON object:

```json
{ "diff": "<the unified diff from Step 1>", "files": "<name-status list>", "defaultBranch": "<DEFAULT_BRANCH>", "scale": <1|2|3> }
```

Use this script verbatim (it encodes the review → adversarial-verify pipeline). Do not restructure it into barriers — the pipeline lets each dimension's findings start verification as soon as that dimension finishes.

````js
export const meta = {
  name: 'review-code',
  description: 'Adversarial multi-agent review of the proposed local changes',
  phases: [
    { title: 'Review' },
    { title: 'Verify' },
  ],
}

// args = { diff, files, defaultBranch, scale }
const scale = (args && args.scale) || 1
const VOTES = scale >= 3 ? 5 : 3

const DIMENSIONS = [
  { key: 'correctness', prompt: 'Correctness bugs: logic errors, off-by-one, null/undefined deref, inverted or wrong conditionals, broken control flow, incorrect API/library usage, bad error handling, resource leaks.' },
  { key: 'security',    prompt: 'Security issues: injection (SQL/shell/HTML), auth/authz gaps, unsafe deserialization, secrets committed to code, path traversal, SSRF, unsafe eval/exec, missing or wrong input validation, TOCTOU.' },
  { key: 'concurrency', prompt: 'Concurrency & state hazards: data races, unsynchronized shared state, deadlocks, await/async mistakes, non-atomic read-modify-write, ordering assumptions.' },
  { key: 'edge-cases',  prompt: 'Unhandled edge cases: empty/huge inputs, boundary values, error/exception paths, partial failure, timeouts/retries, unexpected types, unicode/encoding.' },
  { key: 'regressions', prompt: 'Regressions & breaking changes: altered public behavior or contracts, removed handling, changed defaults, backward-incompatible signature or schema changes, migration hazards.' },
  { key: 'tests',       prompt: 'Test gaps: new/changed logic with no coverage, assertions too weak to catch the real failure modes, tests that assert the wrong thing, missing negative/edge tests.' },
]
// scale 3 adds extra depth on the two most defect-dense lenses
if (scale >= 3) {
  DIMENSIONS.push({ key: 'correctness-2', prompt: 'A second, independent correctness pass focused on data flow across function boundaries and integration points touched by the diff.' })
  DIMENSIONS.push({ key: 'quality',       prompt: 'Maintainability defects that cause future bugs: duplicated logic that will drift, misleading names, dead code, needless complexity, swallowed errors.' })
}

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          category: { type: 'string' },
          summary: { type: 'string' },
          failure_scenario: { type: 'string' },
        },
        required: ['file', 'line', 'severity', 'summary', 'failure_scenario'],
        additionalProperties: false,
      },
    },
  },
  required: ['findings'],
  additionalProperties: false,
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    real: { type: 'boolean' },
    reason: { type: 'string' },
  },
  required: ['real', 'reason'],
  additionalProperties: false,
}

const context = `Default branch: ${args.defaultBranch}\n\nChanged files (name-status):\n${args.files}\n\nUnified diff of the proposed LOCAL changes:\n\n${args.diff}`

const rounds = await pipeline(
  DIMENSIONS,
  // Stage 1 — review through one lens
  (d) => agent(
    `You are one reviewer in an adversarial code-review swarm. Review the proposed LOCAL changes through the "${d.key}" lens ONLY.\n\nFocus: ${d.prompt}\n\nRules:\n- Report ONLY defects introduced or newly exposed by THIS diff — not pre-existing issues elsewhere.\n- Before asserting anything, use Read/Grep/Glob to inspect the surrounding code and confirm the code path really behaves as you claim.\n- Each finding needs: file, line (best estimate in the new file), severity, a one-sentence summary, and a concrete failure_scenario (specific inputs/state -> wrong output or crash).\n- Prefer a few high-confidence findings over many speculative ones. If you find nothing real, return an empty list.\n\n${context}`,
    { label: `review:${d.key}`, phase: 'Review', schema: FINDINGS_SCHEMA }
  ),
  // Stage 2 — adversarially verify every finding from that lens
  (review, d) => parallel(((review && review.findings) || []).map((f) => () =>
    parallel(Array.from({ length: VOTES }, (_unused, i) => () =>
      agent(
        `You are skeptic #${i + 1} on a verification panel. Your job is to REFUTE the review finding below. Assume it is wrong until the code proves otherwise.\n\nInspect the actual code with Read/Grep. Set real=false unless you can trace a concrete, reachable code path that produces the claimed failure with realistic inputs. Guarding code, callers that make the input impossible, or framework behavior that prevents it all count as refutation. Set real=true ONLY if the defect genuinely holds.\n\nFinding (${d.key}, severity ${f.severity}): ${f.summary}\nLocation: ${f.file}:${f.line}\nClaimed failure: ${f.failure_scenario}\n\n${context}`,
        { label: `verify:${d.key}:${f.file}`, phase: 'Verify', schema: VERDICT_SCHEMA }
      )
    )).then((votes) => {
      const clean = votes.filter(Boolean)
      const realCount = clean.filter((v) => v.real).length
      return {
        ...f,
        dimension: d.key,
        confirmed: realCount > clean.length / 2,
        votes_real: realCount,
        votes_total: clean.length,
        refutations: clean.filter((v) => !v.real).map((v) => v.reason).slice(0, 3),
      }
    })
  ))
)

// Flatten, keep only confirmed, dedupe by file+line+summary, rank by severity.
const RANK = { critical: 0, high: 1, medium: 2, low: 3 }
const seen = new Set()
const confirmed = rounds.flat().filter(Boolean)
  .filter((f) => f.confirmed)
  .filter((f) => {
    const k = `${f.file}:${f.line}:${f.summary}`
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })
  .sort((a, b) => (RANK[a.severity] - RANK[b.severity]) || (b.votes_real - a.votes_real))

const dimsRun = DIMENSIONS.map((d) => d.key)
const raw = rounds.flat().filter(Boolean).length
log(`review-code: ${dimsRun.length} lenses, ${raw} candidate findings, ${confirmed.length} confirmed after ${VOTES}-vote adversarial verification`)

return { confirmed, dimensions: dimsRun, candidates: raw, votes: VOTES }
````

## Step 3b: Surface the Run ID for `wfwatch`

The **Workflow** tool runs the swarm in the background and its tool result includes a **run ID** (of the form `wf_…`). The user has a shell function, **`wfwatch`** (defined in their `.zshrc` / `.bashrc`), that live-tails a workflow's progress by that ID.

**Immediately after launching the workflow — before waiting for it to finish — print the run ID to the user in a copyable form, with the exact command to watch it.** For example:

```
🛰  review-code swarm launched — run ID: wf_ab12cd34
   Watch it live in another terminal:  wfwatch wf_ab12cd34
   One-shot snapshot instead:          wfwatch wf_ab12cd34 --once
```

Use the **actual** `runId` string from the Workflow tool result verbatim (do not fabricate or abbreviate it — `wfwatch` resolves the run's journal by exact ID). Then proceed to wait for the workflow to complete and continue with Step 4.

## Step 4: Present the Report

When the workflow returns, read `journal.jsonl` semantics from the returned object — do **not** invent findings. Present the confirmed findings to the user, ranked most-severe first. For each:

- A header line: `[SEVERITY] path/to/file.ext:line — one-sentence summary` (make the `file:line` a clickable markdown link).
- The concrete **failure scenario**.
- Which review lens found it and the verification vote (e.g. "confirmed 3/3, correctness").

Then a short summary line: how many lenses ran, how many candidate findings were raised, and how many survived adversarial verification (the noise the swarm filtered out is a feature — say so). If **nothing** was confirmed, state that clearly and mention which lenses ran, so the user knows the review was thorough rather than skipped.

Do not fix anything in this step — this skill reviews, it does not edit.

## Step 5: Offer Next Steps

After the report, offer (as plain text, not `AskUserQuestion`):
- Address the top N findings (you can implement fixes if the user picks some).
- Re-run at a higher `scale` for an even deeper pass.
- Dive deeper into any single finding.

## Important Rules

1. **Never fabricate or pad findings.** Report only what the workflow confirmed. An empty result is a valid, good outcome.
2. **Scale to the change.** Don't summon `scale: 3` for a typo fix. Follow the table in Step 2.
3. **Review only, by default.** Do not modify code, commit, push, or touch external state unless the user explicitly asks in Step 5.
4. **Findings must be diff-scoped.** Pre-existing issues outside the proposed changes are out of scope unless the diff newly exposes them.
5. **Verification is adversarial on purpose.** The skeptic panel defaults to "refuted"; that's what keeps the signal high. Don't loosen it.
6. **Report honestly.** If the diff was truncated, a lens errored, or coverage was capped, say so.

## Step 6: Self-Improvement

After the run, reflect on how it went:

- Was the diff gathered correctly for this repo's branch setup (merge-base, default branch detection)?
- Was the scale appropriate, or did the swarm over-/under-cover the change?
- Did the adversarial panel wrongly kill real bugs, or let noise through? Tune the votes or the refute prompt if so.
- Were the review lenses the right ones for this codebase's languages/frameworks?

If any issue was encountered, **edit this skill file** (`~/.claude/skills/review-code/SKILL.md`) with a surgical fix so the next run is better. Briefly tell the user what you changed and why.
