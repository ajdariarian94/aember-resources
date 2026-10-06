import logging
from pathlib import Path

from aember.core.context import Context
from aember.core.step import Step
from aember.utils.fetch_artifact import fetch_artifact, fetch_hashes, get_version
from aember.utils.runner import CommandRunner

log = logging.getLogger("yocto.sdk_build")

MACHINE_MAP: dict[str, str] = {
    "x64-poky-linux":     "x64-linux",
    "aarch64-poky-linux": "qemuarm64",
}

TARGET_TRIPLET_MAP: dict[str, str] = {
    "x64-poky-linux":     "x86_64-poky-linux",
    "aarch64-poky-linux": "aarch64-poky-linux",
}

SYSROOT_MAP: dict[str, str] = {
    "x64-poky-linux":     "core2-64-poky-linux",
    "aarch64-poky-linux": "cortexa57-poky-linux",
}

SDK_INSTALLER_TUNE_MAP: dict[str, str] = {
    "x64-poky-linux":     "core2-64",
    "aarch64-poky-linux": "cortexa57",
}

EXTRA_CONFIGURE_MAP: dict[str, str] = {
    "x64-poky-linux":     "",
    "aarch64-poky-linux": "",
    "arm-poky-linux":     "--with-float=hard --with-fpu=neon --with-arch=armv7-a",
}

GCC_REFLECTION_REPO   = "https://forge.sourceware.org/marek/gcc.git"
GCC_REFLECTION_BRANCH = "reflection"


