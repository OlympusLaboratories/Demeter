---
name: ping
description: Send the user a deliberate push notification on their phone, carrying what this session is working on and what it needs from them. Use when the user says ping me, ping me when you're done, ping me if anything comes up, let me know when that finishes, let me know if you get stuck, tell me when you need something, notify me, text me — or invokes /ping. Also used by other skills that need to hand a status update, a question, a blocker or a finished run to the user while they are away from the terminal.
---

# Ping — Tell the User Something, On Their Phone

Send one notification to the user's phone through the configured transport. The point is not that a message arrives — it is that the user can read it on a lock screen and know, without opening a laptop, **what this session was doing** and **whether it needs them**. A ping that says "done" wastes the only sentence you get.

The transport (and its credentials) live in `~/.claude/scripts/notify-send.sh` and `~/.claude/notify.json`. Never name or assume a transport in anything you write — say "your phone" if you have to say anything at all.

**Parameter:** `$ARGUMENTS` — an optional level word, plus an optional note about what to say. Both may be absent.

## Step 0: Is This a Switch-Off?

If `$ARGUMENTS` is `off`, `quiet`, `disarm` or `mute`, on its own, the user is switching this session's notifications off rather than asking for a message. Run this and stop — **send nothing**:

```bash
SESSION="${CLAUDE_CODE_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
if [ -n "$SESSION" ]; then
  "$HOME/.claude/hooks/notify.py" --disarm "$SESSION"
else
  echo "no session id — nothing to disarm"
fi
```

Then report in one line that this session will not notify again until the next ping. Sending a notification on this path would be precisely backwards: the user is at the keyboard telling you they are at the keyboard.

Everything below is for an actual ping.

## Step 1: Pick the Level

Take the level from `$ARGUMENTS` if it names one. Otherwise infer it from the state of the session.

| Word in `$ARGUMENTS` | Level | Use when |
|---|---|---|
| `done`, `finished`, `complete` | `stop` | The work is finished and nothing is blocking. |
| `question`, `decide`, `ask` | `question` | A decision is needed before the work can go on. |
| `blocked`, `permission`, `auth` | `permission` | Needs permission, a credential, a login, or access. |
| `progress`, `status`, `update` | `progress` | A status update part-way through a long run; work continues. |
| `failed`, `error`, `broke` | `failure` | Something broke and will not be fixed without intervention. |

**Default: `stop`.** Use it when `$ARGUMENTS` names no level and the situation does not clearly point at one.

Whatever in `$ARGUMENTS` is not a level word is a note from the user about what they want said. Fold it into the body; it does not replace the context.

## Step 2: Write the Message

The title is `<repo> <short label>` — the same shape the automatic notifications use: `demeter finished`, `ingestion needs a decision`, `billing-api failed`.

The body is **one to three sentences, and never more than 68 words**. That is a hard budget, not a style note. It must answer both of these:

1. What was this session working on?
2. What does it need from the user — or does it need nothing?

Take the context from the session, never from imagination. If the work cannot be described in 68 words, that is a signal the line is too vague, not that the budget is too small. Only the first ~140 characters reach a lock screen, so put the answer first and the detail second.

**A change request gets its full URL, never just its number, and the block below fetches it for you.** `notify.py --change-request` resolves this session's change request from its own transcript, filtered to the session's remote so a URL mentioned in passing cannot win, and the envelope appends it when the body does not already carry one — so the link arrives whether or not you remembered it. Write it into the body yourself when you know it; the append is the backstop, not the plan. `PR #10` is unopenable from a lock screen; the URL is the only thing on that screen the user can act on. The same goes for a ticket, a pipeline or a published artifact — if the message names a thing that lives behind a link, the link goes in the body. Markdown link syntax is pointless here, so write the bare URL. A file path is the exception: it opens nothing on a phone, so name it without one.

**Never paste your chat response into the body.** A turn's closing message is written for someone reading a terminal with the diff in front of them — it has headings, tables, file links and backticks, none of which survive a notification, and it is routinely twenty times the budget. Write the line from scratch, for someone holding a phone who cannot see any of that.

Before sending, count. If the body is over 68 words, cut it rather than sending it long — drop the detail and keep the outcome and the ask, in that order. These are the things to cut first, in order: file paths and counts, tool and library names, anything about how the work was done, and every clause that would still be true if the work had gone differently.

