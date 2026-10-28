#!/usr/bin/env python3
"""Convert a Ripple CW comparison JSON file into a public benchmark record."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from gwmock_benchmark.harness import make_record, write_record


def _cpu_model() -> str:
    """Return the host CPU model, with a portable fallback."""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        # /proc/cpuinfo is Linux-specific; use the portable fallback below.
        pass
    return platform.processor() or platform.machine()


def _benchmark_version() -> str:
    """Return the installed package version or a source-tree tag."""
    try:
        return version("gwmock-benchmark")
    except PackageNotFoundError:
        root = Path(__file__).resolve().parents[1]
        try:
            return subprocess.run(  # noqa: S603
                ["git", "-C", str(root), "describe", "--tags", "--always"],  # noqa: S607
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return "unknown"


def _benchmark_commit() -> str:
    """Return the source revision containing this runner, if available."""
    root = Path(__file__).resolve().parents[1]
    try:
        return subprocess.run(  # noqa: S603
            ["git", "-C", str(root), "rev-parse", "HEAD"],  # noqa: S607
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build_record(raw: dict, label: str) -> dict:
    """Build a metrics-only record from the benchmark's raw JSON output."""
    metric, timing, rates, scope = (
        raw["metric"],
        raw["timing"],
        raw["throughput"],
        raw["timing_scope"],
    )
    gpu_models = scope.get("gpu_models", [])
    package_version = scope["ripple_package_version"]
    libraries = {
        "ripplegw": package_version,
        "jax": scope["jax_version"],
        "lalsuite": scope["lalsuite_package_version"],
    }
    if scope.get("numpy_package_version"):
        libraries["numpy"] = scope["numpy_package_version"]
    if scope.get("jaxlib_package_version"):
        libraries["jaxlib"] = scope["jaxlib_package_version"]
    provenance = {
        "gwmock_benchmark_version": _benchmark_version(),
        "package": "ripplegw",
        "package_version": package_version,
        "library_versions": libraries,
        "python_version": scope["python"],
        "platform": scope.get("platform", platform.platform()),
        "cpu_model": scope.get("cpu_model") or _cpu_model(),
        "gpu_models": gpu_models,
        "n_cpu_cores": int(scope.get("cpu_cores") or os.cpu_count() or 1),
        "n_gpus": len(gpu_models),
        "contributor": None,
    }
    return make_record(
        package="ripplegw",
        suite="continuous-wave",
        label=label,
        configuration={
            "duration_s": metric["duration_s"],
            "sample_rate_hz": metric["sample_rate_hz"],
            "samples_per_signal": timing["samples_per_signal"],
            "f0_hz": metric["f0_hz"],
            "f1_hz_s": metric["f1_hz_s"],
            "batch_size": timing["batch_size"],
            "warm_repeats_median": timing["repeats_median"],
            "barycenter_site": "H1",
            "psd": "ET-D design",
            "psd_sha256": metric["psd_sha256"],
            "psd_source_revision": "0985f75c664786e21cc4f662d4f12fe181b1a536",
            "ripple_source_commit": scope["ripple_source_commit"],
            "benchmark_runner_commit": _benchmark_commit(),
            "comparison_scope": "source polarizations; ET-D is frequency weighting only",
        },
        metrics={
            "etd_weighted_mismatch": metric["combined"],
            "etd_weighted_plus_mismatch": metric["plus"],
            "etd_weighted_cross_mismatch": metric["cross"],
            "etd_weighted_amplitude_ratio": metric["combined_amplitude_ratio_ripple_over_lal"],
            "etd_weighted_relative_norm_error": metric["combined_relative_norm_error"],
            "white_time_domain_mismatch": metric["white_time_domain_mismatch"],
            "ripple_cold_single_seconds": timing["ripple_jit_cold_single_s"],
            "ripple_cold_vmap_batch_seconds": timing["ripple_jit_vmap_cold_per_signal_s"] * timing["batch_size"],
            "ripple_warm_single_seconds": timing["ripple_jit_warm_single_s"],
            "ripple_warm_single_signals_per_second": rates["ripple_jit_warm_single_signals_per_s"],
            "ripple_warm_loop_seconds_per_signal": timing["ripple_jit_python_loop_batch_per_signal_s"],
            "ripple_warm_loop_signals_per_second": rates["ripple_jit_python_loop_batch_signals_per_s"],
            "ripple_warm_vmap_seconds_per_signal": timing["ripple_jit_vmap_warm_per_signal_s"],
            "ripple_warm_vmap_signals_per_second": rates["ripple_jit_vmap_warm_signals_per_s"],
            "lal_warm_seconds_per_signal": timing["lal_warm_single_s"],
            "lal_warm_signals_per_second": rates["lal_warm_single_signals_per_s"],
            "lal_warm_loop_seconds_per_signal": timing["lal_python_loop_batch_per_signal_s"],
            "lal_warm_loop_signals_per_second": rates["lal_python_loop_batch_signals_per_s"],
        },
        provenance=provenance,
    )


def main() -> None:
    """Convert the raw benchmark JSON into a validated public record."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Raw JSON written by cw_compare.py")
    parser.add_argument("output", type=Path, help="Destination metrics-only record")
    parser.add_argument("--label", required=True, help="Run label, for example cpu or nvidia-a30")
    args = parser.parse_args()
    record = build_record(json.loads(args.input.read_text()), args.label)
    write_record(args.output, record)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
