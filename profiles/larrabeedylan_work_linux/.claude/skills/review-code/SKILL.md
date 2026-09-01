# Ultra-Review — Adversarial Review Swarm

Run a thorough, multi-agent **adversarial review** of the changes currently being proposed locally. A fleet of reviewers examines the diff from independent angles; every candidate finding is then attacked by a panel of skeptics, and only findings that survive refutation are reported. The goal is a high-signal, low-noise review that catches real defects a single pass would miss.

**Parameter:** `$ARGUMENTS` — optional. Either a **base** to diff your own work against (`main`, `origin/main`, `HEAD~3`) or an **incoming branch** written by somebody else that you have been asked to review (`dylan/ENG-441`, `origin/feature-x`). Step 0 decides which, and `--base <ref>` / `--branch <ref>` force the choice. With no argument, the skill reviews everything that differs from the repository's default branch, including uncommitted work.

In **Incoming mode** the skill fetches the branch, checks it out into its own worktree, runs the same adversarial review, and then produces a second deliverable: a pack of ready-to-paste MR comments with verified line anchors, so the review can be left on the author's MR without rewriting it by hand.

This skill uses the **Workflow** tool to orchestrate the swarm. Invoking it is an explicit opt-in to multi-agent orchestration — proceed without asking for further permission, but do respect the scaling rules below so the run stays proportional to the diff.

## Step 0: Resolve What You Are Reviewing

`$ARGUMENTS` selects one of two modes and they mean opposite things — the same word is either the base you diff *against* or the branch you diff *for*. Resolve it first, and say the resolution out loud before spending a fleet on it.

| Mode | Chosen when | What gets reviewed |
|---|---|---|
| **Local** (default) | no argument, or the argument is the default branch or a non-branch commit-ish (`main`, `origin/main`, `HEAD~3`, a tag, a SHA) | your own committed + uncommitted work, diffed against that base |
| **Incoming** | the argument names a branch that is not the default branch — somebody else's change you have been asked to review | that branch as pushed, diffed against its merge-base with the default branch |

Flags override the heuristic and are the escape hatch when it guesses wrong:

- `--base <ref>` — force Local mode against `<ref>`.
- `--branch <ref>` — force Incoming mode on `<ref>`.

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
[ -z "$DEFAULT_BRANCH" ] && DEFAULT_BRANCH=$(git branch -r | grep -E 'origin/(main|master)$' | head -1 | sed 's@.*origin/@@')
[ -z "$DEFAULT_BRANCH" ] && DEFAULT_BRANCH=main

ARG="<the argument, with any flag stripped>"
NAME="${ARG#origin/}"

git fetch origin --prune          # cheap, and an incoming branch may not be known locally yet

IS_BRANCH=no
if [ "$NAME" != HEAD ]; then          # `HEAD` is a commit-ish and `origin/HEAD` is a pointer to
                                      # the default branch; neither is a branch to review, and
                                      # `refs/remotes/origin/HEAD` exists in most clones
  git show-ref --verify --quiet "refs/remotes/origin/$NAME" && IS_BRANCH=yes
  git show-ref --verify --quiet "refs/heads/$NAME" && IS_BRANCH=yes
