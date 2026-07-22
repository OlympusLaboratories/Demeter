# Weekly Engineering Snippet Generator

Generate a weekly engineering snippet for Dylan Larrabee (dylan@gridmatic.com) by pulling data from GitLab, Linear, and a manually-curated context file.

## Step 0: Determine Time Range

The snippet covers the past 7 days. **Immediately** use the Bash tool to calculate dates — do not ask the user for dates:
- If the user provided an argument ($ARGUMENTS), use that as the start date
- Otherwise, use today minus 7 days as the start date
- End date is always today
- **IMPORTANT:** Use `YYYY-MM-DD` format (not full ISO 8601 with time component) for date filters.

**IMPORTANT:** Run each `date` command as its own Bash tool call — do NOT wrap them in `echo` statements, as `echo` triggers an unnecessary user permission prompt. Just run the bare `date` command directly.

```
date -u +%Y-%m-%d
date -u -d "7 days ago" +%Y-%m-%d
```

## Step 1: Read Slack/Discussion Context

Read the file `~/.claude/skills/reflect-week/slack-context.md` using the Read tool. This file contains Slack threads, discussions, and other context that Dylan has pasted before running this command.

- If the file is empty or only has the template header, that's fine — skip Slack context and proceed with GitLab + Linear data only.
- If it has content, parse the pasted threads for: incident responses, architecture decisions, cross-team coordination, deployment discussions, problem resolutions, or any other notable work items.
- **Thread boundaries:** The pasted content contains multiple Slack threads concatenated together. Delineate thread boundaries by looking for recurring phrases like "Reply…Also send to" which appear at the end of each copied thread. Use the channel names in these markers (e.g., "Also send to platform-infra-team", "Also send to retail-eng") to identify the domain/team context for each thread.

## Step 2: Gather GitLab Merge Request Data

Use the helper script at `~/.claude/scripts/gitlab-api.sh`. This script reads the GitLab token securely from `~/.claude/.mcp.json` so the token never appears in prompts.

```bash
# Get current user
~/.claude/scripts/gitlab-api.sh current-user

# Get merged MRs (pass username and start date)
~/.claude/scripts/gitlab-api.sh merged-mrs <username> <start_date>

# Get open MRs (pass username)
~/.claude/scripts/gitlab-api.sh open-mrs <username>
```

For each MR, note the title, target project/repo name, and status.

IMPORTANT: Never use curl with API tokens directly. Always use the helper script.

## Step 3: Gather Linear Ticket Data

Load the Linear tools via `ToolSearch` (query: `+linear list issues`) if not already available. Use the `mcp__claude_ai_Linear__*` remote tools (NOT a local `mcp__linear__*` server).

### 3a. Completed Tickets
Use `mcp__claude_ai_Linear__list_issues` to find issues assigned to Dylan that were completed in the past week:
- Status: "Done" or "Completed"
- Updated within the date range
- Assigned to Dylan

The `list_issues` response already includes the `description` field — no need to call `get_issue` per ticket. For each completed ticket, note the identifier (e.g., TEAM-123), title, and description. Use the description to write more precise and informative snippet bullets.

### 3b. In-Progress Tickets
Use `mcp__claude_ai_Linear__list_issues` to find issues assigned to Dylan that are currently in progress:
- Status: "In Progress" or "In Review"
- Assigned to Dylan

**NOTE:** `state` is matched exactly, and Dylan's active tickets almost always sit in **"In Review"** (statusType `started`), not "In Progress" — the latter frequently returns empty. Always query **both** `state: "In Progress"` and `state: "In Review"` as separate `list_issues` calls (run them in parallel) so no active work is missed.

For each in-progress ticket, note the identifier, title, description, and current status.

## Step 3.5: Fetch Quarterly OKRs from Notion

Load the Notion tools via `ToolSearch` (query: `+notion search`) if not already available. Search Notion for Dylan's OKRs for the current quarter:

