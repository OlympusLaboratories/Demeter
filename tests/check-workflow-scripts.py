#!/usr/bin/env python3
"""Pin the contract between a Workflow skill's prose and its extracted script."""

import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = [
    'larrabeedylan_home_darwin',
    'larrabeedylan_work_darwin',
    'larrabeedylan_work_linux',
]
SKILLS = ['review-code', 'changes-description']
INLINE_ONLY = ['review-kludge', 'docs-humanize']

FENCE = re.compile(r'^`{3,}js$', re.M)
IDENT = re.compile(r'`([A-Z][A-Z0-9_]{2,})`')
INLINE_REVIVED = re.compile(r'pass(?:ing)?\s+the\s+script\s+inline|script\s+inline\s+via', re.I)


def STEP_NEAR(name):
    token = re.escape(name)
    step = r'Step\s+\d+[a-z]?'
    return re.compile(
        r'(?:' + step + r'[^.\n]{0,80}?`' + token + r'`'
        r'|`' + token + r'`[^.\n]{0,80}?' + step + r')')

RULES = """check-workflow-scripts.py — the prose/script seam for the Workflow skills.

what it checks, and what each one is written against:

  every skill in the list has a workflow.js beside its SKILL.md, and that file
  opens with `export const meta` — the Workflow tool refuses a script without
  the meta literal, and a missing file is an invocation that fails at launch
  with the swarm already announced

  no SKILL.md carries a js fence any more, at any backtick count. the script
  moved out so that it stops being re-sent on every launch; a fence drifting
  back would restore the cost silently while the scriptPath instruction beside
  it still read correctly. the pattern is `{3,} rather than exactly four: four
  is used in these files only because the scripts contain three-backtick blocks
  of their own, so nothing makes it the form a later paste would take

  SKILL.md names the absolute invocation path, $HOME/.claude/skills/<skill>/
  workflow.js. the tool does not expand ~, and a skill that stopped naming the
  path would leave the reader to guess it

  SKILL.md does not tell the reader to pass the script inline. that is the
  drift worth catching - a revert to the old instruction - and it is a literal
  phrase rather than a judgement. what this replaced was a check for prose
  "recommending a snapshot", which was polarity-inverted: measured, it fired on
  "Never pass a snapshot scriptPath" (a prohibition, so a false failure) and
  stayed silent on "Use the snapshot scriptPath for a cheap re-run" (the thing
  it was for). a regex over prose cannot tell a prohibition from a
  recommendation, so that check is gone rather than widened

  the inline-only skills' fenced script parses under node as well, wrapped the
  same way. the node check used to cover only the two extracted workflow.js
  files, so a syntax error in an inline script shipped silently and failed at
  launch with the swarm already announced - which is the same failure the
  missing-file check exists against, reached by the other route. the fence is
  read by matching its own backtick count, and an unclosed fence is a failure
  rather than an empty string that parses

  the skills that have NOT been migrated keep their inline fence and have no
  workflow.js, and that is asserted too. a half-migration is the defect:
  workflow-resume names all four Workflow skills and sends every resume at
  $HOME/.claude/skills/<skill>/workflow.js, so a skill moved out of INLINE_ONLY
  without gaining the file leaves that instruction naming a path that does not
  exist. checking only the migrated two could not see it

  no ALL_CAPS identifier that lives only in workflow.js is described as being
  in a step of SKILL.md. this is the regression that happened during the
  extraction: changes-description told its --inline path three times to read
  the HOUSE block "in Step 2", and Step 2 no longer contained it. the
  identifier had moved and the prose had not, so the cheapest path through the
  skill pointed at nothing. the window is wide and takes either order, because
  the first draft matched only two phrasings and missed "see Step 2 for the
  HOUSE block". an earlier escape - skip the identifier if it also appears
  unbackticked anywhere in the file - is gone: it disabled this whole rule on
  one stray mention, and an unbackticked mention was never evidence of
  anything

  workflow.js parses under node, wrapped the way the runtime wraps it — the
  body is an async function, so a bare module rejects its top-level return and
  a naive syntax check reports a failure that is not one. skipped when node is
  absent rather than reported as a pass

  the three profile copies are NOT compared here: profiles/check-transform.py
  already compares every tracked file under a profile, so the scripts are
  drift-checked by it and a second copy of that logic would go stale
"""


def fail(problems, message):
    problems.append(message)