### Worked examples

Finished a run (`stop`):

```
Bad:   Done!
Bad:   Task complete. Let me know if you need anything else.
Good:  Migrated the 14 cron jobs to the new scheduler; tests green. Nothing needed — review when you're back.
```

Hit a decision (`question`):

```
Bad:   I have a question for you.
Good:  Reindexing meter_reads: the backfill either locks the table for ~8min or runs online over 2h. Need you to pick before I start.
```

Blocked on access (`permission`):

```
Bad:   Blocked.
Bad:   Encountered an issue while attempting to proceed.
Good:  Can't push the release branch — the forge token expired. Need a fresh one in ~/.secrets to finish.
```

Mid-run update (`progress`):

```
Bad:   Still working.
Good:  3 of 7 services migrated, no failures so far. Nothing needed; next check-in when it's done or breaks.
```

Notice what the good ones share: a concrete noun from the actual work, and an explicit sentence about what is or is not required of the user.

## Step 3: Gather Context

```bash
REPO=$("$HOME/.claude/hooks/notify.py" --repo 2>/dev/null) || REPO=""
[ -n "$REPO" ] || REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
BRANCH=$(git branch --show-current 2>/dev/null)
SESSION="${CLAUDE_CODE_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
LABEL=$("$HOME/.claude/hooks/notify.py" --label "$SESSION" 2>/dev/null)
LINK=$("$HOME/.claude/hooks/notify.py" --change-request "$SESSION" 2>/dev/null)
echo "repo=$REPO label=$LABEL branch=$BRANCH session=${SESSION:0:8}"
```

- `REPO` always resolves, and it resolves through the hook so a deliberate ping and an automatic one never disagree about what to call the same session. Inside a checkout it is the repository name. Outside one it is the machine's configured `host_label`, or the directory name when that is unset — and the plain `basename` expression remains as a fallback for a machine where the hook is not installed, because a ping must never fail just because the cwd is not a checkout. A session that always starts in one fixed directory is exactly the case `host_label` exists for: without it, every ping from that box carries the same uninformative word.
- `LABEL` is this session's chat title — the name on the editor tab, either the one Claude Code generated or one the user typed over it. It is the single most useful piece of context in the header, because it says *which* of a dozen live sessions is talking. Where no title exists — a Remote Control session never writes one — the hook **generates** one from the opening prompt and the assistant's first reply, caches it in this session's state file, and reuses it from then on. The first call to resolve it therefore costs a few seconds and every later one is instant; that is the model working, not a hang. A condensed form of the opening prompt is the fallback under that, so a machine with no CLI still gets something recognisable rather than the branch name. It is empty only where the hook is not installed, or for a session with no prompt yet; omit the field then rather than sending an empty string.
- `BRANCH` is empty on a detached HEAD or outside a repo. Omit the field rather than sending an empty string. It is only a **fallback** for a missing `LABEL`: most work here happens in worktrees, where the branch name is the least surprising thing about a session and says nothing about what it is doing.
- `SESSION` is set in a Claude Code session. Only its first 8 characters go in the envelope. If it is empty, omit the field and skip the thread state entirely.

## Step 4: Send It

Build the JSON with `python3` — never by concatenating shell variables, because the body is prose and one apostrophe or newline would produce an envelope the sender rejects. The heredoc is quoted (`<<'PY'`), so nothing in the title or body is expanded by the shell.

Fill in `LEVEL`, `TITLE` and `BODY` from Steps 1 and 2, then run the whole block as one command — the thread id has to be captured and written back in the same shell.

