# Demeter — Shared Dotfiles

## Project Overview

Demeter is a shared dotfile repo. Each machine setup lives in its own profile directory under `profiles/`. An interactive install script symlinks everything to the right places on any machine (macOS or Linux).

## Repo Structure

```
Demeter/
  install.sh              # Interactive symlink installer (idempotent)
  uninstall.sh            # sweeps every declared link root; -y answers prompts
  .github/
    workflows/
      ai-review.yml       # Hephaestus AI review on every PR
      check-transform.yml # profile drift check, on any PR touching profiles/
      shell-checks.yml    # shellcheck + tests/, on any PR touching the scripts
  _starter/               # Template for new contributors — copy to get started
    .bash_profile
  _vendor/                # Vendor packages (skills + tools) — linked/installed by installer
  lib/                    # Shell libraries sourced by the installer and its siblings
    paths.sh              # git_excludes_path + demeter_link_roots
  tests/                  # Mechanical checks over the installer and its siblings
    check-link-roots.sh   # every link_file dest is under a declared root; `rules` prints what it checks
    check_link_roots.py   # the static half of the above
    uninstall-roundtrip.sh # plant a link under every root, sweep, assert none survive
    check-change-request.py # the ping's link resolution order, over every profile copy; `rules` prints it
    check-publish-artifact.sh # the artifact publish seam's exit codes and arg forwarding; `rules` prints it
  tools/                  # First-party projects shared by every profile
    claude-usage/         # VS Code extension, linked into ~/.claude/tools/
    worktree-sync/        # VS Code extension, linked into ~/.claude/tools/
  git/                    # Git config shared by every profile
    ignore                # machine-wide gitignore, linked to core.excludesFile
  shell/                  # Terminal experience shared by every profile
    terminal.zsh          # gap-filling zsh fragment, sourced last from each rc
    starship.toml         # prompt config (copy of rdev's)
    tmux.conf             # ~/.tmux.conf, or ~/.tmux.conf.local on rdev
    install-tools.sh      # installs the tools + zsh plugins terminal.zsh uses
  vscode/                 # Editor settings shared by every profile
    lib.sh                # editor CLI + path resolution, shared with install.sh
    settings.json         # symlinked over VS Code's user settings.json
    extensions.txt        # extension ids the installer keeps present
    sync-extensions.sh    # rewrites extensions.txt from the current machine
  profiles/               # One directory per machine profile
    check-transform.py    # enforces the work<->home transform and the work pair; `rules` prints what it checks
    larrabeedylan_home_pi/  # Raspberry Pi app host; skills/hooks/scripts are
                            # symlinks to the home_darwin profile's — see its AGENTS.md
    <profile>/            # e.g. larrabeedylan_work_linux
      .zshrc
      .bash_profile
      .claude/
        CLAUDE.md         # global agent instructions, synced to ~/.claude/CLAUDE.md
        settings.json     # permissions + hook registrations
        notify.json.example       # notification transport template; seeded to ~/.claude/notify.json
        environment.json.example  # forge/reviewer/artifact-store overrides; seeded to ~/.claude/environment.json
        skills/           # Claude Code skills, synced to ~/.claude/skills/
          <skill-name>/
            SKILL.md
        hooks/            # Hook scripts, synced to ~/.claude/hooks/
        scripts/          # Helper scripts used by skills
          skill-env.sh    # the per-machine seam; `check` prints what a skill will see
          publish-artifact.sh # publishes HTML to the self-hosted store, or exits 3 if absent
```

## Context Discovery

Before planning or making changes in a directory, **read the `README.md` and `AGENTS.md`** at the root of that directory (and any parent directories up to the repo root) if they exist. These files contain important context about the directory's purpose, conventions, constraints, and how components interact. This applies to research, planning, and implementation — not just code changes.
**The rationale lives in those docs, not here.** This file carries the invariants; the
reasoning behind each — the failure it was written against, the traps it leaves — lives in
the doc that owns the code, named at the end of each Conventions bullet: `lib/`, `git/`,
`shell/`, `vscode/`, `profiles/`, `tools/` and its tools, and each profile's
`.claude/skills/` and `.claude/hooks/`.


## Install Script (`install.sh`)

The installer does the following in order:

