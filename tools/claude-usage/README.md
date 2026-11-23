# Claude Usage

Puts your Claude quota in the VS Code status bar, so you stop having to run the
usage skill to find out how close you are to a limit.

```
Session ●●○○○○ 33% 1h20m   Weekly ●●●○○○ 53% 5d20h   ⟳ now
```

```
✨   Session ●●○○○○ 33% 1h20m   Weekly ●●●○○○ 53% 5d20h   ⟳ now
```

The button on the left opens a new Claude Code chat as a tab in its own locked
editor group — see [The new-chat button](#the-new-chat-button).

Each meter is a separate status bar item: a label, a bar, the percentage used,
and how long until that window resets. The 5-hour session window and the 7-day
window are shown by default; per-model weekly windows and extra-usage spend are
available too. Set `claudeUsage.labelStyle` to `short` for `5h` / `7d` / `$` if
you want the room back.

The chip on the end says how old the reading is, and turns into a warning when
something is wrong:

```
Session ●●○○○○ 33% 1h20m   Weekly ●●●○○○ 53% 5d20h   ⟳ 45s
Session ●●○○○○ 33% 1h20m   Weekly ●●●○○○ 53% 5d20h   ⚠ 6m
Session ●●○○○○ 33% 1h20m   Weekly ●●●○○○ 53% 5d20h   ⚠ 4m · retry 2m
```

A reading more than 2.5 poll intervals old goes yellow, so a percentage that has
quietly stopped moving is obvious rather than silently wrong. While a rate-limit
backoff is in effect the chip shows how long until the next attempt. Set
`claudeUsage.age` to `whenStale` to hide it while everything is healthy, or
`never` to drop it (the tooltip still carries the same information).

Staleness is deliberately kept off the meters themselves: their colour is
reserved for how much quota you have used, and the reset countdowns stay correct
even on a stale reading, because reset times are absolute.

## Where the numbers come from

`GET https://api.anthropic.com/api/oauth/usage`, the same endpoint the Claude
Code CLI reads for `/usage`. The response's `limits` array is the source of
truth (`session`, `weekly_all`, `weekly_scoped`); the older `five_hour` /
`seven_day` fields are used as a fallback if `limits` ever disappears.

## Signing in

Two credential sources, picked by `claudeUsage.credentials`:

- **`claudeCode`** — read the token Claude Code already stores. On macOS that is
  the login keychain item `Claude Code-credentials`; elsewhere it is
  `~/.claude/.credentials.json`. `CLAUDE_CODE_OAUTH_TOKEN` wins over both. This
  is **read-only**: the extension never writes to that store and never refreshes
  that token, so it cannot knock Claude Code out of its own session.
- **`browser`** — the extension's own OAuth login. It opens your real default
  browser with `vscode.env.openExternal` (never a webview or popup, so Okta SSO
  behaves), listens on a throwaway `http://localhost:<port>/callback` for the
  redirect, and exchanges the code with PKCE. Tokens go in VS Code's
  `SecretStorage` and the extension refreshes them itself.

The default, **`auto`**, uses the Claude Code login whenever it has an unexpired
token and falls back to the browser login otherwise.

Claude Code's access token lasts about 24 hours. In `claudeCode` mode an expired
token is not an error the extension can fix — it clears itself the next time you
use Claude Code, which refreshes it. If you would rather not depend on that, run
**Claude Usage: Sign In With Browser** once and the extension will keep its own
token alive for as long as the refresh token lives (about 30 days).

If the loopback redirect never arrives — a remote workspace, a browser that
cannot reach your machine — the extension offers the copy-paste flow instead:
it reopens the browser against Anthropic's manual redirect page and asks you to
paste the code it shows.

### A note on the macOS keychain

The first time the extension shells out to `security` to read
`Claude Code-credentials`, macOS may ask whether VS Code should be allowed to
read that item. Choose **Always Allow** and you will not be asked again. Deny it
and `auto` mode quietly falls back to the browser login.

## Polling, and why it is one request no matter how many windows you have

Every `claudeUsage.pollSeconds` (default 60) while the numbers are moving, and
immediately when the window regains focus. Timer polls are skipped entirely while the window is unfocused,
so a backgrounded editor makes no requests. Failures back off exponentially from
1 minute to 15 minutes, and a `429` honours `Retry-After`. The reset countdowns
re-render every 30 seconds without hitting the network.

You are not the only thing reading this endpoint. Claude Code itself polls
`/api/oauth/usage` from **every running session** — that is where its own
`/usage` numbers come from — and the rate limit is per account, so the CLI and
this extension spend the same budget. Two things keep this extension's share
small.

**It only asks when the answer can have changed.** Your quota moves when you are
running Claude and is perfectly flat when you are not, so a fixed one-minute poll
spends most of its requests re-reading identical numbers. Each reading is
compared with the one before it; after `claudeUsage.steadyAfter` identical
readings in a row (default 2) the interval doubles each time, up to
`claudeUsage.idlePollSeconds` (default 600). Any movement in any percentage
resets it to `claudeUsage.pollSeconds` immediately.

```
identical readings:  0     1     2      3      4      5+
interval:           60s   60s   120s   240s   480s   600s
```

So an idle editor settles at one request per ten minutes, while an editor where
you are actively burning quota stays at one a minute. The tooltip says which rate
is in force. Set `idlePollSeconds` equal to `pollSeconds` to switch this off and
poll at a fixed rate.

**Easing off never delays a reset.** The countdowns do not need the network at
all: `resets_at` is an absolute timestamp, so the time remaining is recomputed
locally and stays exact no matter how slow the polling is. Only the percentage
goes stale. But the reset itself matters — that is the moment the percentage
drops and a new window opens, and it is exactly when you are watching — so the
next poll is never scheduled past the soonest reset. However relaxed the pacing
has become, a window resetting in three minutes is fetched in three minutes, not
in ten. Inside the last two minutes the display also ticks every second rather
than every ten, so the final countdown runs smoothly:

```
Session ●●●●●● 100% 1m     one fetch, then
Session ●●●●●● 100% 35s    rendered locally
Session ●●●●●● 100% 5s     no network
Session ●●●●●● 100% now    → poll fires here, new window picked up at once
```

**And it asks once for all of your windows.** Every editor window runs its own copy of the extension, so without coordination
six open windows would mean six requests a minute — enough to get rate limited,
which is exactly what happened the first time this shipped. Instead the windows
share one reading through a small cache on disk:

- `~/Library/Caches/claude-usage/usage.json` on macOS,
  `$XDG_CACHE_HOME/claude-usage/` on Linux, `%LOCALAPPDATA%\claude-usage\` on
  Windows. One location per user, not per editor installation, so VS Code,
  Insiders and VSCodium all share it. Override it with `CLAUDE_USAGE_CACHE_DIR`.
- A window that finds a reading younger than its poll interval renders it and
  makes no request at all.
- When a reading *is* due, windows race for an exclusive lock file. One wins and
  fetches; the rest read what it wrote. A lock left behind by a crashed window is
  broken after 60 seconds.
- The winner's write is picked up by every other window through a directory
  watch, so they all update together rather than drifting a minute apart. That
  watch is best effort — `fs.watch` is silently useless on some filesystems, and
  Linux refuses new watches once `fs.inotify.max_user_watches` is exhausted — so
  it is backed by a cheap `stat` of the cache file every few seconds. Delivery is
  guaranteed by the `stat`; `fs.watch` only makes it instant.
- Rate-limit backoff is shared too: one window's `429` parks all of them until
  the retry time, instead of each discovering the limit separately.

Only percentages and reset times go in that file — never a token. Poll timers
carry a small random jitter so windows opened together do not stay in lockstep.

**Claude Usage: Refresh Now** always makes a real request, bypassing the cache,
except while a shared rate-limit backoff is in effect.

## Settings

| Setting | Default | What it does |
| --- | --- | --- |
| `claudeUsage.enabled` | `true` | Show the meters at all. |
| `claudeUsage.pollSeconds` | `60` | Refresh interval while readings keep changing, minimum 15. |
| `claudeUsage.idlePollSeconds` | `600` | Slowest interval, used once readings go steady. Equal to `pollSeconds` disables easing off. |
| `claudeUsage.steadyAfter` | `2` | Identical readings in a row before easing off starts. |
| `claudeUsage.credentials` | `auto` | `auto`, `claudeCode`, or `browser`. |
| `claudeUsage.show` | `["session","weekly"]` | Any of `session`, `weekly`, `scoped`, `spend`. |
| `claudeUsage.newChatButton` | `true` | Show the new-chat button to the left of the meters. |
| `claudeUsage.newChatIcon` | `sparkle` | Codicon on that button, without the `$()` wrapper. |
| `claudeUsage.labelStyle` | `long` | `long` gives `Session`/`Weekly`/`Credits`, `short` gives `5h`/`7d`/`$`. |
| `claudeUsage.age` | `always` | `always`, `whenStale`, or `never` for the age chip. |
| `claudeUsage.barWidth` | `6` | Cells per bar; `0` drops the bar and keeps the percentage. |
| `claudeUsage.barStyle` | `dots` | `dots` `●●○○`, `squares` `■■□□`, `bars` `▮▮▯▯`, `blocks` `██░░`, `shaded` `▰▰▱▱`, `line` `━━──`, `ascii` `##--`. |
| `claudeUsage.showReset` | `true` | Append the time until the window resets. |
| `claudeUsage.warnAtPercent` | `75` | Turn the meter yellow at or above this. |
| `claudeUsage.criticalAtPercent` | `90` | Turn it red at or above this. |
| `claudeUsage.alignment` | `right` | Which side of the status bar. |
| `claudeUsage.priority` | `100` | Higher sits further left within that side. |

A meter is never quieter than the API says: if Anthropic reports a window as
`warning` or `critical`, that wins over your thresholds.

## Choosing a bar style

The status bar is drawn in the editor's **UI font**, not a monospace font, and
that font decides how a bar looks. `blocks` (`██░░░░`) was the original default
and is a good example of the trap: SF Pro carries no block elements, so `█` and
`░` each fall back to a *different* font — the filled cells merge into one slab
while the empty ones arrive as outlined boxes, at mismatched widths. The default
is now `dots`, because circles are drawn by essentially every UI font, so all six
cells come from one font at one width.

Which one looks best still depends on your font and zoom level, and the README
cannot tell you. Run **Claude Usage: Choose Bar Style** and move through the
list: each option previews live in the real status bar, and Enter keeps it.

## The new-chat button

To the left of the meters sits a one-glyph button that opens a **new** Claude
Code chat session as a tab in its own **locked** editor group, which is the
layout that makes a chat usable side by side with code: a locked group refuses
to host anything else, so clicking a file in the explorer opens it in your code
group instead of replacing the chat.

It drives the Claude Code extension's own `claude-vscode.editor.open` command,
so the session is an ordinary Claude Code tab — same history, same
`Claude Code: Reopen Closed Session`, same everything. Claude Code puts the tab
beside your code, reusing the column that already holds Claude tabs if there is
one, and this extension then locks that group itself rather than relying on
Claude Code's `claudeCode.lockEditorGroups` setting, so the button behaves the
same whichever way that is set.

The button is hidden by `claudeUsage.newChatButton: false`, and by
`claudeUsage.enabled: false` along with everything else. Without the Claude Code
extension in the window there is nothing to open, and clicking says so.

`claudeUsage.newChatIcon` takes any [codicon](https://microsoft.github.io/vscode-codicons/dist/codicon.html)
name — `sparkle` by default, `comment-discussion`, `add` and `robot` are the
other obvious ones. Unlike the bars, this is a codicon rather than a text glyph,
so it comes from VS Code's own bundled font and cannot fall back to a mismatched
one.

## Commands

- **Claude Usage: Refresh Now** — also what clicking a meter does.
- **Claude Usage: New Claude Chat in a Locked Group** — what the button does.
- **Claude Usage: Choose Bar Style** — live preview of each bar style.
- **Claude Usage: Sign In With Browser**
- **Claude Usage: Sign Out (Forget Browser Login)** — clears only this
  extension's tokens; Claude Code's login is untouched.
- **Claude Usage: Show Details** — the output channel.

Hovering a meter shows every window with its absolute reset time, which
credential source is in use, and how old the reading is.

## Development

```sh
make check      # typecheck + tests + build
make install    # package and install into VS Code
make link       # symlink into ~/.vscode/extensions for live iteration
```

The repo installer offers `make install` for this directory automatically, so a
fresh machine picks it up from `./install.sh`.

---

## Constraints an edit here must respect

Four of these are not discoverable from the code: the credential is read-only because
writing it would log the user out of Claude Code, the usage endpoint's rate limit is
shared with the user's own CLI sessions, the status bar renders in the UI font rather
than a monospace one, and the new-chat button drives another extension's contributed
command rather than an API.

### Claude credentials

`tools/claude-usage/` reads the OAuth token Claude Code stores (macOS keychain item `Claude Code-credentials`, else `~/.claude/.credentials.json`) **read-only** — it must never write to or refresh that token, because a rotated refresh token there would log the user out of Claude Code. Anything needing a token it owns does its own PKCE login and keeps it in VS Code `SecretStorage`. Usage comes from `https://api.anthropic.com/api/oauth/usage` with an `anthropic-beta: oauth-2025-04-20` header; prefer the response's `limits[]` array over the older `five_hour`/`seven_day` fields

### Shared rate limit on `/api/oauth/usage`

the Claude Code CLI polls this endpoint from every running session, and the limit is per account — so anything else reading it (`tools/claude-usage/`) competes with the user's own CLI sessions and must be frugal, not merely cached. Poll adaptively: compare each reading with the last and ease off geometrically while the numbers are flat, snapping back when they move. A fixed interval spends nearly all its requests re-reading identical numbers. Two things must survive that easing off: `resets_at` is absolute, so countdowns are recomputed locally and need no fetch, and the next poll must never be scheduled past the soonest reset — that is the instant the quota frees up and the user is watching it

### One extension, many windows

every editor window loads its own copy of an extension, so anything polling a network endpoint must coordinate or it multiplies by the window count — `tools/claude-usage/` got rate limited this way. It now shares one reading through a lock file plus a JSON cache in the user's cache dir (`~/Library/Caches/claude-usage/`, `$XDG_CACHE_HOME/claude-usage/` on Linux), watched by every window so they update together. Keep that cache per-user rather than per-editor-installation, never put credentials in it, and share backoff state through it as well as data

### Browser OAuth

any login flow here opens the system browser via `vscode.env.openExternal`, never a webview or popup — Okta SSO misbehaves in embedded browsers. Pair it with a loopback `http://localhost:<ephemeral>/callback` listener, and keep the copy-paste fallback for when the redirect can't reach the machine

### Status bar glyphs

the VS Code status bar renders in the **UI font** (SF Pro on macOS), not a monospace font, so a glyph the UI font lacks falls back per-character and neighbouring cells end up from different fonts at different widths — block elements (`█` U+2588, `░` U+2591) mismatch badly this way. Prefer geometric shapes UI fonts actually carry (`●○`, `■□`); when a look depends on the user's font, ship a picker that previews live rather than guessing

### Driving another extension's commands

`tools/claude-usage/`'s new-chat button runs the Claude Code extension's `claude-vscode.editor.open`, which is a contributed command and not API — it can be renamed or absent, and `executeCommand` on a missing id rejects with a raw `command 'x' not found`. Probe `vscode.commands.getCommands(true)` first and say something useful instead. Claude Code locks the new group **itself**, but only when that call created a new column *and* `claudeCode.lockEditorGroups` is on, so claude-usage locks unconditionally afterwards and tolerates the failure — `workbench.action.lockEditorGroup` sets the flag rather than toggling it, and its `activeEditorGroupLocked` precondition gates menus and keybindings, not `executeCommand`. The group it locks only ever holds Claude tabs, because Claude Code opens `ViewColumn.Beside` or reuses a column that already has one. Status bar priority is "higher sits further left" on **both** sides, so the button is `priority + 1` while the meters are `priority - index`
