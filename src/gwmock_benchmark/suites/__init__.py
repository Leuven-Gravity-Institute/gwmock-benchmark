"""Per-package benchmark suites.

Each suite defines the workloads for one gwmock package and returns harness records.
Suites are import-safe: their package-specific dependencies are imported lazily, so
this subpackage imports without any benchmarked package installed.
"""

from __future__ import annotations
