# agent-watch — Design

A VS Code extension that opens an editor tab showing, live, what every Claude Code
session in the current workspace is doing — including the subagents each one spawns,
whether through the `Agent` tool or a `Workflow` swarm.

Status: **M1–M4 built**, plus a polish pass: progressive expansion, viewport refit on
scope change, default-open prose, and honest thinking markers.

---

## 1. Goal

Replace and surpass `wfwatch` (the shell function in each profile's
`.zshrc.local` / `.bashrc`, which tails a workflow `journal.jsonl` and prints
`started` / `result` lines with a 200-character result preview).

What agent-watch adds over it:

- **Every agent, not just workflow agents.** `wfwatch` only reads
  `subagents/workflows/<runId>/journal.jsonl`, so `Agent`-tool subagents are invisible
  to it. Those have transcripts on disk too.
- **What the agent is doing, not just that it started.** Each tool call, its arguments,
  its result, the agent's own prose output — not a truncated final payload.
- **The whole workspace at once.** Multiple worktrees, each with its own live sessions,
  in one view.
- **An editor tab**, not a terminal that must be left running in a split.

### Non-goals for the MVP

- **Chain-of-thought text.** It is not recoverable — see §3. The design treats this as
  settled, not as a thing to work around later.
- Launching, steering, or stopping agents. Read-only observation.
- Detecting which repos a session *edited*. Sessions are filed by the directory they
  started in, so a session in repo A that edits repo B stays under A. Attributing by
  edited path would mean scanning every `tool_use` argument — a different, far more
  expensive feature. Out of scope.
- Remote / SSH sessions. Local `~/.claude/projects` only.

---

## 2. The data on disk

All of it is append-only JSONL under `~/.claude/projects/<slug>/`, where `<slug>` is the
session's working directory with `/` and `.` replaced by `-`
(`/Users/dylanlarrabee/Demeter` → `-Users-dylanlarrabee-Demeter`).

```
~/.claude/projects/<slug>/
  <session-uuid>.jsonl                                  main session transcript
  <session-uuid>/
    workflows/
      wf_<runId>.json                                   run manifest — phases, per-agent label + state
      scripts/<name>-wf_<runId>.js                      script snapshot
    subagents/
      agent-<id>.jsonl                                  Agent-tool subagent transcript
      agent-<id>.meta.json                              { agentType, description, toolUseId, spawnDepth }
      workflows/<runId>/
        journal.jsonl                                   { type: started|result, agentId, key, result }
        agent-<id>.jsonl                                workflow subagent transcript
        agent-<id>.meta.json                            { agentType: "workflow-subagent", spawnDepth }
```

Verified on this machine: 157 session transcripts in the `gridmatic-dev` slug alone,
155 workflow journals across all projects, 29 non-workflow subagent transcripts.

Footprint, measured per-file with `stat` (not `du` on directories — that follows the 74
worktree symlinks and double-counts wildly):

| Scope | Files | Size |
|---|---|---|
| All of `~/.claude/projects` | 11,776 | **1,056 MB** |
| └ under `subagents/` | 11,145 (95%) | **786 MB (74%)** |
| └ session roots | 631 | 270 MB |

### Transcript line shape

Every line is one complete message. Lines carry `sessionId`, `timestamp`, `type`
(`user` / `assistant` / `attachment` / `queue-operation`), and — on real message lines —
`cwd`, `gitBranch`, and `version`. `message.content` is an array of blocks:
`text`, `thinking`, `tool_use`, `tool_result`.

### Parent → child linkage

This is the part that makes a tree view cheap. A subagent's `.meta.json` carries the
`toolUseId` of the `Agent` call that spawned it, and that value is exactly the
`tool_use.id` in the parent transcript:

```json
{"agentType":"Explore","description":"Explore iam reconcile + policy drift",
 "toolUseId":"toolu_01JE8zeWtFZeKxUiW9kZ7KWG","spawnDepth":1}
```

So the parent/child edge is a join on a stable id, not a heuristic over timestamps.
`spawnDepth` gives nesting depth directly, so agents that spawn agents render correctly
without the extension tracking recursion itself.

Workflow subagents have no `toolUseId` (they are launched by the harness, not by a
tool call in the parent transcript); their grouping is the `<runId>` directory, and
`journal.jsonl` supplies launch and completion events keyed by `agentId`.

### The run manifest is the real structure

`<session>/workflows/wf_<runId>.json` carries a `workflowProgress` array with one row per
agent, and it is **written during the run**, not only at the end — a killed run's manifest
shows its Draft phase `done` and its Cross-examine phase mid-flight:

```json
{"type":"workflow_agent","agentId":"a950f4e4902132002","label":"review:correctness",
 "phaseIndex":1,"phaseTitle":"Review","state":"done","model":"claude-opus-5",
 "lastToolName":"StructuredOutput"}
```

All 57 manifests on this machine carry it, and `agentId` joins 96/96 against the agent
files of the largest run. This supersedes every heuristic: labels come from `label`
instead of prompt-sniffing, status from `state` (`done` / `error` / `progress` / `start`)
instead of inference, and the run's own `logs[0]` is a ready-made summary line
("review-code: 6 lenses, 30 candidate findings, 0 out-of-scope, 15 confirmed"). The
journal remains the fallback when a manifest is absent.

