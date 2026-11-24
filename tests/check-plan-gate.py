#!/usr/bin/env python3
import importlib.util
import io
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

SESSION = "11111111-2222-3333-4444-555555555555"
PLAN = "https://artifacts.example.dev/abc123"
LATER = "https://artifacts.example.dev/def456"
PLACEHOLDER_URL = "https://example.invalid/abc"
REJECTED = (
    "https://example.invalid/abc",
    "http://anything.test/page",
    "https://host.example/page",
    "https://localhost/page",
    "https://nodot/page",
    "artifacts.example.dev/abc123",
    "ftp://artifacts.example.dev/abc123",
    "https://artifacts.example.dev/a b",
    "notaurl",
)


def pending(**extra):
    return dict({"url": PLAN, "at": time.time()}, **extra)


def expired(**extra):
    return dict({"url": PLAN, "at": time.time() - 48 * 3600}, **extra)


def load(profile, directory):
    path = os.path.join(REPO, "profiles", profile, ".claude", "hooks", "notify.py")
    spec = importlib.util.spec_from_file_location("gate_" + profile, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    sessions = os.path.join(directory, profile)
    os.makedirs(sessions, exist_ok=True)
    module.session_path = lambda sid: os.path.join(sessions, (sid or "none") + ".json")
    module.load_config = lambda: (dict(module.DEFAULTS), None)
    module.in_quiet_hours = lambda config: False
    module.away_until = lambda: (None, False)
    module.repo_label = lambda cwd, host_label="": "Demeter"
    module.branch_label = lambda cwd: "dylan/OLY-14"
    module.session_title = lambda *a, **k: "Fix and merge OLY-14"
    module.change_request_for = lambda *a, **k: None
    module.turn_seconds = lambda path: 5.0
    module.shorten = lambda raw, kind, config: (raw, "already short")
    module.log = lambda message: None
    return module


def arm(module, **fields):
    state = dict(fields)
    path = module.session_path(SESSION)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle)
    return path


def state_of(module):
    path = module.session_path(SESSION)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def stop_payload():
    return {
        "hook_event_name": "Stop",
        "session_id": SESSION,
        "cwd": REPO,
        "transcript_path": None,
        "last_assistant_message": "Published the plan.",
    }


def question_payload():
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "AskUserQuestion",
        "session_id": SESSION,
        "cwd": REPO,
        "transcript_path": None,
        "tool_input": {"questions": [{"question": "Approve the plan?"}]}
    }


def case_cli_round_trip(module):
    module.session_from_env = lambda: SESSION
    arm(module)
    module.cmd_gate([PLAN])
    if state_of(module).get("gate_pending", {}).get("url") != PLAN:
        return "--gate-pending did not record the url"
    module.cmd_gate([LATER])
    if state_of(module).get("gate_pending", {}).get("url") != LATER:
        return "--gate-pending did not replace an earlier url"
    module.cmd_gate([""])
    if "gate_pending" in state_of(module):
        return "--gate-clear left the marker in place"
    return None


def case_stranded_gate_notifies_unarmed(module):
    sent = []

    def record(envelope):
        sent.append(envelope)
        return 900, None

    module.send = record
    arm(module, gate_pending=pending())
    result = module.handle(stop_payload())
    if not result.startswith("sent"):
        return "an unarmed Stop with a pending gate was not sent: %s" % result
    if "stranded plan gate" not in result:
        return "the send was not reported as a stranded gate: %s" % result
    if not any(PLAN in (e.get("body") or "") for e in sent):
        return "the notification body does not carry the plan url"
    if "gate_pending" in state_of(module):
        return "the marker survived a successful send"
    return None


def case_no_gate_stays_silent(module):
    sent = []

    def record(envelope):
        sent.append(envelope)
        return 900, None

    module.send = record
    arm(module)
    result = module.handle(stop_payload())
    if not result.startswith("skip"):
        return "an unarmed Stop with no pending gate was sent: %s" % result
    return None


def case_failed_send_keeps_marker(module):
    module.send = lambda envelope: (None, "could not reach telegram")
    arm(module, gate_pending=pending())
    result = module.handle(stop_payload())
    if not result.startswith("error"):
        return "a failed send was not reported as an error: %s" % result
    if state_of(module).get("gate_pending", {}).get("url") != PLAN:
        return "a failed send dropped the marker, so nothing will retry"
    return None


def case_rate_limit_keeps_marker(module):
    import time

    module.send = lambda envelope: (900, None)
    arm(module, gate_pending=pending(), last_sent=time.time())
    result = module.handle(stop_payload())
    if "rate limited" not in result:
        return "a rate-limited turn was not skipped: %s" % result
    if state_of(module).get("gate_pending", {}).get("url") != PLAN:
        return "a rate-limited turn dropped the marker, so nothing will retry"
    return None


