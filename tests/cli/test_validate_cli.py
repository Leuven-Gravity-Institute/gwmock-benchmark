"""Tests for the ``gwmock-benchmark validate`` command."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from gwmock_benchmark.cli.main import app

runner = CliRunner()


def _good_record():
    return {
        "schema_version": 1,
        "package": "gwmock-signal",
        "suite": "consistency",
        "label": "IMRPhenomD",
        "configuration": {"n_overlaps": 6, "minimum_frequency": 20.0},
        "metrics": {"min_overlap": 0.999999, "median_overlap": 0.9999995},
        "provenance": {
            "package_version": "0.9.0",
            "library_versions": {"gwmock-signal": "0.9.0"},
            "n_cpu_cores": 4,
            "n_gpus": 0,
            "platform": "Linux-x86_64",
            "python_version": "3.13",
        },
    }


def _write(tmp_path, record):
    path = tmp_path / "signal" / "consistency"
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{record['label']}.json").write_text(json.dumps(record))


def test_validate_passes_on_good_record(tmp_path):
    """A complete, self-consistent record exits 0."""
    _write(tmp_path, _good_record())
    result = runner.invoke(app, ["validate", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "1 records OK" in result.output


def test_validate_fails_on_tampered_record(tmp_path):
    """A record whose worst overlap beats its median exits non-zero and names the file."""
    record = _good_record()
    record["metrics"]["min_overlap"] = 0.99999999  # now exceeds the median
    _write(tmp_path, record)
    result = runner.invoke(app, ["validate", "--data-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "FAIL" in result.output
    assert "min_overlap" in result.output


def test_validate_fails_on_missing_provenance(tmp_path):
    """An incomplete provenance block is reported."""
    record = _good_record()
    record["provenance"]["package_version"] = None
    _write(tmp_path, record)
    result = runner.invoke(app, ["validate", "--data-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "package_version" in result.output
