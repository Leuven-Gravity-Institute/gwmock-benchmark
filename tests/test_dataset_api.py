"""Tests for the static JSON API written by the aggregate command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gwmock_benchmark.cli.main import app
from gwmock_benchmark.harness import record as record_mod
from gwmock_benchmark.harness import validate_record

runner = CliRunner()
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATA = _REPO_ROOT / "data"


def _aggregate(tmp_path: Path, *extra: str):
    result = runner.invoke(app, ["aggregate", "--data-dir", str(_DATA), "--docs-dir", str(tmp_path), *extra])
    assert result.exit_code == 0, result.output
    return tmp_path / "data" / "v1"


def _committed_records() -> list[dict]:
    return [json.loads(p.read_text()) for p in _DATA.rglob("*.json")]


def test_api_files_written(tmp_path):
    """Aggregate writes the manifest, consolidated dump, per-suite splits, and schema."""
    api = _aggregate(tmp_path)
    assert (api / "index.json").exists()
    assert (api / "records.json").exists()
    assert (api / "schema" / "record-v1.json").exists()
    assert (api / "signal" / "performance.json").exists()
    assert (api / "signal" / "consistency.json").exists()


def test_records_json_is_complete_and_valid(tmp_path):
    """records.json contains every committed record, each well-formed."""
    api = _aggregate(tmp_path)
    payload = json.loads((api / "records.json").read_text())

    assert payload["api_version"] == "v1"
    assert payload["schema_version"] == record_mod.SCHEMA_VERSION
    assert payload["count"] == len(_committed_records()) == len(payload["records"])
    for rec in payload["records"]:
        validate_record(rec)  # raises if malformed


def test_per_suite_splits_partition_the_dataset(tmp_path):
    """Per-suite files sum to the consolidated count and stay within their suite."""
    api = _aggregate(tmp_path)
    total = json.loads((api / "records.json").read_text())["count"]

    split_total = 0
    for suite in ("performance", "consistency"):
        payload = json.loads((api / "signal" / f"{suite}.json").read_text())
        assert payload["count"] == len(payload["records"])
        assert {r["suite"] for r in payload["records"]} == {suite}
        assert {r["package"] for r in payload["records"]} == {"gwmock-signal"}
        split_total += payload["count"]
    assert split_total == total


def test_manifest_counts_and_links_resolve(tmp_path):
    """index.json counts agree with the splits and every link points at a written file."""
    api = _aggregate(tmp_path)
    manifest = json.loads((api / "index.json").read_text())

    assert manifest["record_count"] == json.loads((api / "records.json").read_text())["count"]

    # Default run resolves site_url from zensical.toml -> absolute links.
    base = "https://leuven-gravity-institute.github.io/gwmock-benchmark/data/v1/"
    for link in manifest["links"].values():
        assert link.startswith(base)
        assert (api / link[len(base) :]).exists()

    for package in manifest["packages"]:
        seg = package["package"]
        assert package["count"] == sum(s["count"] for s in package["suites"])
        for suite in package["suites"]:
            payload = json.loads((api / seg / f"{suite['suite']}.json").read_text())
            assert payload["count"] == suite["count"]
            assert suite["url"].startswith(base)
            assert (api / suite["url"][len(base) :]).exists()


def test_schema_tracks_record_module(tmp_path):
    """The published schema cannot drift from record.py's required keys / version."""
    api = _aggregate(tmp_path)
    schema = json.loads((api / "schema" / "record-v1.json").read_text())

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert set(schema["required"]) == set(record_mod._REQUIRED_KEYS)
    assert schema["properties"]["schema_version"]["const"] == record_mod.SCHEMA_VERSION


def test_site_url_override_controls_link_style(tmp_path):
    """An explicit --site-url yields absolute links; an empty one yields relative links."""
    api = _aggregate(tmp_path, "--site-url", "https://example.test/")
    manifest = json.loads((api / "index.json").read_text())
    assert manifest["links"]["records"] == "https://example.test/data/v1/records.json"

    api_rel = _aggregate(tmp_path, "--site-url", "")
    manifest_rel = json.loads((api_rel / "index.json").read_text())
    assert manifest_rel["site_url"] is None
    assert manifest_rel["links"]["records"] == "records.json"
    assert manifest_rel["packages"][0]["suites"][0]["url"] == "signal/consistency.json"
