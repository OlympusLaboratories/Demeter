
alias profile='nano ~/.zshrc'

alias pip='pip3'
alias python='python3'

### GIT HELPERS

alias gs='git status '
alias ga='git add '
alias gb='git branch '
alias ob='git branch --sort=-committerdate '
alias gc='git commit'
alias gd='git diff'
alias gpsh='git push'
alias gpu='git push -u origin HEAD'
alias gpl='git pull'
# `go` is a worktree-aware git checkout — see the GIT WORKTREES section below
alias gri='git rebase -i'
alias got='git '
alias get='git '
alias gti='git '
alias igt='git '
alias ob='git branch --sort=committerdate '
alias gsd='git status; git diff'
alias gm='git merge'
alias log='git log'
alias hist="log --pretty=format:'%h %ad | %s%d [%an]' --graph --date=short"
alias hsit='hist '
alias h='hist -5'
alias clean='git clean -i'

alias update='CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD) && git prune && git fetch origin --prune && git pull origin "$CURRENT_BRANCH" --rebase && git status'
alias freshen='DEFAULT_BRANCH=$(_wt_default_branch) && update && git rebase "origin/$DEFAULT_BRANCH" && wtclean --no-fetch -y && git status'
alias f='freshen'

# Go (alias 'go' is git checkout, use 'gol' for Go lang)
alias gol='command go'

### GIT WORKTREES
# Portable across bash and zsh — keep every copy identical.
# (zsh note: never name a local `path` — it shadows $PATH. Hence `wp`.)

# Where `wt` creates new worktrees, relative to the main working tree.
: "${WT_ROOT:=.claude/worktrees}"
# Age (in days) at which `wtclean` calls a worktree stale.
: "${WT_STALE_DAYS:=90}"

_wt_in_repo() {
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 && return 0
  echo "${1:-wt}: not inside a git repository" >&2
  return 1
}

# Absolute path of the main working tree (the one that owns .git)
_wt_main_root() {
  git worktree list --porcelain 2>/dev/null | awk '/^worktree /{ print substr($0, 10); exit }'
}

# Name of the default branch, from the remote's HEAD with a main/master fallback
_wt_default_branch() {
  local d
  d=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
  [ -n "$d" ] || d=$(git branch -r 2>/dev/null | grep -E 'origin/(main|master)$' | head -1 | sed 's@.*origin/@@')
  [ -n "$d" ] || d=main
  printf '%s\n' "$d"
}

# 0 when merging $1 into $2 would change nothing -- $2 already holds every change
# on $1, however it got there. A squash merge rewrites the commit, so the branch
# tip is NOT an ancestor of the default branch and an ancestry test calls a
# squash-merged branch unmerged; comparing the merge result's tree sees through
# that. --write-tree needs git 2.38, so ancestry stays as the fallback.
_wt_absorbed() {
  local b="$1" base="$2" tree want
  want=$(git rev-parse --verify --quiet "$base^{tree}") || return 1
  tree=$(git merge-tree --write-tree "$base" "$b" 2>/dev/null) || {
    git merge-base --is-ancestor "$b" "$base" 2>/dev/null
    return $?
  }
  [ "$tree" = "$want" ]
}

# One "<path><TAB><branch>" line per worktree; branch is "(detached)" when headless
_wt_list() {
  git worktree list --porcelain 2>/dev/null | awk '
    /^worktree / { wp = substr($0, 10); branch = "(detached)"; next }
    /^branch /   { branch = substr($0, 8); sub(/^refs\/heads\//, "", branch); next }
    /^$/         { if (wp != "") { print wp "\t" branch; wp = "" } next }
    END          { if (wp != "") print wp "\t" branch }
  '
}

# Upstream state of a branch: gone (remote branch deleted) | none | ok
_wt_upstream_state() {
  local up track
  up=$(git for-each-ref --format='%(upstream)' "refs/heads/$1" 2>/dev/null)
  [ -n "$up" ] || { echo none; return 0; }
  track=$(git for-each-ref --format='%(upstream:track)' "refs/heads/$1" 2>/dev/null)
  case "$track" in
    *gone*) echo gone ;;
    *)      echo ok ;;
  esac
}

