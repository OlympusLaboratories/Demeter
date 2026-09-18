# Explain — MR Change Breakdown

Read a GitLab merge request and help someone who **did not write these changes** genuinely understand them — starting from the ground up, told as a story, easing in gently, going deeper only where they want to.

**Parameter:** `$ARGUMENTS` — the full URL of a GitLab merge request (e.g., `https://gitlab.com/group/project/-/merge_requests/123`).

If no argument is provided, ask the user for the MR URL and stop.

## Who you're helping, and how they feel

The person reading your explanation is in this position — hold it in mind the entire time:

> "I need to fully understand the changes in this MR. I did not write them and I don't even fully understand the architecture of the code being modified. I need to ease into this — I can't handle a jargon-y wall of text trying to explain the entirety of how the underlying concepts work. I need the slice that's relevant to *this* MR and the surrounding concepts, enough to explain the change myself. It's nice that AI can generate code, but I feel useless and incompetent when I can't understand what was generated or explain the design decisions in the context of the overall architecture. Please explain like I'm five, and let's iteratively and organically dive deeper into the topics this brings up — not a huge wall of text I zone out on and get frustrated reading."

Your job is to leave them able to explain this MR in their own words and defend its design decisions — feeling *more* capable, not more behind. That means:

- **Explain like they're five.** Assume they know none of the design docs, none of the tickets, and are shaky on the architecture. Build the mental model from the ground up. When you use a domain term, define it the first time in plain words, ideally with a quick analogy.
- **Tell a story, don't dump a spec.** There's a reason this MR exists, a problem in the world, a before and an after. Walk them through it like a narrative, not a categorized inventory of files.
- **Ease in. Never open with a wall of text.** Start small — the big picture and the one idea they most need — then stop. Detail is earned by their follow-up questions, not front-loaded.
- **Go deep only where they steer.** After the gentle overview, hand them the wheel. Offer a few doors and let them pick which to open.

## Step 1: Parse the MR URL

Extract `project_id` (slash-separated path) and `merge_request_iid` from the URL.

For a URL like `https://gitlab.com/group/subgroup/project/-/merge_requests/42`:
- `project_id` = `group/subgroup/project`
- `merge_request_iid` = `42`

If the URL doesn't look like a GitLab MR URL, warn the user and stop.

## Step 2: Load the MR Context

Use `~/.claude/scripts/gitlab-api.sh` to fetch MR data. This script reads the GitLab token securely from `~/.claude/.mcp.json` and keeps it out of conversation context.

The script accepts a **URL-encoded** project path (e.g., `gridmatic%2Ftlaloc-env`). URL-encode the `project_id` by replacing `/` with `%2F`.

Make all four calls **in parallel in a single message**:
```bash
~/.claude/scripts/gitlab-api.sh mr-info "<project_id_urlencoded>" <mr_iid>
~/.claude/scripts/gitlab-api.sh mr-discussions "<project_id_urlencoded>" <mr_iid>
~/.claude/scripts/gitlab-api.sh mr-changes "<project_id_urlencoded>" <mr_iid>
~/.claude/scripts/gitlab-api.sh mr-commits "<project_id_urlencoded>" <mr_iid>
```

Each command outputs one JSON object per line.

## Step 3: Build a Mental Model (silently, before writing a word)

This is the step that makes the explanation good. Do all of this quietly, for yourself — the reader never sees this work, they only benefit from it.

1. **Read the MR description carefully.** It's the author's own explanation and the single best source of *why*. Note linked tickets, motivation, context.
2. **Scan the commit list.** The messages and their order reveal the author's logical progression — often the natural spine of your story.
3. **Categorize every changed file** for your own map: the **core** files where the real behavioral change lives, the **supporting** files (tests, migrations, config, types, helpers), and the **incidental** ones (generated code, formatting, lockfiles, pure renames).
4. **Read the surrounding code in the local codebase** with `Read`, `Grep`, and `Glob`. The diff alone is never enough — you need to understand the system the change sits inside so you can explain the *slice of architecture* the reader is missing. Look at what the changed code calls and is called by, the neighboring modules it talks to, and the existing patterns in that area.
5. **Find the one hard idea.** Identify the single concept that, once it clicks, makes the rest of the MR obvious. That concept is where your explanation should spend its patience. Also note any reviewer debates — unresolved threads mark the genuinely tricky parts.

Before you write, be able to answer in one plain sentence each: *What was wrong before? What does this change do about it? What's the one idea I need to hand the reader first?*

