"""Resource measurement around a benchmark workload.

Wall time, peak/average resident memory, and (when present) peak GPU memory. JAX is
imported lazily so this module stays importable without the optional GPU stack.
"""

from __future__ import annotations

import platform
import resource
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path


def _peak_rss_bytes() -> int:
    """Return peak resident set size in bytes (ru_maxrss is KiB on Linux, bytes on macOS)."""
    maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return maxrss * 1024 if platform.system() == "Linux" else maxrss


def _current_rss_bytes() -> int:
    """Return the current resident set size in bytes (Linux ``/proc/self/statm``)."""
    try:
        resident_pages = int(Path("/proc/self/statm").read_text().split()[1])
    except (OSError, IndexError, ValueError):
        return 0
    return resident_pages * resource.getpagesize()


def _gpu_peak_bytes() -> int | None:
    """Return peak GPU bytes-in-use from JAX, or ``None`` if unavailable (e.g. on CPU)."""
    try:
        import jax  # noqa: PLC0415 - optional; only present with a GPU stack installed

        stats = jax.devices()[0].memory_stats()
    except Exception:
        return None
    if not stats:
        return None
    return stats.get("peak_bytes_in_use")


@dataclass
class ResourceUsage:
    """Wall time and memory measured around a workload."""

    wall_seconds: float = 0.0
    peak_rss_bytes: int = 0
    average_rss_bytes: float = 0.0
    gpu_peak_bytes: int | None = None
    output_bytes: int = field(default=0)


@contextmanager
def measure(sample_interval_seconds: float = 0.1) -> Iterator[ResourceUsage]:
    """Measure wall time and resident memory around a ``with`` block.

    Average memory is sampled in a background thread; peak memory comes from
    ``getrusage`` and (if a GPU is present) JAX. The yielded :class:`ResourceUsage`
    is filled in on exit; the caller may set ``output_bytes`` inside the block.
    """
    usage = ResourceUsage()
    samples: list[int] = [_current_rss_bytes()]
    stop = threading.Event()

    def _sample() -> None:
        while not stop.wait(sample_interval_seconds):
            samples.append(_current_rss_bytes())

    sampler = threading.Thread(target=_sample, daemon=True)
    sampler.start()
    start = time.perf_counter()
    try:
        yield usage
    finally:
        usage.wall_seconds = time.perf_counter() - start
        stop.set()
        sampler.join()
        usage.peak_rss_bytes = _peak_rss_bytes()
        usage.average_rss_bytes = sum(samples) / len(samples)
        usage.gpu_peak_bytes = _gpu_peak_bytes()
