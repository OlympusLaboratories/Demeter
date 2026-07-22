# Performance Review Peer Assessment Generator

Synthesize weekly engineering reports into peer assessment responses for performance review prompts.

## Step 1: Read Review Prompts

Start by reading `prompts.md` in this skill directory. It contains the specific peer review questions/prompts that need to be answered.

## Step 2: Read Peer Collaboration Profiles

The peer name is provided as an argument (e.g., `reflect-peer mark`). Read all weekly profiles in `context/{peer_name}/{START_DATE}_to_{END_DATE}.md`. These are written by the `reflect-week` skill and contain Slack interactions, MR reviews, shared Linear tickets, and collaboration summaries specific to that peer.

## Step 3: Pull Peer's MRs for Context

Use the GitLab helper script or MCP tools to fetch the peer's merged MRs for the review period. This helps understand their code contributions and relate them to the collaboration evidence in the context reports.

## TODO

- parameterize by peer name
- pull MRs for the peer for time range to understand code contributions and relate to collaboration done in context reports to write perfomance review prompt answers
- Define output format and sections
- Define review period selection (quarterly, half, custom range)
- Add instructions for synthesizing across multiple weeks
