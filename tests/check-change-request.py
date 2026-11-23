#!/usr/bin/env python3
import importlib.util
import json
import os
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = (
    "larrabeedylan_work_darwin",
    "larrabeedylan_work_linux",
    "larrabeedylan_home_darwin",
)

REAL = "https://github.com/owner/repo/pull/7"
OTHER = "https://github.com/elsewhere/other/pull/99"
FIXTURE = "https://github.com/o/r/pull/9"
SLUG = "owner/repo"


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
]


def run(profile, directory):
    module = load(profile)
    module.remote_slug = lambda cwd=None: SLUG
    failures = []
    for index, (label, lines, cached, want) in enumerate(CASES):
        path = transcript(directory, "%s-%d" % (profile, index), lines)
        state = {"change_request": cached} if cached else {}
        got = module.change_request_for(path, state, REPO)
        if got != want:
            failures.append("  %s\n      want %r\n      got  %r" % (label, want, got))
            continue
        if want and state.get("change_request") != want:
            failures.append(
                "  %s\n      cache not updated: %r" % (label, state.get("change_request"))
            )
    return failures


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "rules":
        print("change_request_for resolution order, checked over every profile copy:")
        print("  1. the forge's own answer   — an html_url/web_url key in a tool result")
        print("  2. prose carrying the session remote's owner/repo")
        print("  3. the value cached in the session state")
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