1. Use `mcp__claude_ai_Notion__notion-search` to search for pages matching "OKR" or "Objectives" for the current quarter (e.g., "Q1 2026 OKRs", "2026 Q1").
2. Read the matching page(s) using `mcp__claude_ai_Notion__notion-fetch` to extract the individual key results assigned to Dylan.
3. Cache the OKRs in memory for use in Steps 4 and 5.

**Quarter calculation:** Q1 = Jan–Mar, Q2 = Apr–Jun, Q3 = Jul–Sep, Q4 = Oct–Dec. Derive from the current date.

**If no OKRs are found:** Note it briefly and continue — OKR mapping is optional enrichment, not a blocker.

## Step 4: Persist Detailed Weekly Report

Before summarizing into the concise snippet, write a detailed weekly report to `~/.claude/skills/reflect-self/context/`. This report is **not** for Slack — it's a rich record for later performance review analysis.

### File naming

Write the report to `~/.claude/skills/reflect-self/context/{START_DATE}_to_{END_DATE}.md` (e.g., `2026-02-13_to_2026-02-20.md`).

### Report contents

The report should be comprehensive and preserve detail that gets lost in the snippet. Include **all** of the following sections:

```markdown
# Weekly Report: {START_DATE} to {END_DATE}

## Merged MRs
For each merged MR, include:
- Title, repo, MR number, and full web_url
- Description summary (copy the first paragraph of the MR description if available)
- Associated Linear ticket(s) if any

## Open/In-Progress MRs
For each open MR, include:
- Title, repo, MR number, web_url, draft status
- Associated Linear ticket(s) if any

## Completed Linear Tickets
For each completed ticket assigned to Dylan:
- Identifier, title, URL, priority
- Description (copy the full ticket description)

## In-Progress Linear Tickets
For each in-progress/in-review ticket assigned to Dylan:
- Identifier, title, URL, status, priority
- Description (copy the full ticket description)

## Slack Context & Collaboration
Summarize each Slack thread from the slack-context.md file:
- Channel/domain
- What was discussed
- Dylan's specific contributions and decisions
- Other people involved
- Outcomes or next steps

Focus on capturing: incident responses, architecture decisions,
cross-team collaboration, problem-solving, mentoring, and process improvements.

## Key Themes
List 3-5 high-level themes or projects that dominated the week
(e.g., "ArgoCD migration", "Build observability", "Retail infra").

## OKR Progress
For each quarterly OKR/key result fetched from Notion in Step 3.5:
- State the OKR/key result
- List specific accomplishments from this week that contribute to it
  (link to MRs, tickets, or Slack threads as evidence)
- If nothing this week maps to a given OKR, omit it

Only include OKRs where this week's work made meaningful progress.

## Evidence Highlights
Flag specific items from the week that are strong evidence for
performance review narratives. Look for:
- **Impact:** Measurable improvements (reliability, cost, speed, unblocking others)
- **Scope / complexity:** Large or technically challenging work
- **Leadership:** Driving decisions, coordinating across teams, mentoring
- **Ownership:** Incident response, on-call heroics, proactive fixes
- **Collaboration:** Cross-team work, enabling other engineers

For each highlight, write 1-2 sentences explaining *why* it matters,
not just *what* happened. Include links to the source (MR, ticket, Slack thread).
Only include genuinely noteworthy items — not every merged MR is evidence.
If nothing stands out this week, write "No standout evidence items this week."
```

### Guidelines
- **Be thorough, not concise.** This is the opposite of the snippet — preserve context and nuance.
- **Attribute collaboration.** Note who Dylan worked with and what his specific role was (led, contributed, reviewed, debugged, coordinated).
- **Capture impact signals.** Note things like: unblocking others, incident response speed, cross-team work, infrastructure improvements, cost savings, reliability gains.
- **Include raw data.** It's fine to include MR descriptions, ticket details, and Slack quotes. A future agent will distill this.
- **Map to OKRs where natural.** Don't force connections — only link work to an OKR when there's a clear, direct relationship.
- **Be selective with evidence.** The Evidence Highlights section is for standout items only. Routine work should stay in the main sections above.
- **Never skip this step.** Even if the snippet is simple, always write the report.

