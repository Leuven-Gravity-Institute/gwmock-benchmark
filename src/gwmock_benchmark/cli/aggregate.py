# ruff: noqa: PLC0415
"""The ``gwmock-benchmark aggregate`` command.

Render the committed dataset into the docs site: for each ``data/<package>/`` group,
load its records and call that package suite's ``render`` to write figures + table
snippets under ``docs/<package>/``. It also writes a static JSON API of the raw
records under ``docs/data/v1/`` (see :mod:`gwmock_benchmark.harness.dataset_api`), so
the published site exposes the results at stable URLs as well as in figures. Run
before ``zensical build`` in the docs pipeline.

The rendered snippets are pulled into pages via ``--8<--`` includes. zensical's
incremental cache keys on each source page's own content, so it does NOT notice when
an included snippet changes and would serve a stale figure/table on the next build.
To keep ``aggregate && zensical build`` correct, this command clears zensical's
``.cache`` after regenerating, forcing a fresh render (CI already builds cache-less).
"""

from __future__ import annotations

import importlib
import shutil
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

# zensical writes its incremental build cache here, relative to the working directory.
_ZENSICAL_CACHE = Path(".cache")
# zensical's config; the canonical site_url lives here, single source of truth.
_ZENSICAL_CONFIG = Path("zensical.toml")


def _config_site_url() -> str | None:
    """Return the ``site_url`` from ``zensical.toml`` in the working directory, if set."""
    if not _ZENSICAL_CONFIG.is_file():
        return None
    config = tomllib.loads(_ZENSICAL_CONFIG.read_text())
    return config.get("project", {}).get("site_url") or config.get("site_url")


def aggregate_command(
    data_dir: Annotated[Path, typer.Option("--data-dir", help="Directory of committed records.")] = Path("data"),
    docs_dir: Annotated[Path, typer.Option("--docs-dir", help="Docs directory to render into.")] = Path("docs"),
    site_url: Annotated[
        str | None,
        typer.Option(
            "--site-url",
            help="Canonical site URL for absolute API links; defaults to zensical.toml, "
            "empty string for relative links.",
        ),
    ] = None,
    clear_cache: Annotated[
        bool,
        typer.Option(
            "--clear-cache/--no-clear-cache",
            help="Clear zensical's .cache so the next build picks up regenerated includes.",
        ),
    ] = True,
) -> None:
    """Render figures and table snippets from the committed dataset into the docs."""
    from gwmock_benchmark.harness import load_records, write_dataset_api

    if not data_dir.is_dir():
        raise typer.BadParameter(f"no data directory at {data_dir}")

    records_by_segment: dict[str, list[dict]] = {}
    for package_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        records = load_records(package_dir)
        if not records:
            continue
        records_by_segment[package_dir.name] = records
        try:
            suite = importlib.import_module(f"gwmock_benchmark.suites.{package_dir.name}")
        except ModuleNotFoundError as error:
            raise typer.BadParameter(f"no suite module for data/{package_dir.name}/") from error
        written = suite.render(records, docs_dir / package_dir.name)
        typer.echo(
            f"{package_dir.name}: {len(records)} records -> {len(written)} artifacts in {docs_dir / package_dir.name}"
        )

    if not records_by_segment:
        typer.echo(f"no records found under {data_dir}")
    else:
        # Faithful JSON dump of the raw records, served alongside the rendered report.
        resolved_url = _config_site_url() if site_url is None else (site_url or None)
        api_dir = docs_dir / "data" / "v1"
        api_written = write_dataset_api(
            records_by_segment,
            api_dir,
            site_url=resolved_url,
            generated=datetime.now(UTC).isoformat(),
        )
        total = sum(len(r) for r in records_by_segment.values())
        typer.echo(f"data API: {total} records -> {len(api_written)} files in {api_dir}")

    # zensical can't see that the included snippets changed; drop its cache so the
    # next build re-renders the affected pages instead of serving stale figures.
    if clear_cache and _ZENSICAL_CACHE.is_dir():
        shutil.rmtree(_ZENSICAL_CACHE)
        typer.echo(f"cleared {_ZENSICAL_CACHE}/ (zensical will re-render on next build)")
