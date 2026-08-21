# Plan Subtasks — Turn Design + Implementation Docs into a Linear Ticket Tree

Read a design doc and an implementation-breakdown doc, cut the work into slices that each map to **one reasonably sized, reviewable MR**, and create a Linear parent ticket with one subtask per slice.

The deliverable is a ticket tree someone can pick up cold. Each subtask must be implementable **to spec by a coding agent** and **understandable by a human** who has not read either doc — thorough without being a jargon-y wall of text.

This skill writes to Linear, but only once, at the very end, after you show the full plan and the user approves it.

**Parameters:** `$ARGUMENTS`

```
/plan-subtasks <design-doc-url> <implementation-doc-url>
/plan-subtasks <design-url> <impl-url> --project "K8s Self-Service" --team PLAT
/plan-subtasks <design-url> <impl-url> --assignee me --label platform --shallow
/plan-subtasks <design-url> <impl-url> --parent PLAT-1557
```

| Part | Meaning |
|---|---|
| First two positional tokens | The **design doc** then the **implementation doc**. Notion URL, Linear document, local file path, or any URL. Order matters unless you use the explicit flags. |
| `--design <ref>` / `--impl <ref>` | Name the docs explicitly instead of relying on position. |
| `--team <key or name>` | Linear team for every ticket. Asked for if omitted and not inferable. |
| `--project "<name>"` | Linear project to file under. **Always confirmed with the user** (Step 2c) even when passed. |
| `--parent <ID>` | Use an existing ticket as the parent instead of creating one. Its description gets the subtask index appended, not overwritten. |
| `--assignee <name\|me\|none>` | Default `me` — every ticket starts assigned to the user running the skill. |
| `--label <name>` | Label applied to every created ticket, repeatable. |
| `--shallow` | Skip the codebase probe (Step 3). Slice from the docs alone — faster, and much likelier to produce tickets that don't match the repo. |
| `--no-fanout` | Do the codebase probe inline instead of dispatching subagents. Use for small initiatives (≤ 4 expected MRs). |
| `--dry-run` | Stop after Step 7. Print the plan, write nothing to Linear. |

If no docs are given, ask for them and stop. If exactly one is given, ask whether it is the design doc, the implementation doc, or both in one page — do not guess.

---

## Step 1: Load the Docs

Load `ToolSearch` tools as needed: `select:mcp__claude_ai_Notion__notion-fetch`, `select:mcp__claude_ai_Linear__get_document`, `select:WebFetch`.

1. **Notion URLs** (`notion.so/…`, `notion.com/…`, `*.notion.site/…`) → `mcp__claude_ai_Notion__notion-fetch` with the URL as `id`. If the fetch fails, retry once, then try `notion-search` on the page title. If the Notion MCP server is unauthorized, say so plainly and stop — this skill has nothing to plan from without the docs.
2. **Local paths** → `Read`. **Linear docs** → `get_document`. **Anything else** → `WebFetch`.
3. **Follow one level of sub-pages.** Both doc types routinely push detail into child pages ("Phase 2 detail", "API shapes", "Migration plan"). Fetch child pages that are clearly part of this spec. Do not crawl the workspace.
4. **Read the comments** on the docs if the tool exposes them (`notion-get-comments`). Late decisions live in comments and contradict the body more often than not.

Then state a **checkpoint** to the user before continuing:

> Loaded **Design:** _<title>_ (<url>) — <one line on what it specifies>
> Loaded **Implementation:** _<title>_ (<url>) — <one line>
> Ticket count I expect to produce: ~N

**Where the two docs disagree, the design doc defines *what* and *why*; the implementation doc defines *how*.** If they conflict on substance (a table the design says is dropped and the breakdown says is migrated), surface the conflict to the user now — do not pick one silently and bury the choice in a ticket.

**Record every distinct doc URL.** Every ticket created in Step 8 carries both links, so keep the canonical URLs verbatim.

---

## Step 2: Establish the Linear Destination

Nothing is created until team, project, and assignee are settled. Load `select:mcp__claude_ai_Linear__list_teams,mcp__claude_ai_Linear__list_projects,mcp__claude_ai_Linear__list_issues,mcp__claude_ai_Linear__get_issue,mcp__claude_ai_Linear__save_issue`.

### 2a. Identify the user

```bash
git config user.name
```

The assignee defaults to `me` — Linear's `save_issue` accepts the literal string `"me"` for `assignee`, so there is no need to look up a user ID.

### 2b. Resolve the team

