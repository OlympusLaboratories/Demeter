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
PLAN_ITEM = "plan"
PLAN_DEPENDENT = ("implement", "commit", "describe", "open")
PLAN_CLEARED = ("done", "skipped")
PLAN_STARTED = ("in-flight", "done")
ITEM_FIELDS = ("id", "obligation", "skill", "target", "waiting_on", "state", "note",
               "link", "stage")
STAGE_FIELDS = ("id", "label", "branch", "change_request", "after")
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


def item(ident, obligation, skill="", target="", waiting_on="", state="pending", note="",
         link="", stage=""):
    return {
        "id": ident,
        "obligation": obligation,
        "skill": skill,
        "target": target,
        "waiting_on": waiting_on,
        "state": state,
        "note": note,
        "link": link,
        "stage": stage,
    }


def stage(ident, label, branch="", change_request="", after=""):
    return {
        "id": ident,
        "label": label,
        "branch": branch,
        "change_request": change_request,
        "after": after,
    }


def base_id(ident):
    return ident.split("@", 1)[0]


def request_items(options, branch, suffix, belongs_to):
    request = "the %s" % (options.request_name or "change request")

    def member(ident, obligation, skill="", target=""):
        return item(ident + suffix, obligation, skill, target, stage=belongs_to)

    items = [
        member("implement", "Implement the change", "", branch),
        member("commit", "Commit with a generated message", "commit-msg", branch),
        member("describe", "Write the change description", "changes-description", branch),
        member("open", "Push and open %s" % request, "autopilot", branch),
        member("link", "Send the user %s's link" % request, "ping", "the user"),
        member("pipeline", "Drive the pipeline green", "autopilot", request),
    ]
    if options.review and not belongs_to:
        items.append(member("review", "Review the diff with the swarm",
                            "review-code", branch))
    items.append(member("threads", "Clear every review thread", "fix-feedback", request))
    if options.iac and options.merge:
        items.append(member("apply", "Apply the infrastructure plan before the merge",
                            "autopilot", request))
    if options.diagram:
        items.append(member("diagram", "Attach the call-flow diagram",
                            "changes-diagram", request))
    if options.merge:
        items.append(member("merge", "Merge %s" % request, "autopilot", request))
    elif options.iac:
        items.append(member("ready",
                            "Hand over %s with its plan unapplied and unmerged"
                            % request, "autopilot", request))
    else:
        items.append(member("ready", "Hand over a ready %s without merging" % request,
                            "autopilot", request))
    items.append(member("ledger", "Append the decision record to the description",
                        "autopilot", request))
    return items


def stack_labels(options):
    return [part.strip() for part in (options.stack or "").split("|") if part.strip()]


def slug(text):
    words = [word for word in re.split(r"[^a-z0-9]+", text.lower()) if word]
    return "-".join(words[:5])


def member_branch(branch, index, label):
    tail = slug(label)
    return "%s/%02d%s" % (branch.rstrip("/"), index, "-" + tail if tail else "")


