"""Tests for resource measurement."""

from __future__ import annotations

import importlib
import time

from gwmock_benchmark.harness import ResourceUsage, measure

# `measure` is re-exported as a function, shadowing the submodule; reach it explicitly.
measure_module = importlib.import_module("gwmock_benchmark.harness.measure")


def test_measure_records_wall_time():
    """Measure captures wall time and resident memory around the block."""
    with measure(sample_interval_seconds=0.01) as usage:
        time.sleep(0.05)
    assert isinstance(usage, ResourceUsage)
    assert usage.wall_seconds >= 0.05
    assert usage.peak_rss_bytes > 0
    assert usage.average_rss_bytes > 0


def test_output_bytes_settable_in_block():
    """The caller can record output_bytes inside the measured block."""
    with measure(sample_interval_seconds=0.01) as usage:
        usage.output_bytes = 12345
    assert usage.output_bytes == 12345


def test_gpu_peak_none_without_gpu():
    """The GPU probe degrades to None when no JAX/GPU is available."""
    with measure(sample_interval_seconds=0.01) as usage:
        pass
    assert usage.gpu_peak_bytes is None


def test_current_rss_falls_back_when_proc_unavailable(monkeypatch):
    """Without /proc (e.g. macOS), current RSS falls back to a non-zero peak."""

    class _NoProc:
        def __init__(self, *_args, **_kwargs):
            pass

        def read_text(self, *_args, **_kwargs):
            raise FileNotFoundError

    monkeypatch.setattr(measure_module, "Path", _NoProc)
    assert measure_module._current_rss_bytes() > 0
