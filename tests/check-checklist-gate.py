#!/usr/bin/env python3
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = (
    "larrabeedylan_work_darwin",
    "larrabeedylan_work_linux",
    "larrabeedylan_home_darwin",
)

SESSION = "77777777-8888-9999-aaaa-bbbbbbbbbbbb"
PAGE = "https://artifacts.example.dev/run123"
OTHER = "https://artifacts.example.dev/run456"

OVERAGE = 90 * 60

BRANCH = "dylan/run-one"
FORK = "dylan/run-two"
THIRD = "dylan/run-three"
DEFAULT = "main"
WORKTREE = "/tmp/checklist-gate/worktrees/run-one"
ELSEWHERE = "/tmp/checklist-gate/worktrees/run-two"
AGAIN = "/tmp/checklist-gate/worktrees/run-three"
MAIN_CHECKOUT = "/tmp/checklist-gate/main"
NOWHERE = "/tmp/checklist-gate/outside-a-repo"
DETACHED = "/tmp/checklist-gate/detached"

BRANCHES = {
    WORKTREE: BRANCH,
    ELSEWHERE: FORK,
    AGAIN: THIRD,
    MAIN_CHECKOUT: DEFAULT,
    NOWHERE: None,
    DETACHED: None,
}

RULES = """
the run checklist gate, checked over every profile copy:

  run-checklist.py writes the marker
    publish with outstanding items        records checklist_pending in the session state
    tick with outstanding items           rewrites it, resetting the stop count
    the marker                            carries the run's branch
    the marker                            holds one record per page, keyed by it
    a write from a second branch          records it beside the first
    a flat marker from the old version    is upgraded, not stranded
    every item done or skipped            drops that page's record
    the last page going                   drops the marker and the spent fork
    no session id in the environment      writes nothing, and does not fail

  notify.py holds the turn end
    outstanding items, nothing in flight  blocks the first Stop and names the open ids
    the held Stop                         is not blocked a second time
    stop_hook_active                      never blocks
    an item in flight, stops below 3      does not block, and counts the stop
    an item in flight, 3 stops            blocks as stale
    a tick between stops                  resets the count, so the next Stop passes
    a subagent's Stop                     never blocks
    an event that is not Stop             never blocks
    a marker older than the TTL           is dropped, and does not block
    no marker at all                      never blocks
    the reason given                      names the open items and why it held

  notify.py catches a run that forked to a second branch
    the branch the marker records         never blocks
    a second branch                       blocks once, naming both branches
    the hold                              offers the re-seed and the second page
    the same second branch again          does not block twice
    a third branch                        blocks on its own
    a marker already held for staleness   still blocks on the fork
    a marker with no branch recorded      never blocks
    a session outside a repository        never blocks
    a detached HEAD                       never blocks
    a subagent, stop_hook_active, non-Stop  never block
    a complete or expired marker          never blocks
    a marker re-seeded on the new branch  stops blocking

  notify.py over a run driving several change requests, a page each
    a session on any page's branch        never blocks
    a branch no page tracks               blocks, naming every page and branch
    the hold                              never claims one page describes it
    one turn end                          counts against every page
    both pages stale                      hold once, in one message
    one stalled page                      holds alone, its sibling counted
    a watcher writing to the other page   does not reset this one's count
    so a page nobody writes to            still reaches a stale hold
    an expired page                       is dropped without its live sibling
    every page expired                    drops the marker
    a finished page beside an open one    never blocks on a fork
    a subagent or stop_hook_active        never blocks
    --checklist-status                    names every page, counts them, writes nothing
    a bare clear with any page open       refuses, naming every page
    --force                               drops every page at once

  the escape hatch
    a clear with items still open         refuses, changes nothing, exits non-zero
    --force                               clears, naming the url and the dropped ids
    a clear with no marker                says so, and exits 0
    a clear with no session               exits 0 and says so
    a marker past the TTL                 clears without --force
    an expired marker's duration          is the time since expiry, not its age
    one open item                         agrees: "1 item is still open"
    a clear of any kind                   drops the marker and nothing beside it
    --checklist-status while armed        prints the url, the branch, the open ids
                                         and the count
    --checklist-status on a forked run    says so, names both branches, writes nothing
    --checklist-status while not          exits non-zero
    --checklist-status either way         mutates nothing, TTL drop included
    the hold text                         names --force and --checklist-status
    run-checklist.py arm                  rewrites the marker from the items file
    arm with every item done               drops the marker instead
    arm                                   leaves armed_at, thread and last_kind alone
"""


class Suite:
    def __init__(self):
        self.failures = 0
        self.checked = 0

    def ok(self, label, condition, detail=""):
        self.checked += 1
        if not condition:
            self.failures += 1
            print("  fail — %s" % label)
            if detail:
                print("      %s" % str(detail).strip().replace("\n", "\n      "))


