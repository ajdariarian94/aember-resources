# aember/cli/base/pack.py

import typer  # type: ignore

from aember.cli.base.build import ComponentName
from aember.config.architecture import Architecture
from aember.config.components import COMPONENTS, get_component
from aember.core.context import Context
from aember.core.pipeline import Pipeline
from aember.steps.release.pack import PackComponent, WriteReleaseIndex
from aember.utils.root import find_root


def pack(
    components: list[ComponentName] = typer.Argument(
        None, help="Components to pack (default: all)"
    ),
    architecture: Architecture = typer.Option(
        Architecture.x64_linux,
        "--arch",
        "-a",
        help="Target architecture",
        case_sensitive=False,
    ),
):
    names = [c.value for c in components] if components else list(COMPONENTS)
    ctx = Context(architecture=architecture.value, root=find_root())
    Pipeline(
        [*(PackComponent(get_component(n)) for n in names), WriteReleaseIndex()]
    ).run(ctx)
