#!/usr/bin/env python3

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "profiles", "check-transform.py")
WORK = "profiles/larrabeedylan_work_darwin/.claude"
HOME = "profiles/larrabeedylan_home_darwin/.claude"

GUARDED_CONTENT = "skills/AGENTS.md"
GUARDED_PRESENCE = "scripts/gitlab-api.sh"
GUARDED_ABSENT_SOURCE = "scripts/github-api.sh"
PLAIN = "skills/plain-skill/SKILL.md"
NO_SOURCE = "skills/absent-skill/SKILL.md"

RULES = """
check-transform.py's derive guard: an allowlist entry records that home_darwin's
copy is deliberately NOT transform(work_darwin), so deriving such a path destroys
the divergence the entry exists for -- and check then passes BECAUSE it did.

the allowlist lookup, driven directly:

  an entry in TRANSFORM_EXEMPT        answers with that table and its recorded reason
  an entry in PRESENCE_EXEMPT         answers too: the ABSENCE of a home copy is
                                      itself the allowlisted fact, and --apply
                                      creates the file that must not exist
  a path in neither                   answers with nothing
  WORK_PAIR_EXEMPT                    is never consulted. derive only ever writes
                                      home_darwin; that table governs work_darwin
                                      against work_linux

the N-of-M count, driven directly:

  every declared entry diverging      reports N == M and names nothing
  one entry that stopped diverging    reports N == M-1 and NAMES it with its table.
                                      the original bug's only signal was this count
                                      silently dropping by one, which reads as an
                                      improvement rather than a loss
  a presence-shaped exemption         is attributed to PRESENCE_EXEMPT, a differing
                                      one to TRANSFORM_EXEMPT

the real script over a throwaway profile tree:

  derive <guarded> --apply            exits non-zero, writes NOTHING, and names the
                                      path, the table and the recorded reason
  derive <guarded>                    still prints to stdout and writes nothing. the
                                      refusal is gated on --apply, because reading the
                                      derived text is how you decide whether an entry
                                      should be retired
  derive <plain> --apply              unchanged: writes transform(source)
  derive <guarded> --apply --force    overwrites, and says what it replaced -- the
                                      differing-line count and the reason discarded
  derive <presence entry> --apply     refused; the home copy still does not exist
  --force on a presence entry         creates the home copy and says so, INCLUDING its
                                      parent directory. retiring a presence entry is
                                      the one case where the home side has no such
                                      directory at all, and the single write site used
                                      to raise FileNotFoundError there -- a latent bug
                                      the real repo hides, since every allowlisted
                                      path it carries sits in a directory that exists
  derive <no source> --apply          unchanged: exits non-zero with "cannot read"
  a guarded path absent from work     reports the ALLOWLIST reason, not "cannot read".
                                      the guard runs before the source read, or the
                                      message is true and silent about the real reason

the real repository, read-only:

  check                               exits 0 and every declared allowlist entry is
                                      still diverging. this is the assertion that
                                      would have caught the original flatten: an
                                      entry that stops diverging means either the
                                      file was overwritten or the entry is stale
  rules                               names both guarded tables, the --force override
                                      and the WORK_PAIR_EXEMPT exclusion
  derive --help                       lists --force
"""


class Suite:
    def __init__(self):
        self.failures = 0
        self.checked = 0

    def ok(self, label, condition, detail=""):
        self.checked += 1
        if not condition:
            self.failures += 1
            print("FAIL  %s" % label)
            if detail != "":
                print("        %s" % detail)

    def report(self, name):
        if self.failures:
            print("%s: %d of %d checks failed" % (name, self.failures, self.checked))
            return 1
        print("%s: %d checks passed" % (name, self.checked))
        return 0