fi
```

**Incoming** when `IS_BRANCH=yes` and `NAME` is not `$DEFAULT_BRANCH`; **Local** otherwise. A ref that `git rev-parse` resolves but that names no branch — `HEAD~3`, a tag, a SHA — is always a base and never an incoming review.

A local branch of the same name does **not** make it Local mode. You may already have their branch from a previous review, and the local copy may be stale; Incoming mode always reviews `origin/$NAME` as pushed, not whatever your checkout remembers.

If the argument resolves to nothing even after the fetch, stop and ask which branch was meant. Do not fall back to reviewing local work — that produces a confident, clean-looking review of entirely the wrong change.

**State the resolution in one line before continuing**, e.g. `Incoming review of dylan/ENG-441 (17 commits, 9 files) against its merge-base with main.` A wrong guess costs one sentence to correct now and a whole swarm to correct later.

## Step 1: Gather the Proposed Changes

In **Local mode**, determine what "the changes being proposed locally" means and collect the diff. Run these with the Bash tool:

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

Also capture the repo root of the checkout being reviewed — the workflow needs it to keep reviewers in bounds:

```bash
git rev-parse --show-toplevel
```

Store as `REPO_ROOT`.

**Handle these cases before proceeding:**
- **No changes** (empty diff): tell the user there's nothing to review and stop.
- **Huge diff** (say, >4000 changed lines or >40 files): note it to the user. Pass the **file list** plus per-file diffs to the workflow rather than one giant blob, and let reviewers `Read`/`Grep` files directly for context. Reviewers always have file-system access, so the diff is a map, not the whole territory.
- **Diff lives outside the session's working directory** (a worktree of another repo, a sibling checkout, any `REPO_ROOT` that isn't the cwd): run every Step 1 command with `cd <that path>` and pass that path as `repoRoot`. This case has burned a real run — see the containment rules in Step 3, which you must not skip. Subagents inherit the *session's* cwd, not yours, so a reviewer told only "the file is over there" will still `Grep` the cwd, latch onto whatever unrelated code matches the diff's vocabulary, and review that instead. Nothing about the output will look wrong: agents complete cleanly, findings are specific and well-argued, and the verification panel confirms them — against the wrong file.

### Step 1b: Incoming mode — fetch, check out, and diff their branch

**Never check their branch out in the working tree you are standing in.** That rewrites the user's files and can destroy uncommitted work. It goes in its own worktree, which is how the rest of this setup already works (`wt`, `wtl`, `wtclean`):

```bash
ROOT=$(git worktree list --porcelain | awk '/^worktree /{ print substr($0,10); exit }')
REVIEW_WT="$ROOT/.claude/worktrees/review/$NAME"
BASE_SHA=$(git merge-base "origin/$NAME" "origin/$DEFAULT_BRANCH")

if [ -d "$REVIEW_WT" ]; then
  git -C "$REVIEW_WT" fetch origin "$NAME" && git -C "$REVIEW_WT" checkout --detach FETCH_HEAD
else
  git worktree add --detach "$REVIEW_WT" "origin/$NAME"
fi
```

The worktree lands inside the repo at `.claude/worktrees/`, matching where `wt` puts everything else — which assumes that path is gitignored in the repo being reviewed. Check it is before creating anything: an un-ignored worktree shows up in the author's `git status` as an embedded repository, and a stray `git add .` can commit it.

`--detach` is deliberate. This is a review, not a checkout to work in: nothing can be committed onto their branch by accident, there is no collision with a local branch of the same name, and re-running after they push more commits is a fetch plus a checkout rather than a merge.

Then gather everything **from inside the worktree**, against the merge-base:

```bash
cd "$REVIEW_WT"
git --no-pager diff --name-status "$BASE_SHA"      # -> files
git --no-pager diff "$BASE_SHA"                    # -> diff
git rev-parse --show-toplevel                      # -> REPO_ROOT (the worktree, NOT your cwd)
git --no-pager log --oneline "$BASE_SHA..HEAD"     # orientation: what they say they did
```

`REPO_ROOT` is the worktree path, and passing it correctly matters more here than anywhere else in this skill. Incoming mode makes "the diff lives outside the session's working directory" the *normal* case rather than the exception below — subagents inherit the session's cwd, so a reviewer that is not pointed at the worktree will read your checkout, find code with familiar names, and review the wrong branch convincingly.

There is no uncommitted work to consider in this mode. You are reviewing what they pushed; do not diff working-tree state, and do not review commits that exist only in your local copy of their branch.

Pass `changeLabel` to the workflow as `incoming changes on branch <NAME>` so the reviewers are not told they are looking at local work.

**Never let domain context name symbols that exist in the cwd but not in the diff.** When you write the orientation blurb for the reviewers (what the service does, what the change is for), keep it in the diff's own vocabulary. Borrowing identifiers from a sibling branch or a design doc — a Go type, a function name, a field like `Dataset.access[]` — hands every agent a search term that resolves somewhere other than the code under review, and that is exactly how the drift above happens.

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
{ "diff": "<the unified diff from Step 1>", "files": "<name-status list>", "defaultBranch": "<DEFAULT_BRANCH>", "repoRoot": "<REPO_ROOT>", "scale": <1|2|3>, "changeLabel": "<omit in Local mode; 'incoming changes on branch <NAME>' in Incoming mode>" }
```

**Pass `args` as a real JSON object, never as a JSON-encoded string.** If it arrives as a string, every `args.x` lookup is `undefined` and reviewers receive a prompt whose diff section reads literally `undefined`. They do not fail — they go hunting in the working directory and produce detailed, confident findings about code that has nothing to do with your change. This has happened twice. The script now hard-throws on missing `diff`/`files`/`repoRoot` rather than running blind, so the failure is immediate and obvious instead of arriving as a plausible-looking report.

