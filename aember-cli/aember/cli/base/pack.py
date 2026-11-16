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
    architectures: list[Architecture] = typer.Option(
        [Architecture.x64_linux],
        "--arch",
        "-a",
        help="Target architecture (repeatable)",
        case_sensitive=False,
    ),
):
    names = [c.value for c in components] if components else list(COMPONENTS)
    root = find_root()
    for arch in architectures:
        ctx = Context(architecture=arch.value, root=root)
        Pipeline([PackComponent(get_component(n)) for n in names]).run(ctx)
    # The index covers everything packed for the version, every architecture
    Pipeline([WriteReleaseIndex()]).run(Context(root=root))
