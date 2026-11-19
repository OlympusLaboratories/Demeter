#!/usr/bin/env python3
import calendar
import json
import os
import re
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
CLAUDE = os.path.join(HOME, ".claude")
CONFIG_PATH = os.path.join(CLAUDE, "notify.json")
SENDER = os.path.join(CLAUDE, "scripts", "notify-send.sh")
STATE = os.path.join(CLAUDE, "notify-state")
AWAY_PATH = os.path.join(STATE, "away.json")
SESSIONS = os.path.join(STATE, "sessions")
LOG_PATH = os.path.join(STATE, "notify.log")
LOG_LIMIT = 1024 * 1024
PLACEHOLDER = "REPLACE_ME"
SEND_TIMEOUT = 10
BODY_LIMIT = 1200
TAIL_CHUNK = 262144
TAIL_LIMIT = 8 * 1024 * 1024

DEFAULTS = {
    "min_turn_seconds": 60,
    "min_interval_seconds": 30,
    "quiet_hours": None,
    "events": {
        "stop": True,
        "permission": True,
        "question": True,
        "idle": True,
        "failure": True,
    },
}

NOTIFICATION_KINDS = {
    "permission_prompt": ("permission", "needs permission"),
    "idle_prompt": ("idle", "waiting on you"),
    "agent_needs_input": ("question", "needs input"),
    "agent_completed": ("stop", "finished"),
    "elicitation_dialog": ("question", "needs input"),
    "elicitation_url_dialog": ("question", "needs input"),
}

QUESTION_TOOLS = {"AskUserQuestion", "ExitPlanMode"}

DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def log(message):
    try:
        os.makedirs(STATE, exist_ok=True)
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > LOG_LIMIT:
            os.replace(LOG_PATH, LOG_PATH + ".1")
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        with open(LOG_PATH, "a") as handle:
            handle.write("%s %s\n" % (stamp, message))
    except OSError:
        pass


def read_json(path, fallback=None):
    try:
        with open(path) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return fallback


