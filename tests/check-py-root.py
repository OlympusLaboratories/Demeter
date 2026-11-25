#!/usr/bin/env python3

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = (
    "larrabeedylan_work_darwin",
    "larrabeedylan_work_linux",
    "larrabeedylan_home_darwin",
)
SCRIPT = "profiles/%s/.claude/skills/changes-diagram/scripts/build_changes_graph.py"

RULES = """
changes-diagram's py_root derivation, which decides whether a Python branch is
drawn as a call graph or as a flat file map:

  the three profile copies            byte-identical — check-transform.py compares
                                      the work pair and the transform, nothing
                                      pins this file on its own

detect_py_root, driven directly:

  a touched package in a monorepo     resolves to that package's root, not to the
                                      first package root found on disk. deriving it
                                      from the layout alone gave every package in
                                      such a repo the wrong root, and so mode=files
  the package holding most of the      wins, and a tie is broken by path, so the
  changed files                       answer does not depend on diff order
  a diff with no Python               falls back to the repo layout scan
  a changed .py under no manifest     falls back to the repo layout scan
  a manifest at the repo root         answers exactly what the layout scan answers,
                                      so the single-package case cannot regress
  the walk up                         stops at the repo root and never escapes it
  a top-level package directory       resolves to the repo root. the loop that used
                                      to look for one returned the same "" as the
                                      fallback beneath it, so it was dead

the script run end to end over a throwaway git repo:

  a change to one package of a        mode=callgraph, with that package's root in
  several-root monorepo               py_root — the acceptance criterion
  --py-root                           still wins over the derivation
  --package                           still wins over the derived prefix
  a diff with no Python               mode=files, and no crash
"""


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
                print("      %s" % str(detail).strip().replace("\n", "\n      "))


def load(profile):
    path = os.path.join(REPO, SCRIPT % profile)
    spec = importlib.util.spec_from_file_location("build_changes_graph_%s" % profile, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(profile):
    with open(os.path.join(REPO, SCRIPT % profile), "rb") as handle:
        return handle.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text)


MONOLITH = "python/service/handler.py"
WIDGET = "python_projects/lib/widget/src/widget/core.py"
WIDGET_OTHER = "python_projects/lib/widget/src/widget/rules.py"
GADGET = "python_projects/lib/gadget/src/gadget/core.py"


def monorepo(root):
    write(os.path.join(root, "pyproject.toml"), "[project]\nname = 'monolith'\n")
    write(os.path.join(root, MONOLITH), "def handle():\n    return 1\n")
    write(os.path.join(root, "python/service/__init__.py"), "")
    for pkg in ("widget", "gadget"):
        base = os.path.join(root, "python_projects/lib", pkg)
        write(os.path.join(base, "pyproject.toml"), "[project]\nname = '%s'\n" % pkg)
        write(os.path.join(base, "src", pkg, "__init__.py"), "")
        write(os.path.join(base, "src", pkg, "core.py"), "def run():\n    return 1\n")
        write(os.path.join(base, "src", pkg, "rules.py"), "def allow():\n    return 1\n")
    write(os.path.join(root, "docs/notes.md"), "notes\n")
    write(os.path.join(root, "loose/orphan.py"), "def stray():\n    return 1\n")


def git(root, *args):
    return subprocess.run(
        ["git", "-C", root, *args], capture_output=True, text=True, check=True
    ).stdout


def unit_checks(suite, module, root):
    detect = module.detect_py_root

    suite.ok(
        "a touched monorepo package resolves to its own root",
        detect(root, [WIDGET]) == "python_projects/lib/widget/src",
        detect(root, [WIDGET]),
    )
    suite.ok(
        "the package holding most of the changed files wins",
        detect(root, [GADGET, WIDGET, WIDGET_OTHER]) == "python_projects/lib/widget/src",
        detect(root, [GADGET, WIDGET, WIDGET_OTHER]),
    )
    one_each = detect(root, [GADGET, WIDGET])
    suite.ok(
        "a tie is broken by path, not by diff order",
        one_each == detect(root, [WIDGET, GADGET]) == "python_projects/lib/gadget/src",
        one_each,
    )
    suite.ok(
        "a diff with no Python falls back to the layout scan",
        detect(root, ["docs/notes.md"]) == "python",
        detect(root, ["docs/notes.md"]),
    )
    suite.ok(
        "an empty diff falls back to the layout scan",
        detect(root, []) == "python",
        detect(root, []),
    )
    suite.ok(
        "a changed .py under the repo's own manifest answers what the layout scan answers",
        detect(root, [MONOLITH]) == module.layout_py_root(module.Path(root)) == "python",
        detect(root, [MONOLITH]),
    )
    suite.ok(
        "the walk up stops at the repo root",
        module.package_root(module.Path(root), "loose/orphan.py") == module.Path(root),
        module.package_root(module.Path(root), "loose/orphan.py"),
    )

    with tempfile.TemporaryDirectory() as bare:
        write(os.path.join(bare, "pkg/__init__.py"), "")
        write(os.path.join(bare, "pkg/core.py"), "def run():\n    return 1\n")
        suite.ok(
            "a top-level package directory with no manifest resolves to the repo root",
            detect(bare, ["pkg/core.py"]) == "",
            detect(bare, ["pkg/core.py"]),
        )
        suite.ok(
            "package_root finds no manifest where there is none",
            module.package_root(module.Path(bare), "pkg/core.py") is None,
        )

    with tempfile.TemporaryDirectory() as layered:
        write(os.path.join(layered, "src/app/__init__.py"), "")
        write(os.path.join(layered, "src/app/core.py"), "def run():\n    return 1\n")
        write(os.path.join(layered, "pyproject.toml"), "[project]\nname = 'app'\n")
        suite.ok(
            "src/ inside the resolved package root is honoured",
            detect(layered, ["src/app/core.py"]) == "src",
            detect(layered, ["src/app/core.py"]),
        )


