# ruff: noqa: PLC0415
"""CLI commands for the gwmock-signal benchmark suite.

``gwmock-benchmark signal performance`` runs one performance cell; ``... consistency``
runs the ripple-vs-LAL match for every approximant. Both write harness records.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

signal_app = typer.Typer(name="signal", help="Benchmarks for the gwmock-signal package.", no_args_is_help=True)

_DEFAULT_START = 1_126_259_462.0


@signal_app.command("performance", no_args_is_help=True)
def performance(  # noqa: PLR0913
    output_json: Annotated[Path, typer.Option("--output-json", "-o", help="Where to write the record.")],
    backend: Annotated[str, typer.Option(help="Waveform backend: lal, pycbc, or ripple.")] = "ripple",
    method: Annotated[str, typer.Option(help="per-event or batched (batched is ripple-only).")] = "batched",
    approximant: Annotated[str, typer.Option(help="Waveform approximant.")] = "IMRPhenomD",
    detectors: Annotated[list[str] | None, typer.Option("--detector", help="Detector (repeatable).")] = None,
    n_events: Annotated[int, typer.Option(help="Number of events in the catalogue.")] = 5000,
    sampling_frequency: Annotated[float, typer.Option(help="Sample rate [Hz].")] = 4096.0,
    minimum_frequency: Annotated[float, typer.Option(help="Low-frequency cutoff [Hz].")] = 20.0,
    segment_duration: Annotated[float, typer.Option(help="Data-segment duration [s].")] = 64.0,
    start_time: Annotated[float, typer.Option(help="GPS start of the tiled span.")] = _DEFAULT_START,
    end_time: Annotated[float, typer.Option(help="GPS end of the tiled span.")] = _DEFAULT_START + 8192.0,
    chunk_size: Annotated[int | None, typer.Option(help="Batched count-chunk size.")] = None,
    n_chirp_mass_bins: Annotated[int, typer.Option(help="Batched chirp-mass bins.")] = 1,
    n_cpu_cores: Annotated[int | None, typer.Option(help="Override allocated CPU cores.")] = None,
    n_gpus: Annotated[int | None, typer.Option(help="Override allocated GPUs.")] = None,
    label: Annotated[str | None, typer.Option(help="Human-readable run label.")] = None,
    write_data: Annotated[bool, typer.Option("--write-data", help="Write segments to size on disk.")] = False,
    max_product_gb: Annotated[float, typer.Option(help="Refuse runs whose product exceeds this.")] = 8.0,
) -> None:
    """Run one CBC catalogue performance cell (cold + warm) and write its record."""
    from gwmock_benchmark.harness import write_record
    from gwmock_benchmark.suites import signal

    try:
        record = signal.run_performance(
            backend=backend,
            method=method,
            approximant=approximant,
            detectors=tuple(detectors) if detectors else signal._DEFAULT_DETECTORS,
            n_events=n_events,
            sampling_frequency=sampling_frequency,
            minimum_frequency=minimum_frequency,
            segment_duration=segment_duration,
            start_time=start_time,
            end_time=end_time,
            chunk_size=chunk_size,
            n_chirp_mass_bins=n_chirp_mass_bins,
            n_cpu_cores=n_cpu_cores,
            n_gpus=n_gpus,
            label=label,
            write_data=write_data,
            max_product_gb=max_product_gb,
        )
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error

    write_record(output_json, record)
    metrics = record["metrics"]
    typer.echo(
        f"{record['label']}: cold {metrics['wall_seconds_cold']:.2f} s / "
        f"warm {metrics['wall_seconds_warm']:.2f} s (compile {metrics['compile_seconds']:.2f} s) "
        f"-> {output_json}"
    )


@signal_app.command("consistency", no_args_is_help=True)
def consistency(  # noqa: PLR0913 - CLI options map one-to-one to suite knobs
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o", help="Directory for per-approximant records.")],
    sampling_frequency: Annotated[float, typer.Option(help="Sample rate [Hz].")] = 2048.0,
    minimum_frequency: Annotated[float, typer.Option(help="Low-frequency cutoff [Hz].")] = 20.0,
    tidal_minimum_frequency: Annotated[float, typer.Option(help="Cutoff for BNS/NRTidal [Hz].")] = 40.0,
    distance: Annotated[float, typer.Option(help="Luminosity distance [Mpc].")] = 400.0,
    n_cpu_cores: Annotated[int | None, typer.Option(help="Override allocated CPU cores.")] = None,
    n_gpus: Annotated[int | None, typer.Option(help="Override allocated GPUs.")] = None,
) -> None:
    """Run the ripple-vs-LAL match per approximant; write one record per approximant."""
    from gwmock_benchmark.harness import write_record
    from gwmock_benchmark.suites import signal

    records = signal.run_consistency(
        sampling_frequency=sampling_frequency,
        minimum_frequency=minimum_frequency,
        tidal_minimum_frequency=tidal_minimum_frequency,
        distance=distance,
        n_cpu_cores=n_cpu_cores,
        n_gpus=n_gpus,
    )
    for record in records:
        path = write_record(output_dir / f"{record['label']}.json", record)
        typer.echo(f"{record['label']}: min={record['metrics']['min_match']:.5f} -> {path}")
