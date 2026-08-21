# Fix — Linear Ticket Implementation

Implement the changes required by a Linear ticket, working on a properly set up feature branch.

**Parameter:** `$ARGUMENTS` — the Linear ticket identifier (e.g., `ENG-123`).

If no argument is provided, ask the user for the ticket ID and stop.

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

## Step 2: Set Up the Worktree

By default this skill isolates the work in its own **git worktree** — a separate working directory on its own branch that shares the repo's `.git`. This lets you run several fixes in parallel (one terminal/session per worktree) without branch checkouts colliding in a single working tree.

**Escape hatch (in-place checkout):** If `$ARGUMENTS` contains `in place`, `--here`, or `no worktree` (case-insensitive), skip the worktree setup and use **Step 2-INPLACE** instead. Also fall back to Step 2-INPLACE if the repo cannot host worktrees (e.g. `git worktree list` errors).

### 2a. Determine the default branch

```bash
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'
```

If that fails, fall back:

```bash
git branch -r | grep -E 'origin/(main|master)$' | head -1 | sed 's@.*origin/@@'
```

Store the result as `DEFAULT_BRANCH`.

### 2b. Check whether you're already set up

```bash
git rev-parse --abbrev-ref HEAD
```

If the current branch already matches `BRANCH_NAME` (case-insensitive), you're already in the right worktree/branch. Fetch and merge the latest default branch, then skip to Step 3:

```bash
git fetch origin <DEFAULT_BRANCH> --quiet
git merge origin/<DEFAULT_BRANCH> --no-edit
```

If the merge has conflicts, stop and tell the user so they can resolve them before continuing.

### 2c. Create and enter the worktree

Set `WORKTREE_PATH` to `.claude/worktrees/<BRANCH_NAME>` (relative to the repo root). Run these commands from the **main repo root**.

1. Fetch the latest default branch:
   ```bash
   git fetch origin <DEFAULT_BRANCH> --quiet
   ```
