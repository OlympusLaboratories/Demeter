# `profiles/` — one directory per machine setup

Each machine's dotfiles and agent configuration live in their own directory here. Three
are real copies — `larrabeedylan_work_darwin`, `larrabeedylan_work_linux` and
`larrabeedylan_home_darwin` — and `larrabeedylan_home_pi` symlinks `skills/`, `hooks/`
and `scripts/` into the home profile rather than being a fourth copy; see its own
`AGENTS.md`.

The two work profiles are **byte-identical**, and the home profile is the work profile
put through a fixed substitution list. `profiles/check-transform.py` is the authority for
that list and for both comparisons; the root `CLAUDE.md` states the rule, and this file
records why the checker exists and what its allowlist is for. Run it with
`profiles/check-transform.py check`, and `rules` to print what it checks.

## Why the checker exists, and why it has an allowlist

### An asserted guarantee is not a guarantee, and this one had already failed on both halves before anybody looked

the bullet above described `cmp transform(work) home` as mechanical while no script existed and nothing compared the two work profiles either. `profiles/check-transform.py` runs both checks — `work_darwin` ≡ `work_linux` byte-identical, and `transform(work_darwin)` ≡ `home_darwin` — and it lives at the repo root rather than in a profile's `scripts/`, because those are symlinked per-machine into `~/.claude/scripts/` and a drift checker that had to exist in four copies would become the thing it checks. **The work-pair half is the one that was never asked for and the one that would have caught the bug**: `docs-humanize` ran in three versions, with `work_linux` and `home_darwin` both descended from a **tracked** `SKILL.md.bak` sitting beside the live file, so the drift was measurement logic — table rows counted as prose sentences, an all-backticked bullet list measured as prose, the dense band at `1.1` instead of `1.25` — and the same document got a different verdict depending on which laptop read it. `*.bak*` is gitignored now, because a backup beside a live file in a directory the installer symlinks **wholesale** is an invitation to edit the wrong one. It compares **git-tracked files only**, or a machine with `prompts.md` or `team.md` on disk reports drift for user data the repo deliberately does not carry. **The allowlist is what makes it survivable rather than ignored**, and its thirteen entries fall in three classes: per-machine configuration (`skill-env.sh`, `notify-send.sh`, the two `.example` files); **a file documenting the forge adapter's response shape** — `fix-feedback`, `changes-explain` and `skills/AGENTS.md` name `mr-info`/`mr-discussions` with a URL-encoded `project_id` against `pr-info`/`pr-reviews` with plain `owner`/`repo`, GraphQL thread ids against discussion ids, and different step numbering, so they are two implementations exactly as the two adapters are, and re-deriving one over the other would replace correct GitHub documentation with GitLab's API renamed, silently, in the files agents read to call it; and never-transform content (the bilingual frontmatter triggers, and `security-audit`'s `stage1_recon.md`, where "GitLab CI" names a CI product to detect and the transform makes it "GitHub Actions, GitHub CI"). Every entry carries a one-line reason and its **differing-line count is still reported** though not enforced, so an exception quietly growing is visible — and that count must come from a real diff: a positional comparison reported `reflect-week`'s sanctioned three-line divergence as 300, and an exception that looks enormous is one nobody will ever re-examine. **A sentence naming which profile is on which forge cannot survive the transform at all**, since the transform rewrites the forge name wherever it appears: the work copy of `skills/AGENTS.md` transformed to "the work profiles (GitHub) and home (GitHub)", and the hand-edited home copy said the work profiles are the GitHub ones — in the file written to stop precisely that confusion, under a heading whose own first sentence is "nothing in a skill may hardcode the forge". So that paragraph now names no forge and points at `skill-env.sh`. Severity splits by who is reading: the `install.sh` step is **warning-only**, because nothing in the installer may be fatal on the Pi's unattended timer, while the CI job **fails** on unallowlisted drift — CI's only advantage over the installer is that somebody reads it, and a check that stays green regardless is a check nobody reads. Finally, **an allowlist entry is a claim, and claims get re-tested**: `settings.json` went on the list and then turned out to differ by exactly one line — home granting `Bash(~/.claude/scripts/gitlab-api.sh:*)` for a script it does not ship — so it came off the list and the dead permission went with it
### `derive --apply` destroyed the thing the allowlist protects, and `check` went green because it did

`cmd_derive` rewrote the home copy as `transform(work_darwin)` and consulted **neither
allowlist**. A path is on the list *precisely because* its home copy is not
`transform(work)`, so on those paths `--apply` never re-derived a drifted file — it
deleted the divergence the entry exists to record. And the verification step afterwards
**passed because of the deletion**: `check` only ever compares `transform(work_darwin)`
against `home_darwin`, so flattening the home copy is exactly what makes that comparison
succeed. Silent, destructive and self-concealing, in a command this repo's own help text
recommends by name — so the recommendation and the hazard arrived together.

