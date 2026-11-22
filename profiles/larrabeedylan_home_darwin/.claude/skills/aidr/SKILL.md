---
name: aidr
description: Re-render a wall of agent-written text as something a human can scan — actions first, commands inline, links clickable, no fluff. "AI; didn't read", after tl;dr. Use when the user says aidr, tl;dr, I'm not reading that, too long, summarize that, give me the short version, what do I actually need to do, cut the slop, or invokes /aidr. Also use on a pasted wall of text, a generated plan, a ticket, a release note or a review comment the user cannot parse.
---

# AIDR — Artificial Intelligence; Didn't Read

The user is looking at text an agent produced and will not read it. Your job is to render the same content in a form they can scan in about ten seconds and act on without re-reading.

**This is a compression, not a rewrite.** You may drop anything. You may never add anything. Every line you produce traces back to the source, and where the source is silent — who runs a step, what value goes in a command, whether something already happened — **say it is silent.** An invented step is worse than the wall it replaced, because the wall was at least true.

**Do not do the work.** The source is often a plan or a set of instructions. Summarizing it is the whole task: do not start implementing, do not run the commands you list, and do not fix the thing being described. The user will act, or ask.

**Parameter:** `$ARGUMENTS` — optional.

| Argument | What to summarize |
|---|---|
| *(none)* | The assistant message immediately before this one. If that message was short, take the whole preceding exchange. |
| Pasted text | That text. |
| A pointer — "the plan above", "that review", "the ticket" | Resolve it in the conversation and summarize that. |
| A file path or URL | Read it, then summarize it. |
| A number or label from a previous `/aidr` **Expand** line | Elaborate on that item only. Same rules, same budget. |

## Step 1: Classify Every Item

Read the source and sort each piece of information into one of four classes. The class decides which section it lands in, and a reader must never have to work out which class a line belongs to.

| Class | Section | Test |
|---|---|---|
| Action required of the user | **Do this** | The user has to type, click, decide or approve something |
| Action already taken | **Done** | The agent already did it; the user is being informed |
| Fact needing no action | **Notes** | True and worth knowing, but nobody has to do anything |
| Explanation | **Why** | Background, reasoning, context |

Two rules make this classification worth doing:

- **If the source does not say who does something, that is a Note, not an action.** Write what the source said and that it does not say who. Guessing it is the user's job invents a chore; guessing it is done invents a completion.
- **Anything that fits no class is dropped.** Restated requirements, descriptions of how the work was done, transitional sentences, and summaries of the summary are not information.

## Step 2: Budget It

- **Body: 150 words maximum**, excluding fenced code blocks and link text. Code is the payload, not prose.
- **The whole thing fits one screen.** If it does not, the compression is not finished.
- **Actions are never dropped.** Every other section is budgeted; dropping an action is the one unsafe compression here. With more than about seven actions, group them under short sub-headings and keep all of them.
- **Omit an empty section entirely.** Never write a heading with "None" or "N/A" under it — a heading that carries nothing still costs a read.

If the source turns out to contain nothing actionable and nothing worth knowing, say exactly that in one line and stop. That is a useful answer and it saves the user the scan.

## Step 3: Render

Fixed section order. Actions come first because theirs is the only section with a deadline attached.

````markdown
**Bottom line** — <one sentence, 25 words max>

**Do this**

1. <imperative instruction, one action>
   ```bash
   <exact command>
   ```
2. <imperative instruction> — [config.ts:88](src/config.ts#L88)

**Done**

- <past tense, what changed>

**Notes**

- <fact>

**Why** *(usually omitted — they can ask)*

- <reason>

**Expand:** `1` <topic> · `2` <topic> · `3` <topic>
````

### Commands

- **Put the command at the step that needs it**, in a fenced block, never described in prose. The user copies; they do not assemble.
- **A command runs as-is, or the step names exactly what to substitute.** `<cluster-name>` is acceptable only when the step says where to get the value. A placeholder the user has to guess is a failed step.
- **One command per block** when the user should check the result between them. Several lines in one block only when they are meant to run as a unit.
- **Never put a destructive command in a block without the consequence in the step text.** The block is the thing that gets copied, so the warning has to be readable before it.

### Links

- **Every path and URL is a clickable markdown link.** Files relative to the workspace root: `[install.sh](install.sh)`, `[SKILL.md:42](profiles/x/.claude/skills/y/SKILL.md#L42)`. URLs plain: `[the pipeline](https://…)`.
- **A bare backticked path is not clickable** and costs the reader a search. Use backticks for commands, flags and symbols — not for things that can be opened.

### Expand

End with the handful of things you could say more about, each a few words. The user picks one and you elaborate on that, under these same rules.

This exists so depth is **offered rather than delivered**. Pre-emptively explaining every point is how the wall got built in the first place. Three to five candidates; omit the line when the source genuinely has no more in it.

## Step 4: Check the Writing

Apply the **ASD-STE100 Simplified Technical English** writing rules. These are the checkable ones:

- **One instruction per sentence.** Two actions means two steps.
- **Procedural sentences under 20 words. Descriptive sentences under 25.**
- **Active voice.** "The hook writes the file", not "the file is written by the hook".
- **Imperative for instructions.** "Run the migration" — not "You should run the migration" or "The migration needs to be run".
- **Simple tenses.** Present, past, future simple. Not "will have been running".
- **One word, one meaning.** Pick a word per concept and reuse it. "Follow the steps", not "adhere to the steps".
- **Keep the articles.** "Run the script", not "Run script".
- **No noun cluster longer than three words.** "The runner cache invalidation policy failure" is not a phrase a human parses.
- **No idiom, slang, or jargon the user has not already used themselves.**
- **Warnings before the step they apply to**, never after.

**Do not claim STE compliance.** Real compliance needs the approved-word dictionary, which is not checkable here. These are the writing rules; the output follows them, and that is the claim.

## Step 5: Strip the Fluff

Delete all of this on sight. The test for each: the reader is worse off for having read it.

- Preamble: "Here is a summary", "Sure", "Great question", "Let me break this down".
- Any restatement of what the user asked for.
- Closing offers: "Let me know if you need anything else", "Happy to go deeper". The **Expand** line replaces every one of them.
- Empathy and editorialising: "This is a bit tricky", "Unfortunately", "I understand the frustration", "Good news!".
- Self-description: how you worked it out, what you read, how many files you looked at.
- Hedging that changes nothing: "it seems", "arguably", "it is worth noting that".
- Any sentence that would read identically had the work gone the other way.

**The sharpest test: delete every sentence that would still be true if the work had failed.** What is left is the content.

## Important Rules

1. **Never add information.** Not a step, not a command, not a cause, not a status. Everything traces to the source, and silence in the source is reported as silence.
2. **Never do the work.** `/aidr` reads and renders. It does not implement, run, fix or commit.
3. **The response is the deliverable.** It obeys every rule in this file, starting with no preamble. Do not announce the summary; print it.
4. **Never drop an action.** Everything else is compressible.
5. **A short source stays short.** If the source was already two clear sentences, say so in one line and do not impose headings on it. Over-structuring is its own kind of noise.
6. **State uncertainty once, plainly, where it applies** — not as a disclaimer at the top and not as a hedge on every line.
