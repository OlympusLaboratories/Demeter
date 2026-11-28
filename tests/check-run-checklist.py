#!/usr/bin/env python3

import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = (
    "larrabeedylan_work_darwin",
    "larrabeedylan_work_linux",
    "larrabeedylan_home_darwin",
)

RULES = """
run-checklist.py, checked over every profile copy:

  rules                                       exits 0 and names every state
  template                                    a valid document, arming first
  template                                    carries the link item ping discharges
  template --review / --diagram / --merge     gate the review, diagram and merge items
  template --diagram                          the diagram sits after the apply gate and
                                              before the merge, and before the ready
                                              hand-over when there is no merge
  template --merge absent                     a "ready, not merged" item instead
  template --iac without --merge              no apply item, and the ready item says the
                                              plan is unapplied - --merge false holds the
                                              apply as well as the merge
  template --branch-mode default              no change request, no merge, no ledger item
  template --request-name                     this machine's word reaches every item
  tick <id>=<state>                           rewrites the items file in place
  tick <id>=in-flight:<text>                  sets what it is waiting on
  tick <id>=done after in-flight              clears waiting_on
  tick <id>=skipped:<reason>                   sets the note
  tick <id>=pending after skipped             clears the stale skip reason
  tick <id>=in-flight after skipped           clears the stale skip reason
  tick <id>=<same state> with no text         keeps the note it already had
  tick <id>=<new state>:<text>                replaces the note
  tick with an id the page lacks              exits non-zero, names the ids it has
  tick with a state that is not one of four   exits non-zero
  tick implement/commit/describe/open while   exits non-zero, names plan, and leaves
    plan is still pending                     the items file untouched
  tick <gated>@<stage> while plan is pending  exits non-zero - a stack's suffixed item
                                              is gated by the one shared plan item
  tick pipeline while plan is pending         exits 0 - the refusal is the plan's
                                              dependents and not an ordering rule
  tick plan=done <gated>=in-flight            exits 0 in ONE command, the shape the
                                              fix skills prescribe
  tick plan=skipped:<reason> <gated>=...      exits 0 - a waiver the user gave is
                                              recorded on the page, never assumed
  template --merge / --merge absent           the ledger item sits ahead of the merge,
                                              and ahead of the ready hand-over
  tick merge/ready while the ledger is        exits non-zero, names the ledger, and
    still pending                             leaves the items file untouched
  tick ledger=done merge=in-flight            exits 0 in ONE command, and so does
                                              ledger=skipped:<reason> for an empty one
  tick merge@2 while ledger@2 is pending      exits non-zero - a stack's record is
                                              paired by suffix, so clearing ledger@2
                                              never releases merge@1
  tick pipeline while the ledger is pending   exits 0 - the refusal is the record's
                                              dependents and not an ordering rule
  tick --run <field>=<value>                  sets a run field
  tick --run with an unknown field            exits non-zero
  tick --publish                              publishes as an update
  publish                                     records url and hash into the items file
  render then items                           round-trips byte for byte
  an unknown state                            exits non-zero
  a skipped item with no reason               exits non-zero
  an in-flight item waiting on nothing        exits non-zero
  a repeated item id                          exits non-zero
  an item with no obligation                  exits non-zero
  items missing or empty                      exits non-zero
  a page with no checklist block              exits non-zero
  items <url> serving the page directly       round-trips
  items <url> serving the store's wrapper     follows the iframe to the raw page
  items <url> that 404s                       exits non-zero
  every item pending                          the page says nothing is armed
  the page icon                               matches publish-artifact.sh ICON_TASKS
  one item in flight                          the page says what it is waiting on
  every item done or skipped                  the page says complete
  a "</script>" in an item                    is escaped, and still round-trips
  an obligation carrying HTML                 is escaped in the table
  waiting_on carrying HTML, item done         is escaped in the table
  waiting_on carrying HTML, item skipped      is escaped in the table
  waiting_on forging a checklist block        does not become the items `items` returns
  a page with two checklist blocks            exits non-zero rather than taking the first
  change_request that is not http(s)          renders as text, never as an href
  change_request that is http(s)              renders as an href
  plan_page that is not http(s)               renders as text, never as an href
  plan_page that is http(s)                   renders as an href
  either field, however rendered              appears once in the facts, never
                                              duplicated by a shared helper
  tick --run plan_page=<url>                  sets it, and it survives the page
  every render                                carries the updated-at stamp
  the page                                    loads nothing over the network
  publish, no store                           passes exit 3 through unchanged
  publish, store present                      sends --purpose tasks, prints url= and hash=
  publish, first time                         two calls: create, then update to embed
                                              its own identity in the page
  publish, identity already recorded          one call, as an update
  every publish call                          sends --purpose tasks and --expires 30d
  publish with a recorded hash                sends --update, so the link cannot change
  publish                                     embeds the identity in the PAGE too
  items <page> then tick --publish             still sends --update, so recovery keeps
                                              the link the user already has

tick is the step-boundary command and it is tested hardest, because the failure it exists
to prevent is the one that actually happened: the page on the run that built this went
stale through a push, a change request and a review verdict, since read-edit-publish is
three steps and three steps get skipped. One command that validates and publishes is the
fix, so an id it does not recognise must be an error rather than a silent no-op.

The page is the run's own record of what it still owes, so a defect here is silent by
construction: a state the renderer does not recognise, an item claiming to be in flight
with nothing behind it, or a second publish that mints a new link all leave a page that
looks right. Each one is an error rather than a blank badge.

"Nothing armed" is computed from the items rather than asserted by the run, which is what
makes autopilot's never-yield-with-nothing-armed rule checkable.

The url cases run against a loopback server in this process, so the suite reaches no
network. They exist because the self-hosted store does not serve the page at the link it
prints: it wraps it in a chrome shell and puts the artifact in an iframe on a second host.
A read that stops at the wrapper finds no checklist block and reports a page with no
items, so following the iframe is what makes re-reading the artifact work at all - and the
raw host is discovered from that wrapper rather than hardcoded, because it differs per
machine.
"""


