"""The benchmark record: a small, self-describing, metrics-only JSON document.

A record carries provenance + configuration + scalar metrics — never raw arrays or
time series. Keeping it tiny is what lets results live in-repo at scale, so writing
is gated by structural validation and a hard size cap.
"""

from __future__ import annotations

import json
from pathlib import Path

SCHEMA_VERSION = 1
# Records are metrics-only; this cap rejects accidental array dumps or pasted logs
# before they bloat the repository. A normal record is ~1.5 KB.
MAX_RECORD_BYTES = 16_384

_REQUIRED_KEYS = ("schema_version", "package", "suite", "label", "configuration", "metrics", "provenance")
_SCALAR = (str, int, float, bool, type(None))


def make_record(  # noqa: PLR0913 - a record constructor; each field is an explicit keyword
    *,
    package: str,
    suite: str,
    label: str,
    configuration: dict,
    metrics: dict,
    provenance: dict,
) -> dict:
    """Assemble a benchmark record dict (does not write it).

    Args:
        package: Benchmarked package name (e.g. ``gwmock-signal``).
        suite: Suite/kind within the package (e.g. ``performance``, ``consistency``).
        label: Human-readable label for the run, used in figures and tables.
        configuration: Small dict of the run settings (scalars or flat lists).
        metrics: Dict of measured numbers (values are numbers or ``None``).
        provenance: The mapping returned by :func:`gwmock_benchmark.harness.provenance`.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "package": package,
        "suite": suite,
        "label": label,
        "configuration": configuration,
        "metrics": metrics,
        "provenance": provenance,
    }


def validate_record(record: dict) -> None:
    """Raise :class:`ValueError` if ``record`` is not a well-formed, small record.

    Enforces the required keys, metrics-only numeric values, scalar/flat-list
    configuration (no nested arrays), and the :data:`MAX_RECORD_BYTES` size cap.
    """
    missing = [key for key in _REQUIRED_KEYS if key not in record]
    if missing:
        raise ValueError(f"record missing required keys: {missing}")

    if not isinstance(record["metrics"], dict):
        raise ValueError("'metrics' must be a dict")
    for name, value in record["metrics"].items():
        if not isinstance(value, (int, float, type(None))) or isinstance(value, bool):
            raise ValueError(f"metric {name!r} must be a number or null, got {type(value).__name__}")

    if not isinstance(record["configuration"], dict):
        raise ValueError("'configuration' must be a dict")
    for name, value in record["configuration"].items():
        if isinstance(value, list):
            if not all(isinstance(item, _SCALAR) for item in value):
                raise ValueError(f"configuration {name!r} must be a flat list of scalars (no nested arrays)")
        elif not isinstance(value, _SCALAR):
            raise ValueError(f"configuration {name!r} must be a scalar or a flat list of scalars")

    size = len(_serialize(record))
    if size > MAX_RECORD_BYTES:
        raise ValueError(
            f"record is {size} bytes, over the {MAX_RECORD_BYTES}-byte cap; "
            "records are metrics-only — do not store raw arrays or logs"
        )


def _serialize(record: dict) -> bytes:
    """Return the canonical on-disk JSON bytes for ``record``."""
    return (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_record(path: str | Path, record: dict) -> Path:
    """Validate ``record`` and write it as JSON to ``path`` (creating parents)."""
    validate_record(record)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_serialize(record))
    return path


def load_records(directory: str | Path) -> list[dict]:
    """Load every ``*.json`` record under ``directory`` (recursively), sorted by path."""
    return [json.loads(p.read_text()) for p in sorted(Path(directory).rglob("*.json"))]
