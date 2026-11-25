#!/usr/bin/env python3

import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

STATES = ("pending", "in-flight", "done", "skipped")
OPEN_STATES = ("pending", "in-flight")
ITEM_FIELDS = ("id", "obligation", "skill", "target", "waiting_on", "state", "note")
RUN_FIELDS = ("title", "repo", "branch", "ticket", "plan_page", "change_request",
              "url", "hash")

BLOCK_ID = "checklist"
BLOCK_OPEN = '<script type="application/json" id="%s">' % BLOCK_ID
BLOCK_CLOSE = "</script>"

PUBLISH_SCRIPT = os.environ.get(
    "PUBLISH_ARTIFACT",
    os.path.join(os.path.expanduser("~"), ".claude", "scripts", "publish-artifact.sh"),
)
ABSENT = 3
EXPIRES = "30d"

SESSIONS = os.path.join(os.path.expanduser("~"), ".claude", "notify-state", "sessions")
SESSION_KEYS = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID")

STATE_LABEL = {
    "pending": "pending",
    "in-flight": "in flight",
    "done": "done",
    "skipped": "skipped",
}


def item(ident, obligation, skill="", target="", waiting_on="", state="pending", note=""):
    return {
        "id": ident,
        "obligation": obligation,
        "skill": skill,
        "target": target,
        "waiting_on": waiting_on,
        "state": state,
        "note": note,
    }


def template(options):
    branch = options.branch or "<branch>"
    request = "the %s" % (options.request_name or "change request")
    items = [
        item("arm", "Arm the session's notifications", "ping", "this session"),
        item("plan", "Get the plan approved by the user", "AskUserQuestion",
             options.ticket or "the problem statement"),
        item("implement", "Implement the change", "", branch),
        item("commit", "Commit with a generated message", "commit-msg", branch),
        item("describe", "Write the change description", "changes-description", branch),
    ]

    if options.branch_mode == "default":
        if options.diagram:
            items.append(item("diagram", "Draw and publish the call-flow diagram",
                              "changes-diagram", branch))
        if options.review:
            items.append(item("review", "Review the diff with the swarm",
                              "review-code", branch))
        items.append(item("push", "Push the default branch", "autopilot", branch))
    else:
        items.append(item("open", "Push and open %s" % request, "autopilot", branch))
        items.append(item("link", "Send the user %s's link" % request, "ping", "the user"))
        items.append(item("pipeline", "Drive the pipeline green", "autopilot", request))
        if options.review:
            items.append(item("review", "Review the diff with the swarm",
                              "review-code", branch))
        items.append(item("threads", "Clear every review thread", "fix-feedback", request))
        if options.iac:
            items.append(item("apply", "Apply the infrastructure plan before the merge",
                              "autopilot", request))
        if options.merge:
            items.append(item("merge", "Merge %s" % request, "autopilot", request))
        else:
            items.append(item("ready", "Hand over a ready %s without merging" % request,
                              "autopilot", request))
        if options.diagram:
            items.append(item("diagram", "Attach the call-flow diagram",
                              "changes-diagram", request))
        items.append(item("ledger", "Append the decision record to the description",
                          "autopilot", request))

    items.append(item("verify", "Verify the change reached production", "autopilot",
                      "the deploy target"))
    items.append(item("close", "Report what happened and send the closing ping",
                      "ping", "the user"))

    return {
        "run": {
            "title": options.title or (options.ticket or "Fix run"),
            "repo": options.repo or "",
            "branch": options.branch or "",
            "ticket": options.ticket or "",
            "plan_page": "",
            "change_request": "",
            "url": "",
            "hash": "",
        },
        "items": items,
    }


def canonical(document, path):
    if not isinstance(document, dict):
        raise ValueError("%s is not a JSON object" % path)

    run_raw = document.get("run", {})
    if not isinstance(run_raw, dict):
        raise ValueError("%s: run is not an object" % path)
    run = {}
    for field in RUN_FIELDS:
        value = run_raw.get(field, "")
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise ValueError("%s: run.%s is not a string" % (path, field))
        run[field] = value

    items_raw = document.get("items")
    if not isinstance(items_raw, list) or not items_raw:
        raise ValueError("%s: items is missing or empty" % path)

    items = []
    seen = set()
    for index, entry in enumerate(items_raw):
        where = "%s: item %d" % (path, index + 1)
        if not isinstance(entry, dict):
            raise ValueError("%s is not an object" % where)
        clean = {}
        for field in ITEM_FIELDS:
            value = entry.get(field, "")
            if value is None:
                value = ""
            if not isinstance(value, str):
                raise ValueError("%s: %s is not a string" % (where, field))
            clean[field] = value.strip()

        if not clean["id"]:
            raise ValueError("%s has no id" % where)
        if clean["id"] in seen:
            raise ValueError("%s repeats the id %s" % (where, clean["id"]))
        seen.add(clean["id"])
        if not clean["obligation"]:
            raise ValueError("%s (%s) has no obligation" % (where, clean["id"]))
        if clean["state"] not in STATES:
            raise ValueError("%s (%s) has state %r, not one of %s"
                             % (where, clean["id"], clean["state"], ", ".join(STATES)))
        if clean["state"] == "skipped" and not clean["note"]:
            raise ValueError("%s (%s) is skipped with no reason" % (where, clean["id"]))
        if clean["state"] == "in-flight" and not clean["waiting_on"]:
            raise ValueError("%s (%s) is in flight and waiting on nothing"
                             % (where, clean["id"]))
        items.append(clean)

    return {"run": run, "items": items}


