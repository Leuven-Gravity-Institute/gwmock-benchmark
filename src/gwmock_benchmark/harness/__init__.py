"""Generic benchmark harness: provenance, resource measurement, and the record schema.

Shared by every package suite. This subpackage has no required third-party
dependencies and imports cleanly without any optional package installed.
"""

from __future__ import annotations

from gwmock_benchmark.harness.measure import ResourceUsage, measure
from gwmock_benchmark.harness.provenance import allocated_cpu_cores, provenance
from gwmock_benchmark.harness.record import (
    MAX_RECORD_BYTES,
    SCHEMA_VERSION,
    load_records,
    make_record,
    validate_record,
    write_record,
)

__all__ = [
    "MAX_RECORD_BYTES",
    "SCHEMA_VERSION",
    "ResourceUsage",
    "allocated_cpu_cores",
    "load_records",
    "make_record",
    "measure",
    "provenance",
    "validate_record",
    "write_record",
]
