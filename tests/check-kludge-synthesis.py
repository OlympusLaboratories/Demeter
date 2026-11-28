#!/usr/bin/env python3
"""Drive review-kludge's Stage 2 consolidation under node and assert its outcomes."""

import json
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join('.claude', 'skills', 'review-kludge', 'SKILL.md')
FENCE = re.compile(r'^(`{3,})js$', re.M)

RULES = """check-kludge-synthesis.py - review-kludge's Stage 2, driven rather than parsed.

what it checks, and what each one is written against:

  the fenced script is EXECUTED under node with agent/parallel/log/args stubbed,
  not merely syntax-checked. check-workflow-scripts.py proves the script parses,
  and a parse check cannot tell the fixed code from the broken code it replaced:
  measured, every behavioural mutation of this logic still parses clean -
  synthesisFailed from !materialized.length to !entries.length, dropping
  .concat(orphans), inverting covered.has(raw_id), or making materialize()
  return null unconditionally. each one reinstates the exact failure the stage
  was rewritten to fix - a thin, un-merged proposal list reported as a clean
  codebase - and each one would have shipped green. check-transform.py cannot
  see it either: it pins the three copies byte-identical, and the convention is
  to change all three, so an identical mutation is not drift

  a healthy synthesis merges, passes through, accepts a new cross-cutting entry
  and BACKFILLS the raw ids it never referenced. the backfill is the half that
  carries the data: dropping a proposal is unrecoverable, while including a
  duplicate costs one vote on a panel that already filters

  a MERGE inherits its unstated fields from its first reference and unions
  locations across every reference. that is what makes a passthrough cost ~20
  output tokens instead of ~400, which is the whole point of the rewrite

  a FAILED synthesis is visible. synthesisFailed goes true, the raw list is used
  un-merged, every proposal still reaches the ballot, and the log says so. this
  is the regression that matters most: the pre-rewrite code fell back to the raw
  list silently and the run read as a verdict on the codebase

  patterns are NOT discarded when the consolidation fails. the stage emits
  patterns first, so a truncated answer carries real patterns beside an empty
  consolidated list - synthesisFailed is true and patterns is non-empty at the
  same time, which is a state SKILL.md's Step 4 prose has to handle and used to
  contradict

  orphans reports 0 on a failed synthesis rather than the whole raw list. the
  naive count is true and useless there: it sits beside synthesisFailed and
  reads as a successful synthesis that omitted everything

  EVERY emitted proposal has a defined area, category, ideal_pattern, impact,
  risk, effort and a non-empty locations list. the consolidated schema requires
  only ref_ids, so each of those is reachable as undefined - and undefined
  renders into the skeptics' ballot and the final report as the literal word

  an entry whose ref_ids resolve to nothing is dropped rather than emitted
  blank, and an entry missing title/problem/refactor is counted in
  unmaterialized rather than vanishing. a referenceless one is the shape no
  backfill can recover, so the counter is the only trace it leaves

  both early returns carry every field the full return carries. Step 4 reads
  these fields, and a clean run is the one path where nothing is wrong - so it
  is the worst place to hand the reporting step an undefined

  the three profile copies are driven independently and must agree. skipped when
  node is absent, which is reported rather than passed over in silence."""

