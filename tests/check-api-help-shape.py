#!/usr/bin/env python3
import ast
import glob
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
    PYTHON_ADAPTER: {'pr-checks': 'ndjson', 'pr-reviews': 'ndjson',
                     'pr-status': 'json', 'pr-info': 'json', 'job-log': 'text'},
    BASH_ADAPTER: {'mr-discussions': 'ndjson', 'mr-notes': 'ndjson',
                   'merge-status': 'json', 'mr-info': 'json', 'job-log': 'text',
                   'protected-refs': 'mixed'},
}

RULES = """the output-shape column every forge adapter prints in `help`

  one row per subcommand, and the shape is the row's last field
  every shape is one of: json, ndjson, text, mixed
  the shape `help` prints equals the shape this test derives from the source
  every subcommand the script implements has a row
  `help` runs with no credentials at all

how each shape is derived here, independently of the script:

  github-api.sh   an ast walk of each cmd_* function — a bare `print` on the
                  success path is text, an `emit` inside a for/while is ndjson,
                  anything else emits exactly one object and is json
  gitlab-api.sh   each `case` arm's text — no `print(json.dumps` is text, a bare
                  `echo` beside one is mixed, a `print(json.dumps` under a python
                  `for` is ndjson, anything else is json

Why this test exists. A watcher that parses the adapter with a whole-stream
`json.load` works on a single-item subcommand and throws on a multi-item one,
and the obvious `except: sys.exit(0)` turns that into no output — which a
monitor renders as "nothing to report". A blocking review then arrives as zero
unresolved threads. The shape column is how a run avoids guessing, and the
GitLab adapter declares it in a comment, so without this test it is a
hand-maintained list that can drift from the code beside it."""


def load_module(path):
    spec = importlib.util.spec_from_loader(
        'adapter_under_test',
        importlib.machinery.SourceFileLoader('adapter_under_test', path),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def calls_named(node, name):
    return any(isinstance(inner, ast.Call)
               and isinstance(inner.func, ast.Name)
               and inner.func.id == name
               for inner in ast.walk(node))


def derive_python(source):
    tree = ast.parse(textwrap.dedent(source))
    if calls_named(tree, 'print'):
        return 'text'
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)) and calls_named(node, 'emit'):
            return 'ndjson'
    return 'json'


def derive_bash(body):
    if not any('print(json.dumps' in line for line in body):
        return 'text'
    if any(re.match(r'\s*echo ', line) for line in body):
        return 'mixed'
    for index, line in enumerate(body):
        loop = re.match(r'(\s*)for .*:\s*$', line)
        if not loop:
            continue
        indent = len(loop.group(1))
        for follower in body[index + 1:]:
            if not follower.strip():
                continue
            if len(follower) - len(follower.lstrip()) <= indent:
                break
            if 'print(json.dumps' in follower:
                return 'ndjson'
    return 'json'


def truth_python(path):
    module = load_module(path)
    return {name: derive_python(inspect.getsource(fn))
            for name, fn in module.COMMANDS.items()}


def truth_bash(path):
    with open(path) as handle:
        lines = handle.read().split('\n')
    label = re.compile(r'^  ([a-z][a-z0-9-]*)\)$')
    shapes = {}
    name = None
    start = None
    for index, line in enumerate(lines):
        match = label.match(line)
        if match or re.match(r'^  \*\)$', line):
            if name is not None:
                shapes[name] = derive_bash(lines[start:index])
            if not match:
                break
            name = match.group(1)
            start = index + 1
    return shapes


def declared_bash(path):
    with open(path) as handle:
        lines = handle.read().split('\n')
    label = re.compile(r'^  ([a-z][a-z0-9-]*)\)$')
    declared = {}
    index = 0
    while index < len(lines):
        match = label.match(lines[index])
        if not match:
            index += 1
            continue
        name = match.group(1)
        index += 1
        while index < len(lines) and lines[index].startswith('    #'):
            found = re.match(r'^    # Shape: (\S+)$', lines[index])
            if found:
                declared[name] = found.group(1)
            index += 1
    return declared


def run_help(path):
    environment = dict(os.environ)
    environment['GITHUB_PERSONAL_ACCESS_TOKEN'] = ''
    environment['GITLAB_PERSONAL_ACCESS_TOKEN'] = ''
    with tempfile.TemporaryDirectory() as empty:
        environment['HOME'] = empty
        command = (['python3', path] if path.endswith(PYTHON_ADAPTER)
                   else ['bash', path])
        done = subprocess.run(command + ['help'], env=environment,
                              capture_output=True, text=True)
    return done


def parse_help(text):
    rows = {}
    for line in text.split('\n'):
        if not line.strip():
            break
        match = re.match(r'^([a-z][a-z0-9-]*)\s+(.*\S)\s*$', line)
        if not match:
            continue
        rows[match.group(1)] = match.group(2).split()[-1]
    return rows


def check(path):
    adapter = os.path.basename(path)
    failures = []

    done = run_help(path)
    if done.returncode != 0:
        return [f'      help exited {done.returncode} with no credentials: '
                f'{done.stderr.strip()[:120]}']

    printed = parse_help(done.stdout)
    truth = truth_python(path) if adapter == PYTHON_ADAPTER else truth_bash(path)

    for name in sorted(truth):
        if name not in printed:
            failures.append(f'      {name}: no row in help')
            continue
        if printed[name] not in SHAPES:
            failures.append(f'      {name}: shape "{printed[name]}" is not one of '
                            f'{", ".join(SHAPES)}')
        if printed[name] != truth[name]:
            failures.append(f'      {name}: help says {printed[name]}, '
                            f'the source says {truth[name]}')

    for name in sorted(set(printed) - set(truth)):
        failures.append(f'      {name}: a help row for a subcommand that is not implemented')

    if adapter == BASH_ADAPTER:
        declared = declared_bash(path)
        for name in sorted(truth):
            if name not in declared:
                failures.append(f'      {name}: no "# Shape:" comment beside the case arm')

    for name, shape in EXPECTED[adapter].items():
        if name in printed and printed[name] != shape:
            failures.append(f'      {name}: expected {shape}, help says {printed[name]}')
        elif name not in printed:
            failures.append(f'      {name}: expected a {shape} row, found none')

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
            adapter = os.path.basename(path)
            truth = truth_python(path) if adapter == PYTHON_ADAPTER else truth_bash(path)
            print(f'  ok   — {relative} ({len(truth)} subcommands)')
    print()
    if broken:
        print('failed')
        return 1
    print('passed (%d adapter copies)' % len(scripts))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