# wt [<branch>] — cd to the worktree for a branch.
#   no argument         → the main working tree
#   exact branch/dir    → that worktree
#   unique substring    → that worktree (ambiguous matches are listed, not guessed)
#   branch has no worktree yet → offer to create one under $WT_ROOT
wt() {
  _wt_in_repo wt || return 1
  local query="$1" list hits n root target branch ans

  list=$(_wt_list)

  if [ -z "$query" ]; then
    target=$(_wt_main_root)
    [ -n "$target" ] || return 1
    cd "$target" || return 1
    echo "→ $(pwd)  [$(git symbolic-ref --short HEAD 2>/dev/null || echo detached)]"
    return 0
  fi

  # exact branch, then exact directory name, then case-insensitive substring
  hits=$(printf '%s\n' "$list" | awk -F'\t' -v q="$query" '$2 == q')
  [ -n "$hits" ] || hits=$(printf '%s\n' "$list" | awk -F'\t' -v q="$query" \
    '{ d = $1; sub(/.*\//, "", d); if (d == q) print }')
  [ -n "$hits" ] || hits=$(printf '%s\n' "$list" | awk -F'\t' -v q="$query" \
    'BEGIN { q = tolower(q) } index(tolower($2), q) || index(tolower($1), q)')

  n=$(printf '%s\n' "$hits" | grep -c .)

  if [ "$n" -gt 1 ]; then
    echo "wt: '$query' matches $n worktrees:" >&2
    printf '%s\n' "$hits" | awk -F'\t' '{ printf "  %-36s %s\n", $2, $1 }' >&2
    return 1
  fi

  if [ "$n" -eq 1 ]; then
    target=$(printf '%s\n' "$hits" | cut -f1)
    cd "$target" || return 1
    echo "→ $(pwd)  [$(git symbolic-ref --short HEAD 2>/dev/null || echo detached)]"
    return 0
  fi

  # No worktree matched — is there a branch by that name to build one from?
  branch=$(git for-each-ref --format='%(refname:short)' refs/heads | grep -iF -- "$query" | head -1)
  if [ -z "$branch" ]; then
    branch=$(git for-each-ref --format='%(refname:lstrip=3)' refs/remotes \
      | grep -iF -- "$query" | grep -v '^HEAD$' | head -1)
  fi
  if [ -z "$branch" ]; then
    echo "wt: no worktree or branch matching '$query'" >&2
    wtl >&2
    return 1
  fi

  root=$(_wt_main_root)
  target="$root/$WT_ROOT/$branch"
  printf "wt: no worktree for '%s' — create %s? [y/N] " "$branch" "$WT_ROOT/$branch"
  read -r ans
  case "$ans" in
    [yY]*) ;;
    *) return 1 ;;
  esac

  if git show-ref --verify --quiet "refs/heads/$branch"; then
    git -C "$root" worktree add "$target" "$branch" || return 1
  elif git show-ref --verify --quiet "refs/remotes/origin/$branch"; then
    git -C "$root" worktree add --track -b "$branch" "$target" "origin/$branch" || return 1
  else
    echo "wt: '$branch' is not a local branch or an origin branch" >&2
    return 1
  fi
  cd "$target" || return 1
  echo "→ $(pwd)  [$branch]"
}

