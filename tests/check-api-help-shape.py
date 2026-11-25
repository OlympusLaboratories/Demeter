#!/usr/bin/env python3
import ast
import glob
import importlib.machinery
import importlib.util
import inspect
import os
import re
import subprocess
import sys
import tempfile
import textwrap

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SHAPES = ('json', 'ndjson', 'text', 'mixed')

PYTHON_ADAPTER = 'github-api.sh'
BASH_ADAPTER = 'gitlab-api.sh'

EXPECTED = {
    PYTHON_ADAPTER: {
        'help': 'text',
        'current-user': 'json',
        'open-prs': 'ndjson',
        'merged-prs': 'ndjson',
        'pr-info': 'json',
        'pr-reviews': 'ndjson',
        'pr-changes': 'ndjson',
        'pr-commits': 'ndjson',
        'pr-for-branch': 'ndjson',
        'reply-to-thread': 'json',
        'resolve-thread': 'json',
        'unresolve-thread': 'json',
        'create-diff-comment': 'json',
        'create-pr': 'json',
        'update-pr-description': 'json',
        'pr-checks': 'ndjson',
        'pr-merge': 'json',
        'pr-auto-merge': 'json',
        'pr-cancel-auto-merge': 'json',
        'pr-status': 'json',
        'pr-notes': 'ndjson',
        'rerun-check': 'json',
        'rerun-workflow': 'json',
        'pr-review-list': 'ndjson',
        'dismiss-review': 'json',
        'request-review': 'json',
        'job-log': 'text',
    },
    BASH_ADAPTER: {
        'help': 'text',
        'current-user': 'json',
        'merged-mrs': 'ndjson',
        'open-mrs': 'ndjson',
        'mr-info': 'json',
        'mr-discussions': 'ndjson',
        'mr-notes': 'ndjson',
        'mr-changes': 'ndjson',
        'reply-to-thread': 'json',
        'reply-to-thread-stdin': 'json',
        'resolve-thread': 'json',
        'update-mr-title': 'json',
        'update-note': 'json',
        'create-note': 'json',
        'mr-commits': 'ndjson',
        'mr-pipelines': 'ndjson',
        'pipeline-jobs': 'ndjson',
        'pipeline-bridges': 'ndjson',
        'job-log': 'text',
        'retry-job': 'json',
        'create-mr': 'json',
        'update-mr-description': 'json',
        'mr-for-branch': 'ndjson',
        'create-diff-comment': 'json',
        'project-info': 'json',
        'project-runners': 'ndjson',
        'runner-info': 'json',
        'ci-variable-keys': 'ndjson',
        'protected-refs': 'mixed',
        'group-members': 'ndjson',
        'merge-mr': 'json',
        'cancel-auto-merge': 'json',
        'rebase-mr': 'json',
        'mr-approvals': 'json',
        'merge-status': 'json',
        'project-members': 'ndjson',
    },
}

RULES = """the output-shape column every forge adapter prints in `help`

the oracle is the EXPECTED table in this file, written by hand and independent of
both adapters. three things are checked against it, and a fourth against the source:

  every subcommand the adapter implements appears in EXPECTED
      so a new subcommand nobody classified fails here rather than shipping blank
  every subcommand in EXPECTED has exactly one help row, and its last field is the shape
  every shape is one of: json, ndjson, text, mixed
  gitlab-api.sh's declared `# Shape:` comment equals EXPECTED for that arm
  the shape derived from the source equals EXPECTED
      a drift check, not the oracle -- it catches an adapter whose behaviour changed
      without its annotation or this table changing with it

`help` must also run with no credentials at all, on both adapters.

how the source-derived shape is computed, independently of either adapter:

  github-api.sh   an ast walk of each cmd_* function -- a bare `print` on the success
                  path (one with no `file=` keyword, so a stderr write does not count)
                  is text, an `emit` inside a for/while is ndjson, anything else emits
                  exactly one object and is json
  gitlab-api.sh   each `case` arm's text, sliced from its label to its `;;` terminator
                  rather than to the next label -- no JSON print at all is text, an
                  unredirected `echo` beside one is mixed, a JSON print under a python
                  `for` is ndjson, anything else is json

Why this test exists. A watcher that parses the adapter with a whole-stream
`json.load` works on a single-item subcommand and throws on a multi-item one, and
the obvious `except: sys.exit(0)` turns that into no output -- which a monitor
renders as "nothing to report". A blocking review then arrives as zero unresolved
threads. The shape column is how a run avoids guessing.

Why the oracle is a table rather than a derivation. It used to be a derivation
copied from the adapter, which made the python half compare the adapter against its
own algorithm: a wrong rule was wrong identically in both copies and the test
passed. A hand-written table cannot agree with a bug by construction, and it is
also what makes an unclassified new subcommand fail."""


def load_module(path):
    loader = importlib.machinery.SourceFileLoader('adapter_under_test', path)
    spec = importlib.util.spec_from_loader('adapter_under_test', loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def calls_to_stdout(node, name):
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        if not isinstance(inner.func, ast.Name) or inner.func.id != name:
            continue
        if any(kw.arg == 'file' for kw in inner.keywords):
            continue
        return True
    return False


def derive_python(source):
    tree = ast.parse(textwrap.dedent(source))
    if calls_to_stdout(tree, 'print'):
        return 'text'
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)) and calls_to_stdout(node, 'emit'):
            return 'ndjson'
    return 'json'


