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
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'integer' },
          real: { type: 'boolean' },
          reason: { type: 'string' },
        },
        required: ['claim', 'real', 'reason'],
        additionalProperties: false,
      },
    },
  },
  required: ['verdicts'],
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
//
// Do NOT filter on "looks like a filename" (an earlier version required a dot
// in the path). Extensionless files are real review surface — Makefile,
// Dockerfile, Jenkinsfile, a hack/ script — and dropping them here does not
// stop reviewers seeing them in the diff, it just discards any finding they
// raise about one, as an out-of-scope stray. The run then reports full
// coverage having quietly excluded those files. Take every path git printed
// and let scopePath do the work.
const changedFiles = new Set(
  A.files.split('\n')
    .map((l) => l.trim().split(/\s+/).pop() || '')
    .filter((p) => p && p !== '/dev/null')
)
if (!changedFiles.size) {
  throw new Error(`review-code: could not parse any file path out of args.files:\n${A.files}\nRefusing to run with an unenforceable scope filter.`)
}
// Fails CLOSED. An empty or unparseable file list must never mean "allow
// everything" — that is precisely how out-of-scope findings reached the report.
const scopePath = (f) => {
  if (!f) return null
  if (f.startsWith('/') && !f.startsWith(repoRoot)) return null
  for (const c of changedFiles) if (f === c) return c
  for (const c of changedFiles) if (f.endsWith('/' + c)) return c
  const tails = [...changedFiles].filter((c) => c.endsWith('/' + f))
  if (tails.length === 1) return tails[0]
  return tails.length ? f : null
}

// Strays are recorded where they are actually dropped (the intake fold,
// before verification). Deriving the count downstream would always report zero,
// because the filtered findings never reach the final array.
const strays = []

const RANK = { critical: 0, high: 1, medium: 2, low: 3 }
const rank = (s) => (RANK[s] === undefined ? RANK.low : RANK[s])

// Stage 1 — review through one lens
const reviews = await parallel(DIMENSIONS.map((d) => () => agent(
  `You are one reviewer in an adversarial code-review swarm. Review the ${changeLabel} through the "${d.key}" lens ONLY.\n\nFocus: ${d.prompt}\n\nRules:\n- Report ONLY defects introduced or newly exposed by THIS diff — not pre-existing issues elsewhere.\n- Before asserting anything, use Read/Grep/Glob to inspect the surrounding code and confirm the code path really behaves as you claim.\n- Each finding needs: file, line (best estimate in the new file), severity, a one-sentence summary, and a concrete failure_scenario (specific inputs/state -> wrong output or crash).\n- Prefer a few high-confidence findings over many speculative ones. If you find nothing real, return an empty list.\n- Every finding must name a file that appears in the changed-files list below. Findings about any other file are discarded unread — returning none is a fine outcome, returning the wrong file's is not.\n\n${context}`,
  { label: `review:${d.key}`, phase: 'Review', schema: FINDINGS_SCHEMA }
)))

// Out-of-scope findings are dropped BEFORE verification: a stray finding
// would otherwise burn VOTES skeptics apiece confirming a defect in a file
// nobody asked about.
const candidates = []
reviews.forEach((review, i) => {
  const lens = DIMENSIONS[i].key
  for (const f of (review && review.findings) || []) {
    const path = scopePath(f.file)
    if (!path) { strays.push(f.file); continue }
    candidates.push({ ...f, file: path, dimension: lens })
  }
})

const clusters = []
const byLocation = new Map()
for (const f of candidates) {
  const key = `${f.file}:${f.line}`
  let c = byLocation.get(key)
  if (!c) {
    c = { file: f.file, line: f.line, severity: f.severity, category: f.category, summary: f.summary, dimension: f.dimension, lenses: [], claims: [] }
    byLocation.set(key, c)
    clusters.push(c)
  }
  if (!c.lenses.includes(f.dimension)) c.lenses.push(f.dimension)
  if (!c.claims.some((x) => x.summary === f.summary && x.failure_scenario === f.failure_scenario)) {
    c.claims.push({ dimension: f.dimension, severity: f.severity, category: f.category, summary: f.summary, failure_scenario: f.failure_scenario })
  }
  if (rank(f.severity) < rank(c.severity)) {
    c.severity = f.severity
    c.category = f.category
    c.summary = f.summary
    c.dimension = f.dimension
  }
}

