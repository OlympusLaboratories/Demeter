#!/usr/bin/env python3
import calendar
import glob
import json
import os
import re
import shutil
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
SEND_TIMEOUT = 30
BODY_LIMIT = 1200
TAIL_CHUNK = 262144
TAIL_LIMIT = 8 * 1024 * 1024
SUMMARY_MODEL = "claude-haiku-4-5-20251001"
SUMMARY_MAX_WORDS = 45
SUMMARY_MIN_CHARS = 200
SUMMARY_MAX_INPUT = 8000
SUMMARY_TIMEOUT = 180
CONDENSE_LIMIT = 240
SUMMARY_GUARD = "NOTIFY_SUMMARIZING"
SUMMARY_SETTINGS = os.path.join(STATE, "summarize-settings.json")
SUMMARY_CWD = os.path.join(STATE, "summarize-cwd")
CLI_CANDIDATES = (
    "~/.claude/local/claude",
    "~/.local/bin/claude",
    "/opt/homebrew/bin/claude",
    "/usr/local/bin/claude",
    "/usr/bin/claude",
    "~/.npm-global/bin/claude",
    "~/.local/share/mise/shims/claude",
    "~/.volta/bin/claude",
    "~/.bun/bin/claude",
)
CLI_SEARCH_PATH = (
    "~/.claude/local",
    "~/.local/bin",
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
    "~/.npm-global/bin",
    "~/.local/share/mise/shims",
)

SUMMARY_PROMPT = (
    "Rewrite the text below as ONE push-notification line for a phone lock screen."
    " Reply with that line only: no markdown, no quotes, no preamble, no trailing list."
    " Use at most %d words."
    " Lead with the outcome, naming concrete nouns from the actual work."
    " Then say what the user has to do, or state plainly that nothing is needed."
    " Never invent a detail that is not in the text below.\n\n%s"
)

