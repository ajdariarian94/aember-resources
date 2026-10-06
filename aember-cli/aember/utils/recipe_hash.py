import hashlib
import logging
from pathlib import Path

log = logging.getLogger("aember.recipe_hash")

HASHES_BASE = "yocto/hashes"


def hash_file_path(root: Path, architecture: str, recipe_name: str) -> Path:
    return root / HASHES_BASE / architecture / f"{recipe_name}.sha256"


def compute_recipe_hash(recipe_path: Path) -> str:
    return hashlib.sha256(recipe_path.read_bytes()).hexdigest()


def read_stored_hash(root: Path, architecture: str, recipe_name: str) -> str | None:
    path = hash_file_path(root, architecture, recipe_name)
    if not path.exists():
        return None
    return path.read_text().strip()


def store_hash(
    root: Path, architecture: str, recipe_name: str, recipe_hash: str
) -> None:
    path = hash_file_path(root, architecture, recipe_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(recipe_hash)
    log.debug("Stored hash: %s", path)


def recipe_changed(root: Path, architecture: str, recipe_path: Path) -> bool:
    recipe_name = recipe_path.stem
    current_hash = compute_recipe_hash(recipe_path)
    stored_hash = read_stored_hash(root, architecture, recipe_name)

    if stored_hash is None:
        log.debug("No stored hash for %s — treating as changed", recipe_name)
        return True

    changed = current_hash != stored_hash
    if changed:
        log.info(
            "Recipe '%s' changed (stored=%s... current=%s...) — rebuild needed",
            recipe_name,
            stored_hash[:8],
            current_hash[:8],
        )
    else:
        log.debug("Recipe '%s' unchanged — skip", recipe_name)

    return changed
