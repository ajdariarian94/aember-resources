import typer  # type: ignore

from aember.config.architecture import Architecture
from aember.core.context import Context
from aember.core.pipeline import Pipeline
from aember.steps.yocto.build_sdk import BuildSdk


def build_sdk(
    architecture: Architecture = typer.Option(
        Architecture.x64_linux,
        help="Target architecture",
        case_sensitive=False,
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Rebuild SDK and gcc-reflection even if already installed",
    ),
):
    ctx = Context(architecture=architecture.value, force=force)
    Pipeline([BuildSdk()]).run(ctx)
    