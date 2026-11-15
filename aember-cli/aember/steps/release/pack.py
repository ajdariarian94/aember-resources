"""
Pack built components into release assets (no upload).

`PackComponent` turns one component output into its asset in
build/release/v<VERSION>/ and records its metadata in .meta/<asset>.json.
`WriteReleaseIndex` then writes manifest.json and SHA256SUMS over every
packed asset of that version. Everything in the release dir except .meta/ is
meant to be uploaded to the GitHub release v<VERSION>.

An asset is only packed when the output matches the current CAS key and the
committed hashes/<arch>/<component>.sha256, so a release can never carry an
artifact its hash file doesn't describe.
"""

import json
import logging
from pathlib import Path

from aember.config.components import COMPONENTS, Component
from aember.config.release import (
    CHECKSUMS,
    MANIFEST,
    META_DIR,
    RELEASE_DIR,
    asset_name,
    is_installer,
    release_tag,
)
from aember.core.context import Context
from aember.core.step import Step
from aember.steps.kas.build import KasBuild
from aember.utils.archive import link_or_copy, sha256_file, zip_dir
from aember.utils.fetch_artifact import get_version
from aember.utils.kas_hash import read_local_hash, read_published_hash

log = logging.getLogger("aember.release")


def release_dir(root: Path, version: str) -> Path:
    return root / RELEASE_DIR / release_tag(version)


class PackComponent(Step):
    """Pack one component output into its release asset."""

    def __init__(self, component: Component) -> None:
        self.component = component

    def _check(self, ctx: Context, build: KasBuild, key: str) -> None:
        name, arch = self.component.name, ctx.architecture
        out = build.output_dir(ctx)
        if not build.is_present(ctx):
            raise RuntimeError(
                f"{name} ({arch}) is not built: {out} is missing or incomplete. "
                f"Run `aember build {name} -a {arch}` first."
            )
        local = read_local_hash(out)
        if local != key:
            raise RuntimeError(
                f"{name} ({arch}) output is stale: built for "
                f"{local[:12] if local else None}..., current key {key[:12]}... "
                f"Run `aember build {name} -a {arch}` first."
            )
        published = read_published_hash(ctx.root, arch, name)
        if published != key:
            raise RuntimeError(
                f"hashes/{arch}/{name}.sha256 "
                f"({published[:12] if published else None}...) does not match "
                f"the current key {key[:12]}..."
            )

    def run(self, ctx: Context) -> None:
        build = KasBuild(self.component)
        key = build.key(ctx)
        self._check(ctx, build, key)

        version = get_version(ctx.root)
        name = asset_name(self.component, ctx.architecture, version)
        dest = release_dir(ctx.root, version) / name

        log.info("Packing %s → %s", self.component.name, dest)
        if is_installer(self.component):
            link_or_copy(build.installer_path(ctx), dest)
        else:
            zip_dir(build.output_dir(ctx), dest)

        meta = {
            "name": name,
            "component": self.component.name,
            "architecture": ctx.architecture,
            "format": "installer" if is_installer(self.component) else "zip",
            "kas_hash": key,
            "sha256": sha256_file(dest),
            "size": dest.stat().st_size,
        }
        meta_path = dest.parent / META_DIR / f"{name}.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
        log.info("Packed %s (%.1f MB)", name, meta["size"] / 1e6)


class WriteReleaseIndex(Step):
    """Write manifest.json and SHA256SUMS for every packed asset."""

    def _assets(self, root: Path, rel_dir: Path) -> list[dict]:
        assets = []
        for meta_path in sorted((rel_dir / META_DIR).glob("*.json")):
            meta = json.loads(meta_path.read_text())
            asset = rel_dir / meta["name"]
            if not asset.is_file():
                raise RuntimeError(f"Asset listed in {meta_path} is missing: {asset}")
            if meta["component"] not in COMPONENTS:
                raise RuntimeError(f"Unknown component in {meta_path}")
            published = read_published_hash(
                root, meta["architecture"], meta["component"]
            )
            if published != meta["kas_hash"]:
                raise RuntimeError(
                    f"{meta['name']} is stale: packed for {meta['kas_hash'][:12]}..., "
                    f"hashes/{meta['architecture']}/{meta['component']}.sha256 is "
                    f"{published[:12] if published else None}... Pack it again."
                )
            assets.append(meta)
        return assets

    def run(self, ctx: Context) -> None:
        version = get_version(ctx.root)
        rel_dir = release_dir(ctx.root, version)
        assets = self._assets(ctx.root, rel_dir)
        if not assets:
            raise RuntimeError(f"No packed assets in {rel_dir}")

        manifest = {"version": version, "tag": release_tag(version), "assets": assets}
        (rel_dir / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")
        (rel_dir / CHECKSUMS).write_text(
            "".join(f"{a['sha256']}  {a['name']}\n" for a in assets)
        )
        log.info(
            "Release %s staged in %s: %s",
            release_tag(version),
            rel_dir,
            ", ".join(a["name"] for a in assets),
        )
