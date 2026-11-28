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

GLOBAL_START = re.compile(r'^## Spawn subagents freely\s*$')
STEP_5B_START = re.compile(r'^## Step 5b\b')
RERUN_BULLET = re.compile(r'^- Re-run at a higher ')
HEADING = re.compile(r'^#')
TOP_BULLET = re.compile(r'^- \S')

MUST_BE_OFFERED = re.compile(r'must\s+be\s+offered', re.I)
SHOULD_BE_OFFERED = re.compile(r'should\s+(?:still\s+)?be\s+offered', re.I)
ONE_SWARM = re.compile(r'authorises\s+\*\*one\*\*')
ONE_RUN_NAMED = re.compile(r'one\s+`review-code`\s+run')
OFFER_NOT_DECIDE = re.compile(r'\*offer\*[^.]{0,120}?never\s+to\s+decide', re.S)
JUDGMENT_GRANT = re.compile(r'trust\s+your\s+judgment', re.I)
BUDGET_CARVED = re.compile(r'budget\s+is\s+explicitly\s+not\s+one\s+of\s+those\s+calls', re.I)
SCALE_COST = re.compile(r'4M\s+subagent\s+tokens')
WINDOW_COST = re.compile(r'quarter\s+of\s+a\s+session\s+window', re.I)

CLAUSES_NAMED = (
    (re.compile(r'`autopilot`\s+Step\s+5b'), "`autopilot` Step 5b's redesign clause"),
    (re.compile(r'`review-code`\s+Step\s+6'), "`review-code` Step 6's higher-scale offer"),
)

ONCE_PER_RUN = re.compile(r'once\s+per\s+run,\s+not\s+once\s+per\s+round', re.I)
OLD_GRANT = re.compile(r'^[^"“]*\bOne re-run is justified when a round changed', re.M)
OFFERING = re.compile(r'\*offering\*', re.I)
NEVER_LAUNCH = re.compile(r'never\s+launch(?:ing|\s+it)', re.I)
FLAG_BOUGHT_ONE = re.compile(r'authorised\s+\*\*one\*\*\s+swarm', re.I)

USERS_TO_AUTHORISE = re.compile(r"user's\s+to\s+authorise", re.I)
OFFER_AND_STOP = re.compile(r'offer\s+it\s+and\s+stop\s+there', re.I)
SCALE_FIT_HEDGE = re.compile(r'rather\s+than\s+offering\s+the\s+re-run\s+blindly', re.I)