def standing(items):
    in_flight = [entry for entry in items if entry["state"] == "in-flight"]
    outstanding = [entry for entry in items if entry["state"] in OPEN_STATES]
    if not outstanding:
        return "complete", "Every item is done or skipped.", []
    if in_flight:
        return "armed", "Waiting on %s." % "; ".join(
            "%s — %s" % (entry["obligation"], entry["waiting_on"]) for entry in in_flight
        ), in_flight
    return ("stalled",
            "%d item%s outstanding and nothing is in flight."
            % (len(outstanding), "" if len(outstanding) == 1 else "s"),
            [])


def session_id():
    for key in SESSION_KEYS:
        value = os.environ.get(key)
        if value:
            return value
    return ""


def session_state_path(ident):
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", ident or "unknown")[:80]
    return os.path.join(SESSIONS, safe + ".json")


def mark_outstanding(document):
    ident = session_id()
    if not ident:
        return False
    items = document["items"]
    verdict, _, in_flight = standing(items)
    path = session_state_path(ident)
    state = {}
    if os.path.exists(path):
        try:
            with open(path) as handle:
                state = json.load(handle)
        except (OSError, ValueError):
            state = {}
    if not isinstance(state, dict):
        state = {}
    if verdict == "complete":
        state.pop("checklist_pending", None)
    else:
        run = document["run"]
        state["checklist_pending"] = {
            "url": run.get("url", ""),
            "hash": run.get("hash", ""),
            "at": time.time(),
            "stops": 0,
            "verdict": verdict,
            "open": [entry["id"] for entry in items if entry["state"] in OPEN_STATES],
            "in_flight": [entry["id"] for entry in in_flight],
        }
    try:
        os.makedirs(SESSIONS, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except OSError:
        return False
    return True


def dump(document):
    text = json.dumps(document, indent=2, sort_keys=True)
    return text.replace("<", "\\u003c")


def read_document(path):
    if path == "-":
        raw = sys.stdin.read()
        label = "stdin"
    else:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
        label = path
    try:
        parsed = json.loads(raw)
    except ValueError as error:
        raise ValueError("%s is not valid JSON: %s" % (label, error))
    return canonical(parsed, label)


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "run-checklist"})
    with urllib.request.urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "replace")


def source(location):
    if not re.match(r"^https?://", location):
        with open(location, encoding="utf-8") as handle:
            return handle.read(), location
    body = fetch(location)
    if BLOCK_OPEN in body:
        return body, location
    framed = re.search(r'<iframe[^>]*\bsrc="(https?://[^"]+)"', body)
    if not framed:
        return body, location
    inner = framed.group(1)
    return fetch(inner), inner


def extract(location):
    page, page_path = source(location)
    found = page.count(BLOCK_OPEN)
    if found < 1:
        raise ValueError("%s carries no %s block" % (page_path, BLOCK_ID))
    if found > 1:
        raise ValueError(
            "%s carries %d %s blocks; refusing to guess which is the run's own"
            % (page_path, found, BLOCK_ID))
    start = page.find(BLOCK_OPEN) + len(BLOCK_OPEN)
    end = page.find(BLOCK_CLOSE, start)
    if end < 0:
        raise ValueError("%s has an unterminated %s block" % (page_path, BLOCK_ID))
    try:
        parsed = json.loads(page[start:end])
    except ValueError as error:
        raise ValueError("%s: the %s block is not valid JSON: %s"
                         % (page_path, BLOCK_ID, error))
    return canonical(parsed, page_path)


def escape(text):
    return html.escape(text, quote=True)


def link_fact(url, label=""):
    if re.match(r"^https?://", url):
        return '<a href="%s">%s</a>' % (escape(url), escape(label or url))
    return "%s %s" % (escape(label), escape(url)) if label else escape(url)


