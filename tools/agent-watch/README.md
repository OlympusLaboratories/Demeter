# agent-watch

A VS Code extension that shows, as a node-and-edge graph, what every Claude Code session
on this machine is doing — including the subagents each one spawns, whether through the
`Agent` tool or a `Workflow` swarm.

It reads the JSONL transcripts Claude Code already writes under `~/.claude/projects`.
Nothing is launched, steered, or deleted; the extension is strictly a reader.

See [DESIGN.md](DESIGN.md) for why it works the way it does — the data on disk, the
worktree scoping rules, and what is deliberately out of scope.

## Status

**M1–M3.** Global discovery, session and subagent enumeration, the graph, **live
updating** (transcripts are tailed incrementally as agents work), **phase banding** of
workflow runs, collapsing of wide layers, pan/zoom, and a node detail modal that reads as
a conversation — your prompts, the agent's prose and its thinking open, tool arguments and
output collapsed until asked for. `Agent Watch: Refresh` forces a
rescan.

**M4.** The detail modal follows live output and the tab survives a window reload.

## Use

- **`$(type-hierarchy) Agents` in the status bar** — opens the graph, or focuses the tab
  if it is already open.
- `Agent Watch: Open` — the same thing from the command palette.
- `Agent Watch: Refresh` — forces a rescan.

The view refreshes every `pollSeconds` while the tab is visible, whether or not anything
was written. That matters for the two things a file watcher cannot see: a session going
**stale** (liveness is a function of the clock, so a session that stops being written has
to change colour with nothing happening on disk) and a **branch or worktree you deleted**
(nothing under `~/.claude/projects` moves when you delete one — it leaves the view within
15s, when the cached git answer expires). A full refresh costs 7ms, about a 2% duty cycle.

Polling runs **only while the tab is visible**. Closing it, or switching to another tab,
stops both the watcher and the heartbeat; returning restarts them with an immediate
refresh. Opening Agent Watch repeatedly reveals the one tab rather than stacking panels or
timers.

Node detail **follows the tail**: new events append as they land and the view stays at the
bottom. Scroll up and it unsticks, with a `↓ Jump to latest` pill to re-follow. Panels you
expanded stay expanded across refreshes.

**The modal reads top to bottom as a conversation.** Your prompt (**you**, with a rule down
its left edge), the agent's reply (**said**) and its thinking (**thought**) all arrive
expanded; tool arguments, tool output and harness-injected **context** arrive folded. None
of it is ever truncated — a long open panel shows its first 20 lines with a **Show more**
button naming exactly how much is held back, and the header above it always reports the
real size.

**Status comes from each node's own transcript**, not from its parent. `●` green means the
transcript was written within the last `liveWindowSeconds` — it is working right now. `◐`
blue means launched and not yet returned but currently quiet, such as an agent waiting on a
long command. `✓` grey means finished. A background agent's `tool_result` arrives within
milliseconds of launch, so judging it by the parent marked it done while it still had
minutes of work left.

**The whole path from a working agent to its session is green**, edges included. A node
with a working descendant is shown as working, because a grey `✓` on it would be a lie
about the subtree underneath. A failure stays visible — `error` is never painted over, and
never propagates upward either.

**A node expands itself the first time it gains children**, so agents appearing under a
node you are watching show up without a click. Only the first time: more children arriving
later leave the expansion alone, and a branch you collapsed by hand stays collapsed. A tree
that already had children when you opened the panel does not spring open either — unless
something in it is **live**, which is the one case you opened the panel for.

**The graph opens collapsed and you expand into it.** By default you see each session and
one level below it — typically a handful of nodes — with a count badge on anything that has
children (`▸90`). Click a badge to open that branch; click again to shut it. Nothing
expands itself.

A workflow run bands into its declared phases, so opening a 96-agent `review-code` run
gives Review (6) and Verify (90) rather than 96 siblings.

Expanding frames what you just opened, rather than refitting the whole tree — the point of
clicking a badge is the children, and a refit answers by zooming out until they are too
small to read. The revealed row is centred and scaled to its full height, and never allowed
to occupy less than a **third of the viewport** — with a ceiling of however much a
**three-node row** gets, so a row of one or two shares that zoom instead of a single box
filling the screen. Anything already larger than a third is left at its natural size, and
nothing is ever magnified so far that it stops fitting across, so a short wide tree cannot
be blown off both edges.

Collapsing reframes the same way, on the row the node now sits in — its siblings, or every
session when it is a root — so you land on the level you stepped back out to. The one
asymmetry is what happens when a row will not fit at the minimum zoom: an expansion anchors
to the row's **top**, since the first child is where you start reading, while a collapse
keeps the **node you clicked** centred, so collapsing one agent inside a 90-sibling row
does not throw you to that row's start.

