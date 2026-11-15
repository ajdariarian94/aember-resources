"""
Run kas inside the pinned kas image (ghcr.io/siemens/kas/kas).

The dev container talks to the host Docker daemon through the mounted socket,
so bind-mount sources must be *host* paths. HOST_ROOT_PATH (set by
devcontainer.json) is the host path of the repo root; outside the dev
container the repo root itself is used.

Inside the kas container the repo is mounted at /work, kas clones layers into
/work/yocto and bitbake runs in /work/yocto/bitbake, so its deploy dir is
yocto/bitbake/tmp/deploy/... in the repo.
"""

import logging
import os
import sys
from pathlib import Path

from aember.config.components import KAS_IMAGE
from aember.utils.runner import CommandRunner

log = logging.getLogger("aember.kas_container")

CONTAINER_ROOT = "/work"
WORK_DIR = "yocto"
BUILD_DIR = "yocto/bitbake"
# Share of the host CPUs the kas container may use (docker --cpus). Using all
# cores crashes WSL during big builds. Override with AEMBER_KAS_CPUS=<n>.
CPU_SHARE = 0.66


def host_root(root: Path) -> str:
    return os.environ.get("HOST_ROOT_PATH") or str(root)


def cpu_limit() -> str:
    override = os.environ.get("AEMBER_KAS_CPUS")
    if override:
        return override
    return f"{max(1.0, (os.cpu_count() or 1) * CPU_SHARE):.2f}"


def docker_args(root: Path, interactive: bool = False) -> list[str]:
    args = ["docker", "run", "--rm"]
    if interactive:
        args.append("-i")
    if interactive or sys.stdout.isatty():
        args.append("-t")
    args += [
        f"--cpus={cpu_limit()}",
        "-v",
        f"{host_root(root)}:{CONTAINER_ROOT}",
        "-w",
        CONTAINER_ROOT,
        # the entrypoint starts as root, remaps the "builder" user to these
        # ids, then drops privileges before running kas
        "--user=root",
        "-e",
        f"USER_ID={os.getuid()}",
        "-e",
        f"GROUP_ID={os.getgid()}",
        "-e",
        f"KAS_WORK_DIR={CONTAINER_ROOT}/{WORK_DIR}",
        "-e",
        f"KAS_BUILD_DIR={CONTAINER_ROOT}/{BUILD_DIR}",
        KAS_IMAGE,
    ]
    return args


def run_kas(root: Path, command: str, kas_files: list[str], *extra: str) -> None:
    """Run `kas <command> <chain> <extra...>` in the kas image."""
    (root / WORK_DIR).mkdir(parents=True, exist_ok=True)
    interactive = command == "shell" and not extra
    cmd = [*docker_args(root, interactive), command, ":".join(kas_files), *extra]
    log.debug("Running %s", " ".join(cmd))
    CommandRunner.run(cmd, cwd=root)