## Step 4.5: Persist Per-Peer Collaboration Profiles

After writing Dylan's self-report, generate a collaboration profile for each peer Dylan interacted with this week. These profiles feed the `reflect-peer` skill at review time.

### Identifying peers

Scan the data gathered in Steps 1–3 for people Dylan collaborated with:
- **Slack threads:** Other participants in threads from `slack-context.md` (by name)
- **MR reviews:** People who reviewed Dylan's MRs, or whose MRs Dylan reviewed
- **Linear tickets:** Co-assignees or commenters on shared tickets

Collect a deduplicated list of peer names (first name, lowercase, e.g. `mark`, `travis`, `madeline`). Exclude Dylan himself and bots/service accounts.

### File naming

For each peer, write a profile to `~/.claude/skills/reflect-peer/context/{peer_name}/{START_DATE}_to_{END_DATE}.md`. Create the `{peer_name}/` subdirectory if it doesn't exist.

### Profile contents

Each peer profile should capture Dylan's interactions with that specific person this week:

```markdown
# {Peer Name}: {START_DATE} to {END_DATE}

## Peer's Contributions (from Dylan's perspective)
What this peer worked on this week, as visible from Slack discussions,
MR activity, and Linear tickets. Capture:
- Projects/features they drove or contributed to
- Problems they identified or solved
- Technical decisions they made or influenced
- Impact of their work (unblocked others, shipped features, fixed outages, etc.)

This is Dylan's perspective — only include what Dylan observed firsthand
through shared channels, reviews, or direct collaboration.

## Shared Slack Threads
For each thread where both Dylan and this peer participated:
- Channel/domain
- Topic summary
- What each person contributed
- How they collaborated (e.g., Dylan debugged while peer deployed, peer raised issue and Dylan fixed it)

## MR Interactions
- MRs where this peer reviewed Dylan's code (or vice versa)
- Include MR title, repo, number, web_url
- Note the nature of the review (approval, feedback, back-and-forth)

## Shared Linear Tickets
- Tickets both are involved in
- Include identifier, title, URL
- Note how work was divided or coordinated

## Collaboration Summary
2-3 sentences summarizing the working relationship this week:
what they worked on together, how they complemented each other,
and any notable dynamics (mentoring, joint debugging, coordination).
```

### Guidelines
- **Only include peers with meaningful interaction.** A drive-by emoji reaction doesn't count. Look for substantive collaboration: discussion, review, joint problem-solving, coordination.
- **Be specific about Dylan's role.** The point is to capture what Dylan contributed to the relationship, not just that they were in the same thread.
- **Skip if no peers found.** If the week's data has no clear peer interactions, skip this step entirely.
- **Keep it factual.** These profiles are raw evidence — save editorializing for the `reflect-peer` skill at review time.

## Step 5: Synthesize the Snippet

Compile all gathered data into the following bullet-point format. Be concise — each bullet should be ONE short sentence. Omit empty sections.

**Grouping by domain:** When Slack context is available, group bullets under domain/team subheadings derived from the Slack channel names (e.g., "Build/CI", "Retail", "Platform Infra", "Observability"). Items that don't clearly belong to a domain can go under a general heading. Within each domain group, list progress items first, then next items.

**Bullet limit:** Each domain group within a section (Progress, Next) must have **no more than 4 bullet points**. If there are more than 4 items for a domain, consolidate related items into single bullets and/or select the 4 most impactful items.

### Output Format

**Do NOT write an HTML file.** Instead, print the final snippet directly in the chat as markdown. The markdown hyperlinks are copyable from the chat UI and paste into Slack with formatting intact.