RULES = """check-swarm-opt-in-rule.py -- a swarm flag authorises one swarm.

the rule spans three files and the agreement between them is the property.
the global CLAUDE.md says who decides a second swarm; autopilot Step 5b and
review-code Step 6 are the two clauses that used to read as permission to
decide it. a skill that drifts back to a grant makes the global rule a fight
to be won at runtime rather than a settled question, and that fight has
already been lost once.

on 2026-11-27 a run resolved --review true, spent the authorised review-code
swarm, worked its findings, and then launched a SECOND swarm on its own
judgment -- roughly 4M more subagent tokens, a quarter of a session window,
unasked. it cited autopilot Step 5b's "one re-run is justified when a round
changed the shape of the change rather than patching it". the condition was
real. the authority was never there.

what the global section owes, in every profile

  it says the Workflow tool MUST be offered, not SHOULD. the old wording lost
  to a skill clause that sounded more specific, and "should still be offered"
  reads as a nicety beside the hard prohibitions in the same file. both the
  presence of must and the ABSENCE of should are pinned, because adding the
  stronger sentence beside the weaker one leaves the weaker one to be found.

  it states the count. the failing run had an explicit opt-in; nothing told it
  that an opt-in is for one run rather than for the topic. silence on the
  number is what the run read as a standing licence.

  it says a skill's "justified" condition is permission to OFFER and never to
  decide, and it names both clauses it overrides. naming them is the part that
  beats a clause which sounds more specific than a general rule -- an override
  a reader has to infer is an override that loses.

  it carves budget out of autopilot's "trust your judgment for everything
  after the code is written". a second swarm is after the code is written, so
  it sits squarely inside that grant unless the grant is narrowed by name.

  it carries the cost as a figure. "dozens of agents" is a scale; 4M subagent
  tokens and a quarter of a session window is a price, and only the second one
  makes the asking-versus-launching asymmetry legible.

what autopilot Step 5b owes, in every profile

  it keeps the once-per-run bound. the fix narrowed who decides the exception,
  not whether the bound exists.

  it licenses an OFFER and says the launch never follows from its own
  judgment. both halves, because "worth offering" alone was the reading that
  failed -- the run offered nothing and launched anyway.

  it names the one-swarm bound and the judgment carve-out, so the clause
  carries its own limit instead of depending on the global file being read at
  the moment of the decision. that dependency is the ticket's own gap 3.

  the old sentence is gone from prose. the check allows it inside quotation
  marks, because the section now cites its former wording as the thing that
  was misread, and forbidding the quote would forbid recording the failure.

what review-code Step 6 owes, in every profile

  it names who authorises, and says to stop at the offer. this bullet was
  always the weaker of the two -- it sits under a heading titled "Offer Next
  Steps" whose preamble says to offer as plain text, and it already warned
  against offering blindly. its only gap was never saying whose call it is.

  it keeps the scale-fit hedge. the two warnings answer different questions --
  whether to mention the re-run at all, and who decides it -- and the second
  is not a replacement for the first.

what it deliberately does not check

  that any run actually asked. nothing reachable from a test observes a swarm
  launch, which is the same reason the re-auth gate shipped without an
  interlock. this pins what the prose instructs.

  the Pi profile. its skills/ is a symlink into home_darwin and it ships no
  user-level CLAUDE.md, so there is nothing of its own to check.

why a separate checker at all

  check-transform.py compares each file against its counterpart ACROSS
  profiles and never two files against each other. none of these three paths
  is allowlisted, so a missing copy is already caught -- but a Step 5b
  reworded back into a grant identically in all three profiles is not drift
  and passes every existing check. the agreement between the global rule and
  the two clauses it overrides is the one property nothing else pins.
"""


def read_lines(problems, label, path):
    if not os.path.isfile(path):
        problems.append(f'{label}: no file at {path}')
        return None
    with open(path, encoding='utf-8') as handle:
        return handle.read().split('\n')


def slice_at(lines, start_re, end_re):
    starts = [i for i, line in enumerate(lines) if start_re.match(line)]
    if len(starts) != 1:
        return None, len(starts)
    start = starts[0]
    end = next((i for i in range(start + 1, len(lines)) if end_re.match(lines[i])),
               len(lines))
    return '\n'.join(lines[start:end]), 1


def check_global(problems, profile):
    label = f'{profile}/CLAUDE.md'
    path = os.path.join(REPO, 'profiles', profile, '.claude', 'CLAUDE.md')
    lines = read_lines(problems, label, path)
    if lines is None:
        return False

    section, found = slice_at(lines, GLOBAL_START, HEADING)
    if section is None:
        problems.append(f'{label}: {found} "Spawn subagents freely" heading(s); '
                        f'expected 1')
        return False

    if not MUST_BE_OFFERED.search(section):
        problems.append(f'{label}: the section does not say the Workflow tool MUST be '
                        f'offered; an advisory rule is what lost to a skill clause')
    if SHOULD_BE_OFFERED.search(section):
        problems.append(f'{label}: the section still says the Workflow tool SHOULD be '
                        f'offered; the weaker sentence is the one a reader finds')
    if not ONE_SWARM.search(section) or not ONE_RUN_NAMED.search(section):
        problems.append(f'{label}: the section does not state that a swarm flag '
                        f'authorises one run; silence on the count is what a run read '
                        f'as a standing licence')
    if not OFFER_NOT_DECIDE.search(section):
        problems.append(f'{label}: the section does not say a skill\'s "justified" '
                        f'condition is permission to offer and never to decide')
    for pattern, clause in CLAUSES_NAMED:
        if not pattern.search(section):
            problems.append(f'{label}: the section does not name {clause} as a clause '
                            f'it overrides, so the override has to be inferred')
    if not JUDGMENT_GRANT.search(section) or not BUDGET_CARVED.search(section):
        problems.append(f'{label}: the section does not carve budget out of '
                        f'autopilot\'s "trust your judgment after the code is '
                        f'written" grant, which a second swarm sits inside')
    if not SCALE_COST.search(section) or not WINDOW_COST.search(section):
        problems.append(f'{label}: the section does not carry the cost as a figure; '
                        f'a scale is not a price')
    return True