SANDBOX_HOME = None
SANDBOX_SESSION = "00000000-1111-2222-3333-444444444444"


def sandboxed(env):
    env = dict(os.environ if env is None else env)
    if SANDBOX_HOME:
        env["HOME"] = SANDBOX_HOME
    env["CLAUDE_CODE_SESSION_ID"] = SANDBOX_SESSION
    env["CLAUDE_SESSION_ID"] = SANDBOX_SESSION
    return env


def run(script, *args, **kwargs):
    kwargs["env"] = sandboxed(kwargs.get("env"))
    return subprocess.run(
        [sys.executable, script] + list(args),
        capture_output=True, text=True, **kwargs)


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
                print("      %s" % detail.strip().replace("\n", "\n      "))

    def exits(self, label, want, finished):
        self.ok(label, finished.returncode == want,
                "want exit %s, got %s\n%s" % (want, finished.returncode,
                                              finished.stderr or finished.stdout))


def facts_block(rendered):
    opener = '<p class="facts">'
    start = rendered.find(opener)
    if start < 0:
        return ""
    start += len(opener)
    return rendered[start:rendered.find("</p>", start)]


CHECKLIST_BLOCK = '<script type="application/json" id="checklist">'


def intact(rendered):
    return (rendered.count("</script>") == rendered.count("<script")
            and rendered.count(CHECKLIST_BLOCK) == 1)


def script_tally(rendered):
    return ("%d <script, %d </script>, %d checklist block(s)"
            % (rendered.count("<script"), rendered.count("</script>"),
               rendered.count(CHECKLIST_BLOCK)))


def document(items, run_fields=None):
    return json.dumps({"run": run_fields or {"title": "t"}, "items": items})


def write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def ids(payload):
    return [entry["id"] for entry in json.loads(payload)["items"]]


def tasks_glyph(profile):
    """The checklist glyph as publish-artifact.sh defines it, or None.

    run-checklist.py carries its own copy because the page declares an icon rather
    than having one injected, so nothing at run time makes the two agree. Reading
    the shell variable from Python would couple the two scripts at run time to stop
    them drifting at rest; asserting they are equal costs nothing and fails here,
    where the drift is, instead of on a published page nobody re-reads.
    """
    path = os.path.join(REPO, "profiles", profile, ".claude", "scripts",
                        "publish-artifact.sh")
    try:
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
    except OSError:
        return None
    match = re.search(r"^ICON_TASKS='(data:[^']+)'$", source, re.M)
    return match.group(1) if match else None


