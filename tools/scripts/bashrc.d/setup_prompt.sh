#!/bin/bash
# Custom prompt (sourced by init.sh after .bashrc is reset)

BASHRC="$HOME/.bashrc"

USER_COLOR='\033[32m'
DOCKER_COLOR='\033[34m'
PATH_COLOR='\033[35m'
COMMAND_COLOR='\033[38;5;214m'
BOLD='\033[1m'
RESET_COLOR='\033[0m'

# Non-printing segments wrapped in \[ \] so line editing works correctly
FIXED_PS1="\[${BOLD}\]\[${USER_COLOR}\]\u\[${RESET_COLOR}\]@\
\[${BOLD}\]\[${DOCKER_COLOR}\]aember-container\[${RESET_COLOR}\]:\
\[${BOLD}\]\[${PATH_COLOR}\]\w\[${RESET_COLOR}\]\
\[${COMMAND_COLOR}\]\$ \[${RESET_COLOR}\]"

if ! grep -q "# BEGIN AEMBER PROMPT" "$BASHRC" 2>/dev/null; then
cat <<EOF2 >> "$BASHRC"

# BEGIN AEMBER PROMPT
VIRTUAL_ENV_DISABLE_PROMPT=1
PS1="${FIXED_PS1}"
# END AEMBER PROMPT
EOF2
fi
