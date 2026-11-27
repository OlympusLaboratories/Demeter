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

SKILLS = {'fix-feedback': 2, 'ping': 1}
LOCKSTEP = ['ping']

HELPER = re.compile(r'(?:~|\$HOME|"\$HOME")/\.claude/(?:scripts|hooks)/[A-Za-z0-9_.-]+')
HEREDOC = re.compile(r"<<-?\s*'[A-Za-z_][A-Za-z0-9_]*'")
REDIRECT = re.compile(r'<\s*<scratchpad>/')
BODY_FILE_ARG = re.compile(r'<scratchpad>/[A-Za-z0-9_<>.-]+\.(?:md|txt)')
ISOLATION = re.compile(r'worktree[- ]isolated|isolation guard', re.I)
GUARD_READS_TEXT = re.compile(
    r'reads?\s+the\s+text\s+of\s+the\s+whole\s+command|reads\s+the\s+command\'s\s+\*?text\*?',
    re.I)

RULES = """check-stdin-body-rule.py — the stdin seam for the skills that post prose.

what it checks, and what each one is written against:

  every skill listed ships a SKILL.md in every profile. the list is the set of
  skills that hand a body of prose to a helper script under ~/.claude, which is
  the only place this rule can be broken

  a SKILL.md that shows a quoted heredoc feeding one of those scripts also
  shows the file form -- a redirect from the scratchpad, or a scratchpad path
  passed where the script takes a body file -- once per posting path the skill
  has, which is the count beside its name. the minimum is per-skill rather than
  "at least one" because fix-feedback posts on two independent paths, a finding
  and a reply, and a single `any` check passed with the redirect deleted from
  one of them. it is not a count of heredocs either: the autonomous reply
  deliberately cites the step above rather than repeating both forms a third
  time. the two forms are equally safe
  because the script collects the text itself either way, and both have to stay
  documented because the worktree isolation guard rules the heredoc out: it
  reads the text of the whole command, heredoc body included, and refuses one
  that feeds an out-of-worktree script any text naming git. a review comment
  about a git defect is the ordinary case on a repo like this one, so a file
  mandating the heredoc alone leaves an isolated run with no sanctioned way to
  post at all. that is what happened: a run used a file five times in direct
  violation of the skill it was following, and was right to

  the same file names the isolation guard and states that the guard reads the
  command's text. a redirect shown with no reason attached is a form the next
  reader deletes as redundant, since on safety grounds it is -- the reason is
  the whole content of the rule

  no SKILL.md still forbids the file form. the exact prohibition this replaced
  was "never pass it as a CLI argument or use temp files with redirects", which
  had the correct reason bolted to the wrong half: an argument is unsafe, a
  redirect is not

  the skills in the lockstep list stay byte-identical across the three
  profiles. ping carries no forge vocabulary, so check-transform.py compares it
  like any other file and would catch a divergence -- but it compares home
  against work and says nothing about the two work copies drifting from each
  other, which is where a hand-replicated edit goes wrong

what it deliberately does not check:

  that any particular command is accepted or refused. the guard lives in the
  harness, not in this repository, so a test here can only pin what the prose
  instructs. the refusals behind these rules were measured by running them from
  inside a worktree, which is the only place they are visible

  review-code and changes-diagram, whose python heredocs were reported as
  refused and measured running. they feed no helper script and name no git, so
  they are outside the rule rather than exceptions to it
"""

FORBIDDEN = [
    ('temp files with redirects', 'bans the file form outright'),
    ('the only sanctioned form', 'states the heredoc is the only form allowed'),
]


def fail(problems, message):
    problems.append(message)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'rules':
        print(RULES, end='')
        return 0

    problems = []
    checked = 0

    for profile in PROFILES:
        for skill, want_files in SKILLS.items():
            path = os.path.join(REPO, 'profiles', profile, '.claude', 'skills',
                                skill, 'SKILL.md')
            label = f'{profile}/{skill}'
            if not os.path.isfile(path):
                fail(problems, f'{label}: no SKILL.md, but it is listed as posting '
                               f'a body through a helper script')
                continue
            with open(path, encoding='utf-8') as handle:
                md = handle.read()
            checked += 1

            feeds_helper = any(
                HEREDOC.search(line) and HELPER.search(line)
                for line in md.splitlines())
            if not feeds_helper:
                fail(problems, f'{label}: no quoted heredoc feeding a ~/.claude helper '
                               f'script. either the skill stopped posting a body, in '
                               f'which case drop it from SKILLS, or the example broke')
                continue

            file_forms = sum(
                1 for line in md.splitlines()
                if HELPER.search(line)
                and (REDIRECT.search(line) or BODY_FILE_ARG.search(line)))
            if file_forms < want_files:
                fail(problems, f'{label}: {file_forms} command(s) show the file form and '
                               f'{want_files} posting path(s) need one, so a '
                               f'worktree-isolated run whose body names git has a path '
                               f'with no sanctioned way to post')

            if not ISOLATION.search(md):
                fail(problems, f'{label}: documents a file form without naming the '
                               f'isolation guard, so the reason is missing and the next '
                               f'reader drops the form as redundant')

            if not GUARD_READS_TEXT.search(md):
                fail(problems, f'{label}: never says the guard reads the command\'s '
                               f'text. without that, a reader checks their paths, finds '
                               f'them inside the worktree, and concludes the refusal '
                               f'cannot apply to them')

            for phrase, why in FORBIDDEN:
                if phrase in md:
                    fail(problems, f'{label}: still contains {phrase!r}, which {why}')

    for skill in LOCKSTEP:
        bodies = {}
        for profile in PROFILES:
            path = os.path.join(REPO, 'profiles', profile, '.claude', 'skills',
                                skill, 'SKILL.md')
            if os.path.isfile(path):
                with open(path, 'rb') as handle:
                    bodies[profile] = handle.read()
        if len(set(bodies.values())) > 1:
            fail(problems, f'{skill}/SKILL.md is not byte-identical across the '
                           f'profiles that have it: '
                           f'{", ".join(sorted(bodies))}')

    if problems:
        print(f'{len(problems)} problem(s):')
        for problem in problems:
            print(f'  {problem}')
        return 1

    print(f'ok: {checked} skill copy(ies) across {len(PROFILES)} profiles, '
          f'{len(LOCKSTEP)} in lockstep')
    return 0


if __name__ == '__main__':
    sys.exit(main())