def load():
    spec = importlib.util.spec_from_file_location("check_transform", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return None


WORK_GUARDED = "Open a merge request on GitLab, then read gitlab-api.sh.\n" * 4
HOME_GUARDED = "The home copy documents github-api.sh by hand, per forge.\n" * 9
WORK_PLAIN = "An MR on GitLab needs the MR id.\n"
HOME_PLAIN = "stale\n"
WORK_PRESENCE = "#!/usr/bin/env bash\n# the GitLab adapter\n"


def build(root):
    shutil.rmtree(os.path.join(root, "profiles"), ignore_errors=True)
    os.makedirs(os.path.join(root, "profiles"), exist_ok=True)
    shutil.copy(SCRIPT, os.path.join(root, "profiles", "check-transform.py"))
    write(os.path.join(root, WORK, GUARDED_CONTENT), WORK_GUARDED)
    write(os.path.join(root, HOME, GUARDED_CONTENT), HOME_GUARDED)
    write(os.path.join(root, WORK, PLAIN), WORK_PLAIN)
    write(os.path.join(root, HOME, PLAIN), HOME_PLAIN)
    write(os.path.join(root, WORK, GUARDED_PRESENCE), WORK_PRESENCE)


def run(root, *args):
    result = subprocess.run(
        [sys.executable, os.path.join(root, "profiles", "check-transform.py")] + list(args),
        capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def unit_checks(suite, module):
    guarded = module.allowlisted_for_derive(GUARDED_CONTENT)
    suite.ok("a TRANSFORM_EXEMPT path answers with its table",
             len(guarded) == 1 and guarded[0][0] == "TRANSFORM_EXEMPT", guarded)
    suite.ok("and carries the recorded reason",
             len(guarded) == 1 and guarded[0][1] == module.TRANSFORM_EXEMPT[GUARDED_CONTENT],
             guarded)

    presence = module.allowlisted_for_derive(GUARDED_PRESENCE)
    suite.ok("a PRESENCE_EXEMPT path answers with its table",
             len(presence) == 1 and presence[0][0] == "PRESENCE_EXEMPT", presence)

    suite.ok("a path in neither answers with nothing",
             module.allowlisted_for_derive("skills/aidr/SKILL.md") == [], "aidr")

    names = [name for name, _table in module.DERIVE_GUARDS]
    suite.ok("WORK_PAIR_EXEMPT is not a derive guard",
             "WORK_PAIR_EXEMPT" not in names, names)
    suite.ok("the derive guards are exactly the two home-facing allowlists",
             names == ["TRANSFORM_EXEMPT", "PRESENCE_EXEMPT"], names)
    suite.ok("every declared allowlist is counted by the N-of-M report",
             sorted(n for n, _t in module.ALL_ALLOWLISTS)
             == sorted(["WORK_PAIR_EXEMPT", "TRANSFORM_EXEMPT", "PRESENCE_EXEMPT"]),
             [n for n, _t in module.ALL_ALLOWLISTS])


def count_checks(suite, module):
    work = [(rel, "differs", None, 1) for rel in module.WORK_PAIR_EXEMPT]
    content = [(rel, "differs", None, 1) for rel in module.TRANSFORM_EXEMPT]
    presence = [(rel, "missing from the right-hand profile", None, 0)
                for rel in module.PRESENCE_EXEMPT]
    declared = (len(module.WORK_PAIR_EXEMPT) + len(module.TRANSFORM_EXEMPT)
                + len(module.PRESENCE_EXEMPT))

    diverging, total, settled = module.allowlist_status(work, content + presence)
    suite.ok("every entry firing reports N == M",
             diverging == total == declared, (diverging, total, declared))
    suite.ok("and names nothing as settled", settled == [], settled)

    dropped = content[0][0]
    diverging, total, settled = module.allowlist_status(work, content[1:] + presence)
    suite.ok("an entry that stopped diverging drops N by one",
             diverging == declared - 1 and total == declared, (diverging, total))
    suite.ok("and is named with its table",
             settled == [("TRANSFORM_EXEMPT", dropped)], settled)

    dropped_presence = presence[0][0]
    diverging, total, settled = module.allowlist_status(work, content + presence[1:])
    suite.ok("a settled presence entry is attributed to PRESENCE_EXEMPT",
             settled == [("PRESENCE_EXEMPT", dropped_presence)], settled)


def end_to_end(suite, root):
    build(root)
    target = os.path.join(root, HOME, GUARDED_CONTENT)
    before = read(target)

    code, out, err = run(root, "derive", GUARDED_CONTENT, "--apply")
    suite.ok("the refusal exits non-zero", code != 0, code)
    suite.ok("the refusal writes nothing", read(target) == before,
             "target changed")
    suite.ok("the refusal names the path", GUARDED_CONTENT in err, err)
    suite.ok("the refusal names the allowlist", "TRANSFORM_EXEMPT" in err, err)
    suite.ok("the refusal quotes the recorded reason",
             "the per-profile skill inventory" in err, err)
    suite.ok("the refusal does not claim to have written",
             "wrote" not in out, out)

    code, out, err = run(root, "derive", GUARDED_CONTENT)
    suite.ok("the bare form still exits 0", code == 0, err)
    suite.ok("the bare form prints the derived text",
             "pull request" in out and "GitHub" in out, out[:120])
    suite.ok("the bare form writes nothing", read(target) == before, "target changed")

    plain_target = os.path.join(root, HOME, PLAIN)
    code, out, err = run(root, "derive", PLAIN, "--apply")
    suite.ok("a plain path is unchanged: exits 0", code == 0, err)
    suite.ok("a plain path is unchanged: writes the derived text",
             read(plain_target) == "A PR on GitHub needs the PR id.\n", read(plain_target))

    presence_target = os.path.join(root, HOME, GUARDED_PRESENCE)
    code, out, err = run(root, "derive", GUARDED_PRESENCE, "--apply")
    suite.ok("a presence entry is refused", code != 0, code)
    suite.ok("and the home copy still does not exist",
             not os.path.exists(presence_target), presence_target)
    suite.ok("and PRESENCE_EXEMPT is named", "PRESENCE_EXEMPT" in err, err)

    code, out, err = run(root, "derive", NO_SOURCE, "--apply")
    suite.ok("an unreadable non-allowlisted source still exits non-zero", code != 0, code)
    suite.ok("and still says cannot read", "cannot read" in err, err)

    code, out, err = run(root, "derive", GUARDED_ABSENT_SOURCE, "--apply")
    suite.ok("a guarded path absent from work_darwin is refused", code != 0, code)
    suite.ok("and reports the allowlist reason rather than cannot read",
             "PRESENCE_EXEMPT" in err and "cannot read" not in err, err)

    build(root)
    before = read(target)
    code, out, err = run(root, "derive", GUARDED_CONTENT, "--apply", "--force")
    suite.ok("--force exits 0", code == 0, err)
    suite.ok("--force overwrites the home copy", read(target) != before, "target unchanged")
    suite.ok("--force wrote the derived text",
             read(target) == WORK_GUARDED.replace("merge request", "pull request")
             .replace("GitLab", "GitHub").replace("gitlab-api.sh", "github-api.sh"),
             read(target))
    suite.ok("--force names the target it replaced",
             GUARDED_CONTENT in out, out)
    suite.ok("--force reports a differing-line count",
             re.search(r"\(\d+ differing lines\)", out) is not None, out)
    suite.ok("--force names the reason it discarded",
             "discarding TRANSFORM_EXEMPT" in out, out)

    build(root)
    code, out, err = run(root, "derive", GUARDED_PRESENCE, "--apply", "--force")
    suite.ok("--force on a presence entry exits 0", code == 0, err)
    suite.ok("--force on a presence entry creates the home copy",
             os.path.exists(presence_target), presence_target)
    suite.ok("and says it is creating one rather than replacing",
             "has no home copy" in out, out)


def real_repo(suite):
    result = subprocess.run([sys.executable, SCRIPT, "check", "--quiet"],
                            capture_output=True, text=True)
    suite.ok("check exits 0 on the real repository", result.returncode == 0,
             result.stdout[-400:] + result.stderr[-400:])

    match = re.search(r"(\d+) of (\d+) allowlist entries still diverging",
                      result.stdout)
    suite.ok("check reports the N-of-M count", match is not None,
             result.stdout[-400:])
    if match is not None:
        diverging, declared = int(match.group(1)), int(match.group(2))
        suite.ok("every declared allowlist entry is still diverging",
                 diverging == declared,
                 "%d of %d -- an entry that stopped diverging was either overwritten "
                 "or is stale; check's output names it" % (diverging, declared))

    result = subprocess.run([sys.executable, SCRIPT, "rules"],
                            capture_output=True, text=True)
    suite.ok("rules exits 0", result.returncode == 0, result.stderr)
    suite.ok("rules says derive --apply refuses a guarded path",
             "derive --apply refuses" in result.stdout, result.stdout[-300:])
    for name in ("TRANSFORM_EXEMPT", "PRESENCE_EXEMPT"):
        suite.ok("rules names %s as a derive guard" % name,
                 name in result.stdout, name)
    suite.ok("rules names the --force override",
             "--force overrides" in result.stdout, result.stdout[-300:])
    suite.ok("rules states the WORK_PAIR_EXEMPT exclusion",
             "WORK_PAIR_EXEMPT is not consulted" in result.stdout,
             result.stdout[-300:])

    result = subprocess.run([sys.executable, SCRIPT, "derive", "--help"],
                            capture_output=True, text=True)
    suite.ok("derive --help lists --force", "--force" in result.stdout,
             result.stdout)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "rules":
        print(RULES.strip())
        return 0

    suite = Suite()

    module = load()
    for name in ("allowlisted_for_derive", "allowlist_status", "report_forced_overwrite",
                 "DERIVE_GUARDS", "ALL_ALLOWLISTS"):
        suite.ok("%s exists" % name, hasattr(module, name))
    if suite.failures:
        return suite.report("check-transform-derive")

    unit_checks(suite, module)
    count_checks(suite, module)

    with tempfile.TemporaryDirectory() as root:
        end_to_end(suite, root)

    real_repo(suite)

    return suite.report("check-transform-derive")


if __name__ == "__main__":
    sys.exit(main())
