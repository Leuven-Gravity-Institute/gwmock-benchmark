# ruff: noqa: PLC0415
"""The ``gwmock-benchmark aggregate`` command.

Render the committed dataset into the docs site: for each ``data/<package>/`` group,
load its records and call that package suite's ``render`` to write figures + table
snippets under ``docs/<package>/``. Run before ``zensical build`` in the docs pipeline.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Annotated

import typer


def aggregate_command(
    data_dir: Annotated[Path, typer.Option("--data-dir", help="Directory of committed records.")] = Path("data"),
    docs_dir: Annotated[Path, typer.Option("--docs-dir", help="Docs directory to render into.")] = Path("docs"),
) -> None:
    """Render figures and table snippets from the committed dataset into the docs."""
    from gwmock_benchmark.harness import load_records

    if not data_dir.is_dir():
        raise typer.BadParameter(f"no data directory at {data_dir}")

    rendered_any = False
    for package_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        records = load_records(package_dir)
        if not records:
            continue
        try:
            suite = importlib.import_module(f"gwmock_benchmark.suites.{package_dir.name}")
        except ModuleNotFoundError as error:
            raise typer.BadParameter(f"no suite module for data/{package_dir.name}/") from error
        written = suite.render(records, docs_dir / package_dir.name)
        rendered_any = True
        typer.echo(
            f"{package_dir.name}: {len(records)} records -> {len(written)} artifacts in {docs_dir / package_dir.name}"
        )

    if not rendered_any:
        typer.echo(f"no records found under {data_dir}")
