import logging
import shutil
from pathlib import Path

from aember.config.components import (
    KAS_IMAGE,
    KERNEL_IMAGE_MAP,
    LOCAL_LAYERS,
    Component,
    get_libc,
    get_machine,
    kas_chain,
    tmp_dir,
)
from aember.config.release import SDK_INSTALLER, asset_name, is_installer
from aember.config.sdk import SDK_SYSROOT_MAP
from aember.core.context import Context
from aember.core.step import Step
from aember.utils.fetch_artifact import fetch_artifact, fetch_file, get_version
from aember.utils.kas_hash import (
    compute_kas_hash,
    read_local_hash,
    read_published_hash,
    store_local_hash,
    store_published_hash,
)
from aember.utils.kas_container import BUILD_DIR, WORK_DIR, run_kas
from aember.utils.runner import CommandRunner

log = logging.getLogger("aember.kas")


class KasBuild(Step):
    """Build one component with kas, or reuse it if its CAS key is unchanged."""

    def __init__(self, component: Component) -> None:
        self.component = component

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def output_dir(self, ctx: Context) -> Path:
        return (
            ctx.root / WORK_DIR / "build" / ctx.architecture / self.component.output_dir
        )

    def installer_path(self, ctx: Context) -> Path:
        """Local copy of the SDK installer (the SDK's release asset)."""
        return ctx.root / WORK_DIR / "build" / ctx.architecture / SDK_INSTALLER

    def asset_name(self, ctx: Context) -> str:
        return asset_name(self.component, ctx.architecture, get_version(ctx.root))

    def is_present(self, ctx: Context) -> bool:
        out = self.output_dir(ctx)
        name = self.component.name
        if name == "kernel":
            return (out / KERNEL_IMAGE_MAP[ctx.architecture]).is_file()
        if name == "busybox":
            return (out / "busybox").is_file()
        if name == "lxc":
            return any((out / "libs").glob("liblxc.so*"))
        if self.component.package:
            return (out / "packages.txt").is_file() and any(
                p.is_file() for p in (out / "rootfs").rglob("*")
            )
        if name == "sdk":
            return (
                out / "sysroots" / SDK_SYSROOT_MAP[ctx.architecture]
            ).is_dir() and self.installer_path(ctx).is_file()
        return out.is_dir() and any(out.iterdir())

    # ------------------------------------------------------------------
    # CAS decision
    # ------------------------------------------------------------------

    def should_build(self, ctx: Context, key: str) -> bool:
        name = self.component.name
        out = self.output_dir(ctx)

        if ctx.force:
            log.info("--force specified, rebuilding %s", name)
            return True

        if self.is_present(ctx) and read_local_hash(out) == key:
            log.info("%s up to date (%s...) — skipping", name, key[:12])
            return False

        published = read_published_hash(ctx.root, ctx.architecture, name)
        if published != key:
            log.info(
                "%s: no published artifact for key %s... (published=%s) — building",
                name,
                key[:12],
                published[:12] if published else None,
            )
            return True

        log.info("%s: published artifact matches — downloading", name)
        if self._fetch(ctx) and self.is_present(ctx):
            store_local_hash(out, key)
            return False

        log.info("%s: download failed — building from source", name)
        return True

    def _fetch(self, ctx: Context) -> bool:
        """Download the release asset into the output dir. Never raises."""
        out = self.output_dir(ctx)
        shutil.rmtree(out, ignore_errors=True)
        if not is_installer(self.component):
            return fetch_artifact(ctx.root, self.asset_name(ctx), out)
        installer = self.installer_path(ctx)
        if not fetch_file(ctx.root, self.asset_name(ctx), installer):
            return False
        try:
            self._run_installer(installer, out)
            return True
        except Exception as e:
            log.warning("SDK installer %s failed: %s", installer, e)
            return False

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _collect(self, ctx: Context) -> None:
        """
        Copy the recipe's deploy output into yocto/build/<arch>/<output_dir>/.

        Recipes deploy into tmp/deploy/images/<machine>/aember/<name>/, which
        bitbake restores from sstate even when do_deploy is not re-run, so
        this is always the artifact of the current build. The output dir is
        replaced as a whole so no stale files survive.
        """
        machine = get_machine(ctx.architecture)
        src = (
            ctx.root
            / BUILD_DIR
            / tmp_dir(ctx.architecture)
            / "deploy"
            / "images"
            / machine
            / "aember"
            / self.component.deploy_name
        )
        if not src.is_dir():
            raise RuntimeError(f"Deploy output not found: {src}")
        out = self.output_dir(ctx)
        shutil.rmtree(out, ignore_errors=True)
        shutil.copytree(src, out, symlinks=True)
        log.info("Collected %s → %s", src, out)

    def _install_sdk(self, ctx: Context) -> None:
        machine = get_machine(ctx.architecture)
        deploy = ctx.root / BUILD_DIR / tmp_dir(ctx.architecture) / "deploy" / "sdk"
        # SDK_NAME is poky-<libc>-<sdkarch>-<image>-<tune>-<machine>
        libc = get_libc(ctx.architecture)
        installers = sorted(deploy.glob(f"poky-{libc}-*-{machine}-toolchain-*.sh"))
        if not installers:
            raise RuntimeError(
                f"No SDK installer for machine '{machine}' in {deploy}. "
                f"Available: {[p.name for p in deploy.glob('*.sh')]}"
            )
        # Keep a copy: it is the SDK's release asset. Copy (not link), since
        # bitbake may rewrite the deploy dir in place.
        installer = self.installer_path(ctx)
        installer.unlink(missing_ok=True)
        shutil.copy2(installers[-1], installer)
        log.info("Copied SDK installer %s → %s", installers[-1].name, installer)
        self._run_installer(installer, self.output_dir(ctx))

    @staticmethod
    def _run_installer(installer: Path, out: Path) -> None:
        shutil.rmtree(out, ignore_errors=True)
        log.info("Installing SDK %s → %s", installer.name, out)
        CommandRunner.run(["sh", str(installer), "-d", str(out), "-y"])

    def key(self, ctx: Context) -> str:
        """CAS key of this component for ctx.architecture."""
        chain = kas_chain(self.component, ctx.architecture)
        key = compute_kas_hash(ctx.root, chain, KAS_IMAGE, LOCAL_LAYERS)
        log.debug("kas chain %s → %s", chain, key)
        return key

    def run(self, ctx: Context) -> None:
        chain = kas_chain(self.component, ctx.architecture)
        key = self.key(ctx)

        if not self.should_build(ctx, key):
            return

        log.info(
            "Building %s for %s (MACHINE=%s)",
            self.component.name,
            ctx.architecture,
            get_machine(ctx.architecture),
        )
        run_kas(ctx.root, "build", chain)

        if self.component.deploy_name is None:
            self._install_sdk(ctx)
        else:
            self._collect(ctx)

        if not self.is_present(ctx):
            raise RuntimeError(
                f"kas build finished but {self.component.name} output is missing "
                f"in {self.output_dir(ctx)}"
            )

        out = self.output_dir(ctx)
        store_local_hash(out, key)
        store_published_hash(ctx.root, ctx.architecture, self.component.name, key)
        log.info(
            "%s built (%s...) — `aember pack`, then commit hashes/%s/%s.sha256 "
            "with the release",
            self.component.name,
            key[:12],
            ctx.architecture,
            self.component.name,
        )