JSON_PRINT = re.compile(r'print\s*\(\s*json\.dumps|json\.dump\s*\(|print\s*\([^)]*json\.')
BARE_ECHO = re.compile(r'^\s*(\|\|\s*)?echo\b')
PY_FOR = re.compile(r'^(\s*)for\b.*:\s*(\S.*)?$')


def derive_bash(body):
    json_lines = [i for i, l in enumerate(body) if JSON_PRINT.search(l)]
    if not json_lines:
        return 'text'
    if any(BARE_ECHO.match(l) and '>&2' not in l for l in body):
        return 'mixed'
    for index, line in enumerate(body):
        loop = PY_FOR.match(line)
        if not loop:
            continue
        if loop.group(2) and JSON_PRINT.search(loop.group(2)):
            return 'ndjson'
        indent = len(loop.group(1))
        for follower in body[index + 1:]:
            if not follower.strip():
                continue
            if len(follower) - len(follower.lstrip()) <= indent:
                break
            if JSON_PRINT.search(follower):
                return 'ndjson'
    return 'json'


LABEL = re.compile(r'^  ([a-z][a-z0-9-]*)\)$')
TERMINATOR = re.compile(r'^\s*;;\s*$')
SHAPE_COMMENT = re.compile(r'^    # Shape: (\S+)$')


def bash_arms(path):
    with open(path) as handle:
        lines = handle.read().split('\n')
    arms = {}
    index = 0
    while index < len(lines):
        match = LABEL.match(lines[index])
        if not match:
            index += 1
            continue
        name = match.group(1)
        start = index + 1
        end = start
        while end < len(lines) and not TERMINATOR.match(lines[end]):
            if LABEL.match(lines[end]):
                break
            end += 1
        arms[name] = lines[start:end]
        index = end
    return arms


def declared_bash(arms):
    declared = {}
    for name, body in arms.items():
        for line in body:
            found = SHAPE_COMMENT.match(line)
            if found:
                declared[name] = found.group(1)
                break
    return declared


def run_help(path):
    environment = dict(os.environ)
    environment['GITHUB_PERSONAL_ACCESS_TOKEN'] = ''
    environment['GITLAB_PERSONAL_ACCESS_TOKEN'] = ''
    with tempfile.TemporaryDirectory() as empty:
        environment['HOME'] = empty
        runner = ['python3'] if path.endswith(PYTHON_ADAPTER) else ['bash']
        return subprocess.run(runner + [path, 'help'], env=environment,
                              capture_output=True, text=True)


ROW = re.compile(r'^([a-z][a-z0-9-]*)\s+(.*\S)\s*$')


def parse_help(text):
    rows = {}
    for line in text.split('\n'):
        if line.lower().startswith('output shape'):
            break
        match = ROW.match(line)
        if match:
            rows.setdefault(match.group(1), match.group(2).split()[-1])
    return rows


def check(path):
    adapter = os.path.basename(path)
    expected = EXPECTED[adapter]
    failures = []

    done = run_help(path)
    if done.returncode != 0:
        return [f'      help exited {done.returncode} with no credentials: '
                f'{done.stderr.strip()[:140]}']

    printed = parse_help(done.stdout)

    if adapter == PYTHON_ADAPTER:
        module = load_module(path)
        implemented = set(module.COMMANDS)
        derived = {name: derive_python(inspect.getsource(fn))
                   for name, fn in module.COMMANDS.items()}
        declared = None
    else:
        arms = bash_arms(path)
        implemented = set(arms)
        derived = {name: derive_bash(body) for name, body in arms.items()}
        declared = declared_bash(arms)

    for name in sorted(implemented - set(expected)):
        failures.append(f'      {name}: implemented but absent from this test\'s '
                        f'EXPECTED table — classify it')
    for name in sorted(set(expected) - implemented):
        failures.append(f'      {name}: in EXPECTED but the adapter does not implement it')

    for name in sorted(set(expected) & implemented):
        want = expected[name]
        if want not in SHAPES:
            failures.append(f'      {name}: EXPECTED holds "{want}", not one of '
                            f'{", ".join(SHAPES)}')
        if name not in printed:
            failures.append(f'      {name}: no row in help')
        elif printed[name] != want:
            failures.append(f'      {name}: help prints {printed[name]}, '
                            f'EXPECTED is {want}')
        if derived.get(name) != want:
            failures.append(f'      {name}: the source derives {derived.get(name)}, '
                            f'EXPECTED is {want}')
        if declared is not None:
            if name not in declared:
                failures.append(f'      {name}: no "# Shape:" comment beside the case arm')
            elif declared[name] != want:
                failures.append(f'      {name}: "# Shape: {declared[name]}" beside the '
                                f'arm, EXPECTED is {want}')

    for name in sorted(set(printed) - set(expected)):
        failures.append(f'      {name}: a help row for a subcommand this test does not know')

    return failures


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'rules':
        print(RULES)
        return 0

    scripts = sorted(
        path for pattern in (PYTHON_ADAPTER, BASH_ADAPTER)
        for path in glob.glob(f'{REPO}/profiles/*/.claude/scripts/{pattern}')
        if not os.path.islink(os.path.dirname(path))
    )
    if not scripts:
        print('no forge adapters found')
        return 1

    print('forge adapter help output shape')
    print()
    broken = 0
    for path in scripts:
        relative = os.path.relpath(path, REPO)
        failures = check(path)
        if failures:
            broken += 1
            print(f'  fail — {relative}')
            for line in failures:
                print(line)
        else:
            count = len(EXPECTED[os.path.basename(path)])
            print(f'  ok   — {relative} ({count} subcommands)')
    print()
    if broken:
        print('failed')
        return 1
    print('passed (%d adapter copies)' % len(scripts))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
