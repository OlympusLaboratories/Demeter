
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
alias igt='git '
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

# Go (alias 'go' is git checkout, use 'gol' for Go lang)
alias gol='command go'

# Terraform helpers
alias tf='terraform '
alias tfi='terraform init '
alias tfp='terraform plan '
alias tfa='terraform apply '

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

[ -f ~/.secrets ] && source ~/.secrets

# direnv
eval "$(direnv hook zsh)"

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
