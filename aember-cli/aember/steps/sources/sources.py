"""
Source archives and SBOMs for the source offer (copyleft licences).

`aember sources <components> -a <arch>` runs bitbake's archiver over a
component's recipes: the component's kas chain plus kas/sources.yml, and only
`do_deploy_archives` (`bitbake --runall`), so everything else is restored from
sstate and no CAS key changes. The archives land in
<TMPDIR>/deploy/sources/<target-sys>/<recipe>/; they are copied into
yocto/build/<arch>/sources/<component>/, next to the SPDX documents of the
same recipes (poky's create-spdx, on by default).

`aember sources --pack` merges every architecture's copies into one
uncompressed tar per release (build/release/v<VERSION>-sources/): the
upstream tarballs are already compressed and mostly the same for every
architecture, so each file is stored once (same path and sha256).
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import shutil
import tarfile
from pathlib import Path

import yaml  # type: ignore

from aember.config.components import Component, kas_chain, tmp_dir
from aember.utils.kas_container import BUILD_DIR, run_kas

log = logging.getLogger("aember.sources")

SOURCES_OVERLAY = "kas/sources.yml"
OUTPUT_DIR = "sources"


def bitbake_target(root: Path, component: Component) -> str:
    """The bitbake target of a component's kas file, as `recipe[:do_task]`."""
    data = yaml.safe_load((root / component.kas_file).read_text())
    target = data["target"]
    task = data.get("task")
    return f"{target}:do_{task}" if task else target


def sources_chain(component: Component, architecture: str) -> list[str]:
    return [*kas_chain(component, architecture), SOURCES_OVERLAY]


def bitbake_command(root: Path, component: Component) -> str:
    return f"bitbake --runall=deploy_archives {bitbake_target(root, component)}"


def deploy_dir(root: Path, architecture: str) -> Path:
    return root / BUILD_DIR / tmp_dir(architecture) / "deploy"


def collect(root: Path, architecture: str, component: Component) -> Path:
    """Copy the deployed archives into yocto/build/<arch>/sources/<component>/."""
    src = deploy_dir(root, architecture) / "sources"
    out = root / "yocto/build" / architecture / OUTPUT_DIR / component.name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    count = 0
    if src.is_dir():
        for target_sys in sorted(src.iterdir()):
            for recipe in sorted(p for p in target_sys.iterdir() if p.is_dir()):
                shutil.copytree(recipe, out / target_sys.name / recipe.name)
                count += 1
    log.info("%s %s: %d recipe source dirs", architecture, component.name, count)
    return out


def run(root: Path, architecture: str, component: Component) -> Path:
    run_kas(
        root,
        "shell",
        sources_chain(component, architecture),
        "-c",
        bitbake_command(root, component),
    )
    return collect(root, architecture, component)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pack(root: Path, version: str) -> Path:
    """One tar of every architecture's sources: each file once, plus an index."""
    out_dir = root / "build/release" / f"v{version}-sources"
    out_dir.mkdir(parents=True, exist_ok=True)
    tar_path = out_dir / f"aember-sources-v{version}.tar"
    seen: dict[str, str] = {}
    index: list[dict] = []
    builds = root / "yocto/build"
    with tarfile.open(tar_path, "w", format=tarfile.PAX_FORMAT) as tar:
        for arch_dir in sorted(p for p in builds.iterdir() if p.is_dir()):
            base = arch_dir / OUTPUT_DIR
            if not base.is_dir():
                continue
            for f in sorted(p for p in base.rglob("*") if p.is_file()):
                rel = f.relative_to(base)
                # <component>/<target-sys>/<recipe>/<file>: stored by recipe
                # and file name, shared by every architecture that has it.
                key = "/".join(rel.parts[2:])
                digest = _sha256(f)
                if key in seen and seen[key] != digest:
                    key = f"{rel.parts[1]}/{key}"  # differs per target
                if key not in seen:
                    seen[key] = digest
                    info = tar.gettarinfo(str(f), arcname=f"sources/{key}")
                    info.uid = info.gid = 0
                    info.uname = info.gname = "root"
                    info.mtime = 315532800  # 1980-01-01, reproducible
                    with f.open("rb") as fh:
                        tar.addfile(info, fh)
                index.append(
                    {
                        "architecture": arch_dir.name,
                        "component": rel.parts[0],
                        "file": f"sources/{key}",
                        "sha256": digest,
                    }
                )
        data = json.dumps(index, indent=1, sort_keys=True).encode()
        info = tarfile.TarInfo("index.json")
        info.size = len(data)
        info.mtime = 315532800
        tar.addfile(info, io.BytesIO(data))
    (out_dir / "SHA256SUMS").write_text(f"{_sha256(tar_path)}  {tar_path.name}\n")
    log.info("Packed %s (%d files)", tar_path, len(seen))
    return tar_path