def render(document, stamp=None):
    run = document["run"]
    items = document["items"]
    verdict, sentence, _ = standing(items)
    if stamp is None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S %Z")

    counts = {state: 0 for state in STATES}
    for entry in items:
        counts[entry["state"]] += 1
    tally = " · ".join("%d %s" % (counts[state], STATE_LABEL[state])
                       for state in STATES if counts[state])

    facts = []
    if run["repo"]:
        facts.append("repo %s" % escape(run["repo"]))
    if run["branch"]:
        facts.append("branch <code>%s</code>" % escape(run["branch"]))
    if run["ticket"]:
        facts.append("ticket %s" % escape(run["ticket"]))
    if run["plan_page"]:
        facts.append(link_fact(run["plan_page"], "plan"))
    if run["change_request"]:
        facts.append(link_fact(run["change_request"]))

    rows = []
    for index, entry in enumerate(items, start=1):
        waiting = escape(entry["waiting_on"])
        if not waiting:
            waiting = "<em>nothing</em>" if entry["state"] in OPEN_STATES else "—"
        detail = escape(entry["note"]) if entry["note"] else ""
        rows.append(
            "<tr class=\"s-%s\">"
            "<td class=\"n\">%d</td>"
            "<td data-label=\"State\"><span class=\"badge\">%s</span></td>"
            "<td class=\"ob\" data-label=\"Obligation\">%s%s</td>"
            "<td data-label=\"Skill\">%s</td>"
            "<td data-label=\"Applies to\">%s</td>"
            "<td class=\"wait\" data-label=\"Waiting on\">%s</td>"
            "</tr>" % (
                entry["state"],
                index,
                escape(STATE_LABEL[entry["state"]]),
                escape(entry["obligation"]),
                ('<span class="note">%s</span>' % detail) if detail else "",
                ("<code>%s</code>" % escape(entry["skill"])) if entry["skill"] else "—",
                escape(entry["target"]) if entry["target"] else "—",
                waiting,
            )
        )

    return PAGE % {
        "title": escape(run["title"] or "Run checklist"),
        "facts": " · ".join(facts) if facts else "no run identity recorded",
        "verdict": verdict,
        "verdict_label": {"armed": "Armed",
                          "stalled": "Nothing armed",
                          "complete": "Complete"}[verdict],
        "sentence": escape(sentence),
        "tally": escape(tally),
        "stamp": escape(stamp),
        "rows": "\n".join(rows),
        "json": dump(document),
    }


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>%(title)s</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #fbfaf8; --fg: #1b1a18; --muted: #605c56; --rule: #ddd8d0; --card: #fff;
    --accent: #7a4e22; --ok: #2f6b3a; --flight: #8a5a12; --skip: #6a6a6a;
    --alarm-bg: #fdecec; --alarm-br: #d98a8a; --alarm-fg: #8c2222;
    --armed-bg: #eef5ee; --armed-br: #9dc0a3;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #17161a; --fg: #eceaf0; --muted: #a39fab; --rule: #343040; --card: #201e26;
      --accent: #d9a86b; --ok: #7fc08c; --flight: #e0b060; --skip: #8d8a95;
      --alarm-bg: #33191b; --alarm-br: #7d3236; --alarm-fg: #f0a8a8;
      --armed-bg: #1c2a1e; --armed-br: #3f6245;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--fg); padding: 0 16px 64px;
    font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Helvetica, Arial, sans-serif;
  }
  main { max-width: 940px; margin: 0 auto; }
  header { padding: 32px 0 14px; }
  .kicker { font-size: 12.5px; letter-spacing: .09em; text-transform: uppercase;
            color: var(--accent); font-weight: 650; }
  h1 { font-size: 24px; line-height: 1.26; margin: 8px 0 8px; font-weight: 650; }
  .facts { color: var(--muted); font-size: 14px; margin: 0; }
  .facts code { font-size: 13px; }
  code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px;
         background: var(--card); border: 1px solid var(--rule); border-radius: 4px; padding: 1px 4px; }
  .state { border-radius: 8px; border: 1px solid var(--rule); background: var(--card);
           padding: 13px 16px; margin: 18px 0 8px; }
  .state .head { font-weight: 680; font-size: 15.5px; }
  .state p { margin: 4px 0 0; font-size: 14px; }
  .state.stalled { background: var(--alarm-bg); border-color: var(--alarm-br); }
  .state.stalled .head { color: var(--alarm-fg); }
  .state.armed { background: var(--armed-bg); border-color: var(--armed-br); }
  .meta { color: var(--muted); font-size: 13px; margin: 0 0 20px; }
  .wrap { overflow-x: auto; }
  table { width: 100%%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--rule);
           vertical-align: top; }
  th { font-size: 12px; text-transform: uppercase; letter-spacing: .06em;
       color: var(--muted); font-weight: 650; }
  td.n { color: var(--muted); font-variant-numeric: tabular-nums; width: 2.2em; }
  td.ob { font-weight: 560; }
  .note { display: block; font-weight: 400; color: var(--muted); font-size: 13px; }
  .badge { display: inline-block; font-size: 11.5px; text-transform: uppercase;
           letter-spacing: .05em; font-weight: 650; padding: 2px 7px; border-radius: 999px;
           border: 1px solid currentColor; white-space: nowrap; }
  tr.s-done .badge { color: var(--ok); }
  @media (max-width: 760px) {
    .wrap { overflow-x: visible; }
    table, tbody, tr, td { display: block; width: 100%%; }
    thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
    tr { border: 1px solid var(--rule); border-radius: 10px; padding: 10px 12px 4px;
         margin: 0 0 12px; position: relative; }
    td { border: 0; padding: 3px 0 7px 0; overflow-wrap: anywhere; }
    td::before { content: attr(data-label); display: block; font-size: 11px;
                 text-transform: uppercase; letter-spacing: .06em; color: var(--muted);
                 font-weight: 650; margin: 0 0 2px; }
    td.n { position: absolute; top: 10px; right: 12px; width: auto; padding: 0;
           font-size: 12px; }
    td.n::before { content: none; }
    td[data-label="State"]::before { content: none; }
    td.wait { border-top: 1px solid var(--rule); padding-top: 7px; }
  }
  tr.s-in-flight .badge { color: var(--flight); }
  tr.s-skipped .badge { color: var(--skip); }
  tr.s-pending .badge { color: var(--muted); }
  tr.s-done td.ob, tr.s-skipped td.ob { color: var(--muted); font-weight: 400; }
  footer { margin-top: 32px; color: var(--muted); font-size: 13px; }
