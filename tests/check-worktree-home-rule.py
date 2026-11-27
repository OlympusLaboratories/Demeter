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

SKILLS = ['fix-linear', 'fix-freeform']

CATALOGUE_START = re.compile(r'isolation guard', re.I)
INSTALLER_START = re.compile(r"^- \*\*Running the repo's own installer")
SIBLING_BULLET = re.compile(r'^- \S')
HEADING = re.compile(r'^#')
RECIPE = re.compile(r'```bash\n(.*?)```', re.S)

HOME_NAMED = re.compile(r'`?HOME=')
EVERY_FORM = re.compile(r'in\s+every\s+form', re.I)
BARE_FORM = re.compile(r'`HOME=<scratch>')
ENV_FORM = re.compile(r'`env\s+HOME=<scratch>')
EXPORT_FORM = re.compile(r'`export\s+HOME=<scratch>')
ONE_MESSAGE = re.compile(r'injecting\s+git\s+configuration', re.I)

EXIT_TOOL = re.compile(r'`ExitWorktree`')
KEEP_ACTION = re.compile(r'action:\s*"keep"')
RETURN_TOOL = re.compile(r'`EnterWorktree`')
ABSOLUTE_PATH = re.compile(r'absolute\s+path', re.I)
WRAPPER_REJECTED = re.compile(
    r'wrapper\s+script[^.]{0,200}?(?:is\s+still\s+wrong|not\s+the\s+way)', re.I)
MKTEMP = re.compile(r'mktemp -d')

RECIPE_PINS = (
    (re.compile(r'\bHOME='), 'the HOME= assignment'),
    (re.compile(r'\bXDG_CONFIG_HOME='), 'the XDG_CONFIG_HOME= unset'),
    (re.compile(r'\bGIT_CONFIG_GLOBAL='), 'the GIT_CONFIG_GLOBAL= pin'),
    (re.compile(r'<WORKTREE>/'), "the worktree-rooted path to the installer"),
)

RULES = """check-worktree-home-rule.py -- the scratch-HOME seam in the fix skills.

the unit is the SECTION, not the file. two earlier drafts got this wrong in the
same direction and each was caught by running it. the first searched each
SKILL.md whole, and passed a mutation that deleted the escape from the guard
catalogue because the installer step further down still named it. the second
bounded the catalogue only at its far end, by the installer bullet -- so the
slice ran from the first /isolation guard/ match to that bullet, measured at
261 lines across 12 headings in fix-linear and 151 across 4 in fix-freeform,
and a HOME paragraph relocated anywhere in that quarter of the file still
passed. the catalogue now ends at the first heading after the LAST guard
match, which is the section boundary, so relocation out of the section fails
where plain deletion already did.

the general lesson, since it has now cost two drafts: a section is bounded at
BOTH ends or it is not a section. an assertion scoped to a slice is only as
strong as the slice, and a slice that reaches to the next thing you happened
to be looking for is a file search wearing a section's name.

what the guard catalogue owes, in both fix skills in every profile

  it names the HOME= refusal at all. fix-linear Step 5 prescribed a scratch
  HOME as THE way to verify an installer change and forbade the real HOME in
  the same bullet, while the guard refuses every form of setting HOME -- so
  from a worktree the step offered one option the harness refuses and one it
  forbids itself, with no third. Step 2 cuts that worktree on every
  --branch new run, which is this machine's default. the catalogue already
  listed the for loop, the compound inspection, the multi-line git body and the
  heredoc naming git, and a list that thorough reads as exhaustive: an omission
  from it is a claim, not a silence.

  it says the assignment is refused in EVERY form, and names all three -- the
  bare HOME=<scratch> prefix, the env HOME=<scratch> prefix, and an
  export HOME=<scratch> line in a multi-line script.

  it names the escape. a catalogue entry that records a refusal and no way out
  leaves the reader exactly where the missing entry left them, which is the
  whole defect one step along.

  it quotes the one refusal message. the ticket that reported this predicted
  the compound form would answer with the "too complex to verify" wording other
  shapes get; it does not, and all three return the same "injecting git
  configuration" message. a reader who greps for the wrong string concludes the
  refusal is not about them, so the message is pinned rather than the
  prediction.

what the installer step owes, in both fix skills in every profile

  it still carries the technique (mktemp -d). the fix was to name the escape,
  not to retire the bullet.

  it carries a runnable bash recipe, and the recipe itself holds the HOME=
  assignment, the XDG_CONFIG_HOME= unset, the GIT_CONFIG_GLOBAL= pin and the
  <WORKTREE>/-rooted path. these are pinned INSIDE the fenced block, not
  anywhere in the bullet, and that distinction was a defect twice over. MKTEMP
  was meant to stand for "still carries the technique" and matches the bullet's
  own prose sentence "pointing HOME at a mktemp -d makes that harmless", so the
  whole fenced block could be deleted -- the XDG and GIT_CONFIG_GLOBAL pins
  with it -- and every assertion still passed. ABSOLUTE_PATH likewise matches
  the sentence "the absolute path is the load-bearing part", so rewriting the
  recipe's last line to a bare ./install.sh passed the very check whose message
  says the run would verify the main checkout's installer instead. an assertion
  pointed at the prose describing a command is not an assertion about the
  command.

  it names both legs of the escape -- ExitWorktree with action "keep", and
  EnterWorktree to come back. keep is the action because the worktree was
  entered by path rather than created by the tool, so the exit removes nothing.
  autopilot Step 10d already takes that exit to reach freshen, so this is a
  route already measured in this repo rather than a new one.

  it says the worktree's copy is invoked by absolute path. running the
  installer from the main checkout verifies the code the branch is changing
  away from, so a run that reports success there has proved nothing about the
  change; install.sh resolves REPO_DIR from BASH_SOURCE, and the absolute path
  is what makes the run read the branch's own tree.

  it records the wrapper script as rejected. a script holding the assignment
  inside the file IS accepted, because the guard is static and reads a
  command's text -- which is exactly why it is not the sanctioned route: it
  hides the refusal rather than answering it, it cannot be reviewed by anyone
  reading the command, and it depends on harness text analysis staying loose
  where the exit depends on a declared tool contract. somebody will find it, so
  it is written down as refused instead of left unmentioned.

what it deliberately does not check

  whether the guard accepts any given command. that lives in the harness, not
  this repo, so this pins what the prose instructs. the refusals behind it were
  measured by running them from inside a worktree, which is the only place they
  are visible. check-stdin-body-rule.py pins its sibling rule the same way.

why a separate checker at all

  check-transform.py compares each file against its counterpart ACROSS
  profiles and never two skills against each other, so three identical copies
  of a bullet missing from the sibling skill pass every other check. only
  fix-linear carried the technique while both carried the catalogue, so the two
  skills disagreed about whether it exists; that agreement is the one property
  nothing else pins.
"""