`repoRoot` is required. The script uses it twice: it tells reviewers where the code actually is, and it **deterministically drops any finding whose file does not resolve under it**. That filter is a backstop, not the primary defense — the primary defense is that reviewers actually receive the diff.

**After launch, confirm the reviewers got the diff before trusting any result.** Read the first agent transcript in the run's directory and check that the prompt ends with real diff text, not `undefined`:

```bash
python3 - <<'PY'
import json,glob,sys
d=sorted(glob.glob('<transcriptDir>/agent-*.jsonl'))[0]
for l in open(d):
    m=(json.loads(l).get('message') or {})
    if m.get('role')!='user': continue
    c=m.get('content'); t=c if isinstance(c,str) else ' '.join(x.get('text','') for x in c if isinstance(x,dict))
    i=t.find('Unified diff'); print(t[i:i+300] if i>=0 else 'NO DIFF SECTION'); break
PY
```

If that prints `undefined`, stop the run immediately (`TaskStop`) — every finding it produces will be about the wrong code.

Use this script verbatim (it encodes the review → adversarial-verify pipeline). Do not restructure it into barriers — the pipeline lets each dimension's findings start verification as soon as that dimension finishes.

**Always pass the script inline via `script`. Never invoke this skill's workflow with `scriptPath` or `resumeFromRunId`.** Every Workflow call snapshots its script to disk and offers that path back for cheap re-runs — but the snapshot is frozen at the moment it was taken. Reusing it silently replays whatever version of this pipeline was current *then*, discarding any correction made to this file since, while the run looks entirely normal. That has already happened once: a fixed skill was bypassed by a `scriptPath` pointing at the pre-fix snapshot from the run it was fixing. If you are re-running after a failed review — the exact moment the shortcut is most tempting — resend the script from this file.

The one sanctioned exception is `/workflow-resume`, which rescues a run this skill lost to a spend limit or a kill. It pairs `resumeFromRunId` with the script re-read from **this** file rather than the snapshot, so the cache is reused and the fix is not discarded. Resuming any other way is the bug above.

````js
export const meta = {
  name: 'review-code',
  description: 'Adversarial multi-agent review of the proposed local changes',
  phases: [
    { title: 'Review' },
    { title: 'Verify' },
  ],
}

// args = { diff, files, defaultBranch, repoRoot, scale }
//
// `args` may arrive as an object OR as a JSON-encoded string depending on how
// the caller passed it. A string is the dangerous case: every `args.x` lookup
// yields `undefined`, so reviewers are handed a prompt whose diff section
// literally reads "undefined". They do not error — they go looking for
// something to review, find unrelated code in the working directory, and
// report confident, well-argued findings about the wrong files. Both known
// failures of this skill were this bug. Normalise, then refuse to start.
const A = typeof args === 'string' ? JSON.parse(args) : (args || {})
for (const k of ['diff', 'files', 'repoRoot']) {
  if (typeof A[k] !== 'string' || !A[k].trim()) {
    throw new Error(
      `review-code: args.${k} is missing or empty (got ${typeof A[k]}). ` +
      `Refusing to spawn reviewers with no diff — they would search the working ` +
      `directory and review unrelated code while looking healthy. ` +
      `Pass args as a JSON OBJECT, not a JSON-encoded string.`
    )
  }
}
const scale = A.scale || 1
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

const repoRoot = A.repoRoot

// Reviewers inherit the SESSION's cwd, which may not be the checkout under
// review. Without this, they grep the cwd, find code that merely shares
// vocabulary with the diff, and review that instead — cleanly, confidently,
// and entirely wrongly. Enforced again by the filter below.
const scopeRule = repoRoot
  ? `\n\nSCOPE — NON-NEGOTIABLE:\nThe checkout under review is rooted at ${repoRoot}. Your shell's working directory is NOT this root; do not assume it is.\n- Every Read/Grep/Glob must be issued against an absolute path under ${repoRoot}.\n- Do NOT search your working directory. If a Grep returns a path outside ${repoRoot}, that file is not under review — ignore it entirely, no matter how relevant it looks.\n- Every finding's \`file\` must be a path under ${repoRoot} (or repo-relative to it). A finding about any other file will be discarded, and the effort spent on it is wasted.\n- If you cannot find the changed files under ${repoRoot}, return an empty list and stop. Do NOT substitute similar-looking code from elsewhere.\n`
  : ''

