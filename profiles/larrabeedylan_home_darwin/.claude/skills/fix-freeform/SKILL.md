---
name: fix-freeform
description: Implement a change the user described in their own words, with no ticket behind it — "fix this bug", "make this change", "implement X", "can you clean up Y". Interrogates the problem statement against the code before planning, picks the branch mode (straight onto the default branch for small local fixes, a feature branch and worktree when the change touches Terraform, when the default branch is protected, or when the tree is dirty), implements it, and hands back a commit message. Use it whenever there is work to do and nothing to look the work up in; use fix-linear instead when a ticket identifier exists.
---

# Fix Freeform — Implement a Change From a Problem Statement

Implement a change the user described in plain words. This is `fix-linear` with the ticket taken away: nothing to fetch, no parent initiative, no linked spec — and nothing to check the request against except the code itself.

**Parameter:** `$ARGUMENTS` — optional flags, then the problem statement.

| Argument | Effect |
|---|---|
| *(everything left after the flags)* | The problem statement — what to fix, change, or build. Required: if nothing is left over, ask the user what they want done and stop. |
| `--branch default` | Work on the repository's **default branch** directly — no feature branch, no worktree, no pull request. The default, and the reason this skill exists apart from `fix-linear`. |
| `--branch new` | Cut `<FIRST_NAME>/<slug>` off the default branch and set up a worktree, exactly as `fix-linear` does. |
| `--one-shot-description [true\|false]` | Default `true`. Passed through to `changes-description` as `--one-shot`: one writer plus the measured word budget and the fact-check — 4–6 agents instead of 20. `false` runs the full four-persona debate. |
| `--changes-diagram [true\|false]` | Default `false`. `true` adds a call-flow diagram of the change (Step 5c). |
| `in place` / `--here` / `no worktree` | Only meaningful once the run is on `--branch new`: take the branch in the current working tree instead of a worktree (Step 2-INPLACE). |
| `/fix-autonomous` (anywhere in the arguments) | A delegation directive, never part of the problem statement. Hand the whole invocation to `fix-autonomous`. See **Delegation** below. |

Parse the flags out of `$ARGUMENTS` **first**; whatever remains is the problem statement. A bare `--one-shot-description` or `--changes-diagram` means `true`. Leaving a flag unparsed hands it to the planner as part of the request, which produces a plan to implement the words "branch new".

### Delegation: `/fix-autonomous` in the arguments

A `/fix-autonomous` or `fix-autonomous` token anywhere in `$ARGUMENTS` is a **delegation directive, not part of the problem statement and not a question to put back to the user**. They are composing two skills, which is what naming one skill inside another's invocation means everywhere in this family: *do this freeform request, and drive it the whole way without checking in.* Strip the token, invoke `fix-autonomous` with the `Skill` tool, pass the remaining flags and the problem statement through verbatim, and let it call back into this skill from its own Step 1.

**Do not ask how far the run should go.** The token already answered that, and asking is worse than a wasted turn: it reads as not having understood the invocation, and it strands a user who deliberately set the run up to need nothing from them. The only thing worth saying out loud is one line naming the delegation as you make it.

Flags cross the hand-off in both directions, so forward every one you do not own rather than treating it as unparsed junk:

- **This skill's flags** — `--branch`, `--one-shot-description`, `--changes-diagram` — are passed on, and `fix-autonomous` hands them back when it re-enters here. Note it overrides `--branch` to `new`: an unattended run always produces a pull request, because review is the only thing between it and the default branch.
- **`fix-autonomous`'s own flags** — `--merge`, `--max-rounds` — mean nothing to this skill and must survive untouched. `--merge false` is how the user says *take it to green, reviewed and ready, then stop*; dropping it silently merges something they wanted held for a second pair of eyes.

Reaching `fix-autonomous` this way loosens nothing — it owns the push, the pull request and the merge, and performs them under its own rules. What it does mean is that Important Rule 1 below binds **this skill's own flow**, not a run that has been handed over. Never cite that rule back as a reason to refuse the delegation.

**These defaults are deliberately the opposite of `fix-linear`'s**, which defaults to a worktree, a full description debate, and a diagram. Freeform work is usually small and local, so the cheap path is the right default and the user escalates explicitly — a ticket exists precisely because somebody judged the work big enough to write down first.

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

This is the step that matters, and it is the one thing this skill has that `fix-linear` does not. `--branch default` commits onto the branch every other checkout is cut from; `--branch new` does what `fix-linear` does. **The mode is not purely the user's choice — three conditions force `new`, and all three are checked before the first edit.**

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

