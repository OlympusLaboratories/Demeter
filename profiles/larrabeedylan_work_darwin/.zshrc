# ~/.zshrc — merged: macOS setup + git/k8s/infra helpers from the Linux dev box

### ZSH SETUP (before prompt / completions)

setopt PROMPT_SUBST

# Persistent history — zsh saves nothing to disk by default
HISTFILE="$HOME/.zsh_history"
HISTSIZE=10000
SAVEHIST=10000
setopt SHARE_HISTORY HIST_IGNORE_DUPS HIST_IGNORE_SPACE

# Completion system + support for bash-style completion scripts (nvm, gcloud)
autoload -Uz compinit && compinit
autoload -Uz bashcompinit && bashcompinit

### EDITING

alias profile="nano ~/.zshrc"
alias src="source ~/.zshrc"

# NOTE: mise manages python/pip on this machine — these would shadow its shims.
# Uncomment only if you stop using mise for python.
# alias pip='pip3'
# alias python='python3'

### GCP COMPUTE INSTANCES

alias on="gcloud config set compute/zone us-central1-b && while true; do gcloud compute instances start dylan-a100-22 && break; done"
alias off="gcloud config set compute/zone us-central1-b && gcloud compute instances stop dylan-a100-22"
alias x="gcloud config set compute/zone us-west1-b && ssh dylan-cpu-new-iap"
alias addkey="ssh-add --apple-use-keychain ~/.ssh/google_compute_engine"

### GIT HELPERS

alias gs='git status '
alias ga='git add '
alias gb='git branch '
alias gc='git commit'
alias gd='git diff'
alias gpsh='git push'
alias gpu='git push --force-with-lease -u origin HEAD'
alias gpl='git pull'
# `go` is a worktree-aware git checkout — see the GIT WORKTREES section below
alias gco.='git checkout .'
alias gri='git rebase -i'
alias got='git '      # typo recovery
alias get='git '      # typo recovery
alias gti='git '      # typo recovery
alias igt='git '      # typo recovery
alias ob='git branch --sort=-committerdate '   # most-recent first
alias gsd='git status; git diff'
alias gm='git merge'
alias log='git log'
alias hist="log --pretty=format:'%h %ad | %s%d [%an]' --graph --date=short"
alias hsit='hist '    # typo recovery
alias h='hist -5'
alias clean='git clean -i'

# Detects main/master (or whatever the remote default is)
_git_default_branch() {
  git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null \
    | sed 's@^refs/remotes/origin/@@' \
    || git remote show origin 2>/dev/null \
    | awk '/HEAD branch/ { print $NF }'
}

alias update='CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD) && git prune && git fetch origin --prune && git pull origin "$CURRENT_BRANCH" --rebase && git status'
alias freshen='DEFAULT_BRANCH=$(_git_default_branch) && update && git rebase "origin/$DEFAULT_BRANCH" && git status'
alias f='freshen'

# Go the language (alias 'go' is git checkout)
alias gol='command go'

### GIT WORKTREES
# Portable across bash and zsh — keep these three profiles' copies identical.
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

  local root here list wp branch kind reason last cutoff removed=0 skipped=0
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

  git -C "$root" worktree prune
  if [ "$apply" -eq 0 ]; then
    printf '\n%d to remove, %d skipped. Re-run with -y to apply.\n' "$removed" "$skipped"
  else
    printf '\n%d removed, %d skipped.\n' "$removed" "$skipped"
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

### TERRAFORM

alias tf='terraform '
alias tfi='terraform init '
alias tfp='terraform plan '
alias tfa='terraform apply '

### KUBERNETES

alias k="kubectl"
alias kpods="kubectl get pods -n production"
alias klogs="kubectl logs -n production -f"
alias krestart="kubectl rollout restart -n production "
alias kdescribe="kubectl describe pod -n production "
alias kwest="kubectl config use-context gke_tlal-1210_us-west1-b_tlaloc"
alias kwestprod="kubectl config use-context gke_tlal-1210_us-west1_production"
alias kcent="kubectl config use-context gke_tlal-1210_us-central1-c_tlaloc"
alias kcentjobs="kubectl config use-context gke_tlal-1210_us-central1-c_tlaloc-jobs"
alias kbuild="kubectl config use-context gke_gridmatic-build_us-central1_build-us-central1"
alias kcontext="kubectl config current-context"
alias kcontexts="kubectl config get-contexts"

