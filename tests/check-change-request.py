#!/usr/bin/env python3
import importlib.util
import json
import os
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = (
    "larrabeedylan_work_darwin",
    "larrabeedylan_work_linux",
    "larrabeedylan_home_darwin",
)

REAL = "https://github.com/owner/repo/pull/7"
BASE = "https://github.com/owner/repo/pull/6"
OTHER = "https://github.com/elsewhere/other/pull/99"
SECOND = "https://github.com/elsewhere/other/pull/100"
FIXTURE = "https://github.com/o/r/pull/9"
SLUG = "owner/repo"
BRANCH = "dylan/OLY-21"


def load(profile):
    path = os.path.join(REPO, "profiles", profile, ".claude", "hooks", "notify.py")
    spec = importlib.util.spec_from_file_location("notify_" + profile, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def transcript(directory, name, lines):
    path = os.path.join(directory, name + ".jsonl")
    with open(path, "w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(json.dumps({"type": "assistant", "text": line}) + "\n")
    return path


def answered(url):
    return 'tool result: {"number": 7, "html_url": "%s", "draft": false}' % url


def answered_escaped(url):
    return '{"content":"{\\"number\\": 7, \\"html_url\\": \\"%s\\"}"}' % url


def opened_from(url, branch):
    return ('tool result: {"number": 7, "html_url": "%s", "title": "t",'
            ' "draft": false, "head": "%s", "base": "main"}' % (url, branch))


def answered_with_state(url, state, branch="somebody/else"):
    return ('tool result: {"title": "t", "description": "d", "state": "%s",'
            ' "author": "a", "web_url": "%s", "source_branch": "%s",'
            ' "target_branch": "main"}' % (state, url, branch))


CASES = [
    (
        "the forge's answer wins over a later prose url",
        [answered(REAL), "merged " + OTHER, "and also " + OTHER],
        None,
        REAL,
    ),
    (
        "the forge's answer survives backslash escaping",
        [answered_escaped(REAL), "merged " + OTHER],
        None,
        REAL,
    ),
    (
        "the forge's answer beats a stale cache",
        [answered(REAL)],
        OTHER,
        REAL,
    ),
    (
        "prose carrying the session remote is the fallback",
        ["opened " + REAL + " for review"],
        None,
        REAL,
    ),
    (
        "prose from another repository is not the session's link",
        ["see " + OTHER + " for context"],
        None,
        None,
    ),
    (
        "a fixture url never answers",
        ["testing with " + FIXTURE],
        None,
        None,
    ),
    (
        "the cache answers only when the scan finds nothing",
        ["nothing resembling a change request here"],
        OTHER,
        OTHER,
    ),
    (
        "a scan that finds a newer url replaces the cache",
        [answered(REAL)],
        OTHER,
        REAL,
    ),
    (
        "the record opened from the session's branch beats a later entry",
        [opened_from(REAL, BRANCH), answered(BASE)],
        None,
        REAL,
    ),
    (
        "the session's remote filters another repository out of the forge's answer",
        [answered(REAL), answered(OTHER)],
        None,
        REAL,
    ),
    (
        "a closed change request is never offered",
        [answered_with_state(REAL, "closed")],
        None,
        None,
    ),
    (
        "a merged change request is never offered",
        [answered_with_state(REAL, "merged")],
        None,
        None,
    ),
    (
        "a record carrying no state is not treated as closed",
        [opened_from(REAL, "somebody/else")],
        None,
        REAL,
    ),
    (
        "a cross-repository answer still wins when it is the only one",
        [answered(OTHER)],
        None,
        OTHER,
    ),
    (
        "a listing of other repositories' change requests answers nothing",
        [answered(OTHER), answered(SECOND)],
        None,
        None,
    ),
    (
        "the cache cannot resurrect a change request the scans rejected as closed",
        [answered_with_state(REAL, "merged")],
        REAL,
        None,
    ),
    (
        "a cached url the transcript says nothing about still answers",
        ["nothing resembling a change request here"],
        REAL,
        REAL,
    ),
    (
        "a cache older than the threshold is not an answer",
        ["nothing resembling a change request here"],
        {"url": OTHER, "at": 0},
        None,
    ),
    (
        "a cache inside the threshold still answers",
        ["nothing resembling a change request here"],
        {"url": OTHER, "at": time.time()},
        OTHER,
    ),
]


def case_branch_beats_a_nearer_slug_match(module, directory, profile):
    # The tail scan reads the last TAIL_CHUNK bytes first and stops on the
    # first answer, so a per-chunk preference order silently degrades to
    # "preferred within the tail". Push the branch-tagged record outside the
    # tail and a slug-only record inside it.
    path = os.path.join(directory, "%s-crosschunk.jsonl" % profile)
    filler = json.dumps({"type": "assistant", "text": "filler " + "z" * 180})
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "assistant", "text": opened_from(
            REAL, BRANCH)}) + "\n")
        written = 0
        while written < module.TAIL_CHUNK * 2:
            handle.write(filler + "\n")
            written += len(filler) + 1
        handle.write(json.dumps({"type": "assistant", "text": answered(
            BASE)}) + "\n")
    got = module.change_request_for(path, {}, REPO)
    if got != REAL:
        return ("the branch-tagged record outside the tail chunk lost to a"
                " nearer slug match\n      want %r\n      got  %r" % (REAL, got))
    return None


