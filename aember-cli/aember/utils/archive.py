"""
Zip packing for release assets.

Zips are reproducible: entries are sorted and carry a fixed timestamp, so the
same output dir always gives the same bytes (and the same sha256). Unix
permission bits are stored and restored, so executables stay executable.
Symlinks to files are stored as regular files (their target's content), so
any unzip tool restores a working tree.
"""

import hashlib
import logging
import os
from pathlib import Path
import shutil
import stat
import zipfile

log = logging.getLogger("aember.archive")

# Earliest timestamp a zip entry can hold
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_CHUNK = 1 << 20


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _entries(src_dir: Path) -> list[Path]:
    entries = []
    for p in sorted(src_dir.rglob("*")):
        if p.is_symlink() and p.is_dir():
            raise RuntimeError(f"Symlinked directory not supported in zip: {p}")
        if p.is_file():
            entries.append(p)
    return entries


def zip_dir(src_dir: Path, zip_path: Path) -> None:
    """Pack the contents of src_dir into zip_path (paths relative to src_dir)."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = zip_path.with_name(zip_path.name + ".tmp")
    tmp.unlink(missing_ok=True)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in _entries(src_dir):
            info = zipfile.ZipInfo(path.relative_to(src_dir).as_posix(), _ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            # stat() follows symlinks: a link is stored as its target file
            mode = stat.S_IMODE(path.stat().st_mode)
            info.external_attr = (stat.S_IFREG | mode) << 16
            with path.open("rb") as src, zf.open(info, "w") as dst:
                shutil.copyfileobj(src, dst, _CHUNK)
    tmp.replace(zip_path)
    log.debug("Packed %s → %s", src_dir, zip_path)


def extract_zip(zip_path: Path, dest_dir: Path) -> None:
    """Extract zip_path into dest_dir, restoring Unix permission bits."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            target = Path(zf.extract(info, dest_dir))
            mode = stat.S_IMODE(info.external_attr >> 16)
            if mode and not info.is_dir():
                target.chmod(mode)
    log.debug("Extracted %s → %s", zip_path, dest_dir)


def link_or_copy(src: Path, dest: Path) -> None:
    """Hard-link src to dest (same filesystem), else copy it."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.unlink(missing_ok=True)
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)