def template(options):
    branch = options.branch or "<branch>"
    labels = stack_labels(options)
    if labels and options.branch_mode == "default":
        raise ValueError("--stack needs a change request per member, "
                         "which --branch-mode default never opens")

    items = [
        item("arm", "Arm the session's notifications", "ping", "this session"),
        item("plan", "Get the plan approved by the user", "AskUserQuestion",
             options.ticket or "the problem statement"),
    ]
    stages = []

    if options.branch_mode == "default":
        items.append(item("implement", "Implement the change", "", branch))
        items.append(item("commit", "Commit with a generated message",
                          "commit-msg", branch))
        items.append(item("describe", "Write the change description",
                          "changes-description", branch))
        if options.diagram:
            items.append(item("diagram", "Draw and publish the call-flow diagram",
                              "changes-diagram", branch))
        if options.review:
            items.append(item("review", "Review the diff with the swarm",
                              "review-code", branch))
        items.append(item("push", "Push the default branch", "autopilot", branch))
        items.append(item("verify", "Verify the change reached production", "autopilot",
                          "the deploy target"))
    elif not labels:
        items.extend(request_items(options, branch, "", ""))
        items.append(item("verify", "Verify the change reached production", "autopilot",
                          "the deploy target"))
    else:
        if options.review:
            items.append(item("review", "Review every branch in the stack with the swarm",
                              "review-code", "the whole stack"))
        for index, label in enumerate(labels, start=1):
            ident = "%d" % index
            here = member_branch(branch, index, label)
            stages.append(stage(ident, label, here, "",
                                "%d" % (index - 1) if index > 1 else ""))
            items.extend(request_items(options, here, "@" + ident, ident))
            items.append(item("verify@" + ident, "Verify the change reached production",
                              "autopilot", "the deploy target", stage=ident))

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
        "stages": stages,
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

    stages_raw = document.get("stages", [])
    if stages_raw is None:
        stages_raw = []
    if not isinstance(stages_raw, list):
        raise ValueError("%s: stages is not a list" % path)

    stages = []
    declared = []
    for index, entry in enumerate(stages_raw):
        where = "%s: stage %d" % (path, index + 1)
        if not isinstance(entry, dict):
            raise ValueError("%s is not an object" % where)
        clean = {}
        for field in STAGE_FIELDS:
            value = entry.get(field, "")
            if value is None:
                value = ""
            if not isinstance(value, str):
                raise ValueError("%s: %s is not a string" % (where, field))
            clean[field] = value.strip()
        if not clean["id"]:
            raise ValueError("%s has no id" % where)
        if clean["id"] in declared:
            raise ValueError("%s repeats the id %s" % (where, clean["id"]))
        if not clean["label"]:
            raise ValueError("%s (%s) has no label" % (where, clean["id"]))
        if clean["after"] and clean["after"] not in declared:
            raise ValueError("%s (%s) comes after %s, which is not an earlier stage"
                             % (where, clean["id"], clean["after"]))
        declared.append(clean["id"])
        stages.append(clean)

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
        if clean["stage"] and clean["stage"] not in declared:
            raise ValueError("%s (%s) belongs to stage %s, which is not declared"
                             % (where, clean["id"], clean["stage"]))
        items.append(clean)

    return {"run": run, "stages": stages, "items": items}


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


def page_key(run):
    for field in ("hash", "url", "branch"):
        value = str(run.get(field) or "").strip()
        if value:
            return value
    return "unpublished"


def tracked_pages(marker):
    if not isinstance(marker, dict):
        return {}
    if isinstance(marker.get("open"), list):
        return {page_key(marker): dict(marker)}
    return {str(key): dict(value) for key, value in marker.items()
            if isinstance(value, dict)}


def unpublished_twin(page, branch):
    return (not str(page.get("hash") or "").strip()
            and not str(page.get("url") or "").strip()
            and str(page.get("branch") or "") == branch)


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

    run = document["run"]
    branch = run.get("branch", "")
    pages = tracked_pages(state.get("checklist_pending"))
    key = page_key(run)
    for other in [name for name in pages if name != key]:
        if unpublished_twin(pages[other], branch):
            pages.pop(other)

    if verdict == "complete":
        pages.pop(key, None)
    else:
        branches = []
        for name in ([branch]
                     + [entry.get("branch", "") for entry in document["stages"]]):
            if name and name not in branches:
                branches.append(name)
        pages[key] = {
            "url": run.get("url", ""),
            "hash": run.get("hash", ""),
            "branch": branch,
            "branches": branches,
            "at": time.time(),
            "stops": 0,
            "verdict": verdict,
            "open": [entry["id"] for entry in items if entry["state"] in OPEN_STATES],
            "in_flight": [entry["id"] for entry in in_flight],
        }

    if pages:
        state["checklist_pending"] = pages
    else:
        state.pop("checklist_pending", None)
        state.pop("checklist_forked", None)
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


