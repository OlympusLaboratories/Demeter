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
workflow runs, collapsing of wide layers, pan/zoom, and a node detail modal whose
arguments and output stay collapsed until asked for. `Agent Watch: Refresh` forces a
rescan.

**M4.** The detail modal follows live output and the tab survives a window reload.

## Use

- **`$(type-hierarchy) Agents` in the status bar** — opens the graph, or focuses the tab
  if it is already open.
- `Agent Watch: Open` — the same thing from the command palette.
- `Agent Watch: Refresh` — forces a rescan.

Polling runs **only while the tab is visible**. Closing it, or switching to another tab,
stops the watcher; returning restarts it with an immediate refresh. Opening Agent Watch
repeatedly reveals the one tab rather than stacking panels or timers.

Node detail **follows the tail**: new events append as they land and the view stays at the
bottom. Scroll up and it unsticks, with a `↓ Jump to latest` pill to re-follow. Panels you
expanded stay expanded across refreshes.

**The graph opens collapsed and you expand into it.** By default you see each session and
one level below it — typically a handful of nodes — with a count badge on anything that has
children (`▸90`). Click a badge to open that branch; click again to shut it. Nothing
expands itself.

A workflow run bands into its declared phases, so opening a 96-agent `review-code` run
gives Review (6) and Verify (90) rather than 96 siblings.

Drag to pan, scroll to zoom, `Fit` to reframe. Zoom tracks how far you actually scrolled
rather than stepping a fixed amount per wheel event, so a trackpad gesture nudges it
instead of flinging it; pinch responds faster than a scroll, and one huge delta can never
jump more than 8%. Tune it with `agentWatch.zoomSensitivity`, or set it to `0` to turn
wheel zoom off and use the `+`/`−` buttons. The view refits itself whenever the graph's
shape changes, so switching from a large run to a single session does not leave you panning
around an apparently blank canvas.

The top row picks a repo, the second row a worktree within it. The repo for the current
workspace is preselected, but every repo on the machine is reachable — sessions that ran
elsewhere are visible without reopening VS Code. Click any node for its full event stream.

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
