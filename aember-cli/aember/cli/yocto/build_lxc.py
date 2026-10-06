import typer  # type: ignore

from aember.config.architecture import Architecture
from aember.core.context import Context
from aember.core.pipeline import Pipeline
from aember.steps.yocto.build_lxc import BuildLxc


def build_lxc(
    architecture: Architecture = typer.Option(
        Architecture.x64_linux,
        help="Target architecture",
        case_sensitive=False,
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Rebuild LXC even if artifacts already exist",
    ),
):
    ctx = Context(architecture=architecture.value, force=force)
    Pipeline([BuildLxc()]).run(ctx)
    