def node_available():
    try:
        subprocess.run(['node', '--version'], capture_output=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def inline_script(md):
    opening = FENCE.search(md)
    if not opening:
        return None
    ticks = opening.group(0)[:-2]
    start = opening.end() + 1
    closing = re.compile(r'^' + re.escape(ticks) + r'$', re.M).search(md, start)
    if not closing:
        return None
    return md[start:closing.start()]


def check_syntax(path, text):
    wrapped = (
        'const agent=()=>{};const parallel=()=>{};const pipeline=()=>{};\n'
        'const phase=()=>{};const log=()=>{};const workflow=()=>{};\n'
        'const args={};const budget={total:null,spent:()=>0,remaining:()=>0};\n'
        'async function __body__() {\n'
        + text.replace('export const meta =', 'const meta =', 1)
        + '\n}\nvoid meta; void __body__;\n'
    )
    import tempfile
    with tempfile.NamedTemporaryFile('w', suffix='.mjs', delete=False) as handle:
        handle.write(wrapped)
        tmp = handle.name
    try:
        result = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
        return result.returncode == 0, result.stderr.strip()
    finally:
        os.unlink(tmp)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'rules':
        print(RULES)
        return 0

    problems = []
    have_node = node_available()
    checked = 0

    for profile in PROFILES:
        for skill in SKILLS:
            where = os.path.join(REPO, 'profiles', profile, '.claude', 'skills', skill)
            md_path = os.path.join(where, 'SKILL.md')
            js_path = os.path.join(where, 'workflow.js')
            label = f'{profile}/{skill}'

            if not os.path.isfile(md_path):
                fail(problems, f'{label}: no SKILL.md')
                continue
            if not os.path.isfile(js_path):
                fail(problems, f'{label}: no workflow.js beside SKILL.md')
                continue

            checked += 1
            with open(md_path, encoding='utf-8') as handle:
                md = handle.read()
            with open(js_path, encoding='utf-8') as handle:
                js = handle.read()

            if not js.startswith('export const meta = {'):
                fail(problems, f'{label}: workflow.js does not open with the meta literal')

            fences = len(FENCE.findall(md))
            if fences:
                fail(problems, f'{label}: SKILL.md carries {fences} js fence(s); '
                               f'the script belongs in workflow.js')

            path_literal = f'$HOME/.claude/skills/{skill}/workflow.js'
            if path_literal not in md:
                fail(problems, f'{label}: SKILL.md never names {path_literal}')

            revived = INLINE_REVIVED.search(md)
            if revived:
                fail(problems, f'{label}: SKILL.md tells the reader to pass the script inline '
                               f'({revived.group(0)!r}); the script is passed by path now')

            for name in sorted(set(IDENT.findall(md))):
                if not re.search(r'\b' + re.escape(name) + r'\b', js):
                    continue
                for stray in STEP_NEAR(name).finditer(md):
                    fail(problems, f'{label}: prose places `{name}` in a step of SKILL.md '
                                   f'({stray.group(0).strip()!r}), but it lives in workflow.js')

            if have_node:
                ok, stderr = check_syntax(js_path, js)
                if not ok:
                    fail(problems, f'{label}: workflow.js does not parse:\n{stderr}')

        for skill in INLINE_ONLY:
            where = os.path.join(REPO, 'profiles', profile, '.claude', 'skills', skill)
            md_path = os.path.join(where, 'SKILL.md')
            label = f'{profile}/{skill}'
            if not os.path.isfile(md_path):
                fail(problems, f'{label}: no SKILL.md, but it is listed as inline-only')
                continue
            if os.path.isfile(os.path.join(where, 'workflow.js')):
                fail(problems, f'{label}: has a workflow.js but is still listed in '
                               f'INLINE_ONLY; move it to SKILLS so its seam is checked')
            with open(md_path, encoding='utf-8') as handle:
                md = handle.read()
            if not FENCE.search(md):
                fail(problems, f'{label}: no js fence in SKILL.md and no workflow.js '
                               f'either, so workflow-resume names a path that does '
                               f'not exist for it')
                continue
            js = inline_script(md)
            if js is None:
                fail(problems, f'{label}: the js fence in SKILL.md is never closed, so no '
                               f'script can be read out of it')
                continue
            if have_node:
                ok, stderr = check_syntax(md_path, js)
                if not ok:
                    fail(problems, f'{label}: the inline script in SKILL.md does not '
                                   f'parse:\n{stderr}')

    if not have_node:
        print('note: node is absent, so the syntax check was skipped')

    if problems:
        print(f'{len(problems)} problem(s):')
        for problem in problems:
            print(f'  {problem}')
        return 1

    print(f"ok: {checked} migrated + {len(INLINE_ONLY) * len(PROFILES)} inline-only skill(s) across {len(PROFILES)} profiles")
    return 0


if __name__ == '__main__':
    sys.exit(main())
