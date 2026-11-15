import logging
from pathlib import Path
import re
import shutil

from aember.config.release import DOWNLOAD_DIR, release_tag
from aember.utils.archive import extract_zip
from aember.utils.github import get_repo, load_github_token
from aember.utils.runner import CommandRunner

log = logging.getLogger("aember.fetch_artifact")


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
    load_github_token(root)
    repo = get_repo(root)
    version = get_version(root)
    dest_dir.mkdir(parents=True, exist_ok=True)

    log.info("Downloading release asset: %s", asset_name)

    CommandRunner.run(
        [
            "gh",
            "release",
            "download",
            release_tag(version),
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


def fetch_artifact(root: Path, asset_name: str, dest_dir: Path) -> bool:
    """
    Download a zip release asset and extract it into dest_dir.
    Returns True if succeeded, False otherwise.
    """
    try:
        zip_path = download_release_asset(root, asset_name, root / DOWNLOAD_DIR)
        extract_zip(zip_path, dest_dir)
        zip_path.unlink()
        log.info("Fetched artifact: %s → %s", asset_name, dest_dir)
        return True
    except Exception as e:
        log.warning("Failed to fetch artifact '%s': %s", asset_name, e)
        return False


def fetch_file(root: Path, asset_name: str, dest: Path) -> bool:
    """
    Download a release asset as-is (e.g. the SDK installer) to dest.
    Returns True if succeeded, False otherwise.
    """
    try:
        path = download_release_asset(root, asset_name, root / DOWNLOAD_DIR)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(path, dest)
        log.info("Fetched file: %s → %s", asset_name, dest)
        return True
    except Exception as e:
        log.warning("Failed to fetch file '%s': %s", asset_name, e)
        return False