class BuildSdk(Step):

    def sdk_install_dir(self, ctx: Context) -> Path:
        return ctx.root / "yocto" / "build" / ctx.architecture / "sdk"

    def gcc_reflection_dir(self, ctx: Context) -> Path:
        return ctx.root / "yocto" / "build" / ctx.architecture / "gcc-reflection"

    def gcc_reflection_install_dir(self, ctx: Context) -> Path:
        return self.gcc_reflection_dir(ctx) / "install"

    def target_sysroot(self, ctx: Context) -> Path:
        sysroot_name = SYSROOT_MAP.get(ctx.architecture)
        if not sysroot_name:
            raise ValueError(
                f"No sysroot mapping for architecture: '{ctx.architecture}'. "
                f"Known: {list(SYSROOT_MAP)}"
            )
        return self.sdk_install_dir(ctx) / "sysroots" / sysroot_name

    def _is_cross(self, ctx: Context) -> bool:
        return TARGET_TRIPLET_MAP.get(ctx.architecture) != "x86_64-poky-linux"

    def _reflect_binary(self, ctx: Context) -> Path:
        triplet = TARGET_TRIPLET_MAP.get(ctx.architecture, "")
        name    = f"{triplet}-g++" if self._is_cross(ctx) else "g++"
        return self.gcc_reflection_install_dir(ctx) / "bin" / name

    def is_sdk_installed(self, ctx: Context) -> bool:
        install_dir = self.sdk_install_dir(ctx)
        sysroot     = self.target_sysroot(ctx)
        env_files   = list(install_dir.glob("environment-setup-*"))
        return install_dir.exists() and bool(env_files) and sysroot.exists()

    def is_gcc_reflection_built(self, ctx: Context) -> bool:
        return self._reflect_binary(ctx).exists()

    def hashes_dir(self, ctx: Context) -> Path:
        return ctx.root / "yocto" / "hashes" / ctx.architecture

    def _ensure_hashes(self, ctx: Context) -> bool:
        # SDK doesn't have a recipe hash — use a sentinel file instead
        sentinel = self.hashes_dir(ctx) / "aember-busybox.sha256"
        if sentinel.exists():
            return True
        log.info("Hash files not found locally — downloading from GitHub Releases")
        return fetch_hashes(ctx.root, ctx.architecture)

    # ---------------------------------------------------------------------------
    # SDK
    # ---------------------------------------------------------------------------

    def _try_download_sdk(self, ctx: Context) -> bool:
        """Try to download prebuilt SDK from GitHub Releases."""
        log.info("SDK not found — trying GitHub Releases")
        version  = get_version(ctx.root)
        artifact = f"aember-sdk-{ctx.architecture}-v{version}.tar.gz"
        return fetch_artifact(ctx.root, artifact, self.sdk_install_dir(ctx).parent)

    def _build_sdk(self, ctx: Context) -> None:
        machine = MACHINE_MAP.get(ctx.architecture)
        if not machine:
            raise ValueError(
                f"Unsupported architecture: '{ctx.architecture}'. "
                f"Known: {list(MACHINE_MAP)}"
            )

        log.info("Building Yocto SDK for MACHINE=%s", machine)

        yocto_cmd = f"""
            export MACHINE={machine} &&
            source {ctx.root}/yocto/poky/oe-init-build-env {ctx.root}/yocto/resources &&
            bitbake core-image-minimal -c populate_sdk
        """
        CommandRunner.run(yocto_cmd, shell=True)

        sdk_install_dir = self.sdk_install_dir(ctx)
        tune_name       = SDK_INSTALLER_TUNE_MAP.get(ctx.architecture, "")
        sdk_deploy_dir  = ctx.root / "yocto" / "resources" / "tmp" / "deploy" / "sdk"
        sdk_installers  = list(sdk_deploy_dir.glob(f"*{tune_name}*.sh"))

        if not sdk_installers:
            raise RuntimeError(
                f"No SDK installer found for tune '{tune_name}' in {sdk_deploy_dir}. "
                f"Available: {list(sdk_deploy_dir.glob('*.sh'))}"
            )

        sdk_installer = sdk_installers[0]
        log.info("Using SDK installer: %s", sdk_installer.name)

        CommandRunner.run(
            f"chmod +x {sdk_installer} && "
            f"{sdk_installer} -d {sdk_install_dir} -y",
            shell=True,
        )
        log.info("SDK installed at %s", sdk_install_dir)

    # ---------------------------------------------------------------------------
    # GCC reflection
    # ---------------------------------------------------------------------------

    def _try_download_gcc_reflection(self, ctx: Context) -> bool:
        """Try to download prebuilt gcc-reflection from GitHub Releases.
        Tar contains gcc-reflection/ top-level — move contents into install/.
        """
        import shutil
        log.info("gcc-reflection not found — trying GitHub Releases")
        version     = get_version(ctx.root)
        artifact    = f"aember-gcc-reflection-{ctx.architecture}-v{version}.tar.gz"
        tmp_dir     = ctx.root / "build" / "downloads" / "gcc_reflection_tmp"
        install_dir = self.gcc_reflection_install_dir(ctx)

        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)

        ok = fetch_artifact(ctx.root, artifact, tmp_dir)

        if ok and tmp_dir.exists():
            # tar extracts to tmp_dir/gcc-reflection/ — move into install/
            src = tmp_dir / "gcc-reflection"
            install_dir.mkdir(parents=True, exist_ok=True)
            if src.exists():
                for f in src.iterdir():
                    dest = install_dir / f.name
                    if dest.exists():
                        dest.unlink() if dest.is_file() else shutil.rmtree(dest)
                    shutil.move(str(f), str(dest))
            shutil.rmtree(tmp_dir, ignore_errors=True)
            log.info("gcc-reflection extracted to %s", install_dir)

        return ok

    def _build_gcc_reflection(self, ctx: Context) -> None:
        target_triplet = TARGET_TRIPLET_MAP.get(ctx.architecture)
        if not target_triplet:
            raise ValueError(
                f"No GCC target triplet for architecture: '{ctx.architecture}'. "
                f"Known: {list(TARGET_TRIPLET_MAP)}"
            )

        gcc_dir     = self.gcc_reflection_dir(ctx)
        install_dir = self.gcc_reflection_install_dir(ctx)
        src_dir     = gcc_dir / "src"
        build_dir   = gcc_dir / "build"

        if not src_dir.exists():
            log.info("Cloning GCC reflection branch from %s", GCC_REFLECTION_REPO)
            CommandRunner.run(
                f"git clone --depth=1 --branch {GCC_REFLECTION_BRANCH} "
                f"{GCC_REFLECTION_REPO} {src_dir}",
                shell=True,
            )

        build_dir.mkdir(parents=True, exist_ok=True)
        install_dir.mkdir(parents=True, exist_ok=True)

        sysroot_flags  = ""
        cross_flags    = ""
        binutils_flags = ""
        sdk_cross_bin  = None

        if self._is_cross(ctx):
            sysroot = self.target_sysroot(ctx)
            if not sysroot.exists():
                raise RuntimeError(
                    f"Target sysroot not found at {sysroot}. "
                    f"SDK must be installed before building gcc-reflection."
                )

            sdk_cross_bin = (
                self.sdk_install_dir(ctx)
                / "sysroots"
                / "x86_64-pokysdk-linux"
                / "usr"
                / "bin"
                / target_triplet
            )

            cc  = sdk_cross_bin / f"{target_triplet}-gcc"
            cxx = sdk_cross_bin / f"{target_triplet}-g++"
            as_ = sdk_cross_bin / f"{target_triplet}-as"
            ld  = sdk_cross_bin / f"{target_triplet}-ld"

            if not cc.exists():
                raise RuntimeError(
                    f"SDK cross-compiler not found at {cc}. "
                    f"Ensure the SDK is fully installed."
                )

            sysroot_flags  = (
                f"--with-sysroot={sysroot} "
                f"--with-build-sysroot={sysroot} "
            )
            cross_flags    = (
                f"CC_FOR_TARGET={cc} "
                f"CXX_FOR_TARGET={cxx} "
                f"AS_FOR_TARGET={as_} "
                f"LD_FOR_TARGET={ld} "
            )
            binutils_flags = (
                f"--with-as={as_} "
                f"--with-ld={ld} "
            )

            log.info("Using sysroot:        %s", sysroot)
            log.info("Using cross-compiler: %s", cc)
            log.info("Using assembler:      %s", as_)

        extra_flags = EXTRA_CONFIGURE_MAP.get(ctx.architecture, "")

        log.info("Configuring GCC reflection for target '%s'...", target_triplet)

        CommandRunner.run(
            f"{src_dir}/configure "
            f"--prefix={install_dir} "
            f"--target={target_triplet} "
            f"{sysroot_flags}"
            f"{cross_flags}"
            f"{binutils_flags}"
            f"{extra_flags} "
            f"--enable-languages=c++ "
            f"--disable-multilib "
            f"--disable-bootstrap "
            f"--disable-libsanitizer",
            shell=True,
            cwd=build_dir,
        )

        log.info("Building GCC with reflection support (~20 min)...")

        path_prefix = ""
        if self._is_cross(ctx) and sdk_cross_bin:
            path_prefix = f"export PATH={sdk_cross_bin}:$PATH && "

        CommandRunner.run(
            f"{path_prefix}make -j$(nproc) && make install",
            shell=True,
            cwd=build_dir,
        )

        self._patch_sdk_env(ctx)
        log.info("GCC reflection compiler installed at %s", self._reflect_binary(ctx))

    def _patch_sdk_env(self, ctx: Context) -> None:
        sdk_install_dir = self.sdk_install_dir(ctx)
        env_files = list(sdk_install_dir.glob("environment-setup-*"))
        if not env_files:
            log.warning("No SDK environment-setup script found, skipping patch")
            return

        reflect_gxx = self._reflect_binary(ctx)
        patch_block = f"""
# ── Reflection compiler (P2996 / CppCon demo) ────────────────────────────────
export CXX_REFLECT="{reflect_gxx}"
alias g++-reflect="{reflect_gxx} -std=c++26 -freflection"
# ─────────────────────────────────────────────────────────────────────────────
"""
        with open(env_files[0], "a") as f:
            f.write(patch_block)

        log.info("Patched %s with CXX_REFLECT=%s", env_files[0].name, reflect_gxx)

    # ---------------------------------------------------------------------------
    # Entry point
    # ---------------------------------------------------------------------------

    def run(self, ctx: Context) -> None:
        log.info("Building SDK for architecture '%s'", ctx.architecture)

        # SDK
        if ctx.force:
            log.info("--force specified, rebuilding SDK")
            self._build_sdk(ctx)
        elif not self.is_sdk_installed(ctx):
            if not self._try_download_sdk(ctx):
                self._build_sdk(ctx)
        else:
            log.info("SDK already installed at %s, skipping", self.sdk_install_dir(ctx))

        # gcc-reflection
        if ctx.force:
            log.info("--force specified, rebuilding gcc-reflection")
            self._build_gcc_reflection(ctx)
        elif not self.is_gcc_reflection_built(ctx):
            if not self._try_download_gcc_reflection(ctx):
                self._build_gcc_reflection(ctx)
        else:
            log.info(
                "GCC reflection already built at %s, skipping",
                self._reflect_binary(ctx),
            )
            