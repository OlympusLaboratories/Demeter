# Fix — Linear Ticket Implementation

Implement the changes required by a Linear ticket, and — unless you are told otherwise — take it all the way to a change request that is ready to merge.

**Parameter:** `$ARGUMENTS` — a Linear ticket identifier, plus optional flags.

| Argument | Env key | Effect |
|---|---|---|
| A Linear ticket identifier (`ENG-123`, `PLAT-3276`) | — | **Required.** The ticket to implement. |
| `--branch new\|default` | `fix_branch` | `new` cuts `<FIRST_NAME>/<TICKET_ID>` off the default branch in its own git worktree. `default` commits onto the repository's default branch — no feature branch, no worktree, no merge request. **Step 2** owns this, and three conditions can force `new` whatever the flag said. |
| `--quick-description [true\|false]` | `fix_quick_description` | `true` passes `--inline` to `changes-description`: **no workflow at all**, the description written in the same turn against that skill's template, measured word budget and fact-check. The run then goes straight on to the hand-off. `false` runs the full four-persona debate, which yields the turn until the swarm reports. |
| `--diagram [true\|false]` | `fix_diagram` | Run `changes-diagram` and attach the published page to the merge request. |
| `--review [true\|false]` | `fix_review` | Run the `review-code` adversarial swarm over this branch's diff, and feed its confirmed findings through `fix-feedback`. |
| `--autopilot [true\|false]` | `fix_autopilot` | `true` hands the finished implementation to `autopilot`, which pushes, opens the merge request, works the review and merges. `false` stops at the commit message and the description, and nothing leaves this machine. |
| `--merge [true\|false]` | `fix_merge` | `autopilot`'s flag, forwarded. `false` drives the run to a green pipeline, a clean review and a ready merge request, then stops without merging. |
| `--max-rounds N` | `fix_max_rounds` | `autopilot`'s flag, forwarded. Review rounds with the same reviewer before escalating. |

**No default is written in this file.** Every one of them differs between machines, so **Step 0** reads them out of `skill-env.sh` and a flag in the invocation overrides whatever came back. A bare flag means `true` — `--diagram` and `--diagram true` are the same thing. Run `~/.claude/scripts/skill-env.sh check` to see what an unflagged run does here.

Parse the flags out of `$ARGUMENTS` **first**; whatever remains is the ticket identifier. Without that, `PLAT-123 --diagram false` is taken whole as the ticket ID and fails validation in Step 1b. If nothing remains once the flags are stripped, ask the user for the ticket ID and stop.

## Step 0: Resolve the Defaults

```bash
~/.claude/scripts/skill-env.sh check
```

Read `fix_autopilot`, `fix_branch`, `fix_quick_description`, `fix_diagram`, `fix_review`, `fix_merge` and `fix_max_rounds`, lay any flag the user passed over the top, and **write the seven resolved values down where you can still see them hours later** — a todo, or a line in your notes. They are not read once: `--merge` decides the end of the run, and `/autopilot` can amend any of them mid-flight, at which point *what is this run set to* has to be answerable without re-deriving it.

Then state the resolution in one line before doing anything else:

> `PLAT-3276 · branch new · full description · diagram · review · autopilot, stopping before the merge`

Every one of those costs the user something, and a wrong default is cheapest to catch here. A key missing from `skill-env.sh` is not an error — it carries working defaults in code, so an absent or malformed `~/.claude/environment.json` degrades to them rather than breaking the run.

### Publish the run checklist — before Step 1, not later

This run owes a dozen things in a fixed order, across a context long enough to be compacted, and neither this file nor your notes are a record of which ones are still outstanding. The checklist is that record: **one published page, seeded from the resolved flags, re-read and updated in place as the run advances**, which the user refreshes to see where the run is. `autopilot`'s **The run checklist** section owns the full contract — the per-machine store, the URL-stability rule, the item shape — and `~/.claude/scripts/run-checklist.py rules` prints the guarantees. This step owes the first publish.

Seed it from the values Step 0 just resolved, so the page cannot list an obligation this run does not have:

```bash
~/.claude/scripts/run-checklist.py template \
  --title 'TICKET_ID: <the change in a few words>' \
  --repo '<repository name>' --branch 'BRANCH_NAME' --ticket 'TICKET_ID' \
  --request-name "$(~/.claude/scripts/skill-env.sh get change_request)" \
  --branch-mode new > <items>.json
~/.claude/scripts/run-checklist.py publish <items>.json
```

Pass `--review`, `--diagram` and `--merge` for each of those flags that resolved true, and `--branch-mode default` on a `--branch default` run. `publish` prints `url=`, `hash=` and `page=`.

**Record the url and the hash beside the seven flag values.** Every later write is an `--update` against that hash. A second plain publish is not a cosmetic mistake: it mints a new link, leaves the one the user is holding frozen at step one, and nothing reports it.

**Exit `3` means this machine has no self-hosted store.** Publish the rendered `page=` file with the **Artifact** tool instead, record the url it returns, and make every later write a publish with that same url. If neither store works, keep the local file, say so in one line, and carry on — the run is not contingent on the page.

**Report the link in the same line as the flag resolution**, or immediately after it. It is what the user opens to watch the run, so a link that arrives buried six steps later is worth nothing.

> `PLAT-3276 · branch new · full description · diagram · review · autopilot, stopping before the merge · checklist: <url>`

**Then tick each item in the same tool-call batch as the step that completes it**, with one command rather than three:

```bash
~/.claude/scripts/run-checklist.py tick <items>.json \
  plan=done 'implement=in-flight:the approved plan' --publish
```

The plan gate, the implementation, the commit message and the description are each an item here. **Never tick in a batch at the end**: the page exists so somebody can refresh it mid-run, and a page caught up only at the finish is a page that was wrong for the whole run — measured on the run that built this feature, which left it reading `commit: in flight` while a review swarm was already going.

**A branch-mode escalation at Step 2b changes the run's shape**, so re-seed the page when one fires, as an update against the recorded hash — otherwise a forced feature branch leaves the checklist describing a `--branch default` run.

**A second branch in the same session is a second run, and owes a checklist of its own — unless it is a planned member of a stack.** A stack is seeded as one page with `run-checklist.py template --stack '<member>|<member>'`, which declares a stage per member and records every member's branch in the session marker, so moving between them never holds a turn end. Everything below is for the unplanned case: a branch this run cut without a stage to put it in. That is not the re-seed above: the first page is still the record of the first branch's obligations, and its link is already in that change request's description. Seed a new items file for the new branch, publish it, and write to both pages from then on. The `Stop` hook holds the first turn end where the session stands on a branch that **no** tracked page claims, and says which of the two cases it is — so a fork is caught rather than left untracked, which is what happened the one time a run did this. Several pages in one session is not a fork and never holds: the session marker keeps a record per page, so every page's branch is compared and every page's staleness is counted on its own.

### Autopilot is on unless it is switched off

`fix_autopilot` is `true` on every profile, so **the ordinary run of this skill ends at a merge request, not at a commit message.** Once the implementation and the deliverables are done, Step 6 hands the run to `autopilot`, which owns the push, the merge request, the pipeline watch, the review rounds, and — when `--merge` is true — the infrastructure apply and the merge itself. **`--merge false` holds both**: an apply is the landing of an infrastructure change, not a step towards it, so a run told not to merge is told not to apply.

**That does not mean this skill stops talking to the user.** Autopilot automates the *tail*. It does not close the gates in Steps 1 through 5: a vague ticket still gets a question, an ambiguous requirement still gets `AskUserQuestion`, and a plan worth seeing still gets shown. The decisions autopilot makes alone are the ones after the code is written, which is the point at which the user stopped watching.

`--autopilot false` is the way back to implementation only — a branch, a commit message, a description, and nothing that leaves this machine. It is the flag for a spike, or for anything you want to look at before it becomes somebody else's notification.

### `/autopilot` can amend the run at any point

The user may run `/autopilot <flags>` while this skill is working — to turn on a diagram they have decided they want, or to release a merge they were holding. That is an **amendment to this run**, not a new run and not a question to put back to them. Apply it per `autopilot`'s *Amending a run in flight* section: change only the flags they named, leave every other flag at its **current** value rather than resetting it to the machine default, say in one line what changed and what it caused to happen now, and carry on from where you were.

A bare `/autopilot` token inside the *initial* invocation is now redundant rather than wrong — autopilot is already on. Strip it, apply any flags it carries, and say nothing further about it.

### Arm the phone at Step 0, on every run

