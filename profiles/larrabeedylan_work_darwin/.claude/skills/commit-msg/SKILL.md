# Commit Message Generator

Generate a single-line conventional commit message based on the current staged and unstaged changes. The subject line doubles as the MR title, so it must be descriptive enough to stand on its own in a merge request list.

## Step 1: Gather Context

### 1a. Get the current branch name

```bash
git rev-parse --abbrev-ref HEAD
```

Store as `BRANCH_NAME`.

### 1b. Extract ticket ID (if present)

Check if `BRANCH_NAME` contains a ticket identifier matching the pattern `[A-Z]+-[0-9]+` (e.g., `ENG-123`, `PLAT-456`). If found, store it as `TICKET_ID`. If not, `TICKET_ID` is empty.

### 1c. Get the diff

Get staged changes first:

```bash
git diff --cached
```

If nothing is staged, fall back to unstaged changes:

```bash
git diff
```

If both are empty, check for untracked files:

```bash
git status --porcelain
```

If there are no changes at all, tell the user: "No changes detected. Stage your changes with `git add` first." and stop.

### 1d. Get the diff stat

```bash
git diff --cached --stat
```

(Or `git diff --stat` if nothing is staged.)

## Step 2: Generate the Commit Message

Analyze the diff and produce a **single-line** conventional commit message. No body. No trailing blank lines. One line only.

### Format

If `TICKET_ID` exists, use it as the conventional commit scope:
```
<type>(TICKET_ID): <subject>
```

If no ticket ID:
```
<type>: <subject>
```

### Type

Always use a conventional commit type:
- **feat** — new feature or capability
- **fix** — bug fix
- **refactor** — restructuring without behavior change
- **chore** — config, dependencies, CI, tooling
- **docs** — documentation only
- **test** — adding or modifying tests
- **style** — formatting, whitespace, linting (no logic change)

### Subject line

- Imperative mood ("add", "fix", "update" — not "added", "fixes", "updated")
- Lowercase after the prefix, no period at the end
- The full line must be under 72 characters
- Specific — name the actual thing changed (function, file, service, config key)
- Must read well as an MR title — a reviewer scanning a list of MRs should understand the change from the subject alone

### Examples

With ticket:
```
fix(ENG-123): handle nil pointer in retry logic
```

```
feat(PLAT-456): add prometheus metrics for batch processor
```

Without ticket:
```
chore: bump helm chart to 3.2.1
```

```
feat: add request deduplication to ingestion pipeline
```

## Step 3: Present the Message

Print the suggested single-line commit message inside a code block so the user can copy it. Then offer:

"You can run `/commit` to commit with this message, or edit it as needed."

## Guidelines

- **One line only.** Never include a body — if the subject needs more context, make the subject more specific rather than adding a body.
- **Be precise.** Use actual names from the diff — functions, files, config keys. Don't paraphrase loosely.
- **One concern per message.** If the diff contains unrelated changes, note this to the user and suggest splitting into separate commits.
- **Don't editorialize.** No "improve", "clean up", "better" — state the concrete change.
