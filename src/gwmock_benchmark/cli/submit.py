# ruff: noqa: PLC0415
"""The ``gwmock-benchmark submit`` command.

Wrap any inner benchmark command into a SLURM batch script or an HTCondor submit
file with the requested resources, for running benchmarks on a cluster.
"""

from __future__ import annotations

import enum
from pathlib import Path
from typing import Annotated

import typer


class Scheduler(enum.StrEnum):
    """Supported cluster schedulers."""

    slurm = "slurm"
    htcondor = "htcondor"


def submit_command(  # noqa: PLR0913 - resource knobs map one-to-one to scheduler directives
    scheduler: Annotated[Scheduler, typer.Argument(help="Cluster scheduler.")],
    command: Annotated[str, typer.Option("--command", "-c", help="Inner command to run on the node.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Where to write the submission script.")],
    job_name: Annotated[str, typer.Option(help="Job name.")] = "gwmock-benchmark",
    cpus: Annotated[int, typer.Option(help="CPU cores to request.")] = 8,
    gpus: Annotated[int, typer.Option(help="GPUs to request (0 = none).")] = 0,
    memory_gb: Annotated[int, typer.Option(help="Memory to request [GB].")] = 16,
    walltime: Annotated[str, typer.Option(help="Wall-time limit HH:MM:SS.")] = "04:00:00",
    account: Annotated[str | None, typer.Option(help="SLURM account.")] = None,
    partition: Annotated[str | None, typer.Option(help="SLURM partition.")] = None,
    gpu_type: Annotated[str | None, typer.Option(help="SLURM GPU type (gres gpu:TYPE:N).")] = None,
    gpu_min_capability: Annotated[
        float | None, typer.Option(help="HTCondor min GPU compute capability (e.g. 8.0).")
    ] = None,
) -> None:
    """Render a cluster submission script for a benchmark command."""
    from gwmock_benchmark.harness import render_htcondor, render_slurm

    try:
        if scheduler is Scheduler.slurm:
            script = render_slurm(
                command,
                job_name=job_name,
                cpus=cpus,
                gpus=gpus,
                gpu_type=gpu_type,
                memory_gb=memory_gb,
                walltime=walltime,
                account=account,
                partition=partition,
            )
        else:
            script = render_htcondor(
                command,
                job_name=job_name,
                cpus=cpus,
                gpus=gpus,
                gpu_min_capability=gpu_min_capability,
                memory_gb=memory_gb,
                walltime=walltime,
                output_dir=str(output.parent),
            )
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(script)
    typer.echo(f"wrote {scheduler.value} script -> {output}")
