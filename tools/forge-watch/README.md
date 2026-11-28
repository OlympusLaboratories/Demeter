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

Every line is an event, and every line is emitted **once per commit**. A state that has not
changed is not repeated, because a `persistent: true` monitor that reports the same thing
every 60 seconds is stopped by the harness for producing too many events.

| Line | When |
| --- | --- |
| `STATUS state=… merged=… review=… head=…` | first poll, and whenever any of those change |
| `REVIEW decision=…` | a review verdict exists — `APPROVED`, `CHANGES_REQUESTED` |
| `THREADS unresolved=N` | at least one unresolved review thread |
| `CHECK <name> <conclusion>` | a check reaches a terminal conclusion |
| `WAITING n of m check(s) still running` | checks exist and some are pending |
| `CHECKS none reported yet` | the head commit has no checks attached yet |
| `CHECKS all n check(s) complete and green` | every check on this commit passed |
| `CHECKS finished with failures: …` | every check finished and at least one did not pass |
| `POLL ERROR …` | one poll failed, carrying the command's stderr |
| `TERMINAL …` | merged, closed, the poll budget ran out, or the watch gave up |

It exits `0` on a terminal state and `1` when it gave up or `gh` is absent. A suggested
`Monitor` filter:

```
grep -E --line-buffered "TERMINAL|CHECKS |POLL ERROR|REVIEW |THREADS unresolved=[1-9]"
```

`CHECKS ` is in that filter and not optional: it is how the run hears that CI settled, now
that settling is not an exit.

## Checks settling is not a terminal state

Only the request's own end states end the watch — `merged`, `closed`, the poll budget, and
`MAX_ERRORS` consecutive failed polls. Every check going green does **not**, because green
on an open pull request is the ordinary mid-run condition of one waiting on a review
verdict, a merge gate, or another push.

OLY-260 is what that cost. The watch exited the moment CI passed, and a review round is
*expected* to push again — autopilot routes every confirmed finding through `fix-feedback`
and then pushes — so `green → push → green` is the designed happy path and the watch was
guaranteed to be gone before the second push. Nothing re-armed it. One run sat for an hour
with its pull request approved, then conflicted, and nothing watching it.

Exiting bought nothing, which is the part worth understanding: the `Monitor` tool turns
**every stdout line** into an event, so the run is woken by the green line whether or not
the process then ends. Reporting and exiting were never the same action.

That made the dedup map outlive a commit for the first time, and `say_once` had to change
with it. Its key is now the head SHA plus the text, so a check that failed, was fixed and
failed again on the new commit is reported again instead of being swallowed as "already
said". Keyed on the text alone, the watch would have stayed alive and gone quiet — which is
the one failure this tool exists to prevent, arriving by the opposite route.

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

## Terminal states are decided by the benign set, never the failing one

A check is **still running** only while its `status` is not `COMPLETED`, and a conclusion
counts as **green** only when it is `SUCCESS`, `NEUTRAL` or `SKIPPED`. Everything else is
terminal and failed, including a value this script has never heard of.

That is the opposite of the obvious design, and the reason is that the obvious design is
the bug this tool exists to prevent. The first version listed the conclusions it knew, and
GitHub's `CheckConclusionState` already carried one it did not — `STARTUP_FAILURE` — so a
check failing that way would have been counted as pending on every poll and the watch
would have run forever. Enumerating an open set leaves that hole open; enumerating the
closed set cannot. Both directions now fail safe: a watch that stops early and says why is
recoverable, and one that silently reads an unknown value as green is worse than one that
never started.

`tests/check-forge-watch.sh` pins this, including a deliberately invented
`SOME_FUTURE_STATE`.

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