def read_skill(problems, label, profile, skill):
    path = os.path.join(REPO, 'profiles', profile, '.claude', 'skills',
                        skill, 'SKILL.md')
    if not os.path.isfile(path):
        problems.append(f'{label}: no SKILL.md at {path}')
        return None
    with open(path, encoding='utf-8') as handle:
        return handle.read().split('\n')


def split_sections(problems, label, lines):
    starts = [i for i, line in enumerate(lines) if INSTALLER_START.match(line)]
    if len(starts) != 1:
        problems.append(f'{label}: {len(starts)} installer bullet(s); expected 1 '
                        f'(the scratch-HOME technique must live in both skills)')
        return None, None
    start = starts[0]

    guard = [i for i, line in enumerate(lines[:start]) if CATALOGUE_START.search(line)]
    if not guard:
        problems.append(f'{label}: no isolation-guard catalogue ahead of the '
                        f'installer bullet')
        return None, None
    stop = next((i for i in range(guard[-1] + 1, start) if HEADING.match(lines[i])),
                start)
    catalogue = '\n'.join(lines[guard[0]:stop])

    end = start + 1
    while end < len(lines) and not SIBLING_BULLET.match(lines[end]):
        end += 1
    installer = '\n'.join(lines[start:end])
    return catalogue, installer


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'rules':
        print(RULES, end='')
        return 0

    problems = []
    checked = 0

    for profile in PROFILES:
        for skill in SKILLS:
            label = f'{profile}/{skill}'
            lines = read_skill(problems, label, profile, skill)
            if lines is None:
                continue
            catalogue, installer = split_sections(problems, label, lines)
            if catalogue is None:
                continue
            checked += 1

            if not HOME_NAMED.search(catalogue):
                problems.append(f'{label}: the guard catalogue never names the HOME= '
                                f'refusal, so a reader consulting a list that '
                                f'thorough concludes a scratch HOME is available')
            else:
                if not EVERY_FORM.search(catalogue):
                    problems.append(f'{label}: the catalogue does not say the '
                                    f'assignment is refused in every form')
                for pattern, form in ((BARE_FORM, 'the bare HOME=<scratch> prefix'),
                                      (ENV_FORM, 'the env HOME=<scratch> prefix'),
                                      (EXPORT_FORM, 'the export HOME=<scratch> line')):
                    if not pattern.search(catalogue):
                        problems.append(f'{label}: the catalogue does not name {form}')
                if not ONE_MESSAGE.search(catalogue):
                    problems.append(f'{label}: the catalogue does not quote the '
                                    f'refusal message, so a reader greps for the '
                                    f'wrong wording and concludes it is not about them')
                if not EXIT_TOOL.search(catalogue):
                    problems.append(f'{label}: the catalogue names the refusal and no '
                                    f'way out, which leaves the reader where the '
                                    f'missing entry left them')

            if not MKTEMP.search(installer):
                problems.append(f'{label}: the installer bullet no longer carries the '
                                f'technique; the fix was to name the escape, not to '
                                f'retire the bullet')
            if not EXIT_TOOL.search(installer) or not RETURN_TOOL.search(installer):
                problems.append(f'{label}: the installer bullet names no escape '
                                f'(ExitWorktree out, EnterWorktree back)')
            elif not KEEP_ACTION.search(installer):
                problems.append(f'{label}: the installer bullet names ExitWorktree '
                                f'without action "keep", the action that removes '
                                f'nothing')
            if not ABSOLUTE_PATH.search(installer):
                problems.append(f'{label}: the installer bullet does not say the '
                                f"worktree's copy is invoked by absolute path, so the "
                                f"run verifies the main checkout's installer instead")
            recipe = RECIPE.search(installer)
            if not recipe:
                problems.append(f'{label}: the installer bullet carries no bash recipe, '
                                f'so the runnable form this rule exists to supply is '
                                f'described and never given')
            else:
                for pattern, pin in RECIPE_PINS:
                    if not pattern.search(recipe.group(1)):
                        problems.append(f'{label}: the recipe is missing {pin}')
            if not WRAPPER_REJECTED.search(installer):
                problems.append(f'{label}: the installer bullet does not record the '
                                f'wrapper script as rejected, and the guard accepts '
                                f'it, so a reader finds it and takes it as the answer')

    if problems:
        print(f'{len(problems)} problem(s):')
        for problem in problems:
            print(f'  {problem}')
        return 1

    print(f'ok: {checked} skill copy(ies) across {len(PROFILES)} profiles, '
          f'{len(SKILLS)} skill(s)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
