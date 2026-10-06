import typer  # type: ignore

from aember.config.architecture import Architecture
from aember.core.context import Context
from aember.core.pipeline import Pipeline
from aember.steps.yocto.build_kernel import BuildKernel


def build_kernel(
    architecture: Architecture = typer.Option(
        Architecture.x64_linux,
        help="Target architecture",
        case_sensitive=False,
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Rebuild kernel even if artifacts already exist",
    ),
):
    ctx = Context(architecture=architecture.value, force=force)
    Pipeline([BuildKernel()]).run(ctx)
    