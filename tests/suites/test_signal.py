"""Tests for the gwmock-signal benchmark suite.

The unit tests run in the base environment (import-safety + CLI wiring). The
``integration`` tests need the ``[signal]`` extra and actually generate waveforms.
"""

from __future__ import annotations

import pytest

from gwmock_benchmark.harness import validate_record
from gwmock_benchmark.suites import signal


def test_suite_metadata():
    """The suite exposes its package name and the two workload entry points."""
    assert signal.PACKAGE == "gwmock-signal"
    assert callable(signal.run_performance)
    assert callable(signal.run_consistency)


def test_signal_cli_registered():
    """The signal sub-app is mounted on the main CLI with both commands."""
    from gwmock_benchmark.cli.main import app
    from gwmock_benchmark.cli.signal import signal_app

    groups = [group.typer_instance.info.name for group in app.registered_groups]
    assert "signal" in groups
    command_names = {command.name for command in signal_app.registered_commands}
    assert {"performance", "consistency"} <= command_names


@pytest.mark.integration
def test_performance_batched_record():
    """A batched performance cell returns a valid record with cold/warm metrics."""
    record = signal.run_performance(
        backend="ripple",
        method="batched",
        n_events=8,
        detectors=("H1", "L1"),
        end_time=signal._DEFAULT_START + 512.0,
        n_cpu_cores=1,
        n_gpus=0,
        label="test",
    )
    validate_record(record)
    assert record["suite"] == "performance"
    assert record["metrics"]["wall_seconds_warm"] > 0
    assert record["metrics"]["events_per_second_warm"] > 0


@pytest.mark.integration
def test_performance_rejects_batched_non_ripple():
    """The batched method is rejected for non-ripple backends."""
    with pytest.raises(ValueError, match="batched method"):
        signal.run_performance(backend="lal", method="batched", n_events=2)


@pytest.mark.integration
def test_performance_oversized_span_rejected():
    """A span whose product exceeds the cap is refused up front."""
    with pytest.raises(ValueError, match="max_product_gb"):
        signal.run_performance(backend="ripple", method="batched", n_events=2, end_time=signal._DEFAULT_START + 3.0e7)


@pytest.mark.integration
def test_consistency_records():
    """Consistency yields one valid record per approximant, all matching LAL closely."""
    records = signal.run_consistency(n_cpu_cores=1, n_gpus=0)
    assert records
    for record in records:
        validate_record(record)
        assert record["suite"] == "consistency"
        assert record["metrics"]["min_overlap"] > 0.999
