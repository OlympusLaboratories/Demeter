# Plan Initiative — Sequence and Delegate a Linear Initiative

Take an initiative represented by a parent Linear ticket and its subtasks, work out what can *actually* run in parallel, assign each subtask to a named engineer, and produce a meeting-ready distribution plan with a swimlane chart.

The output of this skill is a plan a human reads out in a meeting. It is not code, and it does not implement anything.

**Parameters:** `$ARGUMENTS`

```
/plan-initiative PLAT-2116 with victor aimon
/plan-initiative https://linear.app/gridmatic/issue/PLAT-2116 with victor aimon --deadline 2026-09-15
/plan-initiative PLAT-2116 with victor aimon --capacity "victor 50%" --shallow
```

| Part | Meaning |
|---|---|
| First token | Linear identifier (`PLAT-2116`) or issue URL of the **initiative parent**. Required. |
| `with <names…>` | The subset of the team helping on this initiative. Names are matched against `team.md` (see Step 0). The user running the skill is **always** included whether or not they're named. |
| `--deadline <date>` | Target date. Changes the verdict: with a deadline, say whether it lands and what must be cut. |
| `--capacity "<name> <pct>"` | Per-person availability override, repeatable. Default is full capacity from `team.md`. |
| `--shallow` | Skip the codebase probe (Step 2). Sequence from Linear content only — faster, much less reliable. |
| `--no-fanout` | Do the codebase probe inline instead of dispatching subagents. Use for small initiatives (≤4 subtasks). |

If no ticket identifier is given, ask for one and stop. If no helper names are given, ask whether this is a solo sequencing exercise or the user forgot the roster — do not silently plan for one person.

---

## Step 0: Load the Roster

### 0a. Identify the user

```bash
git config user.name
```

Take the first name, lowercased, as `ME`. This person is always a lane in the plan.

### 0b. Read `team.md`

Read `~/.claude/skills/plan-initiative/team.md`.

**If it does not exist:** copy `team.example.md` next to it, tell the user it was created, and ask them to fill it in — then continue this run using whatever they tell you inline. Do not block the whole run on it.

`team.md` holds one section per teammate: seniority, specialties, areas they ramp slowly on, default capacity, and any standing notes about what to hand them. It is the difference between "assign by ticket count" and "assign by who this work actually suits."

### 0c. Resolve the helping subset

Match each name after `with` against a `team.md` section (case-insensitive, first name is enough). The roster for this run is `ME` + the matched helpers, and **only** those people. Ignore everyone else in `team.md` — the file is the whole team, the argument is who's on this initiative.

For any named helper with no `team.md` section, ask the user for a one-line profile (seniority, specialty, ramp areas), use it for this run, and at the end of the run offer to append it to `team.md`.

State the resolved roster back to the user before continuing:

> Planning `PLAT-2116` across 3 lanes: **dylan** (owner, staff), **victor** (new hire, ramping on our auth model), **aimon** (security engineer, 50% capacity).

### 0d. Skill-level ground rule

Everyone on the roster is assumed to be equally capable of *executing* with Claude Code. Seniority and specialty matter for exactly one thing: **how long it takes someone to build the conceptual model the task requires.** Use skill level only to estimate ramp cost, never to decide who is "good enough" for a task.

---

## Step 1: Load the Initiative from Linear

Load Linear tools via `ToolSearch` as needed (`select:mcp__claude_ai_Linear__get_issue`, `select:mcp__claude_ai_Linear__list_issues`, `select:mcp__claude_ai_Linear__list_comments`).