DRIVER = r"""
const SCRIPT = process.argv[2]
const fs = require('node:fs')

const md = fs.readFileSync(SCRIPT, 'utf8')
const open = md.match(/^(`{3,})js$/m)
if (!open) { console.log(JSON.stringify({error: 'no js fence'})); process.exit(0) }
const ticks = open[1]
const from = md.indexOf('\n', open.index) + 1
const to = md.indexOf('\n' + ticks + '\n', from)
if (to < 0) { console.log(JSON.stringify({error: 'unclosed fence'})); process.exit(0) }
const js = md.slice(from, to)

function raw(area, n, locs) {
  return {
    title: area + ' proposal ' + n,
    area,
    category: 'duplication',
    locations: locs,
    problem: 'problem ' + area + n,
    ideal_pattern: 'pattern ' + area + n,
    refactor: 'refactor ' + area + n,
    impact: 'high',
    risk: 'low',
    effort: 'small',
  }
}

const AREAS = {
  alpha: [raw('alpha', 1, ['a.ts:1']), raw('alpha', 2, ['a.ts:9'])],
  beta: [raw('beta', 1, ['b.ts:1']), raw('beta', 2, ['b.ts:9']), raw('beta', 3, ['b.ts:17'])],
}

async function run(synthesis, areaResults) {
  const logs = []
  const results = areaResults || AREAS
  const args = {
    scopeDescription: 'driver',
    scale: 1,
    areas: Object.keys(results).map((name) => ({ name, paths: name + '.ts', summary: 's' })),
  }
  let ballot = null
  const agent = async (prompt, opts) => {
    if (opts.phase === 'Analyze') return { proposals: results[opts.label.split(':')[1]] }
    if (opts.phase === 'Patterns') return synthesis
    ballot = [...prompt.matchAll(/^(P\d\d) — /gm)].map((m) => m[1])
    return { votes: ballot.map((id) => ({ id, keep: true, reason: 'ok' })) }
  }
  const body = new Function(
    'agent', 'parallel', 'log', 'args',
    'return (async () => {\n' + js.replace('export const meta =', 'const meta =') + '\n})()'
  )
  const out = await body(
    agent,
    (thunks) => Promise.all(thunks.map((f) => f())),
    (m) => logs.push(m),
    args
  )
  return { out, logs, ballot }
}

const P = (over) => Object.assign({
  title: 't', problem: 'p', refactor: 'r', category: 'layering',
  locations: ['z.ts:1'], ideal_pattern: 'ip', impact: 'high', risk: 'low', effort: 'small',
}, over)

;(async () => {
  const cases = {}

  cases.healthy = await run({
    patterns: [{ name: 'p1', description: 'd', where_diverges: 'w' }],
    consolidated: [
      { ref_ids: ['R001', 'R003'], title: 'merged', problem: 'mp', refactor: 'mr' },
      { ref_ids: ['R002'] },
      P({ ref_ids: [], title: 'brand new', area: 'cross-cutting' }),
    ],
  })

  cases.nothing = await run(undefined)
  cases.empty_consolidated = await run({
    patterns: [
      { name: 'p1', description: 'd', where_diverges: 'w' },
      { name: 'p2', description: 'd', where_diverges: 'w' },
    ],
    consolidated: [],
  })
  cases.bad_ref = await run({ patterns: [], consolidated: [{ ref_ids: ['R999'] }] })
  cases.no_area = await run({
    patterns: [],
    consolidated: [P({ ref_ids: [] }), { ref_ids: ['R001'] }],
  })
  cases.no_locations = await run({
    patterns: [],
    consolidated: [
      Object.assign(P({ ref_ids: [] }), { locations: undefined }),
      { ref_ids: ['R001'] },
    ],
  })
  cases.half_formed = await run({
    patterns: [],
    consolidated: [
      { ref_ids: [], title: 'no refactor', problem: 'p' },
      { ref_ids: ['R001'] },
    ],
  })
  cases.no_proposals = await run(undefined, { alpha: [], beta: [] })

  console.log(JSON.stringify(cases))
})().catch((e) => {
  console.log(JSON.stringify({ error: String((e && e.stack) || e) }))
})
"""

OPTIONAL = ['area', 'category', 'ideal_pattern', 'impact', 'risk', 'effort']


def profiles():
    root = os.path.join(REPO, 'profiles')
    found = []
    for name in sorted(os.listdir(root)):
        where = os.path.join(root, name)
        if os.path.islink(where) or not os.path.isdir(where):
            continue
        if os.path.islink(os.path.join(where, '.claude', 'skills')):
            continue
        if os.path.isfile(os.path.join(where, SKILL)):
            found.append(name)
    return found


