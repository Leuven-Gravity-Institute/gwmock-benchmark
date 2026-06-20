"""Tests for contribution validation: provenance completeness and the tolerance helper."""

from __future__ import annotations

from gwmock_benchmark.harness import check_provenance, close


def _provenance(**overrides):
    base = {
        "package_version": "0.9.0",
        "library_versions": {"gwmock-signal": "0.9.0"},
        "n_cpu_cores": 8,
        "n_gpus": 1,
        "platform": "Linux-x86_64",
        "python_version": "3.13",
    }
    base.update(overrides)
    return {"provenance": base}


def test_complete_provenance_has_no_problems():
    """A fully populated provenance block passes."""
    assert check_provenance(_provenance()) == []


def test_missing_package_version_flagged():
    """A null package version is reported."""
    problems = check_provenance(_provenance(package_version=None))
    assert any("package_version" in p for p in problems)


def test_empty_library_versions_flagged():
    """An empty library-versions map is reported."""
    problems = check_provenance(_provenance(library_versions={}))
    assert any("library_versions" in p for p in problems)


def test_non_positive_cpu_cores_flagged():
    """A zero/negative core count is reported (booleans are not integers here)."""
    assert any("n_cpu_cores" in p for p in check_provenance(_provenance(n_cpu_cores=0)))
    assert any("n_cpu_cores" in p for p in check_provenance(_provenance(n_cpu_cores=True)))


def test_zero_gpus_is_allowed():
    """A CPU-only run (n_gpus == 0) is valid."""
    assert check_provenance(_provenance(n_gpus=0)) == []


def test_close_tolerates_rounding_but_not_disagreement():
    """``close`` accepts float-rounding noise and rejects genuine mismatch."""
    is_close = close(419.6286387363326, 5000 / 11.915297333034687)
    is_mismatch_close = close(2098.0, 419.6)
    assert is_close
    assert not is_mismatch_close
