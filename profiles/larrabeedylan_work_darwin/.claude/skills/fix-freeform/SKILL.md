---
name: fix-freeform
description: Implement a change the user described in their own words, with no ticket behind it — "fix this bug", "make this change", "implement X", "can you clean up Y". Interrogates the problem statement against the code before planning, cuts a feature branch and worktree, implements it, and — unless autopilot is switched off — pushes, opens the merge request, works the review and merges. Use it whenever there is work to do and nothing to look the work up in; use fix-linear instead when a ticket identifier exists.
---

# Fix Freeform — Implement a Change From a Problem Statement

Implement a change the user described in plain words, and — unless you are told otherwise — take it all the way to a change request that is ready to merge. This is `fix-linear` with the ticket taken away: nothing to fetch, no parent initiative, no linked spec, and nothing to check the request against except the code itself.

**Parameter:** `$ARGUMENTS` — optional flags, then the problem statement.

| Argument | Env key | Effect |
|---|---|---|
| *(everything left after the flags)* | — | The problem statement — what to fix, change, or build. Required: if nothing is left over, ask the user what they want done and stop. |
| `--branch new\|default` | `fix_branch` | `new` cuts `<FIRST_NAME>/<slug>` off the default branch in its own git worktree. `default` commits onto the repository's default branch — no feature branch, no worktree, no merge request. **Step 2** owns this, and three conditions can force `new` whatever the flag said. |
| `--quick-description [true\|false]` | `fix_quick_description` | `true` passes `--inline` to `changes-description`: **no workflow at all**, the description written in the same turn against that skill's template, measured word budget and fact-check. The run then goes straight on to the hand-off. `false` runs the full four-persona debate, which yields the turn until the swarm reports. |
| `--diagram [true\|false]` | `fix_diagram` | Run `changes-diagram` and attach the published page to the merge request. |
| `--review [true\|false]` | `fix_review` | Run the `review-code` adversarial swarm over this branch's diff, and feed its confirmed findings through `fix-feedback`. |
| `--autopilot [true\|false]` | `fix_autopilot` | `true` hands the finished implementation to `autopilot`, which pushes, opens the merge request, works the review and merges. `false` stops at the commit message and the description, and nothing leaves this machine. |
| `--merge [true\|false]` | `fix_merge` | `autopilot`'s flag, forwarded. `false` drives the run to a green pipeline, a clean review and a ready merge request, then stops without merging. |
| `--max-rounds N` | `fix_max_rounds` | `autopilot`'s flag, forwarded. Review rounds with the same reviewer before escalating. |

**No default is written in this file.** Every one of them differs between machines, so **Step 0** reads them out of `skill-env.sh` and a flag in the invocation overrides whatever came back. A bare flag means `true` — `--diagram` and `--diagram true` are the same thing. Run `~/.claude/scripts/skill-env.sh check` to see what an unflagged run does here.

**The flag surface is identical to `fix-linear`'s, and so are the defaults on any given machine.** The two skills differ in where the work comes from — a ticket, or a sentence — and in nothing else. A flag that meant one thing in one and something else in the other would be a trap, because the user types them interchangeably.

Parse the flags out of `$ARGUMENTS` **first**; whatever remains is the problem statement. Leaving a flag unparsed hands it to the planner as part of the request, which produces a plan to implement the words "branch new".

## Step 0: Resolve the Defaults

```bash
~/.claude/scripts/skill-env.sh check
```

Read `fix_autopilot`, `fix_branch`, `fix_quick_description`, `fix_diagram`, `fix_review`, `fix_merge` and `fix_max_rounds`, lay any flag the user passed over the top, and **write the seven resolved values down where you can still see them hours later** — a todo, or a line in your notes. They are not read once: `--merge` decides the end of the run, and `/autopilot` can amend any of them mid-flight, at which point *what is this run set to* has to be answerable without re-deriving it.

Then state the resolution in one line before doing anything else:

> `branch new · one-shot description · no diagram · no swarm · autopilot, merging when green`

Every one of those costs the user something, and a wrong default is cheapest to catch here. A key missing from `skill-env.sh` is not an error — it carries working defaults in code, so an absent or malformed `~/.claude/environment.json` degrades to them rather than breaking the run.

### Autopilot is on unless it is switched off

`fix_autopilot` is `true` on every profile, so **the ordinary run of this skill ends at a merge request, not at a commit message.** Once the implementation and the deliverables are done, 5f hands the run to `autopilot`, which owns the push, the merge request, the pipeline watch, the review rounds, the infrastructure apply, and — when `--merge` is true — the merge itself.

**That does not mean this skill stops talking to the user.** Autopilot automates the *tail*. It does not close any of the gates before it, and in this skill those gates matter more than anywhere else: Step 1b exists precisely because a sentence typed in ten seconds is the least-reviewed input any of these skills take, and an unattended tail is not a reason to stop restating the request, stop checking its claims against the code, or stop reaching for `AskUserQuestion` when the answer changes the implementation. The decisions autopilot makes alone are the ones after the code is written, which is the point at which the user stopped watching.

`--autopilot false` is the way back to implementation only — a branch, a commit message, a description, and nothing that leaves this machine. It is the flag for a spike, or for anything you want to look at before it becomes somebody else's notification.

