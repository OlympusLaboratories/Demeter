# `forge-watch`

One line per change in a pull request's state, for the `Monitor` tool. Nothing else here
polls a forge: every autopilot run used to hand-roll its own loop, and OLY-35 is what that
cost.

```bash
~/.claude/tools/forge-watch/watch.sh <owner> <repo> <pr-number>
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `SLEEP` | `60` | Seconds between polls. Do not go below 60 against a remote forge. |
| `MAX_POLLS` | `0` | Stop after this many polls. `0` means run until a terminal state. |
| `MAX_ERRORS` | `3` | Consecutive failed polls before giving up. |

## Smoke-test it before you arm anything

```bash
MAX_POLLS=1 SLEEP=0 ~/.claude/tools/forge-watch/watch.sh OlympusLaboratories Demeter 28
```

A real `STATUS` line means it works **on this machine**. Empty output or a `POLL ERROR`
means the `Monitor` you were about to arm would have waited forever. That one command is
the whole protection, and it is cheaper than every alternative — see autopilot Step 5.

## What it emits

Every line is an event, and every line is emitted **once**. A state that has not changed
is not repeated, because a `persistent: true` monitor that reports the same thing every 60
seconds is stopped by the harness for producing too many events.

| Line | When |
| --- | --- |
| `STATUS state=… merged=… review=… head=…` | first poll, and whenever any of those change |
| `REVIEW decision=…` | a review verdict exists — `APPROVED`, `CHANGES_REQUESTED` |
| `THREADS unresolved=N` | at least one unresolved review thread |
| `CHECK <name> <conclusion>` | a check reaches a terminal conclusion |
| `WAITING n of m check(s) still running` | checks exist and some are pending |
| `CHECKS none reported yet` | the head commit has no checks attached yet |
| `POLL ERROR …` | one poll failed, carrying the command's stderr |
| `TERMINAL …` | merged, closed, every check finished, the poll budget ran out, or the watch gave up |

It exits `0` on a terminal state and `1` when it gave up or `gh` is absent. A suggested
`Monitor` filter:

```
grep -E --line-buffered "TERMINAL|POLL ERROR|REVIEW |THREADS unresolved=[1-9]"
```

## Why it uses only `gh`

One `gh api graphql` call per poll, with `--jq`, and nothing else.

- **No external `jq`.** It is not installed on `piserver`, where phone sessions run the
  same skills a laptop runs. A loop built from the external binary fails on every poll
  there, and a `2>/dev/null` around it makes that look like an empty result.
- **No `gh <subcommand> --json`.** The Pi's `gh` is an older build and `--json` support
  differs per subcommand; `gh pr checks --json` is the one already observed missing.
  `gh api graphql` is stable across both.
- **Not `github-api.sh`.** That script needs `GITHUB_PERSONAL_ACCESS_TOKEN` in the
  environment and exits without it. On the Pi the token lives in `gh`'s own credential
  store instead, so `gh` works there and the script does not.

## Two failure modes it is built around

**A failed poll emits, and a repeated one is terminal.** `|| true` around a poll is right
for one dropped request and wrong for a missing binary, which fails identically on every
attempt — that is how a watch stays alive, reports nothing it was armed for, and never
exits. So each failure prints `POLL ERROR` with the real stderr, and `MAX_ERRORS` of them
in a row ends the watch loudly.

**An empty answer is not a healthy one.** A response carrying no pull-request state is
reported as a failed poll naming the repo and number, not as "nothing to report" — a wrong
number would otherwise read as a PR that simply has no checks yet, forever.

## Where it runs from

Give it a working directory the run cannot delete. A watcher started inside a worktree
that autopilot Step 10d later reclaims fails on the harness's trailing `pwd`, so a script
that exited `0` is reported as exiting `1`.