DERIVED_LINK = {
    "plan": "plan_page",
    "implement": "plan_page",
    "open": "change_request",
    "link": "change_request",
    "pipeline": "change_request",
    "threads": "change_request",
    "apply": "change_request",
    "diagram": "change_request",
    "merge": "change_request",
    "ready": "change_request",
    "ledger": "change_request",
}

REQUEST_NUMBER = re.compile(
    r"/([^/]+/[^/]+)/(?:-/)?(?:pull|pulls|merge_requests|pull-requests)/(\d+)")


def item_link(entry, run, stages=None):
    target = entry.get("link")
    if not target:
        field = DERIVED_LINK.get(base_id(entry["id"]), "")
        owner = (stages or {}).get(entry.get("stage") or "")
        if field == "change_request" and owner:
            target = owner.get("change_request", "")
        elif field:
            target = run.get(field, "")
    return target if re.match(r"^https?://", target or "") else ""


def request_fact(url):
    if not re.match(r"^https?://", url):
        return escape(url)
    found = REQUEST_NUMBER.search(url)
    label = "%s#%s" % (found.group(1), found.group(2)) if found else url
    return '<a href="%s">%s</a>' % (escape(url), escape(label))


def stage_row(owner, by_stage):
    facts = []
    if owner["branch"]:
        facts.append("branch <code>%s</code>" % escape(owner["branch"]))
    if owner["change_request"]:
        facts.append(request_fact(owner["change_request"]))
    if owner["after"]:
        earlier = by_stage.get(owner["after"])
        facts.append("after %s" % escape(earlier["label"] if earlier
                                         else owner["after"]))
    else:
        facts.append("first to merge")
    return ('<tr class="stagerow"><td class="stagecell" colspan="6">'
            '<span class="slabel">%s</span>'
            '<span class="smeta">%s</span></td></tr>'
            % (escape(owner["label"]), " · ".join(facts)))


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
        facts.append(request_fact(run["change_request"]))

    by_stage = {entry["id"]: entry for entry in document.get("stages", [])}
    if by_stage:
        facts.append("%d in the stack" % len(by_stage))

    rows = []
    standing_stage = None
    for index, entry in enumerate(items, start=1):
        if entry.get("stage", "") != standing_stage:
            standing_stage = entry.get("stage", "")
            owner = by_stage.get(standing_stage)
            if owner:
                rows.append(stage_row(owner, by_stage))
        waiting = escape(entry["waiting_on"])
        if not waiting:
            waiting = "<em>nothing</em>" if entry["state"] in OPEN_STATES else "—"
        detail = escape(entry["note"]) if entry["note"] else ""
        obligation = escape(entry["obligation"])
        destination = item_link(entry, run, by_stage)
        if destination:
            obligation = '<a href="%s">%s</a>' % (escape(destination), obligation)
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
                obligation,
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
        "at": "%d" % time.time(),
        "icon": ICON,
        "rows": "\n".join(rows),
        "json": dump(document),
    }


