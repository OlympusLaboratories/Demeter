# agent-watch

A VS Code extension that shows, as a node-and-edge graph, what every Claude Code session
on this machine is doing — including the subagents each one spawns, whether through the
`Agent` tool or a `Workflow` swarm.

It reads the JSONL transcripts Claude Code already writes under `~/.claude/projects`.
Nothing is launched, steered, or deleted; the extension is strictly a reader.

See [DESIGN.md](DESIGN.md) for why it works the way it does — the data on disk, the
worktree scoping rules, and what is deliberately out of scope.

## Status

**M1 + M2.** Global discovery, session and subagent enumeration, the graph, a per-node
detail modal, and **live updating** — transcripts are tailed incrementally and the view
refreshes itself as agents work. `Agent Watch: Refresh` forces a rescan.

Outstanding: M3 (node detail collapsing, pan/zoom, wide-fan-out grouping) and M4 (polish).

## Use

- `Agent Watch: Open` — opens the graph in an editor tab.
- `Agent Watch: Refresh` — rescans.

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

## Thinking text

Thinking blocks are usually empty on disk — the API returns them that way, since
`thinking.display` defaults to `"omitted"`. The graph shows those as a withheld marker
with a character count rather than pretending nothing happened.

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