def load_hook(profile, directory):
    path = os.path.join(REPO, "profiles", profile, ".claude", "hooks", "notify.py")
    spec = importlib.util.spec_from_file_location("checklist_" + profile, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sessions = os.path.join(directory, profile, "sessions")
    os.makedirs(sessions, exist_ok=True)
    module.session_path = lambda sid: os.path.join(sessions, (sid or "none") + ".json")
    module.log = lambda message: None
    module.branch_label = lambda cwd: BRANCHES.get(cwd, BRANCH)
    module.default_branch_label = lambda cwd: DEFAULT
    return module, sessions


def marker(**extra):
    base = {
        "url": PAGE,
        "hash": "run123",
        "branch": BRANCH,
        "at": time.time(),
        "stops": 0,
        "verdict": "armed",
        "open": ["arm", "implement"],
        "in_flight": ["implement"],
    }
    base.update(extra)
    return base


def pages(*records):
    return {(record.get("hash") or record.get("url") or record.get("branch")
             or "unpublished"): record for record in records}


def put(sessions, value, session=SESSION, extra=None):
    path = os.path.join(sessions, session + ".json")
    state = {} if value is None else {"checklist_pending": value}
    if extra:
        state.update(extra)
    with open(path, "w") as handle:
        json.dump(state, handle)
    return path


def tracked(state, key=None):
    marker = state.get("checklist_pending") or {}
    if key is not None:
        return marker.get(key, {})
    kept = [value for value in marker.values() if isinstance(value, dict)]
    return kept[0] if len(kept) == 1 else {}


def get(sessions, session=SESSION):
    path = os.path.join(sessions, session + ".json")
    if not os.path.exists(path):
        return {}
    with open(path) as handle:
        return json.load(handle)


def stop(session=SESSION, **extra):
    return dict({"hook_event_name": "Stop", "session_id": session}, **extra)


def check_hook(suite, profile, directory):
    hook, sessions = load_hook(profile, directory)
    tag = profile

    put(sessions, marker(verdict="stalled", in_flight=[]))
    held = hook.checklist_gate(stop())
    suite.ok("%s: a stalled checklist blocks the first Stop" % tag, bool(held), held)
    suite.ok("%s: the reason names the open items" % tag,
             bool(held) and "arm" in held and "implement" in held, held)
    suite.ok("%s: the reason says nothing is in flight" % tag,
             bool(held) and "nothing is in flight" in held, held)
    suite.ok("%s: the reason carries the page url" % tag, bool(held) and PAGE in held, held)
    suite.ok("%s: the hold is recorded" % tag,
             get(sessions).get("checklist_pending", {}).get("held") is not None)
    suite.ok("%s: the held Stop is not blocked twice" % tag,
             hook.checklist_gate(stop()) is None)

    put(sessions, marker(verdict="stalled", in_flight=[]))
    suite.ok("%s: stop_hook_active never blocks" % tag,
             hook.checklist_gate(stop(stop_hook_active=True)) is None)

    put(sessions, marker(verdict="stalled", in_flight=[]))
    suite.ok("%s: a subagent's Stop never blocks" % tag,
             hook.checklist_gate(stop(agent_id="sub-1")) is None)
    suite.ok("%s: a subagent with only agent_type never blocks" % tag,
             hook.checklist_gate(stop(agent_type="Explore")) is None)

    put(sessions, marker(verdict="stalled", in_flight=[]))
    suite.ok("%s: a PreToolUse event never blocks" % tag,
             hook.checklist_gate(dict(stop(), hook_event_name="PreToolUse")) is None)

    put(sessions, marker(stops=0))
    suite.ok("%s: an item in flight does not block at the first Stop" % tag,
             hook.checklist_gate(stop()) is None)
    suite.ok("%s: that Stop was counted" % tag,
             get(sessions)["checklist_pending"]["stops"] == 1,
             get(sessions)["checklist_pending"])
    suite.ok("%s: the second Stop does not block" % tag, hook.checklist_gate(stop()) is None)
    suite.ok("%s: the third Stop does not block" % tag, hook.checklist_gate(stop()) is None)
    suite.ok("%s: three stops have been counted" % tag,
             get(sessions)["checklist_pending"]["stops"] == 3,
             get(sessions)["checklist_pending"])
    stale = hook.checklist_gate(stop())
    suite.ok("%s: a checklist three turn-ends old blocks" % tag, bool(stale), stale)
    suite.ok("%s: the stale reason says so" % tag,
             bool(stale) and "turns ended" in stale, stale)

    put(sessions, marker(stops=hook.CHECKLIST_STALE_STOPS))
    suite.ok("%s: a fresh marker written by a tick clears the count" % tag,
             hook.checklist_gate(stop()) is not None)
    put(sessions, marker(stops=0))
    suite.ok("%s: and the next Stop after that tick passes" % tag,
             hook.checklist_gate(stop()) is None)

    put(sessions, marker(verdict="stalled", in_flight=[],
                         at=time.time() - hook.GATE_TTL - 60))
    suite.ok("%s: a marker past the TTL does not block" % tag,
             hook.checklist_gate(stop()) is None)
    suite.ok("%s: and the stale marker is dropped" % tag,
             "checklist_pending" not in get(sessions), get(sessions))

    put(sessions, None)
    suite.ok("%s: no marker never blocks" % tag, hook.checklist_gate(stop()) is None)
    put(sessions, marker(open=[]))
    suite.ok("%s: a marker with no open items never blocks" % tag,
             hook.checklist_gate(stop()) is None)
    suite.ok("%s: a Stop with no session id never blocks" % tag,
             hook.checklist_gate({"hook_event_name": "Stop", "session_id": ""}) is None)

    put(sessions, marker(verdict="stalled", in_flight=[]))
    held = hook.checklist_gate(stop())
    suite.ok("%s: the hold names --checklist-clear --force" % tag,
             bool(held) and "--checklist-clear --force" in held, held)
    suite.ok("%s: the hold names --checklist-status" % tag,
             bool(held) and "--checklist-status" in held, held)


def check_fork(suite, profile, directory):
    hook, sessions = load_hook(profile, directory)
    tag = profile

    put(sessions, marker())
    suite.ok("%s: the recorded branch does not block" % tag,
             hook.checklist_gate(stop(cwd=WORKTREE)) is None)
    suite.ok("%s: and that Stop was counted as an ordinary one" % tag,
             get(sessions)["checklist_pending"]["stops"] == 1,
             get(sessions)["checklist_pending"])

    put(sessions, marker(branches=[BRANCH, FORK]))
    suite.ok("%s: a stack's own second branch does not block" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE)) is None,
             get(sessions))

    put(sessions, marker(branches=[BRANCH, FORK]))
    held = hook.checklist_gate(stop(cwd=AGAIN))
    suite.ok("%s: a branch outside the stack still blocks" % tag, bool(held), held)
    suite.ok("%s: the hold names every branch the stack covers" % tag,
             bool(held) and BRANCH in held and FORK in held, held)

    put(sessions, marker(branch="", branches=[FORK]))
    suite.ok("%s: branches alone is enough to recognise the run" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE)) is None, get(sessions))

    put(sessions, marker(branch="", branches=[]))
    suite.ok("%s: no branch anywhere is not evidence of a fork" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE)) is None, get(sessions))

    put(sessions, marker())
    forked = hook.checklist_gate(stop(cwd=ELSEWHERE))
    suite.ok("%s: a second branch blocks the Stop" % tag, bool(forked), forked)
    suite.ok("%s: the hold names the checklist's branch" % tag,
             bool(forked) and BRANCH in forked, forked)
    suite.ok("%s: the hold names the branch the session is on" % tag,
             bool(forked) and FORK in forked, forked)
    suite.ok("%s: the hold offers the re-seed" % tag,
             bool(forked) and "re-seed" in forked, forked)
    suite.ok("%s: the hold offers a second checklist" % tag,
             bool(forked) and "second run" in forked, forked)
    suite.ok("%s: the re-seed it offers is an update, not a new link" % tag,
             bool(forked) and "--update" in forked, forked)
    suite.ok("%s: the hold carries the page url" % tag,
             bool(forked) and PAGE in forked, forked)
    suite.ok("%s: the fork is spent outside the marker, where a write cannot wipe it"
             % tag,
             get(sessions).get("checklist_forked") == FORK, get(sessions))
    suite.ok("%s: the spend is not written into the marker" % tag,
             "forked" not in get(sessions)["checklist_pending"],
             get(sessions)["checklist_pending"])
    suite.ok("%s: a fork hold does not spend the stale hold" % tag,
             "held" not in get(sessions)["checklist_pending"],
             get(sessions)["checklist_pending"])
    suite.ok("%s: the same fork does not block twice" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE)) is None)

    put(sessions, marker(), extra={"checklist_forked": FORK})
    suite.ok("%s: and a checklist write between two Stops does not re-arm it" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE)) is None)

    again = hook.checklist_gate(stop(cwd=AGAIN))
    suite.ok("%s: a third branch blocks on its own" % tag, bool(again), again)
    suite.ok("%s: and names the third branch" % tag,
             bool(again) and THIRD in again, again)
    suite.ok("%s: which replaces the spent fork" % tag,
             get(sessions).get("checklist_forked") == THIRD, get(sessions))

    put(sessions, marker())
    suite.ok("%s: the window before the run cuts its branch never blocks" % tag,
             hook.checklist_gate(stop(cwd=MAIN_CHECKOUT)) is None)
    suite.ok("%s: and that Stop is counted rather than held" % tag,
             get(sessions)["checklist_pending"]["stops"] == 1,
             get(sessions)["checklist_pending"])
    suite.ok("%s: nor does it spend a fork" % tag,
             "checklist_forked" not in get(sessions), get(sessions))

    put(sessions, marker(open=["verify", "close"], in_flight=["verify"]))
    suite.ok("%s: leaving the worktree after the merge never blocks" % tag,
             hook.checklist_gate(stop(cwd=MAIN_CHECKOUT)) is None)

    put(sessions, marker(branch=DEFAULT))
    suite.ok("%s: a default-branch run escalating to a feature branch still blocks"
             % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE)) is not None)

    put(sessions, marker(held=time.time()))
    suite.ok("%s: a fork blocks even on a marker already held for staleness" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE)) is not None)

    put(sessions, marker(branch=""))
    suite.ok("%s: a marker with no branch never blocks" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE)) is None)

    put(sessions, marker())
    suite.ok("%s: a session outside a repository never blocks" % tag,
             hook.checklist_gate(stop(cwd=NOWHERE)) is None)
    put(sessions, marker())
    suite.ok("%s: a detached HEAD never blocks" % tag,
             hook.checklist_gate(stop(cwd=DETACHED)) is None)

    put(sessions, marker())
    suite.ok("%s: a subagent's Stop never blocks on a fork" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE, agent_id="sub-1")) is None)
    put(sessions, marker())
    suite.ok("%s: stop_hook_active never blocks on a fork" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE, stop_hook_active=True)) is None)
    put(sessions, marker())
    suite.ok("%s: a PreToolUse event never blocks on a fork" % tag,
             hook.checklist_gate(dict(stop(cwd=ELSEWHERE),
                                      hook_event_name="PreToolUse")) is None)

    put(sessions, marker(open=[]))
    suite.ok("%s: a complete checklist never blocks on a fork" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE)) is None)
    put(sessions, marker(at=time.time() - hook.GATE_TTL - 60))
    suite.ok("%s: an expired marker never blocks on a fork" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE)) is None)

    put(sessions, marker(branch=FORK))
    suite.ok("%s: a marker re-seeded on the new branch stops blocking" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE)) is None)
    suite.ok("%s: and the re-seed needed no spent fork to do it" % tag,
             "checklist_forked" not in get(sessions), get(sessions))

    put(sessions, marker(branch=DEFAULT), extra={"checklist_forked": FORK})
    suite.ok("%s: the two-page remedy stays clear after a write to either page" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE)) is None)
    put(sessions, marker(branch=FORK), extra={"checklist_forked": FORK})
    suite.ok("%s: and after a write to the second page too" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE)) is None)


