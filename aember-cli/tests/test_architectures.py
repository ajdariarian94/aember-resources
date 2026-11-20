"""Every architecture is complete: CLI maps, kas machine, Yocto machine,
kernel/BusyBox/LXC configuration and the recipes' COMPATIBLE_MACHINE.

A missing piece otherwise shows up hours into a Yocto build (or not at all:
an absent BusyBox fragment is silently skipped)."""

import re
import unittest
from pathlib import Path

from aember.config import components, qemu, sdk
from aember.config.architecture import Architecture

ROOT = Path(__file__).resolve().parents[2]
RECIPES = ROOT / "meta-aember" / "recipes"
# Yocto's architecture override for each kas machine (TARGET_ARCH)
TARGET_ARCH = {
    "x64-linux": "x86_64",
    "arm64-linux": "aarch64",
    "arm-linux": "arm",
    "riscv64-linux": "riscv64",
}
# The recipes' :append overrides (x86-64, not x86_64)
OVERRIDE = {"x86_64": "x86-64"}


def machines() -> list[str]:
    return [components.get_machine(a.value) for a in Architecture]


class ArchitectureMapsTest(unittest.TestCase):
    def test_every_architecture_is_in_every_map(self):
        for arch in Architecture:
            with self.subTest(arch=arch.value):
                self.assertIn(arch.value, components.MACHINE_MAP)
                self.assertIn(arch.value, components.KERNEL_IMAGE_MAP)
                self.assertIn(arch.value, qemu.QEMU_RUNNER_MAP)
                self.assertIn(arch.value, sdk.SDK_ENV_MAP)
                self.assertIn(arch.value, sdk.SDK_SYSROOT_MAP)
                self.assertIn(arch.value, sdk.VCPKG_TRIPLET_MAP)

    def test_sdk_env_matches_its_sysroot(self):
        for arch in Architecture:
            with self.subTest(arch=arch.value):
                self.assertEqual(
                    sdk.SDK_ENV_MAP[arch.value],
                    "environment-setup-" + sdk.SDK_SYSROOT_MAP[arch.value],
                )

    def test_aarch64_is_the_generic_cortex_a53_tune(self):
        conf = (ROOT / "meta-aember/conf/machine/arm64-linux.conf").read_text()
        self.assertIn('DEFAULTTUNE = "cortexa53"', conf)
        self.assertIn("cortexa53", sdk.SDK_SYSROOT_MAP["aarch64-poky-linux"])

    def test_the_sdk_ships_the_sanitizer_runtimes(self):
        self.assertIn("gcc-sanitizers", (ROOT / "kas/recipes/sdk.yml").read_text())


class MachineFilesTest(unittest.TestCase):
    def test_kas_and_yocto_machine_files_exist(self):
        for machine in machines():
            with self.subTest(machine=machine):
                kas = (ROOT / "kas/machine" / f"{machine}.yml").read_text()
                self.assertIn(f"machine: {machine}", kas)
                conf = ROOT / "meta-aember/conf/machine" / f"{machine}.conf"
                self.assertIn("aember-kernel", conf.read_text())

    def test_recipes_accept_every_machine(self):
        for recipe in (
            "kernel/aember-kernel.bb",
            "busybox/aember-busybox.bb",
            "virtualization/aember-lxc.bb",
        ):
            text = (RECIPES / recipe).read_text()
            allowed = re.search(r'COMPATIBLE_MACHINE = "([^"]+)"', text).group(1)
            for machine in machines():
                with self.subTest(recipe=recipe, machine=machine):
                    self.assertIn(machine, allowed.split("|"))

    def test_kernel_fragments_exist_and_are_wired(self):
        kernel = (RECIPES / "kernel/aember-kernel.bb").read_text()
        for machine in machines():
            arch = TARGET_ARCH[machine]
            override = OVERRIDE.get(arch, arch)
            with self.subTest(machine=machine):
                self.assertIn(f"KBUILD_DEFCONFIG:{override}", kernel)
                self.assertIn(f"AEMBER_KERNEL_FRAGMENTS:append:{override}", kernel)
                self.assertIn(f"AEMBER_KERNEL_TRIM:append:{override}", kernel)
                for name in re.findall(
                    rf"SRC_URI:append:{re.escape(override)}\s*=\s*\"([^\"]+)\"",
                    kernel,
                )[0].split():
                    path = RECIPES / "kernel/files" / name.removeprefix("file://")
                    self.assertTrue(path.exists(), path)

    def test_busybox_and_lxc_configs_exist_and_are_wired(self):
        busybox = (RECIPES / "busybox/aember-busybox.bb").read_text()
        lxc = (RECIPES / "virtualization/aember-lxc.bb").read_text()
        for machine in machines():
            arch = TARGET_ARCH[machine]
            with self.subTest(machine=machine):
                self.assertTrue((RECIPES / f"busybox/files/{machine}.cfg").exists())
                self.assertIn(f'"{arch}" ]; then\n        merge_cfg', busybox)
                self.assertTrue(
                    (RECIPES / f"virtualization/files/{machine}.conf").exists()
                )
                self.assertIn(f"file://{machine}.conf", lxc)
                self.assertIn(f'"{arch}" ]; then\n        install', lxc)


if __name__ == "__main__":
    unittest.main()
