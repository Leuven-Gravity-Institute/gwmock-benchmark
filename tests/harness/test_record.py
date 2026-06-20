"""Tests for the benchmark record schema, validation, and IO."""

from __future__ import annotations

import json

import pytest

from gwmock_benchmark.harness import (
    MAX_RECORD_BYTES,
    SCHEMA_VERSION,
    load_records,
    make_record,
    validate_record,
    write_record,
)


def _record(**overrides) -> dict:
    base = make_record(
        package="gwmock-signal",
        suite="performance",
        label="ripple batched (GPU)",
        configuration={"backend": "ripple", "n_events": 5000, "detectors": ["H1", "L1"]},
        metrics={"wall_seconds_warm": 11.9, "events_per_second_warm": 420.0, "gpu_peak_bytes": None},
        provenance={"package": "gwmock-signal", "package_version": "0.9.0"},
    )
    base.update(overrides)
    return base


def test_make_record_has_schema_version():
    """make_record stamps the current schema version."""
    assert _record()["schema_version"] == SCHEMA_VERSION


def test_valid_record_passes():
    """A well-formed record validates without raising."""
    validate_record(_record())


def test_missing_key_rejected():
    """A record missing a required top-level key is rejected."""
    record = _record()
    del record["metrics"]
    with pytest.raises(ValueError, match="missing required keys"):
        validate_record(record)


def test_non_numeric_metric_rejected():
    """A non-numeric metric value is rejected."""
    with pytest.raises(ValueError, match="must be a number"):
        validate_record(_record(metrics={"throughput": "fast"}))


def test_bool_metric_rejected():
    """A boolean is not accepted as a numeric metric."""
    with pytest.raises(ValueError, match="must be a number"):
        validate_record(_record(metrics={"ok": True}))


def test_nested_array_in_configuration_rejected():
    """A nested array in the configuration is rejected (metrics-only invariant)."""
    with pytest.raises(ValueError, match="flat list of scalars"):
        validate_record(_record(configuration={"grid": [[1, 2], [3, 4]]}))


def test_oversized_record_rejected():
    """A record over the size cap (e.g. a pasted array dump) is rejected."""
    huge = _record(configuration={"samples": list(range(MAX_RECORD_BYTES))})
    with pytest.raises(ValueError, match="over the"):
        validate_record(huge)


def test_write_then_load_roundtrip(tmp_path):
    """A written record is found and parsed back by load_records."""
    write_record(tmp_path / "signal" / "run.json", _record())
    loaded = load_records(tmp_path)
    assert len(loaded) == 1
    assert loaded[0]["label"] == "ripple batched (GPU)"


def test_write_validates_before_writing(tmp_path):
    """write_record validates first and leaves no file on invalid input."""
    with pytest.raises(ValueError, match="must be a number"):
        write_record(tmp_path / "bad.json", _record(metrics={"x": "nope"}))
    assert not (tmp_path / "bad.json").exists()


def test_written_file_is_sorted_json(tmp_path):
    """Records are written as deterministic, key-sorted JSON for clean diffs."""
    path = write_record(tmp_path / "run.json", _record())
    text = path.read_text()
    assert json.loads(text)["package"] == "gwmock-signal"
    assert text.index('"configuration"') < text.index('"metrics"')
