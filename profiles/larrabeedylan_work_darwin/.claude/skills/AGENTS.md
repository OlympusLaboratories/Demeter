# skills/ — Agent Instructions

## Structure

Each skill is a subdirectory containing a `SKILL.md` file that defines the skill's behavior. Skills are symlinked into `~/.claude/skills/` by `install.sh` and become available as slash commands in Claude Code.

## Current Skills

| Skill | Purpose |
|---|---|
| `changes-branch` | Load branch context |
| `changes-description` | Adversarial four-persona debate (senior / skimmer / novice / AI-slop hawk) that converges on an MR description, then fact-checks it against the diff (uses the Workflow tool; prints a `wf_…` run ID to watch live with `wfwatch <id>`) |
| `changes-diagram` | Turns the branch's diff into an interactive call-flow page — each changed function a box with its +/- lines, grouped into module boxes, with new and dropped calls and a click-through review walk. Falls back to a file/module graph on non-Python branches, so a non-empty diff never yields an empty chart. Publishes to whichever artifact store `skill-env.sh` names |
| `changes-explain` | MR change breakdown |
| `commit-msg` | Generate commit messages |
| `docs-humanize` | Adversarial five-persona swarm (archivist / skimmer / newcomer / slop hawk / doer) that rebuilds an AI-written Notion page, markdown file or Linear ticket into something a human reads once and acts on — builds a fact ledger first, then proves against it that nothing real was lost and nothing was invented (uses the Workflow tool; prints a `wf_…` run ID to watch live with `wfwatch <id>`) |
| `docs-update` | Audit and update README.md and AGENTS.md to reflect current repo state |
| `autopilot` | A mode switched on over `fix-linear` or `fix-freeform`, never a task of its own — it overrides none of that skill's flags and adds only the automation: commits, commits, describes, pushes, opens the MR, watches the pipeline and the review bot with `Monitor`, runs a `review-code` swarm alongside that bot, works the review clean, applies infrastructure plans, merges stacked changes in order, and pings you when done or stuck |
| `fix-feedback` | Work through review feedback — MR/PR threads or a local review agent's output |
| `fix-freeform` | `fix-linear` without a ticket — implements a freeform problem statement. Defaults to the repo's default branch, a one-shot description, no diagram and no review swarm (`--review true` opts in); escalates to a feature branch on its own when the change touches Terraform, the default branch is protected, or the tree has unrelated uncommitted work |
| `fix-linear` | Linear ticket implementation. After the description it defaults to both a call-flow diagram and a `review-code` swarm over the branch (`--diagram false` / `--review false` to skip either) |
| `ping` | Send yourself a push notification carrying what this session is doing and what it needs. Invoked directly, or by another skill handing over a status, a question, a blocker or a finished run |
| `plan-initiative` | Sequence a Linear initiative's subtasks and delegate them across named engineers — dependency graph, parallelism verdict, swimlane chart, per-person work orders |
| `plan-subtasks` | Turn a design doc + implementation breakdown into a Linear ticket tree — one parent, one MR-sized subtask per reviewable slice, both doc links on every ticket; confirms team/project/assignee and writes to Linear only after the plan is approved |
| `reflect-peer` | Peer assessment generator (stub) |
| `reflect-self` | Self-assessment generator (stub) |
| `reflect-week` | Generate weekly engineering snippets |
| `review-code` | Adversarial multi-agent review of proposed local changes, or of an incoming branch someone else pushed — the latter is fetched into a detached review worktree and comes back with a pack of ready-to-paste review comments (uses the Workflow tool; prints a `wf_…` run ID to watch live with `wfwatch <id>`) |
| `review-kludge` | Adversarial swarm that reviews recent large features for accumulated kludge/AI-slop and proposes refactors (uses the Workflow tool; prints a `wf_…` run ID to watch live with `wfwatch <id>`) |
| `workflow-resume` | Rescue a `Workflow` swarm that died mid-run — diagnoses why (spend limit, kill, API errors), then either resumes it from the on-disk agent cache or harvests the finished agents' results |

## Worktrees

`fix-linear`, `fix-freeform` (when it escalates to `--branch new`) and `fix-feedback` isolate each fix in its own git worktree by default (under `.claude/worktrees/<branch>`), entered via the `EnterWorktree` tool, so multiple non-blocking fixes can run in parallel — one session per worktree. They offer to install dependencies in the fresh worktree and leave cleanup manual (`git worktree remove`). Pass `in place` / `--here` / `no worktree` in the skill argument to fall back to an in-place checkout. `commit-msg` and `changes-description` operate on the current directory and need no worktree awareness, and `docs-humanize` touches no checkout at all unless its target is a file path. `review-code` does too in its default local mode, but when handed an incoming branch it creates a **detached** review worktree at `.claude/worktrees/review/<branch>` — never checking their branch out over yours — and leaves removal to you. `autopilot` creates no worktree of its own — it inherits whichever one the fix skill it delegated to set up, and owns that single branch for the whole run. Full guide: `WORKTREES.md` at the repo root.

