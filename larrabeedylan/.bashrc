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
alias gpu='git push -u origin HEAD'
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
alias freshen='DEFAULT_BRANCH=$(_git_default_branch) && update && git merge "origin/$DEFAULT_BRANCH" -m "Merge $DEFAULT_BRANCH into working branch" && git status'
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

# Google Cloud SDK
if [ -f "$HOME/google-cloud-sdk/path.bash.inc" ]; then . "$HOME/google-cloud-sdk/path.bash.inc"; fi
if [ -f "$HOME/google-cloud-sdk/completion.bash.inc" ]; then . "$HOME/google-cloud-sdk/completion.bash.inc"; fi

# Source secrets (not committed)
[ -f ~/.secrets ] && source ~/.secrets

# direnv integration
eval "$(direnv hook bash)"

# a-cli (Apollo) tab completion
eval "$(_A_COMPLETE=bash_source a)"