1. **Parent** — `get_issue` with `id:` the identifier and `includeRelations: true`. Capture title, description, status, project, labels, estimate, and relations.
2. **Subtasks** — `list_issues` with `parentId:` the parent's id. For **every** subtask, fetch the full issue with `get_issue` (`includeRelations: true`) plus its comments. Do not plan from the subtask list view; titles alone hide dependencies.
3. **Sub-subtasks** — if any subtask has its own children, load those too. Plan at the deepest level that has real work in it, and say which level you chose.
4. **Relations** — record every `blocks` / `blocked by` / `related` edge Linear already knows about, per subtask.
5. **Existing state** — record current status and current assignee of each subtask. Work already in flight constrains the plan; done work is removed from it.
6. **Linked specs** — scan the parent and subtask descriptions/comments for Notion or other doc links, and fetch them (`select:mcp__claude_ai_Notion__notion-fetch`). Sequencing decisions usually live in the spec, not the tickets. If a link can't be fetched, say so explicitly rather than planning around a gap you didn't mention.

**Checkpoint — state to the user before Step 2:** the parent's goal in one sentence, the number of subtasks by status (todo / in progress / done), and any subtask that is already assigned or in flight.

Assign each subtask a **short handle** for use in the chart — the numeric suffix of its identifier, prefixed by a stream letter if the initiative has obvious streams (`S2-4`, `S1-2`). Keep handles ≤ 6 characters. Maintain the handle → identifier → title mapping; it becomes the chart legend.

---

## Step 2: Probe the Codebase for Real Coupling

Ticket text tells you what someone *intended*. The code tells you what will actually collide. Skip this step only under `--shallow`.

**Fan out.** Dispatch one `Explore` subagent per subtask (or per tight cluster of subtasks when there are more than ~12), in parallel batches — send multiple `Agent` calls in a single message so they run concurrently. Under `--no-fanout`, do the same investigation inline instead.

Give each subagent this brief:

> Read Linear subtask `<ID>: <title>` (description below). Find, in this repo, the code it will have to touch. Do not write anything. Return exactly:
> - `touches`: the files/modules/dirs this work must modify, most-central first
> - `reads`: interfaces, schemas, or contracts it depends on but does not own
> - `hard_deps`: other subtasks in this list whose output this one cannot compile/run/test without, each with one line of evidence from the code
> - `decouplers`: how this could proceed *before* those deps land — interface stub, feature flag, contract-first agreement, fixture, migration split. Say which one and what it costs.
> - `difficulty`: 1–5 on conceptual load (not line count), plus one line on what makes it that number
> - `ramp_cost`: how long someone unfamiliar with this area would spend building the model before they could start, in days
> - `size`: S / M / L (≈0.5d / 1–2d / 3–5d) of implementation once ramped
> - `test_surface`: what proves it works, and whether that requires anything from another subtask
> - `flaggable`: can this land dark behind a flag? yes/no + why

Collect all results into one table. Where a subagent's `hard_deps` disagree with Linear's stated relations, trust the code and flag the discrepancy — a stale `blocked by` in Linear is the single most common source of fake serialization.

Build a **collision matrix**: for every pair of subtasks, the files both would edit. Two tasks with overlapping `touches` are parallelizable only with a merge cost; note it.

---

## Step 3: Build the Dependency Graph

Classify every edge. This classification is the whole value of the skill — get it right and the rest is arithmetic.

