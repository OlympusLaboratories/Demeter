#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys

PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")


def project_dir(path):
    slug = re.sub(r"[^a-zA-Z0-9]", "-", os.path.realpath(path))
    if len(slug) > 200:
        return None
    return os.path.join(PROJECTS, slug)


def main_checkout_of(cwd):
    if not os.path.isdir(cwd):
        return None

    def git(*args):
        return subprocess.run(
            ("git", "-C", cwd) + args,
            capture_output=True, text=True, timeout=10,
        )

    common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    private = git("rev-parse", "--path-format=absolute", "--git-dir")
    if common.returncode or private.returncode:
        return None
    common_dir = os.path.realpath(common.stdout.strip())
    if common_dir == os.path.realpath(private.stdout.strip()):
        return None
    root = os.path.dirname(common_dir)
    return root if os.path.isdir(root) else None


def main_checkout_by_layout(cwd):
    marker = os.sep + ".claude" + os.sep + "worktrees" + os.sep
    idx = cwd.find(marker)
    if idx == -1:
        return None
    root = cwd[:idx]
    return root if os.path.isdir(os.path.join(root, ".git")) else None


def resolve_main_checkout(cwd):
    return main_checkout_of(cwd) or main_checkout_by_layout(cwd)


def find_real_transcript(session_id):
    try:
        entries = os.listdir(PROJECTS)
    except OSError:
        return None
    for entry in entries:
        p = os.path.join(PROJECTS, entry, session_id + ".jsonl")
        if os.path.isfile(p) and not os.path.islink(p):
            return p
    return None


CONTENT_TYPES = {"user", "assistant", "attachment", "system", "progress"}
BACKUP_DIR = os.path.join(os.path.expanduser("~"), ".claude", "backups", "session-stubs")


def read_records(path):
    out = []
    try:
        with open(path, "r", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append((line, json.loads(line)))
                except Exception:
                    return None
    except OSError:
        return None
    return out


def stub_records(path):
    recs = read_records(path)
    if not recs:
        return None
    for _, rec in recs:
        if rec.get("type") in CONTENT_TYPES or "message" in rec:
            return None
    return recs


def absorb_stub(stub_path, target_path):
    recs = stub_records(stub_path)
    if recs is None:
        return False
    try:
        existing = open(target_path, "r", errors="replace").read()
    except OSError:
        return False
    missing = [line for line, _ in recs if line not in existing]
    if missing:
        with open(target_path, "a") as fh:
            fh.write("\n".join(missing) + "\n")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.replace(stub_path, os.path.join(BACKUP_DIR, os.path.basename(stub_path)))
    return True


def link(cwd, session_id, hint=None):
    root = resolve_main_checkout(os.path.realpath(cwd))
    if root is None:
        return None
    dest_dir = project_dir(root)
    own_dir = project_dir(cwd)
    if dest_dir is None or own_dir is None or dest_dir == own_dir:
        return None

    target = os.path.join(own_dir, session_id + ".jsonl")
    if not os.path.exists(target):
        found = None
        if hint and os.path.isfile(hint) and not os.path.islink(hint):
            found = hint
        else:
            found = find_real_transcript(session_id)
        if found and os.path.dirname(os.path.realpath(found)) != dest_dir:
            target = os.path.realpath(found)

    link_path = os.path.join(dest_dir, session_id + ".jsonl")
    if os.path.lexists(link_path):
        if os.path.islink(link_path):
            if os.readlink(link_path) == target:
                return None
            os.unlink(link_path)
        else:
            if os.path.realpath(link_path) == os.path.realpath(target):
                return None
            if not os.path.isfile(target):
                return None
            if not absorb_stub(link_path, target):
                return None
    os.makedirs(dest_dir, exist_ok=True)
    os.symlink(target, link_path)
    return link_path


def last_cwd_of(path):
    cwd = None
    try:
        with open(path, "r", errors="replace") as fh:
            for line in fh:
                if '"cwd"' not in line:
                    continue
                try:
                    cwd = json.loads(line).get("cwd") or cwd
                except Exception:
                    continue
    except OSError:
        pass
    return cwd


def backfill():
    linked, already, unmappable = [], 0, 0
    for entry in sorted(os.listdir(PROJECTS)):
        d = os.path.join(PROJECTS, entry)
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            if not fname.endswith(".jsonl"):
                continue
            src = os.path.join(d, fname)
            if os.path.islink(src) or not os.path.isfile(src):
                continue
            cwd = last_cwd_of(src)
            if not cwd:
                continue
            root = resolve_main_checkout(os.path.realpath(cwd))
            if root is None:
                continue
            dest = project_dir(root)
            if dest is None or dest == os.path.realpath(d):
                continue
            made = link(cwd, fname[:-6], src)
            if made:
                linked.append(made)
            elif os.path.islink(os.path.join(dest, fname)):
                already += 1
            else:
                unmappable += 1
    for p in linked:
        print("linked " + os.path.basename(p) + " -> " + os.path.basename(os.path.dirname(p)))
    print("%d newly linked, %d already linked, %d unmappable" % (len(linked), already, unmappable))


def main():
    if "--backfill" in sys.argv:
        backfill()
        return
    payload = json.load(sys.stdin)
    cwd = payload.get("new_cwd") or payload.get("cwd") or os.getcwd()
    link(cwd, payload["session_id"], payload.get("transcript_path"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
