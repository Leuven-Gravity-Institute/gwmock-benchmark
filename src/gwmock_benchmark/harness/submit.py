"""Render cluster submission scripts for a benchmark command.

Generic and scheduler-specific only in the directives: given any inner shell command
(typically a ``gwmock-benchmark <package> ...`` invocation) and a resource request,
produce a SLURM batch script or an HTCondor submit file. No cluster names or
site-specific assumptions are baked in — accounts, partitions, and environment setup
are left to the caller.
"""

from __future__ import annotations

_MAX_WALLTIME_FIELDS = 3  # HH:MM:SS


def walltime_to_seconds(walltime: str) -> int:
    """Convert an ``HH:MM:SS`` (or ``MM:SS`` / ``SS``) wall-time string to seconds."""
    parts = walltime.split(":")
    if not 1 <= len(parts) <= _MAX_WALLTIME_FIELDS or not all(part.isdigit() for part in parts):
        raise ValueError(f"walltime must be HH:MM:SS, got {walltime!r}")
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return seconds


def render_slurm(  # noqa: PLR0913 - each option maps to a SLURM directive
    command: str,
    *,
    job_name: str = "gwmock-benchmark",
    cpus: int = 1,
    gpus: int = 0,
    gpu_type: str | None = None,
    memory_gb: int = 16,
    walltime: str = "04:00:00",
    account: str | None = None,
    partition: str | None = None,
    output_pattern: str = "%x-%j.out",
) -> str:
    """Return a SLURM batch script that runs ``command`` with the given resources."""
    lines = ["#!/bin/bash", f"#SBATCH --job-name={job_name}", f"#SBATCH --output={output_pattern}"]
    if account:
        lines.append(f"#SBATCH --account={account}")
    if partition:
        lines.append(f"#SBATCH --partition={partition}")
    lines.append(f"#SBATCH --cpus-per-task={cpus}")
    if gpus:
        gres = f"gpu:{gpu_type}:{gpus}" if gpu_type else f"gpu:{gpus}"
        lines.append(f"#SBATCH --gres={gres}")
    lines.append(f"#SBATCH --mem={memory_gb}G")
    lines.append(f"#SBATCH --time={walltime}")
    lines += [
        "",
        "set -euo pipefail",
        "",
        "# Activate your environment here (module load / source venv) before running.",
        command,
        "",
    ]
    return "\n".join(lines)


def render_htcondor(  # noqa: PLR0913 - each option maps to an HTCondor directive
    command: str,
    *,
    job_name: str = "gwmock-benchmark",
    cpus: int = 1,
    gpus: int = 0,
    gpu_min_capability: float | None = None,
    memory_gb: int = 16,
    walltime: str = "04:00:00",
    output_dir: str = ".",
) -> str:
    """Return an HTCondor submit file that runs ``command`` with the given resources.

    The command must not contain single quotes (it is wrapped in ``bash -c '...'``).
    """
    if "'" in command:
        raise ValueError("command must not contain single quotes (it is wrapped in bash -c '...')")
    lines = [
        "universe = vanilla",
        "executable = /bin/bash",
        f"arguments = \"-c '{command}'\"",
        # Some pools block `getenv`; set what the job needs explicitly instead.
        'environment = "HOME=$ENV(HOME)"',
        "should_transfer_files = NO",
        f"output = {output_dir}/{job_name}.$(Cluster).out",
        f"error  = {output_dir}/{job_name}.$(Cluster).err",
        f"log    = {output_dir}/{job_name}.$(Cluster).log",
        f"request_cpus   = {cpus}",
        f"request_memory = {memory_gb} GB",
        f"RequestWallTime = {walltime_to_seconds(walltime)}",
    ]
    if gpus:
        lines.append(f"request_gpus   = {gpus}")
        if gpu_min_capability is not None:
            # Avoid GPUs whose XLA compile is pathologically slow (e.g. Turing 7.5).
            lines.append(f"require_gpus    = (Capability >= {gpu_min_capability})")
    lines += [f'+JobBatchName  = "{job_name}"', "", "queue", ""]
    return "\n".join(lines)
