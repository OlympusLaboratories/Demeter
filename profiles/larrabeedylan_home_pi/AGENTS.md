# larrabeedylan_home_pi — Agent Instructions

The profile for the Raspberry Pi app host (`piserver`). It installs as the `jarvis`
service user, so that the Claude Code Remote Control server — the thing the Claude
mobile app connects to — spawns phone sessions that have the same skills as a
laptop session.

`install.sh` resolves this box as machine type **`pi`**, not `linux`, because
`/etc/rpi-issue` exists. That distinction is the whole reason the type was added:
`SKIP_LIST` is keyed by machine, and the Pi and the rdev box are both Linux while
needing opposite treatment.

## What this profile deliberately does not contain

Three things are absent on purpose, and each would cause a silent failure if added.

### No `settings.json`

`~/.claude/settings.json` on the Pi is owned by the **Gaia** repo, which merges two
key paths into it and leaves the rest alone: `permissions.defaultMode` (set to
`bypassPermissions`, because the `--permission-mode` flag does not reach spawned
sessions on 2.1.245) and one `hooks.PreToolUse` entry registering the hook that
refuses the Artifact tool, so pages publish to this Pi rather than to claude.ai.

Demeter symlinks `settings.json` **wholesale**, and `link_file` under `-y` answers
"back up and replace" with yes. Linking it here would therefore drop phone sessions
back to `auto` permissions — where reads pass and the first real write returns
"Blocked by classifier" — and hand them the Artifact tool back.

The second failure is worse because it is invisible. A symlinked `settings.json`
means `/config` and Gaia's own merge scripts write **into the Demeter clone** on the
Pi. That leaves the tree dirty, and `repos-sync` only fast-forwards a clean tree, so
the automatic update stops and reports nothing.

Demeter's hooks still have to be registered. Gaia does it with a separate merge
script, one owner per key — the same arrangement its other two setup scripts use.

`permissions.allow` is not merged either. These sessions run in `bypassPermissions`,
where an allowlist is moot.

### No user-level `CLAUDE.md`

`~/.claude/CLAUDE.md` does not exist on the Pi, so nothing would be overwritten —
but the slot is **global to the `jarvis` user**, and `jarvis` runs three Claude Code
consumers, not one: the Remote Control server, the voice agent, and the nightly
vault organize pass. Gaia's `AGENTS.md` states that the voice agent's prompt surface
is attacker-reachable, through an unauthenticated webhook, a Telegram message, and
notes synced in from Drive, and that its tool list is a security boundary rather than
an ergonomic setting.

Instructions meant for phone sessions belong in `/home/jarvis/remote-root/CLAUDE.md`,
which is project-scoped and loads only for them. Gaia owns that file.

### No dotfiles

`jarvis` has no interactive shell. The shared `shell/` step is skipped for the same
reason, along with the terminal-tool prompts it would raise.

## What it does install

| | |
| --- | --- |
| Skills | all of them, linked per-directory into `~/.claude/skills/` |
| Hooks | `notify.py` and `link-worktree-session.py`, linked into `~/.claude/hooks/` |
| Scripts | `github-api.sh`, `notify-send.sh`, `skill-env.sh`, `workflow-runs.py` |
| `environment.json` | seeded from this profile's example when absent |
| `notify.json` | seeded from this profile's example, mode 600, and **live immediately** — it references credentials this box already has |
| `git/ignore` | linked, as on every machine |

A user-level skills directory is the **only** route in. `claude remote-control` is
one server for one directory, and flags passed to it do not reach the sessions it
spawns — verified for `--permission-mode` and assumed for the rest of that family.
So anything a phone session must see arrives through `~/.claude/skills/`,
`~/.claude/settings.json`, a `CLAUDE.md` inside `remote-root/`, or a path physically
nested under `remote-root/`.

Linking skills is additive and per-directory, so the `publishing-artifacts` skill
Gaia installs is left exactly where it is. No name collides.