def case_question_clears_marker(module):
    sent = []

    def record(envelope):
        sent.append(envelope)
        return 900, None

    module.send = record
    arm(module, gate_pending=pending())
    result = module.handle(question_payload())
    if not result.startswith("sent"):
        return "the gate question was not sent: %s" % result
    if "gate_pending" in state_of(module):
        return "asking the gate question left the marker pending"
    return None


def drive_main(module, payload):
    saved = (sys.stdin, sys.stdout, sys.argv)
    sys.stdin = io.StringIO(json.dumps(payload))
    sys.stdout = io.StringIO()
    sys.argv = ["notify.py"]
    try:
        return module.main(), sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout, sys.argv = saved


def case_main_emits_the_block_decision_on_stdout(module):
    arm(module, gate_pending=pending())
    code, out = drive_main(module, stop_payload())
    if code != 0:
        return "main() exited %r; Claude Code needs 0 alongside the decision" % code
    if not out.strip():
        return "main() printed nothing to stdout, so no block reaches Claude Code"
    try:
        decision = json.loads(out)
    except ValueError as error:
        return "stdout is not the JSON Claude Code parses: %s" % error
    if decision.get("decision") != "block":
        return "stdout carries decision=%r, not a block" % (decision.get("decision"),)
    if PLAN not in (decision.get("reason") or ""):
        return "the block reason does not carry the plan url"
    return None


def case_main_stays_silent_with_no_gate(module):
    module.send = lambda envelope: (900, None)
    arm(module)
    code, out = drive_main(module, stop_payload())
    if code != 0:
        return "main() exited %r on an ordinary turn end" % code
    if out.strip():
        return "main() printed %r with no plan pending, which would block the turn" % out.strip()
    return None


def case_a_stale_write_cannot_resurrect_the_gate(module):
    arm(module, gate_pending=pending())
    stale = state_of(module)
    if not module.plan_gate(stop_payload()):
        return "the first turn end was not held"
    module.plan_gate(question_payload())
    module.record_sent(SESSION, stale, 123.0, kind="permission", thread=900)
    after = state_of(module)
    if "gate_pending" in after:
        return "a slow handle() write resurrected the cleared gate, so the next turn is held again"
    if after.get("last_kind") != "permission":
        return "the merge dropped a key record_sent owns"
    if after.get("thread") != 900:
        return "the merge dropped the thread record_sent owns"
    return None


def case_stop_is_held_before_it_ends(module):
    arm(module, gate_pending=pending())
    reason = module.plan_gate(stop_payload())
    if not reason:
        return "a turn ending with a plan published was allowed to end"
    if PLAN not in reason:
        return "the hold reason does not carry the plan url"
    if "AskUserQuestion" not in reason:
        return "the hold reason does not name the tool to call"
    if not state_of(module).get("gate_pending", {}).get("held"):
        return "the hold was not recorded, so it cannot be bounded"
    return None


def case_stop_is_held_only_once(module):
    arm(module, gate_pending=pending())
    if not module.plan_gate(stop_payload()):
        return "the first turn end was not held"
    if module.plan_gate(stop_payload()):
        return "a second turn end was held again, which is an infinite loop"
    return None


def case_stop_hook_active_is_honoured(module):
    arm(module, gate_pending=pending())
    payload = dict(stop_payload(), stop_hook_active=True)
    if module.plan_gate(payload):
        return "a stop already continuing from a hook block was held again"
    return None


def case_unrecordable_hold_does_not_block(module):
    module.write_json = lambda path, value: False
    arm(module, gate_pending=pending())
    if module.plan_gate(stop_payload()):
        return "a hold that could not be recorded still blocked, so it will repeat"
    return None


def case_no_gate_is_never_held(module):
    arm(module)
    if module.plan_gate(stop_payload()):
        return "a turn with no plan published was held"
    return None


def case_subagent_stop_is_never_held(module):
    arm(module, gate_pending=pending())
    payload = dict(stop_payload(), agent_id="agent-1", agent_type="Explore")
    if module.plan_gate(payload):
        return "a subagent's stop was held against the session's plan gate"
    return None


def case_question_clears_marker_before_config(module):
    module.load_config = lambda: (None, "no config on this machine")
    arm(module, gate_pending=pending())
    if module.plan_gate(question_payload()):
        return "asking the question held the turn"
    if "gate_pending" in state_of(module):
        return "the marker survived the question, so a later turn would be held"
    return None


