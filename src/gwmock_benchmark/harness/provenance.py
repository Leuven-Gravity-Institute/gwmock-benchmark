"""Run provenance: code versions and hardware that produced a benchmark record.

Generic across all benchmarked packages. Importable without any optional
dependency — every package-specific import is deferred to the suite that needs it.
"""

from __future__ import annotations

import os
import platform
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _library_versions(names: tuple[str, ...]) -> dict[str, str]:
    """Return installed versions for ``names`` (skipping any that are absent)."""
    versions: dict[str, str] = {}
    for name in names:
        if not name:
            continue
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            continue
    return versions


def _cpu_model() -> str:
    """Return the CPU model name (Linux ``/proc/cpuinfo``), or a best-effort fallback."""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        return platform.processor() or "unknown"
    return platform.processor() or "unknown"


def _gpu_models() -> list[str]:
    """Return the GPU model names reported by ``nvidia-smi`` (empty if none)."""
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    # A GPU-capable node with no GPU allocated still has nvidia-smi: it exits
    # non-zero and prints "No devices were found", which must not be read as a model.
    if completed.returncode != 0:
        return []
    return [
        line.strip() for line in completed.stdout.splitlines() if line.strip() and "No devices were found" not in line
    ]


def allocated_cpu_cores() -> int:
    """Return the CPU cores allocated to this job (scheduler env, else machine cores)."""
    for variable in ("SLURM_CPUS_PER_TASK", "SLURM_JOB_CPUS_PER_NODE", "OMP_NUM_THREADS"):
        value = os.environ.get(variable, "")
        if value.isdigit():
            return int(value)
    return os.cpu_count() or 1


def provenance(
    *,
    package: str | None = None,
    libraries: tuple[str, ...] = (),
    n_cpu_cores: int | None = None,
    n_gpus: int | None = None,
) -> dict:
    """Return a record of the code versions and hardware behind a benchmark run.

    Args:
        package: Distribution name of the benchmarked package (e.g. ``gwmock-signal``);
            its version is recorded separately so results stay attributable.
        libraries: Extra distribution names whose versions are relevant to the run
            (e.g. ``ripplegw``, ``jax``); absent ones are skipped.
        n_cpu_cores: Override the allocated CPU-core count (defaults to the scheduler
            allocation or the machine core count) — used for CPU core-hours.
        n_gpus: Override the GPU count (defaults to the number ``nvidia-smi`` reports)
            — used for GPU-hours.
    """
    requested = ("gwmock-benchmark", *((package,) if package else ()), *libraries)
    library_versions = _library_versions(requested)
    gpu_models = _gpu_models()
    return {
        "gwmock_benchmark_version": library_versions.get("gwmock-benchmark", "unknown"),
        "package": package,
        "package_version": library_versions.get(package) if package else None,
        "library_versions": library_versions,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        # Hostname is deliberately NOT recorded: records are committed publicly and a
        # node name would leak the cluster. Hardware identity lives in cpu/gpu models.
        "cpu_model": _cpu_model(),
        "gpu_models": gpu_models,
        "n_cpu_cores": n_cpu_cores if n_cpu_cores is not None else allocated_cpu_cores(),
        "n_gpus": n_gpus if n_gpus is not None else len(gpu_models),
    }