def check_profile(suite, profile, work):
    script = os.path.join(REPO, "profiles", profile, ".claude", "scripts",
                          "run-checklist.py")
    tag = "%s:" % profile
    if not os.path.exists(script):
        suite.ok("%s has a run-checklist.py" % tag, False)
        return
    suite.ok("%s run-checklist.py is executable" % tag, os.access(script, os.X_OK))

    finished = run(script, "rules")
    suite.exits("%s rules" % tag, 0, finished)
    for state in ("pending", "in-flight", "done", "skipped"):
        suite.ok("%s rules names the %s state" % (tag, state),
                 state in finished.stdout)

    full = run(script, "template", "--title", "T", "--repo", "R", "--branch", "b",
               "--ticket", "TKT-1", "--review", "--diagram", "--merge", "--iac")
    suite.exits("%s template" % tag, 0, full)
    full_ids = ids(full.stdout)
    suite.ok("%s template arms first" % tag, full_ids[0] == "arm",
             "first item is %s" % full_ids[0])
    for wanted in ("review", "diagram", "merge", "apply", "ledger", "link", "close"):
        suite.ok("%s template carries the %s item" % (tag, wanted),
                 wanted in full_ids, "got %s" % full_ids)
    suite.ok("%s the diagram comes before the merge" % tag,
             full_ids.index("diagram") < full_ids.index("merge"),
             "got %s" % full_ids)
    suite.ok("%s the diagram comes after the apply gate" % tag,
             full_ids.index("apply") < full_ids.index("diagram"),
             "got %s" % full_ids)
    suite.ok("%s the decision record comes before the merge" % tag,
             full_ids.index("ledger") < full_ids.index("merge"),
             "got %s" % full_ids)

    held = run(script, "template", "--diagram")
    suite.exits("%s template --diagram without --merge" % tag, 0, held)
    held_ids = ids(held.stdout)
    suite.ok("%s the diagram comes before the ready hand-over" % tag,
             held_ids.index("diagram") < held_ids.index("ready"),
             "got %s" % held_ids)
    suite.ok("%s the decision record comes before the ready hand-over" % tag,
             held_ids.index("ledger") < held_ids.index("ready"),
             "got %s" % held_ids)

    unapplied = run(script, "template", "--iac")
    suite.exits("%s template --iac without --merge" % tag, 0, unapplied)
    unapplied_ids = ids(unapplied.stdout)
    suite.ok("%s a held run carries no apply item" % tag,
             "apply" not in unapplied_ids, "got %s" % unapplied_ids)
    suite.ok("%s a held run hands over an unapplied plan" % tag,
             "ready" in unapplied_ids
             and "plan unapplied and unmerged" in unapplied.stdout,
             unapplied.stdout)

    applied = run(script, "template", "--iac", "--merge")
    suite.exits("%s template --iac --merge" % tag, 0, applied)
    suite.ok("%s a merging run still carries the apply item" % tag,
             "apply" in ids(applied.stdout), "got %s" % ids(applied.stdout))

    bare = run(script, "template")
    suite.exits("%s template with no flags" % tag, 0, bare)
    bare_ids = ids(bare.stdout)
    for absent in ("review", "diagram", "merge", "apply"):
        suite.ok("%s an unflagged template omits the %s item" % (tag, absent),
                 absent not in bare_ids, "got %s" % bare_ids)
    suite.ok("%s an unflagged template says ready, not merged" % tag,
             "ready" in bare_ids, "got %s" % bare_ids)

    named = run(script, "template", "--merge", "--request-name", "pull request")
    suite.exits("%s template --request-name" % tag, 0, named)
    suite.ok("%s the machine's own word reaches the items" % tag,
             "Merge the pull request" in named.stdout
             and "change request" not in named.stdout, named.stdout)

    default = run(script, "template", "--branch-mode", "default", "--merge")
    suite.exits("%s template --branch-mode default" % tag, 0, default)
    default_ids = ids(default.stdout)
    for absent in ("open", "link", "pipeline", "threads", "merge", "ready", "ledger"):
        suite.ok("%s a default-branch template omits the %s item" % (tag, absent),
                 absent not in default_ids, "got %s" % default_ids)
    suite.ok("%s a default-branch template pushes" % tag, "push" in default_ids,
             "got %s" % default_ids)

    seed = write(os.path.join(work, "seed.json"), full.stdout)
    page = os.path.join(work, "page.html")
    suite.exits("%s render" % tag, 0, run(script, "render", seed, page, "--stamp", "S"))
    back = run(script, "items", page)
    suite.exits("%s items" % tag, 0, back)
    suite.ok("%s render then items round-trips" % tag, back.stdout == full.stdout,
             "the document changed shape through the page")

    body = open(page, encoding="utf-8").read()
    suite.ok("%s the page carries the stamp" % tag, "S" in body)
    suite.ok("%s the page says nothing is armed" % tag,
             "Nothing armed" in body and "nothing is in flight" in body)
    for scheme in ("http://", "https://", "//cdn", "//fonts"):
        suite.ok("%s the page loads no %s asset" % (tag, scheme),
                 scheme not in body.replace('<html lang="en">', ""),
                 "found %s" % scheme)

    suite.ok("%s the page declares its own icon" % tag,
             'rel="icon"' in body and 'href="data:image/svg+xml,' in body,
             "the store's fallback icon would be used instead")
    suite.ok("%s the page icon matches publish-artifact.sh ICON_TASKS" % tag,
             tasks_glyph(profile) is not None and tasks_glyph(profile) in body,
             "the two copies of the checklist glyph have drifted apart")
    suite.ok("%s the refresh control is in the page" % tag,
             'id="refresh"' in body and 'class="dock"' in body)
    suite.ok("%s the refresh control is pinned to the corner" % tag,
             ".dock { position: fixed" in body)
    suite.ok("%s the refresh control clears the home indicator" % tag,
             "env(safe-area-inset-bottom" in body)
    suite.ok("%s the page carries a machine-readable stamp to age" % tag,
             'id="stamp" data-at="' in body)
    suite.ok("%s refreshing swaps rather than reloads" % tag,
             "fetch(location.href" in body and "DOMParser" in body)
    suite.ok("%s a failed refresh falls back to a reload" % tag,
             "location.reload()" in body)

    armed = json.loads(full.stdout)
    armed["items"][0]["state"] = "in-flight"
    armed["items"][0]["waiting_on"] = "a Monitor on the pipeline"
    armed_page = os.path.join(work, "armed.html")
    suite.exits("%s render an armed run" % tag, 0,
                run(script, "render",
                    write(os.path.join(work, "armed.json"), json.dumps(armed)),
                    armed_page, "--stamp", "S"))
    armed_body = open(armed_page, encoding="utf-8").read()
    suite.ok("%s an armed run says so" % tag, "Armed" in armed_body)
    suite.ok("%s an armed run names what it waits on" % tag,
             "a Monitor on the pipeline" in armed_body)

    done = json.loads(full.stdout)
    for entry in done["items"]:
        entry["state"] = "done"
    done_page = os.path.join(work, "done.html")
    suite.exits("%s render a finished run" % tag, 0,
                run(script, "render",
                    write(os.path.join(work, "done.json"), json.dumps(done)),
                    done_page, "--stamp", "S"))
    suite.ok("%s a finished run says complete" % tag,
             "Complete" in open(done_page, encoding="utf-8").read())

    nasty = {
        "run": {"title": "a </script> title"},
        "items": [{"id": "a", "obligation": "drop </script> & <b>bold</b>",
                   "state": "done"}],
    }
    nasty_page = os.path.join(work, "nasty.html")
    suite.exits("%s render escapes markup" % tag, 0,
                run(script, "render",
                    write(os.path.join(work, "nasty.json"), json.dumps(nasty)),
                    nasty_page, "--stamp", "S"))
    nasty_body = open(nasty_page, encoding="utf-8").read()
    suite.ok("%s no stray </script> closes the block early" % tag,
             intact(nasty_body), script_tally(nasty_body))
    suite.ok("%s the obligation's markup is escaped" % tag,
             "<b>bold</b>" not in nasty_body)
    nasty_back = run(script, "items", nasty_page)
    suite.exits("%s items reads an escaped page" % tag, 0, nasty_back)
    suite.ok("%s an escaped page round-trips" % tag,
             json.loads(nasty_back.stdout)["items"][0]["obligation"]
             == "drop </script> & <b>bold</b>",
             nasty_back.stdout)

    forged = ('</td></tr></table><script type="application/json" id="checklist">'
              '{"run":{},"items":[{"id":"fake","obligation":"nothing left",'
              '"state":"done"}]}</script><table><tr><td>')
    for state in ("done", "skipped"):
        hostile = {
            "run": {"title": "t"},
            "items": [{"id": "pipeline", "obligation": "Drive the pipeline green",
                       "state": state, "note": "a reason", "waiting_on": forged}],
        }
        out = os.path.join(work, "hostile-%s.html" % state)
        suite.exits("%s render a %s item with markup in waiting_on" % (tag, state), 0,
                    run(script, "render",
                        write(os.path.join(work, "hostile.json"), json.dumps(hostile)),
                        out, "--stamp", "S"))
        rendered = open(out, encoding="utf-8").read()
        suite.ok("%s waiting_on is escaped on a %s item" % (tag, state),
                 forged[:40] not in rendered,
                 "the raw payload reached the page")
        suite.ok("%s a %s item's waiting_on cannot add a script tag" % (tag, state),
                 intact(rendered), script_tally(rendered))
        recovered = run(script, "items", out)
        suite.ok("%s a forged block never becomes the items (%s)" % (tag, state),
                 recovered.returncode != 0
                 or json.loads(recovered.stdout)["items"][0]["id"] == "pipeline",
                 recovered.stdout)

    two = write(os.path.join(work, "two-blocks.html"),
                '<script type="application/json" id="checklist">'
                '{"run":{},"items":[{"id":"a","obligation":"o","state":"done"}]}</script>'
                '<script type="application/json" id="checklist">'
                '{"run":{},"items":[{"id":"b","obligation":"o","state":"done"}]}</script>')
    suite.ok("%s a page with two checklist blocks is rejected" % tag,
             run(script, "items", two).returncode != 0)

    for field, label in (("change_request", ""), ("plan_page", "plan")):
        for target, linked in (("javascript:alert(1)", False),
                               ("not a url", False),
                               ("https://example.invalid/pull/9", True)):
            doc = {"run": {"title": "t", field: target},
                   "items": [{"id": "a", "obligation": "o", "state": "done"}]}
            out = os.path.join(work, "cr.html")
            suite.exits("%s render %s %r" % (tag, field, target[:20]), 0,
                        run(script, "render",
                            write(os.path.join(work, "cr.json"), json.dumps(doc)),
                            out, "--stamp", "S"))
            rendered = open(out, encoding="utf-8").read()
            suite.ok("%s %s %r is %s" % (tag, field, target[:20],
                                         "a link" if linked else "text only"),
                     ('href="%s"' % target in rendered) == linked, target)
            shown = facts_block(rendered)
            want = 2 if linked and not label else 1
            suite.ok("%s %s %r appears %d time(s) in the facts"
                     % (tag, field, target[:20], want),
                     shown.count(target) == want, shown[:160])
            if label:
                suite.ok("%s %s %r carries its label" % (tag, field, target[:20]),
                         shown.count(label) == 1, shown[:160])

    numbered = "https://forge.invalid/acme/widgets/pull/54"
    doc = {"run": {"title": "t", "change_request": numbered},
           "items": [{"id": "a", "obligation": "o", "state": "done"}]}
    out = os.path.join(work, "numbered.html")
    suite.exits("%s render a numbered change request" % tag, 0,
                run(script, "render",
                    write(os.path.join(work, "numbered.json"), json.dumps(doc)),
                    out, "--stamp", "S"))
    shown = facts_block(open(out, encoding="utf-8").read())
    suite.ok("%s a numbered change request is shown short" % tag,
             "acme/widgets#54" in shown and shown.count(numbered) == 1, shown[:160])

    plan_url = "https://plans.invalid/abc"
    request_url = "https://forge.invalid/acme/widgets/pull/7"
    other_url = "https://plans.invalid/zzz"
    linked = {"run": {"title": "t", "plan_page": plan_url,
                      "change_request": request_url},
              "items": [{"id": "implement", "obligation": "Implement the change",
                         "state": "pending"},
                        {"id": "merge", "obligation": "Merge it", "state": "pending"},
                        {"id": "arm", "obligation": "Arm it", "state": "pending"},
                        {"id": "close", "obligation": "Close it", "state": "pending",
                         "link": other_url}]}
    out = os.path.join(work, "linked.html")
    suite.exits("%s render a run with both pages recorded" % tag, 0,
                run(script, "render",
                    write(os.path.join(work, "linked.json"), json.dumps(linked)),
                    out, "--stamp", "S"))
    rendered = open(out, encoding="utf-8").read()
    rows = rendered[rendered.find("<tbody>"):]
    suite.ok("%s the implement item links to the plan" % tag,
             '<a href="%s">Implement the change</a>' % plan_url in rows, rows[:400])
    suite.ok("%s a request item links to the change request" % tag,
             '<a href="%s">Merge it</a>' % request_url in rows, rows[:400])
    suite.ok("%s an item with no artefact is not a link" % tag,
             '<a href="%s">Arm it</a>' % plan_url not in rows
             and '<a href="%s">Arm it</a>' % request_url not in rows, rows[:400])
    suite.ok("%s an item's own link wins over the derived one" % tag,
             '<a href="%s">Close it</a>' % other_url in rows, rows[:400])
    suite.ok("%s an item link stays out of the facts" % tag,
             facts_block(rendered).count(plan_url) == 1, facts_block(rendered)[:160])

    linked["run"]["plan_page"] = "javascript:alert(1)"
    linked["items"][3]["link"] = "javascript:alert(2)"
    out = os.path.join(work, "linked-hostile.html")
    suite.exits("%s render a run with hostile page urls" % tag, 0,
                run(script, "render",
                    write(os.path.join(work, "linked-hostile.json"),
                          json.dumps(linked)),
                    out, "--stamp", "S"))
    rendered = open(out, encoding="utf-8").read()
    suite.ok("%s a hostile plan page never becomes an item link" % tag,
             'href="javascript:alert(1)"' not in rendered)
    suite.ok("%s a hostile item link is refused too" % tag,
             'href="javascript:alert(2)"' not in rendered)

    stacked = run(script, "template", "--branch", "dylan/registry",
                  "--request-name", "pull request", "--review", "--merge",
                  "--stack", "load the registry|migrate the call sites")
    suite.exits("%s a stacked template" % tag, 0, stacked)
    stack_doc = json.loads(stacked.stdout)
    stack_ids = [entry["id"] for entry in stack_doc["items"]]

    suite.ok("%s a stack declares one stage per member" % tag,
             [entry["id"] for entry in stack_doc["stages"]] == ["1", "2"],
             stack_doc["stages"])
    suite.ok("%s a stage carries its label" % tag,
             [entry["label"] for entry in stack_doc["stages"]]
             == ["load the registry", "migrate the call sites"], stack_doc["stages"])
    suite.ok("%s a stage carries an ordinal branch" % tag,
             stack_doc["stages"][0]["branch"] == "dylan/registry/01-load-the-registry",
             stack_doc["stages"][0])
    suite.ok("%s a stage says which one it follows" % tag,
             [entry["after"] for entry in stack_doc["stages"]] == ["", "1"],
             stack_doc["stages"])
    suite.ok("%s a stacked run still arms first and closes last" % tag,
             stack_ids[0] == "arm" and stack_ids[-1] == "close", stack_ids)
    for bare in ("implement", "commit", "open", "merge", "ledger", "verify"):
        suite.ok("%s %s is per member, never bare, in a stack" % (tag, bare),
                 bare not in stack_ids
                 and ("%s@1" % bare) in stack_ids and ("%s@2" % bare) in stack_ids,
                 stack_ids)
    suite.ok("%s the swarm is one item for the whole stack" % tag,
             stack_ids.count("review") == 1 and "review@1" not in stack_ids,
             stack_ids)
    suite.ok("%s every member item names its stage" % tag,
             all(entry["stage"] == entry["id"].split("@")[1]
                 for entry in stack_doc["items"] if "@" in entry["id"]),
             stack_doc["items"])
    suite.ok("%s a shared item belongs to no stage" % tag,
             all(entry["stage"] == "" for entry in stack_doc["items"]
                 if "@" not in entry["id"]), stack_doc["items"])
    suite.ok("%s each member merges after its own threads" % tag,
             stack_ids.index("threads@1") < stack_ids.index("merge@1")
             < stack_ids.index("implement@2"), stack_ids)

    suite.exits("%s a stack on the default branch is refused" % tag, 1,
                run(script, "template", "--branch-mode", "default",
                    "--stack", "one|two"))

    stack_seed = write(os.path.join(work, "stack.json"), stacked.stdout)
    marked = run(script, "tick", stack_seed, "merge@2=pending",
                 "--run", "1:change_request=https://forge.invalid/acme/widgets/pull/1")
    suite.exits("%s a stage field can be set" % tag, 0, marked)
    suite.exits("%s an unknown stage is refused" % tag, 1,
                run(script, "tick", stack_seed, "merge@2=pending",
                    "--run", "9:change_request=https://forge.invalid/x/y/pull/1"))
    suite.exits("%s an unknown stage field is refused" % tag, 1,
                run(script, "tick", stack_seed, "merge@2=pending",
                    "--run", "1:nonsense=x"))

    stack_page = os.path.join(work, "stack.html")
    suite.exits("%s render a stack" % tag, 0,
                run(script, "render", stack_seed, stack_page, "--stamp", "S"))
    stack_body = open(stack_page, encoding="utf-8").read()
    suite.ok("%s the page heads each member" % tag,
             stack_body.count('class="stagerow"') == 2, stack_body.count("stagerow"))
    suite.ok("%s a member heading names its branch" % tag,
             "dylan/registry/02-migrate-the-call-sites" in stack_body)
    suite.ok("%s a member heading names what it follows" % tag,
             "after load the registry" in stack_body)
    suite.ok("%s the first member says it merges first" % tag,
             "first to merge" in stack_body)
    suite.ok("%s a member item links to its own change request" % tag,
             '<a href="https://forge.invalid/acme/widgets/pull/1">Merge the pull'
             ' request</a>' in stack_body, stack_body[-600:])
    suite.ok("%s a member with no change request links nothing" % tag,
             stack_body.count(">Merge the pull request</a>") == 1, stack_body[-600:])
    suite.ok("%s a stacked page is still one checklist block" % tag,
             intact(stack_body), script_tally(stack_body))
    stack_back = run(script, "items", stack_page)
    suite.exits("%s items reads a stacked page" % tag, 0, stack_back)
    suite.ok("%s a stacked page round-trips" % tag,
             json.loads(stack_back.stdout)["stages"]
             == json.loads(open(stack_seed, encoding="utf-8").read())["stages"],
             stack_back.stdout[:300])

    bad_stages = (
        ("a repeated stage id",
         [{"id": "1", "label": "a"}, {"id": "1", "label": "b"}], []),
        ("a stage with no label", [{"id": "1", "label": ""}], []),
        ("a stage after an unknown one",
         [{"id": "1", "label": "a", "after": "9"}], []),
        ("a stage after a later one",
         [{"id": "1", "label": "a", "after": "2"}, {"id": "2", "label": "b"}], []),
        ("a stage field that is not a string", [{"id": "1", "label": 7}], []),
        ("an item in an undeclared stage", [], [{"id": "x", "obligation": "o",
                                                 "state": "done", "stage": "9"}]),
    )
    for label, stages, extra in bad_stages:
        payload = json.dumps({
            "run": {"title": "t"},
            "stages": stages,
            "items": extra or [{"id": "a", "obligation": "o", "state": "done"}],
        })
        suite.exits("%s %s is rejected" % (tag, label), 1,
                    run(script, "render",
                        write(os.path.join(work, "badstage.json"), payload),
                        os.path.join(work, "badstage.html"), "--stamp", "S"))

    suite.exits("%s stages that is not a list is rejected" % tag, 1,
                run(script, "render",
                    write(os.path.join(work, "notalist.json"),
                          json.dumps({"run": {"title": "t"}, "stages": {},
                                      "items": [{"id": "a", "obligation": "o",
                                                 "state": "done"}]})),
                    os.path.join(work, "notalist.html"), "--stamp", "S"))

    rejects = (
        ("an unknown state",
         document([{"id": "a", "obligation": "o", "state": "doneish"}])),
        ("a skipped item with no reason",
         document([{"id": "a", "obligation": "o", "state": "skipped"}])),
        ("an in-flight item waiting on nothing",
         document([{"id": "a", "obligation": "o", "state": "in-flight"}])),
        ("a repeated id",
         document([{"id": "a", "obligation": "o", "state": "done"},
                   {"id": "a", "obligation": "p", "state": "done"}])),
        ("an item with no obligation",
         document([{"id": "a", "obligation": "", "state": "done"}])),
        ("an item with no id",
         document([{"id": "", "obligation": "o", "state": "done"}])),
        ("an empty item list", document([])),
        ("no item list", json.dumps({"run": {"title": "t"}})),
        ("a document that is not an object", json.dumps([1, 2, 3])),
        ("a non-string field",
         document([{"id": "a", "obligation": "o", "state": "done", "note": 7}])),
    )
    for label, payload in rejects:
        bad = write(os.path.join(work, "bad.json"), payload)
        finished = run(script, "render", bad, os.path.join(work, "bad.html"))
        suite.ok("%s %s is rejected" % (tag, label), finished.returncode != 0,
                 "exited 0 with %s" % payload)

    broken = write(os.path.join(work, "plain.html"), "<html>no block</html>")
    suite.ok("%s a page with no checklist block is rejected" % tag,
             run(script, "items", broken).returncode != 0)

    check_over_http(suite, tag, script, body, full.stdout)
    check_plan_first(suite, tag, script, work, full.stdout, stacked.stdout)
    check_ledger_first(suite, tag, script, work, full.stdout, stacked.stdout)
    check_tick(suite, tag, script, work, full.stdout)
    check_publish(suite, tag, script, work, seed)


