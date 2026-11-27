#!/usr/bin/env python3
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = [
    'larrabeedylan_home_darwin',
    'larrabeedylan_work_darwin',
    'larrabeedylan_work_linux',
]

POSTING_PATHS = {
    'fix-feedback': [
        ('the finding', re.compile(r'create-diff-comment')),
        ('the reply', re.compile(r'reply-to-thread(?:-stdin)?\b')),
    ],
    'ping': [
        ('the notification body', re.compile(r'notify\.py')),
    ],
}

GUARD_DOC = ['fix-linear', 'fix-freeform']

HELPER = re.compile(r'(?:~|\$HOME|"\$HOME")/\.claude/(?:scripts|hooks)/[A-Za-z0-9_.-]+')
HEREDOC = re.compile(r"<<-?\s*'[A-Za-z_][A-Za-z0-9_]*'")
REDIRECT = re.compile(r'<\s*<scratchpad>/')
BODY_FILE_ARG = re.compile(r'<scratchpad>/[A-Za-z0-9_<>.-]+\.(?:md|txt)')
BODY_AS_ARG = re.compile(r'"<(?:reply|body|comment|note)[_ ]?(?:text|body)?>"')
GUARD_READS_TEXT = re.compile(
    r'reads?\s+the\s+text\s+of\s+the\s+whole\s+command|reads\s+the\s+command\'s\s+\*?text\*?',
    re.I)

FORBIDDEN = [
    ('temp files with redirects', 'bans the file form outright'),
    ('the only sanctioned form', 'states the heredoc is the only form allowed'),
]

RULES = """check-stdin-body-rule.py — the stdin seam for the skills that post prose.

what it checks, and what each one is written against:

  every skill in POSTING_PATHS ships a SKILL.md in every profile. that list is
  the set of skills that hand a body of prose to a helper script under
  ~/.claude, which is the only place this rule can be broken

  EACH POSTING PATH, separately, shows both forms: a quoted heredoc and a file
  (a redirect from the scratchpad, or a scratchpad path where the script takes
  a body file). a path is identified by the subcommand on the command line --
  create-diff-comment for a finding, reply-to-thread/-stdin for a reply,
  notify.py for a notification -- so the check is anchored to the path rather
  than counted over the file. an earlier version summed matching lines and
  compared the total against a per-skill minimum, which is not the same thing:
  deleting the finding path's file form while duplicating the reply path's kept
  the total at 2 and passed, leaving a posting path with no runnable form. a
  count of lines is not a count of paths

  both forms have to stay documented because the worktree isolation guard rules
  the heredoc out: it reads the text of the whole command, heredoc body
  included, and refuses one that feeds an out-of-worktree script any text
  naming git. a review comment about a git defect is the ordinary case on a
  repo like this one, so a file mandating the heredoc alone leaves an isolated
  run with no sanctioned way to post at all. that is what happened: a run used
  a file five times in direct violation of the skill it was following, and was
  right to

  no helper command passes the body as a shell argument. that is the half of
  the rule the prose keeps banning, and checking only for the deleted wording
  would not notice the form coming back: restoring the work profile's old
  `reply-to-thread … "<reply_text>"` beside the new stdin call satisfied every
  other check in this file

  the same file says the guard reads the command's text. a form shown with no
  reason attached is one the next reader deletes as redundant, since on safety
  grounds it is -- the reason is the whole content of the rule. this is checked
  with GUARD_READS_TEXT and not with a looser "worktree-isolated|isolation
  guard" pattern, which fix-feedback already matched before this rule existed
  and so could never have failed for the skill it was written for

  no SKILL.md still forbids the file form. the exact prohibition this replaced
  was "never pass it as a CLI argument or use temp files with redirects", which
  had the correct reason bolted to the wrong half: an argument is unsafe, a
  redirect is not

  every skill in GUARD_DOC documents the refusal and names the file form as the
  way round it. those two carry the measurements behind this whole rule, so a
  job that read neither while claiming to cover them was worse than not
  covering them at all

what it deliberately does not check:

  that any particular command is accepted or refused. the guard lives in the
  harness, not in this repository, so a test here can only pin what the prose
  instructs. the refusals behind these rules were measured by running them from
  inside a worktree, which is the only place they are visible

  that the profile copies agree. check-transform.py already compares
  work_darwin against work_linux byte-identical and transform(work_darwin)
  against home_darwin, so ping -- which carries no forge vocabulary, making its
  transform the identity -- is pinned across all three by that check alone. an
  earlier version of this file duplicated that as a LOCKSTEP check and
  justified it by claiming check-transform.py says nothing about the two work
  copies, which its own WORK_PAIR_EXEMPT (reflect-week, and nothing else)
  contradicts

  review-code and changes-diagram, whose python heredocs were reported as
  refused and measured running. they feed no helper script and name no git, so
  they are outside the rule rather than exceptions to it
"""


