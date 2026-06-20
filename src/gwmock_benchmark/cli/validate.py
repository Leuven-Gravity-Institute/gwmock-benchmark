# ruff: noqa: PLC0415
"""The ``gwmock-benchmark validate`` command.

Cross-check every committed record: structural validity, provenance completeness,
and — via each suite's ``check_contribution`` — that the derived metrics still agree
with the primitives they were computed from. Run in CI on contribution PRs so a
malformed or hand-edited record fails the build instead of being trusted on sight.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Annotated

import typer


def validate_command(
    data_dir: Annotated[Path, typer.Option("--data-dir", help="Directory of committed records.")] = Path("data"),
) -> None:
    """Validate every record under ``data_dir``; exit non-zero if any check fails."""
    from gwmock_benchmark.harness import check_provenance, validate_record

    if not data_dir.is_dir():
        raise typer.BadParameter(f"no data directory at {data_dir}")

    checked = 0
    failed = 0
    for package_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        try:
            suite_module = importlib.import_module(f"gwmock_benchmark.suites.{package_dir.name}")
        except ModuleNotFoundError:
            suite_module = None

        for path in sorted(package_dir.rglob("*.json")):
            checked += 1
            problems: list[str] = []
            try:
                record = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError) as error:
                problems = [f"not readable as JSON: {error}"]
                record = None

            if record is not None:
                try:
                    validate_record(record)
                except ValueError as error:
                    problems.append(str(error))
                problems.extend(check_provenance(record))
                if suite_module is not None and hasattr(suite_module, "check_contribution"):
                    problems.extend(suite_module.check_contribution(record))

            if problems:
                failed += 1
                typer.echo(f"FAIL {path}")
                for problem in problems:
                    typer.echo(f"  - {problem}")

    if failed:
        typer.echo(f"\n{failed} of {checked} records failed validation")
        raise typer.Exit(code=1)
    typer.echo(f"{checked} records OK")
