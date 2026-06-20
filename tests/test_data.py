"""Guard the committed benchmark dataset.

Every record under ``data/`` must satisfy the harness schema and size cap, and must
not leak a hostname. This is the gate that keeps contributed result files well-formed
and tiny enough to live in the repository.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from gwmock_benchmark.harness import MAX_RECORD_BYTES, check_provenance, validate_record

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_RECORDS = sorted(_DATA_DIR.rglob("*.json"))


def test_data_dir_exists():
    """The committed dataset directory is present and non-empty."""
    assert _RECORDS, f"no records found under {_DATA_DIR}"


@pytest.mark.parametrize("path", _RECORDS, ids=lambda p: str(p.relative_to(_DATA_DIR)))
def test_record_is_valid(path):
    """Each committed record satisfies the schema, size cap, and carries no hostname."""
    record = json.loads(path.read_text())
    validate_record(record)
    assert path.stat().st_size <= MAX_RECORD_BYTES
    assert "hostname" not in record.get("provenance", {}), f"{path} leaks a hostname"


@pytest.mark.parametrize("path", _RECORDS, ids=lambda p: str(p.relative_to(_DATA_DIR)))
def test_record_is_internally_consistent(path):
    """Each committed record has complete provenance and self-consistent derived metrics."""
    record = json.loads(path.read_text())
    problems = check_provenance(record)
    package = path.relative_to(_DATA_DIR).parts[0]
    suite_module = importlib.import_module(f"gwmock_benchmark.suites.{package}")
    if hasattr(suite_module, "check_contribution"):
        problems.extend(suite_module.check_contribution(record))
    assert not problems, "\n".join(problems)
