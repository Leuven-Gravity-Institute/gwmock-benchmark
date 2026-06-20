"""Tests for run provenance collection."""

from __future__ import annotations

import importlib
import subprocess

from gwmock_benchmark.harness import provenance

# The harness re-exports a `provenance` function that shadows the submodule of the
# same name, so reach the module explicitly to monkeypatch its internals.
provenance_module = importlib.import_module("gwmock_benchmark.harness.provenance")


def test_provenance_has_core_fields():
    """Provenance returns the core hardware/version fields."""
    prov = provenance()
    for key in ("gwmock_benchmark_version", "cpu_model", "gpu_models", "n_cpu_cores", "n_gpus", "python_version"):
        assert key in prov
    assert isinstance(prov["gpu_models"], list)
    assert prov["n_cpu_cores"] >= 1


def test_absent_package_version_is_none():
    """An uninstalled benchmarked package yields a null package_version."""
    prov = provenance(package="definitely-not-installed-xyz")
    assert prov["package"] == "definitely-not-installed-xyz"
    assert prov["package_version"] is None


def test_overrides_respected():
    """Explicit core/GPU counts override the auto-detected values."""
    prov = provenance(n_cpu_cores=8, n_gpus=1)
    assert prov["n_cpu_cores"] == 8
    assert prov["n_gpus"] == 1


def _fake_run(stdout: str, returncode: int):
    def _run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")

    return _run


def test_gpu_models_parsed(monkeypatch):
    """A successful nvidia-smi query yields the GPU model names."""
    monkeypatch.setattr(provenance_module.subprocess, "run", _fake_run("NVIDIA A30\n", 0))
    assert provenance_module._gpu_models() == ["NVIDIA A30"]


def test_no_devices_message_not_a_gpu(monkeypatch):
    """nvidia-smi's 'No devices were found' (non-zero exit) is not read as a GPU."""
    monkeypatch.setattr(provenance_module.subprocess, "run", _fake_run("No devices were found\n", 6))
    assert provenance_module._gpu_models() == []


def test_nvidia_smi_absent(monkeypatch):
    """A missing nvidia-smi degrades to an empty GPU list."""

    def _raise(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(provenance_module.subprocess, "run", _raise)
    assert provenance_module._gpu_models() == []
