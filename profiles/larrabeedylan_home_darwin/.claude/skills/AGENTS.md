# skills/ — Agent Instructions

## Structure

Each skill is a subdirectory containing a `SKILL.md` file that defines the skill's behavior. Skills are symlinked into `~/.claude/skills/` by `install.sh` and become available as slash commands in Claude Code.

## Current Skills

| Skill | Purpose |
|---|---|
| `changes-branch` | Load branch context |
| `changes-description` | Adversarial four-persona debate (senior / skimmer / novice / AI-slop hawk) that converges on a PR description, then fact-checks it against the diff (uses the Workflow tool; prints a `wf_…` run ID to watch live with `wfwatch <id>`) |
| `changes-diagram` | Turns the branch's diff into an interactive call-flow page — each changed function a box with its +/- lines, grouped into module boxes, with new and dropped calls and a click-through review walk. Falls back to a file/module graph on non-Python branches, so a non-empty diff never yields an empty chart. Publishes to whichever artifact store `skill-env.sh` names |
| `changes-explain` | Change breakdown (diff explainer) |
| `commit-msg` | Generate commit messages |
| `docs-humanize` | Adversarial five-persona swarm (archivist / skimmer / newcomer / slop hawk / doer) that rebuilds an AI-written Notion page, markdown file or Linear ticket into something a human reads once and acts on — builds a fact ledger first, then proves against it that nothing real was lost and nothing was invented (uses the Workflow tool; prints a `wf_…` run ID to watch live with `wfwatch <id>`) |
| `docs-update` | Audit and update README.md and AGENTS.md to reflect current repo state |
| `fix-autonomous` | Drives a ticket or a freeform statement all the way to a merged PR with no gates: implements, commits, describes, pushes, opens the PR, watches the pipeline and the review bot with `Monitor`, works the review clean, applies infrastructure plans, merges stacked changes in order, and pings you when done or stuck |
| `fix-feedback` | Work through review feedback — MR/PR threads or a local review agent's output |
| `fix-freeform` | `fix-linear` without a ticket — implements a freeform problem statement. Defaults to the repo's default branch, a one-shot description and no diagram; escalates to a feature branch on its own when the change touches Terraform, the default branch is protected, or the tree has unrelated uncommitted work |
| `fix-linear` | Linear ticket implementation |
| `ping` | Send yourself a push notification carrying what this session is doing and what it needs. Invoked directly, or by another skill handing over a status, a question, a blocker or a finished run |
| `plan-initiative` | Sequence a Linear initiative's subtasks and delegate them across named engineers — dependency graph, parallelism verdict, swimlane chart, per-person work orders |
| `plan-subtasks` | Turn a design doc + implementation breakdown into a Linear ticket tree — one parent, one MR-sized subtask per reviewable slice, both doc links on every ticket; confirms team/project/assignee and writes to Linear only after the plan is approved |
| `reflect-peer` | Peer assessment generator (stub) |
| `reflect-self` | Self-assessment generator (stub) |
| `review-code` | Adversarial multi-agent review of proposed local changes, or of an incoming branch someone else pushed — the latter is fetched into a detached review worktree and comes back with a pack of ready-to-paste review comments (uses the Workflow tool; prints a `wf_…` run ID to watch live with `wfwatch <id>`) |
| `review-kludge` | Adversarial swarm that reviews recent large features for accumulated kludge/AI-slop and proposes refactors (uses the Workflow tool; prints a `wf_…` run ID to watch live with `wfwatch <id>`) |
| `workflow-resume` | Rescue a `Workflow` swarm that died mid-run — diagnoses why (spend limit, kill, API errors), then either resumes it from the on-disk agent cache or harvests the finished agents' results |

## Worktrees

`fix-linear`, `fix-freeform` (when it escalates to `--branch new`) and `fix-feedback` isolate each fix in its own git worktree by default (under `.claude/worktrees/<branch>`), entered via the `EnterWorktree` tool, so multiple non-blocking fixes can run in parallel — one session per worktree. They offer to install dependencies in the fresh worktree and leave cleanup manual (`git worktree remove`). Pass `in place` / `--here` / `no worktree` in the skill argument to fall back to an in-place checkout. `commit-msg` and `changes-description` operate on the current directory and need no worktree awareness, and `docs-humanize` touches no checkout at all unless its target is a file path. `review-code` does too in its default local mode, but when handed an incoming branch it creates a **detached** review worktree at `.claude/worktrees/review/<branch>` — never checking their branch out over yours — and leaves removal to you. `fix-autonomous` creates no worktree of its own — it inherits whichever one the fix skill it delegated to set up, and owns that single branch for the whole run. Full guide: `WORKTREES.md` at the repo root.

## Workflow Runs

