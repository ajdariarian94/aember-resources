# Maps build system architecture → target sysroot name inside the SDK
SDK_SYSROOT_MAP: dict[str, str] = {
    "x64-poky-linux": "core2-64-poky-linux",
    "aarch64-poky-linux": "cortexa53-poky-linux",
    "arm-poky-linux": "armv7at2hf-neon-poky-linux-gnueabi",
    "riscv64-poky-linux": "riscv64imafdc-poky-linux",
    "x64-poky-linux-musl": "core2-64-poky-linux-musl",
    "aarch64-poky-linux-musl": "cortexa53-poky-linux-musl",
    "arm-poky-linux-musl": "armv7at2hf-neon-poky-linux-musleabi",
    "riscv64-poky-linux-musl": "riscv64imafdc-poky-linux-musl",
}
