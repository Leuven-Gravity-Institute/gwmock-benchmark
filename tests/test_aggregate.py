"""Tests for the aggregate command and the signal renderer (chart + table snippets)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from gwmock_benchmark.cli.main import app

runner = CliRunner()
_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_aggregate_renders_signal(tmp_path):
    """Aggregate renders the committed signal data into chart + table snippets."""
    ripple_docs = tmp_path / "ripplegw"
    ripple_docs.mkdir()
    (ripple_docs / "index.md").write_text("# Ripple CW\n")
    result = runner.invoke(app, ["aggregate", "--data-dir", str(_REPO_ROOT / "data"), "--docs-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output

    generated = tmp_path / "signal" / "generated"
    for name in ("performance-charts.md", "performance-table.md", "consistency-charts.md", "consistency-table.md"):
        assert (generated / name).exists(), name


def test_aggregate_renders_empty_package_page(tmp_path):
    """Package docs have their generated include even before data is contributed."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    docs_dir = tmp_path / "docs"
    package_docs = docs_dir / "ripplegw"
    package_docs.mkdir(parents=True)
    (package_docs / "index.md").write_text("# Ripple CW\n")
    unknown_docs = docs_dir / "unknown"
    unknown_docs.mkdir()
    (unknown_docs / "index.md").write_text("# Unknown package\n")

    result = runner.invoke(
        app,
        [
            "aggregate",
            "--data-dir",
            str(data_dir),
            "--docs-dir",
            str(docs_dir),
            "--no-clear-cache",
        ],
    )
    assert result.exit_code == 0, result.output
    generated = package_docs / "generated" / "continuous-wave-table.md"
    assert "No benchmark records yet" in generated.read_text()


def test_aggregate_reraises_missing_suite_dependencies(tmp_path, monkeypatch):
    """Import failures inside an existing suite are not hidden as missing suites."""
    import importlib

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    docs_dir = tmp_path / "docs"
    package_docs = docs_dir / "broken"
    package_docs.mkdir(parents=True)
    (package_docs / "index.md").write_text("# Broken package\n")

    def fail_import(module_name):
        raise ModuleNotFoundError("suite dependency missing", name="suite_dependency")

    monkeypatch.setattr(importlib, "import_module", fail_import)
    result = runner.invoke(
        app,
        ["aggregate", "--data-dir", str(data_dir), "--docs-dir", str(docs_dir), "--no-clear-cache"],
    )
    assert isinstance(result.exception, ModuleNotFoundError)
    assert result.exception.name == "suite_dependency"


def test_chart_snippet_carries_valid_json_data(tmp_path):
    """The performance chart snippet embeds a valid, chart-ready JSON payload."""
    runner.invoke(app, ["aggregate", "--data-dir", str(_REPO_ROOT / "data"), "--docs-dir", str(tmp_path)])
    charts = (tmp_path / "signal" / "generated" / "performance-charts.md").read_text()
    assert 'class="benchmark-chart-data"' in charts
    assert 'class="benchmark-charts"' in charts

    payload = re.search(r'data-group="signal-performance">(.*?)</script>', charts, re.DOTALL)
    assert payload is not None
    rows = json.loads(payload.group(1))
    assert rows
    assert "throughput_warm" in rows[0]
    assert "wall_cold" in rows[0]


def test_no_cluster_names_in_rendered_output(tmp_path):
    """Neither the chart data nor the tables leak cluster names — hardware only."""
    runner.invoke(app, ["aggregate", "--data-dir", str(_REPO_ROOT / "data"), "--docs-dir", str(tmp_path)])
    generated = tmp_path / "signal" / "generated"
    for name in ("performance-charts.md", "performance-table.md"):
        text = (generated / name).read_text().lower()
        assert "kuleuven" not in text
        assert "stadius" not in text


def test_aggregate_missing_data_dir_errors(tmp_path):
    """Aggregate fails clearly when the data directory does not exist."""
    result = runner.invoke(app, ["aggregate", "--data-dir", str(tmp_path / "nope"), "--docs-dir", str(tmp_path)])
    assert result.exit_code != 0