| Class | Definition | Effect on the plan |
|---|---|---|
| **Hard** | B literally cannot be written, compiled, or tested until A lands. | Serializes. Goes on the critical path. |
| **Soft** | B is *easier* after A, or they touch the same files and would conflict. | Order within one lane, or accept a merge cost. Never serializes across lanes on its own. |
| **False** | Stated as a dependency (in the ticket or in someone's head) but breakable by a stub, contract, flag, or fixture. | **Break it.** Name the decoupler and its cost. |

Hunt false dependencies aggressively — they are where the speedup comes from. Typical breakers:
- **Contract-first**: agree the interface/schema in the meeting, both sides build against it, integrate later.
- **Interface stub / fake**: consumer builds against a hand-written stub while the producer builds the real thing.
- **Feature flag**: dependent work lands dark and is switched on when its dependency arrives.
- **Migration split**: additive schema change lands early and alone; the read/write switch comes later.
- **Fixture / recorded payload**: downstream work tests against a captured payload instead of a live producer.

Then compute:
- **Waves** — topological levels over hard edges only. Wave 0 = everything startable on day one.
- **Critical path** — the longest chain of hard edges by duration (`ramp_cost` + `size`, per the person you'd assign it to).
- **Total work** — sum of all durations.

Present the graph as a table before the chart: handle, title, hard deps, soft deps, false deps broken (+ how), size, difficulty, wave.

---

## Step 4: The Parallelism Verdict

Answer, in plain language and before any assignment detail, whether this initiative can absorb the people being thrown at it — or whether it's a "if one woman can make a baby in nine months, nine women can do it in one" situation. Be blunt. A plan that pretends work is splittable when it isn't will fail in week two, and the whole point of asking is to find out now.

State:

1. **Serial floor** — the critical path duration. No amount of people beats this. Name the chain: `S2-4 → S2-6 → S2-8 → S2-11, 9 days`.
2. **Total work vs. floor** — total person-days ÷ critical path = the maximum useful headcount. If that number is below the roster size, **say that someone will be idle or should work on something else**, and say who.
3. **Realistic speedup** — solo duration vs. planned duration with this roster, after subtracting ramp cost, review time, and integration friction. Give a number and the assumptions behind it.
4. **What cannot be split, and why** — the chains where handing work to a second person makes it slower. Include the teaching-cost cases: work where explaining the model costs more than doing it (`ramp_cost` > `size` on a critical-path task ⇒ the person who already has the model keeps it).
5. **What the parallelism costs** — the flags, stubs, and contracts that have to exist for these lanes to run at once, and who pays for them. Parallelism is never free; name the price.

If the honest answer is "two people is the useful maximum here", say so and recommend what the third person does instead (adjacent work, review capacity, the next initiative). Do not manufacture lanes to fill the roster.

---

## Step 5: Assign the Work

Assign every not-done subtask to exactly one lane. Rules, in priority order:

1. **Critical path goes to whoever traverses it fastest.** Usually the person who already holds the model — often the initiative owner. Protecting the critical path is worth more than balancing the load.
2. **Specialty match.** Security-shaped work to the security engineer, and so on. A specialist's `ramp_cost` on their own domain is ~0.
3. **Teach vs. do.** If `ramp_cost` > `size` *and* the task is on the critical path, keep it with whoever has the context. If it's *off* the critical path, the same task is an excellent learning assignment — the ramp is paid out of slack, and it buys a second person who understands that area. Say explicitly which assignments are learning investments.
4. **New-hire onboarding shape.** Give a ramping engineer an early self-contained win, then work with high context locality (few files, clear tests, low blast radius). Avoid making a new hire the sole owner of a critical-path integration in their first initiative.
5. **Minimize collisions.** Use the collision matrix — do not put two people in the same files in the same wave unless one of them is explicitly the owner of that file and the other is waiting on their merge.
6. **Balance by wave, not by count.** Five tickets in one lane and two in another is fine if the durations match. Idle time inside a wave is the thing to squeeze.
7. **Respect capacity.** A 50% engineer gets half the wave-days, not half the tickets.

For each assignment, record the one-line reason. The reasons are what the user actually says out loud in the meeting.

---

## Step 6: Draw the Swimlane Chart

One horizontal lane per person, time flowing left to right, with vertical channels showing cross-lane dependencies. This is the deliverable the user reads off the screen — alignment errors make it worthless, so build it mechanically, not by eye.

### 6a. Canonical format

This is the target. Match it.

```
═══ DYLAN ════════════════════════════════════════════════════════════

   S2-4 ──┐
          ├─> S2-6 ─────────┬─> S2-8 ───────────────────┐
   S2-5 ─┬┘                 │                           │
         │                  │                           │
         └───────┐          │                           │
                 │          │                           │
═══ AIMON ═══════╪══════════╪═══════════════════════════╪═════════════
                 │          │                           │
   S1-2 ─> S1-3 ─┴> S1-4 ───┼───────────────────────────┤
                  ▲         │                           │
              flag ON       ├─> S2-10 ──────────────────┤
              + S2-5        │                           │
                            │                           ├─> S2-11
═══ VICTOR ═════════════════╪═══════════════════════════╪═════════════
                            │                           │
   S2-1 ─> S2-2 ────────────┼───────────────────────────┤
                            │                           │
                            └─> S2-7 ─> S2-9 ───────────┘
```

Read it as: time flows left to right; each `─>` is a handoff inside one lane; each vertical
channel is a handoff *between* lanes. A lane header carries `╪` only where a channel actually
crosses it — the top header has none, because nothing passes above the first lane.

Character rules:

| Glyph | Use |
|---|---|
| `═══ NAME ═══…` | Lane header, padded with `═` to the full chart width |
| `╪` | A cross-lane channel passing **through** a lane header |
| `──>` | Sequence within a lane (arrowhead at the consumer) |
| `│` | A cross-lane channel running vertically |
| `┬ ┴ ├ ┤ ┼` | Branch off / join into a line |
| `┌ ┐ └ ┘` | Corner where a horizontal run turns into a channel |
| `▲` + text below | A gate on an edge: the condition that must hold before the consumer starts (`flag ON`, `+ S2-5`, `schema merged`) |

### 6b. Build it as a grid, not as prose

Hand-typing box-drawing characters produces misaligned garbage. Instead:

1. Compute the layout: for each task, `wave` → column band (`col = LEFT_MARGIN + wave * BAND`, `BAND` ≈ 12–18 chars, wide enough for the longest handle plus its arrow); for each task, a row inside its owner's lane.
2. Allocate one **vertical channel column** per cross-lane edge, placed right of the producer's end column and left of the consumer's start column. Channels may be reused when they don't overlap vertically.
3. Write a throwaway Python script in the scratchpad that fills a 2-D character grid from the task/edge table and prints it. Run it, look at the output, adjust spacing, re-run.
4. Paste the final grid into the response inside a fenced code block.

Keep total width ≤ 100 characters so it doesn't wrap in a terminal. If it doesn't fit, split into two charts by phase rather than shrinking the labels.

Lane order: the initiative owner first, then the remaining lanes ordered so that lanes with the most edges between them are adjacent — this minimizes long channels crossing unrelated lanes.

### 6c. Verify before showing it

Check every one of these, and fix the chart rather than explaining the discrepancy:

- Every hard edge in the Step 3 table appears as a drawn path, and every drawn path is an edge in the table.
- No task label is overwritten or truncated.
- Every lane header is the same width, and `╪` appears exactly where a channel crosses it.
- Nothing in a lane starts left of its dependencies' end column.
- Every gate annotation (`▲`) sits under the edge it gates.
- Handles in the chart all appear in the legend.

Print the legend directly under the chart: handle → identifier → title → owner, in wave order.

---

## Step 7: Sync Points and Handoff Contracts

Every cross-lane channel in the chart is a moment two humans must agree on something. List them explicitly — this is where initiatives actually fail.

For each sync point:

| Field | Content |
|---|---|
| **When** | The wave/day it happens, and the trigger (`S2-6 merged`) |
| **Who** | Producer → consumer, by name |
| **Artifact** | What literally changes hands: a merged interface, a schema migration, a flag name, a fixture file, an agreed request/response shape |
| **Definition of done** | What the consumer needs to be true before they can proceed — testable, not "it's ready" |
| **If it slips** | What the consumer does meanwhile (stub, other ticket, review) |

Call out separately:

- **Contracts that must be agreed in the distribution meeting itself** — interfaces both sides build against before either has written code. These are the highest-value five minutes of the meeting; list them first with a proposed shape so the meeting ratifies rather than designs.
- **Feature flags** — name, who creates it, who flips it, what it gates, when it's removed.
- **File collisions** — pairs from the collision matrix that survive into the plan, with the agreed merge order.

---

## Step 8: Per-Person Work Order

One block per lane, written so the user can paste it straight into a DM or meeting agenda. Address the engineer directly.

```
### VICTOR — 4 tickets, ~6 days, starts day 1

Start with:  S2-1  PLAT-2131  Add rate-limit config schema
             Self-contained; touches config/ and its tests only. This one gets you
             oriented in the settings layer.

Then:        S2-2  PLAT-2132  Wire the limiter into the request path
             Needs the schema from S2-1. Nothing else blocks it.

             S2-7  PLAT-2137  Backfill job for existing tenants
             Starts once Dylan's S2-6 is merged (day 4). Until then, keep going on S2-2.

             S2-9  PLAT-2139  Metrics + dashboard for limiter hits
             Needs S2-7 in place.

You are blocked by:  Dylan (S2-6, expected day 4)
You unblock:         Nobody — your chain merges at the end.
Sync you must attend: interface agreement on the limiter config shape, day 1.
If you finish early:  Pick up S2-10 from Aimon's lane; it's independent.
Watch out for:        config/limits.py is also touched by S2-4 — Dylan merges first.
```

Include for every lane: ordered tickets with handle + identifier + title, the one-line reason they own it, what blocks them and when it clears, who they unblock, which syncs they must attend, and what to pick up if they finish early. Where an assignment is a deliberate learning investment, say so — the engineer should know it's intentional and that the ramp time is budgeted.

Finish with a short **meeting agenda**: the order to walk the lanes, the contracts to ratify, and the two or three decisions that must be made in the room.

---

## Step 9: Offer to Write Back to Linear

Default is read-only. **Nothing is written to Linear during Steps 1–8.**

After presenting the plan, offer — once, as a single question with an explicit list of what would change:

1. Assign each subtask to its planned owner (`save_issue` with `assigneeId`).
2. Post the sequencing plan (verdict + chart + sync points) as a comment on the parent (`save_comment`).
3. Add the derived `blocks` / `blocked by` relations that Linear is missing, and flag the stale ones for removal — but never delete a relation without the user naming it.

Do all, some, or none, exactly as the user answers. If they decline, stop cleanly — the markdown plan is the deliverable.

---

## Important Rules

1. **Read-only by default.** No Linear writes, no branches, no code changes, until Step 9 and only with explicit approval.
2. **Never fake parallelism.** If the work is serial, say it's serial. The user asked precisely so they wouldn't schedule a meeting around a fantasy.
3. **Every dependency needs evidence.** A hard edge cites the code or the spec line that makes it hard. "Seems related" is a soft edge at best.
4. **Ramp cost is real work.** Count it in the duration of every assignment, never as free.
5. **The chart must match the table.** If the two disagree, the chart is wrong — fix it before showing it.
6. **Name people, not roles.** The output is a distribution plan for three specific humans; write it that way.
7. **State assumptions inline.** Where Linear has no estimate and you sized it yourself, say so at the point of use, not in a footnote.

---

## Step 10: Self-Improvement

After the plan is delivered, reflect:

- Did `team.md` have what was needed, or did you have to ask for profiles mid-run? If you learned something durable about a teammate, offer to append it.
- Were Linear's stated relations trustworthy, or did the codebase probe overturn them? If a pattern shows up repeatedly (e.g. this team never records `blocks`), note it here.
- Did the chart need several passes to align? If a layout rule would have prevented it, add it to Step 6.
- Did the user push back on assignments? Capture the preference — it's usually a standing rule (e.g. "never give the new hire the migration").

If anything would have gone better with different instructions, **edit this skill file** (`~/.claude/skills/plan-initiative/SKILL.md`) surgically — add the note near the relevant step rather than rewriting it. Tell the user what changed and why.
