import logging
from pathlib import Path

from .fetch_artifact import fetch_artifact, get_version
from .github import load_github_token

log = logging.getLogger("aember.check_resources")


def _resources_present(resources_dir: Path) -> bool:
    return resources_dir.exists() and any(resources_dir.iterdir())


def check_resources(root: Path) -> bool:
    """
    Ensure resources/ is present locally.
    If missing/empty, downloads and extracts the aember-resources artifact
    from GitHub Releases (produced by ReleaseStep._pack_resources). If
    already present, skips.
    Returns True if resources are present/fetched successfully, False otherwise.
    """
    load_github_token(root)

    resources_dir = root / "resources"
    log.info("Checking resources_dir=%s (root=%s)", resources_dir, root)

    if _resources_present(resources_dir):
        log.info("Resources already present — skipping")
        return True

    log.info("Resources missing — fetching from release")

    version = get_version(root)
    artifact_name = f"aember-resources-v{version}.zip"

    # The zip's top-level entry is "resources", so extract into root
    # itself rather than into resources_dir.
    return fetch_artifact(root, artifact_name, root)