ICON = (
    "data:image/svg+xml,"
    "%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064"
    "%2064%22%3E%3Crect%20width%3D%2264%22%20height%3D%2264%22%20rx%3D%2214%22%20fill%3D%22"
    "%230b0e11%22%2F%3E%3Cg%20transform%3D%22translate(32%2032)%20scale(0.86)%20"
    "translate(-32%20-32)%22%3E%3Cpath%20d%3D%22M13%2022l5%205%209-10M13%2042l5%205%209-10"
    "%22%20fill%3D%22none%22%20stroke%3D%22%235ef2a0%22%20stroke-width%3D%224.5%22%20"
    "stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%2F%3E%3Cpath%20d%3D%22M35"
    "%2022h17M35%2042h17%22%20stroke%3D%22%232f8f5f%22%20stroke-width%3D%224.5%22%20"
    "stroke-linecap%3D%22round%22%2F%3E%3C%2Fg%3E%3C%2Fsvg%3E"
)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b0e11">
<link rel="icon" type="image/svg+xml" href="%(icon)s">
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
    margin: 0; background: var(--bg); color: var(--fg);
    padding: 0 16px calc(84px + env(safe-area-inset-bottom, 0px));
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
    tr.stagerow { border: 0; border-radius: 0; padding: 0; margin: 18px 0 10px; }
    td.stagecell { border-bottom: 0; padding: 0; }
    td.stagecell::before { content: none; }
  }
  tr.s-in-flight .badge { color: var(--flight); }
  tr.s-skipped .badge { color: var(--skip); }
  tr.s-pending .badge { color: var(--muted); }
  tr.s-done td.ob, tr.s-skipped td.ob { color: var(--muted); font-weight: 400; }
  footer { margin-top: 32px; color: var(--muted); font-size: 13px; }
  td.stagecell { border-bottom: 1px solid var(--rule); padding: 20px 10px 7px; }
  tr.stagerow:first-child td.stagecell { padding-top: 6px; }
  .slabel { display: block; font-weight: 680; font-size: 15px; }
  .smeta { display: block; color: var(--muted); font-size: 13px; margin-top: 2px; }
  a { color: inherit; text-decoration-color: var(--accent); text-underline-offset: 2px; }
  td.ob a { text-decoration-thickness: 1px; }
  .dock { position: fixed; z-index: 30; display: flex; align-items: center; gap: 8px;
          right: calc(14px + env(safe-area-inset-right, 0px));
          bottom: calc(14px + env(safe-area-inset-bottom, 0px)); }
  .dock .ago { background: var(--card); border: 1px solid var(--rule); border-radius: 999px;
               color: var(--muted); font-size: 12.5px; padding: 6px 11px; white-space: nowrap;
               box-shadow: 0 1px 3px rgba(0, 0, 0, .14); }
  .dock .ago:empty { display: none; }
  .dock button { min-width: 44px; min-height: 44px; border-radius: 999px; cursor: pointer;
                 background: var(--card); color: var(--fg); border: 1px solid var(--rule);
                 font: 600 14px/1 inherit; padding: 0 16px;
                 box-shadow: 0 2px 8px rgba(0, 0, 0, .18); }
  .dock button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .dock button[aria-busy="true"] { color: var(--muted); }
  @media (prefers-reduced-motion: no-preference) {
    .dock button { transition: transform .12s ease; }
    .dock button:active { transform: scale(.96); }
  }
  @media print { .dock { display: none; } }
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
<p class="meta" id="stamp" data-at="%(at)s">%(tally)s · updated %(stamp)s</p>

<div class="wrap">
<table>
  <thead><tr><th></th><th>State</th><th>Obligation</th><th>Skill</th><th>Applies to</th><th>Waiting on</th></tr></thead>
  <tbody>
%(rows)s
  </tbody>
</table>
</div>

<footer>The run rewrites this page in place at every step boundary. Refresh keeps your place on the page.</footer>
</main>

<div class="dock">
  <span class="ago" id="ago" aria-live="polite"></span>
  <button type="button" id="refresh">Refresh</button>
</div>