def case_held_gate_still_notifies(module):
    sent = []

    def record(envelope):
        sent.append(envelope)
        return 900, None

    module.send = record
    arm(module, gate_pending=pending(held=1))
    result = module.handle(stop_payload())
    if "stranded plan gate" not in result:
        return "a held gate lost the notification behind the block: %s" % result
    return None


def case_permission_keeps_marker(module):
    module.send = lambda envelope: (900, None)
    arm(module, gate_pending=pending())
    module.handle({
        "hook_event_name": "Notification",
        "notification_type": "permission_prompt",
        "session_id": SESSION,
        "cwd": REPO,
        "transcript_path": None,
        "message": "Claude needs your permission to use Bash",
    })
    if state_of(module).get("gate_pending", {}).get("url") != PLAN:
        return "an unrelated permission prompt consumed the pending gate"
    return None


def case_expired_gate_is_not_held(module):
    arm(module, gate_pending=expired())
    if module.plan_gate(stop_payload()):
        return "a plan published two days ago still held the turn"
    if "gate_pending" in state_of(module):
        return "the expired marker was not dropped"
    return None


def case_expired_gate_does_not_notify(module):
    module.send = lambda envelope: (900, None)
    arm(module, gate_pending=expired())
    result = module.handle(stop_payload())
    if "stranded plan gate" in result:
        return "an expired gate still sent a stranded-gate notification: %s" % result
    if not result.startswith("skip"):
        return "an expired gate on an unarmed session was sent anyway: %s" % result
    if "gate_pending" in state_of(module):
        return "the expired marker survived the turn"
    return None


def case_a_gate_with_no_timestamp_is_kept(module):
    arm(module, gate_pending={"url": PLAN})
    if not module.plan_gate(stop_payload()):
        return "a marker written without a timestamp was treated as expired"
    return None


def case_quiet_hours_do_not_age_the_marker_out(module):
    module.in_quiet_hours = lambda config: True
    arm(module, gate_pending=pending())
    result = module.handle(stop_payload())
    if "quiet hours" not in result:
        return "quiet hours were not honoured: %s" % result
    if state_of(module).get("gate_pending", {}).get("url") != PLAN:
        return "quiet hours dropped the marker, so nothing will retry"
    return None


def quietly(call, *args):
    saved = sys.stderr
    sys.stderr = io.StringIO()
    try:
        return call(*args)
    finally:
        sys.stderr = saved


def case_gate_rejects_an_implausible_url(module):
    module.session_from_env = lambda: SESSION
    for url in REJECTED:
        arm(module)
        quietly(module.cmd_gate, [url])
        if "gate_pending" in state_of(module):
            return "cmd_gate recorded %r, which is not a publishable url" % url
    return None


def case_gate_still_accepts_a_real_url(module):
    module.session_from_env = lambda: SESSION
    arm(module)
    module.cmd_gate([PLAN])
    if state_of(module).get("gate_pending", {}).get("url") != PLAN:
        return "the validation rejected a url the publisher really prints"
    return None


def case_a_rejected_url_does_not_clear_a_pending_gate(module):
    module.session_from_env = lambda: SESSION
    arm(module, gate_pending=pending())
    quietly(module.cmd_gate, [PLACEHOLDER_URL])
    if state_of(module).get("gate_pending", {}).get("url") != PLAN:
        return "a rejected url overwrote or cleared the gate already pending"
    return None


