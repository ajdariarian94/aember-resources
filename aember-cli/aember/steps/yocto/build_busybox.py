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

log = logging.getLogger("yocto.busybox_build")

MACHINE_MAP: dict[str, str] = {
    "x64-poky-linux":     "x64-linux",
    "aarch64-poky-linux": "arm64-linux",
}

RECIPE_REPO_PATH = "yocto/meta-aember/recipes/busybox/aember-busybox.bb"


class BuildBusybox(Step):

    def recipe_path(self, ctx: Context) -> Path:
        return ctx.root / RECIPE_REPO_PATH

    def artifact_dir(self, ctx: Context) -> Path:
        return ctx.root / "yocto" / "build" / ctx.architecture / "busybox"

    def hashes_dir(self, ctx: Context) -> Path:
        return ctx.root / "yocto" / "hashes" / ctx.architecture

    def is_built(self, ctx: Context) -> bool:
        return (self.artifact_dir(ctx) / "busybox").exists()

    def _ensure_recipe(self, ctx: Context) -> bool:
        if self.recipe_path(ctx).exists():
            return True
        log.info("Recipe not found locally — downloading from GitHub")
        return fetch_recipe(ctx.root, RECIPE_REPO_PATH, self.recipe_path(ctx))

    def _ensure_hashes(self, ctx: Context) -> bool:
        hash_file = self.hashes_dir(ctx) / "aember-busybox.sha256"
        if hash_file.exists():
            return True
        log.info("Hash files not found locally — downloading from GitHub Releases")
        return fetch_hashes(ctx.root, ctx.architecture)

    def _download_busybox(self, ctx: Context) -> bool:
        """
        Download busybox from GitHub Releases.
        Tar contains busybox/ top-level dir → extract to tmp, move contents into artifact_dir.
        """
        version  = get_version(ctx.root)
        artifact = f"aember-busybox-{ctx.architecture}-v{version}.tar.gz"
        tmp_dir  = ctx.root / "build" / "downloads" / "busybox_tmp"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)

        ok = fetch_artifact(ctx.root, artifact, tmp_dir)

        if ok and tmp_dir.exists():
            # tar extracts to tmp_dir/busybox/ — move contents into artifact_dir
            busybox_src = tmp_dir / "busybox"
            self.artifact_dir(ctx).mkdir(parents=True, exist_ok=True)
            if busybox_src.exists():
                for f in busybox_src.iterdir():
                    dest = self.artifact_dir(ctx) / f.name
                    if dest.exists():
                        dest.unlink() if dest.is_file() else shutil.rmtree(dest)
                    shutil.move(str(f), str(dest))
            shutil.rmtree(tmp_dir, ignore_errors=True)
            log.info("BusyBox extracted to %s", self.artifact_dir(ctx))

        return ok

    def should_build(self, ctx: Context) -> bool:
        if ctx.force:
            log.info("--force specified, rebuilding BusyBox")
            return True

        if not self._ensure_recipe(ctx):
            log.warning("Could not obtain recipe — building from source")
            return True

        if not self._ensure_hashes(ctx):
            log.warning("Could not obtain hashes — building from source")
            return True

        if recipe_changed(ctx.root, ctx.architecture, self.recipe_path(ctx)):
            log.info("BusyBox recipe changed — rebuilding from source")
            return True

        if not self.is_built(ctx):
            log.info("BusyBox artifact missing — trying GitHub Releases")
            if self._download_busybox(ctx):
                log.info("Downloaded busybox — skipping build")
                return False
            log.info("Download failed — building from source")
            return True

        log.info("BusyBox up to date — skipping")
        return False

    def run(self, ctx: Context) -> None:
        if not self.should_build(ctx):
            log.info(
                "BusyBox already built and recipe unchanged for '%s', skipping",
                ctx.architecture,
            )
            return

        machine = MACHINE_MAP.get(ctx.architecture)
        if not machine:
            raise ValueError(
                f"No Yocto MACHINE mapping for architecture '{ctx.architecture}'. "
                f"Known: {list(MACHINE_MAP)}"
            )

        log.info("Building BusyBox for architecture '%s' (MACHINE=%s)",
                 ctx.architecture, machine)

        yocto_cmd = f"""
            export MACHINE={machine} &&
            source {ctx.root}/yocto/poky/oe-init-build-env {ctx.root}/yocto/resources &&
            bitbake aember-busybox
        """

        CommandRunner.run(yocto_cmd, shell=True)

        store_hash(
            ctx.root,
            ctx.architecture,
            self.recipe_path(ctx).stem,
            compute_recipe_hash(self.recipe_path(ctx)),
        )
        log.info("Stored recipe hash for '%s'", self.recipe_path(ctx).name)
        