// Stage 2 — one adversarial panel per location, returning a verdict per claim.
const unverified = []
const verified = await parallel(clusters.map((c) => () =>
  parallel(Array.from({ length: VOTES }, (_unused, i) => () =>
    agent(
      `You are skeptic #${i + 1} on a verification panel. Your job is to REFUTE each review finding below. Assume every one of them is wrong until the code proves otherwise.\n\nInspect the actual code with Read/Grep. For EACH claim separately, set real=false unless you can trace a concrete, reachable code path that produces THAT claim's own failure with realistic inputs. Guarding code, callers that make the input impossible, or framework behavior that prevents it all count as refutation.\n\nLocation: ${c.file}:${c.line}\nRaised by ${c.lenses.length} review lens(es): ${c.lenses.join(', ')}\n\n${c.claims.map((x, n) => `Claim ${n + 1} (${x.dimension}, severity ${x.severity}): ${x.summary}\nClaimed failure: ${x.failure_scenario}`).join('\n\n')}\n\nReturn one verdict per claim, each carrying that claim's number. These claims share a line and may be entirely unrelated defects: upholding one says nothing about the others, and a claim you cannot refute is not made true by a neighbour that holds. Agreement between lenses is not evidence of a defect either — judge the code, not how many lenses raised it.\n\n${context}`,
      { label: `verify:${c.file}:${c.line}`, phase: 'Verify', schema: VERDICT_SCHEMA }
    )
  )).then((votes) => {
    const clean = votes.filter(Boolean)
    const judged = c.claims.map((x, n) => {
      const cast = clean
        .map((v) => ((v && v.verdicts) || []).find((w) => w && w.claim === n + 1))
        .filter(Boolean)
      const realCount = cast.filter((w) => w.real).length
      return {
        ...x,
        upheld: cast.length > 0 && realCount > cast.length / 2,
        votes_real: realCount,
        votes_total: cast.length,
        grounds: cast.filter((w) => w.real).map((w) => w.reason).slice(0, 3),
        refutations: cast.filter((w) => !w.real).map((w) => w.reason).slice(0, 3),
      }
    })
    const upheld = judged.filter((x) => x.upheld)
    const head = upheld.slice().sort((a, b) => rank(a.severity) - rank(b.severity))[0]
    if (!clean.length) unverified.push(`${c.file}:${c.line}`)
    return {
      ...c,
      claims: judged,
      confirmed: Boolean(clean.length && head),
      panel_votes: clean.length,
      severity: head ? head.severity : c.severity,
      category: head ? head.category : c.category,
      summary: head ? head.summary : c.summary,
      dimension: head ? head.dimension : c.dimension,
      lenses: upheld.length ? [...new Set(upheld.map((x) => x.dimension))] : c.lenses,
      votes_real: head ? head.votes_real : 0,
      votes_total: head ? head.votes_total : 0,
      refutations: judged.filter((x) => !x.upheld).flatMap((x) => x.refutations).slice(0, 3),
    }
  })
))

if (unverified.length) {
  log(`review-code: ${unverified.length} location(s) returned NO usable skeptic votes and are reported as UNVERIFIED, not refuted: ${unverified.join(', ')}`)
}

// Keep only confirmed, rank by severity. The collapse above already left one
// entry per location, so there is nothing further to dedupe.
if (strays.length) {
  log(`review-code: DISCARDED ${strays.length} out-of-scope finding(s) — reviewers strayed outside the diff. Files: ${[...new Set(strays)].join(', ')}`)
}
const confirmed = verified
  .filter(Boolean)
  .filter((f) => f.confirmed)
  .sort((a, b) => (rank(a.severity) - rank(b.severity)) || (b.votes_real - a.votes_real))

const dimsRun = DIMENSIONS.map((d) => d.key)
const raw = candidates.length + strays.length
const collapsed = candidates.length - clusters.length
log(`review-code: ${dimsRun.length} lenses, ${raw} candidate findings, ${strays.length} out-of-scope, ${collapsed} collapsed into a location another lens already raised, ${clusters.length} locations verified, ${confirmed.length} confirmed after ${VOTES}-vote adversarial verification`)

return { confirmed, dimensions: dimsRun, candidates: raw, clusters: clusters.length, collapsed, votes: VOTES, unverified, discarded: strays.length, discardedFiles: [...new Set(strays)], reviewedFiles: [...changedFiles] }