CASES = (
    ("--gate-pending and --gate-clear round-trip through the session state",
     case_cli_round_trip),
    ("a plan gate older than the threshold is not held",
     case_expired_gate_is_not_held),
    ("a plan gate older than the threshold does not notify either",
     case_expired_gate_does_not_notify),
    ("a marker carrying no timestamp is kept rather than aged out",
     case_a_gate_with_no_timestamp_is_kept),
    ("quiet hours still retain a marker inside the threshold",
     case_quiet_hours_do_not_age_the_marker_out),
    ("cmd_gate rejects a placeholder and every other unpublishable shape",
     case_gate_rejects_an_implausible_url),
    ("cmd_gate still accepts the url the publisher prints",
     case_gate_still_accepts_a_real_url),
    ("a rejected url leaves an already-pending gate alone",
     case_a_rejected_url_does_not_clear_a_pending_gate),
    ("an unarmed turn ending with a plan published notifies anyway",
     case_stranded_gate_notifies_unarmed),
    ("an unarmed turn with no plan published stays silent",
     case_no_gate_stays_silent),
    ("a failed send keeps the marker so the next turn retries",
     case_failed_send_keeps_marker),
    ("a rate-limited turn keeps the marker so the next turn retries",
     case_rate_limit_keeps_marker),
    ("asking the gate question clears the marker",
     case_question_clears_marker),
    ("an unrelated permission prompt leaves the marker alone",
     case_permission_keeps_marker),
    ("a turn ending with a plan published is held before it can end",
     case_stop_is_held_before_it_ends),
    ("the hold fires at most once, so it cannot loop",
     case_stop_is_held_only_once),
    ("a stop already continuing from a hook block is not held again",
     case_stop_hook_active_is_honoured),
    ("a hold that cannot be recorded is not applied",
     case_unrecordable_hold_does_not_block),
    ("a turn with no plan published is never held",
     case_no_gate_is_never_held),
    ("a subagent's stop is never held",
     case_subagent_stop_is_never_held),
    ("asking the question clears the marker without consulting the config",
     case_question_clears_marker_before_config),
    ("a gate that was already held still notifies at the turn end",
     case_held_gate_still_notifies),
    ("main() prints the block decision Claude Code parses, on stdout, at exit 0",
     case_main_emits_the_block_decision_on_stdout),
    ("main() prints nothing when no plan is pending",
     case_main_stays_silent_with_no_gate),
    ("a stale snapshot written late cannot resurrect a cleared gate",
     case_a_stale_write_cannot_resurrect_the_gate),
)


def run(profile, directory):
    failures = []
    for label, case in CASES:
        module = load(profile, directory)
        try:
            problem = case(module)
        except Exception as error:
            problem = "raised %r" % (error,)
        if problem:
            failures.append("  %s\n      %s" % (label, problem))
    return failures


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "rules":
        print("the plan gate's contract, over every profile copy:")
        print()
        print("  A published plan is a promise of a question. publish-artifact.sh")
        print("  --purpose plan records the url in the session state, and the Stop hook")
        print("  REFUSES the first turn end that leaves the marker set: it returns")
        print("  {\"decision\": \"block\", \"reason\": ...} and the run is sent back to ask")
        print("  in the turn it was about to end.")
        print()
        print("  The decision is asserted through main() on real stdout, not off the")
        print("  helper's return value: renaming the key or printing it to stderr")
        print("  ships a hook that blocks nothing, and only the process's own output")
        print("  catches that.")
        print()
        print("  The block is bounded three ways, because a blocking hook that repeats")
        print("  is a hang: a `held` stamp in the marker, the payload's")
        print("  stop_hook_active, and a refusal to block at all when the stamp cannot")
        print("  be written. A question clears the marker BEFORE the notification")
        print("  config is read, so quiet hours cannot leave a correct turn blocked.")
        print()
        print("  Every writer MERGES rather than clobbers: it re-reads the file and")
        print("  applies only the keys it owns. A notification handle() can sit in")
        print("  summarize for 180s holding a stale snapshot, and writing that back")
        print("  whole would resurrect a gate another process had already cleared.")
        print()
        print("  The marker is bounded in time as well as in repetition. `at` is")
        print("  load-bearing: a marker older than GATE_TTL is dropped with a log line")
        print("  rather than appended to an unrelated notification turns later. The")
        print("  threshold has a floor rather than being free -- retention across a")
        print("  failed send, a rate-limited turn and quiet hours is a contract, and a")
        print("  quiet-hours window can run eight hours or more, so a TTL shorter than")
        print("  that would silently break the guarantee above. A marker carrying no")
        print("  timestamp at all is kept, not aged out.")
        print()
        print("  cmd_gate validates the shape before recording anything, because it")
        print("  used to accept any non-empty string: a test running against the real")
        print("  $HOME wrote https://example.invalid/abc into live session state and the")
        print("  next Stop appended it to a real notification. http(s) only, a host with")
        print("  a dot, no whitespace, and the RFC 2606 reserved TLDs refused. A")
        print("  rejection logs, exits 0, and leaves any gate already pending alone.")
        print()
        print("  Behind the block, a turn that ends with the marker set anyway still")
        print("  notifies REGARDLESS of arming -- the same exception a blocking")
        print("  question gets, because the user is owed a decision either way. That")
        print("  marker is cleared only when a notification actually reaches the user:")
        print("  a failed send, a rate-limited turn or quiet hours all leave it set so")
        print("  the next turn retries.")
        print()
        print("cases:")
        for label, _ in CASES:
            print("  %s" % label)
        return 0

    broken = {}
    with tempfile.TemporaryDirectory() as directory:
        for profile in PROFILES:
            failures = run(profile, directory)
            if failures:
                broken[profile] = failures

    print("plan gate notification")
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
