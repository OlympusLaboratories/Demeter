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
alias go='git checkout '
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
