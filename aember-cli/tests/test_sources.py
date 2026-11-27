"""aember sources: archiver chain, bitbake command, collect and pack."""

import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from aember.config.components import get_component
from aember.steps.sources import sources

ROOT = Path(__file__).resolve().parents[2]


class ChainTest(unittest.TestCase):
    def test_overlay_comes_last_and_keys_stay(self):
        # The overlay is appended only here: component chains (CAS keys)
        # never contain it.
        chain = sources.sources_chain(get_component("kernel"), "aarch64-poky-linux")
        self.assertEqual(chain[-1], "kas/sources.yml")
        self.assertNotIn("kas/sources.yml", chain[:-1])

    def test_targets(self):
        self.assertEqual(
            sources.bitbake_command(ROOT, get_component("kernel")),
            "bitbake --runall=deploy_archives aember-kernel",
        )
        self.assertEqual(
            sources.bitbake_target(ROOT, get_component("sdk")),
            "core-image-minimal:do_populate_sdk",
        )

    def test_overlay_is_target_and_sdk_only(self):
        text = (ROOT / "kas/sources.yml").read_text()
        self.assertIn('COPYLEFT_RECIPE_TYPES = "target nativesdk cross-canadian"', text)
        self.assertIn('INHERIT += "archiver"', text)


class PackTest(unittest.TestCase):
    def _tree(self, root: Path, arch: str, comp: str, sys_: str, files: dict):
        for name, data in files.items():
            p = root / "yocto/build" / arch / "sources" / comp / sys_ / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)

    def test_same_file_stored_once_different_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            same = {"busybox-1.36/busybox-1.36.tar.bz2": b"upstream"}
            self._tree(root, "x64-poky-linux", "busybox", "x86_64-poky-linux", same)
            self._tree(
                root, "aarch64-poky-linux", "busybox", "aarch64-poky-linux", same
            )
            self._tree(
                root,
                "x64-poky-linux",
                "busybox",
                "x86_64-poky-linux",
                {"busybox-1.36/busybox-1.36-diff.gz": b"x64 patch"},
            )
            self._tree(
                root,
                "aarch64-poky-linux",
                "busybox",
                "aarch64-poky-linux",
                {"busybox-1.36/busybox-1.36-diff.gz": b"arm patch"},
            )
            tar_path = sources.pack(root, "9.9.9")
            with tarfile.open(tar_path) as tar:
                names = tar.getnames()
                index = json.load(tar.extractfile("index.json"))
            self.assertEqual(
                names.count("sources/busybox-1.36/busybox-1.36.tar.bz2"), 1
            )
            diffs = [n for n in names if n.endswith("-diff.gz")]
            self.assertEqual(len(diffs), 2)  # differ per target: both kept
            self.assertEqual(len(index), 4)
            sums = (tar_path.parent / "SHA256SUMS").read_text()
            self.assertIn(tar_path.name, sums)


if __name__ == "__main__":
    unittest.main()
