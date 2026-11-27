#!/usr/bin/env python3

import argparse
import difflib
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORK_DARWIN = 'profiles/larrabeedylan_work_darwin/.claude'
WORK_LINUX = 'profiles/larrabeedylan_work_linux/.claude'
HOME_DARWIN = 'profiles/larrabeedylan_home_darwin/.claude'

SUBSTITUTIONS = [
    (r'an MR', 'a PR'),
    (r'An MR', 'A PR'),
    (r'merge requests', 'pull requests'),
    (r'merge request', 'pull request'),
    (r'Merge Request', 'Pull Request'),
    (r'Merge request', 'Pull request'),
    (r'GitLab', 'GitHub'),
    (r'\bMR(?=\d)', 'PR'),
    (r'\bMRs\b', 'PRs'),
    (r'\bMR\b', 'PR'),
    (r'gitlab-api\.sh', 'github-api.sh'),
]

TRANSFORM_EXEMPT = {
    'environment.json.example':
        'the per-profile forge, reviewer and store values skill-env.sh exists to carry',
    'scripts/skill-env.sh':
        'the seam itself: each profile carries its own defaults in code',
    'scripts/notify-send.sh':
        'the home copy also speaks Telegram, which the Pi reaches through its '
        'scripts/ symlink; the Slack half is this file',
    'skills/fix-feedback/SKILL.md':
        "documents the forge adapter's response shape, which is per-forge",
    'skills/changes-explain/SKILL.md':
        "documents the forge adapter's response shape, which is per-forge",
    'skills/AGENTS.md':
        'documents the adapter contract, the per-profile skill inventory, and rationale '
        'that contrasts the two forges by name',
    'skills/changes-diagram/SKILL.md':
        'the frontmatter trigger list is deliberately bilingual on both profiles',
    'skills/security-audit/resources/stages/stage1_recon.md':
        '"GitLab CI" names a CI product to detect, not forge vocabulary',
}

PRESENCE_EXEMPT = {
    'scripts/gitlab-api.sh':
        'the GitLab adapter; github-api.sh is a separate implementation, not its transform',
    'scripts/github-api.sh':
        'the GitHub adapter; gitlab-api.sh is a separate implementation, not its transform',
    'skills/reflect-week/SKILL.md':
        'reads Slack; work-only by design',
    'skills/reflect-peer/SKILL.md':
        "consumes reflect-week's peer profiles; work-only by design",
    'skills/reflect-self/SKILL.md':
        "consumes reflect-week's weekly reports; work-only by design",
}

WORK_PAIR_EXEMPT = {
    'skills/reflect-week/SKILL.md':
        'BSD date on darwin, GNU date on linux',
}

DERIVE_GUARDS = (
    ('TRANSFORM_EXEMPT', TRANSFORM_EXEMPT),
    ('PRESENCE_EXEMPT', PRESENCE_EXEMPT),
)

ALL_ALLOWLISTS = (
    ('WORK_PAIR_EXEMPT', WORK_PAIR_EXEMPT),
    ('TRANSFORM_EXEMPT', TRANSFORM_EXEMPT),
    ('PRESENCE_EXEMPT', PRESENCE_EXEMPT),
)


def allowlisted_for_derive(rel):
    return [(name, table[rel]) for name, table in DERIVE_GUARDS if rel in table]


def allowlist_status(work_exempted, home_exempted):
    diverging = {('WORK_PAIR_EXEMPT', rel) for rel, _kind, _first, _total in work_exempted}
    for rel, kind, _first, _total in home_exempted:
        table = 'TRANSFORM_EXEMPT' if kind == 'differs' else 'PRESENCE_EXEMPT'
        diverging.add((table, rel))
    declared = [(name, rel) for name, table in ALL_ALLOWLISTS for rel in table]
    settled = sorted((e for e in declared if e not in diverging), key=lambda e: (e[1], e[0]))
    return len(diverging), len(declared), settled


def transform(text):
    for pattern, replacement in SUBSTITUTIONS:
        text = re.sub(pattern, replacement, text)
    return text


def tracked(prefix):
    names = []
    try:
        result = subprocess.run(
            ['git', '-C', REPO, 'ls-files', '-z', '--', prefix],
            capture_output=True, check=True)
        names = [n for n in result.stdout.decode('utf-8').split('\0') if n]
    except (OSError, subprocess.CalledProcessError):
        for dirpath, dirnames, filenames in os.walk(os.path.join(REPO, prefix)):
            dirnames[:] = [d for d in dirnames if d != '__pycache__']
            for name in filenames:
                full = os.path.join(dirpath, name)
                if not os.path.islink(full):
                    names.append(os.path.relpath(full, REPO))
    return {os.path.relpath(n, prefix): os.path.join(REPO, n) for n in names}


