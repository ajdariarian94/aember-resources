#!/bin/bash
# Fully reset .bashrc and set up the workspace environment for aember

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME="$(id -un)"

# -----------------------------
# Run once per container start
# -----------------------------
# VS Code runs postStartCommand twice, sometimes simultaneously.
#  - flock stops two copies running at the same time.
#  - The stamp holds PID 1's start time, which changes on every container
#    (re)start, so a restart always re-initialises. No root needed.
LOCK_FILE="/tmp/aember-init.lock"
STAMP_FILE="$HOME/.cache/aember-init.stamp"
START_ID="$(awk '{print $22}' /proc/1/stat 2>/dev/null)"

exec 9>"$LOCK_FILE"
if ! flock -n 9 || [ "$(cat "$STAMP_FILE" 2>/dev/null)" = "$START_ID" ]; then
    figlet -f big "hacking..." | lolcat
    exit 0
fi

# -----------------------------
# Fix Docker GID mismatch and verify socket access
# -----------------------------
# The socket is bind-mounted with the HOST's docker GID, which may not match
# the image's docker group. Join a group with the host GID (creating
# "docker-host" if needed), and grant a direct ACL so it works in shells that
# are already open (group changes only apply to new login sessions).
if [ -S /var/run/docker.sock ]; then
    HOST_DOCKER_GID="${DOCKER_GID:-$(stat -c '%g' /var/run/docker.sock 2>/dev/null)}"

    if [ -n "$HOST_DOCKER_GID" ]; then
        EXISTING_GROUP="$(getent group "$HOST_DOCKER_GID" | cut -d: -f1)"
        if [ -z "$EXISTING_GROUP" ]; then
            sudo groupadd -g "$HOST_DOCKER_GID" docker-host 2>/dev/null || true
            EXISTING_GROUP="docker-host"
        fi
        if ! id -nG "$USER_NAME" | grep -qw "$EXISTING_GROUP"; then
            sudo usermod -aG "$EXISTING_GROUP" "$USER_NAME" 2>/dev/null || true
        fi
    fi

    sudo setfacl -m "u:${USER_NAME}:rw" /var/run/docker.sock 2>/dev/null || true

    if ! docker info >/dev/null 2>&1; then
        echo "⚠️  $USER_NAME cannot reach /var/run/docker.sock — Docker-in-Docker builds will fail" >&2
    fi
else
    echo "⚠️  /var/run/docker.sock not found — is the socket mounted into this container?" >&2
fi

# -----------------------------
# aember completion
# -----------------------------
# Pass "bash" explicitly: we're launched via /bin/sh, so auto-detection
# would pick the wrong shell.
if command -v aember >/dev/null 2>&1; then
    aember --install-completion bash >/dev/null 2>&1 \
        || echo "⚠️  failed to install aember completion" >&2
else
    echo "⚠️  aember not found — was it installed in the image?" >&2
fi

# -----------------------------
# Reset .bashrc completely
# -----------------------------
cat > "$HOME/.bashrc" <<'BASHRC'
# ~/.bashrc: reset by aember init.sh
case $- in
    *i*) ;;
      *) return;;
esac

HISTCONTROL=ignoreboth
shopt -s histappend
HISTSIZE=1000
HISTFILESIZE=2000
shopt -s checkwinsize

alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'

if [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
fi

if [ -f ~/.bash_completions/aember.sh ]; then
    source ~/.bash_completions/aember.sh
fi
BASHRC

# Helper scripts append their own sections to .bashrc
for script in "$SCRIPT_DIR"/bashrc.d/*.sh; do
    [ -e "$script" ] && source "$script"
done

sudo rm -rf /root/.config/git

# Mark this container start as initialised
mkdir -p "$(dirname "$STAMP_FILE")"
echo "$START_ID" > "$STAMP_FILE"

figlet -f big aember | lolcat
