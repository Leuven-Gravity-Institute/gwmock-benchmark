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


# --- contribution validation (pure arithmetic; no [signal] extra needed) ---------


def _performance_record(**metric_overrides) -> dict:
    """Build a self-consistent performance record from the harness's own formulas."""
    import math

    n_events, n_cpu, n_gpu = 5000, 8, 1
    wall_cold, wall_warm = 27.0, 12.0
    detectors = ["H1", "L1", "V1"]
    sf, sd, start = 4096.0, 64.0, 1_126_259_462.0
    end = start + 8192.0
    raw = math.ceil((end - start) / sd) * len(detectors) * round(sd * sf) * 8
    metrics = {
        "wall_seconds_cold": wall_cold,
        "wall_seconds_warm": wall_warm,
        "compile_seconds": max(wall_cold - wall_warm, 0.0),
        "events_per_second_cold": n_events / wall_cold,
        "events_per_second_warm": n_events / wall_warm,
        "cpu_core_hours_cold": wall_cold / 3600.0 * n_cpu,
        "cpu_core_hours_warm": wall_warm / 3600.0 * n_cpu,
        "gpu_hours_cold": wall_cold / 3600.0 * n_gpu,
        "gpu_hours_warm": wall_warm / 3600.0 * n_gpu,
        "peak_rss_bytes": 6_000_000_000,
        "average_rss_bytes": 5_000_000_000,
        "gpu_peak_bytes": 5_000_000_000,
        "output_bytes": raw,
    }
    metrics.update(metric_overrides)
    return {
        "schema_version": 1,
        "package": "gwmock-signal",
        "suite": "performance",
        "label": "test",
        "configuration": {
            "backend": "ripple",
            "method": "batched",
            "approximant": "IMRPhenomD",
            "detectors": detectors,
            "n_events": n_events,
            "sampling_frequency": sf,
            "minimum_frequency": 20.0,
            "segment_duration": sd,
            "start_time": start,
            "end_time": end,
        },
        "metrics": metrics,
        "provenance": {"n_cpu_cores": n_cpu, "n_gpus": n_gpu},
    }


def test_check_contribution_accepts_consistent_performance():
    """A record whose metrics follow the defining formulas passes."""
    assert signal.check_contribution(_performance_record()) == []


def test_check_contribution_flags_fabricated_throughput():
    """Inflating throughput without changing the wall time is caught."""
    record = _performance_record(events_per_second_warm=5000 / 12.0 * 5)
    problems = signal.check_contribution(record)
    assert any("events_per_second_warm" in p for p in problems)


def test_check_contribution_flags_inconsistent_compile():
    """A compile time that is not cold-minus-warm is caught."""
    problems = signal.check_contribution(_performance_record(compile_seconds=999.0))
    assert any("compile_seconds" in p for p in problems)


def test_check_contribution_flags_impossible_output_size():
    """An output size below the raw data product is caught."""
    problems = signal.check_contribution(_performance_record(output_bytes=1))
    assert any("output_bytes" in p for p in problems)


def test_check_contribution_flags_worst_beating_median():
    """A consistency record whose worst overlap beats its median is caught."""
    record = {
        "schema_version": 1,
        "package": "gwmock-signal",
        "suite": "consistency",
        "label": "IMRPhenomD",
        "configuration": {"n_overlaps": 6, "minimum_frequency": 20.0},
        "metrics": {"min_overlap": 0.9999999, "median_overlap": 0.999},
        "provenance": {"n_cpu_cores": 4, "n_gpus": 0},
    }
    problems = signal.check_contribution(record)
    assert any("min_overlap" in p for p in problems)


@pytest.mark.integration
def test_committed_consistency_records_reproduce():
    """Re-running the deterministic suite reproduces every committed consistency record.

    This takes consistency out of the trust model: a fabricated overlap cannot survive
    an independent recomputation against the same toolchain.
    """
    from pathlib import Path

    from gwmock_benchmark.harness import load_records

    data_dir = Path(__file__).resolve().parents[2] / "data" / "signal" / "consistency"
    records = load_records(data_dir)
    assert records, f"no committed consistency records under {data_dir}"
    problems = signal.reproduce_consistency(records)
    assert not problems, "\n".join(problems)


def test_performance_table_renders_linked_contributor():
    """A recorded contributor handle renders as a GitHub profile link; absent is blank."""
    record = _performance_record()
    record["provenance"]["contributor"] = "octocat"
    table = signal._performance_table([record])
    assert "<th>contributor</th>" in table
    assert '<a href="https://github.com/octocat"' in table
    assert "@octocat" in table

    record["provenance"]["contributor"] = None
    assert signal._contributor_cell(record) == ""


def test_contributor_cell_escapes_handle():
    """The handle is HTML-escaped even though valid handles never need it (defence in depth)."""
    record = _performance_record()
    record["provenance"]["contributor"] = "a<b>"
    assert "<b>" not in signal._contributor_cell(record)