```bash
set -o pipefail
REPO=$("$HOME/.claude/hooks/notify.py" --repo 2>/dev/null) || REPO=""
[ -n "$REPO" ] || REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
BRANCH=$(git branch --show-current 2>/dev/null)
SESSION="${CLAUDE_CODE_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
LABEL=$("$HOME/.claude/hooks/notify.py" --label "$SESSION" 2>/dev/null)
LINK=$("$HOME/.claude/hooks/notify.py" --change-request "$SESSION" 2>/dev/null)
STATE_DIR="$HOME/.claude/notify-state/sessions"

REPLY=$(python3 - "$REPO" "$BRANCH" "$SESSION" "$STATE_DIR" "$LABEL" "$LINK" <<'PY' | "$HOME/.claude/scripts/notify-send.sh" send
import json, os, re, sys

LEVEL = "stop"
TITLE = """demeter finished"""
BODY = """Migrated the 14 cron jobs to the new scheduler; tests green. Nothing needed — review when you're back."""

repo, branch, session, state_dir, label, link = sys.argv[1:7]
envelope = {"title": TITLE, "body": BODY, "level": LEVEL, "repo": repo, "cwd": os.getcwd()}
if label:
    envelope["session_label"] = label
if branch:
    envelope["branch"] = branch
if link and link not in BODY:
    envelope["body"] = (BODY.rstrip() + "\n" + link).strip()
if session:
    envelope["session"] = session[:8]
    path = os.path.join(state_dir, re.sub(r"[^A-Za-z0-9_-]", "-", session)[:80] + ".json")
    try:
        with open(path) as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        state = {}
    if isinstance(state, dict) and state.get("thread"):
        envelope["thread"] = state["thread"]
print(json.dumps(envelope))
PY
) || { echo "ping NOT delivered — notify-send.sh failed, see its stderr above" >&2; exit 1; }

python3 - "$SESSION" "$STATE_DIR" "$REPLY" <<'PY'
import json, os, re, sys, time

session, state_dir, reply = sys.argv[1:4]
if not session:
    raise SystemExit(0)
try:
    thread = json.loads(reply or "{}").get("thread")
except ValueError:
    thread = None
path = os.path.join(state_dir, re.sub(r"[^A-Za-z0-9_-]", "-", session)[:80] + ".json")
try:
    with open(path) as handle:
        state = json.load(handle)
except (OSError, ValueError):
    state = {}
if not isinstance(state, dict):
    state = {}
state["armed_at"] = time.time()
if thread:
    state["thread"] = thread
os.makedirs(state_dir, exist_ok=True)
with open(path, "w") as handle:
    json.dump(state, handle)
PY
```

Three things that block are worth understanding rather than copying:

- **Reading the thread first** is what makes the ping land in the same conversation as this session's other notifications instead of starting a new one. The state file may not exist — no notification has fired on this machine yet, or not for this session. That is the normal case, not an error: an unreadable or absent file means no thread, and the ping goes out unthreaded.
- **Writing the thread back is read-modify-write.** The file also holds `last_sent` and `last_kind`, which the `notify.py` hook owns. Overwriting the file with `{"thread": ...}` alone would drop the hook's rate-limit state. Load, set one key, dump. Create `notify-state/sessions/` if it is missing.
- **`armed_at` is written whether or not a thread came back**, which is why it sits outside the `if thread:` branch. A transport that cannot thread returns no id, and arming the session is the more important of the two jobs — gating it on a thread id would silently leave the session muted on exactly the machines where threading is unavailable.

## What a Ping Opts Into

Sending the message is half of what this skill does. The other half is **arming the session**: `armed_at` in the session state is what switches the automatic `notify.py` notifications on for this session and nothing else.

Automatic notifications are off by default in every session. That is deliberate — a hook that fires on every turn over a minute is indistinguishable from no notifications at all once a dozen sessions are live, because the user stops reading them. So the user opts a session in by asking for a ping, which is the same gesture as saying "I am walking away from this one".

What that means in practice:

- **Before any ping**, the session is silent. `notify.py` logs `skip: session not armed` and sends nothing, however long the turn ran or however stuck it got.
- **After a ping**, that session notifies on the events its config enables — finishing a turn, needing permission, needing a decision, failing. No turn-length floor applies, because the user already said they are not at the keyboard.
- **Arming persists until the user switches it off.** It is a latch, not a timer. Only `/ping off` clears it (Step 0). Nothing else does — not the next prompt, not `back`, not time passing, not the session going idle.
- **Arming is per-session, never global.** Three sessions running and a ping from one of them opts in only that one. The global override is `away`, which is a different gesture with different semantics — it notifies for everything everywhere.

**Never infer that the user has come back.** Answering in chat and then walking away again is the normal case, not the exception, so a prompt arriving is not evidence they are at the keyboard for the rest of the run. Guessing wrong here is expensive and silent: the session goes quiet exactly when the user is relying on it, and nothing reports that it did. The latch is the user's to clear, never this skill's and never the hook's.

A ping is therefore never only a message. Sending one commits this session to notifying the user until they say stop, which is another reason the body has to say what the session is doing: it is the first of a series, not a one-off.

