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

FENCE = re.compile(r'^````js$', re.M)
IDENT = re.compile(r'`([A-Z][A-Z0-9_]{2,})`')


def STEP_NEAR(name):
    token = re.escape(name)
    return re.compile(
        r'(?:Step\s+\d+[a-z]?(?:’s|\'s)?[^.\n]{0,40}?`' + token + r'`'
        r'|`' + token + r'`[^.\n]{0,40}?\bin\s+Step\s+\d+[a-z]?)')


def strip_backticked(text, name):
    return text.replace('`' + name + '`', '')

RULES = """check-workflow-scripts.py — the prose/script seam for the Workflow skills.

what it checks, and what each one is written against:

  every skill in the list has a workflow.js beside its SKILL.md, and that file
  opens with `export const meta` — the Workflow tool refuses a script without
  the meta literal, and a missing file is an invocation that fails at launch
  with the swarm already announced

  no SKILL.md carries a ````js fence any more. the script moved out so that it
  stops being re-sent on every launch; a fence drifting back would restore the
  cost silently while the scriptPath instruction beside it still read correctly

  SKILL.md names the absolute invocation path, $HOME/.claude/skills/<skill>/
  workflow.js. the tool does not expand ~, and a skill that stopped naming the
  path would leave the reader to guess it

  SKILL.md does not tell anyone to pass a snapshot. the whole point of the
  rewrite is that a live path cannot be stale and a snapshot under
  <session>/workflows/scripts/ can, so prose recommending the second is the
  one failure the design removes

  no ALL_CAPS identifier that lives only in workflow.js is described as being
  in a step of SKILL.md. this is the regression that happened during the
  extraction: changes-description told its --inline path three times to read
  the HOUSE block "in Step 2", and Step 2 no longer contained it. the
  identifier had moved and the prose had not, so the cheapest path through the
  skill pointed at nothing. the weaker version of this check - "SKILL.md must
  mention workflow.js somewhere" - is dead, because the invocation path the
  rule above requires already contains that string, so it could never fail on
  its own

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
                fail(problems, f'{label}: SKILL.md carries {fences} ````js fence(s); '
                               f'the script belongs in workflow.js')

            path_literal = f'$HOME/.claude/skills/{skill}/workflow.js'
            if path_literal not in md:
                fail(problems, f'{label}: SKILL.md never names {path_literal}')

            if re.search(r'pass(?:ing)?\s+(?:a\s+)?snapshot', md, re.I):
                fail(problems, f'{label}: SKILL.md appears to recommend a snapshot path')

            for name in sorted(set(IDENT.findall(md))):
                if not re.search(r'\b' + re.escape(name) + r'\b', js):
                    continue
                if re.search(r'\b' + re.escape(name) + r'\b', strip_backticked(md, name)):
                    continue
                for stray in STEP_NEAR(name).finditer(md):
                    fail(problems, f'{label}: prose places `{name}` in a step of SKILL.md '
                                   f'({stray.group(0).strip()!r}), but it lives in workflow.js')

            if have_node:
                ok, stderr = check_syntax(js_path, js)
                if not ok:
                    fail(problems, f'{label}: workflow.js does not parse:\n{stderr}')

    if not have_node:
        print('note: node is absent, so the syntax check was skipped')

    if problems:
        print(f'{len(problems)} problem(s):')
        for problem in problems:
            print(f'  {problem}')
        return 1

    print(f'ok: {checked} workflow skill(s) across {len(PROFILES)} profiles')
    return 0


if __name__ == '__main__':
    sys.exit(main())