def fail(problems, message):
    problems.append(message)


def read_skill(problems, profile, skill, why):
    path = os.path.join(REPO, 'profiles', profile, '.claude', 'skills',
                        skill, 'SKILL.md')
    if not os.path.isfile(path):
        fail(problems, f'{profile}/{skill}: no SKILL.md, but it is listed {why}')
        return None
    with open(path, encoding='utf-8') as handle:
        return handle.read()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'rules':
        print(RULES, end='')
        return 0

    problems = []
    checked = 0
    paths_checked = 0

    for profile in PROFILES:
        for skill, posting_paths in POSTING_PATHS.items():
            label = f'{profile}/{skill}'
            md = read_skill(problems, profile, skill,
                            'as posting a body through a helper script')
            if md is None:
                continue
            checked += 1
            helper_lines = [l for l in md.splitlines() if HELPER.search(l)]

            for name, subcommand in posting_paths:
                paths_checked += 1
                lines = [l for l in helper_lines if subcommand.search(l)]
                if not lines:
                    fail(problems, f'{label}: no helper command for {name}, so that '
                                   f'posting path is gone or its example broke')
                    continue
                if not any(HEREDOC.search(l) for l in lines):
                    fail(problems, f'{label}: {name} shows no quoted heredoc')
                if not any(REDIRECT.search(l) or BODY_FILE_ARG.search(l)
                           for l in lines):
                    fail(problems, f'{label}: {name} shows no file form, so a '
                                   f'worktree-isolated run whose body names git has '
                                   f'no sanctioned way to post on that path')

            for line in helper_lines:
                if BODY_AS_ARG.search(line):
                    fail(problems, f'{label}: a helper command passes the body as a '
                                   f'shell argument ({line.strip()!r}), which is the '
                                   f'one form the rule forbids')

            if not GUARD_READS_TEXT.search(md):
                fail(problems, f'{label}: never says the guard reads the command\'s '
                               f'text. without that, a reader checks their paths, finds '
                               f'them inside the worktree, and concludes the refusal '
                               f'cannot apply to them')

            for phrase, why in FORBIDDEN:
                if phrase in md:
                    fail(problems, f'{label}: still contains {phrase!r}, which {why}')

        for skill in GUARD_DOC:
            label = f'{profile}/{skill}'
            md = read_skill(problems, profile, skill,
                            'as documenting the isolation guard')
            if md is None:
                continue
            checked += 1
            if not GUARD_READS_TEXT.search(md):
                fail(problems, f'{label}: does not document that the guard reads the '
                               f'command\'s text, which is why the file form exists')
            if 'redirect' not in md.lower():
                fail(problems, f'{label}: documents the refusal without naming the '
                               f'file form that works around it')

    if problems:
        print(f'{len(problems)} problem(s):')
        for problem in problems:
            print(f'  {problem}')
        return 1

    print(f'ok: {checked} skill copy(ies) across {len(PROFILES)} profiles, '
          f'{paths_checked} posting path(s)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