### DIRECTORY / MISC

alias lsa='ls -a'
alias ll='ls -la'
alias lla='ls -la'
alias cl='clear'
alias pids="sudo netstat -tulp"
alias gtop="watch -n 1 nvidia-smi"
alias iftop="sudo iftop"

### PROMPT

git_branch() {
    git rev-parse --is-inside-work-tree &>/dev/null || return
    local branch=$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --short HEAD 2>/dev/null)
    echo "($branch)"
}

if [ -x /usr/bin/tput ] && tput setaf 1 >&/dev/null; then
    color_prompt=yes
else
    color_prompt=
fi

if [ "$color_prompt" = yes ]; then
    PROMPT='${debian_chroot:+($debian_chroot)}%F{green}%n@%m%f:%F{blue}%~%f $(git_branch) %# '
else
    PROMPT='${debian_chroot:+($debian_chroot)}%n@%m:%~ $(git_branch) %# '
fi
unset color_prompt

# Terminal window title
case "$TERM" in
xterm*|rxvt*)
    precmd() { print -Pn "\e]0;${debian_chroot:+($debian_chroot)}%n@%m: %~\a" }
    ;;
esac

### COLORS

# ls colors — platform aware (BSD ls on macOS, GNU ls on Linux)
if [[ "$(uname)" == "Darwin" ]]; then
    export CLICOLOR=1
    export LSCOLORS=ExFxCxDxBxegedabagacad
elif [ -x /usr/bin/dircolors ]; then
    eval "$(dircolors -b ~/.dircolors 2>/dev/null || dircolors -b)"
    alias ls='ls --color=auto'
fi
# grep colors (both GNU and BSD grep support --color=auto)
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'

### ENVIRONMENT

export PATH="$HOME/.local/bin:$PATH"
export PATH="/usr/local/go/bin:$HOME/go/bin:$PATH"
export PATH="$HOME/.tfenv/bin:$PATH"
export PATH="$PATH:$HOME/.temporalio/bin"
export PYTHONPATH="$HOME/tlaloc/python"

# GKE / GCP
export USE_GKE_GCLOUD_AUTH_PLUGIN=True
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud/application_default_credentials.json"

### TOOLING

# nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
command -v nvm >/dev/null && nvm use default --silent >/dev/null

# Google Cloud SDK — source the first location that exists (zsh incs)
for _gcloud_dir in "$HOME/google-cloud-sdk" "$HOME/Downloads/google-cloud-sdk"; do
    if [ -f "$_gcloud_dir/path.zsh.inc" ]; then
        . "$_gcloud_dir/path.zsh.inc"
        [ -f "$_gcloud_dir/completion.zsh.inc" ] && . "$_gcloud_dir/completion.zsh.inc"
        break
    fi
done
unset _gcloud_dir

# Secrets (not committed)
[ -f ~/.secrets ] && source ~/.secrets

# direnv
command -v direnv >/dev/null && eval "$(direnv hook zsh)"

# mise — activated for gridmatic-dev (and other repos with .mise.toml).
# Pre-trust configs under $HOME so mise doesn't prompt per repo.
export MISE_TRUSTED_CONFIG_PATHS="$HOME"
command -v mise >/dev/null && eval "$(mise activate zsh)"

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
    tail -n 8 "$j" | jq -rc --argjson C "$cflag" "$HASH"' (if $C==1 then "[38;5;\($col)m\($id[0:8])[0m" else ($id[0:8]) end) as $idc | if .type=="started" then "▶ launched \($idc)" elif .type=="result" then "✓ done     \($idc)  \((.result//{})|tostring|gsub("\n";" ")|.[0:200])" else "• \(.type)" end'
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
