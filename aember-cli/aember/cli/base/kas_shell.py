# aember/cli/base/kas_shell.py

import typer  # type: ignore

from aember.cli.base.build import ComponentName
from aember.config.architecture import Architecture
from aember.config.components import get_component, kas_chain
from aember.utils.kas_container import run_kas
from aember.utils.root import find_root


def kas_shell(
    component: ComponentName = typer.Argument(..., help="Component to configure"),
    architecture: Architecture = typer.Option(
        Architecture.x64_linux,
        "--arch",
        "-a",
        help="Target architecture",
        case_sensitive=False,
    ),
    command: str = typer.Option(
        None,
        "--command",
        "-c",
        help="Run this command instead of an interactive shell",
    ),
):
    chain = kas_chain(get_component(component.value), architecture.value)
    extra = ["-c", command] if command else []
    run_kas(find_root(), "shell", chain, *extra)