GATED = ("implement=in-flight:editing", "commit=done", "describe=done", "open=done")


def check_plan_first(suite, tag, script, work, seed_text, stack_text):
    path = write(os.path.join(work, "gate.json"), seed_text)
    load = lambda: {e["id"]: e for e in json.loads(open(path).read())["items"]}

    for tick in GATED:
        ident = tick.split("=", 1)[0]
        refused = run(script, "tick", path, tick)
        suite.ok("%s tick refuses %s while plan is pending" % (tag, ident),
                 refused.returncode != 0, refused.stdout)
        suite.ok("%s refusing %s names the plan item" % (tag, ident),
                 "plan" in refused.stderr, refused.stderr)
        suite.ok("%s refusing %s writes nothing" % (tag, ident),
                 load()[ident]["state"] == "pending", load()[ident]["state"])

    suite.exits("%s an item the plan does not gate still ticks" % tag, 0,
                run(script, "tick", path, "pipeline=in-flight:CI"))

    suite.exits("%s plan=done and a gated item go in one command" % tag, 0,
                run(script, "tick", path, "plan=done",
                    "implement=in-flight:the approved plan"))

    waived = write(os.path.join(work, "waived.json"), seed_text)
    suite.ok("%s plan=skipped with no reason is refused" % tag,
             run(script, "tick", waived, "plan=skipped").returncode != 0)
    suite.exits("%s a recorded waiver clears the gate" % tag, 0,
                run(script, "tick", waived,
                    "plan=skipped:the user approved the approach in advance",
                    "implement=in-flight:editing"))

    stacked = write(os.path.join(work, "gate-stack.json"), stack_text)
    member = run(script, "tick", stacked, "implement@2=in-flight:editing")
    suite.ok("%s a stack member is gated by the shared plan item" % tag,
             member.returncode != 0, member.stdout)
    suite.exits("%s the shared plan clears every stage" % tag, 0,
                run(script, "tick", stacked, "plan=done",
                    "implement@2=in-flight:editing"))