def read(path):
    try:
        with open(path, encoding='utf-8') as handle:
            return handle.read()
    except (UnicodeDecodeError, OSError):
        return None


def first_difference(want, got):
    want_lines = want.split('\n')
    got_lines = got.split('\n')
    matcher = difflib.SequenceMatcher(None, want_lines, got_lines, autojunk=False)
    changed = 0
    first = None
    for tag, want_start, want_end, got_start, got_end in matcher.get_opcodes():
        if tag == 'equal':
            continue
        changed += max(want_end - want_start, got_end - got_start)
        if first is None:
            first = (
                want_start + 1,
                want_lines[want_start] if want_start < want_end else '<absent>',
                got_lines[got_start] if got_start < got_end else '<absent>',
            )
    return first, changed


def compare(left_prefix, right_prefix, content_exempt, presence_exempt, apply_transform):
    left = tracked(left_prefix)
    right = tracked(right_prefix)
    enforced = []
    exempted = []

    for rel in sorted(set(left) | set(right)):
        if rel not in right:
            entry = (rel, 'missing from the right-hand profile', None, 0)
            (exempted if rel in presence_exempt else enforced).append(entry)
            continue
        if rel not in left:
            entry = (rel, 'present only in the right-hand profile', None, 0)
            (exempted if rel in presence_exempt else enforced).append(entry)
            continue

        want = read(left[rel])
        got = read(right[rel])
        if want is None or got is None:
            continue
        if apply_transform:
            want = transform(want)
        if want == got:
            continue

        first, total = first_difference(want, got)
        entry = (rel, 'differs', first, total)
        (exempted if rel in content_exempt else enforced).append(entry)

    return enforced, exempted


def render(title, enforced, exempted, reasons, quiet):
    lines = [f'## {title}', '']
    if enforced:
        for rel, kind, first, total in enforced:
            if kind == 'differs':
                lines.append(f'DRIFT  {rel}  ({total} differing lines)')
                line, want, got = first
                lines.append(f'       line {line}')
                lines.append(f'         expected: {want[:160]}')
                lines.append(f'         found:    {got[:160]}')
            else:
                lines.append(f'DRIFT  {rel}  ({kind})')
            lines.append('')
    else:
        lines += ['clean', '']

    if exempted and not quiet:
        lines.append('allowed exceptions, reported but not enforced:')
        for rel, kind, first, total in exempted:
            extent = f'{total} differing lines' if kind == 'differs' else kind
            lines.append(f'  {rel}  ({extent})')
            lines.append(f'      {reasons.get(rel, "")}')
        lines.append('')
    return lines


def cmd_check(args):
    work_enforced, work_exempted = compare(
        WORK_DARWIN, WORK_LINUX, WORK_PAIR_EXEMPT, {}, False)
    home_enforced, home_exempted = compare(
        WORK_DARWIN, HOME_DARWIN, TRANSFORM_EXEMPT, PRESENCE_EXEMPT, True)

    lines = ['Demeter profile transform check', '']
    lines += render('work_darwin vs work_linux (byte-identical)',
                    work_enforced, work_exempted, WORK_PAIR_EXEMPT, args.quiet)
    reasons = dict(TRANSFORM_EXEMPT)
    reasons.update(PRESENCE_EXEMPT)
    lines += render('transform(work_darwin) vs home_darwin',
                    home_enforced, home_exempted, reasons, args.quiet)

    total = len(work_enforced) + len(home_enforced)
    diverging, declared, settled = allowlist_status(work_exempted, home_exempted)
    lines.append(f'{total} file(s) drifted outside the allowlist.' if total
                 else 'No drift outside the allowlist.')
    lines.append(f'{diverging} of {declared} allowlist entries still diverging.')
    if settled:
        lines.append(
            '1 entry no longer diverges — re-check whether it is still needed:'
            if len(settled) == 1 else
            f'{len(settled)} entries no longer diverge — re-check whether each is '
            'still needed:')
        for name, rel in settled:
            lines.append(f'  {rel}  ({name})')
    if total:
        lines += [
            '',
            'Re-derive a home file with:',
            '  profiles/check-transform.py derive <path-inside-.claude> --apply',
            'An allowlisted path is refused there, because deriving it would overwrite',
            'the divergence the entry records; --force overrides that.',
            'If the divergence is deliberate, add it to the allowlist in this script',
            'with a one-line reason.',
        ]

    report = '\n'.join(lines)
    print(report)

    if args.summary:
        try:
            with open(args.summary, 'a', encoding='utf-8') as handle:
                handle.write(f'```\n{report}\n```\n')
        except OSError as err:
            print(f'could not write the summary file: {err}', file=sys.stderr)

    if total and not args.warn_only:
        return 1
    return 0


