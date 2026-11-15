# aember/cli/base/publish.py

import typer  # type: ignore

from aember.core.context import Context
from aember.core.pipeline import Pipeline
from aember.steps.release.publish import PublishRelease
from aember.utils.root import find_root


def publish(
    clobber: bool = typer.Option(
        False,
        "--clobber",
        help="Replace assets that already exist in the GitHub release",
    ),
):
    ctx = Context(root=find_root())
    Pipeline([PublishRelease(clobber=clobber)]).run(ctx)