const changeLabel = (A.changeLabel && String(A.changeLabel).trim()) || 'proposed LOCAL changes'
const context = `Default branch: ${A.defaultBranch}\nRepo root under review: ${repoRoot}${scopeRule}\n\nChanged files (name-status):\n${A.files}\n\nUnified diff of the ${changeLabel}:\n\n${A.diff}`

// Files actually touched by the diff — the only legitimate finding locations.
const changedFiles = new Set(
  A.files.split('\n')
    .map((l) => l.trim().split(/\s+/).pop() || '')
    .filter((p) => p && p.includes('.'))
)
if (!changedFiles.size) {
  throw new Error(`review-code: could not parse any file path out of args.files:\n${A.files}\nRefusing to run with an unenforceable scope filter.`)
}
// Fails CLOSED. An empty or unparseable file list must never mean "allow
// everything" — that is precisely how out-of-scope findings reached the report.
const inScope = (f) => {
  if (!f) return false
  if (f.startsWith('/') && !f.startsWith(repoRoot)) return false
  for (const c of changedFiles) if (f === c || f.endsWith('/' + c) || c.endsWith(f)) return true
  return false
}

// Strays are recorded where they are actually dropped (stage 2, before
// verification). Deriving the count downstream would always report zero,
// because the filtered findings never reach the final array.
const strays = []

