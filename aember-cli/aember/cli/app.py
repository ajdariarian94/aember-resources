# aember/cli/app.py

import typer  # type: ignore
from aember.utils.logging import setup_logging

from .base.build import build
from .base.changelog import changelog
from .base.clean import clean
from .base.configure import configure
from .base.documentation import generate_docs, view_docs
from .base.hash import seed_hashes
from .base.launch import launch
from .base.lint import lint
from .base.pack import pack
from .base.release import release
from .qemu.build import build_qemu
from .qemu.launch import launch_qemu
from .yocto.build_busybox import build_busybox
from .yocto.build_kernel import build_kernel
from .yocto.build_lxc import build_lxc
from .yocto.build_sdk import build_sdk

aember = typer.Typer(help="Aember build system")


@aember.callback()
def main(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    )
):
    setup_logging(verbose)


# ----------------------------
# Aember sub-app
# ----------------------------
aember_app = typer.Typer(help="Aember related commands")

# ----------------------------
# Kernel sub-app
# ----------------------------
kernel_app = typer.Typer(help="Kernel related commands")

# ----------------------------
# Busybox sub-app
# ----------------------------
busybox_app = typer.Typer(help="Busybox related commands")

# ----------------------------
# Lxc sub-app
# ----------------------------
lxc_app = typer.Typer(help="Lxc related commands")

# ----------------------------
# sdk sub-app
# ----------------------------
sdk_app = typer.Typer(help="sdk related commands")

# ----------------------------
# qemu sub-app
# ----------------------------
qemu_app = typer.Typer(help="qemu related commands")

# ----------------------------
# Base commands
# ----------------------------
aember.command(help="Generate changelog and bump version")(changelog)
aember.command(help="Clean all build artifacts")(clean)
aember.command(help="Lint Python, C++, and CMake code")(lint)
aember.command(help="Generate project documentation")(generate_docs)
aember.command(help="Hash Artifacts")(seed_hashes)
aember.command(help="Create a release archive")(release)
aember.command(help="Serve documentation locally")(view_docs)

# ----------------------------
# Aember commands
# ----------------------------
aember_app.command("configure", help="Configure the project using CMake")(configure)
aember_app.command("build", help="Build the project using CMake")(build)
aember_app.command("pack", help="Package initramfs and root filesystem")(pack)
aember_app.command("launch", help="Run the system in QEMU")(launch)

# ----------------------------
# Yocto commands (subcommands)
# ----------------------------
kernel_app.command("build", help="Build the kernel with Yocto")(build_kernel)
busybox_app.command("build", help="Build BusyBox with Yocto")(build_busybox)
lxc_app.command("build", help="Build BusyBox with Yocto")(build_lxc)
sdk_app.command("build", help="Build sdk with Yocto")(build_sdk)

# ----------------------------
# Qemu commands (subcommands)
# ----------------------------
qemu_app.command("build", help="Build sdk with Yocto")(build_qemu)
qemu_app.command("launch", help="Build sdk with Yocto")(launch_qemu)


aember.add_typer(aember_app, name="app")
aember.add_typer(kernel_app, name="kernel")
aember.add_typer(busybox_app, name="busybox")
aember.add_typer(lxc_app, name="lxc")
aember.add_typer(sdk_app, name="sdk")
aember.add_typer(qemu_app, name="qemu")