def write_json(path, value):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = "%s.%d" % (path, os.getpid())
        with open(tmp, "w") as handle:
            json.dump(value, handle)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def has_placeholder(value):
    if isinstance(value, str):
        return PLACEHOLDER in value
    if isinstance(value, dict):
        return any(has_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(has_placeholder(item) for item in value)
    return False


def load_config():
    raw = read_json(CONFIG_PATH)
    if not isinstance(raw, dict):
        return None, "no config at %s" % CONFIG_PATH
    transport = raw.get("transport")
    if not transport:
        return None, "config has no transport"
    settings = raw.get(transport)
    if not isinstance(settings, dict):
        return None, "config has no %s section" % transport
    if not any(str(v).strip() for v in settings.values()):
        return None, "%s section is empty" % transport
    if has_placeholder(settings):
        return None, "%s section still has %s" % (transport, PLACEHOLDER)
    merged = dict(DEFAULTS)
    merged.update(raw)
    events = dict(DEFAULTS["events"])
    if isinstance(raw.get("events"), dict):
        events.update(raw["events"])
    merged["events"] = events
    return merged, None


def parse_duration(text):
    match = re.fullmatch(r"(\d+)\s*([smhd]?)", text.strip().lower())
    if not match:
        return None
    return int(match.group(1)) * DURATION_UNITS[match.group(2) or "m"]


def away_until():
    state = read_json(AWAY_PATH)
    if not isinstance(state, dict) or not state.get("away"):
        return None, False
    until = state.get("until")
    if until is None:
        return None, True
    if time.time() >= until:
        return None, False
    return until, True


def describe_away():
    until, active = away_until()
    if not active:
        return "back"
    if until is None:
        return "away (no expiry)"
    return "away for another %s" % human_duration(until - time.time())


def human_duration(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm" % (seconds // 60)
    if seconds < 86400:
        return "%dh%dm" % (seconds // 3600, (seconds % 3600) // 60)
    return "%dd%dh" % (seconds // 86400, (seconds % 86400) // 3600)


def in_quiet_hours(config):
    window = config.get("quiet_hours")
    if not isinstance(window, (list, tuple)) or len(window) != 2:
        return False
    try:
        start, end = int(window[0]), int(window[1])
    except (TypeError, ValueError):
        return False
    hour = time.localtime().tm_hour
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def git(cwd, *args):
    try:
        done = subprocess.run(
            ("git", "-C", cwd) + args,
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def repo_label(cwd):
    if not cwd or not os.path.isdir(cwd):
        return os.path.basename(cwd or "") or "?"
    top = git(cwd, "rev-parse", "--show-toplevel")
    return os.path.basename(top or cwd) or "?"


def branch_label(cwd):
    if not cwd or not os.path.isdir(cwd):
        return None
    head = git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    return head if head and head != "HEAD" else None


def session_path(session_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", session_id or "unknown")[:80]
    return os.path.join(SESSIONS, safe + ".json")


def clip(text, limit=BODY_LIMIT):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n… (%d more chars)" % (len(text) - limit)


def epoch_of(stamp):
    try:
        return calendar.timegm(time.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def handoff_epoch(chunk):
    asked = set()
    newest = None
    for line in chunk.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if record.get("isSidechain"):
            continue
        kind = record.get("type")
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if kind == "assistant":
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and block.get("name") in QUESTION_TOOLS:
                    asked.add(block.get("id"))
            continue
        if kind != "user" or record.get("isMeta"):
            continue
        if record.get("toolUseResult") is not None and not answers_question(content, asked):
            continue
        when = epoch_of(record.get("timestamp"))
        if when is not None:
            newest = when
    return newest


def answers_question(content, asked):
    if not asked or not isinstance(content, list):
        return False
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_result" and block.get("tool_use_id") in asked:
            return True
    return False


def turn_seconds(transcript_path):
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    try:
        ended = os.path.getmtime(transcript_path)
        with open(transcript_path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            window = TAIL_CHUNK
            while True:
                start = max(0, size - window)
                handle.seek(start)
                chunk = handle.read(size - start).decode("utf-8", "replace")
                if start:
                    chunk = chunk.split("\n", 1)[-1]
                began = handoff_epoch(chunk)
                if began is not None:
                    return max(0.0, ended - began)
                if start == 0 or window >= TAIL_LIMIT:
                    return None
                window *= 4
    except OSError:
        return None


def send(envelope):
    if not os.access(SENDER, os.X_OK):
        return None, "sender missing at %s" % SENDER
    try:
        done = subprocess.run(
            [SENDER, "send"],
            input=json.dumps(envelope),
            capture_output=True, text=True, timeout=SEND_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return None, "sender failed: %s" % error
    if done.returncode != 0:
        return None, "sender exit %d: %s" % (done.returncode, (done.stderr or "").strip()[:200])
    reply = {}
    try:
        reply = json.loads(done.stdout or "{}")
    except ValueError:
        pass
    return reply.get("thread"), None


def classify(payload):
    event = payload.get("hook_event_name")
    if event == "Stop":
        return "stop", "finished"
    if event == "StopFailure":
        reason = payload.get("reason") or payload.get("error")
        return "failure", "stopped (%s)" % reason if reason else "stopped with an error"
    if event == "PreToolUse":
        if payload.get("tool_name") in QUESTION_TOOLS:
            return "question", "is asking you a question"
        return None, None
    if event == "Notification":
        kind, label = NOTIFICATION_KINDS.get(payload.get("notification_type"), (None, None))
        return kind, label
    return None, None


def body_for(kind, payload):
    if kind == "question":
        tool_input = payload.get("tool_input")
        if isinstance(tool_input, dict):
            questions = tool_input.get("questions")
            if isinstance(questions, list) and questions:
                asked = [q.get("question") for q in questions if isinstance(q, dict)]
                asked = [q for q in asked if q]
                if asked:
                    return "\n".join("• " + q for q in asked)
            if payload.get("tool_name") == "ExitPlanMode":
                return "Waiting for plan approval."
    if kind == "failure":
        detail = payload.get("message") or payload.get("last_assistant_message")
        return detail or "The session stopped before finishing. It may need restarting."
    return payload.get("message") or payload.get("last_assistant_message") or ""


def handle(payload):
    if payload.get("agent_id") or payload.get("agent_type"):
        return "skip: subagent"

    kind, label = classify(payload)
    if not kind:
        return "skip: unhandled %s/%s" % (
            payload.get("hook_event_name"), payload.get("notification_type"))

    config, problem = load_config()
    if not config:
        return "skip: %s" % problem

    if not config["events"].get(kind, True):
        return "skip: %s disabled" % kind

    if in_quiet_hours(config):
        return "skip: quiet hours"

    _, away = away_until()

    if payload.get("hook_event_name") == "Stop" and not away:
        elapsed = turn_seconds(payload.get("transcript_path"))
        minimum = config["min_turn_seconds"]
        if elapsed is not None and elapsed < minimum:
            return "skip: turn %.0fs < %ss" % (elapsed, minimum)
        if elapsed is None:
            return "skip: turn length unknown"

    session_id = payload.get("session_id") or "unknown"
    state = read_json(session_path(session_id), {}) or {}
    now = time.time()
    last = state.get("last_sent")
    if isinstance(last, (int, float)) and now - last < config["min_interval_seconds"]:
        return "skip: rate limited (%.0fs ago)" % (now - last)

    cwd = payload.get("cwd") or os.getcwd()
    repo = repo_label(cwd)
    branch = branch_label(cwd)
    envelope = {
        "title": "%s %s" % (repo, label),
        "body": clip(body_for(kind, payload)),
        "session": session_id[:8],
        "repo": repo,
        "branch": branch,
        "level": kind,
        "cwd": cwd,
        "thread": state.get("thread"),
        "away": away,
    }

    thread, problem = send(envelope)
    if problem:
        return "error: %s" % problem

    state["last_sent"] = now
    state["last_kind"] = kind
    if thread:
        state["thread"] = thread
    write_json(session_path(session_id), state)
    return "sent %s for %s" % (kind, repo)


def cmd_away(args):
    if args and args[0] == "status":
        print(describe_away())
        return 0
    if args and args[0] in ("off", "back"):
        write_json(AWAY_PATH, {"away": False, "until": None})
        print("back")
        return 0
    until = None
    if args:
        seconds = parse_duration(args[0])
        if seconds is None:
            print("usage: notify.py --away [<duration>|off|status]", file=sys.stderr)
            return 2
        until = time.time() + seconds
    write_json(AWAY_PATH, {"away": True, "until": until})
    print(describe_away())
    return 0


def cmd_test():
    config, problem = load_config()
    if not config:
        print("notify is dormant: %s" % problem)
        print("fill in %s to switch it on" % CONFIG_PATH)
        return 1
    if not os.access(SENDER, os.X_OK):
        print("sender missing or not executable: %s" % SENDER)
        return 1
    done = subprocess.run([SENDER, "check"], capture_output=True, text=True, timeout=30)
    output = (done.stdout or "").strip() or (done.stderr or "").strip()
    print(output or ("ok" if done.returncode == 0 else "failed"))
    print("away state: %s" % describe_away())
    return done.returncode


def main():
    args = sys.argv[1:]
    if args and args[0] == "--away":
        return cmd_away(args[1:])
    if args and args[0] == "--test":
        return cmd_test()
    if args:
        print("usage: notify.py [--test | --away [<duration>|off|status]]", file=sys.stderr)
        return 2
    payload = json.load(sys.stdin)
    log("%s %s" % (payload.get("hook_event_name"), handle(payload)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        if "--test" in sys.argv:
            raise
        log("crash: %r" % (error,))
        sys.exit(0)
