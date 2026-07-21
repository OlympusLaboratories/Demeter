# Performance Review Self-Assessment Generator

Turn weekly engineering reports into draft answers for performance-review prompts.
The output is a starting point the user edits — get it close enough that they only
tweak, not rewrite.

## Step 1: Read the prompts

Read `prompts.md`. Note the exact question, the word limit, and any hint the prompt
gives about what it wants (e.g. "the why matters: impact, difficulty, or what you
learned" — that means the answer is not done until it says why).

## Step 2: Read the weekly reports

Read every file in `context/`. They're written by the `eng-snippet` skill: merged MRs,
Done Linear tickets, in-progress tickets, Slack collaboration, OKR mapping, evidence
highlights. The period to cover is whatever the prompts name (e.g. "Q1 and Q2").

If the reports don't cover the whole period (there are usually gaps), say so **once**,
briefly, and offer to pull the missing window from Linear/GitLab. Don't belabor it.

## Step 3: Pick the accomplishments — get the altitude right

This is where the first drafts failed hardest. Rules:

- **Top accomplishments are owned, multi-week/multi-month initiatives or projects.**
  Never offer a single bug fix, one incident, or a debugging session as a top-2
  accomplishment. Those are *supporting evidence*, not headlines.
- **If the prompt asks for N accomplishments, all N should be comparable in weight.**
  Don't pair a quarter-long migration with a one-day fix.
- Prefer work the person **owned end to end** and work that maps to a stated OKR/project.
- Incidents, clever debugging, and cross-team unblocks are real and worth mentioning —
  but as detail *inside* a bigger accomplishment, or as answers to a different prompt.

## Step 4: Draft — evidence and the "why"

**Every claim must trace to something you can point at.** Reviews are read line by line;
anything the user can't defend gets them "hey, can you explain what you meant here?"
Before writing a claim, find the Done ticket or merged MR behind it.

- **Do not present in-progress / draft / in-review work as delivered.** Check ticket
  status and whether MRs actually merged. "Delivered X" when X is a draft MR is the
  exact thing that gets flagged.
- **No editorializing adjectives.** Cut "durable," "robust," "significant," "seamless,"
  "huge" (unless the *user* chooses to add them — see below).
- **No sweeping quantifiers you can't enumerate.** "Advancing nearly every key result of
  the OKR" is not defensible unless you can name the specific KRs that had *completed*
  work. If you can't, name the one or two that did, or drop the OKR framing.
- **Don't cherry-pick an arbitrary subset of features.** Listing "feature A and feature B"
  out of ten reads as padding. Describe the accomplishment as one coherent thing.
- **Include the why.** The prompt asks for impact, difficulty, or what was learned —
  include at least one. Do not strip this out in the name of caution; a bare list of
  facts with no "why" is an incomplete answer.
- **Forward-looking impact is allowed** if hedged honestly ("potentially a big impact on
  X") — and it's the user's call how strong to make it. Give them the honest raw material
  and let them decide their own pride level. Don't pre-censor it to bland.

## Step 5: Voice — write like a person

The user's repeated, blunt feedback: **write like a person, not a corporate bot. Cut the
filler.** Concrete rules, with real examples of what got rejected:

- First person, plain verbs: "I moved," "I deleted," "I got it running," "I finished it,"
  "I owned it end to end."
- **Banned:** jargon-stacked noun phrases ("headline Q1 CD-reliability OKR," "phased
  additive-then-cutover"), buzzword verbs ("proactively broadcasting"), and self-important
  phrases ("sole institutional-knowledge holder," "multiply the impact," "durable
  architecture, not one-offs").
- Go easy on em-dashes used for drama. A parenthetical or a plain sentence usually reads
  more human.
- Say what a thing is in words a teammate would use out loud. If you wouldn't say it in
  a standup, don't write it.

## Output format

- **Print the answers directly in chat as markdown.** Do not write an HTML or doc file.
- Show the word count next to each answer and keep it **under** the prompt's limit.
- Label them as drafts. If any claim is speculative or you couldn't fully verify it,
  **flag it explicitly** next to the answer instead of quietly baking it in — offer the
  precise-but-blander alternative so the user chooses.
- Keep your own commentary short. The user wants to finish the review and move on.
