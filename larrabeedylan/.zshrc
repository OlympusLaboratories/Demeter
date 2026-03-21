
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
alias go='git checkout '
alias gri='git rebase -i'
alias got='git '
alias get='git '
alias gti='git '
alias ob='git branch --sort=committerdate '
alias gsd='git status; git diff'
alias gm='git merge'
alias log='git log'
alias hist="log --pretty=format:'%h %ad | %s%d [%an]' --graph --date=short"
alias hsit='hist '
alias h='hist -5'
alias clean='git clean -i'

alias update='CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD) && git prune && git fetch origin --prune && git pull origin $CURRENT_BRANCH --rebase && git status'
alias freshen='update && git merge origin main -m "Merge main branch into working branch" && git status'
alias f='freshen'

# Terraform helpers
alias tf='terraform '

# Git branch helper
git_branch() {
    git rev-parse --is-inside-work-tree &>/dev/null || return
    local branch=$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --short HEAD 2>/dev/null)
    echo "($branch)"
}

# Colored prompt (zsh on macOS always supports color)
setopt PROMPT_SUBST
PROMPT="%F{green}%n@%m%f:%F{blue}%~%f \$(git_branch) %# "

# Set terminal window title
case "$TERM" in
xterm*|rxvt*)
    precmd() { print -Pn "\e]0;%n@%m: %~\a" }
    ;;
esac

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

source ~/.secrets

# direnv
eval "$(direnv hook zsh)"

# a-cli tab completion
autoload -Uz compinit && compinit
eval "$(_A_COMPLETE=zsh_source a)"
