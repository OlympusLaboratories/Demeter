# Explain — PR Change Breakdown

Read a GitHub pull request and produce a clear, sequential explanation of what the PR does, how it does it, and why — so the reader can understand the changes without getting lost in the diff.

**Parameter:** `$ARGUMENTS` — the full URL of a GitHub pull request (e.g., `https://github.com/owner/repo/pull/123`).

If no argument is provided, ask the user for the PR URL and stop.

## Step 1: Parse the PR URL

Extract `owner`, `repo`, and `pr_number` from the URL.

For a URL like `https://github.com/acme/my-repo/pull/42`:
- `owner` = `acme`
- `repo` = `my-repo`
- `pr_number` = `42`

If the URL doesn't look like a GitHub PR URL, warn the user and stop.

## Step 2: Load the PR Context

Use `~/.claude/scripts/github-api.sh` to fetch PR data. This script reads the GitHub token from the `GITHUB_PERSONAL_ACCESS_TOKEN` environment variable, so the token never enters conversation context. Owner, repo, and PR number are passed as separate plain arguments (no URL-encoding needed).

Make all four calls **in parallel in a single message**:
```bash
~/.claude/scripts/github-api.sh pr-info <owner> <repo> <pr_number>
~/.claude/scripts/github-api.sh pr-reviews <owner> <repo> <pr_number>
~/.claude/scripts/github-api.sh pr-changes <owner> <repo> <pr_number>
~/.claude/scripts/github-api.sh pr-commits <owner> <repo> <pr_number>
```

Each command outputs one JSON object per line:
- **`pr-info`** — one object with `title`, `description`, `state`, `author`, `web_url`, `source_branch`, `target_branch`, `number`, `draft`.
- **`pr-reviews`** — one object per review item, each tagged with a `type`: `inline` (a diff-line review thread, with `resolved`, `position.new_path`, `position.new_line`, and nested `replies`), `review` (a top-level review body with `review_state` like APPROVED / CHANGES_REQUESTED), or `general` (a PR-level comment).
- **`pr-changes`** — one object per changed file with `old_path`, `new_path`, `diff` (the patch hunk), and `status`.
- **`pr-commits`** — one object per commit with `short_id`, `title`, `message`, `author_name`, `created_at`.

## Step 3: Build a Mental Model

Before writing anything, silently analyze the collected data to understand the PR holistically:

1. **Read the PR description carefully.** This is the author's own explanation — it's the single best source of *why* the change exists. Note any linked tickets, motivation, or context.
2. **Scan the commit list.** The commit messages and their order reveal the author's logical progression.
3. **Categorize every changed file** into one of these buckets:
   - **Core logic** — the files where the main behavioral change lives
   - **Supporting changes** — tests, migrations, configs, type definitions, or helpers that exist to support the core change
   - **Incidental/mechanical** — auto-generated files, formatting, dependency lockfiles, renames with no logic change
4. **Identify the reviewer discussion themes.** Group the `pr-reviews` items by topic. Note any unresolved threads (`inline` items where `resolved` is false) and any `CHANGES_REQUESTED` reviews — these highlight tricky or controversial parts of the PR that deserve extra explanation.
5. **Read relevant surrounding code in the local codebase** using `Read`, `Grep`, and `Glob` to understand the context the changes sit within. The diff alone is not enough — you need to understand the system the code is part of. Focus on:
   - Functions/classes that the changed code calls or is called by
   - Related modules or services that interact with the changed code
   - Existing patterns or conventions in the same area of the codebase

## Step 4: Write the Explanation

Print the explanation in a single, well-structured message. Use the following format:

---

### PR Overview

**Title:** #<number> — "PR Title"
**Author:** @author_name
**Target:** `target_branch`

**Purpose (one paragraph):** A plain-language summary of what this PR accomplishes and *why* it exists. Reference the linked ticket or motivation from the description. Avoid jargon — explain domain-specific terms when they first appear.

---

### How to Read This PR

