# skills/ — Agent Instructions

## Structure

Each skill is a subdirectory containing a `SKILL.md` file that defines the skill's behavior. Skills are symlinked into `~/.claude/skills/` by `install.sh` and become available as slash commands in Claude Code.

## Current Skills

| Skill | Purpose |
|---|---|
| `changes-branch` | Load branch context |
| `changes-description` | Adversarial four-persona debate (senior / skimmer / novice / AI-slop hawk) that converges on an MR description, then fact-checks it against the diff (uses the Workflow tool; prints a `wf_…` run ID to watch live with `wfwatch <id>`) |
| `changes-explain` | MR change breakdown |
| `commit-msg` | Generate commit messages |
| `docs-update` | Audit and update README.md and AGENTS.md to reflect current repo state |
| `fix-feedback` | Work through review feedback — MR/PR threads or a local review agent's output |
| `fix-linear` | Linear ticket implementation |
| `plan-initiative` | Sequence a Linear initiative's subtasks and delegate them across named engineers — dependency graph, parallelism verdict, swimlane chart, per-person work orders |
| `plan-subtasks` | Turn a design doc + implementation breakdown into a Linear ticket tree — one parent, one MR-sized subtask per reviewable slice, both doc links on every ticket; confirms team/project/assignee and writes to Linear only after the plan is approved |
| `reflect-peer` | Peer assessment generator (stub) |
| `reflect-self` | Self-assessment generator (stub) |
| `reflect-week` | Generate weekly engineering snippets |
| `review-code` | Adversarial multi-agent review of proposed local changes, or of an incoming branch someone else pushed — the latter is fetched into a detached review worktree and comes back with a pack of ready-to-paste review comments (uses the Workflow tool; prints a `wf_…` run ID to watch live with `wfwatch <id>`) |
| `review-kludge` | Adversarial swarm that reviews recent large features for accumulated kludge/AI-slop and proposes refactors (uses the Workflow tool; prints a `wf_…` run ID to watch live with `wfwatch <id>`) |

## Worktrees

`fix-linear` and `fix-feedback` isolate each fix in its own git worktree by default (under `.claude/worktrees/<branch>`), entered via the `EnterWorktree` tool, so multiple non-blocking fixes can run in parallel — one session per worktree. They offer to install dependencies in the fresh worktree and leave cleanup manual (`git worktree remove`). Pass `in place` / `--here` / `no worktree` in the skill argument to fall back to an in-place checkout. `commit-msg` and `changes-description` operate on the current directory and need no worktree awareness. `review-code` does too in its default local mode, but when handed an incoming branch it creates a **detached** review worktree at `.claude/worktrees/review/<branch>` — never checking their branch out over yours — and leaves removal to you. Full guide: `WORKTREES.md` at the repo root.

## GitLab Data

MR-related skills (`explain`, `mr-description`, `feedback`, `eng-snippet`) use `~/.claude/scripts/gitlab-api.sh` for all GitLab API access. The script reads the GitLab token from `~/.claude/.mcp.json` so tokens never enter conversation context.

## User Data

Some skills accumulate context data that is NOT tracked in git:
- `eng-snippet/slack-context.md` — ephemeral Slack threads pasted before each run
- `performance-review-self/context/` — weekly self-reports
- `performance-review-peer/context/` — per-peer collaboration profiles
- `performance-review-*/prompts.md` — review questions pasted per cycle
- `plan-initiative/team.md` — team roster (seniority, specialties, ramp areas, capacity); `team.example.md` is the tracked template

These files are gitignored. The install script creates necessary directories.

## Adding a New Skill

1. Create a new directory: `<skill-name>/`
2. Add a `SKILL.md` file defining the skill's prompt and behavior
3. If the skill needs helper scripts, add them to `../scripts/`
4. Run `./install.sh` from the repo root to symlink it
5. Update this file with the new skill entry

**If the skill writes or edits code, restate the no-comments rule in its `SKILL.md`.**
`~/.claude/CLAUDE.md` (from `.claude/CLAUDE.md` in this repo) forbids agent-written code
comments in every repository, but a skill's subagents receive only the skill's own prompt
— they never see the user's `CLAUDE.md`. A skill that leaves the rule implicit will have
its subagents comment freely. Copy the wording from `fix-linear`'s Step 5.
