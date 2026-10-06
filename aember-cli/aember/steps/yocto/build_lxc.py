import logging
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

log = logging.getLogger("yocto.lxc_build")

ARCH_TO_MACHINE: dict[str, str] = {
    "x64-poky-linux":     "x64-linux",
    "aarch64-poky-linux": "arm64-linux",
}

RECIPE_REPO_PATH = "yocto/meta-aember/recipes/virtualization/aember-lxc.bb"


class BuildLxc(Step):

    def recipe_path(self, ctx: Context) -> Path:
        return ctx.root / RECIPE_REPO_PATH

    def artifact_dir(self, ctx: Context) -> Path:
        return ctx.root / "yocto" / "build" / ctx.architecture / "virtualization"

    def hashes_dir(self, ctx: Context) -> Path:
        return ctx.root / "yocto" / "hashes" / ctx.architecture

    def is_built(self, ctx: Context) -> bool:
        return (self.artifact_dir(ctx) / "libs" / "liblxc.so").exists()

    def _ensure_recipe(self, ctx: Context) -> bool:
        if self.recipe_path(ctx).exists():
            return True
        log.info("Recipe not found locally — downloading from GitHub")
        return fetch_recipe(ctx.root, RECIPE_REPO_PATH, self.recipe_path(ctx))

    def _ensure_hashes(self, ctx: Context) -> bool:
        hash_file = self.hashes_dir(ctx) / "aember-lxc.sha256"
        if hash_file.exists():
            return True
        log.info("Hash files not found locally — downloading from GitHub Releases")
        return fetch_hashes(ctx.root, ctx.architecture)

    def should_build(self, ctx: Context) -> bool:
        if ctx.force:
            log.info("--force specified, rebuilding LXC")
            return True

        if not self._ensure_recipe(ctx):
            log.warning("Could not obtain recipe — building from source")
            return True

        if not self._ensure_hashes(ctx):
            log.warning("Could not obtain hashes — building from source")
            return True

        if recipe_changed(ctx.root, ctx.architecture, self.recipe_path(ctx)):
            log.info("LXC recipe changed — rebuilding from source")
            return True

        if not self.is_built(ctx):
            log.info("LXC artifact missing — trying GitHub Releases")
            version  = get_version(ctx.root)
            artifact = f"aember-lxc-{ctx.architecture}-v{version}.tar.gz"
            if fetch_artifact(ctx.root, artifact, self.artifact_dir(ctx).parent):
                log.info("Downloaded LXC artifact — skipping build")
                return False
            log.info("Download failed — building from source")
            return True

        log.info("LXC up to date — skipping")
        return False

    def run(self, ctx: Context) -> None:
        if not self.should_build(ctx):
            log.info(
                "LXC already built and recipe unchanged for '%s', skipping",
                ctx.architecture,
            )
            return

        machine = ARCH_TO_MACHINE.get(ctx.architecture)
        if not machine:
            raise ValueError(
                f"No Yocto MACHINE mapping for architecture '{ctx.architecture}'. "
                f"Known: {list(ARCH_TO_MACHINE)}"
            )

        log.info("Building LXC for architecture '%s' (MACHINE=%s)",
                 ctx.architecture, machine)

        yocto_cmd = f"""
            export MACHINE={machine} &&
            source {ctx.root}/yocto/poky/oe-init-build-env {ctx.root}/yocto/resources &&
            bitbake aember-lxc -c deploy -f
        """

        CommandRunner.run(yocto_cmd, shell=True)

        store_hash(
            ctx.root,
            ctx.architecture,
            self.recipe_path(ctx).stem,
            compute_recipe_hash(self.recipe_path(ctx)),
        )
        log.info("Stored recipe hash for '%s'", self.recipe_path(ctx).name)
        