# wtl — list worktrees with branch, age, upstream state and dirty flag.
# `*` marks the worktree you are standing in.
wtl() {
  _wt_in_repo wtl || return 1
  local here root list wp branch mark age state rel
  here=$(git rev-parse --show-toplevel 2>/dev/null)
  root=$(_wt_main_root)
  list=$(_wt_list)

  printf '%-2s %-36s %-16s %-14s %s\n' " " "BRANCH" "LAST COMMIT" "STATE" "PATH"
  while IFS=$'\t' read -r wp branch; do
    [ -n "$wp" ] || continue
    mark=" "; [ "$wp" = "$here" ] && mark="*"
    age=$(git -C "$wp" log -1 --format='%cr' 2>/dev/null)
    case "$(_wt_upstream_state "$branch")" in
      gone) state="gone" ;;
      none) state="local" ;;
      *)    state="tracked" ;;
    esac
    [ -n "$(git -C "$wp" status --porcelain 2>/dev/null)" ] && state="$state,dirty"
    if [ "$wp" = "$root" ]; then
      rel="(main)"
    else
      rel="$wp"
      case "$wp" in "$root"/*) rel="${wp#$root/}" ;; esac
    fi
    printf '%-2s %-36s %-16s %-14s %s\n' "$mark" "$branch" "${age:-?}" "$state" "$rel"
  done <<< "$list"
}

# wtclean [-y] [--days N] [--no-fetch] [--keep-branches]
#   Removes worktrees whose branch was deleted on the remote, or whose last
#   commit is older than N days (default $WT_STALE_DAYS). Merged branches are
#   deleted too; unmerged stale ones are kept and reported.
#   Then sweeps local branches that no worktree holds -- merged, or gone from
#   the remote and merged -- since the worktree pass can never see those.
#   Dry run unless -y. Never touches the main working tree, the worktree you are
#   standing in, a detached-HEAD worktree, or one with uncommitted changes.
wtclean() {
  _wt_in_repo wtclean || return 1
  local apply=0 days="$WT_STALE_DAYS" fetch=1 keep_branches=0
  while [ $# -gt 0 ]; do
    case "$1" in
      -y|--yes)       apply=1 ;;
      --days)         shift; days="$1" ;;
      --no-fetch)     fetch=0 ;;
      --keep-branches) keep_branches=1 ;;
      -h|--help)
        echo "usage: wtclean [-y] [--days N] [--no-fetch] [--keep-branches]"
        return 0 ;;
      *) echo "wtclean: unknown option '$1'" >&2; return 2 ;;
    esac
    shift
  done
  case "$days" in ''|*[!0-9]*) echo "wtclean: --days needs a number" >&2; return 2 ;; esac

  local root here list wp branch kind reason last cutoff removed=0 skipped=0 branches=0
  root=$(_wt_main_root)
  here=$(git rev-parse --show-toplevel 2>/dev/null)

  if [ "$fetch" -eq 1 ]; then
    echo "fetching --prune (use --no-fetch to skip) …"
    git -C "$root" fetch --all --prune --quiet \
      || echo "wtclean: fetch failed — remote state may be stale" >&2
  fi
  git -C "$root" worktree prune

  cutoff=$(( $(date +%s) - days * 86400 ))
  list=$(_wt_list)

  while IFS=$'\t' read -r wp branch; do
    [ -n "$wp" ] || continue
    [ "$wp" = "$root" ] && continue
    if [ "$branch" = "(detached)" ]; then
      echo "  skip     $wp — detached HEAD"
      continue
    fi

    kind=""; reason=""
    if [ "$(_wt_upstream_state "$branch")" = "gone" ]; then
      kind="gone"; reason="branch deleted on remote"
    else
      last=$(git -C "$wp" log -1 --format='%ct' 2>/dev/null)
      if [ -n "$last" ] && [ "$last" -lt "$cutoff" ]; then
        kind="stale"
        reason="untouched for ${days}+ days (last $(git -C "$wp" log -1 --format='%cr'))"
      fi
    fi
    [ -n "$kind" ] || continue

    if [ "$wp" = "$here" ]; then
      echo "  skip     $branch — you are standing in it ($reason)"
      skipped=$((skipped + 1))
      continue
    fi
    if [ -n "$(git -C "$wp" status --porcelain 2>/dev/null)" ]; then
      echo "  skip     $branch — uncommitted changes ($reason)"
      skipped=$((skipped + 1))
      continue
    fi

    if [ "$apply" -eq 0 ]; then
      echo "  would remove  $branch — $reason"
      removed=$((removed + 1))
      continue
    fi

    git -C "$root" worktree remove "$wp" || continue
    echo "  removed  $branch — $reason"
    removed=$((removed + 1))
    [ "$keep_branches" -eq 1 ] && continue
    if [ "$kind" = "gone" ]; then
      git -C "$root" branch -D "$branch" >/dev/null && echo "           branch $branch deleted"
    elif git -C "$root" branch -d "$branch" >/dev/null 2>&1; then
      echo "           branch $branch deleted"
    else
      echo "           branch $branch kept (unmerged — 'git branch -D $branch' to drop it)"
    fi
  done <<< "$list"

  # Branches no worktree holds. The loop above only ever sees a branch some
  # worktree has checked out, so a branch whose worktree went earlier -- or that
  # never had one -- is invisible to it and survives every run.
  if [ "$keep_branches" -eq 0 ]; then
    local def held b bstate bmerged
    def=$(_wt_default_branch)
    held=$(_wt_list | cut -f2)
    while IFS= read -r b; do
      [ -n "$b" ] || continue
      [ "$b" = "$def" ] && continue
      printf '%s\n' "$held" | grep -Fxq -- "$b" && continue

      bstate=$(_wt_upstream_state "$b")
      bmerged=0
      _wt_absorbed "$b" "refs/remotes/origin/$def" && bmerged=1

      if [ "$bstate" = "gone" ] && [ "$bmerged" -eq 1 ]; then
        reason="merged, and gone from the remote"
      elif [ "$bstate" = "gone" ]; then
        reason="gone from the remote, and NOT in $def — 'git reflog' recovers it"
      elif [ "$bmerged" -eq 1 ]; then
        reason="already merged into $def"
      else
        continue
      fi

      if [ "$apply" -eq 0 ]; then
        echo "  would delete  branch $b — $reason"
      elif git -C "$root" branch -D "$b" >/dev/null 2>&1; then
        echo "  deleted  branch $b — $reason"
      else
        echo "  skip     branch $b — git refused to delete it ($reason)"
        skipped=$((skipped + 1))
        continue
      fi
      branches=$((branches + 1))
    done <<< "$(git -C "$root" for-each-ref --format='%(refname:short)' refs/heads/)"
  fi

  git -C "$root" worktree prune
  if [ "$apply" -eq 0 ]; then
    printf '\n%d worktree(s) to remove, %d branch(es) to delete, %d skipped. Re-run with -y to apply.\n' "$removed" "$branches" "$skipped"
  else
    printf '\n%d worktree(s) removed, %d branch(es) deleted, %d skipped.\n' "$removed" "$branches" "$skipped"
  fi
}

alias wtc='wtclean'

# go [<branch>|<worktree>] — checkout that treats worktrees as branches.
#   local branch, not checked out anywhere else → git checkout
#   local branch held by another worktree       → cd to that worktree
#   worktree directory name (no such branch)    → cd to that worktree
#   anything else (-b, ., --, paths, tags, ...) → handed to git checkout verbatim
go() {
  # Only a single bare word can name a branch or worktree; everything else
  # (`go -b new`, `go .`, `go -- file`, `go HEAD~1 file`) is plain checkout.
  if [ "$#" -ne 1 ] || [ -z "$1" ]; then
    git checkout "$@"
    return
  fi
  case "$1" in -*) git checkout "$@"; return ;; esac
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { git checkout "$@"; return; }

  local query="$1" list hits n wp branch here rc

  list=$(_wt_list)

  if git show-ref --verify --quiet "refs/heads/$query"; then
    # A real branch: checkout works unless a worktree already holds it.
    hits=$(printf '%s\n' "$list" | awk -F'\t' -v q="$query" '$2 == q')
    if [ -z "$hits" ]; then
      git checkout "$query"
      return
    fi
  else
    # Not a branch — match a worktree by directory name (covers detached ones).
    hits=$(printf '%s\n' "$list" | awk -F'\t' -v q="$query" \
      '{ d = $1; sub(/.*\//, "", d); if (d == q) print }')
  fi

  n=$(printf '%s\n' "$hits" | grep -c .)

  if [ "$n" -gt 1 ]; then
    echo "go: '$query' matches $n worktrees:" >&2
    printf '%s\n' "$hits" | awk -F'\t' '{ printf "  %-36s %s\n", $2, $1 }' >&2
    return 1
  fi

  if [ "$n" -eq 1 ]; then
    wp=$(printf '%s\n' "$hits" | cut -f1)
    branch=$(printf '%s\n' "$hits" | cut -f2)
    here=$(git rev-parse --show-toplevel 2>/dev/null)
    if [ "$wp" = "$here" ]; then
      echo "→ already here: $wp  [$branch]"
      return 0
    fi
    cd "$wp" || return 1
    echo "→ $(pwd)  [$branch]"
    return 0
  fi

  # Nothing local matched — let git do remote-tracking DWIM, tags, SHAs and
  # pathspecs, and print its own error when the name is simply wrong.
  git checkout "$query"
  rc=$?
  [ "$rc" -eq 0 ] && return 0

  # Wrong-but-close: surface fuzzy worktree matches that `wt` would have found.
  hits=$(printf '%s\n' "$list" | awk -F'\t' -v q="$query" \
    'BEGIN { q = tolower(q) } index(tolower($2), q) || index(tolower($1), q)')
  if [ -n "$hits" ]; then
    echo "go: worktrees matching '$query' — try 'wt $query':" >&2
    printf '%s\n' "$hits" | awk -F'\t' '{ printf "  %-36s %s\n", $2, $1 }' >&2
  fi
  return $rc
}

# Terraform helpers
alias tf='terraform '
alias tfi='terraform init '
alias tfp='terraform plan '
alias tfa='terraform apply '

# Enable color for ls on macOS
export CLICOLOR=1
export LSCOLORS=ExFxCxDxBxegedabagacad

### DIRECTORY ALIASES

alias lsa='ls -a'
alias ll='ls -l'
alias lla='ls -la'
alias D='cd ~/Desktop'
alias cl='clear'

alias x=''

# continually display gpu stats, kinda like htop
alias gtop="watch -n 1 nvidia-smi"

# like top but for showing network activity/bandwidth
alias iftop="sudo iftop"

[ -f ~/.secrets ] && source ~/.secrets

# Claude Code authenticates with ANTHROPIC_API_KEY if it is set, which bypasses
# the Max subscription and bills a pay-as-you-go console account instead. The key
# above is kept for other tooling; this shadows it for Claude Code only.
claude() { env -u ANTHROPIC_API_KEY command claude "$@"; }


# direnv
eval "$(direnv hook zsh)"

command -v mise >/dev/null && eval "$(mise activate zsh)"

# a-cli tab completion
autoload -Uz compinit && compinit
eval "$(_A_COMPLETE=zsh_source a)"

### CLAUDE CODE — WORKFLOW WATCHER

# wfwatch <run_id> [--once] — watch ANY Claude Code workflow's progress by run id.
# Resolves the journal across sessions/projects and reports only the universal
# signals the Workflow harness emits for every run (started/result events), plus
# a truncated preview of each agent's result. No workflow-/schema-specific fields,
# so it never breaks on a particular prompt. Live tail by default; --once = snapshot.
# (zsh/macOS port of the Linux .bashrc function.)
wfwatch() {
  local rid="$1" mode="$2"
  if [ -z "$rid" ]; then echo "usage: wfwatch <run_id> [--once]"; return 2; fi
  # Newest matching journal via zsh glob qualifiers: (N) nullglob so a no-match
  # expands to nothing instead of erroring, (om) orders by mtime newest-first.
  local -a _hits
  _hits=( "${HOME}"/.claude/projects/*/*/subagents/workflows/"$rid"/journal.jsonl(Nom) )
  local j="${_hits[1]}"
  if [ -z "$j" ]; then echo "wfwatch: no journal found for run id '$rid'"; return 1; fi
  local started done_
  started=$(grep -c '"type":"started"' "$j")
  done_=$(grep -c '"type":"result"' "$j")
  # ANSI colors only when stdout is a terminal (so piping/redirect stays clean).
  local C_RUN='' C_DONE='' C_DIM='' C_RST='' cflag=0
  if [ -t 1 ]; then C_RUN=$'\033[36m'; C_DONE=$'\033[32m'; C_DIM=$'\033[2m'; C_RST=$'\033[0m'; cflag=1; fi
  local rule='────────────────────────────────────────────────'
  # Shared jq prelude: hash agentId → a stable 256-color code ($col) from a
  # curated bright palette, so the same agent always gets the same hue (and its
  # ▶launch / ✓done lines are visually linked without reading the hex id).
  local HASH='(.agentId // "") as $id | ($id|explode|reduce .[] as $c (0; (.*31+$c)%1048576)) as $h | ([39,45,51,75,81,111,117,147,183,203,209,215,221,227,159,123,120,84,48,44,214,170,141,213]) as $pal | ($pal[$h % ($pal|length)]) as $col |'
  if [ "$mode" = "--once" ] || [ "$mode" = "-1" ]; then
    printf "run %s — %d done / %d launched (%d running)\n" "$rid" "$done_" "$started" "$((started-done_))"
    tail -n 8 "$j" | jq -rc --argjson C "$cflag" "$HASH"' (if $C==1 then "[38;5;\($col)m\($id[0:8])[0m" else ($id[0:8]) end) as $idc | if .type=="started" then "▶ launched \($idc)" elif .type=="result" then "✓ done     \($idc)  \((.result//{})|tostring|gsub("\n";" ")|.[0:200])" else "• \(.type)" end'
    return 0
  fi
  printf "watching %s — %d/%d done at start (Ctrl-C to stop)\n" "$rid" "$done_" "$started"
  # Per event: the agentId is colored by a hash of itself (same agent = same
  # color across its launch/done lines); `running` = in-flight (launched - done)
  # shows concurrency; `done N/M` is overall progress. `done` events get a rule +
  # indented result preview so they're easy to separate.
  # --unbuffered: jq block-buffers a pipe, so without it nothing prints until the
  # `tail -f` EOF that never comes; this flushes each line as it arrives.
  local nstart=0 ndone=0 id
  tail -n +1 -f "$j" \
    | jq --unbuffered -rc "$HASH"' if .type=="started" then "S\t\($id[0:8])\t\($col)\t" elif .type=="result" then "R\t\($id[0:8])\t\($col)\t\((.result//{})|tostring|gsub("\n";" ")|.[0:200])" else "O\t\(.type)\t\t" end' \
    | while IFS=$'\t' read -r kind id8 col preview; do
        if [ -n "$C_RST" ] && [ -n "$col" ]; then printf -v id '\033[38;5;%sm%s\033[0m' "$col" "$id8"; else id="$id8"; fi
        case "$kind" in
          S) nstart=$((nstart+1))
             printf "%s▶ launch%s %s  %srunning %-2d  done %d/%d%s\n" \
               "$C_RUN" "$C_RST" "$id" "$C_DIM" "$((nstart-ndone))" "$ndone" "$nstart" "$C_RST" ;;
          R) ndone=$((ndone+1))
             printf "%s%s%s\n" "$C_DIM" "$rule" "$C_RST"
             printf "%s✓ done  %s %s  %srunning %-2d  done %d/%d%s\n" \
               "$C_DONE" "$C_RST" "$id" "$C_DIM" "$((nstart-ndone))" "$ndone" "$nstart" "$C_RST"
             printf "    %s\n" "$preview" ;;
          *) printf "%s• %s%s\n" "$C_DIM" "$id8" "$C_RST" ;;
        esac
      done
}

[ -r "$HOME/.config/zsh/terminal.zsh" ] && source "$HOME/.config/zsh/terminal.zsh"