<script type="application/json" id="checklist">
%(json)s
</script>
<script>
(function () {
  var main = document.querySelector("main");
  var button = document.getElementById("refresh");
  var ago = document.getElementById("ago");
  if (!main || !button || !ago) { return; }

  function since() {
    var stamp = document.getElementById("stamp");
    var at = stamp ? parseFloat(stamp.getAttribute("data-at")) : NaN;
    if (!isFinite(at)) { return ""; }
    var seconds = Math.max(0, Date.now() / 1000 - at);
    if (seconds < 50) { return "just now"; }
    var minutes = Math.round(seconds / 60);
    if (minutes < 60) { return minutes + "m ago"; }
    var hours = Math.round(minutes / 60);
    if (hours < 36) { return hours + "h ago"; }
    return Math.round(hours / 24) + "d ago";
  }

  function paint() { ago.textContent = since(); }

  function swap(text) {
    var parsed = new DOMParser().parseFromString(text, "text/html");
    var fresh = parsed.querySelector("main");
    if (!fresh) { throw new Error("the reply carried no checklist"); }
    var block = parsed.getElementById("checklist");
    var here = document.getElementById("checklist");
    main.innerHTML = fresh.innerHTML;
    if (block && here) { here.textContent = block.textContent; }
    if (parsed.title) { document.title = parsed.title; }
  }

  var busy = false;
  function refresh() {
    if (busy) { return; }
    busy = true;
    button.setAttribute("aria-busy", "true");
    ago.textContent = "checking";
    fetch(location.href, { cache: "no-store", credentials: "same-origin" })
      .then(function (reply) {
        if (!reply.ok) { throw new Error("the store answered " + reply.status); }
        return reply.text();
      })
      .then(function (text) {
        swap(text);
        busy = false;
        button.removeAttribute("aria-busy");
        paint();
      })
      .catch(function () {
        location.reload();
      });
  }

  button.addEventListener("click", refresh);
  paint();
  setInterval(paint, 20000);
})();
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
        if items_path and items_path != "-":
            write(items_path, dump(document) + "\n")
            print("recorded the page identity in %s" % items_path)
        status, url = send(document, page, digest, stamp)
        if status != 0:
            print("published, but the page does not carry its own identity: "
                  "url=%s hash=%s page=%s" % (run["url"], digest, page), file=sys.stderr)
            return status

    print("url=%s" % run["url"])
    print("hash=%s" % run["hash"])
    print("page=%s" % page)
    return 0


def cmd_publish(args):
    document = read_document(args.items)
    status = publish(document, args.items, args.update, args.out, args.stamp)
    mark_outstanding(document)
    return status


PLAN_REFUSED = (
    "the plan gate is not waivable by the size of the change: plan is %s, so"
    " %s cannot be in flight or done. Tick plan=done once the user has"
    " approved the plan, or plan=skipped:<reason> to record that the user"
    " waived it - a reason is required and lands on the page. Either can go"
    " in this same command."
)


def plan_first(items):
    plan = [entry for entry in items if base_id(entry["id"]) == PLAN_ITEM]
    if not plan or any(entry["state"] in PLAN_CLEARED for entry in plan):
        return
    started = [entry for entry in items
               if base_id(entry["id"]) in PLAN_DEPENDENT
               and entry["state"] in PLAN_STARTED]
    if not started:
        return
    raise ValueError(PLAN_REFUSED % (
        plan[0]["state"],
        ", ".join("%s=%s" % (entry["id"], entry["state"]) for entry in started)))


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
    plan_first(document["items"])
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


def locate(document, stage, ident):
    shared = None
    for entry in document["items"]:
        if base_id(entry["id"]) != ident:
            continue
        where = entry.get("stage", "")
        if where == stage:
            return entry
        if not where and shared is None:
            shared = entry
    return shared


def reconcile(document, forge, local=None, stage=""):
    seen = dict(observed(forge))
    seen.update(local or {})
    changed = []
    for ident, (state, text, only_when) in seen.items():
        entry = locate(document, stage, ident)
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
            changed.append("%s~%s" % (entry["id"], state))
            continue
        entry["state"] = state
        entry["waiting_on"] = waiting
        entry["note"] = note
        changed.append("%s=%s" % (entry["id"], state))
    return changed