Before diving in, orient the reader:

- **N files changed** — briefly state the overall scope (e.g., "Adds a new service, updates two API endpoints, and adds tests")
- **Start here:** Name the 1-2 core files the reader should look at first. Explain why these are the heart of the change.
- **Then read:** List the supporting files in the order they should be read, grouped logically.
- **You can skip:** List any incidental/mechanical files and why they don't need close review.

---

### Change-by-Change Breakdown

This is the core of the explanation. Walk through the changes **in logical reading order** (NOT alphabetical, NOT by diff order). Group related files together.

For each logical group or file:

**`path/to/file.ext`** (or group heading if multiple files form one logical unit)

- **What changed:** Describe the concrete code changes in plain terms. Mention specific functions, classes, or blocks that were added/modified/removed. Use short inline code references where helpful, but keep the language accessible.
- **How it works:** Explain the mechanism — what does the new/changed code actually do at runtime? Walk through the logic step by step if it's non-trivial. If a new pattern or abstraction is introduced, explain it.
- **Why:** Explain why this change is needed in the context of the PR's goal. Connect it back to the purpose. If the approach is non-obvious, explain why *this* approach was chosen (use commit messages, PR description, or reviewer discussions as evidence).

Keep each file/group explanation **concise but complete**. A few sentences per bullet is ideal. For simple changes (e.g., adding a test that mirrors the implementation), a single sentence is fine.

---

### Key Design Decisions

If the PR involves non-obvious choices, list them:

- **Decision:** What was chosen and what alternatives existed
- **Rationale:** Why this approach, based on PR description, reviewer discussions, or codebase context

Only include this section if there are genuine decisions worth calling out. Skip it for straightforward PRs.

---

### Open Questions

If reviewer discussions surfaced unresolved questions or debates, summarize them briefly so the reader is aware of areas that may still be in flux.

Only include this section if there are genuine open threads. Skip it for clean PRs.

---

## Step 5: Offer to Go Deeper

After printing the explanation, offer:

> Want me to dive deeper into any specific file or change? Just name it and I'll walk through the code in detail.

Wait for the user to reply. If they ask about a specific file or area, use `Read` to load the relevant code and provide a more detailed, line-by-line walkthrough with full codebase context.

## Important Rules

1. **Write for someone unfamiliar with this part of the codebase.** Assume the reader is a competent engineer who doesn't know this specific area. Define terms, explain patterns, and provide context.
2. **Use plain language.** Avoid unnecessary jargon. When you must use a technical term, briefly explain it on first use.
3. **Logical order, not diff order.** Present changes in the order that makes them easiest to understand, not the order git happens to list them.
4. **Connect every change back to the "why".** Never just describe *what* changed without explaining *why* it changed. The PR description, commit messages, and reviewer discussions are your evidence.
5. **Be honest about complexity.** If something is genuinely complex, say so and take extra care explaining it. Don't gloss over hard parts.
6. **Use the local codebase.** The user is expected to have the repository checked out locally. Use `Read`, `Grep`, and `Glob` to explore surrounding code and provide richer context than the diff alone can give.
7. **Keep it scannable.** Use headers, bold text, and bullet points so the reader can skim to the section they care about.
8. **Don't editorialize.** This skill explains, it doesn't review. Don't critique the code or suggest improvements — that's what the fix-feedback skill is for.

## Step 6: Self-Improvement

After the session, reflect on how the execution went. Consider:

- Did URL parsing work correctly for the given GitHub URL?
- Were there issues fetching data (pagination, permissions, empty responses)?
- Was the explanation the right level of detail — too shallow or too deep?
- Did the logical ordering make sense, or would a different reading order have been clearer?
- Was the local codebase context helpful in enriching the explanation?

If any issues were encountered, **edit this skill file** (`~/.claude/skills/changes-explain/SKILL.md`) to add instructions, warnings, or tips that would prevent the same issue next time. Keep edits surgical. Briefly tell the user what was updated and why.