## Answering From the Phone

A ping tells the user something. **Remote Control** is what lets them do something about it: it forwards the live session to claude.ai and the Claude app, where a blocking permission prompt or an `AskUserQuestion` can be answered from a phone instead of from the terminal. Every session here connects at startup — `remoteControlAtStartup` is `true` in the profile's `settings.json` — so by the time a ping goes out, the session is normally already reachable.

**This skill does not arm that, and cannot.** Remote Control is established by the `/remote-control` slash command or at startup, and a slash command is typed by the user: an agent has no way to run one in its own session. Nor can it read the connection state back. Three rules follow:

- **Never claim the session is answerable from the phone.** The startup setting is the reason it usually is, not evidence that it is this time — a box with no claude.ai login, a gateway `ANTHROPIC_BASE_URL`, or an org policy toggle starts without it and says nothing.
- **Never put "run `/remote-control`" in a ping.** The ping that matters most is the one a long `autopilot` run sends hours after the user walked away, where nothing printed in the terminal will be read. An instruction they cannot see is worse than none: in the run report it reads as though it had been followed.
- **`/ping off` disconnects nothing.** Step 0 clears `armed_at` and stops the automatic notifications, and stops there. The connection was never this skill's to make, so it is not this skill's to break — and dropping it would cut off a session the user may still be driving from their phone. They toggle it with `/remote-control` when they want it gone.

The two channels are separate on purpose. The notification says *come and look*; the connection is *how you act on it*. Nothing about a ping depends on the connection being up, and nothing about the connection depends on a ping having been sent.

## Step 5: Say What Happened

Report in chat, in one line: the level, and that it went out. If the send failed, print the exact stderr from `notify-send.sh` — do not paraphrase it and do not swallow it. The usual cause is `~/.claude/notify.json` being absent or still full of `REPLACE_ME`, and the message says so. A ping the user never receives is worse than an error, because they will keep waiting for it.

## When Another Skill Calls You

Other skills reach this one through the `Skill` tool rather than by re-implementing the send. When they do:

- **The calling skill supplies the context.** It knows what it was doing; this skill does not. Pass the level and a body that already answers "what about, and what's needed" — for example `/ping blocked the review pipeline needs a manual approval on the deploy stage`.
- A bare invocation with no context from a calling skill produces a vague ping. If you are the caller and cannot say what the ping is about, you are not ready to send one.
- This skill sends exactly one notification per invocation and returns. It never loops, waits, or polls for a reply — the notification is one-way by design and nothing comes back through it. The user answers by taking the session over from their phone, which arrives here as an ordinary prompt over Remote Control rather than as a reply to the ping.

## Important Rules

- **Never send a body without context.** "Done", "Finished", "Task complete" are failures. State what the work was and what is needed.
- **Never exceed 68 words.** A notification that has to be opened and scrolled has failed at the one job it has. Over budget means cut, never means send anyway.
- **Never say what is or is not needed unless you know.** If the user has to do something, name it. If they do not, say so explicitly — "nothing needed" is information.
- **Never name the transport.** Say "your phone" or nothing. The transport is a per-machine detail of `notify-send.sh` and this skill is identical on every machine.
- **Never build the envelope with shell string concatenation.** Prose contains quotes, apostrophes, backticks and newlines. `json.dumps` handles all of them; `echo "{\"body\": \"$BODY\"}"` does not.
- **An explicit ping bypasses the gates deliberately.** `notify.py`'s `min_turn_seconds`, `min_interval_seconds`, quiet hours and subagent suppression exist to stop *automatic* notifications from becoming noise across a dozen live sessions. A ping the user asked for is never noise, so this skill calls the sender directly and none of those gates apply. It still depends on `~/.claude/notify.json` being configured — that is the one thing it cannot route around.
- **Never arm a session without sending.** The arming and the message are one gesture; writing `armed_at` after a failed send would leave the session opted in to notifications the user has no reason to expect, having just been told the ping did not go out. The write-back runs only on the success path, which is what the `||` bail-out above protects.
- **Never fail silently.** Non-zero exit from `notify-send.sh` gets reported in chat with its stderr intact.
- **One ping per request.** If the user wants to be told again later, they will ask again, or a longer-running skill will call this one again at its own checkpoint.
