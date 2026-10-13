#!/usr/bin/env python3
import ctypes
import fcntl
import json
import os
import re
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
PROJECTS = os.path.join(HOME, ".claude", "projects")
LOCK_PATH = os.path.join(PROJECTS, ".worktree-unify.lock")
DIR_BACKUPS = os.path.join(HOME, ".claude", "backups", "worktree-project-dirs")
STUB_BACKUPS = os.path.join(HOME, ".claude", "backups", "session-stubs")
CONTENT_TYPES = {"user", "assistant", "attachment", "system", "progress"}
SAMPLE_BYTES = 65536
WORKTREE_MARKER = os.sep + ".claude" + os.sep + "worktrees" + os.sep


def project_dir(path):
    slug = re.sub(r"[^a-zA-Z0-9]", "-", os.path.realpath(path))
    if len(slug) > 200:
        return None
    return os.path.join(PROJECTS, slug)


def git(cwd, *args):
    try:
        out = subprocess.run(
            ("git", "-C", cwd) + args,
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def worktree_of(path):
    if not os.path.isdir(path):
        return None
    top = git(path, "rev-parse", "--path-format=absolute", "--show-toplevel")
    common = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    private = git(path, "rev-parse", "--path-format=absolute", "--git-dir")
    if not (top and common and private):
        return None
    common = os.path.realpath(common)
    if common == os.path.realpath(private):
        return None
    main = os.path.dirname(common)
    return (top, main) if os.path.isdir(main) else None


def checkout_root(path):
    pair = worktree_of(path)
    if pair:
        return pair[1]
    return git(path, "rev-parse", "--path-format=absolute", "--show-toplevel") if os.path.isdir(path) else None


def main_checkout(path):
    pair = worktree_of(path)
    if pair:
        return pair[1]
    idx = path.find(WORKTREE_MARKER)
    if idx == -1:
        return None
    root = path[:idx]
    return root if os.path.isdir(os.path.join(root, ".git")) else None


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


def is_stub(path):
    recs = read_records(path)
    if not recs:
        return False
    return not any(rec.get("type") in CONTENT_TYPES or "message" in rec for _, rec in recs)


def absorb_stub(stub_path, target_path):
    recs = read_records(stub_path) or []
    try:
        with open(target_path, "r", errors="replace") as fh:
            existing = fh.read()
    except OSError:
        return False
    missing = [line for line, _ in recs if line not in existing]
    if missing:
        with open(target_path, "a") as fh:
            fh.write("\n".join(missing) + "\n")
    os.makedirs(STUB_BACKUPS, exist_ok=True)
    os.replace(stub_path, os.path.join(STUB_BACKUPS, "%d-%s" % (time.time(), os.path.basename(stub_path))))
    return True


def same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def walk(root):
    for parent, dirs, files in os.walk(root, followlinks=False):
        rel = os.path.relpath(parent, root)
        links = [d for d in dirs if os.path.islink(os.path.join(parent, d))]
        dirs[:] = [d for d in dirs if d not in links]
        yield rel, dirs, files + links


def plan_conflicts(src, dst):
    for rel, dirs, names in walk(src):
        for name in dirs:
            d = os.path.normpath(os.path.join(dst, rel, name))
            if os.path.lexists(d) and not os.path.isdir(d):
                return d
        for name in names:
            s = os.path.normpath(os.path.join(src, rel, name))
            d = os.path.normpath(os.path.join(dst, rel, name))
            if os.path.islink(s) or not os.path.lexists(d) or os.path.islink(d):
                continue
            if os.path.isdir(d):
                return d
            if same_file(s, d) or is_stub(s) or is_stub(d):
                continue
            return d
    return None


def link_tree(src, dst):
    for rel, dirs, names in walk(src):
        for name in dirs:
            os.makedirs(os.path.normpath(os.path.join(dst, rel, name)), exist_ok=True)
        for name in names:
            s = os.path.normpath(os.path.join(src, rel, name))
            d = os.path.normpath(os.path.join(dst, rel, name))
            if os.path.islink(s):
                if not os.path.lexists(d):
                    os.symlink(os.readlink(s), d)
                continue
            if os.path.lexists(d) and not os.path.islink(d):
                if same_file(s, d):
                    continue
                if is_stub(s):
                    absorb_stub(s, d)
                    continue
                absorb_stub(d, s)
            tmp = d + ".unify-%d" % os.getpid()
            os.link(s, tmp)
            os.replace(tmp, d)


def exchange(a, b):
    try:
        libc = ctypes.CDLL(None, use_errno=True)
    except OSError:
        return False
    if sys.platform.startswith("linux"):
        fn = getattr(libc, "renameat2", None)
        args = (-100, os.fsencode(a), -100, os.fsencode(b), 2)
    elif sys.platform == "darwin":
        fn = getattr(libc, "renamex_np", None)
        args = (os.fsencode(a), os.fsencode(b), 2)
    else:
        return False
    if fn is None:
        return False
    return fn(*args) == 0


def drain(old, home, alias):
    for parent, dirs, files in os.walk(old, topdown=False, followlinks=False):
        rel = os.path.relpath(parent, old)
        for name in files + [d for d in dirs if os.path.islink(os.path.join(parent, d))]:
            s = os.path.join(parent, name)
            d = os.path.normpath(os.path.join(home, rel, name))
            if os.path.lexists(d) and (os.path.islink(s) or same_file(s, d)):
                os.unlink(s)
            elif not os.path.lexists(d):
                os.makedirs(os.path.dirname(d), exist_ok=True)
                os.rename(s, d)
        if parent != old:
            try:
                os.rmdir(parent)
            except OSError:
                pass
    try:
        os.rmdir(old)
    except OSError:
        os.makedirs(DIR_BACKUPS, exist_ok=True)
        os.rename(old, os.path.join(DIR_BACKUPS, "%s-%d" % (os.path.basename(alias), time.time())))


def place_symlink(alias, home):
    tmp = os.path.join(PROJECTS, ".%s.link-%d" % (os.path.basename(alias), os.getpid()))
    os.symlink(os.path.basename(home), tmp)
    try:
        os.rename(tmp, alias)
    except OSError:
        os.unlink(tmp)
        raise


def merge(alias, home):
    if plan_conflicts(alias, home):
        return False
    link_tree(alias, home)
    held = os.path.join(PROJECTS, ".%s.old-%d" % (os.path.basename(alias), os.getpid()))
    os.symlink(os.path.basename(home), held)
    if not exchange(held, alias):
        os.unlink(held)
        os.rename(alias, held)
        os.symlink(os.path.basename(home), alias)
    if os.path.islink(held) or os.path.realpath(held) == os.path.realpath(home):
        os.unlink(held)
        return True
    drain(held, home, alias)
    return True


def unify(worktree, main):
    alias = project_dir(worktree)
    home = project_dir(main)
    if alias is None or home is None or alias == home:
        return None
    os.makedirs(home, exist_ok=True)
    if os.path.islink(alias) and os.path.realpath(alias) == os.path.realpath(home):
        return "already"
    with open(LOCK_PATH, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if os.path.islink(alias) and os.path.realpath(alias) == os.path.realpath(home):
            return "already"
        if os.path.islink(alias) or not os.path.lexists(alias):
            try:
                place_symlink(alias, home)
                return "unified"
            except OSError:
                if not os.path.isdir(alias) or os.path.islink(alias):
                    return None
        return "unified" if merge(alias, home) else "conflict"


def enter_target(tool_input, cwd):
    path = tool_input.get("path")
    if path:
        return worktree_of(os.path.normpath(os.path.join(cwd, os.path.expanduser(path))))
    name = tool_input.get("name")
    root = checkout_root(cwd) if name else None
    if root:
        return (os.path.join(root, ".claude", "worktrees", name), root)
    return None


def sample(path):
    try:
        with open(path, "rb") as fh:
            head = fh.read(SAMPLE_BYTES)
            size = os.fstat(fh.fileno()).st_size
            if size > SAMPLE_BYTES:
                fh.seek(max(SAMPLE_BYTES, size - SAMPLE_BYTES))
                head += b"\n" + fh.read()
    except OSError:
        return ""
    return head.decode("utf-8", "replace")


def recorded_paths(path):
    found = []
    for line in sample(path).splitlines():
        if '"cwd"' not in line and '"relocatedCwd"' not in line and '"worktreePath"' not in line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        session = rec.get("worktreeSession") if isinstance(rec.get("worktreeSession"), dict) else {}
        for value in (rec.get("cwd"), rec.get("relocatedCwd"), session.get("worktreePath")):
            if isinstance(value, str) and value and value not in found:
                found.append(value)
    return found


def worktree_for_dir(d):
    try:
        names = sorted(
            (n for n in os.listdir(d) if n.endswith(".jsonl")),
            key=lambda n: os.lstat(os.path.join(d, n)).st_mtime,
            reverse=True,
        )
    except OSError:
        return None
    for name in names:
        f = os.path.join(d, name)
        if os.path.islink(f):
            continue
        for p in recorded_paths(f):
            if project_dir(p) != d:
                continue
            main = main_checkout(p)
            return (p, main) if main and project_dir(main) != d else None
    return None


def prune_dead_links():
    pruned = 0
    for entry in os.listdir(PROJECTS):
        d = os.path.join(PROJECTS, entry)
        if entry.startswith(".") or os.path.islink(d) or not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            f = os.path.join(d, name)
            if name.endswith(".jsonl") and os.path.islink(f) and not os.path.exists(f):
                os.unlink(f)
                pruned += 1
    return pruned


def backfill():
    counts = {"unified": 0, "already": 0, "conflict": 0}
    for entry in sorted(os.listdir(PROJECTS)):
        d = os.path.join(PROJECTS, entry)
        if entry.startswith("."):
            continue
        if os.path.islink(d):
            counts["already"] += 1
            continue
        if not os.path.isdir(d):
            continue
        pair = worktree_for_dir(d)
        if pair is None:
            continue
        result = unify(*pair)
        if result in counts:
            counts[result] += 1
            if result != "already":
                print("%s %s -> %s" % (result, entry, os.path.basename(project_dir(pair[1]))))
    pruned = prune_dead_links()
    print("%d newly unified, %d already unified, %d left alone (conflicting transcripts), %d dead links pruned" % (
        counts["unified"], counts["already"], counts["conflict"], pruned))


def main():
    if "--backfill" in sys.argv:
        backfill()
        return
    payload = json.load(sys.stdin)
    cwd = payload.get("cwd") or os.getcwd()
    if payload.get("hook_event_name") == "PreToolUse":
        pair = enter_target(payload.get("tool_input") or {}, cwd)
    else:
        pair = worktree_of(payload.get("new_cwd") or cwd)
    if pair:
        unify(*pair)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if "--backfill" in sys.argv:
            raise
    sys.exit(0)