From `--team`, else from a ticket identifier mentioned in the docs (`PLAT-1557` ⇒ team `PLAT`), else from `list_teams` — if there is exactly one team, use it; otherwise ask.

### 2c. Confirm the project — always ask

Call `list_projects` with `team:` and, if the docs name a plausible project, `query:`. Then ask with `AskUserQuestion`, offering:

- the best-matching existing project (recommended, if the match is strong),
- one or two other plausible existing projects,
- **create a new project** named after the initiative,
- **no project**.

Never file into a project the user didn't name. This confirmation is the whole reason the step exists — the tickets are hard to re-home once created, and a wrong project quietly hides an initiative from the people tracking it.

If the user picks "create a new project", create it only in Step 8 with the rest of the writes, never now.

### 2d. Check for prior runs

`list_issues` with the chosen `project` (and `query:` the initiative name). If a parent ticket for this initiative already exists, say so and ask whether to **add to it** (treat as `--parent`), **replace the subtask set**, or **stop**. Do not create a second parallel tree — duplicated ticket trees are the most common damage this skill can do.

State the resolved destination back before continuing:

> Filing into team **PLAT**, project **Namespace Self-Service**, assigned to **dylan**, labels: `platform`. No existing parent found.

---

## Step 3: Probe the Codebase

Docs describe intent. The repo decides what a single MR can actually contain. Skip only under `--shallow`, and when you skip, say in the final output that the slicing is doc-only and unverified.

Work out which repo the docs describe. If the current working directory is not it, ask the user for the path rather than slicing against the wrong tree.

**Fan out.** Dispatch `Explore` subagents in parallel — one per major area the implementation doc names (service, package, schema, frontend surface). Send the `Agent` calls in a single message so they run concurrently. Under `--no-fanout`, do this inline.

Brief each subagent:

> Read this excerpt of an implementation plan: `<area section>`. Do not write anything. Find in this repo:
> - `entry_points`: the files, modules, and functions this work must modify, most-central first, with real paths
> - `patterns`: how this codebase already does this kind of thing (the file to copy from), with a path and a one-line description
> - `contracts`: schemas, interfaces, API types, or generated code this work must fit or regenerate
> - `tests`: where tests for this area live and how they are run
> - `size_signal`: rough scale of the change — files touched and whether it drags a migration, a codegen step, or a config rollout with it
> - `landmines`: anything that will surprise the implementer (generated files, a lockstep deploy, a shared fixture, a flag system)

Collect the results into one table keyed by area. Where the docs name a file or symbol that does not exist, **say so explicitly in the plan** — a stale doc reference copied into a ticket sends the implementer hunting for something that was renamed six months ago.

---

## Step 4: Cut the Work into MR-Sized Slices

This is the judgement the skill exists for. One slice = one merge request.

### What "one reviewable MR" means

A slice qualifies when **all** of these hold:

1. **One concern.** It can be described in a single sentence with no "and".
2. **Reviewable in one sitting** — as a rule of thumb under ~400 lines of hand-written diff, excluding generated files, fixtures, and lockfiles. A slice that is mostly codegen can be much larger; say so in the ticket.
3. **Independently mergeable.** It can land on the default branch on its own without breaking it — behind a feature flag, additive-only, or genuinely inert until a later slice wires it up.
4. **Independently verifiable.** It carries its own tests, or a stated manual verification, that pass at the moment it merges.
5. **At most one schema migration**, and a migration slice is additive-only and separate from the read/write switch that uses it.
6. **No half-done renames or partial refactors** left behind for a later slice to finish.

### How to cut

- Start from the implementation doc's own breakdown — it usually has one — then **re-cut it**. Docs habitually write "Phase 2: build the controller" where the repo says that's four MRs.
- Prefer **vertical slices that ship something observable** over horizontal layers ("all the types", then "all the handlers"), unless the layers genuinely land independently.
- **Split** anything that: touches more than one deployable in a way requiring lockstep, mixes a migration with logic that reads it, mixes a refactor with a behavior change, or has more than one acceptance criterion pointing at unrelated behavior.
- **Merge** anything that: cannot be tested without its neighbor, is a two-line change plus its caller, or would leave the tree in a state nobody could review in isolation.
- Put **scaffolding first** (flags, config schema, interfaces) and **cleanup last** (flag removal, dead-code deletion, doc updates). Both are real tickets; do not smuggle them into the last feature slice.
- Aim for **4–12 slices**. Fewer than 4 for a real initiative usually means slices are too fat; more than ~15 means you are ticketing individual commits — check with the user before going that fine.

