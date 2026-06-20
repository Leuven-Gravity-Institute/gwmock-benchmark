"""Tests for the aggregate command and the signal renderer.

Rendering needs matplotlib (the docs group); the tests skip if it is absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from gwmock_benchmark.cli.main import app

pytest.importorskip("matplotlib")

runner = CliRunner()
_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_aggregate_renders_signal(tmp_path):
    """Aggregate renders the committed signal data into figures + table snippets."""
    result = runner.invoke(app, ["aggregate", "--data-dir", str(_REPO_ROOT / "data"), "--docs-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output

    figures = tmp_path / "signal" / "figures"
    generated = tmp_path / "signal" / "generated"
    assert (figures / "performance_throughput.svg").exists()
    assert (figures / "consistency_matches.svg").exists()
    assert (generated / "performance-table.md").exists()

    table = (generated / "consistency-table.md").read_text()
    assert "Approximant" in table
    # Hardware-only labelling — no cluster names leak into the rendered output.
    perf_table = (generated / "performance-table.md").read_text()
    assert "kuleuven" not in perf_table.lower()
    assert "stadius" not in perf_table.lower()


def test_aggregate_missing_data_dir_errors(tmp_path):
    """Aggregate fails clearly when the data directory does not exist."""
    result = runner.invoke(app, ["aggregate", "--data-dir", str(tmp_path / "nope"), "--docs-dir", str(tmp_path)])
    assert result.exit_code != 0
