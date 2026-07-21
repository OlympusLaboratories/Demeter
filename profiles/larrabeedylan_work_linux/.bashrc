alias profile='nano ~/.bashrc'
alias src='source ~/.bashrc'

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
alias gpu='git push --force-with-lease -u origin HEAD'
alias gpl='git pull'
alias go='git checkout '
alias gco.='git checkout .'
alias gri='git rebase -i'
alias got='git '      # typo recovery
alias get='git '      # typo recovery
alias gti='git '      # typo recovery
alias igt='git '      # typo recovery
alias ob='git branch --sort=committerdate '
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

# Go (alias 'go' is git checkout, use 'gol' for Go lang)
alias gol='command go'

# Terraform
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

# Git branch helper function
git_branch() {
  git branch 2>/dev/null | sed -e '/^[^*]/d' -e 's/* \(.*\)/(\1)/'
}

# Colored prompt with git branch
if [ -x /usr/bin/tput ] && tput setaf 1 >&/dev/null; then
  PS1='\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\] $(git_branch) \$ '
else
  PS1='\u@\h:\w $(git_branch) \$ '
fi

# Terminal window title
case "$TERM" in
xterm*|rxvt*)
    PS1="\[\e]0;\u@\h: \w\a\]$PS1"
    ;;
esac

# Color support for ls (platform-aware)
if [[ "$(uname)" == "Darwin" ]]; then
  export CLICOLOR=1
  export LSCOLORS=ExFxCxDxBxegedabagacad
else
  if [[ -x /usr/bin/dircolors ]]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    alias grep='grep --color=auto'
  fi
fi

### DIRECTORY ALIASES

alias lsa='ls -a'
alias ll='ls -la'
alias lla='ls -la'
alias cl='clear'

alias x='exit'
alias pids="sudo netstat -tulp"

# GPU and network monitoring
alias gtop="watch -n 1 nvidia-smi"
alias iftop="sudo iftop"

### ENVIRONMENT

# PATH
export PATH="$HOME/.local/bin:$PATH"
export PATH="/usr/local/go/bin:$HOME/go/bin:$PATH"
export PATH="$HOME/.tfenv/bin:$PATH"
export PYTHONPATH=$HOME/tlaloc/python

# GCP
export USE_GKE_GCLOUD_AUTH_PLUGIN=True
export GOOGLE_APPLICATION_CREDENTIALS=$HOME/.config/gcloud/application_default_credentials.json

# NVM
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
# Activate the nvm default (e.g. node 20) in every new shell so PATH/NVM_BIN
# don't keep pointing at whichever version was last `nvm use`d.
command -v nvm >/dev/null && nvm use default --silent >/dev/null

# Google Cloud SDK
if [ -f "$HOME/google-cloud-sdk/path.bash.inc" ]; then . "$HOME/google-cloud-sdk/path.bash.inc"; fi
if [ -f "$HOME/google-cloud-sdk/completion.bash.inc" ]; then . "$HOME/google-cloud-sdk/completion.bash.inc"; fi

# Source secrets (not committed)
[ -f ~/.secrets ] && source ~/.secrets

# direnv integration
eval "$(direnv hook bash)"

export PATH="$PATH:/home/dylanlarrabee/.temporalio/bin"

# wfwatch <run_id> [--once] — watch ANY Claude Code workflow's progress by run id.
# Resolves the journal across sessions/projects and reports only the universal
# signals the Workflow harness emits for every run (started/result events), plus
# a truncated preview of each agent's result. No workflow-/schema-specific fields,
# so it never breaks on a particular prompt. Live tail by default; --once = snapshot.
wfwatch() {
  local rid="$1" mode="$2"
  if [ -z "$rid" ]; then echo "usage: wfwatch <run_id> [--once]"; return 2; fi
  local j
  j=$(ls -t ~/.claude/projects/*/*/subagents/workflows/"$rid"/journal.jsonl 2>/dev/null | head -1)
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
