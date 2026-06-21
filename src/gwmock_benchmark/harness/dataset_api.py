"""Static JSON API over the committed benchmark dataset.

The published docs site is static (GitHub Pages), so the "API" is a small tree of
JSON files written next to the rendered report and served at stable URLs under
``data/v1/``:

- ``index.json``              — manifest: versions, counts, and links to everything.
- ``records.json``            — every record across all packages/suites, one request.
- ``<package>/<suite>.json``  — the same envelope, filtered to one package + suite.
- ``schema/record-v1.json``   — JSON Schema for a single record.

This is a faithful dump of the already-validated, size-capped records (see
:mod:`gwmock_benchmark.harness.record`); it adds no benchmark-domain knowledge, so it
lives here in the generic harness rather than in any package suite. Stdlib-only and
import-safe, like the rest of ``harness/``.
"""

from __future__ import annotations

import json
from pathlib import Path

from gwmock_benchmark.harness.record import _REQUIRED_KEYS, SCHEMA_VERSION

# Bumped only on a breaking change to the API layout. Within a version the shape is
# additive-only, so consumers can pin ``data/v1/`` and not break on new fields/records.
API_VERSION = "v1"

# A configuration value is a scalar or a flat list of scalars (mirrors
# ``record.validate_record``); a metric is a number or null (never bool).
_SCALAR_SCHEMA = {"type": ["string", "number", "integer", "boolean", "null"]}
_METRIC_SCHEMA = {"type": ["number", "null"]}


def _api_base(site_url: str | None) -> str:
    """Return the absolute base URL of the API tree, or ``""`` for relative links.

    With a known ``site_url`` the manifest advertises absolute URLs; without one it
    falls back to links relative to ``index.json`` (which still resolve on any host).
    """
    if not site_url:
        return ""
    return site_url.rstrip("/") + "/data/v1/"


def _link(base: str, relative: str) -> str:
    """Join the API base with a path relative to the API root (relative if no base)."""
    return f"{base}{relative}" if base else relative


def build_record_schema(site_url: str | None = None) -> dict:
    """Return a JSON Schema (draft 2020-12) for a single benchmark record.

    Built from :data:`record._REQUIRED_KEYS` / :data:`record.SCHEMA_VERSION` and the
    metrics-only / scalar-or-flat-list rules in :func:`record.validate_record`, so the
    published schema cannot drift from what the harness actually accepts.
    """
    schema: dict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "gwmock-benchmark record",
        "description": "A single metrics-only benchmark data point.",
        "type": "object",
        "required": list(_REQUIRED_KEYS),
        "additionalProperties": False,
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "package": {"type": "string", "description": "Benchmarked package distribution name."},
            "suite": {"type": "string", "description": "Suite within the package, e.g. performance or consistency."},
            "label": {"type": "string", "description": "Human-readable label used in figures and tables."},
            "configuration": {
                "type": "object",
                "description": "Run settings: each value is a scalar or a flat list of scalars.",
                "additionalProperties": {
                    "anyOf": [_SCALAR_SCHEMA, {"type": "array", "items": _SCALAR_SCHEMA}],
                },
            },
            "metrics": {
                "type": "object",
                "description": "Measured numbers; each value is a number or null.",
                "additionalProperties": _METRIC_SCHEMA,
            },
            "provenance": {
                "type": "object",
                "description": "Code versions and hardware behind the run (no hostname).",
                "properties": {
                    "gwmock_benchmark_version": {"type": ["string", "null"]},
                    "package": {"type": ["string", "null"]},
                    "package_version": {"type": ["string", "null"]},
                    "library_versions": {"type": "object", "additionalProperties": {"type": "string"}},
                    "python_version": {"type": "string"},
                    "platform": {"type": "string"},
                    "cpu_model": {"type": "string"},
                    "gpu_models": {"type": "array", "items": {"type": "string"}},
                    "n_cpu_cores": {"type": ["integer", "null"]},
                    "n_gpus": {"type": ["integer", "null"]},
                    "contributor": {"type": ["string", "null"]},
                },
                "additionalProperties": True,
            },
        },
    }
    base = _api_base(site_url)
    if base:
        schema["$id"] = _link(base, "schema/record-v1.json")
    return schema


def _envelope(records: list[dict], generated: str | None) -> dict:
    """Wrap ``records`` in the self-describing API envelope."""
    return {
        "api_version": API_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated": generated,
        "count": len(records),
        "records": records,
    }


def _write_json(path: Path, obj: dict, written: list[Path]) -> None:
    """Write ``obj`` as canonical JSON to ``path`` (creating parents) and track it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    written.append(path)


def write_dataset_api(
    records_by_segment: dict[str, list[dict]],
    output_dir: Path,
    *,
    site_url: str | None = None,
    generated: str | None = None,
) -> list[Path]:
    """Write the static JSON API for the committed dataset under ``output_dir``.

    Args:
        records_by_segment: Records grouped by ``data/<segment>/`` directory name
            (e.g. ``"signal"``); the segment is used as the URL path component.
        output_dir: Directory to write the API tree into (e.g. ``docs/data/v1``).
        site_url: Canonical site URL; when set, manifest links are absolute.
        generated: ISO-8601 build timestamp recorded in the manifest and envelopes.

    Returns:
        The paths written, in write order.
    """
    base = _api_base(site_url)
    written: list[Path] = []

    all_records: list[dict] = []
    packages: list[dict] = []
    for segment in sorted(records_by_segment):
        records = records_by_segment[segment]
        all_records.extend(records)
        suite_entries: list[dict] = []
        for suite in sorted({r["suite"] for r in records}):
            subset = [r for r in records if r["suite"] == suite]
            relative = f"{segment}/{suite}.json"
            _write_json(output_dir / segment / f"{suite}.json", _envelope(subset, generated), written)
            suite_entries.append({"suite": suite, "count": len(subset), "url": _link(base, relative)})
        packages.append(
            {
                "package": segment,
                "distributions": sorted({r["package"] for r in records if r.get("package")}),
                "count": len(records),
                "suites": suite_entries,
            }
        )

    _write_json(output_dir / "records.json", _envelope(all_records, generated), written)
    _write_json(output_dir / "schema" / "record-v1.json", build_record_schema(site_url), written)

    manifest = {
        "api_version": API_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated": generated,
        "site_url": site_url or None,
        "record_count": len(all_records),
        "packages": packages,
        "links": {
            "self": _link(base, "index.json"),
            "records": _link(base, "records.json"),
            "schema": _link(base, "schema/record-v1.json"),
        },
    }
    _write_json(output_dir / "index.json", manifest, written)
    return written