Escalate if the planned change will touch any `*.tf` or `*.tfvars` file, or if the repo carries an `atlantis.yaml` / `atlantis.yml`. Atlantis plans and applies from a **pull request branch**: the plan output is posted on the PR, a human reads it, and the apply is gated on that read. A Terraform change committed straight onto the default branch skips the plan review entirely — nothing is posted anywhere a human looks, and infrastructure can be applied with nobody having seen what it would do. No "it's a one-line change" makes that acceptable, and the user cannot waive it with a flag. If the repo has `*.tf` files but you cannot yet tell whether this change reaches them, leave the question open and settle it in the plan (Step 3) — never by starting to edit and seeing what happens. If it only turns out to be Terraform-touching mid-implementation, stop there and escalate — Step 2e moves a commit you have already made.

**2. The default branch is protected.** Detect this **before** committing, rather than discovering it when a push is rejected. The forge knows; git does not.

```bash
~/.claude/scripts/github-api.sh
```

Run with no arguments, the script prints its usage line — which is the list of subcommands it actually has. If that list includes one reporting protected refs (`protected-refs`), call it with the project path URL-encoded (`group%2Fsubgroup%2Frepo`, derived from `git remote get-url origin`) and look for `DEFAULT_BRANCH` in the result. **If the script carries no such subcommand, the call fails, or no token is configured, you cannot answer the question from here — escalate rather than guess.** An unneeded feature branch costs one `git worktree remove`; a rejected push costs a commit stranded on the branch it was least welcome on, and Step 2e to unpick.

**3. The working tree already has unrelated uncommitted changes.**

```bash
git status --porcelain
```

If the tree is dirty with work that is not yours, escalate: committing on top of it mixes the user's in-progress work into your commit, and `git commit <paths>` only avoids that while you can prove which paths are theirs. The worktree gives you a clean tree and leaves theirs untouched. Never stash or discard it to clear this check — that is Important Rule 2, and it outranks the convenience of staying on the default branch.

Record which checks fired. It goes in the summary and in the commit context.

### 2c. `--branch default` — work on the default branch

No feature branch, no worktree, and **no pull request**. Confirm you are actually on the default branch:

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

By default this path isolates the work in its own **git worktree** — a separate working directory on its own branch that shares the repo's `.git`. This lets several fixes run in parallel (one terminal/session per worktree) without branch checkouts colliding in a single working tree.

**Escape hatch (in-place checkout):** if `$ARGUMENTS` contains `in place`, `--here`, or `no worktree` (case-insensitive), skip the worktree setup and use **Step 2-INPLACE** instead. Also fall back to Step 2-INPLACE if the repo cannot host worktrees (e.g. `git worktree list` errors).

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

## Step 2-INPLACE: In-Place Branch Checkout (escape hatch only)

Use this **only** when the escape hatch in Step 2d applies — it is the original single-working-tree behavior. Compute `DEFAULT_BRANCH` as in Step 2a first.

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

Enter plan mode using `EnterPlanMode`. Carry Step 1b's findings in with you — the restatement, and anything the code already contradicted — and then:

1. **Explore the codebase** — use Glob, Grep, and Read to understand the relevant files, existing patterns, and architecture. Step 1b checked the statement's claims; this step is where you find what it never mentioned, which on a freeform request is most of it. The statement names what the user noticed; the plan has to cover what the change actually touches.

   **Do not trust a call-site count, and do not stop at the obvious grep.** Grepping for a constructor misses call sites that go through a test helper: `rg 'Owner\('` found nine, while two more reached the model as `owner(fetch=..., transform=...)` via the `owner()` factory in `tests/conftest.py`, and only the type-checker caught them. When deleting a field or parameter, also grep for the *lowercase helper* and any `**kwargs` forwarder — or treat the first typecheck run as part of discovery rather than as verification.

   **`rg -r` is `--replace`, not "recursive".** `rg -rn 'foo-bar' .` silently rewrites every match to `n` in the output, which reads as a real but wrong result (it made a bucket named `ftl-local-dev` appear to be named `n`, sending me down a false trail). ripgrep is recursive by default; never pass `-r`.
2. **Design an implementation approach** — identify which files need changes, what the changes are, and in what order.
3. **Confirm the branch mode still holds.** If exploration shows the change reaches a `*.tf` file, or any other Step 2b condition, say so in the plan and escalate before implementing (Step 2e).
4. **Ask clarifying questions** — if the problem statement is ambiguous or missing details, use `AskUserQuestion` to clarify with the user before finalizing the plan.
5. **Present the plan** for user approval via `ExitPlanMode`. State the branch mode in the plan: which branch the work will land on, and whether an escalation fired.

Once the user approves the plan, implement the changes.

## Step 4: Implement the Changes