def check_ledger_first(suite, tag, script, work, seed_text, stack_text):
    path = write(os.path.join(work, "ledger-gate.json"), seed_text)
    load = lambda: {e["id"]: e for e in json.loads(open(path).read())["items"]}
    run(script, "tick", path, "plan=done")

    for tick in ("merge=in-flight:the pipeline", "merge=done"):
        state = tick.split("=", 1)[1].split(":", 1)[0]
        refused = run(script, "tick", path, tick)
        suite.ok("%s tick refuses merge=%s while the ledger is pending"
                 % (tag, state), refused.returncode != 0, refused.stdout)
        suite.ok("%s refusing merge=%s names the ledger item" % (tag, state),
                 "ledger" in refused.stderr, refused.stderr)
        suite.ok("%s refusing merge=%s writes nothing" % (tag, state),
                 load()["merge"]["state"] == "pending", load()["merge"]["state"])

    suite.exits("%s an item the ledger does not gate still ticks" % tag, 0,
                run(script, "tick", path, "pipeline=in-flight:CI"))

    suite.exits("%s ledger=done and the merge go in one command" % tag, 0,
                run(script, "tick", path, "ledger=done", "merge=in-flight:the queue"))

    empty = write(os.path.join(work, "ledger-empty.json"), seed_text)
    run(script, "tick", empty, "plan=done")
    suite.ok("%s ledger=skipped with no reason is refused" % tag,
             run(script, "tick", empty, "ledger=skipped").returncode != 0)
    suite.exits("%s an empty ledger recorded as skipped clears the gate" % tag, 0,
                run(script, "tick", empty, "ledger=skipped:no unreviewed calls",
                    "merge=done"))

    held = run(script, "template", "--branch", "b")
    ready = write(os.path.join(work, "ledger-ready.json"), held.stdout)
    run(script, "tick", ready, "plan=done")
    refused = run(script, "tick", ready, "ready=done")
    suite.ok("%s the hand-over is gated too, not only the merge" % tag,
             refused.returncode != 0, refused.stdout)

    stacked = write(os.path.join(work, "ledger-stack.json"), stack_text)
    run(script, "tick", stacked, "plan=done")
    member = run(script, "tick", stacked, "merge@2=done")
    suite.ok("%s a stack member's merge is gated by its own ledger" % tag,
             member.returncode != 0 and "ledger@2" in member.stderr, member.stderr)
    suite.exits("%s one member's record clears only that member" % tag, 0,
                run(script, "tick", stacked, "ledger@2=skipped:nothing recorded",
                    "merge@2=done"))
    sibling = run(script, "tick", stacked, "merge@1=done")
    suite.ok("%s and never the sibling's" % tag,
             sibling.returncode != 0 and "ledger@1" in sibling.stderr,
             sibling.stderr)


