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
import urllib.parse

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
SENDER_ERR_LIMIT = 500
BODY_LIMIT = 1200
GATE_TTL = 12 * 3600
CHANGE_REQUEST_TTL = 4 * 3600
RESERVED_TLDS = ("invalid", "test", "example", "localhost")
RESTORE_URL_MAX = 2
TAIL_CHUNK = 262144
TAIL_LIMIT = 8 * 1024 * 1024
TITLE_MAX = 48
TITLE_TIMEOUT = 25
TITLE_PROMPT = (
    "Write a 3-6 word title naming what this coding session is about, from the "
    "opening request and the assistant's first reply below. Name the project or "
    "component concretely, the way a tab label would. Output the title alone: no "
    "quotes, no trailing punctuation, no preamble.\n\n%s"
)
SUMMARY_MODEL = "claude-haiku-4-5-20251001"
SUMMARY_MAX_WORDS = 68
SUMMARY_MIN_CHARS = 200
SUMMARY_MAX_INPUT = 8000
SUMMARY_TIMEOUT = 180
CONDENSE_LIMIT = 360
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
    " Never invent a detail that is not in the text below."
    " Keep any http or https URL exactly as it appears, in full — it is the only way the"
    " user can open the thing you are naming from a phone, and a change request named"
    " without its URL is not actionable.\n\n%s"
)

