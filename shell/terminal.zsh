: "${DEMETER_ZSH_PLUGINS:=$HOME/.local/share/zsh}"

_dt_plugin() {
  local name="$1" file="$2" candidate
  for candidate in \
    "$DEMETER_ZSH_PLUGINS/$name/$file" \
    "/opt/homebrew/share/$name/$file" \
    "/usr/local/share/$name/$file" \
    "/usr/share/$name/$file" \
    "/usr/share/zsh/plugins/$name/$file"
  do
    if [[ -r "$candidate" ]]; then
      print -r -- "$candidate"
      return 0
    fi
  done
  return 1
}

HISTFILE="${HISTFILE:-$HOME/.zsh_history}"
HISTSIZE=50000
SAVEHIST=50000
setopt SHARE_HISTORY INC_APPEND_HISTORY HIST_IGNORE_ALL_DUPS HIST_IGNORE_SPACE HIST_REDUCE_BLANKS HIST_VERIFY

WORDCHARS="${WORDCHARS//[\/._-]}"

autoload -Uz add-zsh-hook

_dt_completions="$DEMETER_ZSH_PLUGINS/zsh-completions/src"
_dt_recompinit=0
if [[ -d "$_dt_completions" && -z "${fpath[(r)$_dt_completions]}" ]]; then
  fpath=("$_dt_completions" $fpath)
  _dt_recompinit=1
fi

if (( ! $+functions[compdef] )); then
  autoload -Uz compinit && compinit
elif (( _dt_recompinit )); then
  compinit -C
fi
(( $+functions[bashcompinit] )) || autoload -Uz bashcompinit
(( $+functions[complete] )) || bashcompinit

zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}' 'r:|=*' 'l:|=* r:|=*'
zstyle ':completion:*' group-name ''
zstyle ':completion:*:descriptions' format '%F{yellow}%d%f'
zstyle ':completion:*:warnings' format '%F{red}no matches%f'
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"
zstyle ':completion:*' use-cache on
zstyle ':completion:*' cache-path "$HOME/.cache/zsh/compcache"

if (( ! $+functions[_zsh_autosuggest_start] )); then
  if _dt_found="$(_dt_plugin zsh-autosuggestions zsh-autosuggestions.zsh)"; then
    source "$_dt_found"
  fi
fi
if (( $+functions[_zsh_autosuggest_start] )); then
  ZSH_AUTOSUGGEST_STRATEGY=(history completion)
  ZSH_AUTOSUGGEST_BUFFER_MAX_SIZE=80
  : "${ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE:=fg=8}"
fi

autoload -Uz up-line-or-beginning-search down-line-or-beginning-search
zle -N up-line-or-beginning-search
zle -N down-line-or-beginning-search
bindkey '^[[A' up-line-or-beginning-search
bindkey '^[OA' up-line-or-beginning-search
bindkey '^[[B' down-line-or-beginning-search
bindkey '^[OB' down-line-or-beginning-search
bindkey '^P' up-line-or-beginning-search
bindkey '^N' down-line-or-beginning-search
bindkey '^[[1;5C' forward-word
bindkey '^[[1;5D' backward-word
bindkey '^[[3~' delete-char
bindkey '^[[H' beginning-of-line
bindkey '^[[F' end-of-line

if command -v fzf >/dev/null 2>&1; then
  if (( ! $+functions[fzf-history-widget] )) && _dt_fzf_init="$(fzf --zsh 2>/dev/null)"; then
    eval "$_dt_fzf_init"
  fi
  : "${FZF_DEFAULT_OPTS:=--height 40% --layout=reverse --border}"
  export FZF_DEFAULT_OPTS
  if command -v fd >/dev/null 2>&1; then
    : "${FZF_DEFAULT_COMMAND:=fd --type f --hidden --follow --exclude .git}"
    : "${FZF_CTRL_T_COMMAND:=$FZF_DEFAULT_COMMAND}"
    : "${FZF_ALT_C_COMMAND:=fd --type d --hidden --follow --exclude .git}"
    export FZF_DEFAULT_COMMAND FZF_CTRL_T_COMMAND FZF_ALT_C_COMMAND
  fi
elif (( ! $+functions[fzf-history-widget] )); then
  bindkey '^R' history-incremental-search-backward
fi

if (( ! $+functions[prompt_starship_precmd] )) && command -v starship >/dev/null 2>&1; then
  : "${STARSHIP_CONFIG:=$HOME/.config/starship.toml}"
  export STARSHIP_CONFIG
  eval "$(starship init zsh)"
fi

if (( ! $+functions[prompt_starship_precmd] )); then
  _dt_git_branch() {
    git rev-parse --is-inside-work-tree &>/dev/null || return
    local branch
    branch="$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --short HEAD 2>/dev/null)"
    print -n -- "($branch) "
  }
  setopt PROMPT_SUBST
  PROMPT='%F{green}%n@%m%f:%F{blue}%~%f $(_dt_git_branch)%# '
fi

_dt_set_title() { print -Pn "\e]0;%n@%m: %~\a"; }
case "$TERM" in
  xterm*|rxvt*|screen*|tmux*|alacritty|kitty|ghostty) add-zsh-hook precmd _dt_set_title ;;
esac

if command -v bat >/dev/null 2>&1; then
  alias cat='bat --paging=never'
  : "${BAT_THEME:=ansi}"
  export BAT_THEME
fi
: "${LESS:=-R}"
export LESS

_dt_load_syntax_highlighting() {
  add-zsh-hook -d precmd _dt_load_syntax_highlighting
  if [[ -z "${ZSH_HIGHLIGHT_VERSION:-}" ]]; then
    local found
    if found="$(_dt_plugin zsh-syntax-highlighting zsh-syntax-highlighting.zsh)"; then
      source "$found"
    fi
  fi
  unfunction _dt_load_syntax_highlighting
  unfunction _dt_plugin 2>/dev/null
}
add-zsh-hook precmd _dt_load_syntax_highlighting

unset _dt_completions _dt_recompinit _dt_found _dt_fzf_init