def check_several_pages(suite, profile, directory):
    hook, sessions = load_hook(profile, directory)
    tag = profile

    one = marker(url=PAGE, hash="run123", branch=BRANCH)
    two = marker(url=OTHER, hash="run456", branch=FORK)

    put(sessions, pages(one, two))
    suite.ok("%s: a session on the first page's branch does not block" % tag,
             hook.checklist_gate(stop(cwd=WORKTREE)) is None, get(sessions))
    put(sessions, pages(one, two))
    suite.ok("%s: nor one on the second page's branch" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE)) is None, get(sessions))

    put(sessions, pages(one, two))
    held = hook.checklist_gate(stop(cwd=AGAIN))
    suite.ok("%s: a branch no page tracks still blocks" % tag, bool(held), held)
    suite.ok("%s: and the hold names every tracked page" % tag,
             bool(held) and PAGE in held and OTHER in held, held)
    suite.ok("%s: and every tracked branch" % tag,
             bool(held) and BRANCH in held and FORK in held, held)
    suite.ok("%s: and the branch the session is on" % tag,
             bool(held) and THIRD in held, held)
    suite.ok("%s: the hold says a multi-page run is not a fork" % tag,
             bool(held) and "several change requests" in held, held)
    suite.ok("%s: it does not claim one page describes this session's work" % tag,
             bool(held) and "describes branch" not in held, held)

    put(sessions, pages(one, two))
    for turn in range(1, 4):
        suite.ok("%s: turn end %d counts against both pages" % (tag, turn),
                 hook.checklist_gate(stop(cwd=WORKTREE)) is None
                 and tracked(get(sessions), "run123").get("stops") == turn
                 and tracked(get(sessions), "run456").get("stops") == turn,
                 get(sessions))
    stale = hook.checklist_gate(stop(cwd=WORKTREE))
    suite.ok("%s: both pages go stale together and hold once" % tag,
             bool(stale), stale)
    suite.ok("%s: the one hold names both pages" % tag,
             bool(stale) and PAGE in stale and OTHER in stale, stale)
    suite.ok("%s: and marks both as held" % tag,
             tracked(get(sessions), "run123").get("held") is not None
             and tracked(get(sessions), "run456").get("held") is not None,
             get(sessions))
    suite.ok("%s: so the next turn end is not held again" % tag,
             hook.checklist_gate(stop(cwd=WORKTREE)) is None)

    put(sessions, pages(dict(one, verdict="stalled", in_flight=[]), two))
    stale = hook.checklist_gate(stop(cwd=WORKTREE))
    suite.ok("%s: one stalled page holds while its sibling is healthy" % tag,
             bool(stale) and PAGE in stale and OTHER not in stale, stale)
    suite.ok("%s: the healthy page is left unheld" % tag,
             "held" not in tracked(get(sessions), "run456"), get(sessions))
    suite.ok("%s: and its turn end was counted" % tag,
             tracked(get(sessions), "run456").get("stops") == 1, get(sessions))

    put(sessions, pages(one, two))
    hook.checklist_gate(stop(cwd=WORKTREE))
    hook.checklist_gate(stop(cwd=WORKTREE))
    watched = dict(tracked(get(sessions), "run456"), stops=0, at=time.time())
    put(sessions, pages(tracked(get(sessions), "run123"), watched))
    suite.ok("%s: a watcher writing to the other page does not reset this one" % tag,
             tracked(get(sessions), "run123").get("stops") == 2, get(sessions))
    hook.checklist_gate(stop(cwd=WORKTREE))
    behind = hook.checklist_gate(stop(cwd=WORKTREE))
    suite.ok("%s: so the page nobody wrote to still reaches a stale hold" % tag,
             bool(behind) and PAGE in behind, behind)
    suite.ok("%s: and the page the watcher kept fresh is not named" % tag,
             bool(behind) and OTHER not in behind, behind)

    put(sessions, pages(one, dict(two, at=time.time() - hook.GATE_TTL - 60)))
    suite.ok("%s: an expired page does not take a live sibling with it" % tag,
             hook.checklist_gate(stop(cwd=WORKTREE)) is None, get(sessions))
    suite.ok("%s: the expired page is dropped on its own" % tag,
             sorted(get(sessions).get("checklist_pending") or {}) == ["run123"],
             get(sessions))
    put(sessions, pages(dict(one, at=time.time() - hook.GATE_TTL - 60),
                        dict(two, at=time.time() - hook.GATE_TTL - 60)))
    suite.ok("%s: every page expired drops the marker" % tag,
             hook.checklist_gate(stop(cwd=WORKTREE)) is None
             and "checklist_pending" not in get(sessions), get(sessions))

    put(sessions, pages(dict(one, open=[], in_flight=[]), two))
    suite.ok("%s: a finished page beside an open one never blocks on a fork" % tag,
             hook.checklist_gate(stop(cwd=ELSEWHERE)) is None, get(sessions))

    put(sessions, pages(one, two))
    suite.ok("%s: a subagent's Stop never blocks across pages" % tag,
             hook.checklist_gate(stop(cwd=AGAIN, agent_id="sub-1")) is None)
    put(sessions, pages(one, two))
    suite.ok("%s: stop_hook_active never blocks across pages" % tag,
             hook.checklist_gate(stop(cwd=AGAIN, stop_hook_active=True)) is None)

    put(sessions, pages(one, two))
    before = frozen(sessions)
    status, said = captured(lambda: hook.cmd_checklist_status([SESSION]))
    suite.ok("%s: a status over several pages exits 0" % tag, status == 0, said)
    suite.ok("%s: it names every page" % tag, PAGE in said and OTHER in said, said)
    suite.ok("%s: it names every branch" % tag,
             BRANCH in said and FORK in said, said)
    suite.ok("%s: it counts the tracked pages" % tag, "2 tracked pages" in said, said)
    suite.ok("%s: a status over several pages mutates nothing" % tag,
             frozen(sessions) == before, get(sessions))

    status, said = captured(lambda: hook.cmd_checklist_status([SESSION]))
    suite.ok("%s: a session on a tracked branch is not reported as forked" % tag,
             "has forked" not in said, said)

    status, said = captured(lambda: hook.cmd_checklist_clear([SESSION]))
    suite.ok("%s: a clear with several pages open refuses" % tag, status != 0, said)
    suite.ok("%s: and names both pages it declined to drop" % tag,
             PAGE in said and OTHER in said, said)
    suite.ok("%s: and changed nothing" % tag, frozen(sessions) == before, get(sessions))

    status, said = captured(lambda: hook.cmd_checklist_clear(["--force", SESSION]))
    suite.ok("%s: --force drops every page at once" % tag,
             status == 0 and "checklist_pending" not in get(sessions), get(sessions))

    put(sessions, pages(one, dict(two, at=time.time() - hook.GATE_TTL - OVERAGE)))
    status, said = captured(lambda: hook.cmd_checklist_clear([SESSION]))
    suite.ok("%s: one expired page does not unlock a bare clear" % tag,
             status != 0, said)