### Order and dependencies

For each slice record `blocked_by` (slices whose merge it truly needs) and `blocks`. Distinguish a **hard** dependency (won't compile/test without it) from a **soft** one (same files, merge conflict). Only hard dependencies go into Linear's `blockedBy` relations; soft ones become a "Notes" line in the description.

Number the slices `MR 1 … MR N` in merge order. That number goes in the title.

---

## Step 5: Write the Subtask Descriptions

Every description serves two readers at once: a coding agent that must implement to spec without asking questions, and a human who must be able to read the ticket in two minutes and know what to build. Optimize for both — the failure modes are a vague ticket the agent guesses its way through, and an exhaustive one no human will read.

### Template

```markdown
**Part of:** <PARENT-ID> — <initiative title> · MR <n> of <N>
**Design doc:** <design url>
**Implementation breakdown:** <impl url>

## What and why

Two to four sentences of plain language. What changes, and why anyone wants it.
No jargon that isn't defined in this ticket or obvious from the repo.

## Scope

**In:** the concrete things this MR does.
**Out:** the neighbouring things it deliberately does not do, each with the ticket
that covers it (`MR 5` / `PLAT-1601`).

## Where the code goes

| Path | Change |
|---|---|
| `services/foo/handler.go` | new endpoint `POST /namespaces/:id/grants` |
| `db/migrations/` | additive column `grants.expires_at` |

## How to build it

1. Numbered, imperative steps in the order to do them.
2. Real names: files, functions, flags, env vars, table and column names.
3. Point at the existing pattern to follow: "mirror `services/bar/handler.go`".
4. Enough that an implementer never has to invent an interface — but no code dumps
   unless an exact shape is being fixed across tickets.

## Contracts

Any interface, schema, payload, or flag name that another ticket depends on, given
exactly. Omit this section when nothing crosses a ticket boundary.

## Testing

What proves it works: the test files to add, the cases that matter, how to run them,
and any manual verification the automated tests can't cover.

## Acceptance criteria

- [ ] Each item independently checkable by someone reading the MR.
- [ ] Behavioral, not procedural — "grant expires after TTL", not "wrote a test".
- [ ] The flag/rollout state at merge time is one of these items.

## Dependencies

Blocked by: MR 2 (`PLAT-1599`) — needs the `Grant` type.
Blocks: MR 6.
Safe to start now: yes / no, and what to stub if starting early.

## Notes

Gotchas from the codebase probe: generated files to regenerate, shared fixtures,
deploy ordering, anything the docs got wrong.
```

### Voice rules

- **Address the implementer directly**, imperative mood. "Add", not "we should add".
- **Every term a newcomer wouldn't know gets defined once, in-line**, in six words or fewer.
- **Name real paths and symbols** from the Step 3 probe. A ticket that says "the relevant service" has failed.
- **Do not restate the design doc.** Summarize its decision in a sentence and link out. The links are in the header for exactly this reason.
- **Target 250–600 words per ticket.** Past ~900 words, either the slice is too big or the description is doing the design doc's job.
- **Do not invent specifics the docs don't contain.** Where the docs are silent on something the implementer needs, write it as an open question in `## Notes` and raise it with the user in Step 7 — a plausible invention presented as spec is the worst thing this skill can produce.
- Omit any section that would be empty. An empty heading is noise.

### The parent description

```markdown
**Design doc:** <url>
**Implementation breakdown:** <url>

## Goal
Three to five sentences: the outcome, who it's for, what changes for them.

## Approach
A short paragraph on the shape of the solution and the sequencing rationale.

## Merge sequence
| # | Ticket | Title | Depends on |
(filled in with real identifiers in Step 9)

## Rollout
Flags, migrations, deploy ordering, and how this gets turned on.

## Done when
The initiative-level acceptance criteria — not the union of the subtasks'.

## Open questions
Anything the docs left unresolved, with who needs to answer it.
```

---

## Step 6: Titles

`MR <n>: <verb phrase>` — e.g. `MR 3: Add namespace grant expiry to the reconciler`.

Parent title: the initiative name from the design doc, no `MR` prefix. Keep titles under ~70 characters, specific enough to be unambiguous in a project list, and never numbered in a way that breaks if a slice is added later — if the user inserts a slice during review, renumber the whole set before writing.

---

## Step 7: Show the Plan and Get Approval

**Nothing has been written to Linear yet, and nothing is written until the user says yes.**

Present, in this order:

1. **Destination line** — team, project, assignee, labels, parent (new or existing).
2. **The slice table** — `#`, title, one-line summary, size (S/M/L), blocked-by, files it touches.
3. **The dependency chain** in one line: `MR1 → MR2 → {MR3, MR4} → MR5`.
4. **Two full sample descriptions** — the parent, and the subtask you consider hardest to describe. Not all of them; a wall of N descriptions is unreviewable, and the user is approving the *slicing*, plus a sample of the writing quality.
5. **Open questions** — every gap you found in the docs, and how you plan to word the ticket around it.
6. **Anything the docs claimed that the codebase contradicts.**

Then ask a single question: create these N tickets as described, adjust the slicing first, or stop. Under `--dry-run`, stop here regardless and offer to write the plan to a file.

Take revisions and re-present the table (not the whole plan) until the user approves.

---

## Step 8: Create the Tickets

Only after explicit approval. Create in this order so every child has a real parent to point at:

1. **The project**, if the user chose to create one (`save_project`, loaded via `ToolSearch`).
2. **The parent ticket** — `save_issue` with `team`, `title`, `description`, `project`, `assignee`, `labels`, and `links: [{url: <design>, title: "Design doc"}, {url: <impl>, title: "Implementation breakdown"}]`. Record the returned identifier.
3. **Each subtask, in merge order** — `save_issue` with `team`, `title`, `description`, `parentId: <parent identifier>`, `project`, `assignee`, `labels`, and the same two `links`. Creating them in order keeps them in order in the Linear UI.
4. **The dependency relations** — a second pass of `save_issue` with `blockedBy: [<identifiers>]`, once every subtask has an identifier. Hard dependencies only.
5. **Backfill the parent** — update its `## Merge sequence` table with the real identifiers, using `patch` with a `replace` op rather than rewriting the whole description.

Tool notes that will otherwise cost a retry:

- The assignee field is **`assignee`**, not `assigneeId`, and it accepts `"me"`.
- **`labels` replaces the entire label set.** Pass the full intended list every time.
- **Descriptions take literal newlines**, not `\n` escape sequences.
- `parentId` accepts the human identifier (`PLAT-1598`).
- `blockedBy` is append-only — safe to call twice, so a partial failure can be re-run.

**If a create fails partway through,** stop and report exactly which tickets exist and which don't. Do not retry the whole batch blindly — that is how duplicate trees appear.

---

## Step 9: Verify and Report

Re-fetch the parent with `get_issue` (`includeRelations: true`) and `list_issues` with `parentId:` set to it. Confirm, before reporting success:

- every subtask exists, is parented, and is in the intended project,
- assignee and labels are set on all of them,
- both doc links are attached to every ticket,
- the relations match the Step 4 dependency table.

Then print a final table: `#` · identifier · title · URL · blocked-by. Follow it with:

> Next: `/plan-initiative <PARENT-ID> with <names>` to distribute these across the team, or `/fix-linear <FIRST-ID>` to start MR 1.

---

## Important Rules

1. **One write phase, gated.** Steps 1–7 touch nothing. If the user never approves, nothing exists in Linear.
2. **Confirm the project, every run.** Even when `--project` was passed. Wrong-project tickets are invisible to the people tracking the work.
3. **One MR per ticket, no exceptions.** If a slice can't be described without "and", split it.
4. **Never invent spec.** Doc silence becomes an open question in the ticket and a question to the user — never a confident-sounding fabrication.
5. **Both doc links on every ticket**, in the description header *and* as link attachments. A subtask read in isolation must be able to reach its context.
6. **Ground every ticket in real paths** unless `--shallow`, and say when you didn't.
7. **This skill writes no code and creates no branches.** It produces tickets. Implementation is `/fix-linear`'s job.
8. **If a ticket description would tell the implementer to write a comment in the code, delete that instruction.** Explanation belongs in the MR description, and the repo-wide rule forbids agent-written code comments.

---

## Step 10: Self-Improvement

After the tickets exist, reflect:

- Did the user re-cut the slices? In which direction — too fat, too fine, wrong seams? That's a durable calibration signal; record it.
- Did the docs contradict the codebase, and did the probe catch it before the tickets went out?
- Did any Linear call fail on a field name, ordering, or permission? Add the specific fix here.
- Did the descriptions land, or did the user rewrite the voice? Capture what they changed.

If a different instruction would have avoided a round trip, **edit this skill file** (`~/.claude/skills/plan-subtasks/SKILL.md`) surgically — a note at the relevant step, not a rewrite. Tell the user what changed and why.
