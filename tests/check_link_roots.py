#!/usr/bin/env python3
"""Static half of tests/check-link-roots.sh.

Reads install.sh, extracts every link_file / link_directory_contents
destination, resolves the shell variables install.sh builds them from, and
checks each resulting directory against the roots demeter_link_roots declares.

The shell wrapper supplies ROOTS and RECURSIVE_ROOTS so the declared list is
read from lib/paths.sh rather than restated here.
"""

import os
import re
import sys

LINK_CALL = re.compile(
    r'^\s*(?:link_file|link_directory_contents)\s+"[^"]*"\s+"([^"]*)"'
)

HOME = os.environ["HOME"]

# What install.sh assigns to each variable that can lead a destination. A
# variable absent from here is reported rather than skipped: that is the half
# of this check that catches a new link root.
LEADING_VARS = {
    "$home": [HOME],
    "$claude_dst": [f"{HOME}/.claude"],
    # link_directory_contents is only ever called with a $claude_dst path.
    "$dst_dir": [f"{HOME}/.claude"],
    "$editor_dir": None,  # filled from vscode_user_dirs, below
    "$git_ignore_dst": None,  # filled from git_excludes_path, below
}

# A trailing component that is itself a variable stands for a filename, so the
# directory is whatever precedes it.
FILENAME_VARS = {"$name", "$item"}

# The map above is only correct while install.sh still assigns what it assumes.
# Without this, changing claude_dst to point elsewhere would leave the map
# silently stale, which is the same drift class one layer out.
VAR_ASSIGNMENTS = {
    "$home": re.compile(r'\bhome="\$HOME"'),
    "$claude_dst": re.compile(r'\bclaude_dst="\$home/\.claude"'),
}

# link_directory_contents takes its destination as a parameter, so $dst_dir is
# only as safe as what the call sites pass it.
DST_DIR_CALL = re.compile(r'^\s*link_directory_contents\s+"[^"]*"\s+"(\$claude_dst[^"]*)"')


def declared_roots():
    roots = [r for r in os.environ["ROOTS"].splitlines() if r]
    recursive = [r for r in os.environ["RECURSIVE_ROOTS"].splitlines() if r]
    return roots, recursive


def resolve(dest, editor_dirs, git_ignore_dir):
    """Expand a destination into the concrete directories it can name.

    Returns (dirs, unresolved_variable).
    """
    parts = dest.split("/")
    lead = parts[0]
    rest = parts[1:]

    if lead.startswith("$"):
        if lead == "$editor_dir":
            bases = editor_dirs
        elif lead == "$git_ignore_dst":
            # The whole destination is the file; its directory is the root.
            return [git_ignore_dir], None
        elif lead in LEADING_VARS and LEADING_VARS[lead]:
            bases = LEADING_VARS[lead]
        else:
            return [], lead
    else:
        return [], lead

    # Drop the final component: a filename, literal or variable alike.
    if rest:
        rest = rest[:-1]

    for part in rest:
        if part.startswith("$"):
            if part in FILENAME_VARS:
                continue
            return [], part

    suffix = "/".join(p for p in rest if not p.startswith("$"))
    return [f"{b}/{suffix}" if suffix else b for b in bases], None


def covered(directory, roots, recursive):
    if directory in roots:
        return True
    return any(directory.startswith(r + "/") for r in recursive)


def main():
    install_sh = sys.argv[1]
    roots, recursive = declared_roots()

    editor_dirs = [r for r in roots if r.endswith("/User")]
    git_ignore_dir = next(
        (r for r in roots if r.endswith("/git")),
        HOME,
    )

    failures = []
    checked = 0

    with open(install_sh, encoding="utf-8") as handle:
        source = handle.read()

    for var, pattern in VAR_ASSIGNMENTS.items():
        if not pattern.search(source):
            failures.append(
                f"{var} is resolved by this check as "
                f"{LEADING_VARS[var][0].replace(HOME, '~')}, but install.sh no "
                f"longer assigns it that way. Re-read the assignment and update "
                f"LEADING_VARS."
            )

    dst_dir_calls = [
        line
        for line in source.splitlines()
        if re.match(r'^\s*link_directory_contents\s+"', line)
    ]
    for line in dst_dir_calls:
        if not DST_DIR_CALL.match(line):
            failures.append(
                f"link_directory_contents is called with a destination that is "
                f"not under $claude_dst, so $dst_dir no longer resolves to "
                f"~/.claude: {line.strip()}"
            )

    with open(install_sh, encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            match = LINK_CALL.match(line)
            if not match:
                continue
            dest = match.group(1)
            dirs, unresolved = resolve(dest, editor_dirs, git_ignore_dir)
            if unresolved:
                failures.append(
                    f"install.sh:{lineno}: destination {dest!r} leads with "
                    f"{unresolved!r}, which this check does not know. Add it to "
                    f"LEADING_VARS, or declare its root in demeter_link_roots."
                )
                continue
            for directory in dirs:
                checked += 1
                if not covered(directory, roots, recursive):
                    shown = directory.replace(HOME, "~")
                    failures.append(
                        f"install.sh:{lineno}: links into {shown}, which no "
                        f"root in demeter_link_roots covers. uninstall.sh "
                        f"cannot reach it."
                    )

    print("=== link root coverage ===")
    print("")
    print(f"  {len(roots)} declared root(s), {len(recursive)} recursive")
    print(f"  {checked} destination(s) checked in install.sh")
    print("")

    if not checked:
        print("  FAIL — matched no link_file calls; the parser has gone stale")
        return 1

    if failures:
        for failure in failures:
            print(f"  FAIL — {failure}")
        print("")
        print(f"failed {len(failures)}")
        return 1

    print("  ok   — every destination falls under a declared root")
    print("")
    print("passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
