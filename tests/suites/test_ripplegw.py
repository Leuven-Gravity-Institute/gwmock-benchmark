"""Tests for the continuous-wave Ripple benchmark report."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from gwmock_benchmark.suites import ripplegw

_DATA = Path(__file__).resolve().parents[2] / "data" / "ripplegw" / "continuous-wave"


def _record(name: str = "ripple_ryzen-ai-7-350.json") -> dict:
    return json.loads((_DATA / name).read_text())


def test_check_contribution_accepts_cpu_and_gpu_records():
    """Committed CPU and GPU records satisfy the CW suite invariants."""
    assert ripplegw.check_contribution(_record()) == []
    assert ripplegw.check_contribution(_record("ripple_nvidia-a100.json")) == []


def test_check_contribution_rejects_invalid_values():
    """Invalid run identity and physical or timing values are reported."""
    record = _record()
    record["suite"] = "other"
    assert ripplegw.check_contribution(record) == ["unknown ripplegw suite 'other'"]

    record = _record()
    record["configuration"]["batch_size"] = 0
    metrics = record["metrics"]
    metrics["etd_weighted_mismatch"] = 1.1
    metrics["etd_weighted_amplitude_ratio"] = 0.0
    for key in (
        "ripple_warm_single_seconds",
        "ripple_warm_vmap_seconds_per_signal",
        "lal_warm_seconds_per_signal",
        "lal_warm_loop_seconds_per_signal",
        "ripple_warm_loop_seconds_per_signal",
    ):
        metrics[key] = -1.0
    problems = ripplegw.check_contribution(record)
    assert any("configuration.batch_size" in problem for problem in problems)
    assert any("metrics.etd_weighted_mismatch" in problem for problem in problems)
    assert any("metrics.etd_weighted_amplitude_ratio" in problem for problem in problems)
    assert any("must be positive" in problem for problem in problems)


def test_check_contribution_rejects_throughput_disagreement():
    """Recorded rates must be reciprocals of the matching warm latencies."""
    record = copy.deepcopy(_record())
    for key in (
        "ripple_warm_single_signals_per_second",
        "ripple_warm_vmap_signals_per_second",
        "lal_warm_signals_per_second",
        "lal_warm_loop_signals_per_second",
        "ripple_warm_loop_signals_per_second",
    ):
        record["metrics"][key] = 1.0
    problems = ripplegw.check_contribution(record)
    assert len(problems) == 5
    assert all("disagrees" in problem for problem in problems)


def test_render_writes_populated_and_empty_tables(tmp_path):
    """The report shows device-labelled records and an empty-state row."""
    target = ripplegw.render([_record(), _record("ripple_nvidia-a100.json")], tmp_path)[0]
    table = target.read_text()
    assert "AMD Ryzen AI 7 350" in table
    assert "NVIDIA A100-SXM4-80GB" in table
    assert "nvidia-a100" in table

    empty_target = ripplegw.render([], tmp_path / "empty")[0]
    assert "No benchmark records yet" in empty_target.read_text()