</style>
</head>
<body>
<main>
<header>
  <div class="kicker">Run checklist</div>
  <h1>%(title)s</h1>
  <p class="facts">%(facts)s</p>
</header>

<div class="state %(verdict)s">
  <div class="head">%(verdict_label)s</div>
  <p>%(sentence)s</p>
</div>
<p class="meta">%(tally)s · updated %(stamp)s</p>

<div class="wrap">
<table>
  <thead><tr><th></th><th>State</th><th>Obligation</th><th>Skill</th><th>Applies to</th><th>Waiting on</th></tr></thead>
  <tbody>
%(rows)s
  </tbody>
</table>
</div>

<footer>Refresh to see where the run is. This page is rewritten in place at every step boundary.</footer>
</main>
<script type="application/json" id="checklist">
%(json)s
</script>
</body>
</html>
"""


def write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def cmd_template(args):
    sys.stdout.write(dump(canonical(template(args), "template")) + "\n")
    return 0


def cmd_render(args):
    document = read_document(args.items)
    write(args.out, render(document, stamp=args.stamp))
    print(args.out)
    return 0


def cmd_items(args):
    sys.stdout.write(dump(extract(args.page)) + "\n")
    return 0


def send(document, page, update, stamp):
    run = document["run"]
    write(page, render(document, stamp=stamp))
    command = [PUBLISH_SCRIPT, page, "--purpose", "tasks", "--expires", EXPIRES,
               "--title", run["title"] or "Run checklist",
               "--description", "run checklist"]
    if update:
        command += ["--update", update]

    try:
        finished = subprocess.run(command, capture_output=True, text=True)
    except OSError as error:
        print("cannot run %s: %s" % (PUBLISH_SCRIPT, error), file=sys.stderr)
        return ABSENT, ""

    if finished.stderr:
        sys.stderr.write(finished.stderr)
    if finished.returncode != 0:
        sys.stdout.write(finished.stdout)
        return finished.returncode, ""

    url = ""
    for line in finished.stdout.splitlines():
        candidate = line.strip()
        if re.match(r"^https?://\S+$", candidate):
            url = candidate
    if not url:
        sys.stdout.write(finished.stdout)
        print("the publisher printed no url", file=sys.stderr)
        return 1, ""
    return 0, url


def publish(document, items_path, update, out, stamp):
    run = document["run"]
    page = out or os.path.join(
        os.environ.get("TMPDIR", "/tmp"), "run-checklist-%d.html" % os.getpid())

    status, url = send(document, page, update or run["hash"], stamp)
    if status != 0:
        print("page=%s" % page)
        return status

    digest = url.rstrip("/").rsplit("/", 1)[-1]
    if run["url"] != url or run["hash"] != digest:
        run["url"] = url
        run["hash"] = digest
        status, url = send(document, page, digest, stamp)
        if status != 0:
            print("published, but the page does not carry its own identity: "
                  "url=%s hash=%s page=%s" % (run["url"], digest, page), file=sys.stderr)
            return status
        if items_path and items_path != "-":
            write(items_path, dump(document) + "\n")
            print("recorded the page identity in %s" % items_path)

    print("url=%s" % run["url"])
    print("hash=%s" % run["hash"])
    print("page=%s" % page)
    return 0


def cmd_publish(args):
    document = read_document(args.items)
    status = publish(document, args.items, args.update, args.out, args.stamp)
    mark_outstanding(document)
    return status


def apply_ticks(document, ticks):
    by_id = {entry["id"]: entry for entry in document["items"]}
    for tick in ticks:
        if "=" not in tick:
            raise ValueError("%r is not <id>=<state>[:<text>]" % tick)
        ident, _, rest = tick.partition("=")
        state, _, text = rest.partition(":")
        ident, state, text = ident.strip(), state.strip(), text.strip()
        if ident not in by_id:
            raise ValueError("no item %r; the page has %s"
                             % (ident, ", ".join(sorted(by_id))))
        if state not in STATES:
            raise ValueError("%s: state %r is not one of %s"
                             % (ident, state, ", ".join(STATES)))
        entry = by_id[ident]
        if state != entry["state"]:
            entry["note"] = ""
        entry["state"] = state
        if state == "in-flight":
            entry["waiting_on"] = text or entry["waiting_on"]
        else:
            entry["waiting_on"] = ""
            if text:
                entry["note"] = text
    return document


OBSERVABLE = ("arm", "open", "implement", "commit", "describe",
              "pipeline", "threads", "ledger", "merge")

LEDGER_MARK = "Relevant Decisions"


def git_out(repo, *args):
    try:
        done = subprocess.run(("git", "-C", repo) + args,
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def default_branch(repo):
    head = git_out(repo, "symbolic-ref", "refs/remotes/origin/HEAD")
    if head:
        return head.rsplit("/", 1)[-1]
    for name in ("main", "master"):
        if git_out(repo, "rev-parse", "--verify", "--quiet", "origin/" + name):
            return name
    return "main"


def branch_commits(repo, branch, base):
    if not (repo and branch):
        return None
    for ref in ("origin/%s" % base, base):
        if git_out(repo, "rev-parse", "--verify", "--quiet", ref) is None:
            continue
        count = git_out(repo, "rev-list", "--count", "%s..%s" % (ref, branch))
        if count is not None and count.isdigit():
            return int(count)
    return None


def session_armed():
    ident = session_id()
    if not ident:
        return None
    path = session_state_path(ident)
    if not os.path.exists(path):
        return False
    try:
        with open(path) as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return None
    return bool(isinstance(state, dict) and state.get("armed_at"))


def observed_local(repo, branch, base, body, armed):
    ticks = {}

    def discharged(ident, finished):
        if finished:
            ticks[ident] = ("done", "", None)

    discharged("arm", armed)

    commits = branch_commits(repo, branch, base)
    discharged("commit", bool(commits))
    discharged("implement", bool(commits))

    if body is not None:
        prose = "\n".join(line for line in body.splitlines()
                          if not line.strip().startswith("**Run checklist:**")).strip()
        discharged("describe", bool(prose))
        discharged("ledger", LEDGER_MARK in body)

    return ticks


def observed(forge):
    if not forge.get("url"):
        return {}
    merged = str(forge.get("merged", "")).lower() == "true"
    state = (forge.get("state") or "").upper()
    decision = (forge.get("review") or "NONE").upper()
    unresolved = int(forge.get("unresolved") or 0)
    pending = int(forge.get("checks_pending") or 0)
    failed = int(forge.get("checks_failed") or 0)
    total = int(forge.get("checks_total") or 0)

    ticks = {}
    if forge.get("url"):
        ticks["open"] = ("done", "", None)

    if merged:
        ticks["merge"] = ("done", "", None)
        ticks["pipeline"] = ("done", "", None)
    elif state == "CLOSED":
        ticks["merge"] = ("skipped", "the change request was closed without merging", None)
    elif total == 0:
        ticks["pipeline"] = ("in-flight", "the forge has reported no checks yet", None)
    elif pending:
        ticks["pipeline"] = ("in-flight",
                             "%d of %d check(s) still running" % (pending, total), None)
    elif failed:
        ticks["pipeline"] = ("in-flight", "%d check(s) failed" % failed, None)
    else:
        ticks["pipeline"] = ("done", "", None)

    if not merged:
        if decision == "CHANGES_REQUESTED":
            ticks["threads"] = ("in-flight", "the reviewer requested changes", None)
        elif unresolved:
            ticks["threads"] = ("in-flight", "%d unresolved thread(s)" % unresolved, None)
        elif decision == "APPROVED":
            ticks["threads"] = ("done", "", None)

    if not merged and state and state != "CLOSED":
        if pending or failed or total == 0:
            blocker = "a green pipeline"
        elif decision == "CHANGES_REQUESTED" or unresolved:
            blocker = "a clean review"
        elif decision == "APPROVED":
            blocker = "nothing; the gates are clear"
        else:
            blocker = "a review verdict"
        ticks["merge"] = ("in-flight", blocker, "in-flight")
    return ticks


def reconcile(document, forge, local=None):
    by_id = {entry["id"]: entry for entry in document["items"]}
    seen = dict(observed(forge))
    seen.update(local or {})
    changed = []
    for ident, (state, text, only_when) in seen.items():
        entry = by_id.get(ident)
        if entry is None or ident not in OBSERVABLE:
            continue
        if entry["state"] == "skipped":
            continue
        if only_when and entry["state"] != only_when:
            continue
        waiting = text if state == "in-flight" else ""
        note = "" if state == "in-flight" else text
        if entry["state"] == state:
            if entry.get("waiting_on", "") == waiting:
                continue
            entry["waiting_on"] = waiting
            entry["note"] = note
            changed.append("%s~%s" % (ident, state))
            continue
        entry["state"] = state
        entry["waiting_on"] = waiting
        entry["note"] = note
        changed.append("%s=%s" % (ident, state))
    return changed


def cmd_reconcile(args):
    document = read_document(args.items)
    recorded = (document["run"].get("change_request") or "").strip()
    given = (args.url or "").strip()
    if given and recorded and given.rstrip("/") != recorded.rstrip("/"):
        print("this checklist is for %s, not %s; refusing to write another change "
              "request's state onto it" % (recorded, given), file=sys.stderr)
        return 2
    if not recorded and not given:
        forge = {}
    else:
        forge = {
            "url": given or recorded,
            "state": args.state,
            "merged": args.merged,
            "review": args.review,
            "unresolved": args.unresolved,
            "checks_pending": args.checks_pending,
            "checks_failed": args.checks_failed,
            "checks_total": args.checks_total,
        }
    repo = args.repo or os.getcwd()
    base = args.default_branch or default_branch(repo)
    body = None
    if args.body_file:
        try:
            with open(args.body_file) as handle:
                body = handle.read()
        except OSError:
            body = None
    local = observed_local(repo, document["run"].get("branch", ""), base, body,
                           session_armed())
    changed = reconcile(document, forge, local)
    document = canonical(document, args.items)
    write(args.items, dump(document) + "\n")
    mark_outstanding(document)
    verdict, sentence, _ = standing(document["items"])
    if not changed:
        print("unchanged: %s" % sentence)
        return 0
    print("%s: %s (%s)" % (verdict, sentence, ", ".join(changed)))
    if not args.publish:
        return 0
    return publish(document, args.items, args.update, args.out, args.stamp)


def apply_run_fields(document, assignments):
    for assignment in assignments:
        if "=" not in assignment:
            raise ValueError("%r is not <field>=<value>" % assignment)
        field, _, value = assignment.partition("=")
        field = field.strip()
        if field not in RUN_FIELDS:
            raise ValueError("no run field %r; the page has %s"
                             % (field, ", ".join(RUN_FIELDS)))
        document["run"][field] = value.strip()
    return document


def cmd_tick(args):
    document = read_document(args.items)
    apply_run_fields(document, args.run)
    apply_ticks(document, args.tick)
    document = canonical(document, args.items)
    write(args.items, dump(document) + "\n")
    verdict, sentence, _ = standing(document["items"])
    mark_outstanding(document)
    print("%s: %s" % (verdict, sentence))
    if not args.publish:
        return 0
    return publish(document, args.items, args.update, args.out, args.stamp)


def cmd_arm(args):
    document = read_document(args.items)
    verdict, sentence, _ = standing(document["items"])
    where = document["run"].get("url") or "an unpublished checklist"

    if not session_id():
        print("no session id in the environment: the marker was not written",
              file=sys.stderr)
        print("%s: %s" % (verdict, sentence))
        return 0
    if not mark_outstanding(document):
        print("could not write the session state: the marker was not written",
              file=sys.stderr)
        return 1

    if verdict == "complete":
        print("dropped the marker for %s: %s" % (where, sentence))
        return 0

    open_ids = [entry["id"] for entry in document["items"]
                if entry["state"] in OPEN_STATES]
    print("armed the gate on %s" % where)
    print("%s: %s" % (verdict, sentence))
    print("%d open: %s" % (len(open_ids), ", ".join(open_ids)))
    return 0


def cmd_rules(args):
    print(RULES.strip())
    print()
    print("states: %s" % ", ".join(STATES))
    print("item fields: %s" % ", ".join(ITEM_FIELDS))
    print("run fields: %s" % ", ".join(RUN_FIELDS))
    print("publisher: %s --purpose tasks" % PUBLISH_SCRIPT)
    return 0


RULES = """
run-checklist.py — the run's obligations as a page it can read back.

  template    print a seed document, shaped by the run's resolved flags
  tick        set item states and publish, in ONE command - the step-boundary call
  render      write the page from a document
  publish     render, then publish or update through publish-artifact.sh
  items       print the document embedded in a rendered page, local or published
  arm         rewrite the session's gate marker from the items file, no publish
  rules       this

  tick items.json commit=done describe=in-flight:'the panel' --publish

