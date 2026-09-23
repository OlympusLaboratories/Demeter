# Claude Usage

Puts your Claude quota in the VS Code status bar, so you stop having to run the
usage skill to find out how close you are to a limit.

```
Session ●●○○○○ 33% 1h20m   Weekly ●●●○○○ 53% 5d20h   ⟳ now
```

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

Every `claudeUsage.pollSeconds` (default 60), and immediately when the window
regains focus. Timer polls are skipped entirely while the window is unfocused,
so a backgrounded editor makes no requests. Failures back off exponentially from
1 minute to 15 minutes, and a `429` honours `Retry-After`. The reset countdowns
re-render every 30 seconds without hitting the network.

Every editor window runs its own copy of the extension, so without coordination
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
  watch, so they all update together rather than drifting a minute apart.
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
| `claudeUsage.pollSeconds` | `60` | Refresh interval, minimum 15. |
| `claudeUsage.credentials` | `auto` | `auto`, `claudeCode`, or `browser`. |
| `claudeUsage.show` | `["session","weekly"]` | Any of `session`, `weekly`, `scoped`, `spend`. |
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

## Commands

- **Claude Usage: Refresh Now** — also what clicking a meter does.
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
