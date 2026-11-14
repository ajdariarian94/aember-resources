# aember/cli/app.py

import typer  # type: ignore
from aember.utils.logging import setup_logging

from .base.lint import lint

aember = typer.Typer(help="Aember build system")


@aember.callback()
def main(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    )
):
    setup_logging(verbose)


# ----------------------------
# Aember sub-app
# ----------------------------
aember_app = typer.Typer(help="Aember related commands")

# ----------------------------
# Base commands
# ----------------------------

aember.command(help="Lint Python, C++, and CMake code")(lint)

aember.add_typer(aember_app, name="app")
