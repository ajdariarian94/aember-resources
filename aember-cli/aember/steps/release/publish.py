"""
Publish the staged release build/release/v<VERSION>/ to GitHub.

Before anything is uploaded the step checks that:
  - every asset in manifest.json exists and still has its recorded sha256,
  - HEAD is pushed to origin, and HEAD's committed hashes/<arch>/<c>.sha256
    equal the kas hash of every asset.
The release tag v<VERSION> is created at HEAD, so the tagged commit carries
the hash files that describe the release: a committed hash then always has
its asset.

Assets that already exist in the release are refused unless clobber is set.
manifest.json and SHA256SUMS are always replaced, because they index every
asset of the version and grow when another architecture is added.
"""

import json
import logging
from pathlib import Path
import subprocess

from aember.config.release import CHECKSUMS, MANIFEST, release_tag
from aember.core.context import Context
from aember.core.step import Step
from aember.steps.release.pack import release_dir
from aember.utils.archive import sha256_file
from aember.utils.fetch_artifact import get_version
from aember.utils.github import get_repo, load_github_token
from aember.utils.kas_hash import HASHES_DIR
from aember.utils.runner import CommandRunner

log = logging.getLogger("aember.release")

INDEX_FILES = (MANIFEST, CHECKSUMS)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _gh(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True)


class PublishRelease(Step):
    def __init__(self, clobber: bool = False) -> None:
        self.clobber = clobber

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def _load_manifest(self, rel_dir: Path, version: str) -> list[dict]:
        path = rel_dir / MANIFEST
        if not path.is_file():
            raise RuntimeError(f"No {path}. Run `aember pack` first.")
        manifest = json.loads(path.read_text())
        if manifest.get("version") != version:
            raise RuntimeError(
                f"{path} is for version {manifest.get('version')}, VERSION is "
                f"{version}"
            )
        for asset in manifest["assets"]:
            file = rel_dir / asset["name"]
            if not file.is_file():
                raise RuntimeError(f"Asset missing: {file}")
            if sha256_file(file) != asset["sha256"]:
                raise RuntimeError(
                    f"{file} changed after packing (sha256 mismatch). Pack again."
                )
        return manifest["assets"]

    def _check_head(self, root: Path, assets: list[dict]) -> str:
        head = _git(root, "rev-parse", "HEAD")
        if not _git(root, "branch", "-r", "--contains", head):
            raise RuntimeError(
                f"HEAD {head[:12]} is not pushed to origin. Commit the code and "
                f"hashes/, push, then publish."
            )
        for a in assets:
            rel = f"{HASHES_DIR}/{a['architecture']}/{a['component']}.sha256"
            try:
                committed = _git(root, "show", f"{head}:{rel}")
            except subprocess.CalledProcessError:
                committed = None
            if committed != a["kas_hash"]:
                raise RuntimeError(
                    f"{rel} at HEAD ({committed[:12] if committed else None}...) "
                    f"does not match {a['name']} ({a['kas_hash'][:12]}...). "
                    f"Commit hashes/ with the packed release."
                )
        return head

    # ------------------------------------------------------------------
    # GitHub
    # ------------------------------------------------------------------

    def _existing_assets(self, repo: str, tag: str) -> set[str] | None:
        """Asset names of the release, or None if it doesn't exist."""
        res = _gh("release", "view", tag, "--repo", repo, "--json", "assets")
        if res.returncode != 0:
            if "release not found" in res.stderr.lower():
                return None
            raise RuntimeError(f"gh release view {tag} failed: {res.stderr.strip()}")
        return {a["name"] for a in json.loads(res.stdout)["assets"]}

    @staticmethod
    def _notes(version: str, head: str, assets: list[dict]) -> str:
        rows = "\n".join(
            f"| `{a['name']}` | {a['architecture']} | {a['size'] / 1e6:.1f} MB "
            f"| `{a['kas_hash'][:12]}` |"
            for a in assets
        )
        return (
            f"aember-resources v{version} (commit `{head[:12]}`).\n\n"
            "| Asset | Arch | Size | kas hash |\n|---|---|---|---|\n"
            f"{rows}\n\n"
            "Zips hold a component output dir; the SDK ships as its installer "
            "(`sh <asset> -d <dir> -y`). Verify downloads with `sha256sum -c "
            "SHA256SUMS`; `manifest.json` lists the kas hash of every asset.\n"
        )

    def run(self, ctx: Context) -> None:
        version = get_version(ctx.root)
        tag = release_tag(version)
        rel_dir = release_dir(ctx.root, version)

        assets = self._load_manifest(rel_dir, version)
        head = self._check_head(ctx.root, assets)

        load_github_token(ctx.root)
        repo = get_repo(ctx.root)
        existing = self._existing_assets(repo, tag)

        if existing is None:
            log.info("Creating release %s at %s in %s", tag, head[:12], repo)
            CommandRunner.run(
                [
                    "gh",
                    "release",
                    "create",
                    tag,
                    "--repo",
                    repo,
                    "--target",
                    head,
                    "--title",
                    f"aember-resources {tag}",
                    "--notes",
                    self._notes(version, head, assets),
                ]
            )
            existing = set()

        names = [a["name"] for a in assets]
        clash = sorted(set(names) & existing)
        if clash and not self.clobber:
            raise RuntimeError(
                f"Release {tag} already has {clash}. Use --clobber to replace them."
            )

        files = [str(rel_dir / n) for n in [*names, *INDEX_FILES]]
        log.info("Uploading %d files to %s %s", len(files), repo, tag)
        CommandRunner.run(
            ["gh", "release", "upload", tag, *files, "--repo", repo, "--clobber"]
        )
        log.info("Published %s: https://github.com/%s/releases/tag/%s", tag, repo, tag)
