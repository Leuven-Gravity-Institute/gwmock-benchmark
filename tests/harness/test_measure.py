"""Tests for resource measurement."""

from __future__ import annotations

import time

from gwmock_benchmark.harness import ResourceUsage, measure


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
