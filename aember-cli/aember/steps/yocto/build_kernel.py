import logging
import shutil
from pathlib import Path

from aember.core.context import Context
from aember.core.step import Step
from aember.utils.fetch_artifact import (
    fetch_artifact,
    fetch_hashes,
    fetch_recipe,
    get_version,
)
from aember.utils.recipe_hash import compute_recipe_hash, recipe_changed, store_hash
from aember.utils.runner import CommandRunner

log = logging.getLogger("yocto.kernel_build")

MACHINE_MAP: dict[str, str] = {
    "x64-poky-linux":     "x64-linux",
    "aarch64-poky-linux": "arm64-linux",
}

KERNEL_IMAGE_MAP: dict[str, str] = {
    "x64-poky-linux":     "bzImage",
    "aarch64-poky-linux": "Image",
}

RECIPE_REPO_PATH = "yocto/meta-aember/recipes/kernel/aember-kernel.bb"


class BuildKernel(Step):

    def recipe_path(self, ctx: Context) -> Path:
        return ctx.root / RECIPE_REPO_PATH

    def artifact_dir(self, ctx: Context) -> Path:
        return ctx.root / "yocto" / "build" / ctx.architecture / "kernel"

    def hashes_dir(self, ctx: Context) -> Path:
        return ctx.root / "yocto" / "hashes" / ctx.architecture

    def is_built(self, ctx: Context) -> bool:
        kernel_name = KERNEL_IMAGE_MAP.get(ctx.architecture)
        if not kernel_name:
            return False
        return (self.artifact_dir(ctx) / kernel_name).exists()

    def _ensure_recipe(self, ctx: Context) -> bool:
        if self.recipe_path(ctx).exists():
            return True
        log.info("Recipe not found locally — downloading from GitHub")
        return fetch_recipe(ctx.root, RECIPE_REPO_PATH, self.recipe_path(ctx))

    def _ensure_hashes(self, ctx: Context) -> bool:
        hash_file = self.hashes_dir(ctx) / "aember-kernel.sha256"
        if hash_file.exists():
            return True
        log.info("Hash files not found locally — downloading from GitHub Releases")
        return fetch_hashes(ctx.root, ctx.architecture)

    def _download_kernel(self, ctx: Context) -> bool:
        """
        Download kernel image and modules from GitHub Releases.

        Target structure:
          kernel/
          ├── bzImage
          ├── System.map
          ├── Module.symvers
          ├── kernel-build-manifest.txt
          └── lib/
              └── modules/
                  └── 6.6.68/
                      └── kernel/...

        kernel tar — no top-level dir → extract to tmp_dir, move files into artifact_dir
        modules tar — starts with modules/ → extract to tmp_dir, move modules/ into artifact_dir/lib/
        """
        version      = get_version(ctx.root)
        artifact_dir = self.artifact_dir(ctx)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        # ── Kernel image ──────────────────────────────────────────────────────
        artifact = f"aember-kernel-{ctx.architecture}-v{version}.tar.gz"
        tmp_dir  = ctx.root / "build" / "downloads" / "kernel_tmp"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)

        kernel_ok = fetch_artifact(ctx.root, artifact, tmp_dir)

        if kernel_ok and tmp_dir.exists():
            for f in tmp_dir.iterdir():
                dest = artifact_dir / f.name
                if dest.exists():
                    dest.unlink() if dest.is_file() else shutil.rmtree(dest)
                shutil.move(str(f), str(dest))
            shutil.rmtree(tmp_dir, ignore_errors=True)
            log.info("Kernel image files moved to %s", artifact_dir)

        # ── Kernel modules ────────────────────────────────────────────────────
        # modules tar contains modules/6.6.68/...
        # needs to land at kernel/lib/modules/6.6.68/...
        modules_artifact = f"aember-modules-{ctx.architecture}-v{version}.tar.gz"
        modules_tmp = ctx.root / "build" / "downloads" / "modules_tmp"
        shutil.rmtree(modules_tmp, ignore_errors=True)
        modules_tmp.mkdir(parents=True, exist_ok=True)

        modules_ok = fetch_artifact(ctx.root, modules_artifact, modules_tmp)

        if modules_ok and modules_tmp.exists():
            lib_dir = artifact_dir / "lib"
            lib_dir.mkdir(parents=True, exist_ok=True)
            modules_src = modules_tmp / "modules"
            if modules_src.exists():
                dest = lib_dir / "modules"
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.move(str(modules_src), str(lib_dir))
                log.info("Modules moved to %s", lib_dir / "modules")
            shutil.rmtree(modules_tmp, ignore_errors=True)
        else:
            log.warning("Failed to download modules — continuing without them")

        return kernel_ok

    def should_build(self, ctx: Context) -> bool:
        if ctx.force:
            log.info("--force specified, rebuilding kernel")
            return True

        if not self._ensure_recipe(ctx):
            log.warning("Could not obtain recipe — building from source")
            return True

        if not self._ensure_hashes(ctx):
            log.warning("Could not obtain hashes — building from source")
            return True

        if recipe_changed(ctx.root, ctx.architecture, self.recipe_path(ctx)):
            log.info("Kernel recipe changed — rebuilding from source")
            return True

        if not self.is_built(ctx):
            log.info("Kernel artifact missing — trying GitHub Releases")
            if self._download_kernel(ctx):
                log.info("Downloaded kernel + modules — skipping build")
                return False
            log.info("Download failed — building from source")
            return True

        log.info("Kernel up to date — skipping")
        return False

    def run(self, ctx: Context) -> None:
        if not self.should_build(ctx):
            log.info(
                "Kernel already built and recipe unchanged for '%s', skipping",
                ctx.architecture,
            )
            return

        machine = MACHINE_MAP.get(ctx.architecture)
        if not machine:
            raise ValueError(
                f"No Yocto MACHINE mapping for architecture '{ctx.architecture}'. "
                f"Known: {list(MACHINE_MAP)}"
            )

        log.info("Building kernel for architecture '%s' (MACHINE=%s)",
                 ctx.architecture, machine)

        yocto_cmd = f"""
            export MACHINE={machine} &&
            source {ctx.root}/yocto/poky/oe-init-build-env {ctx.root}/yocto/resources &&
            bitbake aember-kernel
        """

        CommandRunner.run(yocto_cmd, shell=True)

        store_hash(
            ctx.root,
            ctx.architecture,
            self.recipe_path(ctx).stem,
            compute_recipe_hash(self.recipe_path(ctx)),
        )
        log.info("Stored recipe hash for '%s'", self.recipe_path(ctx).name)
        