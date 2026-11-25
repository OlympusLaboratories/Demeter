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

### Publish the run checklist — before Step 1, not later

This run owes a dozen things in a fixed order, across a context long enough to be compacted, and neither this file nor your notes are a record of which ones are still outstanding. The checklist is that record: **one published page, seeded from the resolved flags, re-read and updated in place as the run advances**, which the user refreshes to see where the run is. `autopilot`'s **The run checklist** section owns the full contract — the per-machine store, the URL-stability rule, the item shape — and `~/.claude/scripts/run-checklist.py rules` prints the guarantees. This step owes the first publish.

Seed it from the values Step 0 just resolved, so the page cannot list an obligation this run does not have:

```bash
~/.claude/scripts/run-checklist.py template \
  --title '<the change in a few words>' \
  --repo '<repository name>' --branch 'BRANCH_NAME' \
  --request-name "$(~/.claude/scripts/skill-env.sh get change_request)" \
  --branch-mode new > <items>.json
~/.claude/scripts/run-checklist.py publish <items>.json
```

Pass `--review`, `--diagram` and `--merge` for each of those flags that resolved true, and `--branch-mode default` on a `--branch default` run. `publish` prints `url=`, `hash=` and `page=`.

**Record the url and the hash beside the seven flag values.** Every later write is an `--update` against that hash. A second plain publish is not a cosmetic mistake: it mints a new link, leaves the one the user is holding frozen at step one, and nothing reports it.

**Exit `3` means this machine has no self-hosted store.** Publish the rendered `page=` file with the **Artifact** tool instead, record the url it returns, and make every later write a publish with that same url. If neither store works, keep the local file, say so in one line, and carry on — the run is not contingent on the page.

**Report the link in the same line as the flag resolution**, or immediately after it. It is what the user opens to watch the run, so a link that arrives buried six steps later is worth nothing.

> `branch new · one-shot description · no diagram · no swarm · autopilot, merging when green · checklist: <url>`

**Then tick each item in the same tool-call batch as the step that completes it**, with one command rather than three:

```bash
~/.claude/scripts/run-checklist.py tick <items>.json \
  plan=done 'implement=in-flight:the approved plan' --publish
```

The plan gate, the implementation, the commit message and the description are each an item here. **Never tick in a batch at the end**: the page exists so somebody can refresh it mid-run, and a page caught up only at the finish is a page that was wrong for the whole run — measured on the run that built this feature, which left it reading `commit: in flight` while a review swarm was already going.

**A branch-mode escalation changes the run's shape** — whether it fires at Step 2b or at Step 2e after work has started — so re-seed the page when one does, as an update against the recorded hash, rather than leaving the checklist describing a `--branch default` run.

### Autopilot is on unless it is switched off

`fix_autopilot` is `true` on every profile, so **the ordinary run of this skill ends at a merge request, not at a commit message.** Once the implementation and the deliverables are done, 5f hands the run to `autopilot`, which owns the push, the merge request, the pipeline watch, the review rounds, the infrastructure apply, and — when `--merge` is true — the merge itself.

**That does not mean this skill stops talking to the user.** Autopilot automates the *tail*. It does not close any of the gates before it, and in this skill those gates matter more than anywhere else: Step 1b exists precisely because a sentence typed in ten seconds is the least-reviewed input any of these skills take, and an unattended tail is not a reason to stop restating the request, stop checking its claims against the code, or stop reaching for `AskUserQuestion` when the answer changes the implementation. The decisions autopilot makes alone are the ones after the code is written, which is the point at which the user stopped watching.

`--autopilot false` is the way back to implementation only — a branch, a commit message, a description, and nothing that leaves this machine. It is the flag for a spike, or for anything you want to look at before it becomes somebody else's notification.

### `/autopilot` can amend the run at any point

The user may run `/autopilot <flags>` while this skill is working — to turn on a diagram they have decided they want, or to hold a merge they had been happy to let go. That is an **amendment to this run**, not a new run and not a question to put back to them. Apply it per `autopilot`'s *Amending a run in flight* section: change only the flags they named, leave every other flag at its **current** value rather than resetting it to the machine default, say in one line what changed and what it caused to happen now, and carry on from where you were.

A bare `/autopilot` token inside the *initial* invocation is now redundant rather than wrong — autopilot is already on. Strip it, apply any flags it carries, and say nothing further about it.

### A `/ping` token in the invocation means the user is away

Strip it from the problem statement, then **send the opening ping at Step 0**, in the same tool-call batch as the checklist publish, with the checklist URL in the body. Tick `arm=done` in that batch too.

