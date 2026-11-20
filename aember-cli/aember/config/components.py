from dataclasses import dataclass

KAS_BASE = "kas/base.yml"

# Layers versioned in this repo. Their files are part of every CAS key, since
# kas cannot pin them by commit.
LOCAL_LAYERS: list[str] = ["meta-aember"]

# Build host for every kas build, pinned by digest. It is part of the CAS key:
# changing it invalidates every artifact. Debian 13, kas 5.4 (format 23).
KAS_IMAGE = (
    "ghcr.io/siemens/kas/kas:5.4"
    "@sha256:11f076b79b84f57cb7d933941ff619f09a7c17e562e1643d13836d5f8d0a92f3"
)

# Build system architecture → kas machine file / Yocto MACHINE
MACHINE_MAP: dict[str, str] = {
    "x64-poky-linux": "x64-linux",
    "aarch64-poky-linux": "arm64-linux",
    "arm-poky-linux": "arm-linux",
    "riscv64-poky-linux": "riscv64-linux",
    "x64-poky-linux-musl": "x64-linux",
    "aarch64-poky-linux-musl": "arm64-linux",
    "arm-poky-linux-musl": "arm-linux",
}

# Build system architecture → C library. glibc unless listed: musl variants
# (`<arch>-musl`) are opt-in extras with the same MACHINE plus
# kas/libc/musl.yml in their chain.
LIBC_MAP: dict[str, str] = {
    "x64-poky-linux-musl": "musl",
    "aarch64-poky-linux-musl": "musl",
    "arm-poky-linux-musl": "musl",
}

KAS_LIBC_FILES: dict[str, str] = {
    "musl": "kas/libc/musl.yml",
}

KERNEL_IMAGE_MAP: dict[str, str] = {
    "x64-poky-linux": "bzImage",
    "aarch64-poky-linux": "Image",
    "arm-poky-linux": "zImage",
    "riscv64-poky-linux": "Image",
    "x64-poky-linux-musl": "bzImage",
    "aarch64-poky-linux-musl": "Image",
    "arm-poky-linux-musl": "zImage",
}


@dataclass(frozen=True)
class Component:
    name: str
    # kas recipe file, relative to the repo root
    kas_file: str
    # sub-directory of yocto/build/<arch>/ the artifact is collected into
    output_dir: str
    # sub-directory of tmp/deploy/images/<machine>/aember/ the recipe deploys
    # into (None: not a deploy-based component, e.g. the SDK installer)
    deploy_name: str | None


COMPONENTS: dict[str, Component] = {
    "kernel": Component("kernel", "kas/recipes/kernel.yml", "kernel", "kernel"),
    "busybox": Component("busybox", "kas/recipes/busybox.yml", "busybox", "busybox"),
    "lxc": Component("lxc", "kas/recipes/lxc.yml", "virtualization", "lxc"),
    "sdk": Component("sdk", "kas/recipes/sdk.yml", "sdk", None),
}


def get_component(name: str) -> Component:
    try:
        return COMPONENTS[name]
    except KeyError:
        raise ValueError(
            f"Unknown component '{name}'. Known: {list(COMPONENTS)}"
        ) from None


def get_machine(architecture: str) -> str:
    try:
        return MACHINE_MAP[architecture]
    except KeyError:
        raise ValueError(
            f"No kas machine for architecture '{architecture}'. "
            f"Known: {list(MACHINE_MAP)}"
        ) from None


def get_libc(architecture: str) -> str:
    """C library of an architecture: "glibc" or "musl"."""
    get_machine(architecture)  # unknown architecture -> ValueError
    return LIBC_MAP.get(architecture, "glibc")


def tmp_dir(architecture: str) -> str:
    """bitbake TMPDIR (relative to the build dir) of an architecture."""
    libc = get_libc(architecture)
    return "tmp" if libc == "glibc" else f"tmp-{libc}"


def kas_chain(component: Component, architecture: str) -> list[str]:
    """Ordered kas files (repo-relative) that describe one component build."""
    libc = get_libc(architecture)
    return [
        KAS_BASE,
        f"kas/machine/{get_machine(architecture)}.yml",
        *([KAS_LIBC_FILES[libc]] if libc in KAS_LIBC_FILES else []),
        component.kas_file,
    ]