### `/autopilot` can amend the run at any point

The user may run `/autopilot <flags>` while this skill is working — to turn on a diagram they have decided they want, or to hold a merge they had been happy to let go. That is an **amendment to this run**, not a new run and not a question to put back to them. Apply it per `autopilot`'s *Amending a run in flight* section: change only the flags they named, leave every other flag at its **current** value rather than resetting it to the machine default, say in one line what changed and what it caused to happen now, and carry on from where you were.

A bare `/autopilot` token inside the *initial* invocation is now redundant rather than wrong — autopilot is already on. Strip it, apply any flags it carries, and say nothing further about it.

## Step 1: Understand What Is Being Asked

### 1a. Get the user's first name

```bash
git config user.name
```

Extract the **first name** (the first word, lowercased) and store it as `FIRST_NAME`. It is only used on the `--branch new` path, but it costs one command and the escalation in Step 2b can force that path at any point.

### 1b. Interrogate the problem statement

The absence of a ticket cuts both ways: nothing was lost in translation, and nothing was written down carefully either. Before any planning:

1. **Restate it in one sentence** and show the user: "You want X." Your reading of the request, not a paraphrase of their words. If your sentence is longer than theirs, you have not understood it yet — ask.
2. **Separate the symptom from the guess.** A freeform statement is usually a symptom plus a hypothesis about the cause ("the sync is slow, probably the N+1 in the loader"). The symptom is the requirement; the hypothesis is a thing to test. Implementing the hypothesis and leaving the symptom in place is the most common way this skill fails, and it fails while looking finished.
3. **Verify every factual claim in the statement against the code, before planning.** `fix-linear` has to do this to tickets because a ticket written during research routinely overstates ("every row is wrong", "X carries no Y") or describes a pre-implementation design that shipped narrower. A statement typed into a prompt in ten seconds is **more** prone to that, not less — nobody reviewed it, not even its author, and there is no description field where a second thought could have landed. Concretely:
   - Every path, symbol, function, flag, and config key the statement names: confirm it exists and is spelled that way. Glob or `rg` for it; do not trust the name. Half the paths quoted from memory are wrong in a way that still reads plausibly (`registry.py` for `rule_registry.py`).
   - Every count ("three call sites", "only used by the CLI"): count it yourself.
   - Every behavioural claim ("it retries forever", "the default is 30s"): read the line that sets it.

   **Where the statement and the code disagree, implement what the code says and say so** — quote the claim, name the file and line that contradicts it, and state what you are doing instead. Never correct it silently: that gap is often the most interesting thing in the request, and it is sometimes the actual bug.
4. If the request is still ambiguous in a way that changes the implementation, use `AskUserQuestion` before planning. Asking is cheaper here than on a ticket — the author is right there — and a wrong guess costs exactly as much to review either way.

State the result of this step in a few lines before moving on: the one-sentence restatement, anything the code contradicted, and anything you asked about.

### 1c. Compute the branch name

Needed only on the `--branch new` path — including when Step 2b escalates into it, so do not skip it on the strength of the flag alone.

Derive a slug from the problem statement: lowercase, hyphen-separated, three to five words, naming **the change rather than the symptom** (`cache-sync-timeout`, not `fix-the-slow-thing`). The branch name is `FIRST_NAME/<slug>` — e.g. `dylan/cache-sync-timeout`. Store it as `BRANCH_NAME` and check it is free:

```bash
git branch --list <BRANCH_NAME>
git branch -r --list origin/<BRANCH_NAME>
```

If it is taken, append a distinguishing word rather than reusing someone else's branch.

## Step 2: Choose the Branch Mode

`--branch` decides where the work lands, and it has exactly two values. `new` cuts a feature branch in its own worktree; `default` commits onto the branch every other checkout is cut from, which means no merge request and nothing to review. **The mode is not purely the user's choice — three conditions force `new`, and all three are checked before the first edit.**

`fix-linear` resolves this flag with the same two values and the same three checks. Neither skill has a branch mode the other lacks.

**No-worktree fallback.** If the repo cannot host worktrees (`git worktree list` errors), `--branch new` uses **Step 2-FALLBACK**, which takes the branch in the current checkout. That is a capability fallback, not a mode anybody selects — there is no flag for it, and `--branch` has no third value.

### 2a. Determine the default branch

```bash
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'
```

If that fails, fall back:

```bash
git branch -r | grep -E 'origin/(main|master)$' | head -1 | sed 's@.*origin/@@'
```

Store the result as `DEFAULT_BRANCH`.

### 2b. Run the escalation checks — all three, before the first edit

Run all three even when the user passed `--branch default` explicitly. When one fires, switch to `--branch new` and **announce it in one line naming the reason** — "Escalating to a feature branch: the change touches `*.tf`" — then continue at Step 2d.

**1. The change touches Terraform. This is a safety rule, not a preference.**

```bash
ls atlantis.yaml atlantis.yml 2>/dev/null
git ls-files '*.tf' '*.tfvars' | head
```

