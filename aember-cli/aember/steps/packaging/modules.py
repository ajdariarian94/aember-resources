import json
import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("aember.pack")

# Maps build system architecture → kernel modules lib path
KERNEL_MODULES_BASE: dict[str, str] = {
    "x64-poky-linux": "yocto/build/x64-poky-linux/kernel/lib",
    "aarch64-poky-linux": "yocto/build/aarch64-poky-linux/kernel/lib",
}


def _modules_json_path(root: Path, architecture: str) -> Path:
    """Path to modules.json in the rootfs overlay for this architecture."""
    return (
        root / "resources" / architecture / "rootfs" / "etc" / "aember" / "modules.json"
    )


def _load_modules(root: Path, architecture: str) -> list[str]:
    """
    Load module list from resources/<architecture>/rootfs/etc/aember/modules.json.
    Falls back to empty list if file not found.
    """
    path = _modules_json_path(root, architecture)
    if not path.exists():
        log.warning("modules.json not found at %s — no modules will be packed", path)
        return []

    cfg = json.loads(path.read_text())
    modules = cfg.get("modules", [])
    log.info("Loaded %d module(s) from %s", len(modules), path)
    return modules


def _find_kernel_version(modules_lib_root: Path) -> str | None:
    modules_dir = modules_lib_root / "modules"
    if not modules_dir.exists():
        return None
    versions = [d.name for d in modules_dir.iterdir() if d.is_dir()]
    return versions[0] if len(versions) == 1 else None


def _find_module_file(version_dir: Path, module_name: str) -> Path | None:
    normalized = module_name.replace("-", "_")
    dashed = module_name.replace("_", "-")

    for candidate in [
        f"{normalized}.ko",
        f"{dashed}.ko",
        f"{normalized}.ko.gz",
        f"{dashed}.ko.gz",
        f"{normalized}.ko.xz",
        f"{dashed}.ko.xz",
        f"{normalized}.ko.zst",
        f"{dashed}.ko.zst",
    ]:
        matches = list(version_dir.rglob(candidate))
        if matches:
            return matches[0]

    return None


def _decompress_module(ko_path: Path) -> Path:
    suffixes = "".join(ko_path.suffixes)

    if suffixes.endswith(".ko.zst"):
        cmd = ["zstd", "-d", str(ko_path), "--rm"]
    elif suffixes.endswith(".ko.gz"):
        cmd = ["gunzip", str(ko_path)]
    elif suffixes.endswith(".ko.xz"):
        cmd = ["unxz", str(ko_path)]
    else:
        return ko_path

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Decompression failed for {ko_path.name}: {result.stderr}")
    return ko_path.with_suffix("")


def _run_depmod(rootfs_root: Path, kernel_version: str) -> None:
    log.info("Running depmod for %s", kernel_version)
    result = subprocess.run(
        ["depmod", "-b", str(rootfs_root), kernel_version],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log.warning("depmod failed: %s", result.stderr)
    else:
        log.info("depmod completed successfully")


def copy_kernel_modules(
    architecture: str,
    root: Path,
    rootfs_root: Path,
    build_type: str,
    extra_modules: list[str] | None = None,
) -> None:
    """
    Copy kernel modules into the rootfs at /lib/modules/<kernel_version>/.

    Module list is loaded dynamically from:
      resources/<architecture>/rootfs/etc/aember/modules.json

    Additional modules can be passed via extra_modules (e.g. debug-only ones).

    @param architecture   Build system architecture e.g. "aarch64-poky-linux".
    @param root           Project root (ctx.root).
    @param rootfs_root    Root of the target rootfs being assembled.
    @param build_type     "Debug" or "Release".
    @param extra_modules  Optional additional modules to pack on top of modules.json.
    """
    rel_path = KERNEL_MODULES_BASE.get(architecture)
    if not rel_path:
        raise ValueError(
            f"Unsupported architecture: '{architecture}'. "
            f"Known: {list(KERNEL_MODULES_BASE)}"
        )

    modules_lib_root = root / rel_path

    if not modules_lib_root.exists():
        raise FileNotFoundError(
            f"Kernel modules lib not found at {modules_lib_root}. "
            f"Run 'bitbake aember-kernel' first."
        )

    kernel_version = _find_kernel_version(modules_lib_root)
    if not kernel_version:
        raise RuntimeError(f"Could not detect kernel version under {modules_lib_root}.")

    log.info("Kernel version: %s", kernel_version)

    # ---------------------------------------------------------------------------
    # Load module list from modules.json — single source of truth
    # ---------------------------------------------------------------------------
    module_names = _load_modules(root, architecture)

    if extra_modules:
        module_names.extend(m for m in extra_modules if m not in module_names)
        log.info("Added %d extra module(s): %s", len(extra_modules), extra_modules)

    # Deduplicate preserving order.
    unique_modules = list(dict.fromkeys(module_names))

    log.info("Packing %d module(s): %s", len(unique_modules), ", ".join(unique_modules))

    # ---------------------------------------------------------------------------
    # Copy modules
    # ---------------------------------------------------------------------------
    src_version_dir = modules_lib_root / "modules" / kernel_version
    dst_version_dir = rootfs_root / "lib" / "modules" / kernel_version
    dst_version_dir.mkdir(parents=True, exist_ok=True)

    missing: list[str] = []
    copied: list[str] = []

    for mod_name in unique_modules:
        ko_path = _find_module_file(src_version_dir, mod_name)

        if ko_path is None:
            log.warning("Module '%s' not found under %s", mod_name, src_version_dir)
            missing.append(mod_name)
            continue

        rel = ko_path.relative_to(src_version_dir)
        dst_file = dst_version_dir / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ko_path, dst_file)

        if dst_file.suffix in (".zst", ".gz", ".xz"):
            try:
                dst_file = _decompress_module(dst_file)
                log.info("Packed + decompressed: %s", rel)
            except RuntimeError as e:
                log.warning("%s", e)
        else:
            log.info("Packed: %s", rel)

        copied.append(str(rel))

    log.info("Done: %d packed, %d missing", len(copied), len(missing))

    if missing:
        raise RuntimeError(
            f"Missing kernel modules for '{architecture}': {missing}. "
            f"Ensure they are compiled (=m) in your kernel config."
        )

    _run_depmod(rootfs_root, kernel_version)