def report_forced_overwrite(target, derived, entries):
    rel = os.path.relpath(target, REPO)
    existing = read(target)
    if existing is None:
        print(f'--force: {rel} has no home copy; creating one from work_darwin')
    else:
        _first, changed = first_difference(existing, derived)
        print(f'--force: replacing the allowlisted divergence in {rel} '
              f'({changed} differing lines)')
    for name, reason in entries:
        print(f'  discarding {name}: {reason}')


def cmd_derive(args):
    entries = allowlisted_for_derive(args.path)
    if entries and args.apply and not args.force:
        print(f'refusing to derive {args.path}: it is allowlisted, which records that '
              "home_darwin's copy is deliberately not transform(work_darwin).",
              file=sys.stderr)
        for name, reason in entries:
            print(f'  {name}: {reason}', file=sys.stderr)
        print('Overwriting it would destroy that divergence, and check would then pass '
              'because it did.', file=sys.stderr)
        print('Pass --force to overwrite anyway, and drop the allowlist entry if it is '
              'being retired.', file=sys.stderr)
        return 1

    source = os.path.join(REPO, WORK_DARWIN, args.path)
    target = os.path.join(REPO, HOME_DARWIN, args.path)
    text = read(source)
    if text is None:
        print(f'cannot read {source}', file=sys.stderr)
        return 1
    derived = transform(text)
    if args.apply:
        if entries:
            report_forced_overwrite(target, derived, entries)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, 'w', encoding='utf-8') as handle:
            handle.write(derived)
        print(f'wrote {os.path.relpath(target, REPO)}')
    else:
        sys.stdout.write(derived)
    return 0


def cmd_rules(args):
    print('substitutions, in order:')
    for pattern, replacement in SUBSTITUTIONS:
        print(f'  {pattern:<20} -> {replacement}')
    print()
    print('exempt from the transform comparison:')
    for rel, reason in TRANSFORM_EXEMPT.items():
        print(f'  {rel}\n      {reason}')
    print()
    print('exempt from the presence comparison:')
    for rel, reason in PRESENCE_EXEMPT.items():
        print(f'  {rel}\n      {reason}')
    print()
    print('exempt between the two work profiles:')
    for rel, reason in WORK_PAIR_EXEMPT.items():
        print(f'  {rel}\n      {reason}')
    print()
    print('derive --apply refuses a path in either of these, since the entry records')
    print('that the home copy is deliberately not transform(work_darwin):')
    for name, _table in DERIVE_GUARDS:
        print(f'  {name}')
    print('--force overrides the refusal and prints what it replaced.')
    print('WORK_PAIR_EXEMPT is not consulted: derive only ever writes home_darwin.')
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Check that the two work profiles are byte-identical and that '
                    'home_darwin is the mechanical transform of work_darwin.')
    sub = parser.add_subparsers(dest='command')

    check = sub.add_parser('check', help='compare the profiles and report drift')
    check.add_argument('--warn-only', action='store_true',
                       help='always exit 0, for callers that must not fail')
    check.add_argument('--quiet', action='store_true',
                       help='leave the allowed exceptions out of the report')
    check.add_argument('--summary', metavar='FILE',
                       help='also append the report to FILE as a fenced block')
    check.set_defaults(func=cmd_check)

    derive = sub.add_parser(
        'derive', help="print home_darwin's copy of a file, derived from work_darwin")
    derive.add_argument('path', help='path inside .claude, e.g. skills/aidr/SKILL.md')
    derive.add_argument('--apply', action='store_true',
                        help="overwrite home_darwin's copy with the derived text")
    derive.add_argument('--force', action='store_true',
                        help='apply to an allowlisted path anyway, destroying the '
                             'divergence the entry records')
    derive.set_defaults(func=cmd_derive)

    rules = sub.add_parser('rules', help='print the substitutions and the allowlist')
    rules.set_defaults(func=cmd_rules)

    args = parser.parse_args()
    if not args.command:
        args = parser.parse_args(['check'])
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
