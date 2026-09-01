#!/usr/bin/env python3
"""Inspect, relink, and harvest Claude Code Workflow runs on disk.

Layout this depends on (Claude Code >= 2.1):
  <projects>/<slug>/<session>/workflows/wf_<id>.json          manifest
  <projects>/<slug>/<session>/workflows/scripts/<name>-wf_<id>.js
  <projects>/<slug>/<session>/subagents/workflows/wf_<id>/journal.jsonl
  <projects>/<slug>/<session>/subagents/workflows/wf_<id>/agent-<id>.jsonl

The journal is the resume cache. Workflow resolves it under the CURRENT
session id, which is why `link` exists.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from glob import glob

PROJECTS = os.path.expanduser("~/.claude/projects")
DEGENERATE = re.compile(r'^(\[\s*\]|\{\s*\}|\{\s*"[^"]+"\s*:\s*\[\s*\]\s*\})$')
LIMIT_HINT = re.compile(r"spend limit|usage limit|rate limit|session limit|quota|out of credit", re.I)


def die(msg, code=1):
    print(f"workflow-runs: {msg}", file=sys.stderr)
    sys.exit(code)


def manifests():
    return glob(os.path.join(PROJECTS, "*", "*", "workflows", "wf_*.json"))


def load_manifest(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return None


def journal_dir(run_id, session=None):
    if session:
        hits = glob(os.path.join(PROJECTS, "*", session, "subagents", "workflows", run_id))
    else:
        hits = glob(os.path.join(PROJECTS, "*", "*", "subagents", "workflows", run_id))
    real = [h for h in hits if not os.path.islink(h)]
    return (real or hits or [None])[0]


def read_journal(path):
    """started/result/failed maps keyed by cache key, plus first-seen key order.

    `failed` is the event the harness writes when an agent dies on a terminal
    error (a spend/usage limit is the common one). It carries no reason — that
    lives in the last line of the agent's own transcript, see failure_reason().
    """
    started, results, failed, order = {}, {}, {}, []
    if not path or not os.path.exists(path):
        return started, results, failed, order
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            key, kind = ev.get("key"), ev.get("type")
            if kind == "started":
                started.setdefault(key, []).append(ev)
                order.append(key)
            elif kind == "result":
                results[key] = ev
            elif kind == "failed":
                failed[key] = ev
    return started, results, failed, order


def failure_reason(jdir, agent_id):
    path = os.path.join(jdir or "", f"agent-{agent_id}.jsonl")
    if not agent_id or not os.path.exists(path):
        return None
    try:
        with open(path) as fh:
            lines = fh.read().splitlines()
    except Exception:
        return None
    for line in reversed(lines[-6:]):
        try:
            msg = (json.loads(line).get("message") or {})
        except Exception:
            continue
        content = msg.get("content")
        if isinstance(content, list):
            text = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
        else:
            text = content if isinstance(content, str) else ""
        text = text.strip()
        if text and msg.get("model") == "<synthetic>":
            return text
    return None


def summarize(path):
    m = load_manifest(path)
    if not m:
        return None
    session = os.path.basename(os.path.dirname(os.path.dirname(path)))
    slug = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
    run_id = m.get("runId") or os.path.basename(path)[:-5]
    jdir = journal_dir(run_id)
    jpath = os.path.join(jdir, "journal.jsonl") if jdir else None
    started, results, failed, order = read_journal(jpath)
    dead = set(started) - set(results) - set(failed)
    clean_prefix, seen_keys = 0, set()
    for key in order:
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if key not in results:
            break
        clean_prefix += 1
    reasons = sorted({
        r for r in (failure_reason(jdir, ev.get("agentId")) for ev in failed.values()) if r
    })
    empty = sum(
        1
        for ev in results.values()
        if ev.get("result") is None
        or DEGENERATE.match(json.dumps(ev.get("result"), separators=(",", ":")) or "")
    )
    result = m.get("result")
    result_json = json.dumps(result, separators=(",", ":")) if result is not None else "null"

    if any(LIMIT_HINT.search(r) for r in reasons):
        health = "LIMIT-HIT"
    elif m.get("status") != "completed" or result is None:
        health = "INTERRUPTED"
    elif failed or dead:
        health = "HOLES"
    elif DEGENERATE.match(result_json):
        health = "SUSPECT"
    else:
        health = "OK"

    return {
        "runId": run_id,
        "workflow": m.get("workflowName"),
        "status": m.get("status"),
        "health": health,
        "timestamp": m.get("timestamp"),
        "durationMs": m.get("durationMs"),
        "agentCount": m.get("agentCount"),
        "launched": len(started),
        "finished": len(results),
        "failed": len(failed),
        "dead": len(dead),
        "cleanPrefix": clean_prefix,
        "failureReasons": reasons,
        "emptyResults": empty,
        "error": m.get("error"),
        "logs": m.get("logs") or [],
        "session": session,
        "slug": slug,
        "manifest": path,
        "scriptPath": m.get("scriptPath"),
        "journal": jpath,
        "journalExists": bool(jpath and os.path.exists(jpath)),
        "repoRoot": (m.get("args") or {}).get("repoRoot") if isinstance(m.get("args"), dict) else None,
        "totalTokens": m.get("totalTokens"),
    }


def age(ts):
    if not ts:
        return "?"
    try:
        then = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if secs >= size:
            return f"{int(secs // size)}{unit}"
    return f"{int(secs)}s"


def cmd_list(a):
    rows = [r for r in (summarize(p) for p in manifests()) if r]
    if not a.all:
        rows = [r for r in rows if r["health"] != "OK"]
    rows.sort(key=lambda r: r["timestamp"] or "", reverse=True)
    rows = rows[: a.limit]
    if a.json:
        print(json.dumps(rows, indent=2))
        return
    if not rows:
        print("no resumable runs found (all recent runs completed cleanly; --all to see them)")
        return
    print(f"{'RUN ID':<18} {'WORKFLOW':<20} {'HEALTH':<12} {'AGE':>5} {'DONE/LAUNCH':>12} {'FAIL':>5} {'DEAD':>5} {'REPLAY':>7}  {'CWD (repoRoot)'}")
    for r in rows:
        print(
            f"{r['runId']:<18} {str(r['workflow'])[:20]:<20} {r['health']:<12} "
            f"{age(r['timestamp']):>5} {str(r['finished']) + '/' + str(r['launched']):>12} "
            f"{r['failed']:>5} {r['dead']:>5} {r['cleanPrefix']:>7}  {r['repoRoot'] or ''}"
        )
    print()
    print("REPLAY = agents that replay from cache before the key chain breaks (cleanPrefix);")
    print("compare it with DONE to choose resume vs harvest.")
    print("show <runId> for detail; link <runId> before resuming; harvest <runId> to salvage results")


def find_run(run_id):
    hits = glob(os.path.join(PROJECTS, "*", "*", "workflows", f"{run_id}.json"))
    if not hits:
        die(f"no manifest for run '{run_id}'")
    hits.sort(key=os.path.getmtime, reverse=True)
    return hits[0]


def cmd_show(a):
    path = find_run(a.run_id)
    m = load_manifest(path)
    r = summarize(path)
    for k in (
        "runId", "workflow", "status", "health", "timestamp", "durationMs", "agentCount",
        "launched", "finished", "failed", "dead", "cleanPrefix", "emptyResults", "totalTokens", "session", "slug",
        "repoRoot", "journal", "journalExists", "scriptPath", "manifest",
    ):
        print(f"{k:<14} {r[k]}")
    if r["error"]:
        print(f"{'error':<14} {str(r['error']).splitlines()[0]}")
    for reason in r["failureReasons"]:
        print(f"{'why failed':<14} {reason}")
    for line in r["logs"]:
        print(f"{'log':<14} {line}")
    phases = m.get("phases") or []
    if phases:
        print(f"{'phases':<14} " + ", ".join(str(p.get("title")) for p in phases))
    prog = [p for p in (m.get("workflowProgress") or []) if p.get("type") == "workflow_agent"]
    if prog:
        state = {}
        for p in prog:
            state[p.get("label")] = p.get("state")
        stuck = [lbl for lbl, s in state.items() if s != "done"]
        print(f"{'agents done':<14} {sum(1 for s in state.values() if s == 'done')}/{len(state)}")
        if stuck:
            print(f"{'unfinished':<14} " + ", ".join(stuck[:20]) + (" …" if len(stuck) > 20 else ""))
    if a.args:
        print("\n--- args ---")
        print(json.dumps(m.get("args"), indent=2))
    if a.result:
        print("\n--- result ---")
        print(json.dumps(m.get("result"), indent=2))


def cmd_args(a):
    m = load_manifest(find_run(a.run_id))
    args = m.get("args")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            pass
    print(json.dumps(args, indent=2 if a.pretty else None))


def cmd_script(a):
    m = load_manifest(find_run(a.run_id))
    if a.path:
        print(m.get("scriptPath") or "")
    else:
        print(m.get("script") or "")


def current_session(explicit=None):
    sid = explicit or os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not sid:
        die("cannot determine the current session id — pass --session <uuid> "
            "(it is the UUID directory in this session's scratchpad path)")
    return sid


def session_dir(sid):
    hits = glob(os.path.join(PROJECTS, "*", sid))
    hits = [h for h in hits if os.path.isdir(h)]
    if not hits:
        die(f"no session directory for '{sid}' under {PROJECTS}")
    return hits[0]


def cmd_link(a):
    sid = current_session(a.session)
    sdir = session_dir(sid)
    src = journal_dir(a.run_id)
    if not src or not os.path.exists(os.path.join(src, "journal.jsonl")):
        die(f"no journal.jsonl found for run '{a.run_id}' — nothing to resume from")
    dst = os.path.join(sdir, "subagents", "workflows", a.run_id)
    if os.path.realpath(src) == os.path.realpath(dst):
        print(f"already visible to session {sid}: {dst}")
        return
    if os.path.islink(dst):
        if os.path.realpath(dst) == os.path.realpath(src):
            print(f"already linked: {dst} -> {src}")
            return
        os.unlink(dst)
    elif os.path.exists(dst):
        die(f"refusing to replace real directory {dst}")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.symlink(src, dst)
    print(f"linked {dst} -> {src}")
    print(f"resumeFromRunId '{a.run_id}' will now find its cache in session {sid}")


def cmd_unlink(a):
    sid = current_session(a.session)
    dst = os.path.join(session_dir(sid), "subagents", "workflows", a.run_id)
    if os.path.islink(dst):
        os.unlink(dst)
        print(f"removed link {dst}")
    else:
        print(f"no link at {dst} (nothing removed)")


def cmd_merge(a):
    """Union several runs' journals into a fresh synthetic run the harness can resume from.

    Cache keys are content-addressed and chain-deterministic, so the union of two
    partial journals for the same script+args is a strictly better cache than
    either alone. A resumed run writes only its LIVE agents to its own journal —
    replayed ones are never re-recorded — so without this, chaining resume off
    the newest run throws away everything the first run cached.
    """
    sid = current_session(a.session)
    target = a.into or (a.run_ids[0] + "-m")
    if not re.match(r"^wf_[a-z0-9-]{6,}$", target):
        die(f"'{target}' is not a usable run id (needs to match ^wf_[a-z0-9-]{{6,}}$)")
    events, seen = [], set()
    for run_id in a.run_ids:
        jdir = journal_dir(run_id)
        jpath = os.path.join(jdir, "journal.jsonl") if jdir else None
        if not jpath or not os.path.exists(jpath):
            die(f"no journal for run '{run_id}'")
        kept = 0
        with open(jpath) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                ident = (ev.get("type"), ev.get("key"), ev.get("agentId"))
                if ident in seen:
                    continue
                seen.add(ident)
                events.append(line)
                kept += 1
        print(f"{run_id}: +{kept} events")
    dst = os.path.join(session_dir(sid), "subagents", "workflows", target)
    if os.path.islink(dst):
        os.unlink(dst)
    elif os.path.exists(dst) and not a.force:
        die(f"{dst} already exists — pass --force to overwrite")
    os.makedirs(dst, exist_ok=True)
    with open(os.path.join(dst, "journal.jsonl"), "w") as fh:
        fh.write("\n".join(events) + "\n")
    results = len({json.loads(e).get("key") for e in events if json.loads(e).get("type") == "result"})
    print(f"merged {len(events)} events ({results} cached agent results) into {dst}")
    print(f"resume with resumeFromRunId: '{target}'")


def cmd_harvest(a):
    path = find_run(a.run_id)
    m = load_manifest(path)
    r = summarize(path)
    started, results, failed, order = read_journal(r["journal"])
    jdir = os.path.dirname(r["journal"] or "")
    labels = {
        p["agentId"]: p.get("label")
        for p in (m.get("workflowProgress") or [])
        if p.get("type") == "workflow_agent" and p.get("agentId")
    }
    seen, out = set(), []
    for key in order:
        if key in seen:
            continue
        seen.add(key)
        ev = results.get(key)
        bad = failed.get(key)
        agent_id = (ev or bad or (started.get(key) or [{}])[0]).get("agentId")
        out.append({
            "key": key,
            "agentId": agent_id,
            "label": labels.get(agent_id),
            "state": "done" if ev else ("failed" if bad else "never-returned"),
            "result": ev.get("result") if ev else None,
            "reason": failure_reason(jdir, agent_id) if bad else None,
        })
    payload = {
        "runId": r["runId"],
        "workflow": r["workflow"],
        "health": r["health"],
        "args": m.get("args"),
        "finished": r["finished"],
        "launched": r["launched"],
        "failed": r["failed"],
        "dead": r["dead"],
        "failureReasons": r["failureReasons"],
        "labelled": sum(1 for a in out if a["label"]),
        "agents": out,
    }
    text = json.dumps(payload, indent=2)
    if a.out:
        with open(a.out, "w") as fh:
            fh.write(text)
        print(f"wrote {a.out} ({r['finished']}/{r['launched']} agent results)")
    else:
        print(text)


def main():
    p = argparse.ArgumentParser(prog="workflow-runs", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list", help="list workflow runs worth resuming")
    s.add_argument("--all", action="store_true", help="include healthy completed runs")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("show", help="detail for one run")
    s.add_argument("run_id")
    s.add_argument("--args", action="store_true")
    s.add_argument("--result", action="store_true")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("args", help="print the run's args JSON")
    s.add_argument("run_id")
    s.add_argument("--pretty", action="store_true")
    s.set_defaults(fn=cmd_args)

    s = sub.add_parser("script", help="print the run's snapshot script (diff only — never resend it)")
    s.add_argument("run_id")
    s.add_argument("--path", action="store_true")
    s.set_defaults(fn=cmd_script)

    s = sub.add_parser("link", help="make a run's cache visible to the current session")
    s.add_argument("run_id")
    s.add_argument("--session")
    s.set_defaults(fn=cmd_link)

    s = sub.add_parser("unlink", help="remove a link created by `link`")
    s.add_argument("run_id")
    s.add_argument("--session")
    s.set_defaults(fn=cmd_unlink)

    s = sub.add_parser("merge", help="union several runs' journals into one resumable cache")
    s.add_argument("run_ids", nargs="+")
    s.add_argument("--into", help="run id to write (default: <first>-m)")
    s.add_argument("--session")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_merge)

    s = sub.add_parser("harvest", help="dump every finished agent result from the journal")
    s.add_argument("run_id")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_harvest)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
