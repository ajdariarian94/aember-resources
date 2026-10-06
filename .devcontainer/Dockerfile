# Yocto 6.0 "Wrynose" (LTS) build host. For Scarthgap, use BASE_IMAGE=ubuntu:24.04
ARG BASE_IMAGE=ubuntu:26.04
FROM ${BASE_IMAGE}

ARG UID=1000
ARG GID=1000
ARG USERNAME=dev
ENV DEBIAN_FRONTEND=noninteractive

# Yocto host requirements + a few dev essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential chrpath cpio debianutils diffstat file gawk gcc git \
        iputils-ping libacl1 locales lz4 python3 python3-git python3-jinja2 \
        python3-pexpect python3-pip python3-subunit python3-venv socat \
        texinfo unzip wget xz-utils zstd \
        ca-certificates sudo vim bash-completion figlet lolcat acl docker.io \
    && rm -rf /var/lib/apt/lists/* \
    && locale-gen en_US.UTF-8 \
    && ln -s /usr/games/lolcat /usr/local/bin/lolcat

ENV LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 \
    VIRTUAL_ENV=/venv \
    PATH=/venv/bin:$PATH

# Create user, or rename the image's existing UID (e.g. "ubuntu") to $USERNAME
RUN set -e; \
    existing="$(getent passwd ${UID} | cut -d: -f1 || true)"; \
    if [ -n "$existing" ] && [ "$existing" != "${USERNAME}" ]; then \
        groupmod -n "${USERNAME}" "$(id -gn "$existing")"; \
        usermod -l "${USERNAME}" -d "/home/${USERNAME}" -m "$existing"; \
    elif [ -z "$existing" ]; then \
        groupadd -f -g "${GID}" "${USERNAME}"; \
        useradd -m -s /bin/bash -u "${UID}" -g "${GID}" "${USERNAME}"; \
    fi; \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME}; \
    chmod 0440 /etc/sudoers.d/${USERNAME}; \
    usermod -aG docker "${USERNAME}"

# Python venv for project tools + aember CLI
# The CLI is copied to the same path the workspace is mounted at, and installed
# editable. At runtime the mount covers this copy, so the venv uses your live source.
COPY requirements.txt /tmp/requirements.txt
COPY aember-cli /aember_ws/aember-resources/aember-cli
RUN python3 -m venv /venv \
    && /venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt \
    && /venv/bin/pip install --no-cache-dir -e /aember_ws/aember-resources/aember-cli \
    && chown -R ${UID}:${GID} /venv /aember_ws \
    && rm /tmp/requirements.txt

USER ${USERNAME}
WORKDIR /home/${USERNAME}
