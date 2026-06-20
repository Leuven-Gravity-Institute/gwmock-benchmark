# ruff: noqa PL0415
"""Hello command module."""

from __future__ import annotations

from typing import Annotated

import typer


def hello_command(name: Annotated[str, typer.Option("--name", help="Name.")]) -> None:
    """Hello Command.

    Args:
        name: Name to greet.
    """
    from logging import getLogger

    from gwmock_benchmark.hello_world import say_hello

    logger = getLogger("gwmock_benchmark")

    say_hello(name)

    logger.info("Executed hello_command with name: %s", name)
