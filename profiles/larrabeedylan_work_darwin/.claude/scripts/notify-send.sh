#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".claude", "notify.json")
DM_CACHE = os.path.join(os.path.expanduser("~"), ".claude", "notify-state", "slack-dm.json")
POST_TIMEOUT = 5
PUSH_LIMIT = 140
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


def config():
    try:
        with open(CONFIG_PATH) as handle:
            raw = json.load(handle)
    except OSError:
        fail("no config at %s" % CONFIG_PATH)
    except ValueError as error:
        fail("%s is not valid JSON: %s" % (CONFIG_PATH, error))
    settings = raw.get("slack")
    if not isinstance(settings, dict):
        fail("%s has no slack section" % CONFIG_PATH)
    token = usable(settings.get("bot_token"))
    channel = usable(settings.get("channel"))
    webhook = usable(settings.get("webhook_url"))
    if token and not channel:
        fail("slack.bot_token is set but slack.channel is empty")
    if not token and not webhook:
        fail("set slack.webhook_url, or slack.bot_token plus slack.channel")
    mention = usable(settings.get("mention"))
    if not mention and channel[:1] in ("U", "W"):
        mention = channel
    levels = settings.get("mention_levels")
    if not isinstance(levels, list):
        levels = list(MENTION_LEVELS)
    return token, channel, webhook, mention, [str(x) for x in levels]


def post(url, payload, headers):
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
    body = post(
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


def headline(envelope):
    glyph = GLYPHS.get(envelope.get("level"), "•")
    parts = [envelope.get("repo") or "?"]
    if envelope.get("branch"):
        parts.append(envelope["branch"])
    if envelope.get("session"):
        parts.append(envelope["session"])
    return "%s %s" % (glyph, " · ".join(parts))


def push_text(envelope):
    body = " ".join((envelope.get("body") or "").split())
    if len(body) > PUSH_LIMIT:
        body = body[:PUSH_LIMIT].rstrip() + "…"
    title = envelope.get("title") or "Claude Code"
    return "%s %s%s" % (
        GLYPHS.get(envelope.get("level"), "•"),
        title,
        " — " + body if body else "",
    )


def blocks_for(envelope, mention=""):
    blocks = [{
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": headline(envelope)}],
    }]
    body = (envelope.get("body") or "").strip()[:2900]
    lead = "<@%s>" % mention if mention else ""
    if lead:
        body = "%s %s" % (lead, body) if body else lead
    if body:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": body},
        })
    return blocks


def send(envelope):
    token, channel, webhook, mention, levels = config()
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
        body = post(
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
    post(webhook, {"text": text, "blocks": blocks}, {})
    return {}


def check():
    token, channel, webhook, mention, levels = config()
    if token:
        target = resolve(token, channel)
        route = "bot token to %s (threaded)" % target
        if mention:
            route += ", mentioning <@%s> on %s" % (mention, "/".join(levels))
        if target != channel:
            route += ", the DM with %s" % channel
    else:
        route = "incoming webhook (flat)"
    result = send({
        "title": "notify is wired up",
        "body": "Test message from `notify.py --test`. Delete me.",
        "repo": "demeter",
        "branch": None,
        "session": "test",
        "level": "stop",
    })
    print("sent a test message via %s" % route)
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
