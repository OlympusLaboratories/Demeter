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

## Step 2: Set Up the Branch

### 2a. Determine the default branch

```bash
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'
```

If that fails, fall back:

```bash
git branch -r | grep -E 'origin/(main|master)$' | head -1 | sed 's@.*origin/@@'
```

Store the result as `DEFAULT_BRANCH`.

### 2b. Check the current branch

```bash
git rev-parse --abbrev-ref HEAD
```

Store as `CURRENT_BRANCH`.

### 2c. Branch logic

**If `CURRENT_BRANCH` already matches `BRANCH_NAME`** (case-insensitive):

1. Fetch the latest default branch:
   ```bash
   git fetch origin <DEFAULT_BRANCH> --quiet
   ```
2. Merge the default branch into the current branch to pick up any new changes:
   ```bash
   git merge origin/<DEFAULT_BRANCH> --no-edit
   ```
3. If the merge has conflicts, stop and tell the user about the conflicts so they can resolve them before continuing.

**Otherwise (not on the target branch):**

1. Check for uncommitted changes. If there are any, warn the user and stop — do not switch branches with dirty working tree.
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

Use `mcp__claude_ai_Linear__get_issue` with `id: TICKET_ID` (e.g., `PLAT-1180`). This returns the full issue including title, description, status, labels, and assignee.

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

## Step 3f: Load Initiative Context (if this ticket is a subtask)

Determine whether this ticket is a **subtask of a larger initiative** — i.e. whether the Linear issue has a **parent**. Check the `get_issue` result for a `parent` field (and any `project`/`initiative`/relationship linkage). If those fields aren't present in the response, re-fetch with a relations-capable call (`ToolSearch: select:mcp__claude_ai_Linear__get_issue`) and inspect for a parent.

**If the ticket has a parent (or is otherwise clearly one piece of a larger initiative), gather the surrounding context before planning** — look at sibling tasks, the parent task, and tickets related to the parent for full context on the initiative this ticket is part of:

1. **Parent task** — fetch the parent issue (`get_issue` on the parent's ID) for its full title, description, and comments; this frames the overall goal.
2. **Sibling tasks** — list the parent's other children (`ToolSearch: select:mcp__claude_ai_Linear__list_issues`, filtered by the parent) to see the related work landing alongside this ticket and avoid overlap or conflicting approaches.
3. **Tickets related to the parent** — fetch issues linked/related to the parent (relations, blocks/blocked-by, or the parent's project/initiative issues) for the wider design intent.

Read this material the way you read the ticket itself: it defines the initiative this ticket belongs to, and the implementation should fit that larger design rather than solving the subtask in isolation. Briefly tell the user what initiative this ticket rolls up to and any sibling/parent context that will shape the approach.

**If the ticket has no parent and isn't part of a larger initiative, skip this step.**

## Step 4: Plan the Implementation

Now enter plan mode using `EnterPlanMode`. Use the ticket title, description, comments, any parent/initiative context from Step 3f, and any labels/context to:

1. **Explore the codebase** — use Glob, Grep, and Read to understand relevant files, existing patterns, and architecture.
2. **Design an implementation approach** — identify which files need changes, what the changes are, and in what order.
3. **Ask clarifying questions** — if the ticket description is ambiguous or missing details, use `AskUserQuestion` to clarify with the user before finalizing the plan.
4. **Present the plan** for user approval via `ExitPlanMode`.

Once the user approves the plan, implement the changes.

## Step 5: Implement the Changes

Execute the approved plan:
- Use `TodoWrite` to track implementation tasks.
- Write clean, minimal code that follows existing codebase patterns.
- **Do not reference the ticket, task, or initiative in code comments.** Comments should explain the code for future maintainers — never cite the Linear ticket/task/initiative that prompted the change (no `# ENG-123`, `// per PLAT-1180`, `# for the X initiative`, etc.). That context belongs in the commit message and MR description, not the source.
- Run any relevant tests or linters if the project has them configured.
- Mark each todo as completed as you finish it.

After implementation is complete, give the user a summary of what was changed.

## Step 6: Commit Message and MR Description

Immediately after implementation is complete — do not wait for the user to commit or ask for these:

1. Invoke the `commit-msg` skill using the `Skill` tool to generate a commit message.
2. **Immediately** invoke the `changes-description` skill using the `Skill` tool to generate an MR description. Do NOT wait for the user to respond to the commit message first — both outputs must be presented in the same turn, back-to-back. The `commit-msg` skill ends with a suggestion to run `/commit`, but you must continue and invoke `changes-description` before yielding to the user.

## Important Rules

1. **NEVER modify external state beyond git branch operations.** Do not update Linear tickets, push branches, or create MRs unless explicitly asked.
2. **Respect uncommitted work.** Never discard or stash uncommitted changes without the user's explicit approval.
3. **Ask, don't assume.** If the ticket is vague, ask the user for clarification rather than guessing.
4. **Follow existing patterns.** Match the coding style, naming conventions, and architecture of the existing codebase.
5. **Keep the user informed.** Summarize what you're doing at each major step so the user can course-correct early.
6. **No ticket references in code comments.** Never mention the Linear ticket, task, or initiative in comments on generated code — it's noise for future maintainers. Keep that context in the commit message and MR description instead.

## Step 7: Self-Improvement

After the full workflow is complete, reflect on how the execution went. Consider:

- Did branch setup work smoothly, or were there edge cases (dirty working tree, missing remote, merge conflicts)?
- Was the Linear ticket description clear enough to plan from, or were multiple rounds of clarification needed?
- Did ticket comments contain critical context that changed the implementation approach?
- Did the implementation plan hold up, or did unexpected codebase patterns force changes mid-implementation?
- Were there test failures or linter issues that required rework?
- Did the commit-msg and changes-description skills produce accurate output on the first try, or did the user need to correct them?

If any issues were encountered, **edit this skill file** (`~/.claude/skills/fix-linear/SKILL.md`) to add instructions, warnings, or tips that would prevent the same issue next time. Keep edits surgical — add a note near the relevant step rather than rewriting sections. Briefly tell the user what was updated and why.