### Liveness

Files are appended as work happens, not flushed at the end. Measured while researching
this document: the active session transcript grew 317,133 → 330,499 bytes over a handful
of tool calls, with an mtime 12 seconds old. Granularity is one complete message — not
token-by-token, but well under the latency that matters for watching a swarm.

---

## 3. Thinking text is not available

Every thinking block on disk is:

```json
{"type":"thinking","thinking":"","signature":"CAISjwUK5wIIEhgCKkDzXKRCnVeLSDFYC706t0ayO/Cqe..."}
```

A grep across all 1.1 GB of `~/.claude/projects` for any `"thinking"` value of 20+
characters returns **zero** matches — main sessions, `Agent` subagents, and workflow
subagents alike. No hook event carries it either: `PreToolUse` / `PostToolUse` payloads
are tool input and output only.

### Why it is empty

Not because Claude Code strips it on write — because the API returned it empty. Thinking
blocks have a `display` setting, and `"omitted"` is the **default** on Opus 5 (and Fable 5,
Mythos 5, Opus 4.8, Opus 4.7, Sonnet 5). Under `"omitted"` the `thinking` field arrives as
an empty string. Thinking still happens and is still billed; only visibility changes.

`display: "summarized"` returns a readable **summary** of the reasoning. The **raw** chain
of thought is never exposed on any model under any setting.

### Summaries are obtainable, and verified working

Claude Code 2.1.250 accepts a hidden flag — `--thinking-display <summarized|omitted>` —
absent from `--help` but present in the parser. In interactive mode the binary already
resolves to `"summarized"` when an internal feature gate is on; that gate is off on this
account, which is why transcripts are empty. The flag bypasses it:

```js
function Jfn({explicitDisplay, isNonInteractive, outputFormat, verbose}) {
  if (explicitDisplay) return explicitDisplay;          // the flag wins outright
  if (!isNonInteractive) return Qht() ? "summarized" : undefined;
  ...
}
```

Measured A/B on the same prompt, same model, 2026-10-19:

| Run | CLI | `thinking` chars | `signature` chars |
|---|---|---|---|
| `--thinking-display summarized` | 2.1.250 | **3,675** | — |
| control (no flag) | 2.1.250 | 0 | 16,400 |
| `--thinking-display summarized` | **2.1.304** | **724** | — |
| `--thinking-display highlights` | **2.1.304** | 0 | present |

