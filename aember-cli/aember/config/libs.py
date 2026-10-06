from pathlib import Path
from typing import Dict, List

# ---------------------------------------------------------------------------
# Architecture configuration
# ---------------------------------------------------------------------------

ARCH_CONFIG = {
    "x64-poky-linux": {
        "gcc_reflection_root": Path(
            "/aember_ws/aember/yocto/build/x64-poky-linux/gcc-reflection/install"
        ),
        "poky_sysroot": Path(
            "/aember_ws/aember/yocto/build/x64-poky-linux/sdk/sysroots/core2-64-poky-linux"
        ),
        "virt_libs": Path(
            "/aember_ws/aember/yocto/build/x64-poky-linux/virtualization/libs"
        ),
        "loader_name": "ld-linux-x86-64.so.2",
        "loader_dir": "lib64",
        "gcc_lib_dirs": ["lib", "lib64", "lib/x86_64-linux-gnu"],
    },
    "aarch64-poky-linux": {
        "gcc_reflection_root": Path(
            "/aember_ws/aember/yocto/build/aarch64-poky-linux/gcc-reflection/install"
        ),
        "poky_sysroot": Path(
            "/aember_ws/aember/yocto/build/aarch64-poky-linux/sdk/sysroots/cortexa57-poky-linux"
        ),
        "virt_libs": Path(
            "/aember_ws/aember/yocto/build/aarch64-poky-linux/virtualization/libs"
        ),
        "loader_name": "ld-linux-aarch64.so.1",
        "loader_dir": "lib",
        "gcc_lib_dirs": ["aarch64-poky-linux/lib64"],
    },
}

# Maps build system architecture → kernel modules lib path
KERNEL_MODULES_BASE: Dict[str, str] = {
    "x64-poky-linux": "yocto/build/x64-poky-linux/kernel/lib",
    "aarch64-poky-linux": "yocto/build/aarch64-poky-linux/kernel/lib",
}

# Modules always packed on all architectures
BASE_MODULES: Dict[str, List[str]] = {
    "x64-poky-linux": ["llc", "stp", "bridge", "veth", "br_netfilter"],
    "aarch64-poky-linux": ["llc", "stp", "ipv6", "bridge", "veth", "br_netfilter"],
}

# Debug-only modules
DEBUG_ONLY_MODULES: Dict[str, List[str]] = {
    "x64-poky-linux": ["netconsole"],
    "aarch64-poky-linux": [],
}