def cmd_reconcile(args):
    document = read_document(args.items)
    member = None
    if args.stage:
        for entry in document["stages"]:
            if entry["id"] == args.stage:
                member = entry
                break
        if member is None:
            print("no stage %r; the page has %s"
                  % (args.stage, ", ".join(entry["id"] for entry in document["stages"])
                     or "none"), file=sys.stderr)
            return 2
    owner = member or document["run"]
    recorded = (owner.get("change_request") or "").strip()
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
    local = observed_local(repo, owner.get("branch", ""), base, body, session_armed())
    changed = reconcile(document, forge, local, args.stage)
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
            raise ValueError("%r is not <field>=<value> or <stage>:<field>=<value>"
                             % assignment)
        field, _, value = assignment.partition("=")
        field, value = field.strip(), value.strip()
        if ":" in field:
            ident, _, field = field.partition(":")
            ident, field = ident.strip(), field.strip()
            known = [entry["id"] for entry in document["stages"]]
            if ident not in known:
                raise ValueError("no stage %r; the page has %s"
                                 % (ident, ", ".join(known) or "none"))
            if field not in STAGE_FIELDS:
                raise ValueError("no stage field %r; a stage has %s"
                                 % (field, ", ".join(STAGE_FIELDS)))
            document["stages"][known.index(ident)][field] = value
            continue
        if field not in RUN_FIELDS:
            raise ValueError("no run field %r; the page has %s"
                             % (field, ", ".join(RUN_FIELDS)))
        document["run"][field] = value
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
    print("stage fields: %s" % ", ".join(STAGE_FIELDS))
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

  tick refuses to put implement, commit, describe or open in flight or done
  while plan is still pending, because the plan gate is armed only by
  complying with it: a run that never publishes a plan sets no gate marker
  for the Stop hook to hold on, and standing() reads ANY in-flight item as
  healthy, so plan can sit open for a whole run behind a watcher whose
  per-poll reconcile keeps resetting the staleness count. a run judged a
  one-line change too small for a plan and shipped it, which is the judgement
  this refusal takes away. the way through is plan=done, or
  plan=skipped:<reason> - and canonical already requires that reason, so a
  waiver lands on the page the user reads rather than being taken silently.
  both can go in the same command as the tick they unblock, which is the
  shape the fix skills already prescribe, and reconcile writes item states
  directly rather than through this path, so a watcher is never wedged by it

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

  an item links to the artefact it is about, so the page is a way in rather
  than a status board: plan and implement reach the plan page, and every item
  naming the change request reaches it. the url is derived from the run
  fields, so nothing has to remember to set it, and an item's own link field
  overrides the derived one - which is what a stack needs, where the items
  do not share one change request. the http(s) rule above governs both

  a numbered change request is shown as owner/repo#number rather than as a
  bare url, because the raw link wraps over two lines on the phone the page
  is read on. a url the pattern does not recognise is printed whole

  the page refreshes itself without reloading: the control fetches the page's
  own url and swaps the body in place, so the scroll position survives by
  construction rather than by saving it. browser storage is deliberately not
  used - this page is served cross-origin inside the store's frame, where
  safari may refuse it outright - and a fetch that throws falls back to a
  plain reload, which is the case when the page is opened from a file

  the page declares its own icon as a data uri. the store reads the first one
  out of the html and re-emits it for the wrapper and the manifest, so a page
  that declares none wears whatever icon the origin last installed. an
  external icon file cannot be used: the page must stay self-contained

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

  --iac without --merge carries no apply item at all, because --merge false
  holds the apply as well as the merge: an item the run is forbidden to
  discharge would sit pending to the end, report a finished run as incomplete
  and wedge the Stop gate. the ready item says the plan is unapplied instead

  the items are in the order the run discharges them, and the diagram comes
  before the merge: autopilot draws it at Step 8b, because the merge deletes
  the branch and the worktree that changes-diagram derives its base from

  a run needing several change requests in order declares a stage per member
  with --stack, and the page then carries the thing a flat list cannot say:
  which branch each member is on, which change request it became, and which
  member it merges after. a stack was previously tracked in a side file no
  page ever read, so the checklist described one member and said nothing
  about the others

  only --stack suffixes the item ids, as open@2, and the ordinary template is
  byte-for-byte what it always was. that is deliberate rather than tidy: the
  gate's own tests look items up by their bare id, and more to the point a
  run with one change request should not pay in readability for a shape it is
  not using

  a stage's items are matched on the BASE id, so the forge signals keep
  working per member: reconcile --stage 2 writes that member's open,
  pipeline, threads and merge, refuses a url disagreeing with the change
  request that member recorded, and reads commit and implement from that
  member's own branch. one watcher runs per change request, so without the
  stage every member would write onto the same items

  a stage falls back to the shared items for anything it does not own, which
  is how arm stays one obligation across a whole stack rather than one per
  member

  the swarm is one item for the whole stack, never one per member, because
  running one per member is how a stack spends four figures of agents in five
  minutes. the merge, the verify and the deploy ARE per member - every merge
  to the default branch fires its own deploy, so an intermediate failure is a
  real failure and needs its own item to be visible

  "nothing armed" is computed from the items, never asserted: outstanding work
  with no item in flight renders as an alarm, which is what makes autopilot's
  rule checkable rather than aspirational

  every render carries an updated-at stamp, so a refresh proves the page is
  live rather than a frozen copy. it carries the same instant as a number
  too, which the page ages into "7m ago" - the absolute stamp alone does not
  answer the question a refresh is asking

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

  reconcile never touches plan, review, apply, verify or close - no signal for
  those is solid, and deriving one badly is worse than leaving it manual. apply
  is also seeded only on a merging run, so on --merge false there is no item to
  derive

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

  the marker carries the run's branch, so notify.py's Stop gate can see a
  session that has moved to a second branch. a branch that publishes nothing
  writes nothing, so without it the gate has nothing to hold on and the first
  page describes a run that no longer exists

  it carries every STAGE's branch beside it, because a stack moves between
  its members by design and holding the turn each time would make the gate
  something to switch off. a branch no tracked page claims still holds,
  which is the case the gate is for

  the marker holds ONE RECORD PER PAGE, keyed by the page's identity - its
  hash, else its url, else its branch. a run driving several change requests
  publishes a page each, and a single slot made whichever page wrote last
  the session's whole truth: the fork gate then held a correct run, and
  every other page's staleness became untrackable, since each write resets
  the stop count and a watcher polling one page kept the slot fresh forever.
  unioning the branches into one record was the smaller fix and was rejected
  for that second reason - it buys silence on the false hold by leaving the
  stale-page gate permanently reset

  a page with no identity yet is replaced rather than duplicated when the
  same branch's page is published: a publish that found no artifact store
  still marks the run, keyed by branch, and the url it later earns must not
  strand that first record with an open list nobody can tick

  a publish records the url it reached in the items file BEFORE rewriting the
  page to carry its own identity, because that second write is a separate
  round trip that can fail on its own. the url is already live by then, so
  losing it costs twice: the marker keys the page by a digest the items file
  does not have, and the next publish has no hash to --update, so it mints a
  second page and the link in the change request freezes

  a tracked page can be dropped on its own with notify.py --checklist-clear
  --page <url|branch> --force, since the marker now holds several and a
  forced clear would otherwise disarm the gate for every page at once

  every write rebuilds its own page's record from scratch, so the gate's
  spent-fork record lives in checklist_forked BESIDE the marker rather than
  inside any record - a field inside one is wiped by every publish, tick,
  reconcile and arm to that page, which turns "hold once" into "hold at every
  turn end". it is dropped only with the marker itself, when the last page's
  items are all done or skipped

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
    seed.add_argument("--stack", default="",
                      help="pipe-separated member labels, in merge order, for a run "
                           "that needs several change requests")
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
                      help="set a run field, e.g. --run change_request=<url>, or a "
                           "stage's with --run 2:change_request=<url>")
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
    sync.add_argument("--stage", default="",
                      help="which stack member these facts belong to")
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
