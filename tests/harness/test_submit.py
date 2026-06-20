"""Tests for the cluster submission-script generators."""

from __future__ import annotations

import pytest

from gwmock_benchmark.harness import render_htcondor, render_slurm, walltime_to_seconds

_COMMAND = "gwmock-benchmark signal performance --backend ripple -o out.json"


def test_walltime_to_seconds():
    """Wall-time strings convert to seconds across HH:MM:SS / MM:SS / SS."""
    assert walltime_to_seconds("04:00:00") == 14400
    assert walltime_to_seconds("90:00") == 5400
    assert walltime_to_seconds("45") == 45


def test_walltime_rejects_garbage():
    """A malformed wall-time string is rejected."""
    with pytest.raises(ValueError, match="HH:MM:SS"):
        walltime_to_seconds("4h")


def test_slurm_directives():
    """The SLURM script carries the command and the requested resources."""
    script = render_slurm(_COMMAND, cpus=8, gpus=1, gpu_type="a30", memory_gb=32, walltime="02:00:00", account="acct")
    assert script.startswith("#!/bin/bash")
    assert "#SBATCH --cpus-per-task=8" in script
    assert "#SBATCH --gres=gpu:a30:1" in script
    assert "#SBATCH --mem=32G" in script
    assert "#SBATCH --time=02:00:00" in script
    assert "#SBATCH --account=acct" in script
    assert _COMMAND in script


def test_slurm_cpu_only_has_no_gres():
    """A CPU-only SLURM script omits the GPU gres line."""
    script = render_slurm(_COMMAND, gpus=0)
    assert "--gres" not in script


def test_htcondor_directives():
    """The HTCondor submit file wraps the command and sets resources + wall time."""
    script = render_htcondor(_COMMAND, cpus=4, gpus=1, gpu_min_capability=8.0, memory_gb=16, walltime="01:00:00")
    assert "universe = vanilla" in script
    assert f"arguments = \"-c '{_COMMAND}'\"" in script
    assert "request_cpus   = 4" in script
    assert "request_gpus   = 1" in script
    assert "require_gpus    = (Capability >= 8.0)" in script
    assert "RequestWallTime = 3600" in script
    assert script.rstrip().endswith("queue")


def test_htcondor_cpu_only_has_no_gpu_request():
    """A CPU-only HTCondor file omits request_gpus."""
    script = render_htcondor(_COMMAND, gpus=0)
    assert "request_gpus" not in script


def test_htcondor_rejects_single_quote():
    """A command with single quotes is rejected (bash -c '...' wrapping)."""
    with pytest.raises(ValueError, match="single quotes"):
        render_htcondor("echo 'hi'")