Do not defer it to the `autopilot` hand-off. That is a dozen steps and often hours later, and until a ping lands the session is **mute**: `notify.py` writes `armed_at` only on a successful send, so every turn end, permission prompt and failure before the hand-off is logged as `skip: session not armed` and reaches nobody. A user who typed `/ping` typed it because they are walking away now. Observed: a run took `/ping` in its invocation, sent nothing for its whole first half, and the user's first words were that they had never received the link.

Arming early is safe in both directions. `armed_at` is a latch only `/ping off` clears, and a failed send writes nothing — so an unconfigured `~/.claude/notify.json` leaves the run exactly as it would have been. Report what it said in one line and carry on; the work is never contingent on the notification.

If the token carries a note — `/ping tell me when the plan is up` — pass that note to the `ping` skill as the body hint. A run **without** the token is unchanged: it still arms at the hand-off.

## Step 1: Understand What Is Being Asked

### 1a. Get the user's first name

```bash
git config user.name
```

Extract the **first name** (the first word, lowercased) and store it as `FIRST_NAME`. It is only used on the `--branch new` path, but it costs one command and the escalation in Step 2b can force that path at any point.

### 1b. Interrogate the problem statement

The absence of a ticket cuts both ways: nothing was lost in translation, and nothing was written down carefully either. Before any planning:

1. **Check that the tree you are about to read is current.** Everything below compares the statement against the code, and a checkout that is behind produces findings that are internally consistent, specific, and about code that no longer exists. Resolve the default branch first — the `git symbolic-ref` from Step 2a — then:

   ```bash
   git fetch origin <DEFAULT_BRANCH> --quiet
   git rev-list --count HEAD..origin/<DEFAULT_BRANCH>
   git log -1 --format='%cd' --date=short HEAD
   ```

   **Report the gap before you verify anything** — the commit count and the date of `HEAD` — then apply the threshold:

   - **0 commits behind.** The working tree is authoritative. Read it normally.
   - **1 or more.** Test each path you are about to check a claim against, in both directions. `git log --oneline HEAD..origin/<DEFAULT_BRANCH> -- <path>` says whether upstream moved it; no output means the working tree is still authoritative for that path. Output means it did, and then `git log --oneline origin/<DEFAULT_BRANCH>..HEAD -- <path>` decides what to do about it. Silent, and the branch has not touched that path, so read it with `git show origin/<DEFAULT_BRANCH>:<path>`. **Not silent, and you never read the upstream blob** — it carries none of this branch's own work, which on a base that is itself a feature branch means the whole predecessor. Merge `origin/<DEFAULT_BRANCH>` in and read the result, or say the two have diverged on that path and treat every claim about it as unsettled.
   - **`git show` exits `fatal: path … does not exist in origin/<DEFAULT_BRANCH>`.** Not an error to route around — it is the answer. The path is gone upstream, renamed or deleted, so any claim naming it is a claim about a file that no longer exists. Report that as the finding.
   - **`HEAD` more than 7 days old.** Run the per-path test over every path you touch rather than only the ones the statement names. The per-path log *does* report a rename of a path you name, for the old path and the new one alike, so what defeats it is never naming the path at all — which is exactly what happens when a symbol moved and you are still grepping where it used to live. At a week's distance, assume that has happened.

   Resolving the default branch here repeats one read-only command from Step 2a. That is deliberate — Step 2a stays where it is, and repeating a `symbolic-ref` costs nothing against reading the wrong tree.

   **Every repository the run reads gets this, not only the one you are sitting in.** A second repo reached by `git -C <abs path>` gets the same three commands, **fetch included**, against **its own** default branch. The real failure involved two repos and the second stale one was caught by accident.
2. **Restate it in one sentence** and show the user: "You want X." Your reading of the request, not a paraphrase of their words. If your sentence is longer than theirs, you have not understood it yet — ask.
3. **Separate the symptom from the guess.** A freeform statement is usually a symptom plus a hypothesis about the cause ("the sync is slow, probably the N+1 in the loader"). The symptom is the requirement; the hypothesis is a thing to test. Implementing the hypothesis and leaving the symptom in place is the most common way this skill fails, and it fails while looking finished.
4. **Verify every factual claim in the statement against the code, before planning.** `fix-linear` has to do this to tickets because a ticket written during research routinely overstates ("every row is wrong", "X carries no Y") or describes a pre-implementation design that shipped narrower. A statement typed into a prompt in ten seconds is **more** prone to that, not less — nobody reviewed it, not even its author, and there is no description field where a second thought could have landed. Concretely:
   - Every path, symbol, function, flag, and config key the statement names: confirm it exists and is spelled that way. Glob or `rg` for it; do not trust the name. Half the paths quoted from memory are wrong in a way that still reads plausibly (`registry.py` for `rule_registry.py`).
   - Every count ("three call sites", "only used by the CLI"): count it yourself.
   - Every behavioural claim ("it retries forever", "the default is 30s"): read the line that sets it.

   **Where the statement and the code disagree, implement what the code says and say so** — quote the claim, name the file and line that contradicts it, and state what you are doing instead. Never correct it silently: that gap is often the most interesting thing in the request, and it is sometimes the actual bug. **None of that is authoritative until the tree is known current.** If item 1 reported a gap and you have not read the contradicting line through `origin/<DEFAULT_BRANCH>`, say the tree is behind and read it there before you quote the claim back. Telling the user their statement is wrong on the strength of a stale checkout is worse than never checking it, because they believe you.
