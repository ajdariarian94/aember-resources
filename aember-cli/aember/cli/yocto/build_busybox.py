import typer  # type: ignore

from aember.config.architecture import Architecture
from aember.core.context import Context
from aember.core.pipeline import Pipeline
from aember.steps.yocto.build_busybox import BuildBusybox


def build_busybox(
    architecture: Architecture = typer.Option(
        Architecture.x64_linux,
        help="Target architecture",
        case_sensitive=False,
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Rebuild busybox even if artifacts already exist",
    ),
):
    ctx = Context(architecture=architecture.value, force=force)
    Pipeline([BuildBusybox()]).run(ctx)
    