def run(profile, directory):
    module = load(profile)
    module.remote_slug = lambda cwd=None: SLUG
    module.branch_label = lambda cwd=None: BRANCH
    module.log = lambda message: None
    failures = []
    for index, (label, lines, cached, want) in enumerate(CASES):
        path = transcript(directory, "%s-%d" % (profile, index), lines)
        state = {"change_request": cached} if cached else {}
        got = module.change_request_for(path, state, REPO)
        if got != want:
            failures.append("  %s\n      want %r\n      got  %r" % (label, want, got))
            continue
        if want and module.cached_change_request(state) != want:
            failures.append(
                "  %s\n      cache does not read back: %r"
                % (label, state.get("change_request"))
            )
            continue
        if want and got == want and not cached:
            stored = state.get("change_request")
            if not isinstance(stored, dict):
                failures.append(
                    "  %s\n      the writer stored %r, not a {url, at} record,"
                    " so nothing ever ages out" % (label, stored))
            elif not isinstance(stored.get("at"), (int, float)):
                failures.append(
                    "  %s\n      the stored record carries at=%r, so the ttl"
                    " cannot apply" % (label, stored.get("at")))
    problem = case_branch_beats_a_nearer_slug_match(module, directory, profile)
    if problem:
        failures.append("  the session's branch wins across the whole"
                        " transcript, not just the tail\n      %s" % problem)
    return failures


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "rules":
        print("change_request_for resolution order, checked over every profile copy:")
        print("  1. the forge's own answer   — an html_url/web_url key in a tool result,")
        print("     preferring the record opened from the session's current branch, then")
        print("     one carrying the session remote's owner/repo, then a lone")
        print("     cross-repository answer; a listing matching neither answers nothing")
        print("  2. prose carrying the session remote's owner/repo")
        print("  3. the value cached in the session state, until it ages out")
        print()
        print("a record the transcript shows as closed or merged is dropped at every")
        print("tier, including the prose scan that would otherwise re-find its url")
        print("inside the very answer that declared it closed. an absent state is")
        print("unknown, not closed, so the fallback tiers keep working.")
        print()
        print("cases:")
        for label, _, _, want in CASES:
            print("  %-56s -> %s" % (label, want or "no link"))
        return 0

    total = 0
    broken = {}
    with tempfile.TemporaryDirectory() as directory:
        for profile in PROFILES:
            failures = run(profile, directory)
            total += len(CASES)
            if failures:
                broken[profile] = failures

    print("change request link")
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
    print("passed (%d checks)" % total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