1. Selects the profile to install — from the first CLI argument (a `profiles/` subdirectory name or a path), else auto if only one profile exists, else prompts. `install.sh --help` lists available profiles, and `-y`/`--yes` answers every prompt.
2. Detects machine type — macOS = `mac`, a Raspberry Pi (`/etc/rpi-issue` present) = `pi`, any other Linux = `linux`. The Pi needs a type of its own rather than sharing `linux` with the rdev box: `SKIP_LIST` is keyed by machine, and the two need opposite treatment
3. Initializes git submodules if `.gitmodules` exists
4. Symlinks dotfiles from `profiles/<profile>/` to `~/` (skipping `.claude/`, and any path listed in `~/.rdev-managed.json` on an rdev box)
5. Symlinks `shell/` config (`terminal.zsh` to `~/.config/zsh/`, `starship.toml`, `tmux.conf`) and offers to install any missing terminal tool or zsh plugin
6. Symlinks `.claude/` contents individually (skills linked per-directory into `~/.claude/skills/`)
7. Unifies worktree project dirs into their main checkout's by running `.claude/hooks/link-worktree-session.py --backfill`, first probing it under a bare `PATH` (`/usr/bin:/bin`) — the environment Claude Code actually spawns hooks in
8. Seeds `~/.claude/notify.json` (mode 600) from the profile's `notify.json.example` when absent, probes `notify.py` under the same bare `PATH`, and names the fields still set to `REPLACE_ME`. Never overwrites a filled-in config
9. Seeds `~/.claude/environment.json` from the profile's `environment.json.example` when absent, then runs `skill-env.sh check` and reports whether the forge API helper it resolves to is actually installed. Never overwrites an existing config, and a malformed one is a warning rather than a failure — the skills fall back to the defaults compiled into `skill-env.sh`
10. Symlinks vendor skills from `_vendor/*/` into `~/.claude/skills/`
11. Symlinks shared tools from `tools/*` into `~/.claude/tools/`
12. Prompts to build and install shared tools exposing an `install` target in their Makefile. Runs through `mise exec` when the tool has a `.mise.toml`, so a pinned toolchain resolves in a non-interactive shell. Skipped without prompting when no editor CLI answers `--list-extensions`; otherwise the CLI it resolved is passed to `make install` as `CODE=`, since the Makefile's own `code` lookup fails outside the integrated terminal. Verifies afterwards that the tool's extension id is registered, since a build can succeed without the editor picking it up. Honours `SKIP_LIST` by tool directory name.
13. Symlinks `vscode/settings.json` over VS Code's user settings, on every editor user directory that already exists
14. Sweeps repo workspace `.vscode/settings.json` files for color keys the shared settings own, via `vscode/strip-stale-peacock-keys.sh`
15. Symlinks `git/ignore` to the machine-wide gitignore git actually reads, and verifies it took
16. Prompts to install any extension in `vscode/extensions.txt` missing from the editor. Each `--install-extension` runs under a timeout (`EXTENSION_INSTALL_TIMEOUT`, default 180s) and is then judged by `--list-extensions`, because the server CLI can finish installing and never exit
17. Cleans stale skill symlinks (removes symlinks pointing to deleted repo paths)
18. Creates data directories for skills that accumulate context
19. Runs `profiles/check-transform.py` to report profile drift — **warning-only**, and skipped without complaint when `python3` is absent