5. If the request is still ambiguous in a way that changes the implementation, use `AskUserQuestion` before planning. Asking is cheaper here than on a ticket — the author is right there — and a wrong guess costs exactly as much to review either way.

State the result of this step in a few lines before moving on: the gap between `HEAD` and `origin/<DEFAULT_BRANCH>`, the one-sentence restatement, anything the code contradicted, and anything you asked about.

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

**Work that spans two repos is still workable from one worktree-isolated session — use `git -C <abs path>`.** `cd ~/other-repo && git status` is refused ("changes directory to a location computed at runtime before running git"), but `git -C /Users/…/other-repo status` is accepted, and so is `git -C <repo> worktree add -b <branch> <path> origin/main`. Read/Edit/Write against absolute paths in the other repo are not blocked either. Ask the user early whether they want the second repo driven in the same session or left as a follow-up — it changes how much gets done here. **Give that repo Step 1b's freshness check before you read anything in it** — the same three commands under `git -C <abs path>`, fetch included, against that repo's own default branch. Nothing in this skill has fetched it, so a count taken without that fetch reads a ref exactly as stale as the checkout it is judging.

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

Carry Step 1b's findings with you — the restatement, anything the code already contradicted, and whether the tree is current — and then:

1. **Explore the codebase** — use Glob, Grep, and Read to understand the relevant files, existing patterns, and architecture. Step 1b checked the statement's claims; this step is where you find what it never mentioned, which on a freeform request is most of it. The statement names what the user noticed; the plan has to cover what the change actually touches.

   **Do not trust a call-site count, and do not stop at the obvious grep.** Grepping for a constructor misses call sites that go through a test helper: `rg 'Owner\('` found nine, while two more reached the model as `owner(fetch=..., transform=...)` via the `owner()` factory in `tests/conftest.py`, and only the type-checker caught them. When deleting a field or parameter, also grep for the *lowercase helper* and any `**kwargs` forwarder — or treat the first typecheck run as part of discovery rather than as verification.

   **`rg -r` is `--replace`, not "recursive".** `rg -rn 'foo-bar' .` silently rewrites every match to `n` in the output, which reads as a real but wrong result (it made a bucket named `ftl-local-dev` appear to be named `n`, sending me down a false trail). ripgrep is recursive by default; never pass `-r`.
2. **Design an implementation approach** — identify which files need changes, what the changes are, and in what order.
3. **Confirm the branch mode still holds.** If exploration shows the change reaches a `*.tf` file, or any other Step 2b condition, say so in the plan and escalate before implementing (Step 2e).
4. **Ask clarifying questions** — if the problem statement is ambiguous or missing details, use `AskUserQuestion` to clarify with the user before finalizing the plan.
5. **Plan into the reply, publish, send the link alone, then gate on it — in that order.** Write the full plan into your reply for the terminal **first**, ahead of the publish. Then publish it as a page, send the URL as **its own message carrying nothing but the URL**, and call `AskUserQuestion`. Options are `Approve` and `Change something`. Treat anything other than a clear approval as a revision and plan again. Do **not** call `ExitPlanMode`; this skill never enters plan mode, so there is nothing to exit.

**Publish the plan first, so the gate can hand over a link to the whole thing.** Render the plan as a self-contained HTML page and publish it:

```bash
~/.claude/scripts/publish-artifact.sh <plan>.html \
  --purpose plan \
  --expires 7d \
  --title '<the change in a few words>' \
  --description 'implementation plan'
```

It prints the URL. `--purpose plan` is the whole of the configuration: the script looks up `plan_folder` itself, omits the folder flag when that key is empty, and publishes the page **public**, so the person reading it needs no session. A page published privately is a 404 to everybody but an admin, which is the one reader this gate does not need to reach. **Never pass `--folder` with a name of your own**, since publishing refuses a folder that does not exist. Resolving all of it inside the script is deliberate: the conditional form this replaced, `${FOLDER:+--folder "$FOLDER"}`, splits into two arguments in bash and stays **one** in zsh, so it shipped `--folder PRtifacts/Plans` as a single fused argument and every publish failed on the shell these commands actually run in. `--expires 7d` is deliberate: a plan is worth reading while it is being approved and clutter a fortnight later.

