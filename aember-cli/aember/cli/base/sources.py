# aember/cli/base/sources.py

import typer  # type: ignore

from aember.cli.base.build import ComponentName
from aember.config.architecture import Architecture
from aember.config.components import get_component
from aember.steps.sources import sources as step
from aember.utils.root import find_root


def sources(
    components: list[ComponentName] = typer.Argument(
        None, help="Components whose recipes to archive"
    ),
    architectures: list[Architecture] = typer.Option(
        [Architecture.x64_linux],
        "--arch",
        "-a",
        help="Target architecture (repeatable)",
        case_sensitive=False,
    ),
    pack: bool = typer.Option(
        False,
        "--pack",
        help="Merge every architecture's archives into "
        "build/release/v<VERSION>-sources/aember-sources-v<VERSION>.tar",
    ),
):
    root = find_root()
    for arch in architectures if components else []:
        for c in components:
            step.run(root, arch.value, get_component(c.value))
    if pack:
        version = (root / "VERSION").read_text().strip()
        step.pack(root, version)
