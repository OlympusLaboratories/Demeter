---
name: ping
description: Send the user a deliberate push notification on their phone, carrying what this session is working on and what it needs from them. Use when the user says ping me, ping me when you're done, ping me if anything comes up, let me know when that finishes, let me know if you get stuck, tell me when you need something, notify me, text me — or invokes /ping. Also used by other skills that need to hand a status update, a question, a blocker or a finished run to the user while they are away from the terminal.
---

# Ping — Tell the User Something, On Their Phone

Send one notification to the user's phone through the configured transport. The point is not that a message arrives — it is that the user can read it on a lock screen and know, without opening a laptop, **what this session was doing** and **whether it needs them**. A ping that says "done" wastes the only sentence you get.

The transport (and its credentials) live in `~/.claude/scripts/notify-send.sh` and `~/.claude/notify.json`. Never name or assume a transport in anything you write — say "your phone" if you have to say anything at all.

**Parameter:** `$ARGUMENTS` — an optional level word, plus an optional note about what to say. Both may be absent.

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

The body is **one or two short lines** and must answer both of these:

1. What was this session working on?
2. What does it need from the user — or does it need nothing?

Take the context from the session, never from imagination. If the work cannot be described in a line, that is a signal the line is too vague, not that the line should be longer. Only the first ~140 characters reach a lock screen, so put the answer first and detail second.

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
REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
BRANCH=$(git branch --show-current 2>/dev/null)
SESSION="${CLAUDE_CODE_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
echo "repo=$REPO branch=$BRANCH session=${SESSION:0:8}"
```

- `REPO` always resolves. Outside a git repo it falls back to the directory name — a ping must never fail because the cwd is not a checkout.
- `BRANCH` is empty on a detached HEAD or outside a repo. Omit the field rather than sending an empty string.
- `SESSION` is set in a Claude Code session. Only its first 8 characters go in the envelope. If it is empty, omit the field and skip the thread state entirely.

## Step 4: Send It

Build the JSON with `python3` — never by concatenating shell variables, because the body is prose and one apostrophe or newline would produce an envelope the sender rejects. The heredoc is quoted (`<<'PY'`), so nothing in the title or body is expanded by the shell.

Fill in `LEVEL`, `TITLE` and `BODY` from Steps 1 and 2, then run the whole block as one command — the thread id has to be captured and written back in the same shell.

```bash
set -o pipefail
REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
BRANCH=$(git branch --show-current 2>/dev/null)
SESSION="${CLAUDE_CODE_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
STATE_DIR="$HOME/.claude/notify-state/sessions"

REPLY=$(python3 - "$REPO" "$BRANCH" "$SESSION" "$STATE_DIR" <<'PY' | "$HOME/.claude/scripts/notify-send.sh" send
import json, os, re, sys

LEVEL = "stop"
TITLE = """demeter finished"""
BODY = """Migrated the 14 cron jobs to the new scheduler; tests green. Nothing needed — review when you're back."""

repo, branch, session, state_dir = sys.argv[1:5]
envelope = {"title": TITLE, "body": BODY, "level": LEVEL, "repo": repo, "cwd": os.getcwd()}
if branch:
    envelope["branch"] = branch
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
import json, os, re, sys

session, state_dir, reply = sys.argv[1:4]
if not session:
    raise SystemExit(0)
try:
    thread = json.loads(reply or "{}").get("thread")
except ValueError:
    thread = None
if not thread:
    raise SystemExit(0)
path = os.path.join(state_dir, re.sub(r"[^A-Za-z0-9_-]", "-", session)[:80] + ".json")
try:
    with open(path) as handle:
        state = json.load(handle)
except (OSError, ValueError):
    state = {}
if not isinstance(state, dict):
    state = {}
state["thread"] = thread
os.makedirs(state_dir, exist_ok=True)
with open(path, "w") as handle:
    json.dump(state, handle)
PY
```

Two things that block are worth understanding rather than copying:

- **Reading the thread first** is what makes the ping land in the same conversation as this session's other notifications instead of starting a new one. The state file may not exist — no notification has fired on this machine yet, or not for this session. That is the normal case, not an error: an unreadable or absent file means no thread, and the ping goes out unthreaded.
- **Writing the thread back is read-modify-write.** The file also holds `last_sent` and `last_kind`, which the `notify.py` hook owns. Overwriting the file with `{"thread": ...}` alone would drop the hook's rate-limit state. Load, set one key, dump. Create `notify-state/sessions/` if it is missing.

## Step 5: Say What Happened

Report in chat, in one line: the level, and that it went out. If the send failed, print the exact stderr from `notify-send.sh` — do not paraphrase it and do not swallow it. The usual cause is `~/.claude/notify.json` being absent or still full of `REPLACE_ME`, and the message says so. A ping the user never receives is worse than an error, because they will keep waiting for it.

## When Another Skill Calls You

Other skills reach this one through the `Skill` tool rather than by re-implementing the send. When they do:

- **The calling skill supplies the context.** It knows what it was doing; this skill does not. Pass the level and a body that already answers "what about, and what's needed" — for example `/ping blocked the review pipeline needs a manual approval on the deploy stage`.
- A bare invocation with no context from a calling skill produces a vague ping. If you are the caller and cannot say what the ping is about, you are not ready to send one.
- This skill sends exactly one notification per invocation and returns. It never loops, waits, or polls for a reply — notifications here are one-way by design, and nothing the user does on their phone comes back into this session.

## Important Rules

- **Never send a body without context.** "Done", "Finished", "Task complete" are failures. State what the work was and what is needed.
- **Never say what is or is not needed unless you know.** If the user has to do something, name it. If they do not, say so explicitly — "nothing needed" is information.
- **Never name the transport.** Say "your phone" or nothing. The transport is a per-machine detail of `notify-send.sh` and this skill is identical on every machine.
- **Never build the envelope with shell string concatenation.** Prose contains quotes, apostrophes, backticks and newlines. `json.dumps` handles all of them; `echo "{\"body\": \"$BODY\"}"` does not.
- **An explicit ping bypasses the gates deliberately.** `notify.py`'s `min_turn_seconds`, `min_interval_seconds`, quiet hours and subagent suppression exist to stop *automatic* notifications from becoming noise across a dozen live sessions. A ping the user asked for is never noise, so this skill calls the sender directly and none of those gates apply. It still depends on `~/.claude/notify.json` being configured — that is the one thing it cannot route around.
- **Never fail silently.** Non-zero exit from `notify-send.sh` gets reported in chat with its stderr intact.
- **One ping per request.** If the user wants to be told again later, they will ask again, or a longer-running skill will call this one again at its own checkpoint.
