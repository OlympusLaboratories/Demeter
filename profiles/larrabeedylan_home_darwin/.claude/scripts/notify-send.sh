#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request

HOME = os.path.expanduser("~")
CONFIG_PATH = os.path.join(HOME, ".claude", "notify.json")
DM_CACHE = os.path.join(HOME, ".claude", "notify-state", "slack-dm.json")
POST_TIMEOUT = 20
BODY_LIMIT = 3000
PUSH_LIMIT = 140
SLACK_BLOCK_LIMIT = 2900
MENTION_LEVELS = ("stop", "question", "permission", "failure")

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


def from_file(path):
    # A box that already holds this bot's token in its own file reads it from
    # there rather than keeping a second copy. One owner per credential.
    try:
        with open(os.path.expanduser(path)) as handle:
            return usable(handle.read())
    except OSError as error:
        fail("cannot read %s: %s" % (path, error))


def setting(transport, settings, name):
    direct = usable(settings.get(name))
    if direct:
        return direct
    path = usable(settings.get(name + "_file"))
    if not path:
        return ""
    value = from_file(path)
    if not value:
        fail("%s.%s_file points at %s, which is empty" % (transport, name, path))
    return value


def section():
    try:
        with open(CONFIG_PATH) as handle:
            raw = json.load(handle)
    except OSError:
        fail("no config at %s" % CONFIG_PATH)
    except ValueError as error:
        fail("%s is not valid JSON: %s" % (CONFIG_PATH, error))
    transport = usable(raw.get("transport")) or "telegram"
    if transport not in TRANSPORTS:
        fail("%s names transport %r, which this sender does not speak: %s"
             % (CONFIG_PATH, transport, ", ".join(sorted(TRANSPORTS))))
    settings = raw.get(transport)
    if not isinstance(settings, dict):
        fail("%s has no %s section" % (CONFIG_PATH, transport))
    return transport, settings


def headline(envelope):
    parts = [envelope.get("repo") or "?"]
    context = envelope.get("session_label") or envelope.get("branch")
    if context:
        parts.append(context)
    return " · ".join(parts)


def glyph_for(envelope):
    return GLYPHS.get(envelope.get("level"), "•")


def telegram_config():
    transport, settings = section()
    token = setting(transport, settings, "bot_token")
    chat = setting(transport, settings, "chat_id")
    if not token:
        fail("telegram.bot_token and telegram.bot_token_file are both empty")
    if not chat:
        fail("telegram.chat_id and telegram.chat_id_file are both empty")
    return token, chat


def telegram_post(token, method, payload):
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


def telegram_compose(envelope):
    body = escape((envelope.get("body") or "").strip()[:BODY_LIMIT])
    glyph = glyph_for(envelope)
    if envelope.get("thread"):
        return "%s %s" % (glyph, body) if body else glyph
    header = "<b>%s</b>" % escape(headline(envelope))
    return "%s\n%s" % (header, body) if body else header


def telegram_send(envelope):
    token, chat = telegram_config()
    payload = {
        "chat_id": chat,
        "text": telegram_compose(envelope),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    thread = envelope.get("thread")
    if thread:
        payload["reply_to_message_id"] = thread
        payload["allow_sending_without_reply"] = True
    result = telegram_post(token, "sendMessage", payload)
    return {"thread": thread or result.get("message_id")}


def telegram_route():
    token, chat = telegram_config()
    me = telegram_post(token, "getMe", {})
    return "@%s to chat %s" % (me.get("username", "?"), chat)


def slack_config():
    transport, settings = section()
    token = setting(transport, settings, "bot_token")
    channel = setting(transport, settings, "channel")
    webhook = setting(transport, settings, "webhook_url")
    if token and not channel:
        fail("slack.bot_token is set but slack.channel is empty")
    if not token and not webhook:
        fail("set slack.webhook_url, or slack.bot_token plus slack.channel")
    mention = setting(transport, settings, "mention")
    if not mention and channel[:1] in ("U", "W"):
        mention = channel
    levels = settings.get("mention_levels")
    if not isinstance(levels, list):
        levels = list(MENTION_LEVELS)
    return token, channel, webhook, mention, [str(x) for x in levels]


def slack_post(url, payload, headers):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=dict(headers, **{"Content-Type": "application/json; charset=utf-8"}),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=POST_TIMEOUT) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        fail("slack returned HTTP %s: %s" % (error.code, error.read()[:200].decode("utf-8", "replace")))
    except (urllib.error.URLError, OSError) as error:
        fail("could not reach slack: %s" % error)


