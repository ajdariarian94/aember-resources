import hashlib
import logging
import tarfile
from pathlib import Path

from aember.core.context import Context
from aember.core.step import Step

from .get_version_from_cmake import get_version_from_cmake

log = logging.getLogger("aember.release")

# GitHub Releases file size limit
GITHUB_MAX_BYTES = 2 * 1024 * 1024 * 1024  # 2GB

# Kernel module extensions to include
MODULE_EXTENSIONS = {".ko", ".ko.gz", ".ko.xz", ".ko.zst"}


def _pack(tar_path: Path, src_dir: Path, arcname: str | None = None) -> None:
    """Pack src_dir into tar_path as tar.gz."""
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(src_dir, arcname=arcname or src_dir.name)
    size_mb = tar_path.stat().st_size / (1024 * 1024)
    if tar_path.stat().st_size > GITHUB_MAX_BYTES:
        raise RuntimeError(
            f"{tar_path.name} exceeds GitHub 2GB limit ({size_mb:.0f} MB). "
            f"Split it manually before uploading."
        )
    log.info("  ✅ %s (%.1f MB)", tar_path.name, size_mb)


def _pack_kernel_modules(
    tar_path: Path,
    modules_lib: Path,
    needed_modules: list[str],
) -> None:
    """Pack only needed kernel modules + depmod metadata."""
    if not modules_lib.exists():
        log.warning("Kernel modules lib not found: %s", modules_lib)
        return

    modules_dir = modules_lib / "modules"
    versions = (
        [d for d in modules_dir.iterdir() if d.is_dir()] if modules_dir.exists() else []
    )
    if not versions:
        log.warning("No kernel version directory found under %s", modules_lib)
        return

    version_dir = versions[0]
    log.info("Packing kernel modules (version=%s)", version_dir.name)

    with tarfile.open(tar_path, "w:gz") as tar:
        for meta in [
            "modules.dep",
            "modules.alias",
            "modules.symbols",
            "modules.dep.bin",
            "modules.alias.bin",
            "modules.symbols.bin",
        ]:
            meta_path = version_dir / meta
            if meta_path.exists():
                tar.add(meta_path, arcname=f"modules/{version_dir.name}/{meta}")

        for mod_name in needed_modules:
            normalized = mod_name.replace("-", "_")
            dashed = mod_name.replace("_", "-")
            found = False

            for candidate in [normalized, dashed]:
                for ext in MODULE_EXTENSIONS:
                    matches = list(version_dir.rglob(f"{candidate}{ext}"))
                    if matches:
                        rel = matches[0].relative_to(version_dir)
                        tar.add(matches[0], arcname=f"modules/{version_dir.name}/{rel}")
                        found = True
                        break
                if found:
                    break

            if not found:
                log.warning("Module '%s' not found — skipping", mod_name)

    size_mb = tar_path.stat().st_size / (1024 * 1024)
    log.info("  ✅ %s (%.1f MB)", tar_path.name, size_mb)


def _load_needed_modules(root: Path, architecture: str) -> list[str]:
    import json

    path = (
        root / "resources" / architecture / "rootfs" / "etc" / "aember" / "modules.json"
    )
    if not path.exists():
        log.warning("modules.json not found at %s — packing no modules", path)
        return []
    cfg = json.loads(path.read_text())
    return cfg.get("modules", [])