def build(root, out, *extra):
    script = os.path.join(REPO, SCRIPT % PROFILES[0])
    proc = subprocess.run(
        [sys.executable, script, root, "HEAD~1", out, *extra],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None, proc.stderr
    with open(out) as handle:
        return json.load(handle), proc.stderr


def end_to_end(suite):
    with tempfile.TemporaryDirectory() as root:
        monorepo(root)
        git(root, "init", "--quiet", "--initial-branch", "main")
        git(root, "config", "user.email", "t@example.invalid")
        git(root, "config", "user.name", "t")
        git(root, "add", "-A")
        git(root, "commit", "--quiet", "-m", "base")

        core = os.path.join(root, WIDGET)
        write(core, "def run():\n    return helper()\n\n\ndef helper():\n    return 2\n")
        rules = os.path.join(root, WIDGET_OTHER)
        write(rules, "from widget.core import run\n\n\ndef allow():\n    return run()\n")
        git(root, "add", "-A")
        git(root, "commit", "--quiet", "-m", "change the widget package")

        out = os.path.join(root, "graph.json")

        data, err = build(root, out)
        if data is None:
            suite.ok("the script runs over a monorepo package change", False, err)
            return
        suite.ok(
            "a monorepo package change is drawn as a call graph",
            data["mode"] == "callgraph",
            "mode=%s py_root=%r nodes=%d" % (data["mode"], data["py_root"], len(data["nodes"])),
        )
        suite.ok(
            "py_root is the touched package's root",
            data["py_root"] == "python_projects/lib/widget/src",
            data["py_root"],
        )
        suite.ok(
            "the changed functions became nodes",
            len(data["nodes"]) > 0,
            len(data["nodes"]),
        )

        override, err = build(root, out, "--py-root", "python")
        suite.ok("--py-root still wins", override is not None and override["py_root"] == "python",
                 err if override is None else override["py_root"])

        empty, err = build(root, out, "--py-root", "")
        suite.ok("--py-root '' still switches the prefix off",
                 empty is not None and empty["py_root"] == "",
                 err if empty is None else empty["py_root"])

        packaged, err = build(root, out, "--package", "widget.core")
        suite.ok("--package still wins",
                 packaged is not None and packaged["package"] == "widget.core",
                 err if packaged is None else packaged["package"])

        write(os.path.join(root, "docs/notes.md"), "notes, revised\n")
        git(root, "add", "-A")
        git(root, "commit", "--quiet", "-m", "docs only")
        docs, err = build(root, out)
        suite.ok("a diff with no Python resolves without error", docs is not None, err)
        if docs is not None:
            suite.ok("a diff with no Python is drawn as files", docs["mode"] == "files", docs["mode"])
            suite.ok("a diff with no Python keeps the layout scan's answer",
                     docs["py_root"] == "python", docs["py_root"])


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "rules":
        print(RULES.strip())
        return 0

    suite = Suite()

    reference = read(PROFILES[0])
    for profile in PROFILES[1:]:
        suite.ok(
            "%s is byte-identical to %s" % (profile, PROFILES[0]),
            read(profile) == reference,
            "sizes %d and %d" % (len(read(profile)), len(reference)),
        )

    module = load(PROFILES[0])
    for name in ("detect_py_root", "layout_py_root", "package_root", "changed_py_root"):
        suite.ok("%s exists" % name, hasattr(module, name))
    if suite.failures:
        print("check-py-root: %d of %d checks failed" % (suite.failures, suite.checked))
        return 1

    with tempfile.TemporaryDirectory() as root:
        monorepo(root)
        unit_checks(suite, module, root)

    end_to_end(suite)

    if suite.failures:
        print("check-py-root: %d of %d checks failed" % (suite.failures, suite.checked))
        return 1
    print("check-py-root: %d checks passed" % suite.checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
