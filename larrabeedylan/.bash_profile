function updateprofile() {
  if [ -d ~/Demeter/src ]; then
    cd ~/Demeter/src || return 1
    git checkout .
    git checkout linux
    git pull origin linux
    cd -
  else
    return 0
  fi
  if [ -d ~/Demeter/Demeter ]; then
    cd ~/Demeter/Demeter || return 1
    git checkout .
    git checkout linux
    git pull origin linux
    cd -
  else
    return 0
  fi
}

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

alias profile='nano ~/.bash_profile'

### DIRECTORY ALIASES

alias lsa='ls -a'
alias ll='ls -l'
alias lla='ls -la'
alias D='cd ~/Desktop'
alias cl='clear'

alias count_in_dirs='du -a | cut -d/ -f2 | sort | uniq -c'
alias find_corrupted_images='feh -ur .'

alias x='exit'

### RANDOM HELPERS

# usage: start Artemis torch
start() {
    if [[ "$1" == "a" || "$1" == "A" || "$1" == "Artemis" ]]; then
        bash Artemis/docker/$2/run.sh
    fi

    if [[ "$1" == "p" || "$1" == "P" || "$1" == "Persephone" ]]; then
        echo "no docker images for Persephone"
    fi

    if [[ "$1" == "h" || "$1" == "H" || "$1" == "Hephaestus" ]]; then
        echo "no docker images for Hephaestus"
    fi
}

function stop(){
  local container_names=("Artemis" "Persephone" "Hephaestus")

  for container_name in "${container_names[@]}"
  do  
      # Check if the container is running
      if docker ps -a --format '{{.Names}}' | grep -Eq "^$container_name$"; then
          echo "$container_name is running, stopping..."
          docker stop $container_name
      fi
  done
}

### Jupyter Notebook stuff

alias jp='jupyter notebook --no-browser'

### MISC

PS1="\w > "

### Dev Container Stuff

alias d="docker "

### Hugging Face token stuff

alias hfread='huggingface-cli login --token $HF_READ'
alias hfwrite='huggingface-cli login --token $HF_WRITE'

# continually display gpu stats, kinda like htop
alias gtop="watch -n 1 nvidia-smi"

# like top but for showing network activity/bandwidth
alias iftop="sudo iftop"

# for restricting pernisions on public keys
# (only the owner can read)
alias restrict="chmod 400 "
alias release="sudo chown -R dylan " # <directory> change the premissions for an entire directory

# for opening up permissions on .sh scripts so they can be executed
alias permit="chmod +x "

# turn off the desktop in one minute and exit
function off() {
  sudo shutdown -h 1
  exit
}

# Created by `pipx`
export PATH="$PATH:/home/dylan/.local/bin"

# test change