class ReleaseStep(Step):

    def _version(self, ctx: Context) -> str:
        cmake_file = ctx.root / "CMakeLists.txt"
        return get_version_from_cmake(str(cmake_file))

    def _release_dir(self, ctx: Context) -> Path:
        release_dir = ctx.root / "build" / "release" / ctx.architecture / ctx.build_type
        release_dir.mkdir(parents=True, exist_ok=True)
        return release_dir

    def _sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _pack_resources(self, ctx: Context) -> Path:
        """Pack resources/ folder into a single tar for both architectures."""
        resources_dir = ctx.root / "resources"
        if not resources_dir.exists():
            log.warning("No resources directory found — skipping")
            return None

        artifact = (
            self._release_dir(ctx) / f"aember-resources-v{self._version(ctx)}.tar.gz"
        )

        log.info("Packing resources → %s", artifact.name)

        with tarfile.open(artifact, "w:gz") as tar:
            tar.add(
                resources_dir,
                arcname="resources",
                filter=lambda t: None if t.name.endswith(".gitkeep") else t,
            )

        # Store hash
        sha256 = self._sha256(artifact)
        hash_file = ctx.root / "yocto" / "hashes" / "aember-resources.sha256"
        hash_file.write_text(sha256)
        log.info("Resources hash: %s", sha256)

        return artifact

    def run(self, ctx: Context) -> None:
        log.info(
            "Creating release artifacts for '%s' / '%s'",
            ctx.architecture,
            ctx.build_type,
        )

        root = ctx.root
        cmake_file = root / "CMakeLists.txt"

        if not cmake_file.exists():
            raise FileNotFoundError(f"CMakeLists.txt not found at {cmake_file}")

        version = get_version_from_cmake(str(cmake_file))
        log.info("Version: %s", version)

        arch = ctx.architecture
        build_type = ctx.build_type
        release_dir = root / "build" / "release" / arch / build_type
        release_dir.mkdir(parents=True, exist_ok=True)

        yocto_build = root / "yocto" / "build" / arch

        # ---------------------------------------------------------------------------
        # Resources (shared across architectures/build types)
        # ---------------------------------------------------------------------------
        self._pack_resources(ctx)

        # ---------------------------------------------------------------------------
        # Aember app package (initramfs + kernel image + rootfs image)
        # ---------------------------------------------------------------------------
        package_dir = root / "build" / "package" / arch / build_type
        if package_dir.exists():
            tar_path = release_dir / f"aember-app-{arch}-{build_type}-v{version}.tar.gz"
            log.info("Packing aember app package")
            with tarfile.open(tar_path, "w:gz") as tar:
                for f in package_dir.iterdir():
                    if f.name != "initramfs_root":  # skip unpacked tree
                        tar.add(f, arcname=f.name)
            size_mb = tar_path.stat().st_size / (1024 * 1024)
            log.info("  ✅ %s (%.1f MB)", tar_path.name, size_mb)
        else:
            log.warning("Package dir not found: %s", package_dir)

        # ---------------------------------------------------------------------------
        # Aember binary only (for users who want just the executable)
        # ---------------------------------------------------------------------------
        aember_bin = root / "build" / "install" / arch / build_type / "bin" / "aember"
        if aember_bin.exists():
            tar_path = (
                release_dir / f"aember-binary-{arch}-{build_type}-v{version}.tar.gz"
            )
            log.info("Packing aember binary")
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(aember_bin, arcname="aember")
            size_mb = tar_path.stat().st_size / (1024 * 1024)
            log.info("  ✅ %s (%.1f MB)", tar_path.name, size_mb)

        # ---------------------------------------------------------------------------
        # Yocto artifacts — only pack once (Release build type to avoid duplicates)
        # ---------------------------------------------------------------------------
        if build_type.lower() != "release":
            log.info("Skipping Yocto artifacts for build type '%s'", build_type)
            self._log_summary(release_dir, version)
            return

        # Kernel image only
        kernel_dir = yocto_build / "kernel"
        if kernel_dir.exists():
            tar_path = release_dir / f"aember-kernel-{arch}-v{version}.tar.gz"
            log.info("Packing kernel image")
            kernel_image = "bzImage" if "x64" in arch else "Image"
            include_names = {
                kernel_image,
                "System.map",
                "Module.symvers",
                "kernel-build-manifest.txt",
            }
            with tarfile.open(tar_path, "w:gz") as tar:
                for f in kernel_dir.iterdir():
                    if f.name in include_names:
                        tar.add(f, arcname=f.name)
            size_mb = tar_path.stat().st_size / (1024 * 1024)
            log.info("  ✅ %s (%.1f MB)", tar_path.name, size_mb)

        # Kernel modules — only needed ones from modules.json
        needed_modules = _load_needed_modules(root, arch)
        if needed_modules:
            modules_tar = release_dir / f"aember-modules-{arch}-v{version}.tar.gz"
            log.info("Packing kernel modules: %s", ", ".join(needed_modules))
            _pack_kernel_modules(modules_tar, kernel_dir / "lib", needed_modules)

        # BusyBox
        busybox_dir = yocto_build / "busybox"
        if busybox_dir.exists():
            tar_path = release_dir / f"aember-busybox-{arch}-v{version}.tar.gz"
            log.info("Packing BusyBox")
            _pack(tar_path, busybox_dir)

        # LXC
        lxc_dir = yocto_build / "virtualization"
        if lxc_dir.exists():
            tar_path = release_dir / f"aember-lxc-{arch}-v{version}.tar.gz"
            log.info("Packing LXC")
            _pack(tar_path, lxc_dir)

        # gcc-reflection — install/ only
        gcc_install = yocto_build / "gcc-reflection" / "install"
        if gcc_install.exists():
            tar_path = release_dir / f"aember-gcc-reflection-{arch}-v{version}.tar.gz"
            log.info("Packing gcc-reflection (install/ only)")
            _pack(tar_path, gcc_install, arcname="gcc-reflection")

        # SDK
        sdk_dir = yocto_build / "sdk"
        if sdk_dir.exists():
            tar_path = release_dir / f"aember-sdk-{arch}-v{version}.tar.gz"
            log.info("Packing SDK (this may be large)")
            try:
                _pack(tar_path, sdk_dir)
            except RuntimeError as e:
                log.warning("%s", e)

        # Hash files
        hashes_dir = root / "yocto" / "hashes" / arch
        if hashes_dir.exists():
            tar_path = release_dir / f"aember-hashes-{arch}-v{version}.tar.gz"
            log.info("Packing hash files")
            _pack(tar_path, hashes_dir, arcname=arch)
        else:
            log.warning(
                "Hash directory not found: %s (run 'aember app seed-hashes' first)",
                hashes_dir,
            )

        self._log_summary(release_dir, version)

    def _log_summary(self, release_dir: Path, version: str) -> None:
        log.info("Release artifacts written to: %s", release_dir)
        log.info("Upload to GitHub Releases v%s:", version)
        total_mb = 0.0
        for f in sorted(release_dir.iterdir()):
            size_mb = f.stat().st_size / (1024 * 1024)
            total_mb += size_mb
            log.info("  📦 %s (%.1f MB)", f.name, size_mb)
        log.info("Total: %.1f MB", total_mb)