Execute the approved plan:
- Use `TodoWrite` to track implementation tasks.
- Write clean, minimal code that follows existing codebase patterns.
- **Add no comments to the code you write or change.** No explanatory comments, no banners, no docstring on a symbol that did not have one, no `TODO`s, no commented-out code — and never a reference to the Linear ticket, task, or initiative (`# ENG-123`, `// per PLAT-1180`, `# for the X initiative`). A comment written alongside the code restates the line, goes stale, and makes the reviewer read past it to reach the change. Write the code so it does not need one, and put every explanation in the commit message and PR description instead. Exempt because they are program input rather than commentary: linter and type directives, build pragmas, codegen markers, required license headers, and any doc-comment CI fails without. Leave comments already in the file alone unless your change makes one untrue — then correct or delete it.

  **There is no ticket here, so the shape that rule catches is the comment pointing back at the request itself** — `// as asked`, `# per the request`, `# requested fix` — and it is cut on exactly the same grounds: it tells a future reader nothing about the code and goes stale the moment the line moves.

  **A comment-dense file does not create an exception, and this is where the rule is most often broken.** Some files document the rationale behind every constant — one service spends 25 lines explaining a single retry policy's arithmetic. Writing the new code to match that density and stripping the comments afterwards wastes a full editing pass; decide before the first line that the new code carries none, and route the reasoning to the commit message and PR description as you go. Then say so in the summary, because the asymmetry is genuinely visible in review: a new timeout sitting silently beside a heavily-justified one looks like an oversight rather than a convention. Let the user reverse it in one word if they want the local convention honoured instead.
- Run any relevant tests or linters if the project has them configured.
- **When the real verification command needs credentials you cannot get, build an offline harness rather than shipping unverified logic.** In a Terraform repo the honest ceiling is usually `terraform validate` — `terraform plan` needs a gcloud ADC reauth this session cannot perform (`invalid_grant` / `invalid_rapt`), and some modules additionally need an API key from the environment. `validate` type-checks but never *evaluates* a `precondition`, so a guard that passes validate can still crash at plan time. Copy the new locals into a provider-free config in the scratchpad and drive it with `terraform -chdir=<abs> apply -auto-approve -var mode=…`, outputting the guard lists: it needs no credentials and it tests the counterfactuals — the mis-ordered rule, the deleted rule, the bad value — which no real plan of a correct config ever exercises. That caught a genuine bug once: **HCL's `||` does not short-circuit**, so `length(xs) == 0 || i < xs[0]` throws `Invalid index` on an empty list instead of taking the left branch. Use a sentinel — `try([…][0], length(…))` — not a guarded index. Two harness caveats: `concat` of rule objects with differing attributes yields a *tuple*, so a `var.mode ? concatA : concatB` ternary fails on inconsistent types (use uniform stub objects, or select with a filtered list); and a `for` result expression like `rule.id` is only evaluated for elements passing the `if`.

  **Get the terraform version from the module's own `.mise.toml`, not from a note someone wrote.** Several modules carry one, and that pin is what Atlantis uses, so it is the version a change must actually pass on. A `TFENV_TERRAFORM_VERSION=…` override mentioned elsewhere may predate the pin and silently verify against a version nobody runs. `mise exec terraform@<pinned> -- terraform fmt -check` / `validate` is the check that counts; running the other version too is cheap and worth it, since `init` is the slow part and `fmt` needs none.
- **Terraform renders long strings across lines, so parse what actually ships.** `yamlencode` folds a >80-column value onto continuation lines. That is valid YAML and round-trips correctly, but confirm it rather than assuming: render the exact values block and parse it. `python3` here has no `yaml` module — `ruby -ryaml` does, and `jq` is available.
- **Clean up what `terraform init` leaves behind.** It drops a ~430 MB `.terraform/` in the module directory. It is gitignored (`terraform/.gitignore: **/.terraform*`) so `git status` stays clean and you will not notice — `rm -rf` it when done.
- Mark each todo as completed as you finish it.

After implementation is complete, give the user a summary of what was changed, which branch it is on, and whether any Step 2b check escalated the run.

## Step 5: Commit Message and Description

Immediately after implementation is complete — do not wait for the user to commit or ask for these.

**What these are for depends on the branch mode, and the difference is worth stating plainly.** On `--branch new` (or any escalated run) this is the `fix-linear` path: a commit message and a description the user pastes into the PR they open later. On `--branch default` **there is no pull request** — nothing is opened, nothing is reviewed, nothing has a description field. So the description is a change summary for the commit body and for the user's own reference, and `--changes-diagram` defaults to `false` precisely because there is nothing to attach a diagram to.

### 5a. Commit message

Invoke the `commit-msg` skill using the `Skill` tool.

### 5b. Change description

**Immediately** invoke the `changes-description` skill using the `Skill` tool. Do NOT wait for the user to respond to the commit message first — invoke it in the same turn, back-to-back with the commit message, so the work is already running while they read the commit message. The `commit-msg` skill ends with a suggestion to run `/commit`, but you must continue and invoke `changes-description` before yielding to the user.