**Send one ping before Step 1, whatever the invocation said**, via the `ping` skill with the `Skill` tool, in the same tool-call batch as the checklist publish. Level `progress`: the work is starting and continues. The body names the ticket and what is being done to it, and carries the checklist URL — the one thing the user can act on while the run is still young. Tick `arm` in that same batch.

Do not defer it to the `autopilot` hand-off. That is a dozen steps and often hours later, and until a ping lands the session is **mute**: `notify.py` writes `armed_at` only on a successful send, so every turn end, permission prompt and failure before the hand-off is logged as `skip: session not armed` and reaches nobody. The window that covers is almost the whole of this skill — the ticket, the plan gate, the implementation and the description all sit in front of the hand-off, and they are precisely the steps a user walks away from. Observed from both ends: a run took `/ping` in its invocation, sent nothing for its whole first half, and the user's first words were that they had never received the link; and a run that typed no token at all reached its plan gate with nothing on their phone to tap.

**The justification is this skill's own, and it is deliberately not autopilot's.** `autopilot` Step 0d arms because engaging autopilot is the gesture that says the user is walking away. Starting a fix run is not that gesture — they are usually at the keyboard as they type it. What holds here instead is the asymmetry of the latch: **arming early costs one notification the user is present to ignore, and arming late costs every silent failure before the latch.** Arming early loses nothing, because `min_interval_seconds`, the turn-length floor and quiet hours all still apply to everything that follows. Arming late loses the events themselves, which cannot be recovered once they have gone nowhere.

**Skip it when the session is already armed.** Read `~/.claude/notify-state/sessions/<session-id>.json`; an `armed_at` already present means the user has pinged this session before and the automatic notifications are live. Say so in one line and move on rather than sending a second announcement.

**`--autopilot false` arms too, and that is this skill's decision rather than an inherited one.** Autopilot's rule — *never arm when `--autopilot false`* — is scoped to its own unattended tail, which such a run never reaches. Reading it as a rule about this skill would leave the plan gate of every spike silent. A run that stops at a commit message still has a gate the user can walk away from, and the latch asymmetry above does not care how the run ends.

**A failed send never fails the run.** A missing or unconfigured `~/.claude/notify.json` makes the ping a no-op, and the `ping` skill deliberately does not write `armed_at` on a failed send. Report what it said in one line and carry on — the work is never contingent on the notification.

**Tick `arm` with the outcome rather than the intention**: `done` on a send, `skipped` with the reason on a failure or on an already-armed session. It is item 1 of the checklist because it is the obligation these skills demonstrably skipped, and an item ticked `done` on a send that never landed is worse than no item at all.

A `/ping` token in the invocation no longer decides *whether* to arm, since every run arms. Strip it from the invocation and read it for what it still tells you: the user is confirming they are away, so the body is worth the extra care, and a note it carries — `/ping tell me when the plan is up` — is a body hint to pass to the `ping` skill.

## Step 1: Identify the User and Ticket

### 1a. Get the user's first name

```bash
git config user.name
```

Extract the **first name** (the first word, lowercased) and store it as `FIRST_NAME`.

### 1b. Validate the ticket ID

Store `$ARGUMENTS` (trimmed, uppercased) as `TICKET_ID`. It should match a pattern like `TEAM-123`. If it doesn't look like a valid identifier, warn the user and stop.

### 1c. Compute the branch name

The target branch name is `FIRST_NAME/TICKET_ID` — e.g., `dylan/ENG-123`. Store this as `BRANCH_NAME`.

The identifier must survive into the branch name literally. It is one of the two things the forge integration matches to link the merge request back to the ticket — the other is the identifier in the merge request title, which `autopilot` Step 4b sets — and a link that never forms means the ticket stays in its pre-review state after the work merges, with nothing reporting it.

### 1d. Confirm the ticket is still work to do — before the worktree exists

A completed or canceled ticket is not a change to implement, and nothing later in this skill will notice. Step 3d reads the ticket's status and only *prints* it; Step 3e branches on the ticket's content and never on its state. So settle the state here, where the answer is still free: Step 2 cuts a branch and a worktree, and a ticket read after that has already cost both.

Load `mcp__claude_ai_Linear__get_issue` via `ToolSearch` (query: `select:mcp__claude_ai_Linear__get_issue`) and call it with `id: TICKET_ID` and a narrow selection:

```
fields: ["id", "title", "status", "statusType", "completedAt", "canceledAt", "url", "attachments"]
```

The selection is deliberately narrow — no description, no relations — because Step 3a still makes the full call. Two fields are the reason it is spelled out. **Read `statusType`, never `status`**: `status` is the team's own display name for the column and teams rename those, while `statusType` is a fixed enum (`backlog`, `unstarted`, `started`, `completed`, `canceled`, `triage`). And **`attachments` is where the closing merge request lives**, as a `title` and a `url`; it is the one field that names what shipped the work.

**`statusType` of `completed` or `canceled` — do not proceed to Step 2.**

Verify the claim from the repository rather than trusting the field, using the trick Step 2e already documents: a squash merge leaves `git merge-base --is-ancestor` false while the commit subject is present in the log, so grep for the identifier.

```bash
git fetch origin <DEFAULT_BRANCH> --quiet
git log origin/<DEFAULT_BRANCH> --oneline --grep='<TICKET_ID>'
```

Compute `DEFAULT_BRANCH` as in Step 2a first. Then report, in one short block:

- the status and `statusType`, and the `completedAt` or `canceledAt` date,
- every attachment's title and url — the merge request that closed it,
- the landed commit where the grep confirms one, or a plain statement that none could be confirmed from the repository.

**An unconfirmed merge is not evidence of an open ticket.** The grep finds nothing when the work landed with no identifier in its subject, when it shipped from another repository, or when the ticket was canceled rather than completed. Say the repository could not confirm it and let the state field stand; never upgrade a silent grep into permission to carry on.

Then ask with `AskUserQuestion` — options `Stop` and `Work it anyway` — and treat anything short of a clear "work it anyway" as a stop. **The ask is the point, not a formality.** Legitimate reasons to work a closed ticket exist: a follow-up, a revert, or a criterion the original run deliberately did not meet. That last one is the sharp edge and the reason this is a stop rather than a heuristic — **a completed ticket whose implementation deviated from its acceptance criteria reads, to a fresh run, exactly like an unfinished ticket.** Re-reading the criteria cannot tell the two apart, so the state field is the only signal there is, and a run that re-implements merged work would "fix" the deviation back.

**Any other `statusType` — say so in one line and continue to Step 2.** Name the status, because that line is the record that the state was checked rather than skipped.

## Step 2: Choose the Branch Mode

`--branch` decides where the work lands, and it has exactly two values.

- **`new`** — cut `BRANCH_NAME` off the up-to-date default branch and work in its own **git worktree**: a separate working directory on its own branch sharing the repo's `.git`, so several fixes can run in parallel (one session per worktree) without branch checkouts colliding. Continue at **2d**.
- **`default`** — commit straight onto the repository's default branch. No feature branch, no worktree, and no merge request, so an autopilot run pushes the default branch and ends there. Continue at **2c**.

`fix-freeform` resolves `--branch` with exactly these two values and the same three escalation checks. That is deliberate: the flag means the same thing in both skills, so neither one has a branch mode the other lacks. It carries no equivalent of Step 1d, and needs none — a freeform run has no ticket and so no state to be stale.

**Nothing here runs until Step 1d has found the ticket open.** Both branch modes commit, and `new` also cuts a worktree, so this is the step whose cost a closed ticket cannot be refunded. If a `completed` or `canceled` ticket somehow surfaces after a worktree exists — a run that skipped 1d, or a stack detour that reached Step 3 by another route — stop as 1d directs and **name the worktree path in the stop so the user can remove it**. Never remove it yourself: Important Rule 1 makes worktree cleanup the user's call, and that rule does not carve out a worktree this run created.

**No-worktree fallback.** If the repo cannot host worktrees (`git worktree list` errors), use **Step 2-FALLBACK**, which takes `BRANCH_NAME` in the current checkout instead. That is a capability fallback, not a mode anybody selects — there is no flag for it, and `--branch` has no third value.

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

A ticket does not exempt a change from these. Run all three even when the user passed `--branch default` explicitly. When one fires, switch to `--branch new` and **announce it in one line naming the reason** — "Escalating to a feature branch: the change touches `*.tf`" — then continue at 2d.

**1. The change touches Terraform. This is a safety rule, not a preference.**

```bash
ls atlantis.yaml atlantis.yml 2>/dev/null
git ls-files '*.tf' '*.tfvars' | head
```