const rounds = await pipeline(
  DIMENSIONS,
  // Stage 1 — review through one lens
  (d) => agent(
    `You are one reviewer in an adversarial code-review swarm. Review the ${changeLabel} through the "${d.key}" lens ONLY.\n\nFocus: ${d.prompt}\n\nRules:\n- Report ONLY defects introduced or newly exposed by THIS diff — not pre-existing issues elsewhere.\n- Before asserting anything, use Read/Grep/Glob to inspect the surrounding code and confirm the code path really behaves as you claim.\n- Each finding needs: file, line (best estimate in the new file), severity, a one-sentence summary, and a concrete failure_scenario (specific inputs/state -> wrong output or crash).\n- Prefer a few high-confidence findings over many speculative ones. If you find nothing real, return an empty list.\n- Every finding must name a file that appears in the changed-files list below. Findings about any other file are discarded unread — returning none is a fine outcome, returning the wrong file's is not.\n\n${context}`,
    { label: `review:${d.key}`, phase: 'Review', schema: FINDINGS_SCHEMA }
  ),
  // Stage 2 — adversarially verify every finding from that lens.
  // Out-of-scope findings are dropped BEFORE verification: a stray finding
  // would otherwise burn VOTES skeptics apiece confirming a defect in a file
  // nobody asked about.
  (review, d) => parallel(((review && review.findings) || []).filter((f) => {
    if (inScope(f.file)) return true
    strays.push(f.file)
    return false
  }).map((f) => () =>
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
const all = rounds.flat().filter(Boolean)
if (strays.length) {
  log(`review-code: DISCARDED ${strays.length} out-of-scope finding(s) — reviewers strayed outside the diff. Files: ${[...new Set(strays)].join(', ')}`)
}
const confirmed = all
  .filter((f) => inScope(f.file))
  .filter((f) => f.confirmed)
  .filter((f) => {
    const k = `${f.file}:${f.line}:${f.summary}`
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })
  .sort((a, b) => (RANK[a.severity] - RANK[b.severity]) || (b.votes_real - a.votes_real))

const dimsRun = DIMENSIONS.map((d) => d.key)
const raw = all.length + strays.length
log(`review-code: ${dimsRun.length} lenses, ${raw} candidate findings, ${strays.length} out-of-scope, ${confirmed.length} confirmed after ${VOTES}-vote adversarial verification`)

return { confirmed, dimensions: dimsRun, candidates: raw, votes: VOTES, discarded: strays.length, discardedFiles: [...new Set(strays)], reviewedFiles: [...changedFiles] }
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

**Check `discarded` before you report anything.** If it is non-zero, reviewers strayed outside the diff, and `discardedFiles` names where they went. Say so plainly and up front — and if `discarded` is a large share of `candidates`, do not present the run as a clean review at all. "Zero confirmed findings" and "the swarm never looked at the right file" produce the same empty list and mean opposite things; conflating them tells the user their change is safe when it is merely unexamined. In that case, say the review did not happen, and offer to review a small diff directly yourself rather than re-running a fleet.

**Read the confirmed findings against EACH OTHER before presenting them.** Every finding is verified in isolation by its own panel, so nothing in the pipeline notices when two of them cannot both be true — one asserts a config value is ignored entirely, another asserts that same value changes behavior elsewhere, and both come back confirmed 3/3. Scan for pairs whose mechanisms are mutually exclusive, or where one finding's premise is the negation of another's. When you find such a pair, do not report both as fact: say which one the code actually supports (verify the load-bearing mechanism yourself — read the library source, run the command), and say plainly that the other's mechanism is wrong. Findings that are merely facets of one underlying defect should be grouped under it rather than listed as separate discoveries, and where finding B is a straightforward consequence of finding A, say so instead of counting it as independent evidence.

Do not fix anything in this step — this skill reviews, it does not edit.

## Step 4b: Pin the Line Numbers (Incoming mode)

Findings carry `line` as the reviewer's **best estimate** in the new file. That is good enough for a report the user reads with the code open, and not good enough for a review comment, where a wrong anchor sends the author to an unrelated line and spends your credibility on the way. Pin every finding you intend to hand over.

For each file that has findings, print the changed ranges in new-file coordinates:

```bash
cd "$REVIEW_WT"
git --no-pager diff -U0 "$BASE_SHA" -- <file> | grep '^@@'
```

`@@ -a,b +c,d @@` means the new file changed at lines `c` through `c + d - 1`. **When the count is 1 git omits it** — `@@ -5 +5 @@` is a one-line change at line 5, not a malformed header, and reading it as `d = 0` puts the anchor a line early on every single-line fix.

Then, per finding:

1. `Read` the file around the estimated line and find the exact line the finding is about — the specific statement named in the summary, not the function that contains it.
2. **Inside a changed range** → a line comment. Record the exact new-file line, plus a 2–5 line span to highlight when the defect spans a block rather than a statement.
3. **Outside every changed range** → the finding is about code this diff exposes but does not touch. It becomes a file-level comment naming the file and function. Do not invent a line anchor for it, and expect the author to push back on scope — say in the comment why the diff makes it live now.
4. **Cannot be located at all** → the finding is vaguer than it looked. Drop it from the comment pack, keep it in the report, and say which ones you dropped and why.

Never emit an anchor you have not opened the file and confirmed. "Somewhere around line 120" is worse than no line number, because the author will go to line 120.

## Step 5: Produce the Review Comment Pack (Incoming mode)

The Step 4 report is written for the user. The comment pack is written for **the author of the change**, in the user's voice, to be pasted into MR threads by hand. Those are different documents for different readers, and the second is not a reformatting of the first — write it fresh.

Print the pack after the report under its own heading, one fenced block per comment so each is a clean copy-paste. Order by file, then by line, which is the order the user will walk the diff. Group into three sections:

- **Blocking** — should be fixed before merge.
- **Worth raising** — real, but the author may reasonably disagree or defer.
- **Nits** — naming, a clearer construct, a dead branch. Optional by definition. If there are more than two or three, keep the best and drop the rest; a wall of nits buries the blocking comment.

Head each entry with the anchor, outside the fence, so the user can see where it goes without opening the block:

```
**`internal/grants/apply.go:112`** · highlight 110–114 · blocking
```

Rules for the comment text itself — it will be read by somebody who did not ask for the user's opinion and cannot hear their tone:

1. **Two to four sentences.** The mechanism, then the concrete consequence. Stop there.
2. **Lead with the mechanism, not the verdict.** "A zero `cfg.Timeout` makes `deadline` fire on the first pass, so the loop exits before any retry" beats "this retry logic is broken".
3. **Ask where you are inferring intent.** If the code could be deliberate, a question gets a better answer than an assertion — "was zero meant to mean 'no timeout' here?". Never ask a question you already know the answer to; that reads as passive aggression rather than curiosity.
4. **No praise sandwich, no preamble, no sign-off.** Not "nice work overall, one small thing". The author is here for the finding.
5. **Never mention the swarm, the verification vote, the severity label, or this tool.** The comment is the user's own. Provenance in a review thread starts an argument about process instead of code.
6. **Offer a fix only when writing it is shorter than describing it** — then use a GitLab suggestion block so the author can apply it in one click. Anything larger is their call to make, not yours to design in a thread.
7. **Plain language, no shared-context assumptions.** The author may not know the subsystem the reviewer went and read.
8. **One finding per comment.** Two defects on adjacent lines are two threads, because they will get two different replies.

Close the pack with a single **summary comment** for the MR's main discussion, three sentences at most: what the change does as you understand it, whether anything blocks, and how many non-blocking notes there are. Getting the "what it does" line wrong is worth avoiding — if the swarm's picture of the change is thin, say less rather than guessing at intent.

If nothing was confirmed, the summary comment is the entire pack, and it says the review found no defects. Say that plainly rather than posting nothing: a review that ran and found nothing is information the author wants.

**Never post any of it.** The user posts these, edits them first, and decides what to drop — same rule as `fix-feedback`.

## Step 6: Offer Next Steps

After the report, offer (as plain text, not `AskUserQuestion`):
- Address the top N findings (you can implement fixes if the user picks some — fix the code and add no comments; the explanation of a fix goes in your response, not into the source). **Incoming mode:** their branch is not yours to edit — offer instead to draft the change as a suggestion block in the relevant comment.
- Re-run at a higher `scale` for an even deeper pass.
- Dive deeper into any single finding.
- **Incoming mode:** re-run after the author pushes (a fetch and a re-checkout in the same worktree), or remove the review worktree with `git worktree remove <path>` now that the review is posted.

## Important Rules

1. **Never fabricate or pad findings.** Report only what the workflow confirmed. An empty result is a valid, good outcome.
2. **Scale to the change.** Don't summon `scale: 3` for a typo fix. Follow the table in Step 2.
3. **Review only, by default.** Do not modify code, commit, push, or touch external state unless the user explicitly asks in Step 5.
4. **Findings must be diff-scoped.** Pre-existing issues outside the proposed changes are out of scope unless the diff newly exposes them.
5. **Verification is adversarial on purpose.** The skeptic panel defaults to "refuted"; that's what keeps the signal high. Don't loosen it.
6. **Report honestly.** If the diff was truncated, a lens errored, or coverage was capped, say so.
7. **Check that every finding names a file from the diff before reporting anything.** Both known failures of this skill produced complete, confident, adversarially-verified reports about files that were not in the diff. Cross-check `reviewedFiles` against the paths in `confirmed`; if they don't match, the run is void regardless of how good the findings look. Note that `discarded: 0` proves nothing on its own — it was 0 in a run where 100% of findings were out of scope, because the scope filter itself was disabled by the undefined-args bug.
8. **Match the tool to the diff.** A one-file, few-dozen-line change does not need 27 agents. If the swarm's setup cost exceeds the change, say so and offer to read it yourself instead.
9. **Incoming branches are read-only.** Never commit, amend, push, rebase, or force anything on somebody else's branch, and never check it out over the user's working tree — it gets a detached worktree or it does not get reviewed.
10. **Never post a comment.** The pack is printed in chat for the user to paste, edit, and prune. Posting to the MR is their action, not yours, and it stays that way even if a tool is available that could do it.
11. **Never remove the review worktree unless asked.** Offer it in Step 6 and leave it alone otherwise — cleanup is the user's call, and a re-review after the author pushes wants that worktree still there.
12. **Say which mode ran.** Every report and every pack opens by naming the branch and base it reviewed. A review of the wrong branch reads exactly like a review of the right one.

## Step 7: Self-Improvement

After the run, reflect on how it went:

- Was the diff gathered correctly for this repo's branch setup (merge-base, default branch detection)?
- Was the scale appropriate, or did the swarm over-/under-cover the change?
- Did the adversarial panel wrongly kill real bugs, or let noise through? Tune the votes or the refute prompt if so.
- Were the review lenses the right ones for this codebase's languages/frameworks?
- **Incoming mode:** did Step 0 pick the right mode from the bare argument, or did the user have to correct it with `--base`/`--branch`? A wrong guess means the heuristic needs tightening here, not a note in the report.
- **Incoming mode:** did any comment in the pack need its line anchor fixed by hand before posting? That is Step 4b failing, and it is the one defect in this skill the author of the change will see.

If any issue was encountered, **edit this skill file** (`~/.claude/skills/review-code/SKILL.md`) with a surgical fix so the next run is better. Briefly tell the user what you changed and why.