DEFAULTS = {
    "min_turn_seconds": 60,
    "min_interval_seconds": 30,
    "quiet_hours": None,
    "only_when_armed": True,
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


def usable(value):
    text = str(value or "").strip()
    return text and PLACEHOLDER not in text


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
    if not any(usable(v) for v in settings.values()):
        return None, "%s section is empty or still says %s" % (transport, PLACEHOLDER)
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


def scan_tail(transcript_path, finder):
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    try:
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
                found = finder(chunk)
                if found is not None:
                    return found
                if start == 0 or window >= TAIL_LIMIT:
                    return None
                window *= 4
    except OSError:
        return None


def handoff_at(transcript_path):
    return scan_tail(transcript_path, handoff_epoch)


def title_in(chunk):
    generated = None
    for line in reversed(chunk.splitlines()):
        if '"ai-title"' not in line and '"custom-title"' not in line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        if record.get("type") == "custom-title":
            chosen = record.get("customTitle")
            if isinstance(chosen, str) and chosen.strip():
                return chosen.strip()
        elif record.get("type") == "ai-title" and generated is None:
            chosen = record.get("aiTitle")
            if isinstance(chosen, str) and chosen.strip():
                generated = chosen.strip()
    return generated


def session_title(transcript_path):
    return scan_tail(transcript_path, title_in)


def transcript_for(session_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", session_id or "")
    if not safe:
        return None
    found = glob.glob(os.path.join(HOME, ".claude", "projects", "*", safe + ".jsonl"))
    if not found:
        return None
    return max(found, key=lambda p: os.path.getmtime(p))


def turn_seconds(transcript_path):
    began = handoff_at(transcript_path)
    if began is None:
        return None
    try:
        return max(0.0, os.path.getmtime(transcript_path) - began)
    except OSError:
        return None


def armed_state(state):
    if isinstance(state.get("armed_at"), (int, float)):
        return True, None
    return False, "session not armed - no ping has opted it in"


def armed_sessions():
    try:
        names = os.listdir(SESSIONS)
    except OSError:
        return []
    found = []
    for name in sorted(names):
        if not name.endswith(".json"):
            continue
        state = read_json(os.path.join(SESSIONS, name))
        if isinstance(state, dict) and isinstance(state.get("armed_at"), (int, float)):
            found.append(name[:-5])
    return found


def disarm_sessions():
    cleared = 0
    for session in armed_sessions():
        path = session_path(session)
        state = read_json(path)
        if not isinstance(state, dict):
            continue
        state.pop("armed_at", None)
        if write_json(path, state):
            cleared += 1
    return cleared


def strip_markdown(text):
    text = re.sub(r"```.*?```", " ", text or "", flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*\|.*$", " ", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"[*_>]", "", text)
    return " ".join(text.split())


def condense(text, limit=CONDENSE_LIMIT):
    flat = strip_markdown(text)
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if stop > limit // 3:
        return cut[:stop + 1]
    return cut.rstrip() + "\u2026"


def summarizer_path(settings):
    explicit = settings.get("command")
    if explicit:
        path = os.path.expanduser(str(explicit))
        return path if os.access(path, os.X_OK) else None
    for candidate in CLI_CANDIDATES:
        path = os.path.expanduser(candidate)
        if os.access(path, os.X_OK) and not os.path.isdir(path):
            return path
    search = os.pathsep.join(
        [os.path.expanduser(d) for d in CLI_SEARCH_PATH]
        + (os.environ.get("PATH") or "").split(os.pathsep))
    return shutil.which("claude", path=search)


def summarizer_env(binary):
    environ = dict(os.environ)
    environ.pop("ANTHROPIC_API_KEY", None)
    environ[SUMMARY_GUARD] = "1"
    extra = [os.path.dirname(binary)] + [os.path.expanduser(d) for d in CLI_SEARCH_PATH]
    present = (environ.get("PATH") or "").split(os.pathsep)
    environ["PATH"] = os.pathsep.join(
        [d for d in extra if d and d not in present] + present)
    return environ


def summarizer_cwd():
    try:
        os.makedirs(SUMMARY_CWD, exist_ok=True)
        return SUMMARY_CWD
    except OSError:
        return None


def summarizer_settings():
    try:
        os.makedirs(STATE, exist_ok=True)
        with open(SUMMARY_SETTINGS, "w") as handle:
            json.dump({"hooks": {}}, handle)
        return SUMMARY_SETTINGS
    except OSError:
        return None


def window(text, limit=SUMMARY_MAX_INPUT):
    if len(text) <= limit:
        return text
    head = limit * 2 // 3
    return text[:head].rstrip() + " [...] " + text[-(limit - head):].lstrip()


def summarize(text, config):
    settings = config.get("summarize")
    if not isinstance(settings, dict):
        return None, "no summarize section"
    if settings.get("enabled") is False:
        return None, "disabled"
    if os.environ.get(SUMMARY_GUARD):
        return None, "already inside a summarizer"
    binary = summarizer_path(settings)
    if not binary:
        return None, "no claude cli found"
    words = settings.get("max_words") or SUMMARY_MAX_WORDS
    argv = [
        binary, "-p",
        "--model", settings.get("model") or SUMMARY_MODEL,
        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
    ]
    bare = summarizer_settings()
    if bare:
        argv += ["--settings", bare]
    argv.append(SUMMARY_PROMPT % (words, window(strip_markdown(text))))
    try:
        done = subprocess.run(
            argv, input="", capture_output=True, text=True,
            env=summarizer_env(binary), cwd=summarizer_cwd(),
            timeout=settings.get("timeout") or SUMMARY_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, "summarizer timed out"
    except (OSError, subprocess.SubprocessError) as error:
        return None, "summarizer failed: %r" % (error,)
    if done.returncode != 0:
        return None, "summarizer exit %d: %s" % (
            done.returncode, " ".join((done.stderr or "").split())[:160])
    line = " ".join((done.stdout or "").split())
    if not line:
        return None, "summarizer returned nothing"
    parts = line.split()
    if len(parts) > words:
        line = " ".join(parts[:words]).rstrip(",;:") + "\u2026"
    return line, None


def shorten(raw, kind, config):
    text = (raw or "").strip()
    if not text:
        return "", "no body"
    if len(text) < SUMMARY_MIN_CHARS:
        return condense(text), "already short"
    line, problem = summarize(text, config)
    if line:
        return line, "summarized %d->%d chars" % (len(text), len(line))
    return condense(text), "condensed, %s" % problem


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
    session_id = payload.get("session_id") or "unknown"
    state = read_json(session_path(session_id), {}) or {}

    if not away:
        armed, reason = armed_state(state)
        if config["only_when_armed"]:
            if not armed:
                return "skip: %s" % reason
        elif payload.get("hook_event_name") == "Stop" and not armed:
            elapsed = turn_seconds(payload.get("transcript_path"))
            minimum = config["min_turn_seconds"]
            if elapsed is not None and elapsed < minimum:
                return "skip: turn %.0fs < %ss" % (elapsed, minimum)
            if elapsed is None:
                return "skip: turn length unknown"

    now = time.time()
    last = state.get("last_sent")
    if isinstance(last, (int, float)) and now - last < config["min_interval_seconds"]:
        return "skip: rate limited (%.0fs ago)" % (now - last)

    cwd = payload.get("cwd") or os.getcwd()
    repo = repo_label(cwd)
    branch = branch_label(cwd)
    body, how = shorten(body_for(kind, payload), kind, config)
    envelope = {
        "title": "%s %s" % (repo, label),
        "body": body,
        "session": session_id[:8],
        "repo": repo,
        "branch": branch,
        "level": kind,
        "session_label": session_title(payload.get("transcript_path")),
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
    return "sent %s for %s (%s)" % (kind, repo, how)


def cmd_away(args):
    if args and args[0] == "status":
        print(describe_away())
        print("sessions opted in: %d" % len(armed_sessions()))
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


def cmd_disarm(args):
    target = args[0] if args else ""
    if not target:
        print("usage: notify.py --disarm <session-id>|all", file=sys.stderr)
        return 2
    if target == "all":
        cleared = disarm_sessions()
        print("disarmed %d session%s" % (cleared, "" if cleared == 1 else "s"))
        return 0
    path = session_path(target)
    state = read_json(path)
    if not isinstance(state, dict) or state.pop("armed_at", None) is None:
        print("session %s was not armed" % target[:8])
        return 0
    write_json(path, state)
    print("disarmed session %s" % target[:8])
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
    print("sessions opted in: %d" % len(armed_sessions()))
    report_summarizer(config)
    return done.returncode


def report_summarizer(config):
    settings = config.get("summarize")
    if not isinstance(settings, dict):
        print("summarizer: no summarize section in %s" % CONFIG_PATH)
        return
    if settings.get("enabled") is False:
        print("summarizer: switched off in %s" % CONFIG_PATH)
        return
    binary = summarizer_path(settings)
    if not binary:
        print("summarizer: no claude cli found - notifications will be condensed, not summarized")
        print("  looked in: %s" % ", ".join(CLI_CANDIDATES))
        print("  set summarize.command in %s to point at it" % CONFIG_PATH)
        return
    print("summarizer: %s (model %s, %d words, %ss budget)" % (
        binary, settings.get("model") or SUMMARY_MODEL,
        settings.get("max_words") or SUMMARY_MAX_WORDS,
        settings.get("timeout") or SUMMARY_TIMEOUT))
    sample = (
        "The migration finished. I moved all fourteen cron jobs onto the new scheduler,"
        " updated the terraform module that provisions them, and the full test suite is"
        " green. There is nothing blocking and nothing for you to do, though the change"
        " is worth a look when you are back at a keyboard since it touches production"
        " scheduling. I have not committed any of it yet."
    )
    began = time.time()
    line, problem = summarize(sample, config)
    took = time.time() - began
    if line:
        print("  working, %.1fs: %s" % (took, line))
    else:
        print("  FAILED after %.1fs: %s" % (took, problem))
        print("  notifications still work; they will be condensed instead of summarized")


def main():
    args = sys.argv[1:]
    if args and args[0] == "--away":
        return cmd_away(args[1:])
    if args and args[0] == "--test":
        return cmd_test()
    if args and args[0] == "--disarm":
        return cmd_disarm(args[1:])
    if args and args[0] == "--label":
        print(session_title(transcript_for(args[1] if len(args) > 1 else "")) or "")
        return 0
    if args:
        print(
            "usage: notify.py [--test | --away [<duration>|off|status]"
            " | --disarm <session-id>|all | --label <session-id>]", file=sys.stderr)
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