def node_available():
    try:
        subprocess.run(['node', '--version'], capture_output=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def drive(skill_path):
    with tempfile.NamedTemporaryFile('w', suffix='.cjs', delete=False) as handle:
        handle.write(DRIVER)
        driver = handle.name
    try:
        done = subprocess.run(['node', driver, skill_path], capture_output=True, text=True)
    finally:
        os.unlink(driver)
    if done.returncode != 0:
        return None, done.stderr.strip() or 'node exited non-zero with no stderr'
    try:
        return json.loads(done.stdout), None
    except ValueError:
        return None, f'driver printed unparseable output: {done.stdout[:400]!r}'


def fail(problems, message):
    problems.append(message)


def assert_case(problems, label, cases):
    if 'error' in cases:
        fail(problems, f'{label}: the driver threw: {cases["error"]}')
        return

    healthy = cases['healthy']
    out, logs = healthy['out'], '\n'.join(healthy['logs'])
    if out['synthesisFailed'] is not False:
        fail(problems, f'{label}: a healthy synthesis reported synthesisFailed')
    if len(out['patterns']) != 1:
        fail(problems, f'{label}: a healthy synthesis lost its patterns')
    if out['consolidatedCount'] != 5:
        fail(problems, f'{label}: 3 materialized + 2 backfilled should be 5 consolidated, '
                       f'got {out["consolidatedCount"]} - the orphan backfill is the half '
                       f'that stops a proposal being dropped unrecoverably')
    if out['orphans'] != 2:
        fail(problems, f'{label}: expected 2 backfilled orphans, got {out["orphans"]}')
    if out['raw'] != 5:
        fail(problems, f'{label}: expected raw 5, got {out["raw"]}')
    if len(healthy['ballot']) != 5:
        fail(problems, f'{label}: only {len(healthy["ballot"])} of 5 proposals reached '
                       f'the skeptics\' ballot')
    merged = [p for p in out['proposals'] if p['title'] == 'merged']
    if not merged:
        fail(problems, f'{label}: the merged entry never materialized')
    else:
        m = merged[0]
        if m['locations'] != ['a.ts:1', 'b.ts:1']:
            fail(problems, f'{label}: a merge must union its references\' locations, '
                           f'got {m["locations"]}')
        if m['ideal_pattern'] != 'pattern alpha1':
            fail(problems, f'{label}: a merge must inherit unstated fields from its first '
                           f'reference, got ideal_pattern {m["ideal_pattern"]!r}')
        if m['area'] != 'alpha + beta':
            fail(problems, f'{label}: a cross-area merge should label both areas, '
                           f'got {m["area"]!r}')
    if not [p for p in out['proposals'] if p['refactor'] == 'refactor alpha2']:
        fail(problems, f'{label}: a passthrough must carry its body through verbatim')
    if 'SYNTHESIS FAILED' in logs:
        fail(problems, f'{label}: a healthy synthesis logged SYNTHESIS FAILED')
    if '2 raw proposal(s) the synthesizer omitted' not in logs:
        fail(problems, f'{label}: the log never named the backfilled count')
    if 'synthesizing 5 observations' not in logs:
        fail(problems, f'{label}: no log event precedes the Patterns call, so a long '
                       f'synthesis is indistinguishable from a hang')

    nothing = cases['nothing']
    out, logs = nothing['out'], '\n'.join(nothing['logs'])
    if out['synthesisFailed'] is not True:
        fail(problems, f'{label}: a synthesis returning nothing must set synthesisFailed')
    if out['patterns']:
        fail(problems, f'{label}: patterns should be empty when nothing came back')
    if out['consolidatedCount'] != 5:
        fail(problems, f'{label}: a failed synthesis must fall back to the whole raw list, '
                       f'got {out["consolidatedCount"]} of 5')
    if len(out['proposals']) != 5:
        fail(problems, f'{label}: a failed synthesis dropped proposals instead of passing '
                       f'the raw list to the panel')
    if out['orphans'] != 0:
        fail(problems, f'{label}: orphans must read 0 on a failed synthesis, not the whole '
                       f'raw list, got {out["orphans"]}')
    if 'SYNTHESIS FAILED' not in logs:
        fail(problems, f'{label}: a failed synthesis was not logged, which is the silent '
                       f'degradation this stage was rewritten to stop')
    if 'omitted were carried through' in logs:
        fail(problems, f'{label}: the failed-synthesis log double-reports orphans')

    partial = cases['empty_consolidated']
    out, logs = partial['out'], '\n'.join(partial['logs'])
    if out['synthesisFailed'] is not True:
        fail(problems, f'{label}: an empty consolidated list must set synthesisFailed')
    if len(out['patterns']) != 2:
        fail(problems, f'{label}: patterns that did arrive must survive a failed '
                       f'consolidation, got {len(out["patterns"])} of 2')
    if '2 pattern(s) came back' not in logs:
        fail(problems, f'{label}: the log must report the pattern count rather than '
                       f'asserting there are none')

    out = cases['bad_ref']['out']
    if out['consolidatedCount'] != 5:
        fail(problems, f'{label}: an entry whose ref_ids resolve to nothing must be dropped '
                       f'and the raw list used, got {out["consolidatedCount"]}')
    if out['synthesisFailed'] is not True:
        fail(problems, f'{label}: nothing materialized, so synthesisFailed must be true')

    for key in ('no_area', 'no_locations', 'half_formed', 'healthy', 'nothing'):
        for p in cases[key]['out']['proposals']:
            for field in OPTIONAL:
                if p.get(field) in (None, ''):
                    fail(problems, f'{label}: case {key} emitted a proposal with no '
                                   f'{field} ({p.get("title")!r}); the consolidated schema '
                                   f'requires only ref_ids, so undefined renders into the '
                                   f'ballot and the report as the literal word')
            if not p.get('locations'):
                fail(problems, f'{label}: case {key} emitted a proposal with an empty '
                               f'locations list ({p.get("title")!r}), so the skeptics are '
                               f'asked to verify it against no code at all')

    half = cases['half_formed']['out']
    if half['unmaterialized'] != 1:
        fail(problems, f'{label}: an entry missing a refactor must be counted in '
                       f'unmaterialized, got {half["unmaterialized"]} - a referenceless '
                       f'one leaves no other trace')

    clean = cases['no_proposals']['out']
    full = set(cases['healthy']['out'].keys())
    missing = sorted(full - set(clean.keys()))
    if missing:
        fail(problems, f'{label}: the no-proposals early return omits {missing}, so Step 4 '
                       f'reads undefined on the one path where nothing is wrong')


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'rules':
        print(RULES)
        return 0

    found = profiles()
    if not found:
        print('0 problem(s): no profile carries review-kludge/SKILL.md - '
              'discovery is broken, since every assertion would pass vacuously')
        return 1

    if not node_available():
        print(f'note: node is absent, so the {len(found)} profile(s) were not driven')
        return 0

    problems = []
    for profile in found:
        skill_path = os.path.join(REPO, 'profiles', profile, SKILL)
        cases, error = drive(skill_path)
        if error:
            fail(problems, f'{profile}: {error}')
            continue
        assert_case(problems, profile, cases)

    if problems:
        print(f'{len(problems)} problem(s):')
        for problem in problems:
            print(f'  {problem}')
        return 1

    print(f'ok: review-kludge Stage 2 driven under node across {len(found)} profile(s)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
