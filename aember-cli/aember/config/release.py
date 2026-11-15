"""
Release assets of aember-resources.

Every built component is published as one asset of the GitHub release
v<VERSION>:

  aember-<component>-<arch>-v<VERSION>.zip   kernel, busybox, lxc: the output dir
  aember-sdk-<arch>-v<VERSION>.sh            the SDK installer (self-relocating)
  manifest.json                              version, kas hash + sha256 per asset
  SHA256SUMS                                 `sha256sum -c` list of all assets

The SDK ships as its installer, not as a zip of the installed tree: the
installed SDK is ~4 GB (GitHub caps assets at 2 GiB), holds >1000 symlinks and
has the install path baked into its scripts and binaries. The consumer runs
`<installer> -d <dir> -y` wherever it wants the SDK.
"""

from aember.config.components import Component

# Staging dir for packed assets, relative to the repo root (git-ignored)
RELEASE_DIR = "build/release"

# Download dir for fetched assets, relative to the repo root (git-ignored)
DOWNLOAD_DIR = "build/downloads"

# Per-asset metadata written by `aember pack`, inside the release dir
META_DIR = ".meta"

MANIFEST = "manifest.json"
CHECKSUMS = "SHA256SUMS"

# Local copy of the SDK installer, next to the installed SDK in
# yocto/build/<arch>/. Kept so the SDK can be packed after it was fetched.
SDK_INSTALLER = "sdk-installer.sh"


def release_tag(version: str) -> str:
    return f"v{version}"


def is_installer(component: Component) -> bool:
    """The SDK is the only component that ships as an installer."""
    return component.deploy_name is None


def asset_name(component: Component, architecture: str, version: str) -> str:
    ext = "sh" if is_installer(component) else "zip"
    return f"aember-{component.name}-{architecture}-v{version}.{ext}"