def check_tick(suite, tag, script, work, seed_text):
    path = write(os.path.join(work, "tick.json"), seed_text)
    load = lambda: {e["id"]: e for e in json.loads(open(path).read())["items"]}
    run(script, "tick", path, "plan=done")

    suite.exits("%s tick" % tag, 0,
                run(script, "tick", path, "commit=done",
                    "review=in-flight:workflow wf_abc"))
    items = load()
    suite.ok("%s tick sets the state" % tag, items["commit"]["state"] == "done",
             items["commit"]["state"])
    suite.ok("%s tick sets what an in-flight item waits on" % tag,
             items["review"]["waiting_on"] == "workflow wf_abc",
             items["review"]["waiting_on"])

    suite.exits("%s tick to done after in-flight" % tag, 0,
                run(script, "tick", path, "review=done"))
    suite.ok("%s leaving in-flight clears waiting_on" % tag,
             load()["review"]["waiting_on"] == "", load()["review"]["waiting_on"])

    suite.exits("%s tick to skipped with a reason" % tag, 0,
                run(script, "tick", path, "ledger=skipped:no unreviewed calls"))
    suite.ok("%s tick sets the note" % tag,
             load()["ledger"]["note"] == "no unreviewed calls",
             load()["ledger"]["note"])

    suite.exits("%s tick un-skips an item" % tag, 0,
                run(script, "tick", path, "verify=pending"))
    suite.ok("%s leaving skipped clears the stale reason" % tag,
             load()["verify"]["note"] == "", load()["verify"]["note"])

    run(script, "tick", path, "verify=skipped:nothing deploys")
    suite.exits("%s tick skipped to in-flight" % tag, 0,
                run(script, "tick", path, "verify=in-flight:the deploy watcher"))
    items = load()
    suite.ok("%s skipped to in-flight clears the stale reason" % tag,
             items["verify"]["note"] == "", items["verify"]["note"])
    suite.ok("%s skipped to in-flight sets the blocker" % tag,
             items["verify"]["waiting_on"] == "the deploy watcher",
             items["verify"]["waiting_on"])

    run(script, "tick", path, "open=done:PR 31")
    suite.exits("%s re-tick the same state" % tag, 0,
                run(script, "tick", path, "open=done"))
    suite.ok("%s a re-tick of the same state keeps the note" % tag,
             load()["open"]["note"] == "PR 31", load()["open"]["note"])
    suite.exits("%s tick replaces a note" % tag, 0,
                run(script, "tick", path, "open=pending:reopened"))
    suite.ok("%s new text replaces the note on a state change" % tag,
             load()["open"]["note"] == "reopened", load()["open"]["note"])

    typo = run(script, "tick", path, "comit=done")
    suite.ok("%s tick rejects an unknown id" % tag, typo.returncode != 0, typo.stdout)
    suite.ok("%s tick names the ids it does have" % tag, "commit" in typo.stderr,
             typo.stderr)

    suite.ok("%s tick rejects a state outside the four" % tag,
             run(script, "tick", path, "commit=doneish").returncode != 0)
    suite.ok("%s tick rejects an argument with no =" % tag,
             run(script, "tick", path, "commit").returncode != 0)

    suite.exits("%s tick --run" % tag, 0,
                run(script, "tick", path, "commit=done",
                    "--run", "change_request=https://example.invalid/pull/9"))
    suite.ok("%s tick --run sets the field" % tag,
             json.loads(open(path).read())["run"]["change_request"]
             == "https://example.invalid/pull/9")
    suite.ok("%s tick --run rejects an unknown field" % tag,
             run(script, "tick", path, "commit=done",
                 "--run", "nonsense=x").returncode != 0)
    suite.ok("%s tick --run rejects an assignment with no =" % tag,
             run(script, "tick", path, "commit=done",
                 "--run", "change_request").returncode != 0)

    plan_url = "https://example.invalid/plan99"
    suite.exits("%s tick --run plan_page" % tag, 0,
                run(script, "tick", path, "commit=done",
                    "--run", "plan_page=%s" % plan_url))
    suite.ok("%s tick --run sets plan_page" % tag,
             json.loads(open(path).read())["run"]["plan_page"] == plan_url)
    planned = os.path.join(work, "tick-plan-page.html")
    suite.exits("%s render with plan_page" % tag, 0,
                run(script, "render", path, planned, "--stamp", "S"))
    carried = run(script, "items", planned)
    suite.exits("%s items with plan_page" % tag, 0, carried)
    suite.ok("%s plan_page survives the page" % tag,
             json.loads(carried.stdout)["run"]["plan_page"] == plan_url,
             carried.stdout[:200])

    log = os.path.join(work, "tick-publisher-args.txt")
    fake = write(os.path.join(work, "tick-publisher.sh"),
                 '#!/bin/sh\nfor a in "$@"; do echo "$a" >>"%s"; done\n'
                 'echo https://store.invalid/tick99\n' % log)
    os.chmod(fake, 0o755)
    finished = run(script, "tick", path, "commit=done", "--publish",
                   "--out", os.path.join(work, "tick.html"), "--stamp", "S",
                   env=dict(os.environ, PUBLISH_ARTIFACT=fake))
    suite.exits("%s tick --publish" % tag, 0, finished)
    suite.ok("%s tick --publish prints the url" % tag,
             "url=https://store.invalid/tick99" in finished.stdout, finished.stdout)
    recorded = json.loads(open(path).read())["run"]
    suite.ok("%s publish records the url into the items file" % tag,
             recorded["url"] == "https://store.invalid/tick99", recorded)
    suite.ok("%s publish records the hash into the items file" % tag,
             recorded["hash"] == "tick99", recorded)

    os.remove(log)
    suite.exits("%s a later tick --publish reuses the recorded hash" % tag, 0,
                run(script, "tick", path, "describe=done", "--publish",
                    "--out", os.path.join(work, "tick.html"), "--stamp", "S",
                    env=dict(os.environ, PUBLISH_ARTIFACT=fake)))
    sent = open(log, encoding="utf-8").read().splitlines()
    suite.ok("%s the recorded hash becomes --update without being passed" % tag,
             "--update" in sent and "tick99" in sent, "got %s" % sent)