Escalate if the planned change will touch any `*.tf` or `*.tfvars` file, or if the repo carries an `atlantis.yaml` / `atlantis.yml`. Atlantis plans and applies from a **merge request branch**: the plan output is posted on the merge request, a human reads it, and the apply is gated on that read. A Terraform change committed straight onto the default branch skips the plan review entirely — nothing is posted anywhere a human looks, and infrastructure can be applied with nobody having seen what it would do. No "it is a one-line change" makes that acceptable, and the user cannot waive it with a flag. If the repo has `*.tf` files but you cannot yet tell whether this change reaches them, leave the question open and settle it in the plan (Step 4) — never by starting to edit and seeing what happens.

**2. The default branch is protected.** Detect this **before** committing, rather than discovering it when a push is rejected. The forge knows; git does not.

```bash
~/.claude/scripts/gitlab-api.sh help
```

`help` prints every subcommand the script actually has, each with the arguments it takes. Both are generated from the script's own source, so neither can drift from what is implemented, and it needs no token — it works on a machine with nothing configured yet. If that list includes one reporting protected refs (`protected-refs`), call it with the project path URL-encoded (`group%2Fsubgroup%2Frepo`, derived from `git remote get-url origin`) and look for `DEFAULT_BRANCH` in the result. **If the script carries no such subcommand, the call fails, or no token is configured, you cannot answer the question from here — escalate rather than guess.** An unneeded feature branch costs one `git worktree remove`; a rejected push costs a commit stranded on the branch it was least welcome on.

**3. The working tree already has unrelated uncommitted changes.**

```bash
git status --porcelain
```

If the tree is dirty with work that is not yours, escalate: committing on top of it mixes the user's in-progress work into your commit. The worktree gives you a clean tree and leaves theirs untouched. Never stash or discard it to clear this check — that is Important Rule 2, and it outranks the convenience of staying on the default branch.

**Escalation is one-way within a run.** Once a check has fired, `--branch default` is off the table for the rest of the run even if the user restates the flag — explain why rather than complying, because the commits now live on a branch created for exactly that reason. The dirty-tree check is the one that can clear: if the user commits or stashes their own work themselves, re-run `git status --porcelain` and `default` is available again.

Record which checks fired. It goes in the summary and in the commit context.

### 2c. `--branch default` — work on the default branch

No feature branch, no worktree, and **no merge request**. This is an unusual shape for a ticket — a ticket exists because somebody wrote the work down, which usually means somebody expects to review it — so say in one line that there will be nothing to review before carrying on. Then confirm you are actually on the default branch:

```bash
git rev-parse --abbrev-ref HEAD
```

- **If HEAD is `DEFAULT_BRANCH`**, bring it up to date without creating a merge commit:
  ```bash
  git fetch origin <DEFAULT_BRANCH> --quiet
  git merge --ff-only origin/<DEFAULT_BRANCH>
  ```
  If the fast-forward is refused, the local default branch has commits of its own or has diverged. Stop and tell the user what is there — do not resolve it with a merge commit on their default branch.
- **If HEAD is some other branch**, stop and ask which they meant. Working on whatever branch happens to be checked out is a different thing from what `--branch default` promises, and switching branches under the user silently is worse than either. If they answer "the branch I am on", continue here with that branch in place of `DEFAULT_BRANCH` — the protection check in 2b still applies to it.

Then go to Step 3. Everything after this runs in the current working tree, and an autopilot run ends at its own Step 4a with a pushed default branch and no merge request.

### 2d. Check whether you're already set up

```bash
git rev-parse --abbrev-ref HEAD
```

If the current branch already matches `BRANCH_NAME` (case-insensitive), you're already in the right worktree/branch. Fetch and merge the latest default branch, then skip to Step 3:

```bash
git fetch origin <DEFAULT_BRANCH> --quiet
git merge origin/<DEFAULT_BRANCH> --no-edit
```

If the merge has conflicts, stop and tell the user so they can resolve them before continuing.

### 2e. Create and enter the worktree

> **The base branch is not always the default branch, and only the ticket knows.** This step runs before Step 3 reads the ticket, so a ticket saying "branches off MR2" or "stacked on PLAT-1234" would get a worktree cut from the wrong base. When the ticket ID looks like part of a stack — a title carrying the `MR<n>` prefix, a parent initiative that sequences MRs — **fetch the ticket (Step 3a) and its siblings (Step 3f) first**, then come back here knowing the base. Before assuming a named predecessor is unmerged, check whether it already landed: a squash-merge leaves `git merge-base --is-ancestor <branch> origin/<default>` false while the *commit subject* is present in `git log origin/<default>`, so grep the log for the ticket ID rather than trusting the ancestry test. If it landed, the default branch **is** the right base and no stacking is needed.

Set `WORKTREE_PATH` to `.claude/worktrees/<BRANCH_NAME>` (relative to the repo root). Run these commands from the **main repo root**.

1. Fetch the latest default branch:
   ```bash
   git fetch origin <DEFAULT_BRANCH> --quiet
   ```