DEFAULTS = {
    "min_turn_seconds": 60,
    "min_interval_seconds": 30,
    "quiet_hours": None,
    "only_when_armed": True,
    "notify_when_blocked": True,
    "host_label": "",
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

BLOCKING_KINDS = {"question", "permission"}

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


def repo_root(cwd):
    # --show-toplevel answers the WORKTREE's own root, so a session in
    # .claude/worktrees/dylan/OLY-17 labels itself "OLY-17" -- the branch, not
    # the repo, and every worktree of one repo looks like a different project.
    # --git-common-dir points at the main checkout's .git from anywhere,
    # including a linked worktree, so its parent is the repository itself.
    common = git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        common = git(cwd, "rev-parse", "--git-common-dir")
        if common and not os.path.isabs(common):
            common = os.path.join(cwd, common)
    if common:
        root = os.path.dirname(os.path.realpath(common))
        if root and os.path.isdir(root):
            return root
    return git(cwd, "rev-parse", "--show-toplevel")


def repo_label(cwd, host_label=""):
    # A session rooted outside a project has no repo to name. The directory
    # basename is what the field used to fall back to, and on a box whose
    # sessions all start in one fixed directory that is the same uninformative
    # word every time. host_label replaces it with something that identifies
    # the machine instead, and stays empty everywhere it is not configured.
    #
    # A repository rooted at $HOME counts as "no project": a dotfiles-style home
    # repo answers rev-parse for every path beneath it, so without this the
    # label is the home directory's name and host_label is never reached.
    if not cwd or not os.path.isdir(cwd):
        return host_label or os.path.basename(cwd or "") or "?"
    top = repo_root(cwd)
    if top and os.path.realpath(top) != os.path.realpath(HOME):
        return os.path.basename(top) or "?"
    # Outside a project the directory is what names the session: a phone session
    # spawned in remote-root should read "remote-root", which says what kind of
    # session it is, where the machine name says only where every session runs.
    # host_label answers the one case the directory cannot -- $HOME itself.
    here = os.path.realpath(cwd)
    name = os.path.basename(here)
    if name and here != os.path.realpath(HOME):
        return name
    return host_label or name or "?"


def branch_label(cwd):
    if not cwd or not os.path.isdir(cwd):
        return None
    top = git(cwd, "rev-parse", "--show-toplevel")
    if top and os.path.realpath(top) == os.path.realpath(HOME):
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


def scan_head(transcript_path, finder):
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    try:
        with open(transcript_path, "rb") as handle:
            size = os.fstat(handle.fileno()).st_size
            window = TAIL_CHUNK
            while True:
                handle.seek(0)
                chunk = handle.read(window).decode("utf-8", "replace")
                if window < size:
                    chunk = chunk.rsplit("\n", 1)[0]
                found = finder(chunk)
                if found is not None:
                    return found
                if window >= size or window >= TAIL_LIMIT:
                    return None
                window *= 4
    except OSError:
        return None


def prompt_label(text):
    named = re.search(r"<command-name>\s*(/?[\w:.-]+)\s*</command-name>", text)
    if named:
        args = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
        text = named.group(1) + (" " + args.group(1) if args else "")
    for tag in ("system-reminder", "pasted_content", "ide_selection",
                "command-message", "command-name", "command-args",
                "local-command-stdout", "local-command-stderr"):
        text = re.sub(r"<%s[^>]*>.*?</%s>" % (tag, tag), " ", text, flags=re.S)
    text = re.sub(r"<[^>]{1,40}>", " ", text)
    text = " ".join(text.split())
    if not text:
        return None
    if len(text) > TITLE_MAX:
        text = (text[:TITLE_MAX].rsplit(" ", 1)[0] or text[:TITLE_MAX]) + "\u2026"
    return text


def first_prompt_in(chunk):
    for line in chunk.splitlines():
        if '"last-prompt"' not in line and '"user"' not in line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        if record.get("type") == "last-prompt":
            text = record.get("lastPrompt")
            if isinstance(text, str) and text.strip():
                found = prompt_label(text)
                if found:
                    return found
        elif record.get("type") == "user" and not record.get("isMeta"):
            content = (record.get("message") or {}).get("content")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = " ".join(
                    block.get("text", "") for block in content
                    if isinstance(block, dict) and block.get("type") == "text")
            else:
                continue
            if text.strip():
                found = prompt_label(text)
                if found:
                    return found
    return None


def opening_exchange_in(chunk):
    prompt = None
    reply = None
    for line in chunk.splitlines():
        if ('"last-prompt"' not in line and '"user"' not in line
                and '"assistant"' not in line):
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        kind = record.get("type")
        if prompt is None and kind == "last-prompt":
            text = record.get("lastPrompt")
            if isinstance(text, str) and text.strip():
                prompt = text.strip()
        elif kind in ("user", "assistant"):
            if kind == "user" and record.get("isMeta"):
                continue
            content = (record.get("message") or {}).get("content")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = " ".join(
                    block.get("text", "") for block in content
                    if isinstance(block, dict) and block.get("type") == "text")
            else:
                continue
            if not text.strip():
                continue
            if kind == "user" and prompt is None:
                prompt = text.strip()
            elif kind == "assistant" and reply is None:
                reply = text.strip()
        if prompt and reply:
            break
    return (prompt, reply) if prompt else None


def generate_title(transcript_path, config):
    if os.environ.get(SUMMARY_GUARD):
        return None, "inside a summarizer"
    settings = config.get("summarize") if isinstance(config, dict) else None
    if not isinstance(settings, dict) or settings.get("enabled") is False:
        return None, "summarize disabled"
    binary = summarizer_path(settings)
    if not binary:
        return None, "no claude cli found"
    found = scan_head(transcript_path, opening_exchange_in)
    if not found:
        return None, "no opening exchange"
    prompt, reply = found
    text = "Opening request: %s" % condense(prompt, 600)
    if reply:
        text += "\n\nAssistant's first reply: %s" % condense(reply, 600)
    argv = [
        binary, "-p",
        "--model", settings.get("model") or SUMMARY_MODEL,
        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
    ]
    bare = summarizer_settings()
    if bare:
        argv += ["--settings", bare]
    argv.append(TITLE_PROMPT % text)
    try:
        done = subprocess.run(
            argv, input="", capture_output=True, text=True,
            env=summarizer_env(binary), cwd=summarizer_cwd(),
            timeout=settings.get("title_timeout") or TITLE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, "title timed out"
    except (OSError, subprocess.SubprocessError) as error:
        return None, "title failed: %r" % (error,)
    if done.returncode != 0:
        return None, "title exit %d" % done.returncode
    line = " ".join((done.stdout or "").split()).strip().strip('"\u201c\u201d')
    line = line.rstrip(".")
    if not line or len(line) > 80:
        return None, "title unusable"
    return line, "generated"


def session_title(transcript_path, config=None, state=None):
    found = scan_tail(transcript_path, title_in)
    if found:
        return found
    if isinstance(state, dict):
        cached = state.get("title")
        if isinstance(cached, str) and cached.strip():
            return cached.strip()
    if config is not None:
        made, why = generate_title(transcript_path, config)
        if made:
            if isinstance(state, dict):
                state["title"] = made
            return made
        log("title: %s" % why)
    return scan_head(transcript_path, first_prompt_in)


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


def keep_url(match):
    bang, label, target = match.group(1), match.group(2), (match.group(3) or "").strip()
    if bang or not re.match(r"https?://", target):
        return label
    if target in label:
        return label
    return ("%s %s" % (label, target)).strip()


def strip_markdown(text):
    text = re.sub(r"```.*?```", " ", text or "", flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"(!?)\[([^\]]*)\]\(([^)]*)\)", keep_url, text)
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


def restore_urls(line, source):
    present = set(urls_in(line))
    missing = [url for url in dict.fromkeys(urls_in(source))
               if url not in present]
    if not missing:
        return line
    ranked = ([u for u in missing if CHANGE_REQUEST_RE.search(u)]
              + [u for u in missing if not CHANGE_REQUEST_RE.search(u)])
    return (line.rstrip() + " " + " ".join(ranked[:RESTORE_URL_MAX])).strip()


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
    flat = strip_markdown(text)
    argv.append(SUMMARY_PROMPT % (words, window(flat)))
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
    return restore_urls(line, flat), None


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
        return None, "sender exit %d: %s" % (
            done.returncode, (done.stderr or "").strip()[:SENDER_ERR_LIMIT])
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


CHANGE_REQUEST_RE = re.compile(
    r"https?://[^\s<>\"')\]]+?/(?:pull/|-/merge_requests/)\d+")
CHANGE_REQUEST_ANSWERED_RE = re.compile(
    r"\\?\"(?:html_url|web_url)\\?\"\s*:\s*\\?\""
    r"(https?://[^\s<>\"'\\)\]]+?/(?:pull/|-/merge_requests/)\d+)")
CHANGE_REQUEST_OBJECT_RE = re.compile(
    r"\{[^{}]*?\\?\"(?:html_url|web_url)\\?\"\s*:\s*\\?\""
    r"(https?://[^\s<>\"'\\)\]]+?/(?:pull/|-/merge_requests/)\d+)"
    r"[^{}]*\}")
RECORD_BRANCH_RE = re.compile(
    r"\\?\"(?:head|source_branch)\\?\"\s*:\s*\\?\"([^\"\\]+)")
RECORD_STATE_RE = re.compile(
    r"\\?\"state\\?\"\s*:\s*\\?\"([^\"\\]+)")
CHANGE_REQUEST_NAMED_RE = re.compile(
    r"\b[MP]R\b"
    r"|(?i:\b[MP]Rs?\s*#?\d+)"
    r"|(?i:\b(?:pull|merge)\s+requests?\s*#?\d*)")
CLOSED_STATES = ("closed", "merged")
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")


def urls_in(text):
    return [url.rstrip(".,;:") for url in URL_RE.findall(text or "")]


def closed_change_request(state):
    return isinstance(state, str) and state.strip().lower() in CLOSED_STATES


def plausible_url(url):
    text = (url or "").strip()
    if not re.match(r"^https?://\S+$", text):
        return False
    try:
        host = (urllib.parse.urlparse(text).hostname or "").lower()
    except ValueError:
        return False
    if "." not in host or host.endswith("."):
        return False
    return host.rsplit(".", 1)[-1] not in RESERVED_TLDS


def remote_slug(cwd):
    # "owner/repo" for the session's own remote, which is what separates this
    # run's change request from any other URL the transcript happens to carry.
    url = git(cwd or os.getcwd(), "remote", "get-url", "origin")
    if not url:
        return None
    url = re.sub(r"\.git/?$", "", url.strip())
    match = re.search(r"[:/]([^/:]+/[^/]+)$", url)
    return match.group(1).lower() if match else None


def change_request_records(chunk):
    text = chunk or ""
    detail = {}
    for match in CHANGE_REQUEST_OBJECT_RE.finditer(text):
        body = match.group(0)
        branch = RECORD_BRANCH_RE.search(body)
        state = RECORD_STATE_RE.search(body)
        detail[match.group(1)] = (
            branch.group(1) if branch else None,
            state.group(1) if state else None,
        )
    records = []
    for url in CHANGE_REQUEST_ANSWERED_RE.findall(text):
        branch, state = detail.get(url, (None, None))
        records.append({"url": url, "branch": branch, "state": state})
    return records


def change_request_answered_in(chunk, tier, slug=None, branch=None):
    records = [r for r in change_request_records(chunk)
               if not closed_change_request(r["state"])]
    if not records:
        return None
    if tier == "branch":
        if not branch:
            return None
        mine = [r for r in records if r["branch"] and r["branch"] == branch]
        return mine[-1]["url"] if mine else None
    if tier == "slug":
        if not slug:
            return None
        local = [r for r in records if slug in r["url"].lower()]
        return local[-1]["url"] if local else None
    distinct = list(dict.fromkeys(r["url"] for r in records))
    return distinct[0] if len(distinct) == 1 else None


def change_request_in(chunk, slug=None):
    # Recency alone is not enough: an example URL, a link to somebody else's
    # change request, or this hook's own test fixtures all match the shape.
    # Only a URL carrying the session's own owner/repo can be this run's, and
    # where no remote resolves the honest answer is none rather than a guess.
    closed = set(r["url"] for r in change_request_records(chunk)
                 if closed_change_request(r["state"]))
    found = [u.rstrip(".,;:") for u in CHANGE_REQUEST_RE.findall(chunk or "")]
    if slug:
        found = [u for u in found
                 if slug in u.lower() and u not in closed]
    else:
        found = []
    return found[-1] if found else None


def change_request_closed_in(chunk, url):
    for record in change_request_records(chunk):
        if record["url"] == url and closed_change_request(record["state"]):
            return True
    return None


def cached_change_request(state):
    if not isinstance(state, dict):
        return None
    cached = state.get("change_request")
    if isinstance(cached, str):
        return cached.strip() or None
    if not isinstance(cached, dict):
        return None
    url = cached.get("url")
    if not isinstance(url, str) or not url.strip():
        return None
    at = cached.get("at")
    if isinstance(at, (int, float)) and time.time() - at > CHANGE_REQUEST_TTL:
        log("dropped a change request cached %s ago" % human_duration(time.time() - at))
        return None
    return url.strip()


def change_request_for(transcript_path, state, cwd=None):
    # Re-read on every call. A session opens more than one change request over
    # its life, so a value cached on first sight is the oldest one rather than
    # the current one, and it feeds itself: once the state file is read back
    # into the transcript, the stale URL is also the most recent URL in it.
    # The cache is therefore only a fallback for a scan that found nothing.
    where = cwd or os.getcwd()
    slug = remote_slug(where)
    branch = branch_label(where)
    found = None
    for tier in ("branch", "slug", "lone"):
        found = scan_tail(
            transcript_path,
            lambda chunk, t=tier: change_request_answered_in(
                chunk, t, slug, branch),
        )
        if found:
            break
    if not found and slug:
        found = scan_tail(
            transcript_path, lambda chunk: change_request_in(chunk, slug)
        )
    if not found:
        cached = cached_change_request(state)
        if cached and scan_tail(
                transcript_path,
                lambda chunk: change_request_closed_in(chunk, cached)):
            log("dropped a cached change request the transcript shows closed")
            return None
        return cached
    if isinstance(state, dict):
        state["change_request"] = {"url": found, "at": time.time()}
    return found


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


def build_envelope(level, title, body, repo, branch, session_id, label, cwd, thread):
    envelope = {
        "title": title,
        "body": body,
        "level": level,
        "repo": repo,
        "cwd": cwd,
    }
    if label:
        envelope["session_label"] = label
    if branch:
        envelope["branch"] = branch
    if session_id:
        envelope["session"] = session_id[:8]
    if thread:
        envelope["thread"] = thread
    return envelope


STATE_CARRIED = ("title", "change_request", "thread")


def merge_state(path, updates=(), drop=()):
    state = read_json(path, {}) or {}
    if not isinstance(state, dict):
        state = {}
    for key, value in (updates.items() if isinstance(updates, dict) else updates):
        state[key] = value
    for key in drop:
        state.pop(key, None)
    return write_json(path, state)


def record_sent(session_id, state, now, kind=None, thread=None, arm=False, drop=()):
    updates = dict((key, state[key]) for key in STATE_CARRIED if key in state)
    if kind is not None:
        updates["last_sent"] = now
        updates["last_kind"] = kind
    if arm:
        updates["armed_at"] = now
    if thread:
        updates["thread"] = thread
    return merge_state(session_path(session_id), updates, drop)


def append_change_request(body, transcript_path, state, cwd):
    text = body or ""
    if CHANGE_REQUEST_RE.search(text):
        return body, False
    if not CHANGE_REQUEST_NAMED_RE.search(text):
        return body, False
    link = change_request_for(transcript_path, state, cwd)
    if not link:
        return body, False
    return (text.rstrip() + "\n" + link).strip(), True


GATE_HOLD = (
    "Do not end this turn yet. A plan was published at %s and nothing has asked"
    " the user to approve it \u2014 publishing a plan is a promise of a question."
    " Send the link as a message on its own, then call AskUserQuestion with"
    " Approve and Change something, in this turn. If the plan was already"
    " approved, or it needs no approval, run"
    " `~/.claude/hooks/notify.py --gate-clear` and end the turn again."
)


CHECKLIST_STALE_STOPS = 3

CHECKLIST_HOLD = (
    "Do not end this turn yet. The run checklist at %s still shows %s, and %s."
    " The page is what the user and the next agent read to see where this run"
    " is, so a page behind the run is the same defect as a run with nothing in"
    " flight. Tick what is actually done with"
    " `~/.claude/scripts/run-checklist.py tick <items.json> <id>=<state> --publish`"
    " in this turn. If the run is genuinely finished or abandoned, run"
    " `~/.claude/hooks/notify.py --checklist-clear --force` and end the turn"
    " again — a bare clear refuses while items are open."
    " `--checklist-status` reports the marker without touching it."
)


def checklist_reason(gate):
    stops = gate.get("stops")
    if gate.get("verdict") == "stalled":
        return "nothing is in flight"
    if isinstance(stops, int) and stops >= CHECKLIST_STALE_STOPS:
        return ("it has not been written since %d turns ended"
                % CHECKLIST_STALE_STOPS)
    return ""


def checklist_gate(payload):
    if payload.get("agent_id") or payload.get("agent_type"):
        return None
    session_id = payload.get("session_id") or ""
    if not session_id:
        return None
    path = session_path(session_id)
    state = read_json(path, {}) or {}
    if not isinstance(state, dict):
        return None
    gate = state.get("checklist_pending")
    if not isinstance(gate, dict) or not gate.get("open"):
        return None
    if gate_expired(gate):
        merge_state(path, drop=("checklist_pending",))
        log("dropped a stale run checklist marker")
        return None
    if payload.get("hook_event_name") != "Stop" or payload.get("stop_hook_active"):
        return None
    if gate.get("held"):
        return None

    reason = checklist_reason(gate)
    if not reason:
        merge_state(path, {"checklist_pending":
                           dict(gate, stops=int(gate.get("stops") or 0) + 1)})
        return None

    if not merge_state(path, {"checklist_pending": dict(gate, held=time.time())}):
        return None
    open_items = ", ".join(str(entry) for entry in gate["open"][:6])
    return CHECKLIST_HOLD % (gate.get("url") or "the published page", open_items, reason)


def gate_expired(gate):
    at = gate.get("at") if isinstance(gate, dict) else None
    if not isinstance(at, (int, float)):
        return 0
    age = time.time() - at
    return age if age > GATE_TTL else 0


def drop_expired_gate(path, gate):
    age = gate_expired(gate)
    if not age:
        return False
    merge_state(path, drop=("gate_pending",))
    log("dropped a plan gate published %s ago" % human_duration(age))
    return True


def plan_gate(payload):
    if payload.get("agent_id") or payload.get("agent_type"):
        return None
    session_id = payload.get("session_id") or ""
    if not session_id:
        return None
    path = session_path(session_id)
    state = read_json(path, {}) or {}
    if not isinstance(state, dict):
        return None
    gate = state.get("gate_pending")
    if not isinstance(gate, dict) or not gate.get("url"):
        return None
    if drop_expired_gate(path, gate):
        return None

    event = payload.get("hook_event_name")
    if event == "PreToolUse" and payload.get("tool_name") in QUESTION_TOOLS:
        merge_state(path, drop=("gate_pending",))
        log("gate cleared by %s" % payload.get("tool_name"))
        return None
    if event != "Stop" or payload.get("stop_hook_active") or gate.get("held"):
        return None

    if not merge_state(path, {"gate_pending": dict(gate, held=time.time())}):
        return None
    return GATE_HOLD % gate["url"]


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

    gate = state.get("gate_pending")
    if isinstance(gate, dict) and drop_expired_gate(session_path(session_id), gate):
        state.pop("gate_pending", None)
        gate = None
    gate_url = gate.get("url") if isinstance(gate, dict) else None
    stranded_gate = bool(gate_url) and payload.get("hook_event_name") == "Stop"
    if stranded_gate:
        label = "published a plan and is waiting on you"

    unarmed_blocking = False
    if not away:
        armed, reason = armed_state(state)
        if (not armed and config["notify_when_blocked"]
                and (kind in BLOCKING_KINDS or stranded_gate)):
            unarmed_blocking = True
        elif config["only_when_armed"]:
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
    repo = repo_label(cwd, config["host_label"])
    branch = branch_label(cwd)
    body, how = shorten(body_for(kind, payload), kind, config)
    envelope = build_envelope(
        kind, "%s %s" % (repo, label), body, repo, branch, session_id,
        session_title(payload.get("transcript_path"), config, state),
        cwd, state.get("thread"))
    envelope["away"] = away

    # A session's first notification becomes the thread root, and the root is
    # the only message carrying the repo and the title. When that first event is
    # a permission prompt the thread opens on a demand, with nothing saying which
    # session is asking -- observed as a root reading only "Claude needs your
    # permission to use Bash". So anchor the thread first: an empty body renders
    # as the header alone, and the event follows as a reply beneath it.
    if not envelope.get("thread"):
        anchor = dict(envelope, body="")
        anchor.pop("thread", None)
        anchored, anchor_problem = send(anchor)
        if anchored:
            envelope["thread"] = anchored
            state["thread"] = anchored
            log("anchored thread %s for %s" % (anchored, repo))
        else:
            log("anchor failed (%s); sending as root" % anchor_problem)

    # Naming a change request without its link leaves the user hunting for it
    # from a phone, and every rule telling a skill to include one is an
    # instruction a model can forget. The transcript already holds the URL, so
    # the hook appends it rather than trusting the body to carry it.
    if stranded_gate and gate_url not in (envelope.get("body") or ""):
        envelope["body"] = (
            (envelope.get("body") or "").rstrip() + "\n" + gate_url).strip()

    envelope["body"], appended = append_change_request(
        envelope.get("body"), payload.get("transcript_path"), state, cwd)
    if appended:
        log("appended change request link for %s" % repo)

    thread, problem = send(envelope)
    if problem:
        return "error: %s" % problem

    spent = ("gate_pending",) if (stranded_gate or kind == "question") else ()
    record_sent(session_id, state, now, kind=kind, thread=thread, drop=spent)
    if unarmed_blocking:
        how += "; unarmed: blocking gate"
    if stranded_gate:
        how += "; stranded plan gate"
    return "sent %s for %s (%s)" % (kind, repo, how)


def checklist_marker(session_id):
    state = read_json(session_path(session_id), {}) or {}
    if not isinstance(state, dict):
        return {}
    gate = state.get("checklist_pending")
    return gate if isinstance(gate, dict) else {}


def checklist_ids(gate, field):
    found = gate.get(field)
    if not isinstance(found, list):
        return []
    return [str(entry) for entry in found]


def describe_open(ids, verb):
    return "%d item%s %s open: %s" % (
        len(ids), "" if len(ids) == 1 else "s", verb, ", ".join(ids))


def cmd_checklist_clear(args):
    rest = [arg for arg in args if arg != "--force"]
    forced = len(rest) != len(args)
    session_id = (rest[0] if rest else "").strip() or session_from_env()
    if not session_id:
        print("no session id resolved: nothing to clear", file=sys.stderr)
        return 0

    gate = checklist_marker(session_id)
    if not gate:
        print("no run checklist marker for this session: nothing to clear")
        return 0

    where = gate.get("url") or "an unpublished checklist"
    open_ids = checklist_ids(gate, "open")
    expired = gate_expired(gate)

    if open_ids and not forced and not expired:
        print("refusing to clear the run checklist marker for %s" % where,
              file=sys.stderr)
        print(describe_open(open_ids, "are still"), file=sys.stderr)
        print("pass --force if this run is genuinely finished or abandoned,"
              " or tick what is done", file=sys.stderr)
        log("refused to clear the run checklist marker for %s: %d open"
            % (session_id[:8], len(open_ids)))
        return 1

    merge_state(session_path(session_id), drop=("checklist_pending",))
    log("run checklist marker cleared for %s" % session_id)
    print("cleared the run checklist marker for %s" % where)
    if expired:
        print("it had expired %s ago, so the gate would not have held on it"
              % human_duration(expired))
    elif open_ids:
        print(describe_open(open_ids, "were still"))
    else:
        print("nothing was outstanding")
    return 0


def cmd_checklist_status(args):
    session_id = (args[0] if args else "").strip() or session_from_env()
    if not session_id:
        print("not armed: no session id resolved", file=sys.stderr)
        return 1

    gate = checklist_marker(session_id)
    if not gate:
        print("not armed: no run checklist marker for this session")
        return 1

    where = gate.get("url") or "an unpublished checklist"
    expired = gate_expired(gate)
    if expired:
        print("not armed: the marker for %s expired %s ago"
              % (where, human_duration(expired)))
    else:
        print("armed: %s" % where)

    stops = gate.get("stops")
    stops = stops if isinstance(stops, int) else 0
    print("verdict %s, %d turn end%s since the last write, %s"
          % (gate.get("verdict") or "unknown", stops,
             "" if stops == 1 else "s",
             "already held once" if gate.get("held") else "not yet held"))

    open_ids = checklist_ids(gate, "open")
    print(describe_open(open_ids, "are") if open_ids else "nothing is open")
    in_flight = checklist_ids(gate, "in_flight")
    if in_flight:
        print("in flight: %s" % ", ".join(in_flight))
    return 1 if expired else 0


def cmd_gate(args):
    url = (args[0] if args else "").strip()
    if url and not plausible_url(url):
        log("gate rejected an implausible url: %r" % url[:120])
        print("not a plausible artifact url, so the gate was not recorded: %s"
              % url[:120], file=sys.stderr)
        return 0
    session_id = (args[1] if len(args) > 1 else "").strip() or session_from_env()
    if not session_id:
        print("no session id resolved: the gate was not recorded", file=sys.stderr)
        return 0

    path = session_path(session_id)
    state = read_json(path, {}) or {}
    if not isinstance(state, dict):
        state = {}

    if url:
        state["gate_pending"] = {"url": url, "at": time.time()}
    else:
        state.pop("gate_pending", None)
    if not write_json(path, state):
        print("could not write %s" % path, file=sys.stderr)
        return 0
    log("gate %s for session %s" % ("pending" if url else "cleared", session_id[:8]))
    return 0


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


PING_USAGE = (
    "usage: notify.py --ping --level <level> --title <title>"
    " [--body <text>|-] [--session <id>]"
    "\n       the body is read from stdin when --body is absent or -")


def session_from_env():
    for name in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def cmd_ping(args):
    given = {"--level": "", "--title": "", "--session": "", "--body": None}
    rest = list(args)
    while rest:
        flag = rest.pop(0)
        if flag not in given or not rest or rest[0].startswith("--"):
            print(PING_USAGE, file=sys.stderr)
            return 2
        given[flag] = rest.pop(0)

    level = given["--level"].strip()
    title = given["--title"].strip()
    body = given["--body"]
    if body is None or body == "-":
        body = sys.stdin.read()
    body = body.strip()
    if not level or not title or not body:
        print(PING_USAGE, file=sys.stderr)
        return 2

    session_id = given["--session"].strip() or session_from_env()
    config, _ = load_config()
    cwd = os.getcwd()
    repo = repo_label(cwd, (config or DEFAULTS)["host_label"])
    transcript_path = transcript_for(session_id) if session_id else None
    state = (read_json(session_path(session_id), {}) or {}) if session_id else {}
    if not isinstance(state, dict):
        state = {}
    label = session_title(transcript_path, config, state) if session_id else ""
    body, appended = append_change_request(body, transcript_path, state, cwd)

    envelope = build_envelope(
        level, title, body, repo, branch_label(cwd), session_id, label,
        cwd, state.get("thread"))
    thread, problem = send(envelope)
    if problem:
        log("--ping %s failed: %s" % (level, problem))
        print(problem, file=sys.stderr)
        return 1

    if session_id:
        if not record_sent(session_id, state, time.time(), thread=thread, arm=True):
            print("sent, but %s could not be written: this session is NOT armed"
                  % session_path(session_id), file=sys.stderr)
    else:
        print("no session id resolved: sent unthreaded, and this session is"
              " NOT armed for automatic notifications", file=sys.stderr)
    log("--ping sent %s for %s (%s%s)" % (
        level, repo, "armed" if session_id else "unarmed, no session id",
        ", link appended" if appended else ""))
    print("sent %s for %s" % (level, repo))
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
    print("unarmed sessions still notify when blocked: %s" % (
        "yes (%s)" % ", ".join(sorted(BLOCKING_KINDS))
        if config["notify_when_blocked"] else "no"))
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
    if args and args[0] == "--ping":
        return cmd_ping(args[1:])
    if args and args[0] == "--gate-pending":
        return cmd_gate(args[1:])
    if args and args[0] == "--gate-clear":
        return cmd_gate([""] + args[1:])
    if args and args[0] == "--checklist-clear":
        return cmd_checklist_clear(args[1:])
    if args and args[0] == "--checklist-status":
        return cmd_checklist_status(args[1:])
    if args and args[0] == "--change-request":
        session_id = args[1] if len(args) > 1 else ""
        path = session_path(session_id) if session_id else None
        state = (read_json(path, {}) or {}) if path else {}
        if not isinstance(state, dict):
            state = {}
        before = cached_change_request(state)
        print(change_request_for(transcript_for(session_id), state, os.getcwd()) or "")
        if path and state.get("change_request") and cached_change_request(state) != before:
            merge_state(path, {"change_request": state["change_request"]})
        return 0
    if args and args[0] == "--label":
        session_id = args[1] if len(args) > 1 else ""
        config, _ = load_config()
        path = session_path(session_id) if session_id else None
        state = (read_json(path, {}) or {}) if path else {}
        if not isinstance(state, dict):
            state = {}
        before = state.get("title")
        print(session_title(transcript_for(session_id), config, state) or "")
        if path and state.get("title") and state.get("title") != before:
            merge_state(path, {"title": state["title"]})
        return 0
    if args and args[0] == "--repo":
        # The ping skill resolves the same field for a message it sends itself.
        # Sharing this resolution is what keeps a deliberate ping and an
        # automatic one from disagreeing about what to call the same session.
        config, _ = load_config()
        host_label = (config or DEFAULTS)["host_label"]
        print(repo_label(args[1] if len(args) > 1 else os.getcwd(), host_label))
        return 0
    if args:
        print(
            "usage: notify.py [--test | --away [<duration>|off|status]"
            " | --disarm <session-id>|all | --label <session-id>"
            " | --repo [<cwd>] | --change-request <session-id>"
            " | --gate-pending <url> [<session-id>]"
            " | --gate-clear [<session-id>]"
            " | --checklist-clear [--force] [<session-id>]"
            " | --checklist-status [<session-id>]"
            " | --ping --level <level> --title <title>"
            " [--body <text>|-] [--session <id>]]", file=sys.stderr)
        return 2
    payload = json.load(sys.stdin)
    hold = plan_gate(payload)
    if hold:
        print(json.dumps({"decision": "block", "reason": hold}))
        log("Stop held: a plan was published and no question was asked")
        return 0
    hold = checklist_gate(payload)
    if hold:
        print(json.dumps({"decision": "block", "reason": hold}))
        log("Stop held: the run checklist is behind the run")
        return 0
    log("%s %s" % (payload.get("hook_event_name"), handle(payload)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        if "--test" in sys.argv or "--ping" in sys.argv:
            raise
        log("crash: %r" % (error,))
        sys.exit(0)
