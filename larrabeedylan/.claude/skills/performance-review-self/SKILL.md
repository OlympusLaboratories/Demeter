# Performance Review Self-Assessment Generator

Synthesize weekly engineering reports into self-assessment responses for performance review prompts.

## Step 1: Read Review Prompts

Start by reading `prompts.md` in this skill directory. It contains the specific review questions/prompts that need to be answered.

## Step 2: Read Weekly Reports

Read all reports in `context/{START_DATE}_to_{END_DATE}.md`. These are written by the `eng-snippet` skill and contain merged MRs, completed Linear tickets, Slack collaboration context, OKR progress, and evidence highlights.

## TODO

- Define output format and sections
- Define review period selection (quarterly, half, custom range)
- Add instructions for synthesizing across multiple weeks
