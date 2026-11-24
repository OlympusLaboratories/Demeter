#!/usr/bin/env python3
import importlib.util
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = (
    "larrabeedylan_work_darwin",
    "larrabeedylan_work_linux",
    "larrabeedylan_home_darwin",
)

LINK = "https://github.com/owner/repo/pull/7"
OTHER_LINK = "https://github.com/owner/repo/pull/8"
PAGE = "https://artifacts.example.dev/abc123"
DOCS = "https://docs.example.dev/runbooks/deploys"


def load(profile):
    path = os.path.join(REPO, "profiles", profile, ".claude", "hooks", "notify.py")
    spec = importlib.util.spec_from_file_location("body_" + profile, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.log = lambda message: None
    return module


NAMED = (
    "opened PR #7 for review",
    "opened MR #7 for review",
    "opened PR7 for review",
    "the PR is green",
    "the MR is green",
    "pr #7 is green",
    "the pull request is green",
    "the merge request is green",
    "two pull requests are waiting",
    "pull request #7 is green",
    "shipped it, see " + LINK,
)

UNNAMED = (
    "Migrated the 14 cron jobs to the new scheduler; tests green.",
    "Can't push the release branch - the forge token expired.",
    "3 of 7 services migrated, no failures so far.",
    "Published the plan at " + PAGE,
    "Reindexing meter_reads: picked the online backfill.",
    "Mr Smith approved the design doc.",
    "Priced it at 7 pr units, whatever those are.",
    "Shipped release #3 to staging.",
    "Closed issue #412 as a duplicate.",
    "",
)


def case_a_named_change_request_gets_the_link(module):
    module.change_request_for = lambda *a, **k: LINK
    for body in NAMED:
        got, appended = module.append_change_request(body, None, {}, REPO)
        if LINK in body:
            if appended:
                return "%r already carried the link and got a second copy" % body
            continue
        if not appended or LINK not in got:
            return "%r names a change request but got no link" % body
    return None


def case_an_unnamed_body_is_left_alone(module):
    module.change_request_for = lambda *a, **k: LINK
    for body in UNNAMED:
        got, appended = module.append_change_request(body, None, {}, REPO)
        if appended or got != body:
            return "%r names no change request but was given %r" % (body, got)
    return None


def case_an_unrelated_url_no_longer_suppresses_the_link(module):
    module.change_request_for = lambda *a, **k: LINK
    body = "Plan approved and PR #7 is green, page at " + PAGE
    got, appended = module.append_change_request(body, None, {}, REPO)
    if not appended or LINK not in got:
        return "a published-page url cost the user the change request link"
    body = "PR #7 is green; runbook at " + DOCS
    got, appended = module.append_change_request(body, None, {}, REPO)
    if not appended or LINK not in got:
        return "a docs url cost the user the change request link"
    return None


def case_a_change_request_url_still_suppresses_the_link(module):
    module.change_request_for = lambda *a, **k: OTHER_LINK
    body = "shipped " + LINK
    got, appended = module.append_change_request(body, None, {}, REPO)
    if appended or got != body:
        return "a body already linking a change request got a second, different one"
    return None


def case_an_unresolvable_link_appends_nothing(module):
    module.change_request_for = lambda *a, **k: None
    body = "opened PR #7 for review"
    got, appended = module.append_change_request(body, None, {}, REPO)
    if appended or got != body:
        return "nothing resolved but something was appended: %r" % got
    return None


def case_a_dropped_url_is_restored(module):
    source = "Opened the change request at %s and the pipeline is green" % LINK
    line = "Opened the change request and the pipeline is green"
    got = module.restore_urls(line, source)
    if LINK not in got:
        return "the summarizer dropped the url and nothing put it back"
    return None


def case_a_mangled_url_does_not_replace_the_real_one(module):
    source = "Opened %s for review" % LINK
    line = "Opened https://github.com/owner/repo/pull/70 for review"
    got = module.restore_urls(line, source)
    if LINK not in module.urls_in(got):
        return ("a mangled number stood in for the url the input carried: %r"
                % module.urls_in(got))
    return None


def case_a_prefix_mangle_is_still_restored(module):
    for real, emitted in (
        ("https://github.com/owner/repo/pull/7",
         "https://github.com/owner/repo/pull/70"),
        ("https://github.com/owner/repo/pull/1",
         "https://github.com/owner/repo/pull/123"),
    ):
        got = module.restore_urls("Opened %s" % emitted, "Opened %s" % real)
        if real not in module.urls_in(got):
            return ("%s is a prefix of %s and was never restored: %r"
                    % (real, emitted, module.urls_in(got)))
    return None


def case_a_truncated_url_is_never_manufactured(module):
    whole = "https://github.com/owner/repo/pull/1234"
    limit = module.SUMMARY_MAX_INPUT
    pad = "x " * ((limit * 2 // 3 - 20) // 2)
    body = pad + whole + " tail " + ("y " * 2000)
    got = module.restore_urls("Run finished.", module.strip_markdown(body))
    for url in module.urls_in(got):
        if url != whole and whole.startswith(url):
            return "a truncated fragment of the url was appended: %r" % url
    return None


def case_the_append_is_capped(module):
    source = " ".join("https://example.dev/p/%d" % i for i in range(12))
    got = module.restore_urls("short summary.", source)
    if len(module.urls_in(got)) > module.RESTORE_URL_MAX:
        return ("restored %d urls against a cap of %d"
                % (len(module.urls_in(got)), module.RESTORE_URL_MAX))
    return None


def case_a_surviving_url_is_not_duplicated(module):
    source = "Opened %s for review" % LINK
    line = "Opened %s for review" % LINK
    got = module.restore_urls(line, source)
    if got.count(LINK) != 1:
        return "a url the summarizer kept was appended a second time: %r" % got
    return None


def case_the_change_request_url_is_never_the_one_capped(module):
    source = "plan %s, docs %s, change request %s" % (PAGE, DOCS, LINK)
    got = module.restore_urls("nothing but prose", source)
    restored = module.urls_in(got)
    if LINK not in restored:
        return ("the change request link was dropped by the cap while %r"
                " survived" % restored)
    if len(restored) > module.RESTORE_URL_MAX:
        return "restored %d urls against a cap of %d" % (
            len(restored), module.RESTORE_URL_MAX)
    return None


def case_the_trim_cannot_be_what_drops_a_url(module):
    settings = {"max_words": 6, "timeout": 1}
    module.summarizer_path = lambda s: "/usr/bin/true"
    module.summarizer_env = lambda binary: {}
    module.summarizer_cwd = lambda: None
    module.summarizer_settings = lambda: None

    class Done(object):
        returncode = 0
        stdout = "one two three four five six seven eight %s" % LINK
        stderr = ""

    real_run = module.subprocess.run
    module.subprocess.run = lambda *a, **k: Done()
    try:
        line, problem = module.summarize(
            "body naming " + LINK, {"summarize": settings})
    finally:
        module.subprocess.run = real_run
    if problem:
        return "the stubbed summarizer reported %s" % problem
    if LINK not in module.urls_in(line):
        return "the word trim removed the url: %r" % line
    return None


def case_no_url_input_is_unchanged(module):
    line = "Migrated the cron jobs; tests green."
    if module.restore_urls(line, "Migrated the cron jobs; tests green.") != line:
        return "a body with no urls was altered"
    return None


CASES = (
    ("a body naming a change request is given its link",
     case_a_named_change_request_gets_the_link),
    ("a body naming no change request is left alone",
     case_an_unnamed_body_is_left_alone),
    ("a published page or docs url no longer suppresses the link",
     case_an_unrelated_url_no_longer_suppresses_the_link),
    ("a body already linking a change request is left alone",
     case_a_change_request_url_still_suppresses_the_link),
    ("a body naming one that cannot be resolved gets nothing",
     case_an_unresolvable_link_appends_nothing),
    ("a url the summarizer dropped is restored",
     case_a_dropped_url_is_restored),
    ("a url the summarizer mangled does not stand in for the real one",
     case_a_mangled_url_does_not_replace_the_real_one),
    ("a real url that is a prefix of the mangled one is still restored",
     case_a_prefix_mangle_is_still_restored),
    ("the window's truncation never manufactures a url to append",
     case_a_truncated_url_is_never_manufactured),
    ("the restore is capped so it cannot blow the body budget",
     case_the_append_is_capped),
    ("a url the summarizer kept is not duplicated",
     case_a_surviving_url_is_not_duplicated),
    ("the change request link is never the url the cap drops",
     case_the_change_request_url_is_never_the_one_capped),
    ("the word trim is never what removes a url",
     case_the_trim_cannot_be_what_drops_a_url),
    ("a body carrying no url is returned unchanged",
     case_no_url_input_is_unchanged),
)


def run(profile):
    failures = []
    for label, case in CASES:
        module = load(profile)
        try:
            problem = case(module)
        except Exception as error:
            problem = "raised %r" % (error,)
        if problem:
            failures.append("  %s\n      %s" % (label, problem))
    return failures


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "rules":
        print("what reaches the notification body, over every profile copy:")
        print()
        print("  The hook appends the change request's link because a rule telling a")
        print("  skill to include it is a rule a model forgets. Two conditions, not")
        print("  one: the body must actually NAME a change request, and it must not")
        print("  already carry a change request's url.")
        print()
        print("  Naming is PR/MR with a number, a bare #number, or pull/merge")
        print("  request(s). A body about anything else -- a migration, an expired")
        print("  token, a published plan -- gets no link, because the user's rule is")
        print("  about messages that mention a change request.")
        print()
        print("  The suppression is specific. It used to be `\"http\" in body`, so a")
        print("  published artifact url or a docs link cost the user the one link on")
        print("  the screen they could act on. Only a change-request url suppresses.")
        print()
        print("  The summarizer is not trusted with a url. SUMMARY_PROMPT asks the")
        print("  model to reproduce one verbatim and the word trim can cut one off the")
        print("  end of the line; neither is a guarantee. So every url the summarizer")
        print("  was given is re-extracted from its answer, and one that did not come")
        print("  back is re-appended AFTER the trim -- the trim can never be what")
        print("  removes it. A mangled url is left where it is and the real one added")
        print("  beside it, because dropping text the model produced is the riskier")
        print("  repair; a url that survived is not duplicated.")
        print()
        print("cases:")
        for label, _ in CASES:
            print("  %s" % label)
        return 0

    broken = {}
    for profile in PROFILES:
        failures = run(profile)
        if failures:
            broken[profile] = failures

    print("notification body")
    print()
    for profile in PROFILES:
        if profile in broken:
            print("  fail — %s" % profile)
            for line in broken[profile]:
                print(line)
        else:
            print("  ok   — %s (%d cases)" % (profile, len(CASES)))
    print()
    if broken:
        print("failed")
        return 1
    print("passed (%d checks)" % (len(CASES) * len(PROFILES)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
