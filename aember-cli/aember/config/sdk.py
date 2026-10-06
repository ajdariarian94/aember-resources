# Maps build system architecture → SDK environment-setup filename
SDK_ENV_MAP: dict[str, str] = {
    "x64-poky-linux": "environment-setup-core2-64-poky-linux",
    "aarch64-poky-linux": "environment-setup-cortexa57-poky-linux",
}

# Maps build system architecture → vcpkg triplet
VCPKG_TRIPLET_MAP: dict[str, str] = {
    "x64-poky-linux": "x64-poky-linux",
    "aarch64-poky-linux": "aarch64-poky-linux",
}