def captured(call):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = call()
    return status, out.getvalue() + err.getvalue()


def frozen(sessions):
    return json.dumps(get(sessions), sort_keys=True)


def hours(seconds):
    return "%dh" % (int(seconds) // 3600)


def check_escape_hatch(suite, profile, directory):
    hook, sessions = load_hook(profile, directory)
    tag = profile

    status, said = captured(lambda: hook.cmd_checklist_status([SESSION]))
    suite.ok("%s: a status with no marker exits non-zero" % tag, status != 0, status)
    suite.ok("%s: and says it is not armed" % tag, "not armed" in said, said)

    status, said = captured(lambda: hook.cmd_checklist_clear([SESSION]))
    suite.ok("%s: a clear with no marker exits 0" % tag, status == 0, status)
    suite.ok("%s: and says there is nothing to clear" % tag,
             "nothing to clear" in said, said)

    put(sessions, marker(verdict="stalled", in_flight=[]))
    before = frozen(sessions)
    status, said = captured(lambda: hook.cmd_checklist_clear([SESSION]))
    suite.ok("%s: a clear with items open exits non-zero" % tag, status != 0, status)
    suite.ok("%s: it refuses out loud" % tag, "refusing" in said, said)
    suite.ok("%s: the refusal names the page" % tag, PAGE in said, said)
    suite.ok("%s: the refusal names the open ids" % tag,
             "arm" in said and "implement" in said, said)
    suite.ok("%s: the refusal names --force" % tag, "--force" in said, said)
    suite.ok("%s: the refusal changed nothing" % tag,
             frozen(sessions) == before, get(sessions))
    suite.ok("%s: so the gate still holds after a refused clear" % tag,
             hook.checklist_gate(stop()) is not None)

    put(sessions, marker(verdict="stalled", in_flight=[]))
    before = frozen(sessions)
    status, said = captured(lambda: hook.cmd_checklist_status([SESSION]))
    suite.ok("%s: a status on a live marker exits 0" % tag, status == 0, status)
    suite.ok("%s: it names the page" % tag,
             "armed" in said and PAGE in said, said)
    suite.ok("%s: it names the open ids" % tag,
             "arm" in said and "implement" in said, said)
    suite.ok("%s: it reports the turn-end count" % tag, "turn end" in said, said)
    suite.ok("%s: it names the branch the checklist describes" % tag,
             BRANCH in said, said)
    suite.ok("%s: a status mutates nothing" % tag,
             frozen(sessions) == before, get(sessions))
    suite.ok("%s: so the gate still holds after a status" % tag,
             hook.checklist_gate(stop()) is not None)

    put(sessions, marker(branch=FORK))
    before = frozen(sessions)
    status, said = captured(lambda: hook.cmd_checklist_status([SESSION]))
    suite.ok("%s: a status on a forked run says the run has forked" % tag,
             "forked" in said, said)
    suite.ok("%s: and names both branches" % tag,
             FORK in said and BRANCH in said, said)
    suite.ok("%s: a status on a forked run still mutates nothing" % tag,
             frozen(sessions) == before, get(sessions))

    put(sessions, marker(branch=""))
    status, said = captured(lambda: hook.cmd_checklist_status([SESSION]))
    suite.ok("%s: a status with no branch recorded says so" % tag,
             "no branch recorded" in said, said)

    put(sessions, marker(verdict="stalled", in_flight=[]),
        extra={"checklist_forked": FORK, "armed_at": 1234.5})
    status, _ = captured(lambda: hook.cmd_checklist_clear(["--force", SESSION]))
    state = get(sessions)
    suite.ok("%s: a forced clear drops the spent fork with the marker" % tag,
             status == 0 and "checklist_forked" not in state, state)
    suite.ok("%s: and still leaves armed_at alone" % tag,
             state.get("armed_at") == 1234.5, state)

    put(sessions, marker(verdict="stalled", in_flight=[]))
    status, said = captured(lambda: hook.cmd_checklist_clear(["--force", SESSION]))
    suite.ok("%s: --force exits 0" % tag, status == 0, status)
    suite.ok("%s: --force drops the marker" % tag,
             "checklist_pending" not in get(sessions), get(sessions))
    suite.ok("%s: --force names the page it cleared" % tag, PAGE in said, said)
    suite.ok("%s: --force names the ids it dropped" % tag,
             "arm" in said and "implement" in said, said)
    suite.ok("%s: and the next Stop passes" % tag, hook.checklist_gate(stop()) is None)

    put(sessions, marker(verdict="stalled", in_flight=[]))
    status, _ = captured(lambda: hook.cmd_checklist_clear([SESSION, "--force"]))
    suite.ok("%s: --force after the session id works too" % tag,
             status == 0 and "checklist_pending" not in get(sessions), status)

    put(sessions, marker(verdict="stalled", in_flight=[],
                         at=time.time() - hook.GATE_TTL - OVERAGE),
        extra={"armed_at": 1234.5, "thread": "T9", "last_kind": "progress"})
    before = frozen(sessions)
    status, said = captured(lambda: hook.cmd_checklist_status([SESSION]))
    suite.ok("%s: a status reports an expired marker as not armed" % tag,
             status != 0 and "not armed" in said, said)
    suite.ok("%s: a status does not drop an expired marker, unlike the gate" % tag,
             frozen(sessions) == before, get(sessions))
    suite.ok("%s: a status reports the time since expiry, not the marker's age" % tag,
             hours(OVERAGE) in said
             and hours(hook.GATE_TTL + OVERAGE) not in said, said)
    status, said = captured(lambda: hook.cmd_checklist_clear([SESSION]))
    suite.ok("%s: an expired marker clears without --force" % tag, status == 0, status)
    suite.ok("%s: and the clear says it had expired" % tag, "expired" in said, said)
    suite.ok("%s: and the clear reports the overage, not the age" % tag,
             hours(OVERAGE) in said
             and hours(hook.GATE_TTL + OVERAGE) not in said, said)
    suite.ok("%s: and it is gone" % tag,
             "checklist_pending" not in get(sessions), get(sessions))
    state = get(sessions)
    suite.ok("%s: an expired clear leaves armed_at alone" % tag,
             state.get("armed_at") == 1234.5, state)

    put(sessions, marker(verdict="stalled", in_flight=[]),
        extra={"armed_at": 1234.5, "thread": "T9", "last_kind": "progress"})
    status, _ = captured(lambda: hook.cmd_checklist_clear(["--force", SESSION]))
    state = get(sessions)
    suite.ok("%s: a forced clear drops the marker" % tag,
             status == 0 and "checklist_pending" not in state, state)
    suite.ok("%s: a forced clear leaves armed_at alone" % tag,
             state.get("armed_at") == 1234.5, state)
    suite.ok("%s: a forced clear leaves the thread alone" % tag,
             state.get("thread") == "T9", state)
    suite.ok("%s: a forced clear leaves last_kind alone" % tag,
             state.get("last_kind") == "progress", state)

    put(sessions, marker(verdict="stalled", in_flight=[], open=["merge"]))
    status, said = captured(lambda: hook.cmd_checklist_status([SESSION]))
    suite.ok("%s: one open item reads as one item" % tag,
             "1 item is open" in said, said)
    status, said = captured(lambda: hook.cmd_checklist_clear([SESSION]))
    suite.ok("%s: and the refusal agrees with it" % tag,
             "1 item is still open" in said, said)
    status, said = captured(lambda: hook.cmd_checklist_clear(["--force", SESSION]))
    suite.ok("%s: and a forced clear puts it in the past tense" % tag,
             "1 item was still open" in said, said)

    put(sessions, marker(open=[], in_flight=[]))
    status, said = captured(lambda: hook.cmd_checklist_clear([SESSION]))
    suite.ok("%s: a marker with nothing open clears without --force" % tag,
             status == 0, status)
    suite.ok("%s: and says nothing was outstanding" % tag,
             "nothing was outstanding" in said, said)

    saved = dict(os.environ)
    for key in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID"):
        os.environ.pop(key, None)
    try:
        status, said = captured(lambda: hook.cmd_checklist_clear([]))
        suite.ok("%s: a clear with no session id exits 0" % tag, status == 0, status)
        suite.ok("%s: and says so" % tag, "no session id" in said, said)
        status, said = captured(lambda: hook.cmd_checklist_status([]))
        suite.ok("%s: a status with no session id exits non-zero" % tag,
                 status != 0, status)
        suite.ok("%s: and says it is not armed" % tag, "not armed" in said, said)
    finally:
        os.environ.clear()
        os.environ.update(saved)


def run_checklist(profile, work, args, environment):
    script = os.path.join(REPO, "profiles", profile, ".claude", "scripts", "run-checklist.py")
    env = dict(os.environ)
    env.update(environment)
    return subprocess.run([sys.executable, script] + args, capture_output=True,
                          text=True, cwd=work, env=env)


def check_writer(suite, profile, work):
    tag = profile
    sessions = os.path.join(work, "notify-state", "sessions")
    home = os.path.join(work, "home")
    os.makedirs(os.path.join(home, ".claude", "notify-state", "sessions"), exist_ok=True)
    sessions = os.path.join(home, ".claude", "notify-state", "sessions")
    env = {"HOME": home, "CLAUDE_CODE_SESSION_ID": SESSION}

    items = os.path.join(work, "items.json")
    made = run_checklist(profile, work, [
        "template", "--title", "T", "--repo", "R", "--branch", "b", "--branch-mode", "new",
    ], env)
    suite.ok("%s: template exits 0" % tag, made.returncode == 0, made.stderr)
    with open(items, "w") as handle:
        handle.write(made.stdout)

    with open(os.path.join(sessions, SESSION + ".json"), "w") as handle:
        json.dump({"armed_at": 1234.5, "thread": "T1", "last_kind": "progress"}, handle)

    ticked = run_checklist(profile, work, [
        "tick", items, "plan=done", "implement=in-flight:the plan",
    ], env)
    suite.ok("%s: tick exits 0" % tag, ticked.returncode == 0, ticked.stderr)
    state = get(sessions)
    suite.ok("%s: tick wrote the marker" % tag, "checklist_pending" in state, state)
    pending = tracked(state)
    suite.ok("%s: the marker is keyed by the page" % tag,
             list((state.get("checklist_pending") or {})) == ["b"], state)
    suite.ok("%s: the marker lists the open items" % tag,
             "arm" in pending.get("open", []) and "implement" in pending.get("open", []),
             pending)
    suite.ok("%s: the marker names what is in flight" % tag,
             pending.get("in_flight") == ["implement"], pending)
    suite.ok("%s: the marker records the verdict" % tag,
             pending.get("verdict") == "armed", pending)
    suite.ok("%s: the marker records the run's branch" % tag,
             pending.get("branch") == "b", pending)
    suite.ok("%s: a fresh marker has no stops" % tag, pending.get("stops") == 0, pending)
    suite.ok("%s: a fresh marker is not held" % tag, "held" not in pending, pending)
    suite.ok("%s: the writer leaves armed_at alone" % tag, state.get("armed_at") == 1234.5, state)
    suite.ok("%s: the writer leaves the thread alone" % tag, state.get("thread") == "T1", state)
    suite.ok("%s: the writer leaves last_kind alone" % tag,
             state.get("last_kind") == "progress", state)

    unstored = dict(env)
    unstored["PUBLISH_ARTIFACT"] = os.path.join(work, "no-such-publisher")
    run_checklist(profile, work, ["publish", items], unstored)
    suite.ok("%s: a publish with no artifact store still marks the run" % tag,
             "checklist_pending" in get(sessions), get(sessions))

    with open(os.path.join(sessions, SESSION + ".json"), "w") as handle:
        json.dump({"checklist_pending": pages(dict(pending, stops=9, held=1.0))},
                  handle)
    run_checklist(profile, work, ["tick", items, "implement=done"], env)
    pending = tracked(get(sessions))
    suite.ok("%s: a later tick resets the stop count" % tag, pending.get("stops") == 0, pending)
    suite.ok("%s: a later tick clears the hold" % tag, "held" not in pending, pending)

    legacy = os.path.join(sessions, SESSION + ".json")
    with open(legacy, "w") as handle:
        json.dump({"checklist_pending": dict(pending, stops=9, held=1.0)}, handle)
    run_checklist(profile, work, ["tick", items, "implement=done"], env)
    state = get(sessions)
    suite.ok("%s: a write upgrades a flat marker left by the previous version" % tag,
             list((state.get("checklist_pending") or {})) == ["b"], state)
    suite.ok("%s: without stranding it as a second page" % tag,
             tracked(state).get("stops") == 0, state)

    second = os.path.join(work, "second.json")
    reseeded = run_checklist(profile, work, [
        "template", "--title", "T", "--repo", "R", "--branch", "c", "--branch-mode", "new",
    ], env)
    with open(second, "w") as handle:
        handle.write(reseeded.stdout)
    with open(os.path.join(sessions, SESSION + ".json"), "w") as handle:
        json.dump({"checklist_pending": pages(dict(pending, branch="b")),
                   "checklist_forked": "c"}, handle)
    run_checklist(profile, work, ["tick", second, "plan=done"], env)
    state = get(sessions)
    suite.ok("%s: a write from the second branch records it beside the first" % tag,
             sorted(state.get("checklist_pending") or {}) == ["b", "c"], state)
    suite.ok("%s: and leaves the first page's own items untouched" % tag,
             tracked(state, "b").get("open") == pending.get("open"), state)
    suite.ok("%s: and a write never wipes the spent fork" % tag,
             state.get("checklist_forked") == "c", state)

    with open(second) as handle:
        done = json.load(handle)
    for entry in done["items"]:
        entry["state"] = "done"
        entry["waiting_on"] = ""
    with open(second, "w") as handle:
        json.dump(done, handle)
    run_checklist(profile, work, ["arm", second], env)
    state = get(sessions)
    suite.ok("%s: a complete page drops its own record" % tag,
             list((state.get("checklist_pending") or {})) == ["b"], state)
    suite.ok("%s: and the spend survives while another page is open" % tag,
             state.get("checklist_forked") == "c", state)

    with open(os.path.join(sessions, SESSION + ".json"), "w") as handle:
        json.dump({"checklist_pending": pages(dict(pending, branch="c")),
                   "checklist_forked": "c", "armed_at": 7.0}, handle)
    run_checklist(profile, work, ["arm", second], env)
    state = get(sessions)
    suite.ok("%s: the last page going drops the marker and the spent fork" % tag,
             "checklist_pending" not in state and "checklist_forked" not in state,
             state)
    suite.ok("%s: and leaves armed_at alone doing it" % tag,
             state.get("armed_at") == 7.0, state)

    with open(os.path.join(sessions, SESSION + ".json"), "w") as handle:
        json.dump({"armed_at": 99.0, "thread": "T2", "last_kind": "stop"}, handle)
    armed = run_checklist(profile, work, ["arm", items], env)
    suite.ok("%s: arm exits 0" % tag, armed.returncode == 0, armed.stderr)
    state = get(sessions)
    suite.ok("%s: arm rewrites the marker from the items file alone" % tag,
             "checklist_pending" in state, state)
    suite.ok("%s: arm names the open items" % tag,
             "describe" in armed.stdout and "close" in armed.stdout, armed.stdout)
    suite.ok("%s: arm publishes nothing" % tag, "url=" not in armed.stdout, armed.stdout)
    suite.ok("%s: arm leaves armed_at alone" % tag, state.get("armed_at") == 99.0, state)
    suite.ok("%s: arm leaves the thread alone" % tag, state.get("thread") == "T2", state)
    suite.ok("%s: arm leaves last_kind alone" % tag,
             state.get("last_kind") == "stop", state)

    with open(items) as handle:
        document = json.load(handle)
    for entry in document["items"]:
        entry["state"] = "done"
        entry["waiting_on"] = ""
    with open(items, "w") as handle:
        json.dump(document, handle)
    dropped = run_checklist(profile, work, ["arm", items], env)
    suite.ok("%s: arm on a complete checklist exits 0" % tag,
             dropped.returncode == 0, dropped.stderr)
    suite.ok("%s: arm on a complete checklist drops the marker" % tag,
             "checklist_pending" not in get(sessions), get(sessions))
    run_checklist(profile, work, ["tick", items, "plan=done"], env)
    suite.ok("%s: a complete checklist drops the marker" % tag,
             "checklist_pending" not in get(sessions), get(sessions))

    stacked = os.path.join(work, "stacked.json")
    seeded = run_checklist(profile, work,
                           ["template", "--branch", BRANCH, "--merge",
                            "--stack", "first|second"], env)
    suite.ok("%s: a stacked template seeds" % tag, seeded.returncode == 0, seeded.stderr)
    with open(stacked, "w") as handle:
        handle.write(seeded.stdout)
    run_checklist(profile, work, ["arm", stacked], env)
    pending = tracked(get(sessions))
    suite.ok("%s: the marker carries every branch in the stack" % tag,
             pending.get("branches") == [BRANCH, BRANCH + "/01-first",
                                         BRANCH + "/02-second"], pending)
    suite.ok("%s: and still carries the run's own branch" % tag,
             pending.get("branch") == BRANCH, pending)

    flat = os.path.join(work, "flat.json")
    plain = run_checklist(profile, work, ["template", "--branch", BRANCH], env)
    with open(flat, "w") as handle:
        handle.write(plain.stdout)
    run_checklist(profile, work, ["arm", flat], env)
    suite.ok("%s: an unstacked run records just its own branch" % tag,
             tracked(get(sessions)).get("branches") == [BRANCH],
             get(sessions).get("checklist_pending"))

    bare_arm = dict(env)
    bare_arm.pop("CLAUDE_CODE_SESSION_ID")
    bare_arm["CLAUDE_SESSION_ID"] = ""
    silent = run_checklist(profile, work, ["arm", items], bare_arm)
    suite.ok("%s: arm with no session id still exits 0" % tag,
             silent.returncode == 0, silent.stderr)

    bare = dict(env)
    bare.pop("CLAUDE_CODE_SESSION_ID")
    bare["CLAUDE_SESSION_ID"] = ""
    quiet = run_checklist(profile, work, ["tick", items, "plan=done"], bare)
    suite.ok("%s: no session id still exits 0" % tag, quiet.returncode == 0, quiet.stderr)


def reconciled(profile, work, items, env, **forge):
    flags = []
    for key, value in forge.items():
        flags += ["--" + key.replace("_", "-"), str(value)]
    return run_checklist(profile, work, ["reconcile", items] + flags, env)


def states(items):
    with open(items) as handle:
        document = json.load(handle)
    return {entry["id"]: (entry["state"], entry.get("waiting_on", ""))
            for entry in document["items"]}


def check_reconcile(suite, profile, work):
    tag = profile
    home = os.path.join(work, "home")
    os.makedirs(os.path.join(home, ".claude", "notify-state", "sessions"), exist_ok=True)
    env = {"HOME": home, "CLAUDE_CODE_SESSION_ID": SESSION}
    items = os.path.join(work, "reconcile.json")

    made = run_checklist(profile, work, [
        "template", "--title", "T", "--repo", "R", "--branch", "b",
        "--branch-mode", "new", "--review", "--merge",
    ], env)
    with open(items, "w") as handle:
        handle.write(made.stdout)

    running = reconciled(profile, work, items, env, url="https://forge/pr/1",
                         state="OPEN", merged="false", review="NONE", unresolved=0,
                         checks_pending=2, checks_total=3, checks_failed=0)
    suite.ok("%s: reconcile exits 0" % tag, running.returncode == 0, running.stderr)
    now = states(items)
    suite.ok("%s: a running pipeline is in flight" % tag,
             now["pipeline"][0] == "in-flight", now["pipeline"])
    suite.ok("%s: and says how many checks are left" % tag,
             "2 of 3" in now["pipeline"][1], now["pipeline"])
    suite.ok("%s: an open change request ticks the open item" % tag,
             now["open"][0] == "done", now["open"])
    suite.ok("%s: reconcile never touches the swarm item" % tag,
             now["review"][0] == "pending", now["review"])
    suite.ok("%s: reconcile never touches implement" % tag,
             now["implement"][0] == "pending", now["implement"])

    green = reconciled(profile, work, items, env, url="https://forge/pr/1",
                       state="OPEN", merged="false", review="APPROVED", unresolved=0,
                       checks_pending=0, checks_total=3, checks_failed=0)
    now = states(items)
    suite.ok("%s: a green pipeline is done" % tag, now["pipeline"][0] == "done", now["pipeline"])
    suite.ok("%s: an approved review with no threads clears them" % tag,
             now["threads"][0] == "done", now["threads"])
    suite.ok("%s: the change is reported" % tag, "pipeline=done" in green.stdout, green.stdout)

    blocked = reconciled(profile, work, items, env, url="https://forge/pr/1",
                         state="OPEN", merged="false", review="CHANGES_REQUESTED",
                         unresolved=1, checks_pending=0, checks_total=3, checks_failed=0)
    now = states(items)
    suite.ok("%s: changes requested reopens the threads item" % tag,
             now["threads"][0] == "in-flight", now["threads"])
    suite.ok("%s: and says why" % tag, "requested changes" in now["threads"][1], now["threads"])
    suite.ok("%s: a reopened item is reported as a change" % tag,
             "threads=in-flight" in blocked.stdout, blocked.stdout)

    pushed = reconciled(profile, work, items, env, url="https://forge/pr/1",
                        state="OPEN", merged="false", review="NONE", unresolved=0,
                        checks_pending=1, checks_total=3, checks_failed=0)
    suite.ok("%s: a push moves a done pipeline back to in flight" % tag,
             states(items)["pipeline"][0] == "in-flight", pushed.stdout)

    red = reconciled(profile, work, items, env, url="https://forge/pr/1",
                     state="OPEN", merged="false", review="NONE", unresolved=0,
                     checks_pending=0, checks_total=3, checks_failed=1)
    now = states(items)
    suite.ok("%s: a failed check is never done" % tag,
             now["pipeline"][0] == "in-flight", now["pipeline"])
    suite.ok("%s: and names the failure" % tag, "failed" in now["pipeline"][1], now["pipeline"])

    again = reconciled(profile, work, items, env, url="https://forge/pr/1",
                       state="OPEN", merged="false", review="NONE", unresolved=0,
                       checks_pending=0, checks_total=3, checks_failed=1)
    suite.ok("%s: an unchanged forge state reports unchanged" % tag,
             again.stdout.startswith("unchanged:"), again.stdout)

    merged = reconciled(profile, work, items, env, url="https://forge/pr/1",
                        state="MERGED", merged="true", review="APPROVED", unresolved=0,
                        checks_pending=0, checks_total=3, checks_failed=0)
    now = states(items)
    suite.ok("%s: a merged change ticks the merge item" % tag,
             now["merge"][0] == "done", now["merge"])
    suite.ok("%s: merging settles the pipeline too" % tag,
             now["pipeline"][0] == "done", now["pipeline"])
    suite.ok("%s: merge is reported" % tag, "merge=done" in merged.stdout, merged.stdout)

    closed_items = os.path.join(work, "closed.json")
    with open(closed_items, "w") as handle:
        handle.write(made.stdout)
    reconciled(profile, work, closed_items, env, url="https://forge/pr/1",
               state="CLOSED", merged="false", review="NONE", unresolved=0,
               checks_pending=0, checks_total=0, checks_failed=0)
    suite.ok("%s: a closed change request skips the merge with a reason" % tag,
             states(closed_items)["merge"][0] == "skipped", states(closed_items)["merge"])

    skipped_items = os.path.join(work, "skipped.json")
    with open(skipped_items, "w") as handle:
        handle.write(made.stdout)
    run_checklist(profile, work, ["tick", skipped_items,
                                  "pipeline=skipped:no pipeline in this repo"], env)
    reconciled(profile, work, skipped_items, env, url="https://forge/pr/1",
               state="OPEN", merged="false", review="NONE", unresolved=0,
               checks_pending=0, checks_total=3, checks_failed=0)
    suite.ok("%s: reconcile never revives a deliberately skipped item" % tag,
             states(skipped_items)["pipeline"][0] == "skipped",
             states(skipped_items)["pipeline"])

    suite.ok("%s: reconcile rearms the gate marker" % tag,
             "checklist_pending" in get(os.path.join(home, ".claude", "notify-state", "sessions")),
             get(os.path.join(home, ".claude", "notify-state", "sessions")))


def git(repo, *args):
    return subprocess.run(("git", "-C", repo) + args, capture_output=True, text=True)


def build_repo(root):
    os.makedirs(root, exist_ok=True)
    git(root, "init", "--quiet", "--initial-branch=main")
    git(root, "config", "user.email", "t@example.invalid")
    git(root, "config", "user.name", "Test")
    with open(os.path.join(root, "seed.txt"), "w") as handle:
        handle.write("seed\n")
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", "seed")
    git(root, "branch", "feature")
    return root


def commit_on(root, branch, text):
    git(root, "checkout", "--quiet", branch)
    with open(os.path.join(root, text + ".txt"), "w") as handle:
        handle.write(text + "\n")
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", text)
    git(root, "checkout", "--quiet", "main")


def check_local_signals(suite, profile, work):
    tag = profile
    home = os.path.join(work, "home")
    sessions = os.path.join(home, ".claude", "notify-state", "sessions")
    os.makedirs(sessions, exist_ok=True)
    env = {"HOME": home, "CLAUDE_CODE_SESSION_ID": SESSION}
    repo = build_repo(os.path.join(work, "repo"))
    items = os.path.join(work, "local.json")

    made = run_checklist(profile, work, [
        "template", "--title", "T", "--repo", "R", "--branch", "feature",
        "--branch-mode", "new", "--review", "--merge",
    ], env)
    with open(items, "w") as handle:
        handle.write(made.stdout)

    def sync(**extra):
        flags = ["--repo", repo, "--default-branch", "main"]
        for key, value in extra.items():
            flags += ["--" + key.replace("_", "-"), str(value)]
        return run_checklist(profile, work, ["reconcile", items] + flags, env)

    sync()
    now = states(items)
    suite.ok("%s: no armed_at leaves arm pending" % tag, now["arm"][0] == "pending", now["arm"])
    suite.ok("%s: a branch with no commits leaves commit pending" % tag,
             now["commit"][0] == "pending", now["commit"])

    with open(os.path.join(sessions, SESSION + ".json"), "w") as handle:
        json.dump({"armed_at": 1.0}, handle)
    sync()
    suite.ok("%s: armed_at ticks arm done" % tag, states(items)["arm"][0] == "done",
             states(items)["arm"])

    with open(os.path.join(sessions, SESSION + ".json"), "w") as handle:
        json.dump({}, handle)
    sync()
    suite.ok("%s: /ping off never un-ticks a ping that was sent" % tag,
             states(items)["arm"][0] == "done", states(items)["arm"])
    with open(os.path.join(sessions, SESSION + ".json"), "w") as handle:
        json.dump({"armed_at": 1.0}, handle)

    run_checklist(profile, work, ["tick", items, "implement=in-flight:writing it"], env)
    sync()
    now = states(items)
    suite.ok("%s: a missing commit never demotes a true in-flight" % tag,
             now["implement"][0] == "in-flight", now["implement"])
    suite.ok("%s: and leaves its blocker alone" % tag,
             now["implement"][1] == "writing it", now["implement"])

    commit_on(repo, "feature", "work")
    sync()
    now = states(items)
    suite.ok("%s: a commit on the branch ticks commit done" % tag,
             now["commit"][0] == "done", now["commit"])
    suite.ok("%s: and ticks implement done over the in-flight" % tag,
             now["implement"][0] == "done", now["implement"])

    git(repo, "checkout", "--quiet", "main")
    git(repo, "merge", "--no-ff", "--quiet", "-m", "merge feature", "feature")
    sync()
    now = states(items)
    suite.ok("%s: a merge commit never un-ticks commit" % tag,
             now["commit"][0] == "done", now["commit"])
    suite.ok("%s: nor implement" % tag, now["implement"][0] == "done", now["implement"])

    git(repo, "branch", "-f", "feature", "main")
    sync()
    now = states(items)
    suite.ok("%s: a branch contained in the base never un-ticks commit" % tag,
             now["commit"][0] == "done", now["commit"])

    body = os.path.join(work, "body.md")
    with open(body, "w") as handle:
        handle.write("**Run checklist:** https://example.invalid/x\n")
    sync(body_file=body)
    now = states(items)
    suite.ok("%s: a body carrying only the checklist link is not a description" % tag,
             now["describe"][0] == "pending", now["describe"])
    suite.ok("%s: and no fold leaves the ledger pending" % tag,
             now["ledger"][0] == "pending", now["ledger"])

    with open(body, "w") as handle:
        handle.write("**Run checklist:** https://example.invalid/x\n\n## Summary\n\nIt does a thing.\n")
    sync(body_file=body)
    suite.ok("%s: real prose ticks describe done" % tag,
             states(items)["describe"][0] == "done", states(items)["describe"])

    with open(body, "w") as handle:
        handle.write("## Summary\n\nIt does a thing.\n\n<details>\n<summary>Relevant Decisions (2)</summary>\n</details>\n")
    sync(body_file=body)
    suite.ok("%s: the decision fold ticks the ledger done" % tag,
             states(items)["ledger"][0] == "done", states(items)["ledger"])

    with open(body, "w") as handle:
        handle.write("**Run checklist:** https://example.invalid/x\n")
    sync(body_file=body)
    now = states(items)
    suite.ok("%s: a body that loses its prose never un-ticks describe" % tag,
             now["describe"][0] == "done", now["describe"])
    suite.ok("%s: nor the ledger" % tag, now["ledger"][0] == "done", now["ledger"])

    run_checklist(profile, work, ["tick", items, "ledger=skipped:nothing worth recording"], env)
    sync(body_file=body)
    suite.ok("%s: a skipped item survives a contradicting signal" % tag,
             states(items)["ledger"][0] == "skipped", states(items)["ledger"])

    run_checklist(profile, work, ["tick", items,
                                  "merge=in-flight:a stale blocker from a pause"], env)
    sync(url="https://forge/pr/9", state="OPEN", merged="false", review="NONE",
         unresolved=0, checks_pending=0, checks_total=3, checks_failed=0)
    suite.ok("%s: an owned item's stale blocker is refreshed while it is open" % tag,
             "stale blocker" not in states(items)["merge"][1], states(items)["merge"])

    suite.ok("%s: verify is never derived" % tag,
             states(items)["verify"][0] == "pending", states(items)["verify"])
    suite.ok("%s: the swarm item is never derived" % tag,
             states(items)["review"][0] == "pending", states(items)["review"])

    fresh = os.path.join(work, "noreq.json")
    with open(fresh, "w") as handle:
        handle.write(made.stdout)
    blind = run_checklist(profile, work, [
        "reconcile", fresh, "--repo", repo, "--default-branch", "main",
        "--state", "MERGED", "--merged", "true", "--review", "APPROVED",
        "--checks-pending", "0", "--checks-total", "3", "--checks-failed", "0",
    ], env)
    now = states(fresh)
    suite.ok("%s: a checklist with no change request exits 0" % tag,
             blind.returncode == 0, blind.stderr)
    suite.ok("%s: and never derives merge from a request it does not have" % tag,
             now["merge"][0] == "pending", now["merge"])
    suite.ok("%s: nor the pipeline" % tag, now["pipeline"][0] == "pending", now["pipeline"])

    owned = os.path.join(work, "owned.json")
    with open(owned, "w") as handle:
        handle.write(made.stdout)
    run_checklist(profile, work, ["tick", owned, "arm=done", "--run",
                                  "change_request=https://forge/pr/1"], env)
    wrong = run_checklist(profile, work, [
        "reconcile", owned, "--url", "https://forge/pr/999", "--state", "MERGED",
        "--merged", "true", "--review", "APPROVED",
        "--checks-pending", "0", "--checks-total", "3", "--checks-failed", "0",
    ], env)
    suite.ok("%s: another change request's state is refused" % tag,
             wrong.returncode != 0, wrong.stdout)
    suite.ok("%s: and the refusal names both requests" % tag,
             "pr/1" in wrong.stderr and "pr/999" in wrong.stderr, wrong.stderr)
    suite.ok("%s: and nothing was written" % tag,
             states(owned)["merge"][0] == "pending", states(owned)["merge"])

    right = run_checklist(profile, work, [
        "reconcile", owned, "--url", "https://forge/pr/1", "--state", "MERGED",
        "--merged", "true", "--review", "APPROVED",
        "--checks-pending", "0", "--checks-total", "3", "--checks-failed", "0",
    ], env)
    suite.ok("%s: the matching change request is accepted" % tag,
             right.returncode == 0 and states(owned)["merge"][0] == "done",
             states(owned)["merge"])

    missing = os.path.join(work, "nowhere")
    quiet = run_checklist(profile, work, ["reconcile", items, "--repo", missing,
                                          "--default-branch", "main"], env)
    suite.ok("%s: an unreadable repository does not fail the sync" % tag,
             quiet.returncode == 0, quiet.stderr)

    stack = os.path.join(work, "reconcile-stack.json")
    seeded = run_checklist(profile, work, [
        "template", "--branch", "b", "--merge", "--stack", "first|second"], env)
    with open(stack, "w") as handle:
        handle.write(seeded.stdout)
    run_checklist(profile, work, [
        "tick", stack, "plan=done",
        "--run", "1:change_request=https://forge/pr/1",
        "--run", "2:change_request=https://forge/pr/2"], env)

    synced = run_checklist(profile, work, [
        "reconcile", stack, "--stage", "2", "--url", "https://forge/pr/2",
        "--state", "MERGED", "--merged", "true", "--repo", missing], env)
    suite.ok("%s: a per-stage sync exits 0" % tag, synced.returncode == 0, synced.stderr)
    now = states(stack)
    suite.ok("%s: it writes the member it was given" % tag,
             now["merge@2"][0] == "done", now["merge@2"])
    suite.ok("%s: and leaves the other member alone" % tag,
             now["merge@1"][0] == "pending", now["merge@1"])
    suite.ok("%s: it names the member in what it changed" % tag,
             "merge@2=done" in synced.stdout, synced.stdout)

    wrong = run_checklist(profile, work, [
        "reconcile", stack, "--stage", "2", "--url", "https://forge/pr/1",
        "--state", "MERGED", "--merged", "true", "--repo", missing], env)
    suite.ok("%s: a member refuses another member's change request" % tag,
             wrong.returncode == 2, wrong.stdout + wrong.stderr)
    suite.ok("%s: and says which two it is refusing to confuse" % tag,
             "pr/2" in wrong.stderr and "pr/1" in wrong.stderr, wrong.stderr)

    unknown = run_checklist(profile, work, [
        "reconcile", stack, "--stage", "9", "--repo", missing], env)
    suite.ok("%s: an unknown member is refused" % tag,
             unknown.returncode == 2 and "no stage" in unknown.stderr, unknown.stderr)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "rules":
        print(RULES.strip())
        return 0

    suite = Suite()
    directory = tempfile.mkdtemp()
    try:
        for profile in PROFILES:
            check_hook(suite, profile, directory)
            check_fork(suite, profile, os.path.join(directory, "fork"))
            check_several_pages(suite, profile, os.path.join(directory, "pages"))
            check_escape_hatch(suite, profile, os.path.join(directory, "hatch"))
            work = os.path.join(directory, profile, "writer")
            os.makedirs(work, exist_ok=True)
            check_writer(suite, profile, work)
            sync = os.path.join(directory, profile, "reconcile")
            os.makedirs(sync, exist_ok=True)
            check_reconcile(suite, profile, sync)
            local = os.path.join(directory, profile, "local")
            os.makedirs(local, exist_ok=True)
            check_local_signals(suite, profile, local)
    finally:
        shutil.rmtree(directory, ignore_errors=True)

    if suite.failures:
        print("checklist gate: %d of %d checks failed" % (suite.failures, suite.checked))
        return 1
    print("checklist gate: %d checks passed" % suite.checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