## The three symlinks, and why they are not copies

`skills/`, `hooks/` and `scripts/` are symlinks to the
`larrabeedylan_home_darwin` profile's copies.

Every other pair of profiles here differs by a **transform** — the nine
substitutions that turn a work skill into its home counterpart — and `cmp
transform(work) home` is what makes drift in that pair detectable. Home and the Pi
differ by the *identity* transform: same forge, same change-request vocabulary, same
reviewer arrangement. A fourth byte-identical copy would therefore add a drift
surface with nothing to check it against, and the first divergence would be a typo
nobody notices.

A symlink cannot drift. If the Pi ever does need its own copy of a skill, replacing
the symlink with a real directory is a deliberate, visible act rather than an edit
that happens to land in one of four places.

The two `.json.example` files are real files, because they are the only things that
genuinely differ — see below.

## The two example files, and why each one differs

`artifact_store` is pinned to **`mnemosyne`** rather than left on `auto`. On every
other machine `auto` is right because it probes mnemosyne, then the Artifact tool,
then writes a local file. Here the Artifact tool is refused by a hook, so it is not a
fallback — naming the store directly is what keeps a skill from treating a refusal as
a transport problem.

`iac_bot`, `review_bots` and `review_job` are **empty here and filled in on the
box.** This repository is public, so the reviewer's and the infrastructure bot's
account names do not belong in a committed example — Gaia's `setup-demeter.sh`
merges them into `~/.claude/environment.json` after the installer seeds it, and
skips any key that already has a value.

That split matters for one reason beyond tidiness: an empty `iac_bot` disables
the apply-before-merge gate **outright**, and Gaia is planned and applied by
Atlantis on the pull request with no push-to-`main` trigger at all. A phone
session that merged a `.tf` change before the apply would leave the repository
claiming infrastructure that does not exist. So the gate is not optional on this
box, and a Pi whose `environment.json` still has those keys empty has not had
`setup-demeter.sh` run against it.

### `notify.json.example` references the credential instead of carrying it

The Pi already holds the notification bot's token and chat id in its own files,
for its own alerting, so this profile's example points at them with
`bot_token_file` and `chat_id_file` rather than keeping a second copy. The `_file`
forms are read only when the direct key is empty, so there is one owner per
credential and nothing to rotate twice.

The consequence is that notifications here are **live on the first install**,
where every other profile ships a `REPLACE_ME` template and stays dormant until
somebody pastes a token. That is not a weakening of the "ships switched off"
rule: `only_when_armed` is `true`, so a session is silent until a `/ping` arms it,
which is the gate that actually matters.

## When changing this profile

- Nothing here may name a transport. The Slack/Telegram split lives in
  `notify-send.sh`, which is why the `ping` skill is byte-identical everywhere.
- The `pi` machine type and its `SKIP_LIST` entries are in `install.sh`. A new
  VS Code step added to the installer needs `should_skip "vscode"` or an entry of
  its own, or it will fire on a box with no editor.
- The Pi side of this — the systemd timer that pulls Demeter and re-runs the
  installer, and the hook-registration merge — lives in Gaia under
  `bare-metal/piserver/bootstrap/demeter/`. Changing what this profile installs may
  mean changing that too.
- **The five `:pi` skip entries are bare basenames, so they are reserved names
  here.** `should_skip` matches a filename with no notion of which step asked, and
  it is consulted by both `.claude/` loops as well as `link_directory_contents`. A
  skill, hook or script named `vscode`, `shell`, `tools`, `settings.json` or
  `CLAUDE.md` would therefore be dropped on the Pi and nowhere else, with only a
  warning in a log nobody reads.
- **A name that collides with a skill Gaia installs is not benign.** Linking is
  additive and nothing collides today, but `link_file` on a real directory asks
  "back up and replace?", which under `-y` is answered yes — so a future Demeter
  skill named `publishing-artifacts` would move Gaia's aside to a `.bak` and warn
  rather than fail.