Key behaviors:
- `-y`/`--yes` answers every prompt instead of reading stdin, and is propagated to `vscode/strip-stale-peacock-keys.sh`, the only sub-script that prompts. It **refuses to run without an explicit profile** when more than one exists: profile selection is the one prompt with no safe default, and defaulting it links another machine's dotfiles over yours. It deliberately consumes no stdin, so `yes | ./install.sh <profile>` keeps working for anything already written against it — the flag's advantage is an exit status that is the installer's own rather than `141` from `yes` catching a `SIGPIPE` under `pipefail`
- Never copies `~/.claude` aside; it only replaces symlinks, leaving your session data in place
- Backs up existing real files before replacing
- Skips already-correct symlinks
- Removes stale skill symlinks that point into the repo but whose target no longer exists
- Respects `SKIP_LIST` for machine-specific files (format: `"filename:machine"`, machine = `mac` | `linux` | `pi` | `both`). It is honoured by the dotfile loop, both `.claude/` loops, `link_directory_contents`, and every `vscode`/`shell`/`tools`/`gitignore` step gate — a new step that skips none of those will fire on a box with no editor
- `.claude/CLAUDE.md` is symlinked to `~/.claude/CLAUDE.md` — the user-level instruction file loaded in every repository (no installer change was needed; the top-level `.claude/` file loop already handles it)
- `settings.json` is **symlinked** like everything else, and only *copied* with `__DEMETER_REPO__` path templating when the profile's copy actually contains that token — templating cannot write through a symlink. No profile uses the token today, so in practice every profile's `settings.json` is a symlink, which is what lets `/config` edits land back in the repo as a tracked diff. The corollary bites on a box whose `settings.json` is owned by something else: a symlink there sends `/config` writes into the clone, leaving it dirty so the next pull silently stops fast-forwarding. That is why the `pi` profile ships no `settings.json` at all
- `settings.local.json` lives at `.claude/.claude/` and is symlinked normally
- `.mcp.json` is NOT managed by the repo (contains tokens) — configure manually
- `.claude/hooks/` is linked per-file into `~/.claude/hooks/` by the same `.claude/` directory loop; the hooks that run from there are registered in each profile's `settings.json`
- `tools/` is profile-independent and linked per-directory into `~/.claude/tools/`. Linking only makes the source available, so a tool exposing a Makefile `install` target is then offered a build (step 12) — the symlink alone gives no signal that an installed artefact is older than the source
- `vscode/extensions.txt` is the companion to `settings.json`: a theme named in settings does nothing until its extension exists, and VS Code falls back silently. The installer only ever **adds** — a locally-installed extension missing from the list is left alone. `vscode/sync-extensions.sh` writes the list back from a machine; it excludes extension ids published from `tools/*/package.json`, which are not on the Marketplace and are installed by their own make target. `editor_cli()` resolves the CLI and `read_extension_list()` parses the file (`#` comments and blanks ignored) — both from `vscode/lib.sh`, shared with the installer
- `vscode/settings.json` is profile-independent and symlinked **wholesale** over the editor's user settings (`~/Library/Application Support/Code/User/` on mac, `~/.config/Code/User/` on linux, plus Insiders and VSCodium when present). Because it is a symlink, VS Code writes UI changes back into the repo — machine-specific keys (`window.zoomLevel`, `claudemeter.debugLogFile`) are kept last in the file so they stand out in a diff. `vscode_user_dirs()` in `vscode/lib.sh` resolves the paths; `should_skip "vscode" "$machine"` opts a platform out
- `vscode/strip-stale-peacock-keys.sh` is the counterpart to `peacock.excludedSettings`: an exclusion stops Peacock writing a key but never removes the copies it wrote before, and a workspace file outranks the shared settings, so the pin loses silently in exactly the repos nobody thinks to check. The sweep reads the owned-key list out of `vscode/settings.json` (never hardcodes it), scans `$HOME` five deep with `PEACOCK_SCAN_ROOT`/`PEACOCK_SCAN_DEPTH` overrides, prompts once with what it found, and re-parses every file it edits to prove only the owned keys left — a file whose keys share a line is reported, not rewritten. Run standalone or let step 14 run it
- `git/ignore` is profile-independent and linked to **`core.excludesFile` when it is set, else `$XDG_CONFIG_HOME/git/ignore`** — `git_excludes_path()` in `lib/paths.sh` resolves that, expanding a leading `~`/`$HOME`. Linking the XDG default is what makes it need no `git config` at all, and linking the configured path instead is what keeps a machine that sets `core.excludesFile` (an rdev image, say) from leaving the file inert. `is_rdev_managed` opts that path out, `should_skip "gitignore" "$machine"` opts a platform out. The step then runs `git check-ignore` in a throwaway `git init` (`git_ignores_probe()`) rather than trusting the symlink, because every failure mode here is silent
- Idempotent — safe to re-run after pulling changes

## When Making Changes

- **Shell scripts**: Use `shellcheck` on any changed `.sh` files if available
- **README**: Keep `README.md` up to date when adding features or changing the installer workflow
- **AGENTS.md**: Keep `AGENTS.md` files up to date when directory structure, patterns, or conventions change
- **CLAUDE.md**: Keep this file up to date when repo structure, installer behavior, or conventions change
- **Test the installer**: After modifying `install.sh`, verify it still works on a clean run — the script must remain idempotent

## Conventions

## Conventions

Each bullet is an invariant, then the doc that explains why. Read that doc before changing
anything in its subtree.

