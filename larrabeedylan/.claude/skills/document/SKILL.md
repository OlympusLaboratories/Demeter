# Document — Update Project Documentation

Audit and update `README.md` and `AGENTS.md` files so they accurately reflect the current state of the codebase. This ensures future sessions (and other contributors) have full context about structure, conventions, and design decisions.

**Parameter:** `$ARGUMENTS` — optional path scope (e.g., `src/ingestion`). If omitted, operates on the entire repo.

## Step 1: Determine Scope

### 1a. Get recent changes

```bash
git log --oneline --name-only -20
```

Store the list of changed files as `CHANGED_FILES`.

If `$ARGUMENTS` is provided, filter `CHANGED_FILES` to only those under the given path. Store the scoped root as `SCOPE_ROOT`. If `$ARGUMENTS` is empty, `SCOPE_ROOT` is the repo root.

### 1b. Identify affected directories

From `CHANGED_FILES`, collect every unique directory (and its parents up to `SCOPE_ROOT`) that contains at least one changed file. These are the directories whose documentation may need updating. Store as `AFFECTED_DIRS`.

## Step 2: Discover Existing Documentation

For each directory in `AFFECTED_DIRS` (starting from the deepest and working up to `SCOPE_ROOT`):

1. Check if a `README.md` exists in that directory.
2. Check if an `AGENTS.md` exists in that directory.
3. Read any that exist.

Also read:
- `CLAUDE.md` at the repo root (for repo-level conventions).
- `README.md` at the repo root.

Store all discovered documentation files as `DOC_FILES`.

## Step 3: Audit Each Documentation File

For each file in `DOC_FILES`, compare its contents against the **actual current state** of the directory it documents. Check for:

### 3a. Structural accuracy
- Are all files and subdirectories mentioned? Are any listed files missing (deleted or renamed)?
- Are file/directory descriptions still correct?
- Are any new files or directories undocumented?

### 3b. Convention and pattern accuracy
- Do described conventions still match what the code actually does?
- Are architectural patterns described accurately?
- Are setup/install/build instructions still correct?

### 3c. Completeness of design context
- Do recent changes introduce new patterns, conventions, or architectural decisions that aren't documented?
- Are there non-obvious design decisions in recent commits whose reasoning should be captured?

To answer these questions, **read the actual files and directories** — do not rely on assumptions. Use Glob to list directory contents, Read to inspect files, and Grep to verify patterns mentioned in docs.

## Step 4: Present Findings

Before making any changes, present a summary to the user:

> **Documentation audit for `SCOPE_ROOT`**
>
> **Files to update:**
> - `path/to/README.md` — [what needs updating and why]
> - `path/to/AGENTS.md` — [what needs updating and why]
>
> **New files to create:**
> - `path/to/AGENTS.md` — [why this directory warrants documentation]
>
> **No changes needed:**
> - `path/to/README.md` — already accurate

Only propose creating new documentation files for directories that have meaningful structure worth documenting (multiple files with distinct roles, non-obvious conventions, or architectural significance). Not every directory needs an `AGENTS.md`.

Wait for user approval before proceeding.

## Step 5: Apply Updates

For each approved change:

1. **Edit existing files** — use surgical edits to update outdated sections. Preserve the existing structure and voice. Do not rewrite sections that are still accurate.
2. **Create new files** — follow the conventions of neighboring documentation files for tone and format.
3. **Update `CLAUDE.md`** — if any changes affect repo-level structure, conventions, or installer behavior, update `CLAUDE.md` at the repo root.

### Writing guidelines

- **Be factual.** Document what exists and why, not aspirational state.
- **Capture the "why."** When recent changes introduced a design decision, include the reasoning — this is the most valuable context for future sessions.
- **Stay concise.** A table of files with one-line descriptions is better than verbose paragraphs.
- **Match existing style.** If the file uses tables, keep using tables. If it uses bullet lists, keep using bullet lists.
- **No filler.** Don't add sections just for completeness. Every line should earn its place.

## Step 6: Summary

After all edits are applied, print a short summary:

> **Updated N documentation files:**
> - `path/to/file.md` — [one-line description of what changed]

## Important Rules

1. **Read before writing.** Always read the current file contents and directory state before proposing changes. Never guess.
2. **Don't create unnecessary docs.** A directory with one file and no conventions doesn't need an `AGENTS.md`.
3. **Preserve existing content.** Only change what's actually wrong or missing. Don't reformulate sentences that are already clear and correct.
4. **No secrets in docs.** Never document API keys, tokens, or sensitive config values.
5. **Scope matters.** If `$ARGUMENTS` scopes to a subdirectory, don't update docs outside that scope unless they directly reference the scoped area.
