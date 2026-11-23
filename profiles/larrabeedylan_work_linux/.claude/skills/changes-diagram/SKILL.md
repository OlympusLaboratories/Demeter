---
name: changes-diagram
description: Turn the current branch's diff into an interactive diagram and publish it — a call-flow chart of the changed Python functions, or a file-and-import map when the change is Go, Terraform, TypeScript or anything else. Use when the user says "diagram this branch", "visualize the MR", "visualize the PR", "draw this diff", "show me the call flow", "make a review page for this branch", or "changes-diagram".
---

# Diagram — Chart What This Branch Changes

Turn a branch's diff into one self-contained HTML page and publish it. Two modes, picked automatically:

- **callgraph** — every changed Python function is a box showing lines added and removed, grouped into dashed module boxes, wired together by the calls that were kept, added and dropped, with one hop of unchanged neighbours, callers found elsewhere in the repo, and an `UNUSED` badge on anything production code no longer calls.
- **files** — one box per changed file with its line counts, grouped into directory boxes, wired by imports and references read out of the source (Go import paths, TypeScript/JavaScript relative imports, Terraform module sources and `resource`/`data` references, Python imports). This is what a Go, Terraform, TypeScript, Markdown or mixed branch gets.

The script falls back to **files** mode whenever the Python pass finds no changed functions, so **a non-empty diff never produces an empty chart**. An empty chart reads as "nothing changed", which is the one answer this skill must never give by accident.

