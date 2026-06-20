"""End-to-end tests for the ``gwmock-benchmark submit`` CLI command."""

from __future__ import annotations

from typer.testing import CliRunner

from gwmock_benchmark.cli.main import app

runner = CliRunner()


def test_submit_registered():
    """The submit command is mounted on the main app."""
    result = runner.invoke(app, ["submit", "--help"])
    assert result.exit_code == 0
    assert "slurm" in result.output.lower()


def test_submit_slurm_writes_script(tmp_path):
    """Submit slurm writes a batch script containing the command."""
    out = tmp_path / "job.slurm"
    result = runner.invoke(
        app,
        ["submit", "slurm", "-c", "gwmock-benchmark signal performance -o r.json", "-o", str(out), "--gpus", "1"],
    )
    assert result.exit_code == 0, result.output
    text = out.read_text()
    assert text.startswith("#!/bin/bash")
    assert "--gres=gpu:1" in text
    assert "gwmock-benchmark signal performance" in text


def test_submit_htcondor_writes_submit_file(tmp_path):
    """Submit htcondor writes a submit file with a wall-time request."""
    out = tmp_path / "job.sub"
    result = runner.invoke(
        app, ["submit", "htcondor", "-c", "gwmock-benchmark signal consistency -o data", "-o", str(out)]
    )
    assert result.exit_code == 0, result.output
    text = out.read_text()
    assert "universe = vanilla" in text
    assert "RequestWallTime = 14400" in text


def test_submit_htcondor_single_quote_rejected(tmp_path):
    """A command with single quotes is rejected with a clear CLI error."""
    out = tmp_path / "job.sub"
    result = runner.invoke(app, ["submit", "htcondor", "-c", "echo 'hi'", "-o", str(out)])
    assert result.exit_code != 0
    assert not out.exists()