what it guarantees, and what each one is written against:

  tick exists because a page the run has to remember to rewrite is a page that
  goes stale: read-edit-publish is three steps and it was skipped through a
  push, a change request and a review verdict on the very run that built this.
  one command, run in the same batch as the step it records, is the fix

  tick refuses an id the page does not have, so a typo is an error rather than
  a silent no-op that leaves the item behind

  tick clears waiting_on when an item leaves in-flight, so a finished item
  cannot keep advertising a blocker that is gone

  tick clears the note on any state CHANGE unless new text replaces it, so a
  skip reason cannot outlive the skip - an item un-skipped by an amendment
  (--diagram true arriving late) would otherwise read as pending while still
  carrying "not needed". A re-tick of the SAME state keeps its note, so
  annotating an item twice is not destructive

  publish records the page's url and hash into BOTH the items file and the
  page itself, which costs a second write on the first publish only. without
  it the published page embeds an empty identity, so recovering a document
  with `items <url>` - the documented /unpause route - loses the hash and the
  next publish mints a new link, which is the one thing the design forbids

  every field reaching the page is escaped, waiting_on included. that field is
  rendered for a done or skipped item too, and when it was the one unescaped
  path a crafted value could close the table and open a SECOND checklist block
  ahead of the real one - whereupon `items` returned the forged obligations and
  the run believed them, since it is told to trust the page over its context

  extract refuses a page carrying more than one checklist block rather than
  taking the first, so a forged block is a loud error and not a silent swap

  change_request and plan_page are only rendered as links when they are
  http(s); anything else is printed as text, so a javascript: value cannot
  become a clickable link on a page that is published public

  plan_page carries the plan artifact's url through the run, because the items
  file is the only state that already survives both the hand-off to autopilot
  and a pause - the change request's description is written from it, not from
  whatever is still in the context window

  every item carries an obligation, the skill that discharges it, what it
  applies to, what it is waiting on, and one of exactly four states

  an unknown state is an error, never a blank badge - a typo in a state must
  not render as a page that looks fine

  a skipped item with no reason is an error - "skipped" alone records that an
  obligation was dropped and nothing about why

  an in-flight item waiting on nothing is an error - that pairing is the exact
  claim the page exists to make checkable

  the template is shaped by the resolved flags, so the page can neither list a
  diagram the run will not draw nor omit a merge it will perform

  "nothing armed" is computed from the items, never asserted: outstanding work
  with no item in flight renders as an alarm, which is what makes autopilot's
  rule checkable rather than aspirational

  every render carries an updated-at stamp, so a refresh proves the page is
  live rather than a frozen copy

  render then items round-trips byte-for-byte, so re-reading the artifact hands
  the run its obligations as data rather than prose to parse

  items takes the published url as readily as a local file, and follows the
  store's own wrapper to the raw page by reading the iframe it serves - the raw
  host is discovered, never hardcoded, because it differs per machine

  the page is self-contained - no network assets - so it still renders from the
  filesystem on a machine with no store

  exit 3 from publish means this machine has no self-hosted store, passed
  through from publish-artifact.sh unchanged

  every publish expires the page, so the store does not accumulate one
  checklist per run forever - a finished run's page is a record worth keeping
  for a while and clutter after that

  reconcile sets the items whose truth is observable, so the page stops
  depending on the run remembering to tick:

    from the forge      open, pipeline, threads, merge
    from local git      commit, implement - a commit on the branch that is not
                        on the default branch
    from the body       describe (prose beyond the checklist link), ledger (the
                        decision fold)
    from session state  arm (armed_at is present)

  reconcile never touches plan, review, verify or close - no signal for those
  is solid, and deriving one badly is worse than leaving it manual

  every local signal only ever promotes: it ticks an item done when it can see
  the obligation discharged, and says nothing when it cannot. absence is not
  evidence - a merged branch has no commits ahead of its base, and armed_at is
  cleared by /ping off long after the ping was sent, so a two-way signal would
  un-tick finished work and wedge the gate on obligations nobody can re-do

  a skipped item is never revived, so a deliberate skip survives every pass

  an owned item's blocker is refreshed on every pass, not only when it reaches
  a terminal state, so a stale note cannot outlive what it described

  reconcile refuses a url that disagrees with the recorded change request, and
  derives nothing from the forge when no change request is recorded - the facts
  must belong to this checklist

  arm is the way back from notify.py --checklist-clear --force. it rewrites the
  marker from the items file alone - no render, no publish, no network - through
  the same mark_outstanding() every write uses, so there is one definition of
  the marker rather than a second one that can disagree with it. nothing else
  re-armed the gate except the next publish or tick, which is precisely the
  action a stalled run is failing to take
