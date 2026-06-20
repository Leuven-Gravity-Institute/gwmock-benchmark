"""Contribution validation: checks that go beyond structure to internal consistency.

:func:`gwmock_benchmark.harness.validate_record` proves a record is *well-formed*.
The checks here prove it is *internally consistent*: provenance is complete, and
(via each suite's own ``check_contribution``) every derived metric still agrees with
the primitives it was computed from. Hand-editing a single number — a throughput, a
core-hour total — breaks those relations, so naive tampering and accidental errors
fail. It cannot detect a fully self-consistent fabricated record; nothing cheap can,
because the run happens on hardware the project does not control.
"""

from __future__ import annotations

import math
import re

# GitHub handle: 1-39 chars, alphanumeric or single hyphens, no leading/trailing/double hyphen.
_GITHUB_HANDLE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")


def close(measured: float, expected: float, *, rel_tol: float = 1e-3, abs_tol: float = 1e-9) -> bool:
    """Return whether a measured value matches an expected one within tolerance.

    Derived metrics are stored at full float precision straight from their defining
    formula, so they should match to far better than ``rel_tol``; the loose tolerance
    only guards against trivial rounding, not genuine disagreement.
    """
    return math.isclose(float(measured), float(expected), rel_tol=rel_tol, abs_tol=abs_tol)


def check_provenance(record: dict) -> list[str]:
    """Return a list of provenance-completeness problems (empty means OK).

    A contribution must say what produced it: the benchmarked package version, the
    library versions, the CPU allocation, and the platform/Python it ran on.
    """
    problems: list[str] = []
    prov = record.get("provenance")
    if not isinstance(prov, dict):
        return ["provenance is missing or not a mapping"]

    if not prov.get("package_version"):
        problems.append("provenance.package_version is missing")
    if not isinstance(prov.get("library_versions"), dict) or not prov.get("library_versions"):
        problems.append("provenance.library_versions is empty")

    n_cpu = prov.get("n_cpu_cores")
    if not isinstance(n_cpu, int) or isinstance(n_cpu, bool) or n_cpu < 1:
        problems.append(f"provenance.n_cpu_cores must be a positive integer, got {n_cpu!r}")

    n_gpu = prov.get("n_gpus")
    if not isinstance(n_gpu, int) or isinstance(n_gpu, bool) or n_gpu < 0:
        problems.append(f"provenance.n_gpus must be a non-negative integer, got {n_gpu!r}")

    if not prov.get("platform"):
        problems.append("provenance.platform is missing")
    if not prov.get("python_version"):
        problems.append("provenance.python_version is missing")

    # Optional: a contributor handle, if present, must be a plausible GitHub username
    # (it is published verbatim and rendered as a profile link).
    contributor = prov.get("contributor")
    if contributor is not None and not _GITHUB_HANDLE.match(str(contributor).lstrip("@")):
        problems.append(f"provenance.contributor {contributor!r} is not a valid GitHub handle")
    return problems