`changes-description`, `docs-humanize`, `review-code`, and `review-kludge` orchestrate swarms through the **Workflow** tool. Each run leaves a manifest, a script snapshot, and a `journal.jsonl` agent cache under `~/.claude/projects/<slug>/<session>/`. All four **launch and yield**: the tool returns a `wf_…` run id immediately, the skill prints it with the `wfwatch` command, ends the turn, and resumes on the run's completion notification. None of them may hold the session open waiting on a swarm — no `TaskOutput`, `Monitor`, `ScheduleWakeup`, or polling — so the user keeps a free prompt line for the whole run. `workflow-resume` reads all of it through `~/.claude/scripts/workflow-runs.py` (`list`, `show`, `args`, `script`, `link`, `merge`, `harvest`).

Two facts those four skills depend on: a workflow reports `completed` even when agents died mid-run (`agent()` returns `null`, the script carries on), and the resume cache is a **prefix** — a hash chain over agent calls that stops replaying at the first agent with no recorded result. Neither is visible from the report a swarm prints.

## GitHub Data

PR-related skills (`changes-explain`, `changes-description`, `fix-feedback`, `reflect-week`) use `~/.claude/scripts/github-api.sh` for GitHub API access. It reads the token from `GITHUB_PERSONAL_ACCESS_TOKEN` in the environment, so it never enters conversation context, and takes owner, repo, and PR number as plain arguments.

`fix-feedback` is the only one that **writes** through it, and both writes are gated on an explicit yes in chat: Step 3b opens one new comment per unique review-swarm finding (`create-diff-comment` — body over stdin; anchors to the diff line, retrying as a file-level and then a general comment when GitHub rejects the anchor), and Step 7b replies into an existing thread (`reply-to-thread`). `pr-for-branch` finds the PR when only the branch is known — its arguments accept `-` to derive owner and repo from `origin` and the branch from `HEAD`. Note that `create-diff-comment` returns a REST comment id, not the GraphQL thread ID `reply-to-thread` needs; re-run `pr-reviews` to pick that up.

## User Data

Some skills accumulate context data that is NOT tracked in git:
- `eng-snippet/slack-context.md` — ephemeral Slack threads pasted before each run
- `performance-review-self/context/` — weekly self-reports
- `performance-review-peer/context/` — per-peer collaboration profiles
- `performance-review-*/prompts.md` — review questions pasted per cycle
- `plan-initiative/team.md` — team roster (seniority, specialties, ramp areas, capacity); `team.example.md` is the tracked template

These files are gitignored. The install script creates necessary directories.

## Skill Environment

Nothing in a skill may hardcode the forge, the AI reviewer's username, the infrastructure
bot, or the artifact store. Those differ between the work profiles (GitHub, a self-hosted store) and work (GitLab, Claude
Artifacts, a self-hosted store), and a skill that bakes one machine's
answer in fails silently on the other — grepping for the wrong bot username finds no
threads and reports a clean review.

`~/.claude/scripts/skill-env.sh` is the seam. It carries this profile's defaults **in its
own code** and merges `~/.claude/environment.json` over them, so a missing or malformed
config degrades to working defaults instead of breaking a run.

```bash
~/.claude/scripts/skill-env.sh check          # everything a skill will see
~/.claude/scripts/skill-env.sh get review_bots
```

**An empty value means the capability is absent on this machine, never "guess at it".**
Empty `review_bots` means treat every non-operational bot thread as real feedback; empty
`iac_bot` disables the apply-before-merge gate; empty `review_job` means a review cannot be
re-triggered and the skill must say so rather than retry something that does not exist.

A skill added here that touches the forge, a reviewer, or an artifact store reads these
values rather than naming anything. The example file is committed; the real one is seeded
by the installer and never overwritten.

## Autonomous Runs

`fix-autonomous` composes the ordinary skills rather than reimplementing them: `fix-linear`
or `fix-freeform`, then `commit-msg`, `changes-description`, `fix-feedback --autonomous`,
`changes-diagram` and `ping`. Three invariants it must never lose:

- **It waits with the `Monitor` tool, never a sleep or a poll loop.** Several runs may be
  live at once and each blocking one costs a session. Every terminal state must emit a
  line — a watcher that reports only success stays silent through a crashloop, and silence
  is indistinguishable from "still running".
- **Review comments outrank CI.** Fixing comments means pushing, and a push restarts the
  pipeline, so handling CI first throws away a whole run.
- **It supersedes `fix-linear`/`fix-freeform` Important Rule 1** (never push, never open a
  pull request) for the one branch it created, and for nothing else. That carve-out is
  written into `fix-autonomous` explicitly; it is not something an agent may infer.

`fix-feedback --autonomous` is the only sanctioned relaxation of that skill's "never write
unasked" rule. It still never pushes — committing and pushing belong to the caller — and it
still never resolves a thread it disagreed with.

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
