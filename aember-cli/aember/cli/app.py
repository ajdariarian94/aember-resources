# aember/cli/app.py

import typer  # type: ignore
from aember.utils.logging import setup_logging

from .base.build import build
from .base.kas_shell import kas_shell
from .base.lint import lint
from .base.pack import pack
from .base.publish import publish
from .base.sources import sources

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

aember.command(help="Build components with kas (CAS-cached)")(build)
aember.command(
    name="kas-shell", help="Open a bitbake shell in the kas build container"
)(kas_shell)
aember.command(help="Lint Python, C++, and CMake code")(lint)
aember.command(
    help="Pack built components into release assets in build/release/ (no upload)"
)(pack)
aember.command(help="Upload the packed release build/release/v<VERSION>/ to GitHub")(
    publish
)

aember.command(
    help="Source archives (copyleft recipes) for the source offer; --pack merges them"
)(sources)

aember.add_typer(aember_app, name="app")