Escalate if the planned change will touch any `*.tf` or `*.tfvars` file, or if the repo carries an `atlantis.yaml` / `atlantis.yml`. Atlantis plans and applies from a **merge request branch**: the plan output is posted on the MR, a human reads it, and the apply is gated on that read. A Terraform change committed straight onto the default branch skips the plan review entirely — nothing is posted anywhere a human looks, and infrastructure can be applied with nobody having seen what it would do. No "it's a one-line change" makes that acceptable, and the user cannot waive it with a flag. If the repo has `*.tf` files but you cannot yet tell whether this change reaches them, leave the question open and settle it in the plan (Step 3) — never by starting to edit and seeing what happens. If it only turns out to be Terraform-touching mid-implementation, stop there and escalate — Step 2e moves a commit you have already made.

**2. The default branch is protected.** Detect this **before** committing, rather than discovering it when a push is rejected. The forge knows; git does not.

```bash
~/.claude/scripts/gitlab-api.sh help
```

`help` prints every subcommand the script actually has, each with the arguments it takes. Both are generated from the script's own source, so neither can drift from what is implemented, and it needs no token — it works on a machine with nothing configured yet. If that list includes one reporting protected refs (`protected-refs`), call it with the project path URL-encoded (`group%2Fsubgroup%2Frepo`, derived from `git remote get-url origin`) and look for `DEFAULT_BRANCH` in the result. **If the script carries no such subcommand, the call fails, or no token is configured, you cannot answer the question from here — escalate rather than guess.** An unneeded feature branch costs one `git worktree remove`; a rejected push costs a commit stranded on the branch it was least welcome on, and Step 2e to unpick.

**3. The working tree already has unrelated uncommitted changes.**

```bash
git status --porcelain
```

If the tree is dirty with work that is not yours, escalate: committing on top of it mixes the user's in-progress work into your commit, and `git commit <paths>` only avoids that while you can prove which paths are theirs. The worktree gives you a clean tree and leaves theirs untouched. Never stash or discard it to clear this check — that is Important Rule 2, and it outranks the convenience of staying on the default branch.

Record which checks fired. It goes in the summary and in the commit context.

### 2c. `--branch default` — work on the default branch

No feature branch, no worktree, and **no merge request**. Confirm you are actually on the default branch:

```bash
git rev-parse --abbrev-ref HEAD
```

- **If HEAD is `DEFAULT_BRANCH`**, bring it up to date without creating a merge commit:
  ```bash
  git fetch origin <DEFAULT_BRANCH> --quiet
  git merge --ff-only origin/<DEFAULT_BRANCH>
  ```
  If the fast-forward is refused, the local default branch has commits of its own or has diverged. Stop and tell the user what is there — do not resolve it with a merge commit on their default branch.
- **If HEAD is some other branch**, stop and ask which they meant. Working on whatever branch happens to be checked out is a different thing from what `--branch default` promises, and switching branches under the user silently is worse than either. If they answer "the branch I'm on", continue here with that branch in place of `DEFAULT_BRANCH` — the protection check in Step 2b still applies to it.

Then go to Step 3. Everything after this runs in the current working tree.

### 2d. `--branch new` — branch and worktree

This path isolates the work in its own **git worktree** — a separate working directory on its own branch that shares the repo's `.git`. This lets several fixes run in parallel (one terminal/session per worktree) without branch checkouts colliding in a single working tree. If the repo cannot host worktrees, fall back to **Step 2-FALLBACK**.

1. Check whether you are already there:
   ```bash
   git rev-parse --abbrev-ref HEAD
   ```
   If the current branch already matches `BRANCH_NAME` (case-insensitive), fetch and merge the latest default branch, then skip to Step 3:
   ```bash
   git fetch origin <DEFAULT_BRANCH> --quiet
   git merge origin/<DEFAULT_BRANCH> --no-edit
   ```
   If the merge has conflicts, stop and tell the user so they can resolve them before continuing.
2. Otherwise set `WORKTREE_PATH` to `.claude/worktrees/<BRANCH_NAME>` (relative to the repo root) and run the rest from the **main repo root**. Fetch the latest default branch:
   ```bash
   git fetch origin <DEFAULT_BRANCH> --quiet
   ```
