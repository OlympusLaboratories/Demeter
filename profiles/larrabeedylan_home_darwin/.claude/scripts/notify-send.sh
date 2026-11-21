#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".claude", "notify.json")
POST_TIMEOUT = 20
BODY_LIMIT = 3000

GLYPHS = {
    "stop": "✅",
    "permission": "🔐",
    "question": "❓",
    "progress": "🔄",
    "idle": "💤",
    "failure": "🔥",
}


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def usable(value):
    text = str(value or "").strip()
    return "" if "REPLACE_ME" in text else text


def config():
    try:
        with open(CONFIG_PATH) as handle:
            raw = json.load(handle)
    except OSError:
        fail("no config at %s" % CONFIG_PATH)
    except ValueError as error:
        fail("%s is not valid JSON: %s" % (CONFIG_PATH, error))
    settings = raw.get("telegram")
    if not isinstance(settings, dict):
        fail("%s has no telegram section" % CONFIG_PATH)
    token = usable(settings.get("bot_token"))
    chat = usable(settings.get("chat_id"))
    if not token:
        fail("telegram.bot_token is empty")
    if not chat:
        fail("telegram.chat_id is empty")
    return token, chat


def post(token, method, payload):
    request = urllib.request.Request(
        "https://api.telegram.org/bot%s/%s" % (token, method),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=POST_TIMEOUT) as response:
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        detail = error.read()[:300].decode("utf-8", "replace")
        try:
            detail = json.loads(detail).get("description", detail)
        except ValueError:
            pass
        fail("telegram returned HTTP %s: %s" % (error.code, detail))
    except (urllib.error.URLError, OSError) as error:
        fail("could not reach telegram: %s" % error)
    try:
        reply = json.loads(body)
    except ValueError:
        fail("telegram sent back something that is not JSON: %s" % body[:200])
    if not reply.get("ok"):
        fail("telegram refused the message: %s" % reply.get("description", body[:200]))
    return reply.get("result") or {}


def escape(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def compose(envelope):
    glyph = GLYPHS.get(envelope.get("level"), "•")
    parts = [envelope.get("repo") or "?"]
    if envelope.get("branch"):
        parts.append(envelope["branch"])
    if envelope.get("session"):
        parts.append(envelope["session"])
    header = "%s <b>%s</b>" % (glyph, escape(envelope.get("title") or "Claude Code"))
    trail = "<i>%s</i>" % escape(" · ".join(parts))
    body = (envelope.get("body") or "").strip()
    lines = [header, trail]
    if body:
        lines.append("<pre>%s</pre>" % escape(body[:BODY_LIMIT]))
    return "\n".join(lines)


def send(envelope):
    token, chat = config()
    payload = {
        "chat_id": chat,
        "text": compose(envelope),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    thread = envelope.get("thread")
    if thread:
        payload["reply_to_message_id"] = thread
        payload["allow_sending_without_reply"] = True
    result = post(token, "sendMessage", payload)
    return {"thread": thread or result.get("message_id")}


def check():
    token, chat = config()
    me = post(token, "getMe", {})
    result = send({
        "title": "notify is wired up",
        "body": "Test message from notify.py --test. Delete me.",
        "repo": "demeter",
        "branch": None,
        "session": "test",
        "level": "stop",
    })
    print("sent a test message as @%s to chat %s" % (me.get("username", "?"), chat))
    if result.get("thread"):
        print("message id %s" % result["thread"])


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "check":
        check()
        return 0
    if action != "send":
        print("usage: notify-send.sh send|check", file=sys.stderr)
        return 2
    try:
        envelope = json.load(sys.stdin)
    except ValueError as error:
        fail("envelope on stdin is not valid JSON: %s" % error)
    print(json.dumps(send(envelope)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