## Workflow Runs

`changes-description`, `docs-humanize`, `review-code`, and `review-kludge` orchestrate swarms through the **Workflow** tool. `fix-linear`, `fix-freeform` and `autopilot` reach two of them indirectly — `changes-description` always, and `review-code` on the `--review` flag — so a single fix run can leave two run directories behind. Each run leaves a manifest, a script snapshot, and a `journal.jsonl` agent cache under `~/.claude/projects/<slug>/<session>/`. All four **launch and yield**: the tool returns a `wf_…` run id immediately, the skill prints it with the `wfwatch` command, ends the turn, and resumes on the run's completion notification. None of them may hold the session open waiting on a swarm — no `TaskOutput`, `Monitor`, `ScheduleWakeup`, or polling — so the user keeps a free prompt line for the whole run. `workflow-resume` reads all of it through `~/.claude/scripts/workflow-runs.py` (`list`, `show`, `args`, `script`, `link`, `merge`, `harvest`).

Two facts those four skills depend on: a workflow reports `completed` even when agents died mid-run (`agent()` returns `null`, the script carries on), and the resume cache is a **prefix** — a hash chain over agent calls that stops replaying at the first agent with no recorded result. Neither is visible from the report a swarm prints.

## GitLab Data

MR-related skills (`explain`, `mr-description`, `feedback`, `eng-snippet`) use `~/.claude/scripts/gitlab-api.sh` for all GitLab API access. The script reads the GitLab token from `~/.claude/.mcp.json` so tokens never enter conversation context.

`fix-feedback` is the only one that **writes** through it, and both writes are gated on an explicit yes in chat: Step 3b opens one new anchored discussion per unique review-swarm finding (`create-diff-comment` — body over stdin, so the single-quote rule that governs `reply-to-thread` does not apply; falls back to an unanchored note when the line sits outside the MR diff or the commit is unpushed), and Step 7b replies into an existing thread (`reply-to-thread`). `mr-for-branch` finds the MR when only the branch is known — both its arguments accept `-` to derive the project from `origin` and the branch from `HEAD`.

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
bot, or the artifact store. Those differ between the work profiles (GitLab, Claude
Artifacts) and home (GitHub, a self-hosted store), and a skill that bakes one machine's
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

`autopilot` is a **mode on a fix skill, not a task of its own** — it cannot be invoked
against nothing, and `/autopilot <ticket or statement>` still routes through `fix-linear`
or `fix-freeform` and inherits that skill's defaults. It composes the ordinary skills
rather than reimplementing them: the fix skill, then `commit-msg`,
`changes-description`, `review-code`, `fix-feedback --autonomous`, `changes-diagram` and
`ping`. Five invariants it must never lose:

- **It waits with the `Monitor` tool, never a sleep or a poll loop.** Several runs may be
  live at once and each blocking one costs a session. Every terminal state must emit a
  line — a watcher that reports only success stays silent through a crashloop, and silence
  is indistinguishable from "still running".
- **Review comments outrank CI.** Fixing comments means pushing, and a push restarts the
  pipeline, so handling CI first throws away a whole run.
- **The swarm is launched with the watcher, not after it.** `review-code` and the forge's
  own reviewer read the same pushed diff and neither gates the other, so both start in the
  turn that arms the `Monitor` and the run yields once for both. The swarm runs once per
  run, not once per review round. Whichever run opens a change request also
  passes `--review false` down, so the swarm runs here rather than before the push and
  `fix-feedback` has somewhere to post its findings.
- **It owns no flag but `--merge` and `--max-rounds`, and overrides none.** It is a
  modifier on a fix skill, not a peer: every decision a parameter expresses was already
  made there, `--branch` included. `--review` is therefore on through `fix-linear` and off
  through `fix-freeform`, and being unattended is not a reason to spend a fleet the user
  declined. A `--branch default` run pushes the default branch and ends — Steps 5–10 have
  no change request to drive — which is safe to honour because `fix-freeform`'s own Step 2b
  has already forced a feature branch for Terraform, a protected default branch, or a dirty
  tree.
- **It supersedes `fix-linear`/`fix-freeform` Important Rule 1** (never push, never open a
  change request) for the one branch it created, and for nothing else. That carve-out is
  written into `autopilot` explicitly; it is not something an agent may infer.

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
