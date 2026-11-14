"""
CAS keys for kas builds.

The key of an artifact is the sha256 over the build image reference, its
ordered kas chain and every file of the in-repo layers (path + content).
External repos are pinned by commit and the image by digest, so the key covers
the recipes, config fragments, patches and the build host.

Two places record a key:
  - yocto/build/<arch>/<component>/.kas-hash  local: what this checkout has
  - hashes/<arch>/<component>.sha256          committed: what is published
"""

import hashlib
import logging
from pathlib import Path

log = logging.getLogger("aember.kas_hash")

HASHES_DIR = "hashes"
LOCAL_MARKER = ".kas-hash"


def _layer_files(root: Path, layers: list[str]) -> list[str]:
    files = []
    for layer in layers:
        files += [
            p.relative_to(root).as_posix()
            for p in (root / layer).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        ]
    return sorted(files)


def compute_kas_hash(
    root: Path, kas_files: list[str], image: str, layers: list[str]
) -> str:
    h = hashlib.sha256()
    h.update(image.encode())
    h.update(b"\0")
    for rel in [*kas_files, *_layer_files(root, layers)]:
        h.update(rel.encode())
        h.update(b"\0")
        h.update((root / rel).read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def published_hash_path(root: Path, architecture: str, component: str) -> Path:
    return root / HASHES_DIR / architecture / f"{component}.sha256"


def _read(path: Path) -> str | None:
    return path.read_text().strip() if path.is_file() else None


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n")
    log.debug("Wrote %s", path)


def read_published_hash(root: Path, architecture: str, component: str) -> str | None:
    return _read(published_hash_path(root, architecture, component))


def store_published_hash(
    root: Path, architecture: str, component: str, value: str
) -> None:
    _write(published_hash_path(root, architecture, component), value)


def read_local_hash(output_dir: Path) -> str | None:
    return _read(output_dir / LOCAL_MARKER)


def store_local_hash(output_dir: Path, value: str) -> None:
    _write(output_dir / LOCAL_MARKER, value)
