# Global Instructions

These apply in every repository, on top of any project-level `CLAUDE.md` or `AGENTS.md`.

## Do not add comments to code

Write no comments in code you create or change. That means no explanatory comment, no
banner or section divider, no preamble above a function, no docstring on a symbol that
did not already have one, no note about why the change was made or what it replaced, no
`TODO`, and never commented-out code.

The reason is that a comment written next to the code it describes almost always restates
the line, goes stale on the next edit, and pads the diff — a reviewer has to read it and
decide whether to trust it before they can get to the change itself. Explanation belongs
in the commit message, the MR/PR description, and the review thread, where the people who
need it read it once.

In practice:

- **Make the code not need the comment.** A clearer name, an early return instead of a
  nested branch, a small named function instead of a labelled block. Wanting to explain a
  line is a signal to rewrite the line, not to annotate it.
- **Leave existing comments alone.** They are somebody else's decision and not yours to
  tidy up. One exception: when your change makes an existing comment untrue, correct it or
  delete it — never leave a comment lying about the code beneath it.
- **Machine-read comments are program input, not commentary — write them normally.**
  Linter and type-checker directives (`//nolint`, `# noqa`, `# type: ignore`,
  `eslint-disable`), build and compiler pragmas (`//go:build`, `//go:generate`,
  `#pragma`), codegen markers, shebangs, license headers the repo requires, and
  annotations a tool parses. So is a doc-comment that CI fails without — write the
  shortest one that passes.
- **An explicit request wins.** If asked for a comment, or for documented or annotated
  code, write it — for what was asked and nothing further.

None of this reduces how much you explain. Explain in the response, the commit message,
and the description, at whatever length is useful there.

## Spawn subagents freely

Standing instruction, and it overrides any session default to the contrary: **use the Agent
tool whenever work genuinely parallelises, without asking first.** Independent reviews,
searches across unrelated areas, and per-file or per-dimension passes should fan out rather
than run one after another.

The reason is that the fan-out is observable here. `tools/agent-watch/` renders every
subagent as a live node under the session that spawned it, with the path from a working
agent back to its session drawn in green, so a swarm is something to watch rather than
something opaque. Exploring sequentially to avoid spawning buys nothing in exchange.

This covers the Agent tool only. The **Workflow** tool is a different scale — it can launch
dozens of agents in one run — so it keeps its own opt-in and should still be offered rather
than assumed.

Two things a spawned agent does not inherit, so put them in its prompt:

- **This file.** A subagent gets the prompt it is given, not the user's `CLAUDE.md`, so the
  no-comments rule above has to be restated to any agent that writes or edits code.
- **"Read-only" has to name the repo.** An agent told only to review read-only has still
  written test files into the working tree. Say explicitly that it must not create, edit or
  delete anything under the repo, give it a scratch directory, and tell it to clean up.

Ask first only when the work is destructive, touches external state, or when the number of
agents is itself the question.