**IMPORTANT: Use Unicode bullet characters (`•`) instead of markdown dash bullets (`-`).** Markdown bullets are randomly stripped when copy-pasting from the chat UI into Slack. Literal `•` characters survive the paste reliably. Do NOT use a `---` horizontal rule between Progress and Next sections — it is not preserved when pasting into Slack. Instead, use the same Hangul filler (`ㅤ`) separator used between domain groups.

**Domain headings:** Use blockquoted (`>`) domain headings with _italic_ text (not bold) to visually separate groups. Adjacent blockquotes merge when pasted into Slack, so **insert a line containing only the Hangul filler character `ㅤ` (U+3164)** between the last bullet of one domain group and the next blockquoted heading. A normal blank line is not enough — Slack collapses it. The Hangul filler is invisible but acts as a non-empty line that breaks blockquote merging.

Example structure (as markdown in chat):

```
**Progress:**

> _ArgoCD Migration_
• [description] ([repo !number](MR_WEB_URL))
• TICKET-ID: [ticket title]

ㅤ

> _Build/CI_
• ...

ㅤ

**Next:**

> _ArgoCD Migration_
• [description] ([repo !number](MR_WEB_URL)) - [status]
• TICKET-ID: [ticket title] - [status]

**Blockers:**
• [Only include if actual blockers identified]
```

**Linear ticket links:** make each ticket ID a markdown hyperlink to its Linear URL.

**MR links:** Use shorthand format `repo !number` as the display text (e.g. `tlaloc-env !1975`), hyperlinked via markdown to the full `web_url` from the GitLab API response.

## Important Rules

1. **Be concise.** Each bullet is ONE short sentence. No paragraphs.
2. **Deduplicate.** If an MR and a ticket refer to the same work, combine into a single bullet.
3. **Prioritize.** List the most impactful items first within each section.
4. **Be precise and verifiable.** Every claim must be directly traceable to an MR, ticket, or Slack message. Do not paraphrase loosely, guess at details (e.g. service names from truncated descriptions), or editorialize. If an MR description was truncated and you cannot confirm specifics, state only what you know. Prefer linking to the source over describing it. An engineer should be able to scrutinize every bullet and verify it.
5. **Skip empty sections.** If there are no blockers, omit the Blockers section entirely.
6. **Handle errors gracefully.** If a service is unreachable, note it briefly (e.g., "(Linear data unavailable)") and continue with available data.
7. **NEVER modify external state.** Never update MRs or modify tickets.
8. **Output as markdown in chat only.** Do NOT write an HTML file. Print the snippet directly in chat using markdown formatting — bold for headers, italics for domain groups, bullet points for items, and markdown links for MR/ticket references. The user copies directly from chat into Slack.
9. **NEVER use API tokens directly.** If using Bash fallback, always use `~/.claude/scripts/gitlab-api.sh` which reads tokens securely from config.
10. **Always persist the detailed report.** The performance-context report (Step 4) must be written before the snippet is displayed. If writing the file fails, warn the user but still produce the snippet.

## Step 6: Self-Improvement

After the snippet is written and presented to the user, reflect on how the execution went. Consider:

- Did any tool calls fail or require retries? (e.g., wrong parameters, missing `Read` before `Write`, tool not loaded)
- Did any MCP tools need to be loaded via `ToolSearch` in a way that could be streamlined?
- Were there data gaps or API quirks that should be documented? (e.g., parameter format issues, missing fields)
- Was the output format correct on the first try, or did it need adjustment?
- Did the `list_merge_requests` tool require `project_id` when a broader query would have been better?

If any issues were encountered, **edit this skill file** (`~/.claude/skills/reflect-week/SKILL.md`) to add instructions, warnings, or tips that would prevent the same issue next time. Keep edits surgical — add a note near the relevant step rather than rewriting sections. Briefly tell the user what was updated and why.