Pass `--one-shot` unless `--one-shot-description false` was given: a single writer plus the measured word budget and the fact-check, which is the right shape for a change small enough to have gone to the default branch. Pass nothing (the full debate) when the flag is `false` or the user asked for a thorough description.

If `changes-description` launches its debate as a background workflow, it prints a run ID and yields the turn — that is correct, not a stall. Yield with it: the description arrives when the completion notification does, and blocking on it (`TaskOutput`, `Monitor`, a poll loop) only takes the user's prompt line away for the length of the run.

### 5c. Call-flow diagram (`--changes-diagram true` only)

Skipped entirely by default. When the flag is `true`, invoke the `changes-diagram` skill using the `Skill` tool once the description is away — it diffs the branch against its base and publishes one self-contained page: a call-flow chart of the changed functions, or a file-and-import map when the change is Terraform, Go or TypeScript. Pass the base explicitly on the `--branch default` path (`origin/<DEFAULT_BRANCH>`), since there is no feature branch for it to infer one from. If the skill is not installed on this machine, say so rather than hand-rolling a diagram.

### 5d. Re-print the commit message, verbatim

The description output is long, so by the time it finishes the commit message from 5a has scrolled far up the terminal. In the turn that presents the description, close by repeating it — unchanged from what `commit-msg` produced, no re-generation, no re-wording, no summary of it — in its own fenced block under a `Commit message` heading, so both blocks the user copies sit next to each other at the bottom. If the user corrected the commit message in between, repeat the corrected version.

## Important Rules

1. **NEVER push, NEVER open a pull request, and never modify external state.** Local git is yours: creating a branch, creating a worktree, and — when the user asks for it — committing are all fine. **`--branch default` means the commit lands on the default branch, not that it leaves this machine.** That distinction matters more here than anywhere else in these skills: a stray push of a feature branch creates a branch nobody asked for, while a stray push of the default branch is a direct write to the branch every other checkout, every CI pipeline, and (with Atlantis) every apply is cut from. So do not run `git push` in any form — not with `-u`, not as a `--dry-run` "check", not because "it would be rejected anyway" — and do not create a pull request. Pushing is the user's explicit action, always. Never remove a worktree the user didn't ask you to — cleanup is the user's call. **This rule scopes to this skill's own flow.** Naming `/fix-autonomous` in the arguments *is* the user's explicit action, and it hands the run to a skill that owns pushing and merging under its own rules — see **Delegation** above, and never quote this rule back as a reason to refuse it.
2. **Respect uncommitted work.** Never discard or stash uncommitted changes without the user's explicit approval. A dirty tree escalates the branch mode (Step 2b); it never gets cleared to keep the cheap path.
3. **Ask, don't assume.** If the problem statement is vague, ask the user rather than guessing — and where the statement and the code disagree, the code wins and you say so out loud.
4. **Follow existing patterns.** Match the coding style, naming conventions, and architecture of the existing codebase.
5. **Keep the user informed.** Summarize what you're doing at each major step, and announce every escalation in one line as it happens, with the reason.
6. **No comments in the code.** Do not add explanatory comments, docstrings, or references to the request in code you write or modify — the full rule is in Step 4. Explanation goes in the commit message and PR description, never the source. Machine-read directives (linter suppressions, build pragmas, a doc-comment CI requires) are program input, not commentary, and stay allowed.
7. **Escalation is one-way within a run.** Once the Terraform or protected-branch check has fired, `--branch default` is off the table for the rest of the run even if the user restates the flag — explain why rather than complying. The dirty-tree check is the one that can clear: if the user commits or stashes their own work themselves, re-run `git status --porcelain` and the default-branch path is available again.

## Step 6: Self-Improvement

After the full workflow is complete, reflect on how the execution went. Consider:

- Was the problem statement specific enough to plan from, or did it take several rounds of clarification?
- Did Step 1b's verification find anything the statement got wrong — and did saying so change the implementation?
- Did an escalation fire, and did it fire at the right time (before the first edit, or late enough to need Step 2e)?
- Was `--branch default` the right call in hindsight, or did the change turn out to deserve review?
- Did the implementation plan hold up, or did unexpected codebase patterns force changes mid-implementation?
- Were there test failures or linter issues that required rework?
- Did `commit-msg` and `changes-description` produce accurate output on the first try, or did the user need to correct them?

If any issues were encountered, **edit this skill file** (`~/.claude/skills/fix-freeform/SKILL.md`) to add instructions, warnings, or tips that would prevent the same issue next time. Keep edits surgical — add a note near the relevant step rather than rewriting sections. Briefly tell the user what was updated and why.