- **One profile directory per machine setup**, under `profiles/` (e.g. `larrabeedylan_work_linux`)
- **Dotfiles only**: Files in profile directories should be dotfiles (prefixed with `.`) or inside `.claude/`
- **No secrets in repo**: Sensitive values (API keys, tokens) belong in `~/.secrets` or similar, sourced from shell config — never committed
- **Machine-specific skipping**: Use the `SKIP_LIST` array in `install.sh` to control per-platform linking
- **rdev boxes**: rdev regenerates `~/.zshrc` and `~/.tmux.conf` and lists them in `~/.rdev-managed.json`; customize through `~/.zshrc.local`, `~/.zshrc.pre` and `~/.tmux.conf.local`, never a managed file. → `shell/AGENTS.md`
- **The Pi profile is an identity transform**: it symlinks `skills/`, `hooks/` and `scripts/` into the home profile and ships no `settings.json`, no user-level `CLAUDE.md` and no dotfiles. → `profiles/larrabeedylan_home_pi/AGENTS.md`
- **One owner per path family**: `lib/paths.sh` and `vscode/lib.sh` own the resolvers, and a new `link_file` destination must fall under a root declared in `demeter_link_roots` or CI fails. → `lib/AGENTS.md`
- **`comm` needs one case and one collation**: `vscode/sync-extensions.sh` lowercases both sides and pins `LC_ALL=C` on every `sort` and `comm`, because `comm` does not validate its input. → `vscode/AGENTS.md`
- **A glob with no match is a filename**: the `.claude/.*` loop ran unguarded for months and, on every profile with no hidden entries in `.claude/` (which is all of them), created a dangling symlink in `~/.claude` literally named `.*`. It had been there since July before anyone looked. `[[ -e "$src" ]] || continue` is the fix, and the general rule is that an unguarded glob feeding `link_file` creates garbage rather than doing nothing. `link_directory_contents` also skips `__pycache__` outright — it is gitignored build cruft, so publishing it into `~/.claude` is wrong on every machine and would ship one architecture's bytecode cache to another
- **Nothing in the installer may be fatal on an unattended run**: the submodule update was a bare command under `set -e`, so a flaky network at 04:30 aborted the whole run and installed nothing. It warns now. Any step that can fail for a reason outside the repo needs the same treatment, because the Pi's timer has no one watching it
- **Skills**: Each skill gets its own directory under `.claude/skills/` with a `SKILL.md` file
- **An empty diagram is worse than no diagram**: `changes-diagram` guarantees a non-empty diff produces a non-empty chart, and records which mode it drew. → `profiles/<p>/.claude/skills/AGENTS.md`
- **The diagram's publish target is configuration**: a new external resource must clear the Artifact tool's CSP allowlist or it fails invisibly, a local file is a success, and the self-hosted branch goes through `publish-artifact.sh` rather than discovering a command at runtime. → `profiles/<p>/.claude/skills/AGENTS.md`
- **A skill must never hardcode what differs between machines**: `scripts/skill-env.sh` is the seam, and **an empty value means the capability is absent here, never "go and guess"**. → `profiles/<p>/.claude/skills/AGENTS.md`
- **One script reaches the self-hosted artifact store, and four keys carry the machine difference**: `publish-artifact.sh` prints the URL or exits **3** to mean "no such store here", which is the ordinary answer on a work box rather than a failure. A caller passes `--purpose plan|diagram` and the script resolves the folder, because `${FOLDER:+--folder "$FOLDER"}` in a skill body yields two arguments under bash and **one** under zsh. → `profiles/<p>/.claude/skills/AGENTS.md`
- **A forge helper's subcommand list is derived from its own source**: it is the skills' only discovery mechanism, so never hand-maintain it. → `profiles/<p>/.claude/skills/AGENTS.md`
- **A clip has to announce itself**: `job-log` bounds its output and every path prints the total and what it dropped. → `profiles/<p>/.claude/skills/AGENTS.md`
- **Profile divergence is a mechanical transform, not prose rewriting**: a work skill becomes its home counterpart through exactly these ten substitutions, in order — `an MR`→`a PR`, `An MR`→`A PR`, `merge requests`→`pull requests`, `merge request`→`pull request`, `Merge Request`→`Pull Request`, `Merge request`→`Pull request`, `GitLab`→`GitHub`, `\bMR(?=\d)`→`PR`, `\bMRs\b`→`PRs`, `\bMR\b`→`PR` — plus `gitlab-api.sh`→`github-api.sh`. **`profiles/check-transform.py` is where that list now lives in code**, and it is the authority — this prose is the explanation, not the implementation. Three traps. **`\bMR\b` cannot see `MR2`** — the digit is a word character — so stack labels like `MR1`…`MR5` in `plan-subtasks` survive untransformed without the lookahead rule. **`\b` silently no-ops in BSD `sed` on macOS**, producing output that looks transformed and is not; use `perl`, GNU sed, or python `re`. And **never add a URL-rewriting rule**: `reflect-peer`'s context files carry real `gitlab.com/-/merge_requests/…` links that are evidence, not vocabulary, and rewriting the host turns them into 404s. Write the **work** copy so the transform yields clean English on the other side — never `an \`MR<n>\``, and no literal example URLs — since the transform cannot see through a backtick or into a hostname. Say "merge request" in the work copy wherever the home copy should say "pull request"
- **An asserted guarantee is not a guarantee**: `profiles/check-transform.py` checks the work pair and the transform over tracked files, warning-only in `install.sh` and **failing** in CI. → `profiles/AGENTS.md`
- **A rewrite needs a substrate**: `docs-humanize` builds a numbered fact ledger first and measures every later phase against it. → `profiles/<p>/.claude/skills/AGENTS.md`
- **Subagents are encouraged, Workflows are not assumed**: `.claude/CLAUDE.md` carries a standing instruction to spawn subagents whenever work parallelises, without asking — sessions otherwise arrive with a harness default telling them not to, which is not something this repo sets and not something a skill can see. The justification is `tools/agent-watch/`: a fan-out is observable here, so it costs nothing to watch. The **Workflow** tool keeps its own opt-in, since it launches agents by the dozen. The same section restates the two things a spawned agent never inherits — the no-comments rule, and that "read-only" has to explicitly forbid writing into the working tree, which agents have ignored when it was merely implied
- **The scannable-output spec lives in two places on purpose, and they are not duplicates**: a wall of generated prose is unreadable in a way the reader cannot fix after the fact, so the rules for avoiding one belong in `.claude/CLAUDE.md`, loaded into every conversation in every repo — a skill the agent has to be reminded to invoke is a skill that arrives after the damage. `aidr` is the retrofit for when it was forgotten anyway, and the split is by cost: the global copy is compressed to the rules themselves because it is paid for on every single turn, while the skill carries the procedure, the four-way classification, the budget and the worked template because it is paid for only when invoked. Four things are load-bearing in both. **Actions come first**, because theirs is the only section with a deadline. **The class of every line is unambiguous** — action for the reader, action already taken, fact, background — since a reader working out which is which is doing the writer's job. **Commands sit at the step that needs them** and run as-is, because a command assembled out of prose is a command retyped wrong. And **paths are markdown links, never backticked** (`[config.ts:88](src/config.ts#L88)`), since a bare path costs a search in exactly the editor these are read in. Two guards stop the cure becoming the disease: the spec is a **compression that may drop anything and add nothing** — silence in the source is reported as silence, because an invented step is worse than the wall it replaced — and **structure is only applied where structure is needed**, since headings on a two-sentence answer are the same padding in a different shape. ASD-STE100 is cited for its *writing* rules only (one instruction per sentence, under 20 words, active, imperative, simple tenses, no noun cluster past three words); compliance is never claimed, because the approved-word dictionary is not checkable here and claiming it would be the exact kind of unearned confidence the rule exists to remove
- **No comments in code**: `.claude/CLAUDE.md` forbids agent-written code comments globally. Any skill that writes or edits code must restate the rule in its own prompt — subagents spawned by a skill receive the skill's text, not the user's `CLAUDE.md`. The only sanctioned exception is `security-audit`'s PoC and verification tests, where the write-up is the deliverable
- **No skill edits itself**: thirteen of the twenty-four skills used to end with a `Self-Improvement` step telling the run to edit `~/.claude/skills/<name>/SKILL.md`, which is a **symlink into this clone** — so a session working in an unrelated repository was being instructed to write into Demeter's working tree from outside it. Three costs, and the first is the one that bites silently: it leaves the clone dirty, which is the exact mechanism this file already documents as fatal for `settings.json`, because the Pi's HEAD-guarded daily pull stops fast-forwarding and the auto-update dies with nothing reporting it — and the Pi reaches that file, since its `skills/` is a symlink into `home_darwin`. Second, the edit lands in exactly one of the three real profile copies with no transform run, manufacturing the drift `check-transform.py` exists to detect. Third, it charged ~1KB of resident prose per skill on **every** invocation for a checklist reached at most once, at the end, when the run is usually out of budget. The replacement is in `.claude/CLAUDE.md`: a shortcoming observed during a run is named to the user in one line with the suggested edit, and lands through the ordinary reviewed path (`/fix-freeform` on Demeter), which edits every copy and runs the check. `pause`, `unpause`, `workflow-resume`, `ping` and `aidr` — the newer skills — never carried the step, so this makes the older ones match them rather than inventing a convention. Three of the roughly seventy reflection questions were worth keeping and were folded into the step that *reports* to the user, not a step that rewrites the file: `autopilot` Step 11 names a deploy signal that did not prove what it was meant to, `review-code` Step 6 says whether the scale fit the diff, `fix-feedback` Step 8 names the findings that landed unanchored. The rest were either self-tuning instructions that only made sense to a file editing itself, or already required by an existing step
- **Vendor packages**: Third-party skill sets go in `_vendor/<name>/` as git submodules
- **rdev bootstrap**: it clones **every** repo before setting any up, and runs each setup under `timeout` so a hung step fails one repo rather than the run. → `tools/AGENTS.md`
- **Shared tools**: machine-independent projects live in `tools/<name>/`, and **nothing runnable ships in git** — a box that skipped installer step 12 has the id registered with no `dist/`. → `tools/AGENTS.md`
- **The three editor extensions share one scaffold**: `tools/extension.mk` holds the body, so never copy build config between tools, and keep `outDir`/`rootDir` per-tool. → `tools/AGENTS.md`
- **A README link to a sibling file fails `vsce package`**: an in-page anchor is fine, a relative link is not. → `tools/AGENTS.md`
- **Never truncate content to protect the webview**: pay for a huge tool result by **not rendering** it. Clipping is for one-line headers, and `clip()` must never touch a `<pre>`. → `tools/agent-watch/DESIGN.md`
- **Notifications are one-way**: `notify.py` does one HTTP POST and exits, and nothing here may hold a turn open. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **A ping cannot be answered**: Remote Control is armed at startup and no skill can read its state, so a ping must **never** claim the session is answerable. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **Asking costs a stalled run**: ask before anything irreversible or chargeable, otherwise take the most defensible option plus a ledger line. An ask must stand alone. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **A notification is only as good as its gate**: `agent_id` events are suppressed, `min_interval_seconds` always applies, and turn length is measured from the **last handoff back to you**. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **Notifications are opt-in per session, and `/ping` is the opt-in**: `armed_at` is a latch only `/ping off` clears, written only on a successful send. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **The latch gates news, never stuck**: `question` and `permission` notify **without** arming; `idle` is excluded, and an explicit off switch and quiet hours still outrank it. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **The notification body is summarized by a model**: via `claude -p` on the subscription, never an API key; every failure degrades to a mechanical condense and still sends. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **Only a thread’s first message repeats its context**: the root is `<repo> · <title>`, anchored before the first event; replies are `<glyph> <body>`. An absolute URL survives `strip_markdown`. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **Composition is shared across transports; only delivery is not**: both senders use one layout, and the `ping` skill's budget moves with `SUMMARY_MAX_WORDS`. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **`--show-toplevel` answers the worktree, not the repository**: use `--git-common-dir`, and reproduce any label bug from **inside** a worktree. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **Outside a repository the directory names the session**: a named directory wins; `host_label` answers only `$HOME` itself. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **Away mode is a file, not an environment variable**: hooks do not inherit your shell's environment. It drops `min_turn_seconds` and nothing else. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **A `U…` id is not a DM channel**: resolve it through `conversations.open`, because posting to a user id returns `ok` and lands with Slackbot. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **Threading a Slack DM silences everything after the first message**: the mention that fixes it **must sit in the `blocks`, not only `text`**. Telegram is unaffected. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **A Slack incoming webhook cannot thread**: threading needs a bot token, and the push preview shows only `text`, never `blocks`. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **`/ping` is the deliberate counterpart to the hook**: an explicit ping **bypasses every gate**, shares the session state read-modify-write, and names no transport. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **A hook that fails is invisible**: every invocation including the silent ones logs, every error path exits 0, and an unfilled config is a dormant no-op. → `profiles/<p>/.claude/hooks/AGENTS.md`
- **Claude credentials**: `claude-usage` reads Claude Code's token **read-only** and must never write or refresh it — that would log the user out. → `tools/claude-usage/README.md`
- **One extension, many windows**: anything polling the network shares one reading through a lock file plus a cache in the user's cache dir, and never stores credentials there. → `tools/claude-usage/README.md`
- **Never gate an install on OS-dependent behaviour**: `make install` runs the tests, so assert the code's own guarantee rather than that the kernel delivered an event. → `tools/AGENTS.md`
- **The editor's tsserver runs ahead of the pinned compiler**: a next-major diagnostic shows in the Problems tab and never in CI. Fix the config; keep `rootDir` explicit. → `tools/AGENTS.md`
- **Extension test stubs**: `vscodeStub.ts` must cover everything `activate()` touches — a gap is a vitest *unhandled error* with every test still passing. → `tools/AGENTS.md`
- **Status bar glyphs**: it renders in the **UI font**, so prefer `●○`/`■□` over block elements that fall back per-character. → `tools/claude-usage/README.md`
- **Driving another extension's commands**: a contributed command is not API, so probe `getCommands(true)` first. Status bar priority is "higher sits further left" on **both** sides. → `tools/claude-usage/README.md`
- **Shared rate limit on `/api/oauth/usage`**: the limit is per account and the CLI already polls it, so be frugal rather than cached and never poll past the soonest reset. → `tools/claude-usage/README.md`
- **Browser OAuth**: open the system browser via `vscode.env.openExternal`, never a webview — Okta SSO misbehaves in embedded browsers. → `tools/claude-usage/README.md`
- **Theme ids**: every theme-scoped key takes a theme's **settingsId**, often not its display name, and a wrong id fails silently. → `vscode/AGENTS.md`
- **Shared terminal**: `shell/` is one terminal experience for every machine, sourced **last** from each rc, and it **fills gaps only** — per-feature guards, never one `is_rdev` switch. → `shell/AGENTS.md`
- **VS Code shell integration is manual**: `shell/terminal.zsh` sources the script itself, because automatic injection breaks revived terminals. → `shell/AGENTS.md`
- **Global git ignore**: an entry belongs in `git/ignore` only when it is true of every repo on every machine. Ignore the **file**, never the directory. → `git/AGENTS.md`
- **Editor settings**: one shared `settings.json`; color fixes go in its theme-scoped `workbench.colorCustomizations`, never a per-repo file, and anything Peacock writes goes in `peacock.excludedSettings`. → `vscode/AGENTS.md`
- **Peacock favorites**: the list replaces Peacock's rather than extending it, and every value must clear 4.5:1 against the foreground Peacock picks. → `vscode/AGENTS.md`
- **`workbench.experimental.modernUI` is off on purpose**: it reroutes tab and command-center colors away from the theme, hiding the active tab label under most light themes. → `vscode/AGENTS.md`
- **An autonomous run waits with `Monitor`, never with sleep**: a watcher's filter must emit on **every** terminal state, since silence is indistinguishable from still-running. → `profiles/<p>/.claude/skills/AGENTS.md`
- **Reviews outrank CI**: open threads come first, because every push restarts the pipeline. The merge step **re-reads the verdict itself**, a green review job means the reviewer ran rather than approved, and an apply precedes the merge. → `profiles/<p>/.claude/skills/AGENTS.md`
- **Two reviews, and the swarm is the one with a filter**: its skeptics must **refute** every candidate, and it runs once per run, never once per round. → `profiles/<p>/.claude/skills/AGENTS.md`
- **Autopilot is on by default**: the fix skills *hand over* rather than being wrapped, and it automates the **tail, not the thinking** — their gates stay open. → `profiles/<p>/.claude/skills/AGENTS.md`
- **`/autopilot <flags>` mid-run is an amendment**: change only the flags it names and leave the rest at their **current run value**, never the machine default. → `profiles/<p>/.claude/skills/AGENTS.md`
- **One flag surface across both fix skills**: the same seven flags with the same meanings, and what differs is per machine and lives in `skill-env.sh`. → `profiles/<p>/.claude/skills/AGENTS.md`
- **`--quick-description` is about latency, not agent count**: `true` means `--inline`, with the budget **measured by a command** and the result reported as `self fact-checked`. → `profiles/<p>/.claude/skills/AGENTS.md`
- **The decision record is captured early and published late**: appended to a local ledger as decisions are made, published once as a collapsed fold, never as a comment. → `profiles/<p>/.claude/skills/AGENTS.md`
- **"Merged" is not "deployed"**: establish the deploy path **before** the merge gate, tie verification to the landed SHA, never upgrade cannot-observe into success, and warn rather than remediate. → `profiles/<p>/.claude/skills/AGENTS.md`
- **Engaging autopilot arms the phone**: one ping goes out before the first unattended step, since `armed_at` is written only on a successful send. **Every route in arms.** → `profiles/<p>/.claude/skills/AGENTS.md`
- **A pause is only graceful if it was affordable**: the run **journals as it goes**, and the state file must stand alone without the transcript. → `profiles/<p>/.claude/skills/AGENTS.md`
- **Stopping a run means stopping it**: `TaskStop` every watcher and record a **re-arm instruction**; an armed auto-merge and an unverified deploy are unsafe to park on. → `profiles/<p>/.claude/skills/AGENTS.md`
- **The resume trigger is a detached poll on wall-clock**: not `Monitor`, which caps at 30 minutes, and never a usage percentage, which nothing refreshes once windows close. → `profiles/<p>/.claude/skills/AGENTS.md`
- **Quota comes from the `claude-usage` cache, never the API**: taking `usage.lock` or writing there is forbidden, `resetsAt` is epoch **milliseconds**, and all four meters get checked. → `profiles/<p>/.claude/skills/AGENTS.md`
- **`/resume` is a built-in, so the skill is `/unpause`**: a name a built-in owns silently never fires. → `profiles/<p>/.claude/skills/AGENTS.md`
- **A `$<digit>` anywhere in a skill body is rewritten at invocation**: it corrupts any `awk` program while the file on disk still looks correct. Sweep including `$0`. → `profiles/<p>/.claude/skills/AGENTS.md`
- **A swarm's resume cache is keyed on the diff**: a moved branch voids it entirely, and the state file keeps an **ordered chain** of run ids. → `profiles/<p>/.claude/skills/AGENTS.md`
- **`scriptPath` is a trap for resuming a swarm**: the snapshot is frozen, so it replays the *pre-fix* pipeline; `workflow-resume` is the only sanctioned route. → `profiles/<p>/.claude/skills/AGENTS.md`
- **Recorded authority survives a pause; recorded evidence does not**: a recorded `--merge true` still authorises the merge, but approvals, pipeline state and apply markers are all re-read. → `profiles/<p>/.claude/skills/AGENTS.md`
- **Run state belongs outside the repository**: it lives under `~/.claude`, keyed by repo and branch so another session can find it. → `profiles/<p>/.claude/skills/AGENTS.md`
- **A cleanup command is only as complete as the thing it iterates**: `wtclean` sweeps branches, not just worktrees, and merges in memory because **ancestry cannot see a squash merge**. → `shell/AGENTS.md`
- **Deleting the merged branch is part of merging**: it is `wtclean`’s only signal, so the delete is pushed at **confirmed** merge — never a stack member’s branch. → `profiles/<p>/.claude/skills/AGENTS.md`
- **A resumed run must enter its worktree first**: **subagents inherit the session's working directory**, so a swarm started elsewhere reviews the wrong repository plausibly. → `profiles/<p>/.claude/skills/AGENTS.md`
- **Review findings are persisted, not just chatted**: `fix-feedback` posts each finding as an anchored comment *before* working the queue, deduped against fetched threads. → `profiles/<p>/.claude/skills/AGENTS.md`
- **`acceptEdits` makes an unattended run unattendable**: it prompts for every `Bash` call, so `permissions.defaultMode` is `auto`; the post-approval mode is chosen at the `ExitPlanMode` prompt. → `profiles/<p>/.claude/skills/AGENTS.md`
- **Plan mode is not what gates `Bash`**: permission rules do, and Claude Code **splits on shell operators** so **every segment must be allowed**. Entries stay read-only. → `profiles/<p>/.claude/skills/AGENTS.md`
- **Hooks**: one script per hook under `.claude/hooks/`, registered by a `$HOME/.claude/hooks/<name>` path. **Claude Code spawns hooks with a bare `PATH`**, so the installer probes each one. → `profiles/<p>/.claude/hooks/AGENTS.md`