Drag to pan (without selecting the labels you drag over), scroll to zoom, `Fit` to
reframe. Zoom tracks how far you actually scrolled
rather than stepping a fixed amount per wheel event, so a trackpad gesture nudges it
instead of flinging it; pinch responds faster than a scroll, and one huge delta can never
jump more than 8%. Tune it with `agentWatch.zoomSensitivity`, or set it to `0` to turn
wheel zoom off and use the `+`/`−` buttons. The view refits itself whenever the graph's
shape changes, so switching from a large run to a single session does not leave you panning
around an apparently blank canvas.

**Every session node carries an `↗` button** in its bottom-right corner that opens that
chat. If the session's tab is still open it is revealed rather than duplicated; if not, it
resumes from its transcript. A session that ran outside this window's workspace is refused
rather than resumed — Claude Code would attach it to the folder this window has open, not
the one it actually ran in — with an offer to open the right folder in a new window
instead.

Each session node is named by the title on its Claude Code tab — the one the model wrote,
or the one you typed over it — not by its UUID.

Arriving at a tree opens the path down to whatever is **live** in it, however deep — a
transcript being written right now, not merely an agent that was launched and never
reported back, since that claim can outlive the work by weeks. A wide band of live agents
still stays collapsed rather than flooding the canvas, drawn green with its badge so you
can see where to click. A collapse you made by hand still wins, and
the expansion closes again when the work stops.

The top row picks a repo, the second row a branch within it. The repo this window has open
is pinned first and marked with a dot. The two are told apart by
more than position, because both wrap: each row carries a caption in a fixed left gutter,
they are separated by a hairline, and repo chips are square and bold against the branch
chips' pills. Wrapping stays inside its own block, so the caption on the left always says
which kind you are looking at. The repo for the current
workspace is preselected, but every repo on the machine is reachable — sessions that ran
elsewhere are visible without reopening VS Code. Click any node for its full event stream.

**Work you have cleaned up stays hidden.** Deleting a branch or removing a worktree is the
clearest signal there is that you are done with it, but its transcripts live on for
`cleanupPeriodDays` afterwards. So a session is listed only while the worktree it ran in is
still in `git worktree list` and the branch it ran on still exists, and a project directory
is listed only when it is inside a git repository at all — which is what keeps scratchpad
and `/tmp` directories out of the repo row. The status line reports the count it hid, and
`agentWatch.hideDeletedWork` turns the whole filter off. Nothing is deleted: this is a
display filter, and git is the authority, so a repo git cannot answer for is left alone
rather than emptied.

Depth runs left to right and siblings stack vertically, because swarms are wide and
shallow: a real 96-agent run lays out 722px wide by 5936px tall, so breadth scrolls
instead of overflowing.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `agentWatch.projectsDir` | `""` | Override the projects directory. Empty resolves `CLAUDE_CONFIG_DIR`, then `~/.claude/projects`. |
| `agentWatch.liveWindowSeconds` | `60` | A transcript written this recently counts as live. |
| `agentWatch.recentDays` | `7` | Only sessions touched this recently are listed. |
| `agentWatch.maxSessionsPerRepo` | `12` | Most recent sessions loaded per repo. |
| `agentWatch.pollSeconds` | `2` | How often watched transcripts are re-stat'd. This poll is the guarantee; native file watching is only an accelerator. |
| `agentWatch.zoomSensitivity` | `1` | Multiplier for scroll-wheel zoom. Lower is gentler; `0` disables it. |
| `agentWatch.initialDepth` | `1` | Levels below each session expanded on first render. `0` shows sessions alone. |
| `agentWatch.hideDeletedWork` | `true` | Hide sessions whose git worktree or branch no longer exists, and project directories outside any git repository. The status line reports how many were hidden. |
| `agentWatch.statusBarPriority` | `110` | Higher numbers sit further left within the right-hand group. The default clears claude-usage, which spans 50–101 at its own default priority, so the two tools' items stay grouped rather than interleaved. |

## Thinking text

Thinking blocks are usually empty on disk — the API returns them that way, since
`thinking.display` defaults to `"omitted"`. Those render as `thought · not recorded`.

To populate them, launch Claude Code through `vscode/claude-wrapper.sh` (see the repo
README) — it adds `--thinking-display summarized` when the installed build supports it.
Summaries then persist to the transcript and render here with no change to this extension.

Launching Claude Code with `--thinking-display summarized` makes the API return a readable
summary, which then persists to the transcript and renders here with no change to this
extension. The raw chain of thought is never available on any model. That flag is
undocumented and its accepted values have changed between releases — see §3 of DESIGN.md.

## Develop

Requires node 22 (pinned in `.mise.toml`).

```sh
make setup      # npm install
make check      # typecheck + tests + build
make link       # symlink into ~/.vscode/extensions, then reload the window
make unlink     # remove the symlink
make install    # package a vsix and install it
```

Tests are pure and machine-independent on purpose: nothing in the suite reads the real
`~/.claude/projects`, so `make install` cannot fail because of what happens to be on disk.