2. Check whether a worktree for this branch already exists:
   ```bash
   git worktree list --porcelain
   ```
   If `BRANCH_NAME` (or `WORKTREE_PATH`) is already listed, **enter it** with the `EnterWorktree` tool (`path:` = that worktree's path), merge `origin/<DEFAULT_BRANCH>` (`--no-edit`), then skip to Step 3 — its dependencies are already installed, so skip Step 2f too.
3. Check whether the branch already exists locally or on the remote:
   ```bash
   git branch --list <BRANCH_NAME>
   git branch -r --list origin/<BRANCH_NAME>
   ```
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

### 2f. Offer to install dependencies

A fresh worktree has no installed dependencies or build artifacts. Detect the project's package manager from files present in the worktree and **offer to run the install command — wait for the user's approval before running it**:

- `package-lock.json` → `npm install` · `yarn.lock` → `yarn` · `pnpm-lock.yaml` → `pnpm install` · `bun.lockb` → `bun install`
- `uv.lock` → `uv sync` · `poetry.lock` → `poetry install` · `requirements.txt` → `pip install -r requirements.txt`
- `go.mod` → `go mod download` · `Gemfile` → `bundle install` · `Cargo.toml` → `cargo fetch`

If several match, prefer the one matching the lockfile present. If none match, or the user declines, note that dependencies are not installed and continue.

**Never judge an install by a piped command's exit code.** `pnpm install 2>&1 | tail -25` exits with `tail`'s status, so a hard failure reports success. Run the installer bare, or check `${PIPESTATUS[0]}`.

**In `gridmatic-dev`, `pnpm install` needs a live GAR token and often cannot get one.** npm resolves through the foundation Artifact Registry, and `make npm-auth` mints the token via `gcloud`. In a non-interactive session `gcloud` frequently needs a reauth it cannot prompt for, so both `make npm-auth` and any `pnpm install` that must fetch metadata fail (`ERR_PNPM_FETCH_403`, or `ERR_PNPM_NO_OFFLINE_META` with `--offline`). Note also that `pnpm` is not on `PATH` — it comes from mise, so invoke it as `mise exec -- pnpm`.

When that happens, **Step 5's re-auth gate fires first** — say the GAR token needs minting, hand the user `make npm-auth && pnpm install`, ping, and ask. Then, while they re-authenticate, borrow the main checkout's already-installed tree rather than declaring the change unverifiable:

```bash
ln -s <MAIN_REPO>/apps/<app>/node_modules <WORKTREE>/apps/<app>/node_modules
mise exec -- <WORKTREE>/apps/<app>/node_modules/.bin/vitest run <paths>
```

Tests and lint run correctly this way. **Type-checking does not** — the borrowed tree's generated `@gridmatic/*` workspace packages belong to whatever commit the main checkout sits on, so `tsc -b` emits phantom errors (`Cannot find module '@gridmatic/notify-api'`) that have nothing to do with the branch. Report the count and confirm none are in the changed files rather than presenting it as a clean type-check. Remove the symlink when done — left in place it silently resolves imports against another checkout. The gate has already told the user what to re-run, so there is nothing to save for the end of the run.

**The symlink is required, not merely convenient, when the session is worktree-isolated.** A one-shot invocation of the binary by its absolute path in the main checkout — `mise exec -- /Users/…/gridmatic-dev/packages/<pkg>/ts/node_modules/.bin/openapi-typescript …` — is refused by the isolation guard ("too complex to verify that it stays inside the worktree"), and so is any command combining `cd`, a pipe, and an outside path. Create the symlink inside the worktree, invoke the binary through the *relative* `./node_modules/.bin/…` path, then delete it. The inner symlinks in a pnpm tree are relative to their real location, so they still resolve to the main checkout's store — this works.

**The isolation guard also refuses `cd … && cat > file <<'EOF' … EOF` and any pipe-plus-`$PIPESTATUS` one-liner.** It is not only about paths outside the worktree — a *shape* it cannot statically verify gets refused too, so writing a whole file via heredoc and writing a lint invocation as `… | tail; echo ${PIPESTATUS[0]}` both fail. Use the Write tool for whole-file content and the Edit tool for patches (they are never refused, and Write is faster than a heredoc anyway), and run linters/test binaries bare so their real exit code surfaces.

**The Bash working directory persists between calls, and a bare `cd` will strand you.** After `cd apps/portal`, a later `cd apps/portal` fails and a relative `ln -s packages/…` lands in the wrong place. Either issue every path absolutely, or re-`cd` to the worktree root as its own command before any step whose relative paths matter. `pwd` when a relative path fails unexpectedly.

**A ticket whose scope spans two repos is still workable from one worktree-isolated session — use `git -C <abs path>`.** PLAT-2528 needed a tlaloc-env branch and a gridmatic-dev docs branch. `cd ~/gridmatic-dev && git status` is refused ("changes directory to a location computed at runtime before running git"), but `git -C /Users/…/gridmatic-dev status` is accepted, and so is `git -C <repo> worktree add -b <branch> <path> origin/main`. Read/Edit/Write against absolute paths in the other repo are not blocked either. So: create the second repo's worktree with `git -C`, edit through absolute paths, and check both trees with two separate `git -C … status --porcelain` calls. Ask the user early whether they want the second repo driven in the same session or left as a follow-up — it changes how much gets done here, and the Step 3 "Done when" list often names a file that lives in the other repo. **Give that repo the Step 4 freshness check before you read anything in it, fetch included** — `git -C <abs path> fetch origin <its default branch> --quiet` first, then the same `rev-list --count` and `log -1` against that repo. Nothing in this skill has fetched it, so a count taken without that fetch reads a ref exactly as stale as the checkout it is judging and can only ever report `0`.

**Two more shapes the isolation guard refuses, both hit on PLAT-2460.** A `for` loop over scenarios (`for m in a b c; do terraform … -var mode=$m; done`), and a compound `A; echo ---; B; echo ---; C` that merely *inspects* things outside the worktree (`tfenv list`, `cat ~/.config/…`). Neither touches git and neither writes outside, but the guard is static: any multi-command shape it cannot unroll gets refused. Issue them as separate plain calls — batch the independent ones into one message so they still run in parallel. Note `terraform -chdir=<abs path>` *is* accepted, which is how to drive a scratchpad harness without `cd`.

**A multi-line script body naming `git` is refused where the same statements joined by `;` on one line are accepted.** Measured both ways from inside a worktree: `M=origin/main; A=$(git --no-pager diff "$M" -- . | wc -l); B=$(git --no-pager diff --name-status "$M" -- . | grep -c .)` runs, and the identical three statements on three lines do not. One `git` substitution on a line of its own is already enough to be refused. There is nothing to deduce about *which* git invocation offended, because none of them did. **Do not read that as "one line is safe"** — the guard judges the whole command's complexity, not its newlines, and these two measurements fix no boundary: three `;`-joined substitutions also ran, so where a one-liner stops being verifiable is unknown. The reliable move is separate calls, batched into one message when they are independent.

**The guard reads the command's *text*, not only its paths, so a heredoc body that merely mentions `git` is refused.** Piping a comment or a notification body into `~/.claude/scripts/gitlab-api.sh` or `~/.claude/hooks/notify.py` fails with *feeds &lt;script&gt; text naming git in a plain command* whenever that prose contains the word, even though nothing in the body executes and the same heredoc without the word runs. **A redirect from a file is the fix and is accepted**: the prose is then in the file rather than in the command, and both scripts read stdin either way. Write the file with the Write tool. `fix-feedback` and `ping` both carry this as a rule of their own, because posting a review comment about a `git` defect is the ordinary case rather than the corner one.

## Step 2-FALLBACK: Branch Checkout Without a Worktree

Use this **only** when `--branch new` is in force and the repo cannot host worktrees — it is the original single-working-tree behavior, kept as a capability fallback. Nobody selects it with a flag. Compute `DEFAULT_BRANCH` as in 2a and run the 2b checks first.

### Check the current branch

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

## Step 3: Fetch the Linear Ticket

Load the `get_issue` tool via `ToolSearch` (query: `select:mcp__claude_ai_Linear__get_issue`) if not already available.

### 3a. Fetch by identifier

Use `mcp__claude_ai_Linear__get_issue` with `id: TICKET_ID` and `includeRelations: true` (e.g., `PLAT-1180`). This returns the full issue including title, description, status, labels, assignee, relations, and — critically — the **`parent`** field.

**This is the full fetch; the ticket's state was already settled at Step 1d.** That step read `statusType` with a narrow `fields` selection and either stopped the run or recorded that the ticket is open, so do not re-litigate it here. The two calls are deliberately separate rather than one: 1d has to answer before Step 2 spends a branch and a worktree, and this one wants the description and the relations that 1d omitted.

**`get_issue`'s default response omits `parentId` entirely.** `includeRelations: true` adds blocks/blocked-by/related but *not* the parent, so the field is simply absent and reads as "no parent" when there may well be one. Make a second call passing `fields: ["id", "title", "parentId", "projectId"]` — a nonempty `fields` selection is the only way to surface it. Do this before concluding a ticket is parentless, and note that a project-level MR stack (siblings sharing the `MR<n>` title prefix with no shared parent) needs `list_issues` with `project:` rather than `parentId:`.

**Record the `parent` field now.** Explicitly note whether the issue has a parent and, if so, capture the parent's identifier. This determines whether Step 3f applies, and Step 3f is mandatory whenever a parent exists — do not lose this information between steps.

### 3b. If not found

Tell the user the ticket could not be located and ask them to provide the ticket title and description manually.

### 3c. Fetch ticket comments

After fetching the issue, also fetch all comments/discussion on the ticket. Use `ToolSearch` to discover the comments tool — try these queries in order until one returns a tool:
1. `select:mcp__claude_ai_Linear__list_comments`
2. `select:mcp__claude_ai_Linear__get_comments`
3. `+Linear comment`

If a comments tool is found, call it with the issue ID to retrieve all comments. If no comments tool is available, skip this step and note to the user that comments could not be fetched.

### 3d. Display the ticket

From the result, extract:
- **Title**
- **Description**
- **Priority**
- **Status**

Display a brief summary:
> **TICKET_ID: Title**
> Priority: ... | Status: ...
> Description (first ~3 sentences or 200 chars)

**Status is printed here because Step 1d acted on it, not instead of acting on it.** For a long time this list ended at a status nothing anywhere read, which is how a `Done` ticket reached planning: the field was on the screen and the run walked past it. Restate 1d's verdict beside the status so the line records a decision rather than a value.

**Backstop — if Step 1d did not run, settle the state now, before Step 3e.** Go back and do 1d in full: the narrow fetch, the `git log` grep, the report, and the ask. Then follow the Step 2 rule for a worktree that already exists — name its path in the stop and leave the removal to the user.

If comments were fetched, display them below the summary:
> **Comments** (N total):
> - **Author** (date): comment body (first ~2 sentences or 150 chars each)

Include ALL comments — these often contain critical context, decisions, and clarifications that inform the implementation.

## Step 3e: Detect "address MR comments" tickets

After displaying the ticket, check if the ticket is about **addressing comments or feedback left on a merge request**. Look for signals like:
- Title or description mentions "address comments", "address feedback", "follow up" on a merge request/MR
- Description links to a merge request on GitLab — the URL path carries the MR number

If the ticket matches this pattern:
1. Extract the MR URL from the description.
2. **Invoke the `fix-feedback` skill** using the `Skill` tool, passing the MR URL as the argument.
3. After the `fix-feedback` skill completes, skip Steps 4 and 5 (plan and implement) — the fix-feedback skill handles everything.
4. Proceed directly to Step 6 (commit message, MR description, diagram and review).

If the ticket does NOT match this pattern, continue to Step 4 as normal.

## Step 3f: Load Parent and Sibling Context (MANDATORY for subtasks)

**This step is not optional and must not be skipped.** A subtask implemented without its parent and sibling context is a failure of this skill even when the code itself is correct — the implementation will not fit the larger design. Use the `parent` field you recorded in Step 3a to decide which branch applies.

**If the issue has NO parent:** state explicitly to the user — "This ticket has no parent; no initiative context to load" — and continue to Step 4. Do not silently skip; say it.

**If the issue HAS a parent, you MUST load all of the following before planning:**

1. **Parent ticket** — call `get_issue` with `id:` set to the parent's identifier and `includeRelations: true`. Read its full title, description, and comments (fetch comments the same way as Step 3c). This frames the overall goal.
2. **Sibling tickets** — call `mcp__claude_ai_Linear__list_issues` with `parentId:` set to the parent's identifier (load it via `ToolSearch: select:mcp__claude_ai_Linear__list_issues` if not already available). This returns every child of the parent — i.e. this ticket's siblings. Read each sibling's title and description to understand the work landing alongside this ticket and avoid overlap or conflicting approaches. For any sibling that looks closely related, fetch its full issue with `get_issue`.
3. **Related tickets** — from the parent's `relations` (blocks / blocked-by / related — available because you passed `includeRelations: true`) and its `project`, fetch the linked issues for the wider design intent.

Do not treat a failed or empty tool call as "no context." If a call errors, retry or try the alternate tool, and only move on once you have genuinely confirmed there is nothing there.

**Checkpoint — you may not enter plan mode (Step 4) until you have stated all of the following to the user:**
- the parent ticket's identifier and overall goal,
- how many siblings exist and what each covers,
- any related/blocking tickets that affect the approach.

Read this material the way you read the ticket itself: it defines the initiative this ticket belongs to, and the implementation should fit that larger design rather than solving the subtask in isolation.

## Step 3g: Load Linked Notion Pages (MANDATORY when present)

Linear tickets frequently link to a Notion doc (design spec, RFC, requirements) that holds the real detail behind a terse ticket. **This step is not optional when such a link exists** — implementing without reading the linked spec is a failure of this skill even if the code is correct.

1. **Scan for Notion links.** Search the ticket **title, description, comments** (from Step 3c), and the ticket's **attachments/links/relations** (from the `includeRelations: true` result in Step 3a) for any Notion URL — patterns like `notion.so/...`, `www.notion.so/...`, or a workspace subdomain such as `<workspace>.notion.site/...`. Collect every distinct URL/page you find.

2. **If NO Notion link is found:** state explicitly to the user — "No Notion pages linked in this ticket" — and continue to Step 4. Do not silently skip; say it.

3. **If one or more Notion links are found**, load the Notion fetch tool via `ToolSearch` (query: `select:mcp__claude_ai_Notion__notion-fetch`; if that returns nothing, try `+Notion fetch`). If no Notion tool is available at all, tell the user the Notion MCP server appears unauthorized/unavailable and that the linked spec could not be loaded — then continue, noting the implementation is proceeding without it.

4. **Fetch each linked page** with `mcp__claude_ai_Notion__notion-fetch`, passing the page URL (or its extracted page ID) as `id`. Read the full content into context.
   - If a fetched page **references or links to further Notion pages** that are clearly part of the same spec (e.g. a sub-page for the exact feature this ticket implements), fetch those too — one level deep is usually enough. Don't chase the entire workspace; stay within what's relevant to this ticket.
   - Do not treat a failed or empty fetch as "nothing there." If a call errors, retry once or try `notion-search` with the page title to locate it, and only move on once you've genuinely confirmed the content is unreachable.

5. **Checkpoint — before entering plan mode, state to the user:** which Notion page(s) you loaded (title + URL) and a one-to-two-sentence summary of what each contributes to the implementation. If a link was found but could not be fetched, say so explicitly.

Treat the Notion content as first-class context alongside the ticket description itself — where the ticket and the spec conflict, surface the discrepancy to the user rather than silently picking one.

> **Other doc links:** If the ticket links a non-Notion doc (Google Docs/Drive, Confluence, etc.), try to load it via `ToolSearch` the same way (search for a matching MCP tool). If no tool is available or the server is unauthorized, tell the user which doc couldn't be loaded and continue — don't block the workflow on it.

## Step 4: Plan the Implementation

**Gate: do not start planning until the Step 1d, Step 3f and Step 3g checkpoints are satisfied** — the ticket is open or the user has confirmed working a closed one, you have stated the parent/sibling/related context (or confirmed no parent), *and* you have loaded any linked Notion pages (or confirmed none are linked / could not be fetched). If you cannot yet do any of them, return to the relevant step before continuing.

Step 1d is listed here as well as at its own step because planning is the expensive thing it protects. A closed ticket that reaches this point gets a plan, a published page, an approval and an implementation of work that already shipped — so the gate that guards planning is the right place to require the answer a second time.

**The gate is not waivable, and the size of the change is not a reason.** A one-line edit gets the same approval as a thousand-line rewrite. Whether an approach needs the user's eyes is the user's judgement rather than yours, and a run that makes that call for them has destroyed the one record they would have checked the work against — which is how this rule came to be written: a run judged a one-line bundle change too small for a plan, implemented it, shipped it, and the user learned afterwards that no approved plan had ever existed. There is no "it is a one-line change", no "the fix is obvious", no "the plan would be shorter than this sentence". The one legitimate exit is the **user** waiving it, and that is recorded rather than assumed — tick `plan=skipped:<reason>` so the waiver and its reason land on the page they refresh, and clearing a skip needs their word and never yours. `run-checklist.py tick` enforces this rather than trusting it: it refuses to put `implement`, `commit`, `describe` or `open` in flight or done while `plan` is still `pending`, so the gate has stopped being armed only by complying with it.

**Everything below is a prohibition on plan *mode*, never on planning.** The run that skipped this step described it afterwards as a step requiring `ExitPlanMode` — it had taken away *do not use plan mode at all* and lost the gate underneath it. The approval is the step; plan mode is one way to get it, and the wrong one.

**Do not use plan mode at all.** The approval gate is the point; plan mode is one way to get it and it is the wrong one here, for two independent reasons. Inside it, **`permissions.allow` cannot cover a shell construct** — a `for` loop or a pipeline has no single command head to match, so Claude Code cannot even offer to remember it: the prompt reads `Yes`/`No` with no "allow for this project" option, and an unattended run stops dead on a command that only reads files. And leaving it is worse: `ExitPlanMode` drops the session into whichever mode the approval prompt offers, which is `acceptEdits` wherever auto mode is unavailable — and `acceptEdits` auto-approves edits while **prompting for every single `Bash` call** for the rest of the run. Both were observed repeatedly on runs whose whole purpose was to need nothing from anybody. Widening the allowlist fixes neither and never will.

So **never call `EnterPlanMode` or `ExitPlanMode` in this skill.** Explore and plan under the session's own mode, then gate on `AskUserQuestion`, which asks just as plainly, notifies the user's phone through the same hook, and leaves the session's permission mode exactly where it was.

**Nothing is created or modified before the plan is approved.** Plan mode used to enforce that and now it is a rule you keep yourself. Read, Glob, Grep and read-only shell are the whole toolkit of this step: no Edit, no Write, no `git` command that changes state, no install, no network write.

**Confirm the tree you are about to read is current — Step 2's fetch does not settle it.** Step 2 cut this worktree from a freshly fetched `origin/<DEFAULT_BRANCH>`, so unlike a freeform run there is no window here in which exploration precedes a fetch at all. What that does not give you is a *current* remote ref by the time this step runs, and three routes get there behind: Step 3 reads the ticket, its siblings and any linked Notion page in between, Step 2c's "the branch I am on" bullet never fetches, and a base that is itself a feature branch is behind the default branch by design. So fetch again — one quiet command — and read the gap:

```bash
git fetch origin <DEFAULT_BRANCH> --quiet
git rev-list --count HEAD..origin/<DEFAULT_BRANCH>
git log -1 --format='%cd' --date=short HEAD
```

Anything but `0` and the per-path rule in `fix-freeform` Step 1b applies here in full, including the two traps worth restating. A path **this branch** has also changed is never read from upstream, because the upstream blob carries none of the branch's work. And `fatal: path … does not exist` from `git show` is the answer rather than a failure — the path is gone upstream, so every claim naming it is about a file that no longer exists.

**Every additional repository gets the same three commands, fetch included, against its own default branch.** That is where this is easiest to miss — the two-repo case in Step 2f reads a second checkout nothing has ever fetched, so a count taken there without its own fetch compares against a ref as stale as the tree it is judging and can only ever report `0`.

Use the ticket title, description, comments, the parent/sibling/related context from Step 3f, and any labels/context to:

1. **Explore the codebase** — use Glob, Grep, and Read to understand relevant files, existing patterns, and architecture. **Re-verify the ticket's own factual claims against the source rather than restating them.** A ticket written during research routinely overstates ("every row is wrong", "X carries no Y") or describes a pre-implementation design that shipped narrower. Both happened here: one table row was already correct, and a sibling MR shipped a stale-snapshot behavior the ticket described as absent. Restating an unchecked ticket claim puts it in the plan, the code, the commit message and the MR description, where a reviewer has to disprove it four times. Where ticket and code disagree, implement what the code says and say so explicitly — but only once the tree is known current. If the count above was not `0`, read the contradicting line through `origin/<DEFAULT_BRANCH>` before you quote the ticket back, since telling the author their ticket is wrong on the strength of a stale checkout is worse than never checking it.

   **Check every path the ticket names actually exists, and do not trust its call-site count.** On PLAT-3276 the ticket's scope list named two files that do not exist (`src/ftl/bigquery/registry.py` → really `rule_registry.py`; `tests/unit/test_registry_loader.py` → really `test_registry_packages.py`), said "9 call sites" when there were 11, and missed a docs reference entirely. A ticket author greps once from memory; you have the tree. Run the ticket's own "done when" greps *before* planning, not just after.

   **Grepping for the constructor misses call sites that go through a test helper.** `rg 'Owner\('` found nine; two more reached the model as `owner(fetch=..., transform=...)` via the `owner()` factory in `tests/conftest.py`, and only pyright caught them. When deleting a field or parameter, also grep for the *lowercase helper* and any `**kwargs` forwarder — or just treat the first typecheck run as part of discovery rather than as verification.

   **`rg -r` is `--replace`, not "recursive".** `rg -rn 'foo-bar' .` silently rewrites every match to `n` in the output, which reads as a real but wrong result (it made a bucket named `ftl-local-dev` appear to be named `n`, sending me down a false trail). ripgrep is recursive by default; never pass `-r`.
2. **Design an implementation approach** — identify which files need changes, what the changes are, and in what order.
3. **Ask clarifying questions** — if the ticket description is ambiguous or missing details, use `AskUserQuestion` to clarify with the user before finalizing the plan.
4. **Plan into the reply, publish, send the link alone, then gate on it — in that order.** Write the full plan into your reply for the terminal **first**, ahead of the publish. Then publish it as a page, send the URL as **its own message carrying nothing but the URL**, and call `AskUserQuestion`. Options are `Approve` and `Change something`. Treat anything other than a clear approval as a revision and plan again. Do **not** call `ExitPlanMode`; this skill never enters plan mode, so there is nothing to exit.

**Publish the plan first, so the gate can hand over a link to the whole thing.** Render the plan as a self-contained HTML page and publish it:

```bash
~/.claude/scripts/publish-artifact.sh <plan>.html \
  --purpose plan \
  --expires 7d \
  --title '<the ticket id and the change in a few words>' \
  --description 'implementation plan'
```

It prints the URL. `--purpose plan` is the whole of the configuration: the script looks up `plan_folder` itself, omits the folder flag when that key is empty, and publishes the page **public**, so the person reading it needs no session. A page published privately is a 404 to everybody but an admin, which is the one reader this gate does not need to reach. **Never pass `--folder` with a name of your own**, since publishing refuses a folder that does not exist. Resolving all of it inside the script is deliberate: the conditional form this replaced, `${FOLDER:+--folder "$FOLDER"}`, splits into two arguments in bash and stays **one** in zsh, so it shipped `--folder PRtifacts/Plans` as a single fused argument and every publish failed on the shell these commands actually run in. `--expires 7d` is deliberate: a plan is worth reading while it is being approved and clutter a fortnight later.

**Exit status 3 means this machine has no self-hosted store.** That is the ordinary answer on most of them and not a failure — publish the same HTML with the **Artifact** tool instead and use the link it returns. Any other non-zero status is a real failure: say what it printed in one line, then ask the question with no link. **Never hold the gate open waiting for a link.** A plan the user can only read in the terminal still gets approved; a question that never arrives strands the run.

**Send the link as a message of its own, immediately before the question.** `AskUserQuestion` renders no links, so a URL inside the question text arrives as characters nobody can tap — on the phone screen this whole gate exists to serve. The chat message before it is clickable and is the last thing on screen when the question lands, so that is where the link goes, on a line of its own.

**That message carries the URL and nothing else**, and "nothing else" is the load-bearing half. No plan, no summary of the plan, no restatement of the change, no account of what happens once it is approved, no closing offer. Each of those is prose the reader has to scroll past to reach the only actionable thing on the screen, and they do not read it — the page is where the plan is, which is why it was published. A bare label in front of the URL is the most that earns its place. This is also why the plan prose goes into the reply **ahead of** the publish rather than beside the link: the terminal copy still earns its keep as the fallback for a publish that fails, and in front of the publish it cannot wedge itself between the link and the question.

**Publishing the plan and asking the question are one turn. Never end the turn between them.** This is the failure the whole gate is built to avoid, and it has happened: the plan was published, the link was posted, the turn ended, and the run sat waiting on an approval nobody had been asked for. Publishing feels like the deliverable, so the turn reads as finished — but a published plan is nothing except the thing a question is about. No tool call belongs between the publish and the `AskUserQuestion`, and nothing is worth one more exploratory check first.

The cost of ending that turn is paid entirely by the user, which is why it is so easy to miss. Step 0's ping normally means the session is armed by the time this gate is reached, so a turn that ends here does at least reach their phone — but it reaches it as a turn-end summary of a turn that published a plan, which is not a question and does not read as one, so nothing tells them an approval is owed. And on the run where Step 0's send failed, the gate question is the **only** event that notifies an unarmed session at all: skip it there and the run is silent with the plan ready — no notification, no question, and nothing on the user's phone to tap.

`publish-artifact.sh --purpose plan` records the URL in the session state, and the `Stop` hook **refuses the first turn end that leaves it set** — it blocks the stop and hands back the instruction to ask, so the question happens before the turn can finish. A turn that ends with the marker set a second time is not blocked again; the hook notifies instead, even on an unarmed session. **Treat both as a smoke alarm, not a safety net.** Being sent back to ask costs a turn, and the notification behind it costs another and arrives saying "waiting on you" rather than asking the actual question. Asking in the same turn as the publish is the only version that costs nobody anything. If a plan genuinely needs no question — the user approved it in advance, or it was published for the record — clear the marker with `~/.claude/hooks/notify.py --gate-clear` rather than letting the interlock fire.

**The question itself carries no plan.** One line naming the change, then `Approve` and `Change something`, and nothing else. The compressed per-file summary this replaced was written when the question text was the only copy that reached the phone; with a link one tap above it, that summary is a second and worse copy of the plan, and it fills the screen the question is read on. A question reading only "approve the plan?" would still strand the user, which is why the link is a hard requirement of this step rather than a nicety — and why a failed publish is reported in one line rather than waited on. `ExitPlanMode` was never an option here: the hook sends the fixed string `Waiting for plan approval.` for it and never the plan.

While the question is open the plan item on the run checklist is `in-flight`, waiting on the user — which is the one state that makes a stalled gate visible on the page rather than only in the transcript. Once the user approves, tick it and **record the plan page's URL on the checklist in the same command**:

```bash
~/.claude/scripts/run-checklist.py tick <items>.json \
  plan=done 'implement=in-flight:the approved plan' \
  --run plan_page=<the published plan url> --publish
```

`plan_page` is how the URL reaches the merge request's description at `autopilot` Step 4b. The items file is the one piece of run state that survives both the hand-off and a pause, so recording it here is what stops the link depending on a context window that gets compacted — the same argument that put the run's obligations on a page in the first place. A run whose publish failed has no URL and records none: the field stays empty and Step 4b writes no line.

Then implement the changes.

## Step 5: Implement the Changes

**Keep a task list, whatever the size of the change.** It was skipped on the grounds that a one-line change had no tasks worth listing, which is the same judgement Step 4's gate refuses and is wrong for the same reason: the list is a record the user checks the work against, so whether a change deserves one is theirs to decide rather than yours. `TodoWrite` is how you keep it. **Where that tool is not available in the session, say so in one line and keep the list on the run checklist instead** — measured on the run that wrote this rule, where `TodoWrite` was absent. An absent capability is reported, never worked around, and never read as permission to keep no list at all.

Execute the approved plan:
- Use `TodoWrite` to track implementation tasks.
- Write clean, minimal code that follows existing codebase patterns.
- **Add no comments to the code you write or change.** No explanatory comments, no banners, no docstring on a symbol that did not have one, no `TODO`s, no commented-out code — and never a reference to the Linear ticket, task, or initiative (`# ENG-123`, `// per PLAT-1180`, `# for the X initiative`). A comment written alongside the code restates the line, goes stale, and makes the reviewer read past it to reach the change. Write the code so it does not need one, and put every explanation in the commit message and MR description instead. Exempt because they are program input rather than commentary: linter and type directives, build pragmas, codegen markers, required license headers, and any doc-comment CI fails without. Leave comments already in the file alone unless your change makes one untrue — then correct or delete it.

  **A comment-dense file does not create an exception, and this is where the rule is most often broken.** Some files document the rationale behind every constant — `apps/iam/internal/workflows/reconcile.go` spends 25 lines explaining one retry policy's arithmetic. Writing the new code to match that density and stripping the comments afterwards wastes a full editing pass; decide before the first line that the new code carries none, and route the reasoning to the commit message and MR description as you go. Then say so in the summary, because the asymmetry is genuinely visible in review: a new timeout sitting silently beside a heavily-justified one looks like an oversight rather than a convention. Mention it in the MR description's context, and let the user reverse it in one word if they want the local convention honoured instead.
- Run any relevant tests or linters if the project has them configured.
- **When the real verification command needs credentials you cannot get, fire the re-auth gate below, and only then build an offline harness rather than shipping unverified logic.** The gate comes first and the harness is what you do while the user re-authenticates — never instead of telling them. In `tlaloc-env` the honest ceiling is usually `terraform validate` — `terraform plan` needs a gcloud ADC reauth this session cannot perform (`invalid_grant` / `invalid_rapt`), and `terraform/gridmatic-dev/iam` additionally needs `TEMPORAL_CLOUD_API_KEY`. `validate` type-checks but never *evaluates* a `precondition`, so a guard that passes validate can still crash at plan time. Copy the new locals into a provider-free config in the scratchpad and drive it with `terraform -chdir=<abs> apply -auto-approve -var mode=…`, outputting the guard lists: it needs no credentials and it tests the counterfactuals — the mis-ordered rule, the deleted rule, the bad value — which no real plan of a correct config ever exercises. On PLAT-2460 this caught a genuine bug: **HCL's `||` does not short-circuit**, so `length(xs) == 0 || i < xs[0]` throws `Invalid index` on an empty list instead of taking the left branch. Use a sentinel — `try([…][0], length(…))` — not a guarded index. Two harness caveats: `concat` of rule objects with differing attributes yields a *tuple*, so a `var.mode ? concatA : concatB` ternary fails on inconsistent types (use uniform stub objects, or select with a filtered list); and a `for` result expression like `rule.id` is only evaluated for elements passing the `if`, which is why the file's existing `allowed_roles` can safely read `rule.role_pattern` over deny rules that lack one.

  **Get the terraform version from the module's own `.mise.toml`, not from a ticket's note.** Several modules now carry one (`terraform/gridmatic-dev/iam/.mise.toml` pins `1.11.4`) and that pin is what Atlantis uses, so it is the version a change must actually pass on. A `TFENV_TERRAFORM_VERSION=…` override mentioned in a sibling ticket may predate the pin and silently verify against a version nobody runs. `mise exec terraform@<pinned> -- terraform fmt -check` / `validate` is the check that counts; running the other version too is cheap and worth it, since `init` is the slow part and `fmt` needs none.
- **Terraform renders long strings across lines, so parse what actually ships.** `yamlencode` folds a >80-column value onto continuation lines. That is valid YAML and round-trips correctly, but confirm it rather than assuming: render the exact values block and parse it. `python3` here has no `yaml` module — `ruby -ryaml` does, and `jq` is available.
- **Clean up what `terraform init` leaves behind.** It drops a ~430 MB `.terraform/` in the module directory. It is gitignored (`terraform/.gitignore: **/.terraform*`) so `git status` stays clean and you will not notice — `rm -rf` it when done.
- **Running the repo's own installer or bootstrap as a verification is often safe, and the safe way is a scratch `HOME`.** Where the change *is* an installer, executing it is the only honest check, and pointing `HOME` at a `mktemp -d` makes that harmless: every link destination, every editor settings directory and every extension install resolves under the scratch tree. Unset `XDG_CONFIG_HOME` and pin `GIT_CONFIG_GLOBAL` as well, or an XDG-derived path escapes back to the real config directory. Run it **twice** and diff the second run's output — idempotence is the property that actually breaks, and the second run should report only "already linked". Never run it against the real `HOME` **from a worktree**: every link would point into a directory that gets deleted at cleanup. Two costs to expect. It initialises submodules in the worktree, and a worktree with initialised submodules can no longer be removed by `git worktree remove` — `git submodule deinit` does not undo that, so cleanup needs `rm -rf` plus `git worktree prune` (autopilot Step 10d carries the detail). And a build step may run the project's test suite, so budget for it or run it in the background while CI and the review proceed.
- Mark each todo as completed as you finish it.

### The re-auth gate — stop, say which credential, and wait

A command that fails for a missing or expired login is not work to route around. **The trigger is naming the credential, not failing twice.** The moment you can say which login died, you are already past the point where continuing helps — `invalid_grant` or `invalid_rapt`, any message telling you to run `gcloud auth login` or `gcloud auth application-default login`, `Reauthentication required`, `ERR_PNPM_FETCH_403` from a registry behind a minted token, a `401` or `403` from the forge API, a non-zero auth-status check on the adapter `skill-env.sh` resolved, an expired cluster credential, `Resource not accessible by integration`. Anything meaning *log in again* is in the list.

Four things, in this order, in the same turn:

1. **Say it in the reply**, with the exact re-auth command in a fenced block of its own. The credential is one this session cannot see, which makes this the one shape of command that is genuinely the user's to run.
2. **Record the blocker on the run checklist**, against whichever item is in flight — `implement=in-flight:waiting on gcloud ADC re-auth`. The page is the only run state that survives a compaction, and a run stopped on a login with nothing saying so reads as a run still working.
3. **Send a `permission` ping** with the `ping` skill — the level its table already maps `auth` to — naming the credential and carrying the same command.
4. **Call `AskUserQuestion`** — header `Re-auth`, options `Yes` and `No`, question `Have you reauthenticated? <what expired> — run: <command>`. The question text *is* the push notification's body, so a bare *Have you reauthenticated?* reaches a lock screen saying nothing about what to re-authenticate.

**`Yes` is verified once, with the command that failed** — the same command, not a cheaper substitute and not a variant. Still failing means the wrong account or the wrong project, which is common and is not something to guess at: say what it printed and ask again.

**`No` does not continue past the gate.** No retry, no substitute command, no second credential path, no other account. Work that genuinely does not need the credential carries on — the code, the commit message, the description — while the credential-dependent step stays open and named, never faked and never reported as done.

**Banned outright**, because each of these looks reasonable from the inside: deriving a new way around the credential at runtime; a token read out of somewhere it was not offered from; switching the verification off; downgrading it to a check needing no credential and reporting *that* as the check; and declaring the change unverifiable without having told the user, since the honest ceiling is reportable and silence is not.

**A fallback this file already names is not a workaround.** The borrowed `node_modules` tree in Step 2f and the offline harness above are recorded, measured techniques: use them *after* the gate has fired, and report their ceiling honestly. An invented workaround and a written-down one are not the same kind of thing, and only the first is what this gate exists against.

`autopilot`'s **The re-auth gate** section carries the rationale, and the exception it takes to that skill's rule against pinging beside a question. The procedure is here in full because a `--autopilot false` run never reaches it, and because the credential wall is usually hit in this step rather than in the tail.

After implementation is complete, give the user a summary of what was changed.

## Step 6: Commit Message, MR Description, and the Hand-off

Immediately after implementation is complete — do not wait for the user to commit or ask for these:

1. Invoke the `commit-msg` skill using the `Skill` tool to generate a commit message.
2. **Immediately** invoke the `changes-description` skill using the `Skill` tool to generate an MR description. Do NOT wait for the user to respond to the commit message first — invoke it in the same turn, back-to-back with the commit message, so nothing is waiting on them reading it. The `commit-msg` skill ends with a suggestion to run `/commit`, but you must continue and invoke `changes-description` before yielding to the user.

   **The description must come from this skill.** If you are composing prose for a description field yourself, you have skipped a required step — invoke `changes-description` with `--inline` at the very least, which keeps your prose and adds back the measured word budget and the fact-check against the diff. **"In hand" means an artefact that skill produced**, named by its workflow run id or by the `--inline` fact-check it ran; prose sitting in this context window is not a description, however much of the diff went into it. `changes-description`'s own Rule 5 says the same thing, and stating it only there is useless to the reader who skipped that skill — which is exactly the reader who needs it. Descriptions written by hand have run to about 1,100 words with eleven sections and tables; the panel cut one of them to 284 words and found a rollout fact stated backwards.

   **`--quick-description` is this skill's flag; `--inline` is what `changes-description` is handed.** The two names do not line up, so read the mapping rather than the words. `--quick-description true` → pass `--inline` and nothing else. `--quick-description false` → pass **no flag at all** and let the full four-persona panel sit. A flag named "quick" whose `false` value means "pass nothing" is worth one careful read now rather than a wrong description later.

   **`true` means no workflow, not a cheaper one.** What quick buys is the merge request being open sooner, not a smaller agent bill: a workflow of any size prints a run ID and ends the turn, so the description — and the push, the merge request and everything autopilot does after them — all arrive one completion notification later. `--inline` has that skill write the description in this same turn, against its template, its measured word budget and a fact-check against the diff, and this run carries straight on. Its `--one-shot` (4–6 agents) and `--quick` (15–16) are both unreachable from here on purpose, because this flag is a boolean; invoke `/changes-description --one-shot` by hand on the rare run that wants a middle setting.

   **The turn only yields on `--quick-description false`.** There, `changes-description` launches a background workflow, prints a run ID and hands the turn back before the description exists — that is correct, not a stall. Yield with it: blocking on it (`TaskOutput`, `Monitor`, a poll loop) only takes the user's prompt line away for the length of the run, and the description arrives when the completion notification does. On `--quick-description true` there is nothing to wait for and nothing to watch, so continue to step 3 and the hand-off in the same turn.
3. **Re-print the commit message after the MR description, verbatim.** The `changes-description` output is long, so by the time it finishes the commit message from step 1 has scrolled far up the terminal. In the turn that presents the description — the one the swarm's completion notification wakes you into on a `--quick-description false` run, or the turn you wrote it in on a quick one — close by repeating it — unchanged from what `commit-msg` produced, no re-generation, no re-wording, no summary of it — in its own fenced block under a `Commit message` heading, so both blocks the user copies sit next to each other at the bottom. If the user corrected the commit message between step 1 and here, repeat the corrected version.
4. **Then hand the run to `autopilot`, unless `--autopilot false` was passed.** In that same turn, once the description and the re-printed commit message are out, invoke the `autopilot` skill using the `Skill` tool and pass it the resolved flag state from Step 0 — `--branch`, `--diagram`, `--review`, `--merge`, `--max-rounds` — as values, not as the user's original argument string, so an amendment made mid-run is not silently rolled back to a machine default.

   **The checklist crosses the hand-off as state, not as a fresh publish.** Tick the commit-message and description items, then give `autopilot` the page's url and its update hash along with the flags. It adopts that page and keeps writing to it; a second publish there would hand the user's existing link to a checklist that stops at step five. **The items file goes with it**, not just the url and the hash: `plan_page` lives in there, and Step 4b writes the change request's description from it.

   **Autopilot owns everything from here, and that includes the diagram and the swarm.** Do not run `changes-diagram` or `review-code` yourself on this path. Autopilot runs the swarm in the turn that arms its pipeline watcher, *after* the push, because `fix-feedback` posts each confirmed finding to the merge request as an anchored comment and there is no merge request to post to before the push. It attaches the diagram once the review is settled and before the merge, which is both the point at which the code has stopped moving — a diagram of a branch that changed three more times is worse than none — and the last point at which the branch and the worktree `changes-diagram` derives its base from still exist. Running either of them here would mean doing the work twice and losing the posting target the first time.

   **The hand-off is not a question.** Autopilot is on because this machine's `fix_autopilot` says so, or because the user said so; either way the decision is already made. Say in one line that you are handing over, and what the run will do when it gets there — "Handing to autopilot: push, open the MR, work the review, stop before the merge" — then hand over.

   What crosses the hand-off is the *state*, not the invocation: the branch, the worktree, the commits, the commit message and the description all already exist, and autopilot starts at its Step 2 rather than re-entering this skill.

### 6e and 6f run only when `--autopilot false`

With autopilot off, nothing is going to push this branch, so the diagram and the swarm are this skill's to run — they are the only review the change is going to get, and they are both deliverables the user asked for by flag.

**6e. Produce the call-flow diagram when `--diagram` is true.** Invoke the `changes-diagram` skill using the `Skill` tool with no arguments on a `--branch new` run — it defaults to the current branch against the default branch, which is exactly this branch. On a `--branch default` run pass the base explicitly (`origin/<DEFAULT_BRANCH>`), because `merge-base(<default>, HEAD)` is `HEAD` there and the skill would correctly report that there is nothing to draw. It publishes an HTML page and hands back a link, or returns a local file path when no artifact store is reachable; **either outcome is a success.** Print whichever you got as a single line under the commit message block, so it cannot push the two blocks the user copies apart.

   **It must never fail this run.** If `changes-diagram` errors, is not installed, or returns nothing usable, say so in one line and carry on. Do not retry it, do not draw the diagram yourself, and do not let it hold back items 1–3 — the commit message and the description are the deliverables here, and losing them to a missing diagram would be a bad trade.

**6f. Run the review swarm when `--review` is true.** Once the diagram line is out, invoke the `review-code` skill using the `Skill` tool with no arguments — its Local mode defaults to everything that differs from the default branch, committed and uncommitted alike, which is exactly this branch's work whether or not the user has run `/commit` yet.

   **Invoking it here is the opt-in, not a question to put to the user.** `review-code` orchestrates a swarm through the `Workflow` tool, which is otherwise reserved for work the user asked for in so many words. They asked for it here: the flag resolving to `true` *is* the standing request. Do not stop to confirm, and do not ask whether the diff is big enough to be worth a fleet — `review-code` sizes its own swarm to the diff in its Step 2, so a one-line change already costs a one-line change's worth of agents.

   **Why it runs after the description rather than alongside it.** Both read the same diff, but only one of them can invalidate the other: a confirmed finding usually means a code change, and a description written against a diff that is about to move is the thing that goes stale. Running the review second makes the order of execution match the direction of invalidation. Launching both at once would also put two full swarms in flight over the same branch at the same time.

   It launches as a background workflow and yields the turn with a `wf_…` run ID, exactly as `changes-description` did. Yield with it — no `TaskOutput`, no `Monitor`, no poll loop. The findings arrive when the swarm's completion notification does; present them then, and close by naming `/fix-feedback` as the way to work through them.

   **It must never fail this run**, on exactly the terms the diagram has: if `review-code` errors or is not installed, say so in one line and carry on.

## Important Rules

1. **This skill never pushes and never writes to Linear — the hand-off does.** Inside Steps 1 through 6 you create local branches and worktrees, commit when asked, and publish the diagram; you do not push, open an MR, or update a Linear ticket. That is not a prohibition on the *run* — `autopilot` owns every one of those actions and performs them under its own rules from Step 6 onwards — it is a statement about which skill is accountable for them, so that `--autopilot false` reliably means nothing left this machine. Never quote this rule back as a reason to refuse the hand-off. And never remove a worktree the user did not ask you to: cleanup is the user's call.
2. **Respect uncommitted work.** Never discard or stash uncommitted changes without the user's explicit approval.
3. **Ask, don't assume.** If the ticket is vague, ask the user for clarification rather than guessing.
4. **Follow existing patterns.** Match the coding style, naming conventions, and architecture of the existing codebase.
5. **Keep the user informed.** Summarize what you're doing at each major step so the user can course-correct early.
6. **No comments in the code.** Do not add explanatory comments, docstrings, or ticket references to code you write or modify — the full rule is in Step 5. Explanation goes in the commit message and MR description, never the source. Machine-read directives (linter suppressions, build pragmas, a doc-comment CI requires) are program input, not commentary, and stay allowed.
7. **Never route around a credential.** A command that fails for an expired or missing login is a stop, not a puzzle. Fire **The re-auth gate** in Step 5: say which credential died and the command that renews it, record the blocker on the checklist, ping at `permission`, and ask `Have you reauthenticated?` with `Yes` and `No`. Never derive a way around it, never reach for another account or credential path, and never switch a verification off or swap it for one needing no credential and report that as the check. A fallback this file already names is allowed once the gate has fired and its ceiling is reported honestly; an invented one never is. The asymmetry is the argument: telling the user at the first failure costs one notification they can act on, and finding out half an hour later costs everything in between plus an answer worse than the one they would have given.
