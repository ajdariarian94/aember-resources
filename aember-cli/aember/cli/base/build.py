# aember/cli/base/build.py

from enum import Enum

import typer  # type: ignore

from aember.config.architecture import Architecture
from aember.config.components import COMPONENTS, get_component
from aember.core.context import Context
from aember.core.pipeline import Pipeline
from aember.steps.kas.build import KasBuild
from aember.utils.root import find_root

ComponentName = Enum("ComponentName", {name: name for name in COMPONENTS}, type=str)


def build(
    components: list[ComponentName] = typer.Argument(
        ..., help="Components to build, in order"
    ),
    architectures: list[Architecture] = typer.Option(
        [Architecture.x64_linux],
        "--arch",
        "-a",
        help="Target architecture (repeatable)",
        case_sensitive=False,
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Rebuild even if the CAS key is unchanged",
    ),
):
    root = find_root()
    for arch in architectures:
        ctx = Context(architecture=arch.value, force=force, root=root)
        Pipeline(KasBuild(get_component(c.value)) for c in components).run(ctx)