2. Check whether a worktree for this branch already exists:
   ```bash
   git worktree list --porcelain
   ```
   If `BRANCH_NAME` (or `WORKTREE_PATH`) is already listed, **enter it** with the `EnterWorktree` tool (`path:` = that worktree's path), merge `origin/<DEFAULT_BRANCH>` (`--no-edit`), then skip to Step 3 — its dependencies are already installed, so skip Step 2d too.
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

### 2d. Offer to install dependencies

A fresh worktree has no installed dependencies or build artifacts. Detect the project's package manager from files present in the worktree and **offer to run the install command — wait for the user's approval before running it**:

- `package-lock.json` → `npm install` · `yarn.lock` → `yarn` · `pnpm-lock.yaml` → `pnpm install` · `bun.lockb` → `bun install`
- `uv.lock` → `uv sync` · `poetry.lock` → `poetry install` · `requirements.txt` → `pip install -r requirements.txt`
- `go.mod` → `go mod download` · `Gemfile` → `bundle install` · `Cargo.toml` → `cargo fetch`

If several match, prefer the one matching the lockfile present. If none match, or the user declines, note that dependencies are not installed and continue.

## Step 2-INPLACE: In-Place Branch Checkout (escape hatch only)

Use this **only** when the escape hatch in Step 2 applies — it's the original single-working-tree behavior. Compute `DEFAULT_BRANCH` as in Step 2a first.

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

If comments were fetched, display them below the summary:
> **Comments** (N total):
> - **Author** (date): comment body (first ~2 sentences or 150 chars each)

Include ALL comments — these often contain critical context, decisions, and clarifications that inform the implementation.

## Step 3e: Detect "address MR comments" tickets

After displaying the ticket, check if the ticket is about **addressing comments or feedback left on a merge request**. Look for signals like:
- Title or description mentions "address comments", "address feedback", "follow up" on a merge request/MR
- Description contains a GitLab MR URL (e.g., `https://gitlab.com/.../merge_requests/NNN`)

If the ticket matches this pattern:
1. Extract the MR URL from the description.
2. **Invoke the `fix-feedback` skill** using the `Skill` tool, passing the MR URL as the argument.
3. After the `fix-feedback` skill completes, skip Steps 4 and 5 (plan and implement) — the fix-feedback skill handles everything.
4. Proceed directly to Step 6 (commit message and MR description).

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

## Step 4: Plan the Implementation

**Gate: do not enter plan mode until the Step 3f checkpoint is satisfied** — either you have stated the parent/sibling/related context to the user, or you have confirmed the ticket has no parent. If you cannot yet do either, return to Step 3f before continuing.

Now enter plan mode using `EnterPlanMode`. Use the ticket title, description, comments, the parent/sibling/related context from Step 3f, and any labels/context to:

1. **Explore the codebase** — use Glob, Grep, and Read to understand relevant files, existing patterns, and architecture.
2. **Design an implementation approach** — identify which files need changes, what the changes are, and in what order.
3. **Ask clarifying questions** — if the ticket description is ambiguous or missing details, use `AskUserQuestion` to clarify with the user before finalizing the plan.
4. **Present the plan** for user approval via `ExitPlanMode`.

Once the user approves the plan, implement the changes.

## Step 5: Implement the Changes

Execute the approved plan:
- Use `TodoWrite` to track implementation tasks.
- Write clean, minimal code that follows existing codebase patterns.
- **Add no comments to the code you write or change.** No explanatory comments, no banners, no docstring on a symbol that did not have one, no `TODO`s, no commented-out code — and never a reference to the Linear ticket, task, or initiative (`# ENG-123`, `// per PLAT-1180`, `# for the X initiative`). A comment written alongside the code restates the line, goes stale, and makes the reviewer read past it to reach the change. Write the code so it does not need one, and put every explanation in the commit message and MR description instead. Exempt because they are program input rather than commentary: linter and type directives, build pragmas, codegen markers, required license headers, and any doc-comment CI fails without. Leave comments already in the file alone unless your change makes one untrue — then correct or delete it.
- Run any relevant tests or linters if the project has them configured.
- Mark each todo as completed as you finish it.

After implementation is complete, give the user a summary of what was changed.

## Step 6: Commit Message and MR Description

Immediately after implementation is complete — do not wait for the user to commit or ask for these:

1. Invoke the `commit-msg` skill using the `Skill` tool to generate a commit message.
2. **Immediately** invoke the `changes-description` skill using the `Skill` tool to generate an MR description. Do NOT wait for the user to respond to the commit message first — both outputs must be presented in the same turn, back-to-back. The `commit-msg` skill ends with a suggestion to run `/commit`, but you must continue and invoke `changes-description` before yielding to the user. Pass `--quick` unless the branch is large or the user asked for a thorough description — `changes-description` runs a multi-agent debate, and the full-length version is disproportionate for a routine ticket.

## Important Rules

1. **NEVER modify external state beyond local git branch/worktree operations.** Creating a local branch or worktree is fine; do not update Linear tickets, push branches, or create MRs unless explicitly asked. Never remove a worktree the user didn't ask you to — cleanup is the user's call.
2. **Respect uncommitted work.** Never discard or stash uncommitted changes without the user's explicit approval.
3. **Ask, don't assume.** If the ticket is vague, ask the user for clarification rather than guessing.
4. **Follow existing patterns.** Match the coding style, naming conventions, and architecture of the existing codebase.
5. **Keep the user informed.** Summarize what you're doing at each major step so the user can course-correct early.
6. **No comments in the code.** Do not add explanatory comments, docstrings, or ticket references to code you write or modify — the full rule is in Step 5. Explanation goes in the commit message and MR description, never the source. Machine-read directives (linter suppressions, build pragmas, a doc-comment CI requires) are program input, not commentary, and stay allowed.

## Step 7: Self-Improvement

After the full workflow is complete, reflect on how the execution went. Consider:

- Did branch setup work smoothly, or were there edge cases (dirty working tree, missing remote, merge conflicts)?
- Was the Linear ticket description clear enough to plan from, or were multiple rounds of clarification needed?
- Did ticket comments contain critical context that changed the implementation approach?
- Did the implementation plan hold up, or did unexpected codebase patterns force changes mid-implementation?
- Were there test failures or linter issues that required rework?
- Did the commit-msg and changes-description skills produce accurate output on the first try, or did the user need to correct them?

If any issues were encountered, **edit this skill file** (`~/.claude/skills/fix-linear/SKILL.md`) to add instructions, warnings, or tips that would prevent the same issue next time. Keep edits surgical — add a note near the relevant step rather than rewriting sections. Briefly tell the user what was updated and why.