"""


def main():
    parser = argparse.ArgumentParser(
        description="Render and publish a fix/autopilot run's checklist.")
    sub = parser.add_subparsers(dest="command")

    seed = sub.add_parser("template", help="print a seed document on stdout")
    seed.add_argument("--title", default="")
    seed.add_argument("--repo", default="")
    seed.add_argument("--branch", default="")
    seed.add_argument("--ticket", default="")
    seed.add_argument("--request-name", default="",
                      help="this machine's change_request, e.g. pull request")
    seed.add_argument("--branch-mode", choices=("new", "default"), default="new")
    seed.add_argument("--review", action="store_true")
    seed.add_argument("--diagram", action="store_true")
    seed.add_argument("--merge", action="store_true")
    seed.add_argument("--iac", action="store_true")
    seed.set_defaults(func=cmd_template)

    page = sub.add_parser("render", help="write the page from a document")
    page.add_argument("items")
    page.add_argument("out")
    page.add_argument("--stamp", default=None)
    page.set_defaults(func=cmd_render)

    back = sub.add_parser("items", help="print the document embedded in a page")
    back.add_argument("page", help="a rendered file, or the published page's url")
    back.set_defaults(func=cmd_items)

    send = sub.add_parser("publish", help="render, then publish or update in place")
    send.add_argument("items")
    send.add_argument("--update", default="")
    send.add_argument("--out", default="")
    send.add_argument("--stamp", default=None)
    send.set_defaults(func=cmd_publish)

    mark = sub.add_parser(
        "tick", help="set item states and publish the page, in one command")
    mark.add_argument("items")
    mark.add_argument("tick", nargs="+", metavar="ID=STATE[:TEXT]",
                      help="TEXT is what it waits on for in-flight, else the note")
    mark.add_argument("--run", action="append", default=[], metavar="FIELD=VALUE",
                      help="set a run field, e.g. --run change_request=<url>")
    mark.add_argument("--publish", action="store_true",
                      help="also write the page, as an update against the recorded hash")
    mark.add_argument("--update", default="")
    mark.add_argument("--out", default="")
    mark.add_argument("--stamp", default=None)
    mark.set_defaults(func=cmd_tick)

    sync = sub.add_parser(
        "reconcile",
        help="set the forge-observable items from what the forge reports")
    sync.add_argument("items")
    sync.add_argument("--url", default="")
    sync.add_argument("--state", default="")
    sync.add_argument("--merged", default="false")
    sync.add_argument("--review", default="NONE")
    sync.add_argument("--unresolved", default="0")
    sync.add_argument("--checks-pending", dest="checks_pending", default="0")
    sync.add_argument("--checks-failed", dest="checks_failed", default="0")
    sync.add_argument("--checks-total", dest="checks_total", default="0")
    sync.add_argument("--body-file", dest="body_file", default="",
                      help="a file holding the change request body")
    sync.add_argument("--repo", default="",
                      help="the repository to read git facts from (default: cwd)")
    sync.add_argument("--default-branch", dest="default_branch", default="")
    sync.add_argument("--publish", action="store_true")
    sync.add_argument("--update", default="")
    sync.add_argument("--out", default="")
    sync.add_argument("--stamp", default=None)
    sync.set_defaults(func=cmd_reconcile)

    again = sub.add_parser(
        "arm", help="rewrite the session's gate marker from the items file")
    again.add_argument("items")
    again.set_defaults(func=cmd_arm)

    rules = sub.add_parser("rules", help="print what this script guarantees")
    rules.set_defaults(func=cmd_rules)

    args = parser.parse_args()
    if not getattr(args, "func", None):
        parser.print_help(sys.stderr)
        return 2
    try:
        return args.func(args)
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