And the summary **persists to the transcript on disk**, which is what agent-watch reads —
confirmed by reading the written `.jsonl` back, not just the stream. The text is
substantive prose ("I'm working through all four cases systematically — True/False gods
crossed with 'ja' meaning yes or no…"), not a label.

**Use `summarized`.** 2.1.304 added a third choice, `highlights`, which leaves the
`thinking` field empty and emits no new block type — nothing reaches disk. The resolution
function is byte-for-byte equivalent across 2.1.250 and 2.1.304 (`if (explicitDisplay)
return explicitDisplay`), so the override itself is stable; the *set of values* is not.

Caveat: the flag is undocumented, hidden from `--help`, and its accepted values changed
between two releases three weeks apart. Treat it as an enhancement, never a dependency,
and re-probe `--thinking-display bogus` after any upgrade — the parser error lists the
currently valid choices.

### Version skew to be aware of

Two Claude Code binaries exist on this machine and update independently:

| Install | Path | Updates via |
|---|---|---|
| CLI | `/opt/homebrew/bin/claude` (2.1.304) | `brew upgrade --cask claude-code` |
| VS Code extension bundle | `~/.vscode/extensions/anthropic.claude-code-<ver>-darwin-arm64/resources/native-binary/claude` (2.1.250) | VS Code extension updates |

The extension's bundle is what an in-editor session actually runs, so a wrapper script
must point at the binary whose session you want to affect. agent-watch itself is
unaffected — it reads files, not binaries — but the two can write transcripts from
different versions into the same project directory.

### Format stability across the upgrade

Every identifier the design depends on is present in 2.1.304: `subagents`, `toolUseId`,
`spawnDepth`, `agentType`, `journal.jsonl`, `workflows`, `workflow-subagent`, `gitBranch`.
A transcript written by 2.1.304 carries `cwd`, `gitBranch`, `version`, and `sessionId` per
line exactly as 2.1.250 did. The data model in §2 is verified against the current release.

### Design consequence

The renderer must **print `thinking` text whenever the field is non-empty** and fall back
to the dimmed no-text marker only when it is empty. Both states are real and will coexist
in the same workspace — sessions launched with the flag carry summaries, sessions without
it do not — so this is a required branch, not insurance against a hypothetical.

A thinking block with no text renders as a **dimmed marker with a duration** — an honest
"it thought here for 4s" rather than a gap that reads like missing data.

### The signature is not a backdoor

Decoding one: a protobuf-ish frame, ~45% printable bytes, carrying plaintext metadata
(`claude-opus-5`, `thinking`, a block UUID, `prefix_before_block_v1`) around a
high-entropy payload. Its length varies with the thinking length (816–7,964 base64
characters across one session), so it plainly carries content-derived state — but there
is no client-side key, and its documented purpose is letting the API verify a thinking
block was not altered when you pass it back on a later turn. It is a replay credential,
not a transcript. Treat recovery as closed.

The only route to real streamed thinking is launching agents from the extension itself via
`claude -p --output-format stream-json --include-partial-messages`. That is a different
product — an orchestrator, not a viewer — and is explicitly out of scope. A viewer built on
files keeps working against agents launched that way later, so this door stays open.

---

## 4. Workspace and worktree scoping

The requirement: several tickets in flight in separate worktrees at once, all visible,
grouped separately.

Four facts from the current machine shape this:

1. **Worktrees live inside the main checkout**, at
   `<main>/.claude/worktrees/<user>/<TICKET>`.

2. **Their project dirs are already unified.** `link-worktree-session.py` (installer step
   7) makes each worktree's `~/.claude/projects/<slug>` a **directory symlink** to the main
   checkout's slug — 74 such symlinks exist here. So every session for a repo, from the main
   checkout or any worktree, lands in **one directory**. The extension resolves one path and
   sees everything. It should resolve symlinks and de-duplicate by inode, or it will show
   each session once per worktree alias.

3. **A session's `cwd` changes mid-session.** `EnterWorktree` moves a session from the
   main checkout into a worktree, so the first line's `cwd` is the main checkout and later
   lines carry the worktree path. Worktree identity is the session's **latest** `cwd`, never
   its first. `cwd` also goes deeper than the worktree root
   (`.../PLAT-3138/apps/portal`), so matching is a **prefix match against known worktree
   roots**, not equality.

4. **The directory name is not reliable.** The dir named `…-worktrees-dylan-PLAT-3048`
   contains a session whose `cwd` is `…/worktrees/dylan/PLAT-3138`. Grouping must come
   from transcript `cwd`, never from the slug the file happens to sit under.

### Resolution

Discovery is **global, not workspace-scoped** — the user routinely runs sessions in other
repos and wants to see those swarms too. The workspace decides what is *selected*, not
what is *visible*.

```
scan ~/.claude/projects/*          → 25 real dirs (74 symlinked aliases skipped)
  newest .jsonl mtime per dir      → activity + liveness, stat only
group by repo, sort by recency     → the repo switcher
workspace folder → git common dir  → which repo is preselected
within a repo: latest cwd per session → worktree tabs
```

This costs nothing. A full stat-only scan of all 25 project dirs measures at **1 ms**, so
it can re-run on every refresh. The expensive part is parsing transcripts, and that stays
lazy — only the selected repo's visible sessions are read.

Being global also removes a failure mode rather than adding one: with workspace-scoped
discovery, a session that had moved into a worktree via `EnterWorktree` could resolve to a
project dir the workspace never looked at. Scanning everything and grouping by transcript
`cwd` sidesteps that entirely.

Opening the main checkout or any worktree still lands on the same repo, since both resolve
through `git rev-parse --git-common-dir`. A workspace that is not a git repo at all falls
back to no preselection — the switcher simply opens on the most recently active repo.

### Work that has been cleaned up

Deleting a branch or removing a worktree is the clearest statement available that a piece
of work is finished, and it is one the transcripts do not get: they stay for
`cleanupPeriodDays` (30) afterwards. Measured on this machine, **25 of the 49** retained
gridmatic-dev sessions were on branches that no longer exist — half the list was closed
tickets. Two rules, both answered by git rather than by guessing at path names:

- the session's worktree must still appear in `git worktree list`;
- the session's `gitBranch` must still appear in `git branch`.

A project directory is listed only when its path is inside a git work tree at all, which is
what removes `/private/tmp` and the per-session `…/scratchpad` directories from the repo
row — they are not repos, so no name-matching on "tmp" is needed.

Finding this exposed a grouping bug underneath. `worktreeRootFor` matched the longest
*known* root first and only fell back to the worktree path pattern, but the main checkout
is a path prefix of every worktree under it, so a **removed** worktree's cwd matched the
main root and its sessions were filed under `main` — which is precisely why deleted tickets
showed up where it was least expected. The pattern is now tried first, so a worktree path
identifies its own root whether or not git still knows it.

Both rules only apply when git answered: an empty `worktree list` or `branch` result means
the question could not be asked, and nothing is hidden on the strength of a failed
subprocess. Nothing is deleted either — `agentWatch.hideDeletedWork` turns the filter off,
and the status line always reports the count it hid, so the UI never silently shrinks.

The cost had to be paid down before it shipped. `reload()` runs on **every 2s poll**, so
asking git per repo per tick would have meant ~35 process spawns every two seconds against
the 1 the panel used before. `GitFacts` memoizes each answer per path for 15s and is
cleared by the explicit refresh, which takes a real refresh cycle to 7 spawns and the four
after it to zero.

---

## 5. UI

One editor webview tab, `Agent Watch`, opened by a command and restorable across reloads.

The main surface is a **node-and-edge graph**, not a collapsible outline. An edge means
*spawned by*, so the shape of a run is legible at a glance: which agent fanned out, how
wide, and how deep the nesting went.

```
  repo:  ▾ gridmatic-dev ●●●     (tlaloc-env ●  ·  Demeter  ·  5 more)
  tabs:    main ●     PLAT-3048 ●●     PLAT-2715     ftl-worker
  ─────────────────────────────────────────────────────────────────────

                                    ┌──────────────┐
                              ┌─────┤ review:bugs  │ ✓ 3 findings
                              │     └──────────────┘
   ┌───────────────┐    ┌─────┴────┐  ┌──────────────┐
   │ session       │────┤ wf_8a8d  ├──┤ review:perf  │ ✓ 0 findings
   │ 952ca67e   ● │    │ 11/16    │  └──────────────┘
   └───────────────┘    └─────┬────┘  ┌──────────────┐   ┌─────────────┐
                              └───────┤ verify:auth  ├───┤ Explore     │ ◐
                                      │ ◐ 0m18s      │   └─────────────┘
                                      └──────────────┘
```

- **The two scope rows are told apart by more than position.** Repo chips and branch chips
  started out identical pills on adjacent lines, which is legible only while neither row
  wraps — and both do, at any realistic panel width. Each row now carries a caption in a
  fixed left gutter (a two-column grid, so wrapped chips stay in their own block rather
  than flowing under the label), a hairline separates the rows, and repo chips are square
  and bold against the branch chips' pills. Checked by rendering the real stylesheet in
  headless Chrome at 380px, where each row wraps to three lines and still reads correctly.
- **Layout is a left-to-right layered tree.** Depth grows rightward, siblings stack
  vertically. This matters: a swarm is wide and shallow (16–27 siblings at depth 1), so
  breadth must land on the axis that scrolls naturally. Top-down would put 27 nodes
  side by side and force horizontal scrolling for the common case.
- **Layout comes from `d3-hierarchy`** (`tree()`), bundled via npm — a pure function from
  node tree to coordinates, with no DOM dependency, so it unit-tests directly. Rendering
  is hand-written SVG; no charting framework, no CDN (CSP would block it anyway).
- **Status is carried by the node itself** — border color plus a glyph, so it reads without
  clicking: `●` live (animated ring), `◐` running, `✓` done, `✗` error, dimmed for idle.
  Node label is `agentType` over `description` from the `.meta.json`.
- **A session node carries the title on its editor tab**, not its UUID. Claude Code writes
  the tab title into the transcript itself: `{"type":"ai-title","aiTitle":…}` for the one
  the model generates, `{"type":"custom-title","customTitle":…}` for one renamed by hand.
  Both are re-emitted throughout the run and **interleave** — a session renamed `PLAT-3138`
  still gets fresh `ai-title` lines after the rename — so last-line-wins would hand the
  model's guess back to someone who had already overruled it. The hand-set title therefore
  wins outright, and only within each kind does the newest line win. 505 of the 578 sessions
  touched in the last week carry one; the remainder (all but a handful being one session
  seen through 70 worktree symlinks) fall back to the first 8 characters of the UUID.
- **A session node opens its own chat.** `claude-vscode.editor.open` is undocumented past
  its title, but the extension calls it internally as
  `(sessionId, initialPrompt, viewColumn)` and its `createPanel` keys open panels by
  session id — so passing an id reveals that chat if its tab is still open and resumes it
  from the transcript if not. The prompt argument is passed as `undefined` deliberately:
  with one set, revealing an already-open session pops a "Your prompt was not applied"
  notice. Being a contributed command and not API, it is probed through
  `vscode.commands.getCommands(true)` first, since `executeCommand` on a missing id rejects
  with a raw `command 'x' not found`.

  The guard that matters is **cwd**. Claude Code resolves a resumed session's working
  directory from `workspaceFolders[0]`, not from the transcript, so resuming a session that
  ran in another repo would attach it to whatever this window has open — and agent-watch
  deliberately shows every repo on the machine. Those are refused with an offer to open the
  right folder in a new window. One accepted side effect: any column other than
  `ViewColumn.Active` makes the extension set its own preferred location to `panel`, and
  `Active` would open the chat on top of Agent Watch itself, so the preference is allowed
  to move — which is what asking for a tab means anyway.

  Geometry: the button sits bottom-right, mirroring the expand badge top-right. It clears
  the badge and the label row but does overlap the sublabel row, so `sublabelCapacity`
  takes it into account — the capacity helpers now take a `{ badge, open }` record and
  shorten a row only for the boxes that actually intersect it, which is asserted rather
  than assumed.
- **Click a node → modal** with that agent's full event stream: tool calls, arguments,
  results, text output, and thinking summary when present. The modal is where "a lot of
  information" lives, keeping the graph itself scannable — which is the whole point of
  choosing a graph over nested line items.
- **A row never occupies less than a third of the viewport.** Framing by fit alone caps at
  100%, which leaves one or two children as a couple of small boxes adrift on a large
  canvas — technically framed, practically still lost. The scale is therefore raised until
  the row covers at least `MIN_HEIGHT_FRACTION` (1/3) of the canvas height, bounded twice:
  never past `MAX_ZOOM` (4), the same ceiling the wheel stops at, and never so far that the
  box stops fitting *across*, which is what keeps a short wide tree from being magnified
  off both edges.

  A third bound exists because the first two were not enough: a row of one taken literally
  to a third of the viewport wants 5×, which is a single box filling the screen. The
  fraction is therefore computed against `max(row height, the height three nodes would
  take)`, so **three nodes is the most magnified anything ever gets** and shorter rows
  share that zoom rather than exceeding it. On a 1200×700 canvas every row of 1–3 lands at
  1.37 (9%, 21%, 33% of the height), 4 at 1.01, and 6 or more are already past a third at
  100% and left alone. `fitToView` runs through the same function, so a lone session node
  opens at 1.37× rather than marooned at 1× or blown up to 4×.
- **Expanding a node frames what it just revealed**, rather than refitting the whole tree.
  Refitting was the obvious thing and the wrong one: the point of clicking expand is the
  children, and a refit answers by zooming *out* until they are too small to read. The new
  view is scaled from the children's bounding box and centred on the wider box that reaches
  back to the parent, so the edge into the row stays visible — but only while that wider box
  still fits across; past that the parent is dropped and the children are centred alone,
  since the children are what the click asked for. Floored at the same 0.55 as `Fit`. Past
  that floor the row is anchored at its **top** instead
  of centred, so a 96-child expansion starts at the first child and scrolls down rather
  than dropping you in the middle of a row with no way to tell which end you are at.
  Collapsing reframes the same way, on the row the toggled node now sits in — its siblings,
  or every session when it is a root — so the view lands on the level you just stepped back
  out to. Holding the raw transform instead would drift, since the tree reflows underneath
  a collapse.

  The one asymmetry is what happens when the row will not fit. An expansion anchors to the
  row's top, because the first child is where you start reading. A collapse anchors to the
  **node you clicked**: collapsing one agent inside a 90-sibling row would otherwise throw
  the view to the top of that row and lose your place entirely. So `frameBox` takes an
  optional `anchor` — the sub-box to keep centred when the row overflows — and only the
  collapse path passes one.
- **Pan and zoom**, with a `Fit` control. The viewport refits automatically whenever the
  graph's *shape* changes — scope key plus node count plus dimensions — because a zoom
  level chosen for a 96-node run leaves a single-node session off-screen on an apparently
  blank canvas. Manual pan/zoom is preserved within a shape, and discarded when it changes.
- **The graph opens collapsed, by depth.** Width was the wrong rule: with every layer under
  the 12-child threshold, a real `gridmatic-dev` view expanded to **33 nodes at
  988x1348px**, which fit-to-view then shrank below readability. Depth is what controls
  size. `initialDepth` (default 1) expands each session and one level below it; the same
  view now opens at **3 nodes, 456x108px**, at full zoom. The width rule still applies
  within an expanded level.
- **Every node with children carries a count badge** (`▸90` / `▾90`) that expands or
  collapses that branch in place. Clicking the badge toggles; clicking the node body opens
  its detail. An explicit toggle always beats both default rules. The badge sits in the
  top-right corner, clear of the sublabel row — it was first placed vertically centred,
  where it sat directly on top of the second line of text. Its geometry and the resulting
  text capacities live in `nodeChrome.ts` as pure functions, with a test asserting the
  badge box does not intersect the sublabel row, so the overlap cannot silently return
  when a font size or node dimension changes.
- **Zoom is proportional, not per-event.** The first implementation applied a fixed 1.12x
  per wheel event, which is fine for a mouse and violent on a trackpad, where one gesture
  fires dozens of events. It now exponentiates the real pixel delta (normalizing line and
  page scroll modes), caps any single event at 8%, and treats a pinch — which arrives as
  ctrl+wheel — as a deliberate gesture that responds faster. The maths lives in `zoom.ts`
  as a pure function so the feel is unit-tested: 20 trackpad ticks must stay under 1.15x,
  and scrolling back must land exactly where it started.
- **Fit never shrinks past readability.** It clamps at 0.55 and anchors top-left when the
  graph is larger than the viewport, rather than scaling an arbitrarily large tree down to
  an unreadable smudge.
- **Nothing an agent said or a tool returned is truncated.** Text, thinking and tool
  output all reach the modal whole, with their newlines intact. A single `Bash` result can
  be hundreds of KB, so the cost is paid by *not rendering* rather than by cutting: each
  panel fills its `<pre>` the first time it is opened, so a closed panel costs nothing but
  its one-line header, and the host re-posts an open node's detail only when that node's
  content has actually changed (`detailRevision` in `panel.ts`) instead of on every poll.
  Only the one-line headers are clipped — node labels and the per-tool summary, where a
  single line is the whole point.
- **The conversation is open, the machinery is folded away.** Your prompts, the agent's
  prose and its thinking are all expanded on arrival, so a node reads as a transcript
  rather than a list of things to click. Tool arguments and output stay collapsed, as does
  injected context. A default-open panel longer than 20 lines or 1600 characters
  (`preview.ts`) shows that much with a **Show more** button carrying the exact count of
  what is held back — a reversible fold, never a cut, and the header above it always states
  the true size. Which panels the reader opened and which they expanded both survive the
  live re-render, keyed by event index and panel label.
- **Who said it is on the record.** A text event carries a `role`: your prompt renders as
  **you** with an accent rule down its left edge, the agent's prose as **said**, and a line
  the harness injected (`isMeta` — skill preambles, local-command caveats, image markers)
  as **context**, expanded by neither default nor accident. Before this, every one of them
  read "said". Two traps live here: a prompt's `content` is frequently a bare **string**
  rather than a block list, and `blocksOf` returning `[]` for that form meant most prompts
  never reached the view at all; and `isMeta` text is not something the user typed, so
  labelling it "you" would put words in their mouth.
- **A status bar entry** (`$(type-hierarchy) Agents`) opens the tab, or focuses it when it
  is already open. Priority is **110**, not an arbitrary number: status bar priority puts
  higher values further left on *both* sides, and claude-usage occupies 50–101 at its
  default (new-chat `priority + 1`, meters `priority - index`, freshness 50). Anything
  inside that span interleaves with its meters instead of sitting beside them.
- **Two levels of scope above the graph**: a repo switcher (all 25 project dirs, sorted by
  recent activity, live counts shown) and, under it, worktree tabs for the selected repo.
  The current workspace's repo is preselected but never limits what is reachable.
- Theme-aware via `var(--vscode-*)` tokens throughout, including the SVG strokes and
  fills. No hardcoded colors.

### Agent status, derived

- Workflow agents: `journal.jsonl` — `started` with no matching `result` → running.
- `Agent`-tool subagents: running until the parent transcript shows a `tool_result`
  carrying that agent's `toolUseId`.
- Sessions: live if the transcript's mtime is within 60s; otherwise idle or done.

No polling of agent processes, no PID tracking — purely derived from the files.

---

## 6. Architecture

```
src/
  extension.ts        activate, command registration, panel lifecycle
  workspace.ts        workspace folder → main checkout → slug → project dir
  worktrees.ts        git worktree list, cwd → worktree bucket (prefix match)
  discovery.ts        enumerate sessions + subagents, de-dup symlinked dirs by inode
  tail.ts             incremental JSONL reader (byte offset, partial-line carry)
  watch.ts            fs.watch + stat-poll fallback, debounced
  model.ts            transcript lines → Session / Agent / Event tree
  summarize.ts        per-tool one-line summaries (clipped; content never is)
  retention.ts        sweep planning + execution (see §7)
  panel.ts            webview host, postMessage protocol
  webview/
    graph.ts          d3-hierarchy layout → SVG nodes and edges
    modal.ts          per-agent event stream detail
    styles.css        var(--vscode-*) tokens only
  testing/
    vscodeStub.ts     the vscode surface activate() touches
```

Matching `tools/claude-usage/`: esbuild bundle to `dist/extension.js`, vitest, `tsc
--noEmit` typecheck. One runtime dependency — `d3-hierarchy` — bundled by esbuild, chosen
because it is pure math with no DOM coupling, which keeps the layout unit-testable and the
rendering ours.

### Tailing

Read forward from a stored byte offset per file; never re-read a file from the start.
Keep a partial-line buffer, since a write can land mid-line. A file whose size *shrinks*
was rewritten — reset the offset and reparse. On first open, seek backward for the last N
messages rather than parsing a 1.5 MB transcript in full.

### Watching

`fs.watch` on each target plus a **`stat` poll every 2s** (`agentWatch.pollSeconds`). Per
the repo rule, the poll is the guarantee and `fs.watch` is the optimization that is
allowed to do nothing — `make install` runs the test suite, so a test asserting inotify
delivered an event turns an install into a hard failure on a box where watches are
unavailable. The suite asserts the poll keeps the view current with the watch factory
stubbed to throw `ENOSPC`.

Two signature rules, both learned from failures rather than guessed:

- **Files** are `mtime:size`. **Directories** are `count:hash(sorted names)` — *not*
  mtime. Directory mtime is millisecond-truncated, so a file created in the same
  millisecond as the baseline reads as unchanged; that surfaced as a test failing 2 runs
  in 5 before the signature changed.
- **Every agent transcript is watched individually**, not just the directory holding it.
  A directory signature only moves when entries are added, removed or renamed, so an agent
  appending to its existing transcript — the main thing to watch during a swarm — would
  otherwise be invisible.

A native event is **not** trusted on its own: its listener re-runs the signature check and
calls back only if something really moved. On macOS `fs.watch` fires on a directory merely
being read, so the reload's own `readdir` calls made the watcher re-trigger itself — into a
300 ms debounce that resets on every call, which can starve indefinitely under a burst.
That is why refreshes looked erratic: they were driven by a feedback loop rather than by
the data. Treating the native event as a *hint to check* rather than as the change itself
makes `fs.watch` a true accelerator, which is what the repo rule says it has to be.

Cost is not a concern: a real 96-agent run yields 98 targets and one full poll measures
**0.5 ms**, a 0.027% duty cycle at the 2s interval.

### A file-change watcher cannot carry time-derived state

Watching files answers "has anything been written?". Two things the UI shows are not
answers to that question:

- **Liveness is a function of the clock.** A session is live while its transcript's mtime
  is under `liveWindowSeconds` old, so a session that *stops* being written has to change
  colour with nothing happening on disk. Under change-driven refresh alone it never did —
  it stayed green until some unrelated event forced a reload, which is exactly the "I have
  to click around between repo tabs" symptom.
- **Deleted branches and worktrees live in git, not in the transcripts.** Nothing under
  `~/.claude/projects` moves when a branch is deleted, so no watcher can notice.

So the panel runs its own heartbeat: a reload every `pollSeconds` while the tab is visible,
calling `reload()` directly rather than through the debounce, so an event storm can never
starve it. A full reload — rescan, reload the selected repo, relayout — measures **7 ms
warm**, and 16 ticks at the real 2s cadence against this machine's projects directory
measure a **2.2% duty cycle**. `GitFacts` keeps that honest: branch and worktree lists
expire after 15s, so a deleted branch leaves the UI within 15s, while whether a path is a
git repo at all is cached for 5 minutes, since it effectively never changes. Measured over
32s of polling, that is **9 git invocations total** — 5 one-off repo probes, then
`worktree list` and `branch` twice each.

### Polling only runs when someone is looking

Three guarantees, each covered by a test:

- **Nothing polls with the tab closed.** The watcher belongs to the panel; `onDidDispose`
  clears the interval and closes every native handle.
- **Nothing polls while the tab is hidden.** `retainContextWhenHidden` keeps the webview
  alive behind another tab, which would otherwise mean polling forever in the background.
  `onDidChangeViewState` stops the watcher when the panel goes invisible and restarts it —
  with one immediate refresh, so the view is never stale on return — when it comes back.
  Signatures survive the pause, so a change made while hidden is caught on resume rather
  than missed.
- **Timers cannot stack.** `start()` is a no-op while a timer exists, `startHeartbeat()`
  is a no-op while the heartbeat exists, and `show()` reveals the existing panel instead of
  constructing a second one, so repeated opens converge on a single watcher and a single
  heartbeat. Both stop on hide and on dispose.

### Performance

- Never load `subagents/` trees eagerly; a session's subagents are read when its node
  is expanded, or when it is live.
- Cap retained events per agent in memory (~2000, oldest dropped) with a "load earlier"
  control.
- Default to sessions touched in the last 7 days, with a control to widen.
- One extension host does the file I/O; the webview only receives deltas. Opening the
  tab in several windows means several tailers — acceptable, since each window scopes to
  its own workspace, unlike the shared-endpoint problem claude-usage had.

---

## 7. Retention — resolved, no code needed

`cleanupPeriodDays` is a real Claude Code setting — *"Number of days to retain chat
transcripts before automatic cleanup (default: 30)."* All three Demeter profiles had it
pinned to **3650** (ten years), which was not deliberate. It is now **30**.

### The sweep covers `subagents/` too

An earlier draft of this section proposed a two-tier policy keeping subagent transcripts
for a different period than session transcripts. **That was overcomplicated and is
dropped.** There is no reason to want a different retention period for the two; the only
real question was whether the built-in sweep reaches `subagents/` at all, or whether it
deletes a session's root transcript and strands its subagent tree forever.

It reaches them. The evidence is a natural experiment in the existing data:

- `cleanupPeriodDays: 3650` landed in Demeter on **2026-09-02** (commit `f4308ee`). Before
  that date the 30-day default was active.
- The oldest surviving transcript anywhere is **2026-07-28** — the record starts abruptly,
  exactly as it would if a 30-day sweep had been running and then stopped.
- A root-only sweep would therefore have left a large population of orphaned `subagents/`
  directories dated July and August, their roots deleted out from under them.
- Actual count: **86 of 87 subagents dirs still have their root transcript** (34 with roots
  older than 2026-09-02), and the single orphan is dated **2026-09-19** — after the sweep
  stopped, so it cannot be sweep debris.

Zero orphans from the window where the sweep provably ran. The sweep removes the session
directory along with the root transcript.

This is inference from absence rather than direct observation of the code — static
analysis of the 2.1.304 binary surfaced only the settings schema, and a sandboxed probe
via `CLAUDE_CONFIG_DIR` aborted at `Not logged in` because credentials live in the macOS
keychain and do not follow the config dir. But the natural experiment is strong, and the
cost of being wrong is visible: re-run the §2 `stat` measurement in a month, and if
`subagents/` has not fallen, revisit.

### What agent-watch does

Nothing. No sweep, no delete path, no trash handling, none of the symlink hazards that
came with it. The graph carries a passive footprint line — total size and the age of the
oldest transcript — so the number stays visible without the extension ever deleting
anything. Expected steady state at 30 days is roughly 450 MB rather than 1,056 MB.

---

## 8. Repo and install integration

- Lives at `tools/agent-watch/`, profile-independent, symlinked into `~/.claude/tools/`
  by installer step 9 like the other tools.
- `Makefile` with `setup` / `build` / `test` / `typecheck` / `check` / `link` / `package` /
  `install`, copied from `tools/claude-usage/Makefile`, including the `CODE ?=` resolution
  so `make install` works over Remote-SSH. Installer step 10 then offers the build.
- Publisher `dylanlarrabee`, id `dylanlarrabee.agent-watch`. `vscode/sync-extensions.sh`
  already excludes ids published from `tools/*/package.json`, so it stays out of
  `vscode/extensions.txt` automatically.
- `tsconfig.json` sets `"rootDir": "src"` explicitly beside `outDir` — TS 6 (what the
  editor's bundled tsserver uses) requires it, and without it the Problems tab shows a
  diagnostic that `npm run typecheck` never reproduces.
- `src/testing/vscodeStub.ts` must cover the entire `vscode` surface `activate()` touches,
  and `activate()` must `.catch()` its background promises. A missing stub property throws
  inside fire-and-forget work and surfaces as a vitest *unhandled error*: every test passes,
  the process exits non-zero, and `make install` fails with nothing obviously wrong.
- Nothing runnable ships in git — `node_modules/`, `dist/`, `*.vsix` ignored by the tool's
  own nested `.gitignore`.
- No agent-written code comments, per `.claude/CLAUDE.md`.

---

## 9. Milestones

**M1 — read-only snapshot.** Global discovery scan, enumerate sessions and
subagents, build the tree, render it as a static graph in a webview. No watching. Proves
the data model, the worktree grouping, and the layout under a real 27-node fan-out.

**M2 — live.** Incremental tailing, stat-poll + `fs.watch`, delta messages to the webview,
status glyphs, auto-expand of live nodes.

**M3 — legible.** Node detail modals, per-tool summaries, truncation with expand, worktree
tabs with badges, pan/zoom and fit-to-view, wide-fan-out grouping, theme tokens.

**M4 — fit and finish.** Done, minus two items that turned out to need nothing:

- The modal now **follows the tail**. An open node's detail is re-pushed on every refresh,
  the body sticks to the bottom as events arrive, scrolling up unsticks it, and a
  `↓ Jump to latest` pill re-sticks. Open `<details>` panels and scroll position survive a
  refresh, so expanding an output does not get undone two seconds later.
- Panel restore via `registerWebviewPanelSerializer`, scope-aware empty states.
- **No retention sweep** — §7 resolved that to a settings change, already made.
- **No installer change.** Step 10 is generic: `tool_has_install_target` looks for a
  Makefile `install:` rule and `run_tool_install` uses `mise exec` when a `.mise.toml` is
  present. agent-watch has both, so it is picked up with no edit to `install.sh`.

Not done: "copy agent prompt" or "reveal transcript" actions. A `Reveal transcript` button
was built and then removed — nobody opens a raw JSONL from here, and keeping it meant
carrying a node-id-to-file map through the loader, store and protocol for one unused
button.

M1–M2 is the point at which it is worth using daily; M3 is the point at which it beats
`wfwatch` outright.

---

## 10. Open questions

1. **Does `wfwatch` stay?** It costs nothing to keep, and it works over plain SSH where
   the extension does not. Recommendation: keep it, stop advertising it in the skills once
   M3 lands.
2. **Should the skills print a clickable `agent-watch` link** next to the run ID, the way
   they print the `wfwatch` command today? Cheap, and it closes the loop between launching
   a swarm and watching it. Needs a URI handler.
3. **Is a sidebar tree view wanted in addition to the editor tab?** The editor tab is what
   was asked for and is the better surface for this much content. A sidebar view is a
   plausible M5 for at-a-glance liveness without giving up an editor column.
4. **Retention — resolved enough to defer.** The 3650 was accidental. Fix the number,
   measure whether the built-in sweep covers `subagents/` (§7), and only then decide
   whether agent-watch keeps its own sweep. Gates M4 only.
5. **Multi-root workspaces** are now a non-issue: discovery is global (§4), so several
   folders simply mean several repos already present in the switcher, with the first
   folder's repo preselected.
6. **~~The fan-out is flat~~ — RESOLVED in M3, and it needed no skill change.** The plan
   was to have the workflow-authoring skills emit stage markers. They already do:
   `review-code`, `review-kludge` and `changes-description` all declare `meta.phases` and
   pass `phase:` + `label:` on every `agent()` call, identically across all three profiles,
   and the harness persists both into the run manifest. The gap was purely that
   agent-watch was not reading it. The 96-agent run now bands into Review (6) and
   Verify (90), and with wide layers collapsed it lays out at 988x1162px instead of
   988x5936px — 23 nodes instead of 100.
7. **~~Modals render everything inline~~ — RESOLVED in M3.** Arguments and output are
   behind `<details>` toggles labelled with their size, collapsed by default.
8. **~~Prose was buried behind a toggle~~ — RESOLVED.** An agent's own text is the one
   thing worth reading without a click, so `said` panels open by default while arguments
   and tool output stay collapsed.
9. **~~Empty thinking blocks read as a bug~~ — RESOLVED.** `0 chars withheld by the API`
   told the user nothing and looked broken. They now render as `thought · not recorded`.
   The underlying fix is opt-in: `vscode/claude-wrapper.sh` launches Claude Code with
   `--thinking-display summarized` so the field is populated at the source (see the
   repo README). Verified end to end through the wrapper: 270 characters of real summary
   persisted to the transcript.
10. **~~The modal was a dead snapshot~~ — RESOLVED in M4.** It did not update as new
   events landed, and reading the newest entry meant scrolling the whole history. The
   panel now re-pushes the open node's detail on every refresh and the view tails the
   bottom by default; scrolling up unsticks it and raises a `↓ Jump to latest` pill. The
   subtlety worth keeping: a naive re-render would collapse every open `<details>` and
   reset scroll on each 2s tick, so the renderer records which panels are open and
   restores both.
