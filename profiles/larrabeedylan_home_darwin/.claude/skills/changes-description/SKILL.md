# PR Description Generator

Generate a succinct yet clear pull request description based on the changes already discussed in the current chat context.

## Prerequisites

This command expects that the current conversation already contains context about the branch changes — typically loaded via `/changes-branch` or by the user pasting diffs/discussing code changes. If no changes have been discussed, tell the user: "No changes found in the current conversation. Run `/changes-branch` first or describe/paste the changes you'd like summarized."

## Step 1: Analyze the Conversation Context

Review all changes discussed in the current chat:
- Diffs, code snippets, and file modifications
- The user's stated intent or goals for the changes
- Any bug fixes, features, refactors, or config changes mentioned
- Decisions made during the conversation (e.g., why a particular approach was chosen)

## Step 2: Write the PR Description

**Output the PR description inside a single markdown code block** (triple backticks with no language tag) so the user can copy the raw markdown and paste it directly into GitHub's PR description field, where it will render correctly with headings, bullets, and links intact. The content inside the code block must be valid, well-formatted markdown.

Use this template inside the code block. The **Summary** and **Changes** sections are always required. The remaining sections are optional — only include them when the conversation contains relevant context.

```
## Summary

1-3 sentences explaining what this PR does and why. Be specific about the concrete change — name the components, services, or files affected. Reference the problem, ticket, or goal that prompted the change.

## Changes

Bulleted list of the key implementation details — only include items that a reviewer needs to know to understand the approach. Skip obvious or trivial changes. If there are notable trade-offs or alternatives that were considered, mention them briefly.

## Testing

(Optional — include only if tests were added or modified.)
Brief description of what tests were added/changed and what they cover.

## Verification

(Optional — include only if commands were run during the conversation to verify correctness, e.g., linting, dry-runs, syntax checks, `terraform plan`, `helm template`, etc.)
List the commands used and their outcomes.

## Rollout

(Optional — include only if there are deployment steps, feature flags, migration considerations, or sequencing requirements.)
Bullet the rollout steps or considerations a reviewer/deployer should be aware of.
```

**IMPORTANT:** The description MUST be wrapped in a code block so the user copies raw markdown, not rendered markdown. When pasted into GitHub's description field, the markdown will render properly with headers, bullets, and links.

### Guidelines

- **Be concise.** Reviewers skim PR descriptions. Prefer short sentences and bullets over paragraphs.
- **Be precise.** Use the actual names of functions, files, services, and config keys from the diff. Don't paraphrase loosely.
- **Don't pad.** If the change is simple, the description should be short. A one-line fix needs only a brief Summary and Changes. Only include Testing, Verification, and Rollout when there's real content for them — never add placeholder text like "N/A".
- **Don't editorialize.** Stick to what the code does. Avoid subjective claims like "greatly improves" or "much cleaner".
- **Respect what was discussed.** If the user explained their reasoning during the chat, reflect that in the Why section rather than inventing your own rationale.

## Step 3: Self-Improvement

After generating the description, reflect on how the execution went. Consider:

- Was there enough context in the conversation to write a good description, or were there gaps?
- Did the user need to correct or adjust the output?
- Were there edge cases (multiple unrelated changes in one branch, unclear intent)?

If any issues were encountered, **edit this skill file** (`~/.claude/skills/changes-description/SKILL.md`) to add instructions or tips that would prevent the same issue next time. Keep edits surgical. Briefly tell the user what was updated and why.
