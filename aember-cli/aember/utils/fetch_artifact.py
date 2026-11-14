import logging
import re
import subprocess
import tarfile
from pathlib import Path

from aember.utils.runner import CommandRunner

log = logging.getLogger("aember.fetch_artifact")


def _get_repo(root: Path) -> str:
    """owner/name of the GitHub repo, taken from the `origin` remote."""
    url = subprocess.run(
        ["git", "-C", str(root), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    if not match:
        raise RuntimeError(f"origin is not a GitHub remote: {url}")
    return match.group(1)


def get_version(root: Path) -> str:
    version = (root / "VERSION").read_text().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise RuntimeError(f"Invalid VERSION '{version}' (expected x.y.z)")
    return version


def download_release_asset(root: Path, asset_name: str, dest_dir: Path) -> Path:
    """
    Download a GitHub Release asset into dest_dir using gh CLI.
    Returns the path to the downloaded file.
    """
    repo = _get_repo(root)
    version = get_version(root)
    dest_dir.mkdir(parents=True, exist_ok=True)

    log.info("Downloading release asset: %s", asset_name)

    CommandRunner.run(
        [
            "gh",
            "release",
            "download",
            f"v{version}",
            "--repo",
            repo,
            "--pattern",
            asset_name,
            "--dir",
            str(dest_dir),
            "--clobber",
        ]
    )

    return dest_dir / asset_name


def extract_tar(tar_path: Path, dest_dir: Path) -> None:
    """Extract a tar.gz into dest_dir and remove the archive."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(dest_dir, filter="tar")
    tar_path.unlink()
    log.debug("Extracted to %s", dest_dir)


def fetch_artifact(root: Path, artifact_name: str, dest_dir: Path) -> bool:
    """
    Download and extract a named release artifact into dest_dir.
    Returns True if succeeded, False otherwise.
    """
    try:
        download_dir = root / "build" / "downloads"
        tar_path = download_release_asset(root, artifact_name, download_dir)
        extract_tar(tar_path, dest_dir)
        log.info("Fetched artifact: %s → %s", artifact_name, dest_dir)
        return True
    except Exception as e:
        log.warning("Failed to fetch artifact '%s': %s", artifact_name, e)
        return False