Observed on a branch whose only intended change was a 20-line addition:
`derive skills/AGENTS.md --apply` took the home diff from `+20` to `+50 −11`, replacing
eleven hand-written home paragraphs with transformed work prose. The **only** signal was
the exception count dropping from 14 to 13, which reads as an improvement rather than a
loss, and it was caught by reading a diffstat.

**There are two destruction shapes, and the ticket named one.** `TRANSFORM_EXEMPT`
overwrites a hand-maintained home copy — `notify-send.sh` is 185 differing lines,
`fix-feedback/SKILL.md` 160. But `PRESENCE_EXEMPT` is worse in kind: there the **absence**
is the allowlisted fact, so `derive scripts/gitlab-api.sh --apply` *creates* a GitLab
adapter on the GitHub profile, and the same command would plant all three work-only
`reflect-*` skills in a profile that deliberately ships none.

Five things carry the fix. **It refuses rather than warns**, because a warning on stdout
is what the original run already printed (`wrote profiles/…/AGENTS.md`) and read straight
past. **It is gated on `--apply`**, so a bare `derive <allowlisted path>` still prints to
stdout — that read-only inspection is how you decide whether an entry should be retired,
and refusing it would remove the tool you need to clear the refusal. **The guard runs
before the source read**, since `scripts/github-api.sh` is home-only and reading first
answers `cannot read …` — true, and silent about the real reason. **`WORK_PAIR_EXEMPT` is
not consulted**, because `derive` only ever writes `home_darwin` and that table governs
`work_darwin` against `work_linux`. And **`--force` prints what it replaced** — the
differing-line count and the reason being discarded — for the genuine case of retiring an
entry.

**The count became a ratio, and that is the half that makes a flatten visible.** `check`
now reports `14 of 14 allowlist entries still diverging` and **names** any entry that has
stopped, rather than leaving the fact encoded in a number nobody memorised. It is
**reported, never enforced**: an entry legitimately stops diverging in the commit that
retires it, so failing CI there would make that commit unmergeable, and the installer's
step must stay warning-only regardless. The enforcement lives in
`tests/check-transform-derive.py`, which asserts `N == M` against the real repository — a
correct retirement removes the entry *and* re-derives the file, so it keeps `N == M`,
while a flatten that leaves the entry behind fails. That is the assertion that would have
caught the original bug.

**Writing the test found a second, latent bug the real repo hides.** The single write site
was a bare `open(target, 'w')`, which raises `FileNotFoundError` when the target's parent
directory does not exist. Every allowlisted path in the repo today sits in a directory
that already exists on both sides, so it never fired — but retiring a `PRESENCE_EXEMPT`
entry is exactly the case where the home side has no such directory, which is the one
thing `--force` was added to support. The write now creates the directory.

### How the transform rule was arrived at, and its two never-transform cases

The root `CLAUDE.md` carries the substitution list itself and the three traps. This is the
reasoning behind it — the hole that was found in the list, the cost of not treating
divergence as a transform, and the two classes of content the transform must never touch.

The sentence-case rule is the one that was missing, and the hole was structural rather than cosmetic: the set carried the lowercase and the title-case forms, so "Merge request" at the start of a line or after a dash fell through every rule. Treating it as a transform rather than an edit is what makes drift detectable: the checker either passes or names the file and the first differing line. It had not been treated that way, and the cost was real — `fix-linear` and `commit-msg` on the home profile still said "merge request" and "GitLab" throughout, because they were copied rather than transformed. And a **frontmatter trigger list is bilingual on both profiles, so it is the second never-transform case** alongside URLs: `changes-diagram`'s `description:` carries both `"visualize the MR"` and `"visualize the PR"` on work *and* home, because those strings are utterances a user might type rather than vocabulary describing a forge — a user on either machine says either word. Transforming them collapses the pair into a duplicate and silently drops a trigger. Prose in a description still transforms normally (`autopilot`'s "merged merge request" must become "merged pull request"), so the exemption is the quoted phrases, not the line. That URL rule binds only the files the checker enforces: an allowlisted file is hand-maintained per forge, so the literal `gitlab.com/-/merge_requests/123` example in the work copies of `changes-explain` and `fix-feedback` is correct where it sits and stays there. The corollary bites in ordinary prose too: a work copy that reaches for the neutral "change request" transforms to "change request", not "pull request", so a home copy hand-edited to the right word reads as drift forever. 