def check_over_http(suite, tag, script, page, want):
    wrapper = ('<!doctype html><html><head><title>wrapped</title></head><body>'
               '<div id="banner">chrome</div>'
               '<iframe id="frame" src="%s/raw" title="wrapped"></iframe>'
               '</body></html>')

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/raw" or self.path == "/direct":
                payload = page
            elif self.path == "/wrapped":
                payload = wrapper % base
            else:
                self.send_error(404)
                return
            encoded = payload.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *_args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    base = "http://127.0.0.1:%d" % server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        direct = run(script, "items", base + "/direct")
        suite.exits("%s items over http" % tag, 0, direct)
        suite.ok("%s a page served directly round-trips" % tag, direct.stdout == want,
                 direct.stdout)

        wrapped = run(script, "items", base + "/wrapped")
        suite.exits("%s items follows the store's wrapper" % tag, 0, wrapped)
        suite.ok("%s the wrapped page round-trips" % tag, wrapped.stdout == want,
                 wrapped.stdout)

        suite.ok("%s a url that 404s is rejected" % tag,
                 run(script, "items", base + "/missing").returncode != 0)
    finally:
        server.shutdown()
        server.server_close()


def check_publish(suite, tag, script, work, seed):
    absent = write(os.path.join(work, "absent-publisher.sh"),
                   "#!/bin/sh\necho 'no store here' >&2\nexit 3\n")
    os.chmod(absent, 0o755)
    environment = dict(os.environ, PUBLISH_ARTIFACT=absent)
    suite.exits("%s publish with no store passes exit 3 through" % tag, 3,
                run(script, "publish", seed, "--out", os.path.join(work, "p.html"),
                    "--stamp", "S", env=environment))

    log = os.path.join(work, "publisher-args.txt")
    fake = write(os.path.join(work, "publisher.sh"),
                 '#!/bin/sh\necho "--CALL--" >>"%s"\nfor a in "$@"; do echo "$a" >>"%s"; done\n'
                 'echo https://store.invalid/abc123\n' % (log, log))
    os.chmod(fake, 0o755)
    environment = dict(os.environ, PUBLISH_ARTIFACT=fake)

    def calls():
        if not os.path.exists(log):
            return []
        out = []
        for token in open(log, encoding="utf-8").read().splitlines():
            if token == "--CALL--":
                out.append([])
            elif out:
                out[-1].append(token)
        return out

    finished = run(script, "publish", seed, "--out", os.path.join(work, "p.html"),
                   "--stamp", "S", env=environment)
    suite.exits("%s publish with a store" % tag, 0, finished)
    suite.ok("%s publish prints the url" % tag,
             "url=https://store.invalid/abc123" in finished.stdout, finished.stdout)
    suite.ok("%s publish prints the hash" % tag,
             "hash=abc123" in finished.stdout, finished.stdout)
    sent = calls()
    suite.ok("%s publish sends --purpose tasks on every call" % tag,
             all("--purpose" in c and c[c.index("--purpose") + 1] == "tasks"
                 for c in sent) and sent, "got %s" % sent)
    suite.ok("%s the first call of a first publish sends no --update" % tag,
             sent and "--update" not in sent[0], "got %s" % sent)
    suite.ok("%s a first publish then updates to embed its identity" % tag,
             len(sent) == 2 and "--update" in sent[1]
             and sent[1][sent[1].index("--update") + 1] == "abc123", "got %s" % sent)
    suite.ok("%s publish expires the page with its real value" % tag,
             all("--expires" in c and c[c.index("--expires") + 1] == "30d"
                 for c in sent), "got %s" % sent)

    page = os.path.join(work, "p.html")
    embedded = run(script, "items", page)
    suite.exits("%s the published page can be read back" % tag, 0, embedded)
    identity = json.loads(embedded.stdout)["run"]
    suite.ok("%s the published page embeds its own url" % tag,
             identity["url"] == "https://store.invalid/abc123", identity)
    suite.ok("%s the published page embeds its own hash" % tag,
             identity["hash"] == "abc123", identity)

    os.remove(log)
    recovered = write(os.path.join(work, "recovered.json"), embedded.stdout)
    suite.exits("%s publish from a document recovered off the page" % tag, 0,
                run(script, "tick", recovered, "plan=done", "commit=done", "--publish",
                    "--out", os.path.join(work, "r.html"), "--stamp", "S",
                    env=environment))
    sent = calls()
    suite.ok("%s a recovered document still updates the same link" % tag,
             len(sent) == 1 and "--update" in sent[0]
             and sent[0][sent[0].index("--update") + 1] == "abc123", "got %s" % sent)

    os.remove(log)
    recorded = json.loads(open(seed, encoding="utf-8").read())
    recorded["run"]["hash"] = "abc123"
    recorded["run"]["url"] = "https://store.invalid/abc123"
    again = write(os.path.join(work, "recorded.json"), json.dumps(recorded))
    finished = run(script, "publish", again, "--out", os.path.join(work, "p.html"),
                   "--stamp", "S", env=environment)
    suite.exits("%s publish with a recorded hash" % tag, 0, finished)
    sent = calls()
    suite.ok("%s a recorded identity publishes once, as an update" % tag,
             len(sent) == 1 and "--update" in sent[0]
             and sent[0][sent[0].index("--update") + 1] == "abc123", "got %s" % sent)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "rules":
        print(RULES.strip())
        return 0

    global SANDBOX_HOME
    suite = Suite()
    for profile in PROFILES:
        work = tempfile.mkdtemp()
        SANDBOX_HOME = os.path.join(work, "home")
        os.makedirs(os.path.join(SANDBOX_HOME, ".claude", "notify-state", "sessions"),
                    exist_ok=True)
        try:
            check_profile(suite, profile, work)
        finally:
            SANDBOX_HOME = None
            shutil.rmtree(work, ignore_errors=True)

    if suite.failures:
        print("run-checklist: %d of %d checks failed" % (suite.failures, suite.checked))
        return 1
    print("run-checklist: %d checks passed" % suite.checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
