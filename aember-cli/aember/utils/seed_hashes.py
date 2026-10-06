import logging
from pathlib import Path

from aember.utils.recipe_hash import compute_recipe_hash, store_hash

log = logging.getLogger("aember.seed_hashes")

# Maps architecture → list of recipe paths (relative to root)
RECIPES: dict[str, list[str]] = {
    "x64-poky-linux": [
        "yocto/meta-aember/recipes/kernel/aember-kernel.bb",
        "yocto/meta-aember/recipes/virtualization/aember-lxc.bb",
        "yocto/meta-aember/recipes/busybox/aember-busybox.bb",
    ],
    "aarch64-poky-linux": [
        "yocto/meta-aember/recipes/kernel/aember-kernel.bb",
        "yocto/meta-aember/recipes/virtualization/aember-lxc.bb",
        "yocto/meta-aember/recipes/busybox/aember-busybox.bb",
    ],
}


def seed_recipe_hashes(root: Path, architecture: str) -> None:
    """
    Compute and store SHA256 hashes for all recipes under
    yocto/hashes/<architecture>/<recipe>.sha256

    Commit these files to the repo — fresh clones can then
    compare against prebuilt GitHub Release artifacts and skip
    rebuilding if nothing changed.
    """
    recipes = RECIPES.get(architecture)
    if not recipes:
        raise ValueError(
            f"No recipes configured for architecture '{architecture}'. "
            f"Known: {list(RECIPES)}"
        )

    log.info("Seeding recipe hashes for '%s'", architecture)

    for recipe_rel in recipes:
        recipe_path = root / recipe_rel

        if not recipe_path.exists():
            log.warning("Recipe not found, skipping: %s", recipe_path)
            continue

        h = compute_recipe_hash(recipe_path)
        store_hash(root, architecture, recipe_path.stem, h)

        log.info("  ✅ %s (%s...)", recipe_path.name, h[:8])

    log.info("Done — commit yocto/hashes/%s/ to your repo", architecture)