3. Check whether a worktree for this branch already exists:
   ```bash
   git worktree list --porcelain
   ```
   If `BRANCH_NAME` (or `WORKTREE_PATH`) is already listed, **enter it** with the `EnterWorktree` tool (`path:` = that worktree's path), merge `origin/<DEFAULT_BRANCH>` (`--no-edit`), then skip to Step 3 — its dependencies are already installed, so skip the install offer below too.
   **A worktree that already exists may also already have an open merge request** — a previous run can be interrupted after it pushed and opened one (an API rate limit, a killed session). Before re-planning anything, check for one: run `~/.claude/scripts/gitlab-api.sh` with no arguments and use whichever of its subcommands lists merge requests for a branch head. If one is open, its diff, its description and its CI state are the record of what that run completed, and they are read *first* — the work already done is established by reading the merge request, not by re-deriving it from the problem statement. Do not re-implement a change the diff already contains, do not open a second merge request, and do not cut a new branch. Nothing else in 2d assumes this, which is exactly why it has to be checked here.
4. **If the branch exists** (locally or remotely) but has no worktree, add a worktree on it:
   ```bash
   git worktree add <WORKTREE_PATH> <BRANCH_NAME>
   ```
   Then call the `EnterWorktree` tool with `path: <WORKTREE_PATH>` to move this session into it, and merge in the latest default branch:
   ```bash
   git merge origin/<DEFAULT_BRANCH> --no-edit
   ```
   If the merge conflicts, stop and tell the user.
5. **If the branch does not exist**, create it in a fresh worktree off the up-to-date default branch:
   ```bash
   git worktree add -b <BRANCH_NAME> <WORKTREE_PATH> origin/<DEFAULT_BRANCH>
   ```
   Then call the `EnterWorktree` tool with `path: <WORKTREE_PATH>` to move this session into it.

After entering, confirm to the user which worktree and branch they are now in. Every later step (implementation, `commit-msg`, `changes-description`, `review-code`, `fix-feedback`) runs inside this worktree.

> **Cleanup is manual.** Worktrees created here are *not* auto-removed on session exit. When the branch is merged or abandoned, the user removes it with `git worktree remove <WORKTREE_PATH>`. See `WORKTREES.md` in the Demeter repo for the full worktree guide.

**Offer to install dependencies.** A fresh worktree has no installed dependencies or build artifacts. Detect the project's package manager from files present in the worktree and **offer to run the install command — wait for the user's approval before running it**:

- `package-lock.json` → `npm install` · `yarn.lock` → `yarn` · `pnpm-lock.yaml` → `pnpm install` · `bun.lockb` → `bun install`
- `uv.lock` → `uv sync` · `poetry.lock` → `poetry install` · `requirements.txt` → `pip install -r requirements.txt`
- `go.mod` → `go mod download` · `Gemfile` → `bundle install` · `Cargo.toml` → `cargo fetch`

If several match, prefer the one matching the lockfile present. If none match, or the user declines, note that dependencies are not installed and continue.

**Never judge an install by a piped command's exit code.** `pnpm install 2>&1 | tail -25` exits with `tail`'s status, so a hard failure reports success. Run the installer bare, or check `${PIPESTATUS[0]}`.

**In `gridmatic-dev`, `pnpm install` needs a live GAR token and often cannot get one.** npm resolves through the foundation Artifact Registry, and `make npm-auth` mints the token via `gcloud`. In a non-interactive session `gcloud` frequently needs a reauth it cannot prompt for, so both `make npm-auth` and any `pnpm install` that must fetch metadata fail (`ERR_PNPM_FETCH_403`, or `ERR_PNPM_NO_OFFLINE_META` with `--offline`). Note also that `pnpm` is not on `PATH` — it comes from mise, so invoke it as `mise exec -- pnpm`.

When that happens, don't declare the change unverifiable. Borrow the main checkout's already-installed tree:

```bash
ln -s <MAIN_REPO>/apps/<app>/node_modules <WORKTREE>/apps/<app>/node_modules
mise exec -- <WORKTREE>/apps/<app>/node_modules/.bin/vitest run <paths>
```

Tests and lint run correctly this way. **Type-checking does not** — the borrowed tree's generated `@gridmatic/*` workspace packages belong to whatever commit the main checkout sits on, so `tsc -b` emits phantom errors (`Cannot find module '@gridmatic/notify-api'`) that have nothing to do with the branch. Report the count and confirm none are in the changed files rather than presenting it as a clean type-check. Remove the symlink when done — left in place it silently resolves imports against another checkout — and tell the user to run `make npm-auth && pnpm install` once they've re-authed.

**The symlink is required, not merely convenient, when the session is worktree-isolated.** A one-shot invocation of the binary by its absolute path in the main checkout is refused by the isolation guard ("too complex to verify that it stays inside the worktree"), and so is any command combining `cd`, a pipe, and an outside path. Create the symlink inside the worktree, invoke the binary through the *relative* `./node_modules/.bin/…` path, then delete it. The inner symlinks in a pnpm tree are relative to their real location, so they still resolve to the main checkout's store — this works.

**The isolation guard also refuses `cd … && cat > file <<'EOF' … EOF` and any pipe-plus-`$PIPESTATUS` one-liner.** It is not only about paths outside the worktree — a *shape* it cannot statically verify gets refused too. Use the Write tool for whole-file content and the Edit tool for patches (they are never refused, and Write is faster than a heredoc anyway), and run linters and test binaries bare so their real exit code surfaces.

**The Bash working directory persists between calls, and a bare `cd` will strand you.** After `cd apps/portal`, a later `cd apps/portal` fails and a relative `ln -s packages/…` lands in the wrong place. Either issue every path absolutely, or re-`cd` to the worktree root as its own command before any step whose relative paths matter. `pwd` when a relative path fails unexpectedly.

**Work that spans two repos is still workable from one worktree-isolated session — use `git -C <abs path>`.** `cd ~/other-repo && git status` is refused ("changes directory to a location computed at runtime before running git"), but `git -C /Users/…/other-repo status` is accepted, and so is `git -C <repo> worktree add -b <branch> <path> origin/main`. Read/Edit/Write against absolute paths in the other repo are not blocked either. Ask the user early whether they want the second repo driven in the same session or left as a follow-up — it changes how much gets done here.

**Two more shapes the isolation guard refuses.** A `for` loop over scenarios (`for m in a b c; do terraform … -var mode=$m; done`), and a compound `A; echo ---; B; echo ---; C` that merely *inspects* things outside the worktree. Neither touches git and neither writes outside, but the guard is static: any multi-command shape it cannot unroll gets refused. Issue them as separate plain calls — batch the independent ones into one message so they still run in parallel. Note `terraform -chdir=<abs path>` *is* accepted, which is how to drive a scratchpad harness without `cd`.

### 2e. Escalating after work has already started

A check can fire late: the change turns out to touch Terraform, or a push the user tries is rejected. Nothing is lost while the commit is still local. Tell the user exactly which commits are about to move, then:

```bash
git branch <BRANCH_NAME>
git reset --keep origin/<DEFAULT_BRANCH>
git switch <BRANCH_NAME>
```

`--keep` refuses rather than destroying uncommitted work, which is the behaviour you want here. Do not run this on a branch carrying commits you did not make without naming them first.

## Step 2-FALLBACK: Branch Checkout Without a Worktree

Use this **only** when `--branch new` is in force and the repo cannot host worktrees — it is the original single-working-tree behavior, kept as a capability fallback. Nobody selects it with a flag. Compute `DEFAULT_BRANCH` as in 2a and run the 2b checks first.

```bash
git rev-parse --abbrev-ref HEAD
```

Store as `CURRENT_BRANCH`.

**If `CURRENT_BRANCH` already matches `BRANCH_NAME`** (case-insensitive):

1. `git fetch origin <DEFAULT_BRANCH> --quiet`
2. `git merge origin/<DEFAULT_BRANCH> --no-edit`
3. If the merge has conflicts, stop and tell the user so they can resolve them before continuing.

**Otherwise (not on the target branch):**

1. Check for uncommitted changes. If there are any, warn the user and stop — do not switch branches with a dirty working tree.
   ```bash
   git status --porcelain
   ```
2. Fetch and update the default branch:
   ```bash
   git fetch origin <DEFAULT_BRANCH> --quiet
   ```
3. Check if `BRANCH_NAME` already exists locally or on the remote:
   ```bash
   git branch --list <BRANCH_NAME>
   git branch -r --list origin/<BRANCH_NAME>
   ```
4. If the branch already exists (locally or remotely), check it out and merge in the latest default branch:
   ```bash
   git checkout <BRANCH_NAME>
   git merge origin/<DEFAULT_BRANCH> --no-edit
   ```
5. If the branch does not exist, create it from the up-to-date default branch:
   ```bash
   git checkout -b <BRANCH_NAME> origin/<DEFAULT_BRANCH>
   ```

After this step, confirm to the user which branch they are now on.

## Step 3: Plan the Implementation

**Do not use plan mode at all.** The approval gate is the point; plan mode is one way to get it and it is the wrong one here, for two independent reasons. Inside it, **`permissions.allow` cannot cover a shell construct** — a `for` loop or a pipeline has no single command head to match, so Claude Code cannot even offer to remember it: the prompt reads `Yes`/`No` with no "allow for this project" option, and an unattended run stops dead on a command that only reads files. And leaving it is worse: `ExitPlanMode` drops the session into whichever mode the approval prompt offers, which is `acceptEdits` wherever auto mode is unavailable — and `acceptEdits` auto-approves edits while **prompting for every single `Bash` call** for the rest of the run. Both were observed repeatedly on runs whose whole purpose was to need nothing from anybody. Widening the allowlist fixes neither and never will.

So **never call `EnterPlanMode` or `ExitPlanMode` in this skill.** Explore and plan under the session's own mode, then gate on `AskUserQuestion`, which asks just as plainly, notifies the user's phone through the same hook, and leaves the session's permission mode exactly where it was.

**Nothing is created or modified before the plan is approved.** Plan mode used to enforce that and now it is a rule you keep yourself. Read, Glob, Grep and read-only shell are the whole toolkit of this step: no Edit, no Write, no `git` command that changes state, no install, no network write.

Carry Step 1b's findings with you — the restatement, and anything the code already contradicted — and then:

1. **Explore the codebase** — use Glob, Grep, and Read to understand the relevant files, existing patterns, and architecture. Step 1b checked the statement's claims; this step is where you find what it never mentioned, which on a freeform request is most of it. The statement names what the user noticed; the plan has to cover what the change actually touches.

   **Do not trust a call-site count, and do not stop at the obvious grep.** Grepping for a constructor misses call sites that go through a test helper: `rg 'Owner\('` found nine, while two more reached the model as `owner(fetch=..., transform=...)` via the `owner()` factory in `tests/conftest.py`, and only the type-checker caught them. When deleting a field or parameter, also grep for the *lowercase helper* and any `**kwargs` forwarder — or treat the first typecheck run as part of discovery rather than as verification.

   **`rg -r` is `--replace`, not "recursive".** `rg -rn 'foo-bar' .` silently rewrites every match to `n` in the output, which reads as a real but wrong result (it made a bucket named `ftl-local-dev` appear to be named `n`, sending me down a false trail). ripgrep is recursive by default; never pass `-r`.
2. **Design an implementation approach** — identify which files need changes, what the changes are, and in what order.
3. **Confirm the branch mode still holds.** If exploration shows the change reaches a `*.tf` file, or any other Step 2b condition, say so in the plan and escalate before implementing (Step 2e).
4. **Ask clarifying questions** — if the problem statement is ambiguous or missing details, use `AskUserQuestion` to clarify with the user before finalizing the plan.
5. **Present the plan and gate on it — and put the plan inside the question.** Write the full plan into your reply for the terminal, then call `AskUserQuestion` whose **question text carries the plan itself**, compressed: the link published below, then the files that change, what changes in each, and in what order. Options are `Approve` and `Change something`. Treat anything other than a clear approval as a revision and plan again. Do **not** call `ExitPlanMode`; this skill never enters plan mode, so there is nothing to exit.

**Publish the plan first, so the question can carry a link to the whole thing.** Render the plan as a self-contained HTML page and publish it:

```bash
FOLDER=$(~/.claude/scripts/skill-env.sh get plan_folder)
~/.claude/scripts/publish-artifact.sh <plan>.html \
  ${FOLDER:+--folder "$FOLDER"} \
  --expires 7d \
  --title '<the change in a few words>' \
  --description 'implementation plan'
```

It prints the URL. `plan_folder` is empty on a machine with nowhere to file it, and the `${FOLDER:+…}` form then omits the flag rather than passing an empty one — **never substitute a folder name of your own**, since publishing refuses a folder that does not exist. `--expires 7d` is deliberate: a plan is worth reading while it is being approved and clutter a fortnight later.

**Exit status 3 means this machine has no self-hosted store.** That is the ordinary answer on most of them and not a failure — publish the same HTML with the **Artifact** tool instead and use the link it returns. Any other non-zero status is a real failure: say what it printed in one line, then ask the question with the summary alone. **Never hold the gate open waiting for a link.** A plan the user can only read in the terminal still gets approved; a question that never arrives strands the run.

**The question text is the only copy of the plan that is certain to reach the phone**, so a question reading "approve the plan?" strands the user — they get a notification saying the session is waiting and no way to know what for without opening the laptop. `ExitPlanMode` was no better: the hook sends the fixed string `Waiting for plan approval.` for it and never the plan, so this is a gap being closed rather than one being introduced. Keep the question under roughly fifteen lines — the link, then one line per file, leading with the path — because it is read on a phone screen. The link is what carries the full plan to the phone; the lines are what tell the user whether opening it is worth doing, so neither replaces the other. State the branch mode in the plan: which branch the work will land on, and whether an escalation fired.

Once the user approves the plan, implement the changes.

## Step 4: Implement the Changes

Execute the approved plan:
- Use `TodoWrite` to track implementation tasks.
- Write clean, minimal code that follows existing codebase patterns.
- **Add no comments to the code you write or change.** No explanatory comments, no banners, no docstring on a symbol that did not have one, no `TODO`s, no commented-out code — and never a reference to the Linear ticket, task, or initiative (`# ENG-123`, `// per PLAT-1180`, `# for the X initiative`). A comment written alongside the code restates the line, goes stale, and makes the reviewer read past it to reach the change. Write the code so it does not need one, and put every explanation in the commit message and MR description instead. Exempt because they are program input rather than commentary: linter and type directives, build pragmas, codegen markers, required license headers, and any doc-comment CI fails without. Leave comments already in the file alone unless your change makes one untrue — then correct or delete it.

  **There is no ticket here, so the shape that rule catches is the comment pointing back at the request itself** — `// as asked`, `# per the request`, `# requested fix` — and it is cut on exactly the same grounds: it tells a future reader nothing about the code and goes stale the moment the line moves.

  **A comment-dense file does not create an exception, and this is where the rule is most often broken.** Some files document the rationale behind every constant — one service spends 25 lines explaining a single retry policy's arithmetic. Writing the new code to match that density and stripping the comments afterwards wastes a full editing pass; decide before the first line that the new code carries none, and route the reasoning to the commit message and MR description as you go. Then say so in the summary, because the asymmetry is genuinely visible in review: a new timeout sitting silently beside a heavily-justified one looks like an oversight rather than a convention. Let the user reverse it in one word if they want the local convention honoured instead.
- Run any relevant tests or linters if the project has them configured.
- **When the real verification command needs credentials you cannot get, build an offline harness rather than shipping unverified logic.** In a Terraform repo the honest ceiling is usually `terraform validate` — `terraform plan` needs a gcloud ADC reauth this session cannot perform (`invalid_grant` / `invalid_rapt`), and some modules additionally need an API key from the environment. `validate` type-checks but never *evaluates* a `precondition`, so a guard that passes validate can still crash at plan time. Copy the new locals into a provider-free config in the scratchpad and drive it with `terraform -chdir=<abs> apply -auto-approve -var mode=…`, outputting the guard lists: it needs no credentials and it tests the counterfactuals — the mis-ordered rule, the deleted rule, the bad value — which no real plan of a correct config ever exercises. That caught a genuine bug once: **HCL's `||` does not short-circuit**, so `length(xs) == 0 || i < xs[0]` throws `Invalid index` on an empty list instead of taking the left branch. Use a sentinel — `try([…][0], length(…))` — not a guarded index. Two harness caveats: `concat` of rule objects with differing attributes yields a *tuple*, so a `var.mode ? concatA : concatB` ternary fails on inconsistent types (use uniform stub objects, or select with a filtered list); and a `for` result expression like `rule.id` is only evaluated for elements passing the `if`.

  **Get the terraform version from the module's own `.mise.toml`, not from a note someone wrote.** Several modules carry one, and that pin is what Atlantis uses, so it is the version a change must actually pass on. A `TFENV_TERRAFORM_VERSION=…` override mentioned elsewhere may predate the pin and silently verify against a version nobody runs. `mise exec terraform@<pinned> -- terraform fmt -check` / `validate` is the check that counts; running the other version too is cheap and worth it, since `init` is the slow part and `fmt` needs none.
- **Terraform renders long strings across lines, so parse what actually ships.** `yamlencode` folds a >80-column value onto continuation lines. That is valid YAML and round-trips correctly, but confirm it rather than assuming: render the exact values block and parse it. `python3` here has no `yaml` module — `ruby -ryaml` does, and `jq` is available.
- **Clean up what `terraform init` leaves behind.** It drops a ~430 MB `.terraform/` in the module directory. It is gitignored (`terraform/.gitignore: **/.terraform*`) so `git status` stays clean and you will not notice — `rm -rf` it when done.
- Mark each todo as completed as you finish it.

After implementation is complete, give the user a summary of what was changed, which branch it is on, and whether any Step 2b check escalated the run.

## Step 5: Commit Message, Description, and the Hand-off

Immediately after implementation is complete — do not wait for the user to commit or ask for these.

**What these are for depends on the branch mode, and the difference is worth stating plainly.** On `--branch new` — the normal path — the description fills the merge request that 5f is about to open. On `--branch default` **there is no merge request**: nothing is opened, nothing is reviewed, nothing has a description field, so the description is a change summary for the commit body, for the user's own reference, and for the one-line report an autopilot run ends with. Write it as carefully either way; a summary nobody reads on a merge request is still the only account of the change that will exist.

### 5a. Commit message

Invoke the `commit-msg` skill using the `Skill` tool.

### 5b. Change description

**Immediately** invoke the `changes-description` skill using the `Skill` tool. Do NOT wait for the user to respond to the commit message first — invoke it in the same turn, back-to-back with the commit message, so nothing is waiting on them reading it. The `commit-msg` skill ends with a suggestion to run `/commit`, but you must continue and invoke `changes-description` before yielding to the user.

**`--quick-description` is this skill's flag; `--inline` is what `changes-description` is handed.** The two names do not line up, so read the mapping rather than the words. `--quick-description true` → pass `--inline` and nothing else. `--quick-description false` → pass **no flag at all** and let the full four-persona panel sit. A flag named "quick" whose `false` value means "pass nothing" is worth one careful read now rather than a wrong description later.

**`true` means no workflow, not a cheaper one.** What quick buys is the merge request being open sooner, not a smaller agent bill: a workflow of any size prints a run ID and ends the turn, so the description — and the push, the merge request and everything autopilot does after them — all arrive one completion notification later. `--inline` has that skill write the description in this same turn, against its template, its measured word budget and a fact-check against the diff, and this run carries straight on. Its `--one-shot` (4–6 agents) and `--quick` (15–16) are both unreachable from here on purpose, because this flag is a boolean; invoke `/changes-description --one-shot` by hand on the rare run that wants a middle setting.

**The turn only yields on `--quick-description false`.** There, `changes-description` launches a background workflow, prints a run ID and hands the turn back before the description exists — that is correct, not a stall. Yield with it: blocking on it (`TaskOutput`, `Monitor`, a poll loop) only takes the user's prompt line away for the length of the run, and the description arrives when the completion notification does. On `--quick-description true` there is nothing to wait for and nothing to watch, so work through the rest of Step 5 — up to and including the hand-off in 5f — in this same turn.

### 5c. Call-flow diagram — `--diagram true` and `--autopilot false` only

**On an autopilot run this step is autopilot's, not yours.** It attaches the diagram at its final step, once the code has stopped moving, because a diagram of a branch that changed three more times is worse than none. Run it here only when `--autopilot false` has taken the tail away — then it is the only chance the change gets at one. When both conditions hold, invoke the `changes-diagram` skill using the `Skill` tool once the description is away — it diffs the branch against its base and publishes one self-contained page: a call-flow chart of the changed functions, or a file-and-import map when the change is Terraform, Go or TypeScript. Pass the base explicitly on the `--branch default` path (`origin/<DEFAULT_BRANCH>`), since there is no feature branch for it to infer one from. If the skill is not installed on this machine, say so rather than hand-rolling a diagram.

### 5d. Re-print the commit message, verbatim

The description output is long, so by the time it finishes the commit message from 5a has scrolled far up the terminal. In the turn that presents the description, close by repeating it — unchanged from what `commit-msg` produced, no re-generation, no re-wording, no summary of it — in its own fenced block under a `Commit message` heading, so both blocks the user copies sit next to each other at the bottom. If the user corrected the commit message in between, repeat the corrected version.

### 5e. Review swarm — `--review true` and `--autopilot false` only

**On an autopilot run this step is autopilot's, not yours.** It runs the swarm in the turn that arms its pipeline watcher, *after* the push, because `fix-feedback` posts each confirmed finding to the merge request as an anchored comment and there is no merge request to post to before the push. Running it here on an autopilot run would mean doing the work twice and losing the posting target the first time. Run it here only when `--autopilot false` has taken the tail away.

When both conditions hold, invoke the `review-code` skill using the `Skill` tool once the commit message has been re-printed. It prints only its run-ID block before yielding, so the two blocks the user copies stay within a screen of the prompt.

**Pass the base explicitly on the `--branch default` path** — `--base <DEFAULT_BRANCH>`, the bare branch name rather than `origin/<DEFAULT_BRANCH>`, since `review-code` prepends the remote itself when it computes the merge-base. On an escalated `--branch new` run pass no argument at all and let it infer the base from the branch, which is what it does best.

Invoking it is the opt-in — `--review true` was the user asking for a swarm, and `review-code` sizes its own fleet to the diff — so do not stop to confirm that one is warranted.

It launches as a background workflow and yields the turn with a `wf_…` run ID. Yield with it, present the findings when the completion notification arrives, and name `/fix-feedback` as the way to work through them. If the skill is not installed on this machine, say so in one line rather than hand-rolling a review.

**On `--branch default` the findings land on code that is already on the default branch**, and that is the one thing worth saying out loud when you present them: there was no review gate between this change and every other checkout, so a confirmed finding is a follow-up commit rather than a comment on a merge request. That asymmetry is also the argument for passing `--review true` on anything that turned out bigger than it looked.

### 5f. Hand the run to `autopilot`, unless `--autopilot false` was passed

In the same turn that the description and the re-printed commit message go out, invoke the `autopilot` skill using the `Skill` tool and pass it the resolved flag state from Step 0 — `--branch`, `--diagram`, `--review`, `--merge`, `--max-rounds` — as **values, not as the user's original argument string**, so an amendment made mid-run is not silently rolled back to a machine default.

**The hand-off is not a question.** Autopilot is on because this machine's `fix_autopilot` says so, or because the user said so; either way the decision is already made. Say in one line that you are handing over and what the run will do when it gets there — "Handing to autopilot: push, open the MR, work the review, merge when it is green" — then hand over.

What crosses the hand-off is the *state*, not the invocation: the branch, the worktree, the commits, the commit message and the description all already exist, and autopilot starts at its Step 2 rather than re-entering this skill.

**On `--branch default` the hand-off still happens, and it is short.** There is no merge request to open, so autopilot pushes the default branch at its Step 4a, records the commit, and ends with a report saying the change is live and nobody reviewed it. That is the trade `--branch default` makes; it is the user's to make, and it is the one fact they need back from a run they were not watching.

## Important Rules

1. **This skill never pushes and never opens a merge request — the hand-off does.** Local git is yours: creating a branch, creating a worktree, and committing are all fine. Pushing, opening a merge request and merging belong to `autopilot`, which owns them from 5f onwards under its own rules. That is a statement about which skill is accountable, not a prohibition on the run, and it is what makes `--autopilot false` reliably mean *nothing left this machine*. Never quote this rule back as a reason to refuse the hand-off. **`--branch default` means the commit lands on the default branch, not that it is unreviewed by accident.** That distinction matters more here than anywhere else in these skills: a stray push of a feature branch creates a branch nobody asked for, while a stray push of the default branch is a direct write to the branch every other checkout, every CI pipeline, and (with Atlantis) every apply is cut from. So do not run `git push` in any form — not with `-u`, not as a `--dry-run` "check", not because "it would be rejected anyway" — and do not create a merge request. Pushing is the user's explicit action, always. Never remove a worktree the user didn't ask you to — cleanup is the user's call. **This rule scopes to this skill's own flow.** Naming `/autopilot` in the arguments *is* the user's explicit action, and it hands the run to a skill that owns pushing and merging under its own rules — see **Delegation** above, and never quote this rule back as a reason to refuse it.
2. **Respect uncommitted work.** Never discard or stash uncommitted changes without the user's explicit approval. A dirty tree escalates the branch mode (Step 2b); it never gets cleared to keep the cheap path.
3. **Ask, don't assume.** If the problem statement is vague, ask the user rather than guessing — and where the statement and the code disagree, the code wins and you say so out loud.
4. **Follow existing patterns.** Match the coding style, naming conventions, and architecture of the existing codebase.
5. **Keep the user informed.** Summarize what you're doing at each major step, and announce every escalation in one line as it happens, with the reason.
6. **No comments in the code.** Do not add explanatory comments, docstrings, or references to the request in code you write or modify — the full rule is in Step 4. Explanation goes in the commit message and MR description, never the source. Machine-read directives (linter suppressions, build pragmas, a doc-comment CI requires) are program input, not commentary, and stay allowed.
7. **Escalation is one-way within a run.** Once the Terraform or protected-branch check has fired, `--branch default` is off the table for the rest of the run even if the user restates the flag — explain why rather than complying. The dirty-tree check is the one that can clear: if the user commits or stashes their own work themselves, re-run `git status --porcelain` and the default-branch path is available again.
