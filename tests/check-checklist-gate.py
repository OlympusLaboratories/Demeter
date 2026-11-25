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

RULES = """
the run checklist gate, checked over every profile copy:

  run-checklist.py writes the marker
    publish with outstanding items        records checklist_pending in the session state
    tick with outstanding items           rewrites it, resetting the stop count
    every item done or skipped            drops the marker entirely
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

  the escape hatch
    --checklist-clear                     drops the marker, so the next Stop passes
    --checklist-clear with no session     exits 0 and says so
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
    return module, sessions


def marker(**extra):
    base = {
        "url": PAGE,
        "hash": "run123",
        "at": time.time(),
        "stops": 0,
        "verdict": "armed",
        "open": ["arm", "implement"],
        "in_flight": ["implement"],
    }
    base.update(extra)
    return base


def put(sessions, value, session=SESSION):
    path = os.path.join(sessions, session + ".json")
    with open(path, "w") as handle:
        json.dump({} if value is None else {"checklist_pending": value}, handle)
    return path


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
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        cleared = hook.cmd_checklist_clear([SESSION])
    suite.ok("%s: --checklist-clear exits 0" % tag, cleared == 0, cleared)
    suite.ok("%s: --checklist-clear drops the marker" % tag,
             "checklist_pending" not in get(sessions), get(sessions))
    suite.ok("%s: and the next Stop passes" % tag, hook.checklist_gate(stop()) is None)


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
    pending = state.get("checklist_pending", {})
    suite.ok("%s: the marker lists the open items" % tag,
             "arm" in pending.get("open", []) and "implement" in pending.get("open", []),
             pending)
    suite.ok("%s: the marker names what is in flight" % tag,
             pending.get("in_flight") == ["implement"], pending)
    suite.ok("%s: the marker records the verdict" % tag,
             pending.get("verdict") == "armed", pending)
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
        json.dump({"checklist_pending": dict(pending, stops=9, held=1.0)}, handle)
    run_checklist(profile, work, ["tick", items, "implement=done"], env)
    pending = get(sessions).get("checklist_pending", {})
    suite.ok("%s: a later tick resets the stop count" % tag, pending.get("stops") == 0, pending)
    suite.ok("%s: a later tick clears the hold" % tag, "held" not in pending, pending)

    with open(items) as handle:
        document = json.load(handle)
    for entry in document["items"]:
        entry["state"] = "done"
        entry["waiting_on"] = ""
    with open(items, "w") as handle:
        json.dump(document, handle)
    run_checklist(profile, work, ["tick", items, "plan=done"], env)
    suite.ok("%s: a complete checklist drops the marker" % tag,
             "checklist_pending" not in get(sessions), get(sessions))

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


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "rules":
        print(RULES.strip())
        return 0

    suite = Suite()
    directory = tempfile.mkdtemp()
    try:
        for profile in PROFILES:
            check_hook(suite, profile, directory)
            work = os.path.join(directory, profile, "writer")
            os.makedirs(work, exist_ok=True)
            check_writer(suite, profile, work)
            sync = os.path.join(directory, profile, "reconcile")
            os.makedirs(sync, exist_ok=True)
            check_reconcile(suite, profile, sync)
    finally:
        shutil.rmtree(directory, ignore_errors=True)

    if suite.failures:
        print("checklist gate: %d of %d checks failed" % (suite.failures, suite.checked))
        return 1
    print("checklist gate: %d checks passed" % suite.checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