Bundled files (paths relative to this skill's directory):

- `scripts/build_changes_graph.py` — diffs a base ref against the working tree and writes the graph JSON.
- `scripts/render_page.py` — injects that JSON into the template.
- `assets/template.html` — the page itself. Generic; it reads `nodes`, `edges`, `modules` and `files` and ignores anything else.

## Step 1: Read the environment

Every forge- and publishing-specific fact comes from the machine, not from this file:

```bash
ENV=~/.claude/scripts/skill-env.sh
CR=$("$ENV" get change_request_short)
STORE=$("$ENV" get artifact_store)
```

`CR` is whatever this machine calls a change request. `STORE` is one of `claude`,
`mnemosyne`, `auto` or `local`. Run `"$ENV" check` to see every value at once.

Use `$CR` whenever you have to name the change request in what you write back to the user. Elsewhere prefer **the change** or **the branch** — they read correctly everywhere and need no lookup.

## Step 2: Pick the base and the title

Run from the repo root (`git rev-parse --show-toplevel`).

- **Base**: `git merge-base <default-branch> HEAD`, or the target branch of the change when you know it. The diff is base → working tree, so committed *and* uncommitted tracked changes are both included; untracked files are not.
- If `git diff --stat <base>` is empty, stop and tell the user there is nothing to draw — most often the wrong base, or a branch that is already merged. Do not publish an empty page.
- **Title**: the title of the change if you know it, else the ticket id and subject from the branch name or the most recent commit (e.g. `ENG-412 split the dispatch loop`).

## Step 3: Build the graph JSON

Write outputs to the session scratchpad, **one folder per branch**, so republishing the same branch reuses the same file path and updates the same page instead of creating a second one:

```bash
SKILL=<this skill's directory>
OUT=<scratchpad>/changes-diagram/<branch-name-with-slashes-replaced>
mkdir -p "$OUT"
python3 "$SKILL/scripts/build_changes_graph.py" . "$BASE" "$OUT/graph.json" --title "<title>"
```

It prints `N nodes, M edges, K groups, mode=<callgraph|files>`.

Two overrides exist, both derived from the repo when omitted — pass them only when the derived values are visibly wrong:

- `--py-root` — the directory Python module paths are relative to. Detected by looking for `src/` with packages in it, then `python/`, then the packages `pyproject.toml` declares, then top-level directories holding an `__init__.py`, falling back to the repo root.
- `--package` — a dotted prefix that limits which modules become nodes. Derived from the changed modules' common prefix; when they share none, no filter is applied at all. Pass `--package ''` to switch the filter off explicitly, or a wider prefix when the change reaches past it.

The JSON records what was used in `py_root` and `package`, so Step 5 can check them.

## Step 4: Render the page

```bash
python3 "$SKILL/scripts/render_page.py" "$OUT/graph.json" "$SKILL/assets/template.html" "$OUT/<branch>.html"
```

The template ships a fixed `<title>`, and a published page takes its name from that tag in preference to any title passed at publish time. Retitle the **rendered copy** (never the template, which is shared by every run):

```bash
python3 - "$OUT/<branch>.html" "<title>" <<'PY'
import html, re, sys
path, title = sys.argv[1], sys.argv[2]
page = open(path).read()
open(path, "w").write(re.sub(r"<title>.*?</title>", lambda m: "<title>%s</title>" % html.escape(title), page, count=1))
PY
```

## Step 5: Sanity-check the JSON, not the HTML

Skim the data in one command. Reading the rendered HTML tells you nothing useful and costs a lot of context:

```bash
python3 -c "
import json; d = json.load(open('$OUT/graph.json'))
print(d['mode'], len(d['nodes']), 'nodes', len(d['edges']), 'edges', '| py_root', repr(d['py_root']), '| package', repr(d['package']))
for n in d['nodes']:
    if n['status'] != 'context' or n.get('orphaned'):
        print(f\"{n['status']:9} +{n['added']:<3} -{n['removed']:<3} {'T' if n['test'] else ' '} {'UNUSED' if n.get('orphaned') else '':6} {n['id']}\")"
```

Three things to check:

1. The touched functions or files match what the change is actually about.
2. `mode=files` on a branch that is mostly Python usually means `py_root` or `package` was derived wrongly — re-run Step 3 with the override and compare.
3. An `UNUSED` badge that looks wrong almost always is: it means no caller was *resolved*, and call resolution is static (see Limitations). Mention it as a question, never as a finding.

## Step 6: Publish

Branch on `$STORE` from Step 1.

### `claude` — publish with the Artifact tool

Call the **Artifact** tool with `file_path` set to the rendered HTML, plus:

- `favicon` — one or two emoji, **first publish only**. Use `🔀`. On every later publish of the same branch, omit it: an artifact keeps the icon it was created with, and people find the tab by its icon.
- `title` — a short noun phrase naming the change (the `<title>` written in Step 4 normally supplies this).
- `description` — one sentence saying what the page shows, naming the branch.

Re-running for the same branch: rebuild, then publish **the same file path**. That updates the page in place and keeps its URL. A new path creates a second artifact and orphans the first.

### `mnemosyne` — publish with the shared script

```bash
FOLDER=$(~/.claude/scripts/skill-env.sh get diagram_folder)
~/.claude/scripts/publish-artifact.sh <rendered>.html \
  ${FOLDER:+--folder "$FOLDER"} \
  --title '<short noun phrase naming the change>' \
  --description '<one sentence, naming the branch>'
```

It prints the URL on stdout. `diagram_folder` is empty on a machine with no folder to
file into, and the `${FOLDER:+…}` form then omits the flag rather than passing an empty
one — **never substitute a folder name of your own**, because publishing refuses a folder
that does not exist and the run loses its diagram to a guess.

**Exit status 3 is not a failure.** It means this machine has no self-hosted store, which
is the ordinary answer on most of them. Fall through to the next option. Any other
non-zero status is a real failure: report what it printed in one line, then fall through
the same way.

Re-running for the same branch: pass `--update <hash>` taken from the previous URL, which
revises the page in place and keeps its link and its stored data.

### `auto` — mnemosyne, then the Artifact tool, then local

Try each in that order and stop at the first that works. Say which one published it.

### `local`, or everything above failed

Write the HTML to the scratchpad and print its **absolute path** so the user can `open` it. The page is fully self-contained apart from two CDN assets (fonts and the layout engine), so it renders from the filesystem.

**Never hard-fail this step.** A diagram sitting in a local file is a success with a caveat; an exception is a wasted run.

## Step 7: Reply

Give the user the link or path, then 2–4 lines on what the chart actually shows for this change — the main flow difference in `callgraph` mode, the shape of the file/import map in `files` mode, and anything flagged `UNUSED`. Say which mode produced it, so an unexpectedly coarse chart is never mistaken for a shallow change.

Then the warning, which is not boilerplate: **the page embeds the diff of every changed function (callgraph mode) or every changed file (files mode)**. Anyone the page is shared with can read that code. An Artifact is private until it is shared from its Share menu — say so, and say it before anyone shares the link rather than after.

## How the page reads

- Boxes: outlined = modified, green = added, red dashed and struck through = removed, small grey = unchanged neighbour. Bar length is to one scale across the whole change.
- Dashed boxes = modules in `callgraph` mode, directories in `files` mode — labelled with the path, module-level `+/-` (imports, constants, `__main__`), and how many unchanged functions are hidden.
- Edges: grey = kept, green = new, red dashed = dropped. In `files` mode those are imports and references rather than calls.
- Toolbar: Production / Tests charts, Before + after / After / Before, and a toggle for unchanged neighbours. Panel: the review walk (changed functions in call order, callers first), the per-item diff, callers and callees, Prev/Next.
- `#tests` in the URL opens the tests chart.

## Limitations

- **Call resolution is static and name-based.** Same-module calls, `from X import f`, module aliases (`import a.b as m; m.f()`), `self.method()` and `monkeypatch.setattr(mod, "f", ...)` resolve. Calls through another object (`client.fetch()`), `getattr`, dispatch tables and registries do not become edges — which is also why an `UNUSED` badge is a question and not a verdict.
- **`--package` bounds the graph.** Callers outside the package are not drawn and do not count against `UNUSED`.
- **`files` mode is a map, not a call graph.** Its boxes are files, so a 400-line change to one file is a single box; its edges are import and reference statements found by regex, so a generated or dynamically-built import is missed, and a non-relative TypeScript specifier (a bare package name, or a `tsconfig` path alias) is deliberately not resolved. Terraform edges come from local `module` sources and from `resource`/`data`/`module` references that name a declaration in another changed file. A language with no extractor — Markdown, YAML, SQL, shell — gets correctly-counted boxes and no edges at all. Treat a sparse `files`-mode chart as "the imports between changed files", never as "these files are unrelated".
- **Only changed files become boxes in `files` mode.** An unchanged file both of them import is not drawn, so two files that are related through it look unrelated.
- **Binary files** appear as boxes with no line counts and no diff, labelled `binary file`.
- **When every changed file is a test**, `files` mode puts them all on the main chart rather than leaving it empty and hiding everything behind the Tests tab.
- **Layout uses elkjs 0.9.3 from jsDelivr**, and the fonts come from Google Fonts. Both load over the network; the rest of the page is self-contained.
