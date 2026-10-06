import typer  # type: ignore

from aember.config.architecture import Architecture
from aember.core.context import Context
from aember.utils.seed_hashes import seed_recipe_hashes


def seed_hashes(
    architecture: Architecture = typer.Option(
        Architecture.x64_linux,
        help="Target architecture",
        case_sensitive=False,
    ),
):
    """
    Seed recipe hashes for prebuilt Yocto artifacts.

    Run this once after a manual Yocto build so subsequent
    aember CLI commands can skip unchanged recipes automatically.
    """
    ctx = Context(architecture=architecture.value)
    seed_recipe_hashes(ctx.root, ctx.architecture)