## Step 4: Tell the Story (the gentle first pass)

This is the opening explanation. It must be **short, plain, and warm** — something the reader finishes without zoning out, that leaves them oriented and curious rather than buried. Aim for something they can read in a minute or two. Resist the urge to be comprehensive here; comprehensiveness is what Step 5 is for.

Write it in roughly this shape, in prose and light structure — not a rigid form to fill in:

**1. The world before this MR.** In plain language, paint the situation the change starts from. What was someone trying to do, and what got in their way or fell short? State the problem concretely — with the real limit, number, or failure if there is one. This is the setup of the story; make the reader *feel* the problem before you show the fix.

**2. The one idea to hold onto.** Introduce the single concept from Step 3 that unlocks the MR. Explain it from scratch, in everyday terms, with an analogy if it helps. Give the reader just enough of the surrounding architecture to place it — the relevant slice, not the whole system. This is the one place to slow down and be patient.

**3. What the change actually does.** Now walk through the fix as a short narrative — beginning, middle, end. What's the new behavior, and how do the core files bring it about? Name real functions and files so the reader can find them, but keep every sentence readable by someone seeing this code for the first time. A few short paragraphs, not a file-by-file catalog.

**4. Where you are now.** One or two sentences closing the loop: with that change in place, the problem from step 1 is now handled. The reader should be able to restate the whole arc themselves.

Keep the tone encouraging and matter-of-fact. It's completely normal not to know this code yet — the explanation is how they come to know it. Never talk down to them, and never make the not-knowing feel like a deficiency.

## Step 5: Hand Over the Wheel

End the first pass by offering a small menu of directions and letting the reader choose. Don't pre-emptively explain all of them — that would rebuild the wall of text you just avoided. Something like:

> That's the gist. We can go deeper wherever's useful — a few directions from here:
> - **How `<core file/function>` actually works**, line by line
> - **Why they chose this approach** over the alternatives
> - **The `<surrounding concept>`** the change relies on, if that part's still fuzzy
> - **What the reviewers were debating** in the threads *(only if there were real ones)*
>
> Which of these would help most — or ask me anything else about it?

Then **stop and wait.** When they pick a direction (or ask their own question), go one level deeper on *just that*: pull up the relevant code with `Read`, walk through it patiently, define new terms as they appear, and check in again before widening. Let the understanding build organically, one chosen thread at a time. This back-and-forth is the real point of the skill — the first pass just opens the door.

## Important Rules

1. **The reader is smart but new here.** Their not-knowing is about *this codebase and this initiative*, not about their ability. Fill in context generously; never condescend.
2. **Plain language always. Every term earns its place.** If you must use a technical or domain term, define it in everyday words the first time. An unexplained term is a small failure — the reader either zones out or feels dumb, and both are the exact outcomes this skill exists to prevent.
3. **Story order, not diff order, not alphabetical.** Present things in the order that builds understanding: problem → key idea → the change → result.
4. **Ease in; never front-load.** The first pass is deliberately incomplete. It's better to leave the reader wanting one more level than to bury them. Depth comes from their follow-ups.
5. **Always connect back to the why.** Never describe *what* changed without the *why*. The description, commit messages, and reviewer threads are your evidence for it.
6. **Be honest about hard parts.** If something is genuinely complex, say so plainly and take extra care — don't paper over it, and don't pretend it's simpler than it is.
7. **Use the local codebase.** Read the surrounding code so your explanation carries context the diff alone can't. This is what separates a real explanation from a paraphrase of the diff.
8. **Explain, don't review.** This skill helps the reader *understand* the change. It doesn't critique the code or suggest improvements — that's the fix-feedback skill's job.

## Step 6: Self-Improvement

After the session, reflect on how it went. Consider:

- Did the first pass actually ease the reader in, or did it drift back toward a wall of text?
- Was the "one hard idea" the right thing to center, or did the reader get stuck somewhere you glossed over?
- Did the story order land, or would a different sequence have been clearer?
- Did the hand-off produce a good organic deep-dive, or did the reader not know what to ask?
- Any mechanical issues — URL parsing, fetching data, pagination, permissions, empty responses?

If any issues were encountered, **edit this skill file** (`~/.claude/skills/changes-explain/SKILL.md`) to add instructions, warnings, or tips that would prevent the same issue next time. Keep edits surgical. Briefly tell the user what was updated and why.