**Exit status 3 means this machine has no self-hosted store.** That is the ordinary answer on most of them and not a failure — publish the same HTML with the **Artifact** tool instead and use the link it returns. Any other non-zero status is a real failure: say what it printed in one line, then ask the question with no link. **Never hold the gate open waiting for a link.** A plan the user can only read in the terminal still gets approved; a question that never arrives strands the run.

**Send the link as a message of its own, immediately before the question.** `AskUserQuestion` renders no links, so a URL inside the question text arrives as characters nobody can tap — on the phone screen this whole gate exists to serve. The chat message before it is clickable and is the last thing on screen when the question lands, so that is where the link goes, on a line of its own.

**That message carries the URL and nothing else**, and "nothing else" is the load-bearing half. No plan, no summary of the plan, no restatement of the change, no account of what happens once it is approved, no closing offer. Each of those is prose the reader has to scroll past to reach the only actionable thing on the screen, and they do not read it — the page is where the plan is, which is why it was published. A bare label in front of the URL is the most that earns its place. This is also why the plan prose goes into the reply **ahead of** the publish rather than beside the link: the terminal copy still earns its keep as the fallback for a publish that fails, and in front of the publish it cannot wedge itself between the link and the question.

**Publishing the plan and asking the question are one turn. Never end the turn between them.** This is the failure the whole gate is built to avoid, and it has happened: the plan was published, the link was posted, the turn ended, and the run sat waiting on an approval nobody had been asked for. Publishing feels like the deliverable, so the turn reads as finished — but a published plan is nothing except the thing a question is about. No tool call belongs between the publish and the `AskUserQuestion`, and nothing is worth one more exploratory check first.

The cost of ending that turn is paid entirely by the user, which is why it is so easy to miss. Turn-end notifications are suppressed on a session nothing has armed yet, and the arming ping does not go out until the hand-off to `autopilot` — which is several steps away, past the gate. The gate question is the one event that notifies on an unarmed session. Skip it and the run is silent with the plan ready: no notification, no question, and nothing on the user's phone to tap.

`publish-artifact.sh --purpose plan` records the URL in the session state, and the `Stop` hook **refuses the first turn end that leaves it set** — it blocks the stop and hands back the instruction to ask, so the question happens before the turn can finish. A turn that ends with the marker set a second time is not blocked again; the hook notifies instead, even on an unarmed session. **Treat both as a smoke alarm, not a safety net.** Being sent back to ask costs a turn, and the notification behind it costs another and arrives saying "waiting on you" rather than asking the actual question. Asking in the same turn as the publish is the only version that costs nobody anything. If a plan genuinely needs no question — the user approved it in advance, or it was published for the record — clear the marker with `~/.claude/hooks/notify.py --gate-clear` rather than letting the interlock fire.

**The question itself carries no plan.** One line naming the change, then `Approve` and `Change something`, and nothing else. The compressed per-file summary this replaced was written when the question text was the only copy that reached the phone; with a link one tap above it, that summary is a second and worse copy of the plan, and it fills the screen the question is read on. A question reading only "approve the plan?" would still strand the user, which is why the link is a hard requirement of this step rather than a nicety — and why a failed publish is reported in one line rather than waited on. `ExitPlanMode` was never an option here: the hook sends the fixed string `Waiting for plan approval.` for it and never the plan. State the branch mode in the plan: which branch the work will land on, and whether an escalation fired.

While the question is open the plan item on the run checklist is `in-flight`, waiting on the user — which is the one state that makes a stalled gate visible on the page rather than only in the transcript. Once the user approves, tick it and **record the plan page's URL on the checklist in the same command**:

```bash
~/.claude/scripts/run-checklist.py tick <items>.json \
  plan=done 'implement=in-flight:the approved plan' \
  --run plan_page=<the published plan url> --publish
```

`plan_page` is how the URL reaches the merge request's description at `autopilot` Step 4b. The items file is the one piece of run state that survives both the hand-off and a pause, so recording it here is what stops the link depending on a context window that gets compacted — the same argument that put the run's obligations on a page in the first place. A run whose publish failed has no URL and records none: the field stays empty and Step 4b writes no line.

Then implement the changes.

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

**The checklist crosses the hand-off as state, not as a fresh publish.** Tick the commit-message and description items, then give `autopilot` the page's url and its update hash along with the flags. It adopts that page and keeps writing to it; a second publish there would hand the user's existing link to a checklist that stops at step five. **The items file goes with it**, not just the url and the hash: `plan_page` lives in there, and Step 4b writes the change request's description from it.

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