def check_autopilot(problems, profile):
    label = f'{profile}/autopilot'
    path = os.path.join(REPO, 'profiles', profile, '.claude', 'skills',
                        'autopilot', 'SKILL.md')
    lines = read_lines(problems, label, path)
    if lines is None:
        return False

    section, found = slice_at(lines, STEP_5B_START, HEADING)
    if section is None:
        problems.append(f'{label}: {found} "Step 5b" heading(s); expected 1')
        return False

    if not ONCE_PER_RUN.search(section):
        problems.append(f'{label}: Step 5b no longer carries the once-per-run bound; '
                        f'the fix narrowed who decides the exception, not the bound')
    if OLD_GRANT.search(section):
        problems.append(f'{label}: Step 5b still states the re-run as justified in its '
                        f'own prose; that sentence was cited to spend an unasked swarm '
                        f'(quoting the old wording as a record is allowed)')
    if not OFFERING.search(section) or not NEVER_LAUNCH.search(section):
        problems.append(f'{label}: Step 5b does not license an offer and forbid the '
                        f'launch; the failing run offered nothing and launched anyway')
    if not FLAG_BOUGHT_ONE.search(section):
        problems.append(f'{label}: Step 5b does not say the flag authorised one swarm, '
                        f'so the clause carries no limit of its own')
    if not JUDGMENT_GRANT.search(section):
        problems.append(f'{label}: Step 5b does not name the "trust your judgment" '
                        f'grant it is narrowing, which is the grant a second swarm '
                        f'sits inside')
    return True


def check_review_code(problems, profile):
    label = f'{profile}/review-code'
    path = os.path.join(REPO, 'profiles', profile, '.claude', 'skills',
                        'review-code', 'SKILL.md')
    lines = read_lines(problems, label, path)
    if lines is None:
        return False

    bullet, found = slice_at(lines, RERUN_BULLET, TOP_BULLET)
    if bullet is None:
        problems.append(f'{label}: {found} "Re-run at a higher" bullet(s); expected 1')
        return False

    if not USERS_TO_AUTHORISE.search(bullet) or not OFFER_AND_STOP.search(bullet):
        problems.append(f'{label}: the re-run bullet does not say the second pass is '
                        f"the user's to authorise and to stop at the offer")
    if not SCALE_FIT_HEDGE.search(bullet):
        problems.append(f'{label}: the re-run bullet lost the scale-fit hedge; '
                        f'whether to mention a re-run and who decides it are '
                        f'different questions')
    return True


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'rules':
        print(RULES, end='')
        return 0

    problems = []
    checked = 0

    for profile in PROFILES:
        for check in (check_global, check_autopilot, check_review_code):
            if check(problems, profile):
                checked += 1

    if problems:
        print(f'{len(problems)} problem(s):')
        for problem in problems:
            print(f'  {problem}')
        return 1

    print(f'ok: {checked} section(s) across {len(PROFILES)} profiles')
    return 0


if __name__ == '__main__':
    sys.exit(main())