def dm_channel(token, user):
    try:
        with open(DM_CACHE) as handle:
            cached = json.load(handle).get(user)
    except (OSError, ValueError):
        cached = None
    if cached:
        return cached
    body = slack_post(
        "https://slack.com/api/conversations.open",
        {"users": user},
        {"Authorization": "Bearer " + token},
    )
    try:
        reply = json.loads(body)
    except ValueError:
        fail("slack sent back something that is not JSON: %s" % body[:200])
    if not reply.get("ok"):
        fail("could not open a DM with %s: %s (the bot needs the im:write scope)"
             % (user, reply.get("error", body[:200])))
    opened = (reply.get("channel") or {}).get("id")
    if not opened:
        fail("slack opened a DM but did not say which: %s" % body[:200])
    try:
        os.makedirs(os.path.dirname(DM_CACHE), exist_ok=True)
        with open(DM_CACHE, "w") as handle:
            json.dump({user: opened}, handle)
    except OSError:
        pass
    return opened


def resolve(token, channel):
    if channel[:1] in ("U", "W") and " " not in channel:
        return dm_channel(token, channel)
    return channel


def push_text(envelope):
    body = " ".join((envelope.get("body") or "").split())
    if len(body) > PUSH_LIMIT:
        body = body[:PUSH_LIMIT].rstrip() + "…"
    if envelope.get("thread"):
        return "%s %s" % (glyph_for(envelope), body) if body else glyph_for(envelope)
    return "%s%s" % (headline(envelope), " — " + body if body else "")


def blocks_for(envelope, mention=""):
    blocks = []
    body = (envelope.get("body") or "").strip()[:SLACK_BLOCK_LIMIT]
    if envelope.get("thread"):
        body = "%s %s" % (glyph_for(envelope), body) if body else glyph_for(envelope)
    else:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": headline(envelope)}],
        })
    lead = "<@%s>" % mention if mention else ""
    if lead:
        body = "%s %s" % (lead, body) if body else lead
    if body:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": body},
        })
    return blocks


def slack_send(envelope):
    token, channel, webhook, mention, levels = slack_config()
    text = push_text(envelope)
    at = mention if mention and envelope.get("level") in levels else ""
    if at:
        text = "<@%s> %s" % (at, text)
    blocks = blocks_for(envelope, at)
    if token:
        target = resolve(token, channel)
        payload = {"channel": target, "text": text, "blocks": blocks, "unfurl_links": False}
        thread = envelope.get("thread")
        if thread:
            payload["thread_ts"] = thread
        body = slack_post(
            "https://slack.com/api/chat.postMessage",
            payload,
            {"Authorization": "Bearer " + token},
        )
        try:
            reply = json.loads(body)
        except ValueError:
            fail("slack sent back something that is not JSON: %s" % body[:200])
        if not reply.get("ok"):
            fail("slack refused the message: %s" % reply.get("error", body[:200]))
        return {"thread": thread or reply.get("ts")}
    slack_post(webhook, {"text": text, "blocks": blocks}, {})
    return {}


def slack_route():
    token, channel, webhook, mention, levels = slack_config()
    if not token:
        return "incoming webhook (flat)"
    target = resolve(token, channel)
    route = "bot token to %s (threaded)" % target
    if mention:
        route += ", mentioning <@%s> on %s" % (mention, "/".join(levels))
    if target != channel:
        route += ", the DM with %s" % channel
    return route


TRANSPORTS = {
    "telegram": (telegram_send, telegram_route),
    "slack": (slack_send, slack_route),
}


def send(envelope):
    transport, _ = section()
    return TRANSPORTS[transport][0](envelope)


def check():
    transport, _ = section()
    route = TRANSPORTS[transport][1]()
    result = send({
        "title": "notify is wired up",
        "body": "Test message from notify.py --test. Delete me.",
        "repo": "demeter",
        "branch": None,
        "session": "test",
        "level": "stop",
    })
    print("sent a test message via %s %s" % (transport, route))
    if result.get("thread"):
        print("thread id %s" % result["thread"])


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
