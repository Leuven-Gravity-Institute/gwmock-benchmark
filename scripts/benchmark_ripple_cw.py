#!/usr/bin/env python3
# Copyright 2026, Isaac C. F. Wong
# SPDX-License-Identifier: BSD-3-Clause (see benchmark_ripple_cw.LICENSE)
"""Reproduce a small ET-D-weighted CW comparison and throughput check.

The accuracy metric is computed on source-frame ``(h_plus, h_cross)`` pairs.
The timing comparison uses LAL's detector-strain simulator and Ripple's
polarization API; the output payloads therefore differ and are labelled in the
presentation.  Timing excludes ephemeris loading; Ripple cold timings include
the first JIT compilation and execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import time
from importlib.metadata import version
from pathlib import Path

import jax
import jax.numpy as jnp
import lal
import lalpulsar
import matplotlib.pyplot as plt
import numpy as np
import ripplegw
from lalpulsar import simulateCW
from ripplegw.waveforms.cw.ephemeris import resolve_ephemeris_path
from ripplegw.waveforms.cw.PulsarSignal import PulsarSignal

jax.config.update("jax_enable_x64", True)

START_GPS = 1_000_000_000
DURATION = 32.0
SAMPLE_RATE = 256.0
F0 = 100.0
F1 = -1.1e-9
ALPHA = 1.3
DELTA = -0.5
PHI0 = 1.1
PSI = 0.37
APLUS = 1.0
ACROSS = 0.64
NANOSECONDS_PER_SECOND = 1_000_000_000
DETECTOR = lal.CachedDetectors[lal.LALDetectorIndexLHODIFF]


def _sync(tree):
    """Wait for every JAX leaf in a result tree to finish executing."""
    return jax.tree.map(
        lambda x: x.block_until_ready() if hasattr(x, "block_until_ready") else x,
        tree,
    )


def _cpu_model():
    """Return the host CPU model, with a portable fallback."""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        # /proc/cpuinfo is Linux-specific; use the portable fallback below.
        pass
    return platform.processor() or platform.machine()


def _gpu_models():
    """Return NVIDIA GPU model names when nvidia-smi is available."""
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _weighted_metrics(reference, candidate, weight):
    """One-sided PSD match maximized over a common complex amplitude."""
    n_samples = reference.shape[-1]
    af = np.fft.rfft(reference, axis=-1)
    bf = np.fft.rfft(candidate, axis=-1)
    factors = np.full(af.shape[-1], 2.0)
    factors[0] = 1.0
    if n_samples % 2 == 0:
        factors[-1] = 1.0
    weighted = factors / weight
    aa = float(np.sum(np.sum(np.abs(af) ** 2, axis=0) * weighted))
    bb = float(np.sum(np.sum(np.abs(bf) ** 2, axis=0) * weighted))
    ab = np.sum(np.sum(np.conjugate(af) * bf, axis=0) * weighted)
    coeff = ab / aa
    residual_f = bf - coeff * af
    rr = float(np.sum(np.sum(np.abs(residual_f) ** 2, axis=0) * weighted))
    overlap = abs(ab) / math.sqrt(aa * bb)
    # Algebraically equal to 1 - |overlap|, but stable for near-identical data.
    return {
        "mismatch": rr / (bb * (1.0 + overlap)),
        "amplitude_ratio": math.sqrt(bb / aa),
        "overlap": overlap,
    }


def _etd_mismatch(reference, candidate, sample_rate, psd_path):
    """Compute source-polarization mismatch using the ET-D PSD."""
    f = np.fft.rfftfreq(reference.shape[-1], d=1.0 / sample_rate)
    psd_f, psd_y = np.loadtxt(psd_path, unpack=True)
    psd = np.interp(f, psd_f, psd_y, left=np.inf, right=np.inf)
    return _weighted_metrics(reference, candidate, psd)


def _lal_source_polarizations(earth_path, sun_path, n):
    """Generate reference h+ and hx samples with LAL barycentric timing."""
    eph = lalpulsar.InitBarycenter(earth_path, sun_path)
    bi = lalpulsar.BarycenterInput()
    bi.site = DETECTOR
    for k in range(3):
        bi.site.location[k] = DETECTOR.location[k] / lal.C_SI
    bi.alpha, bi.delta, bi.dInv = ALPHA, DELTA, 0.0
    edat = lalpulsar.EarthState()
    emit = lalpulsar.EmissionTime()
    dt = 1.0 / SAMPLE_RATE
    hp = np.empty(n)
    hc = np.empty(n)
    for i in range(n):
        elapsed = i * dt
        sec = START_GPS + int(elapsed)
        ns = round((elapsed - int(elapsed)) * 1e9)
        if ns == NANOSECONDS_PER_SECOND:
            sec, ns = sec + 1, 0
        tgps = lal.LIGOTimeGPS(sec, ns)
        bi.tgps = tgps
        lalpulsar.BarycenterEarth(edat, tgps, eph)
        lalpulsar.Barycenter(emit, bi, edat)
        tau = (tgps.gpsSeconds - START_GPS) + tgps.gpsNanoSeconds * 1e-9 + emit.deltaT
        phase = PHI0 + 2.0 * math.pi * (F0 * tau + 0.5 * F1 * tau**2)
        hp[i] = APLUS * math.cos(phase)
        hc[i] = ACROSS * math.sin(phase)
    return np.stack((hp, hc))


def _make_lal_simulator(earth_path, sun_path, index=0):
    """Build a LAL detector-strain simulator for one benchmark source."""
    phi0 = PHI0 + 0.01 * index

    def waveform(dt):
        """Return phase and amplitude parameters at barycentric time dt."""
        return 2.0 * math.pi * (F0 * dt + 0.5 * F1 * dt**2), APLUS, ACROSS

    return simulateCW.CWSimulator(
        float(START_GPS),
        START_GPS,
        DURATION,
        waveform,
        5.0,
        phi0,
        PSI,
        ALPHA,
        DELTA,
        "H1",
        earth_ephem_file=earth_path,
        sun_ephem_file=sun_path,
    )


def _median_seconds(call, repeats):
    """Measure synchronized calls and return their median wall time."""
    times = []
    for _ in range(repeats):
        before = time.perf_counter()
        result = call()
        if isinstance(result, (tuple, list, dict)):
            _sync(result)
        elif hasattr(result, "block_until_ready"):
            result.block_until_ready()
        times.append(time.perf_counter() - before)
    return statistics.median(times)


def main():  # noqa: PLR0915
    """Run the CW validation and throughput benchmark, then save figures."""
    # This standalone runner keeps orchestration, measurements, and reporting together.
    parser = argparse.ArgumentParser()
    parser.add_argument("--psd", type=Path, required=True, help="ET-D two-column PSD")
    parser.add_argument("--out", type=Path, required=True, help="output directory")
    parser.add_argument("--device", choices=("auto", "cpu", "gpu"), default="auto")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--repeats", type=int, default=7)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    earth_path = resolve_ephemeris_path(os.environ.get("RIPPLE_EARTH_EPHEMERIS", "earth00-40-DE405.dat.gz"))
    sun_path = resolve_ephemeris_path(os.environ.get("RIPPLE_SUN_EPHEMERIS", "sun00-40-DE405.dat.gz"))
    n = int(DURATION * SAMPLE_RATE)
    dt = 1.0 / SAMPLE_RATE
    t = jnp.arange(n, dtype=jnp.float64) * dt
    model = PulsarSignal(earth_path, sun_path, START_GPS, n_spindowns=1, ref_time_ssb=float(START_GPS))
    site = DETECTOR.location
    base = {
        "alpha": ALPHA,
        "delta": DELTA,
        "f0": F0,
        "phi0": PHI0,
        "aplus": APLUS,
        "across": ACROSS,
        "site_x": site[0],
        "site_y": site[1],
        "site_z": site[2],
        "f1": F1,
    }
    params = {k: jnp.asarray(v, dtype=jnp.float64) for k, v in base.items()}

    # Move inputs to the requested backend before starting any timed region.
    device = jax.devices()[0] if args.device == "auto" else jax.devices(args.device)[0]
    with jax.default_device(device):
        t = jax.device_put(t, device)
        params = jax.tree.map(lambda x: jax.device_put(x, device), params)

        def one(p):
            """Generate the source-polarization pair for one parameter set."""
            return model(t, p)

        one_jit = jax.jit(one)
        begin = time.perf_counter()
        single_cold = _sync(one_jit(params))
        cold_single_s = time.perf_counter() - begin
        single_warm_s = _median_seconds(lambda: one_jit(params), args.repeats)

        batch = args.batch_size
        batch_params_np = {k: np.full(batch, float(v), dtype=np.float64) for k, v in base.items()}
        batch_params_np["phi0"] = PHI0 + np.arange(batch) * 0.01
        batch_params = {k: jax.device_put(jnp.asarray(v), device) for k, v in batch_params_np.items()}
        sequential_params = [{k: value[i] for k, value in batch_params.items()} for i in range(batch)]

        def sequential():
            """Generate the benchmark batch through repeated single calls."""
            return [_sync(one_jit(p)) for p in sequential_params]

        sequential_s = _median_seconds(sequential, args.repeats)
        batched = jax.jit(jax.vmap(one))
        begin = time.perf_counter()
        batch_cold_output = _sync(batched(batch_params))
        cold_vmap_s = time.perf_counter() - begin
        vmap_warm_s = _median_seconds(lambda: batched(batch_params), args.repeats)

    # ET-D-weighted source-polarization comparison on the same time grid.
    ref = _lal_source_polarizations(earth_path, sun_path, n)
    got = np.stack((np.asarray(single_cold["p"]), np.asarray(single_cold["c"])))
    combined_metric = _etd_mismatch(ref, got, SAMPLE_RATE, args.psd)
    plus_metric = _etd_mismatch(ref[0:1], got[0:1], SAMPLE_RATE, args.psd)
    cross_metric = _etd_mismatch(ref[1:2], got[1:2], SAMPLE_RATE, args.psd)
    white_weight = np.ones(n // 2 + 1)
    white_metric = _weighted_metrics(ref, got, white_weight)

    # LAL's simulator returns detector-frame strain. Construct its instances
    # before timing; this isolates repeated generation from ephemeris setup.
    lal_one = _make_lal_simulator(earth_path, sun_path)
    begin = time.perf_counter()
    lal_cold_output = lal_one.get_strain(SAMPLE_RATE)[1]
    lal_first_s = time.perf_counter() - begin
    lal_warm_s = _median_seconds(lambda: lal_one.get_strain(SAMPLE_RATE), args.repeats)
    lal_batch = [_make_lal_simulator(earth_path, sun_path, i) for i in range(args.batch_size)]
    lal_loop_s = _median_seconds(lambda: [sim.get_strain(SAMPLE_RATE) for sim in lal_batch], args.repeats)

    timings = {
        "duration_s": DURATION,
        "sample_rate_hz": SAMPLE_RATE,
        "samples_per_signal": n,
        "batch_size": args.batch_size,
        "repeats_median": args.repeats,
        "lal_first_generation_s": lal_first_s,
        "lal_warm_single_s": lal_warm_s,
        "lal_python_loop_batch_per_signal_s": lal_loop_s / args.batch_size,
        "ripple_jit_cold_single_s": cold_single_s,
        "ripple_jit_warm_single_s": single_warm_s,
        "ripple_jit_python_loop_batch_per_signal_s": sequential_s / args.batch_size,
        "ripple_jit_vmap_cold_per_signal_s": cold_vmap_s / args.batch_size,
        "ripple_jit_vmap_warm_per_signal_s": vmap_warm_s / args.batch_size,
    }
    throughput = {
        "lal_warm_single_signals_per_s": 1.0 / lal_warm_s,
        "lal_python_loop_batch_signals_per_s": args.batch_size / lal_loop_s,
        "ripple_jit_warm_single_signals_per_s": 1.0 / single_warm_s,
        "ripple_jit_python_loop_batch_signals_per_s": args.batch_size / sequential_s,
        "ripple_jit_vmap_warm_signals_per_s": args.batch_size / vmap_warm_s,
    }
    gpu_models = []
    if getattr(device, "platform", "") in ("cuda", "gpu"):
        gpu_models = _gpu_models()
        if not gpu_models:
            gpu_models = [getattr(device, "device_kind", str(device))]

    ripple_root = Path(ripplegw.__file__).resolve().parents[2]
    ripple_commit = os.environ.get("RIPPLE_SOURCE_COMMIT")
    if ripple_commit is None:
        try:
            ripple_commit = subprocess.run(  # noqa: S603
                ["git", "-C", str(ripple_root), "rev-parse", "HEAD"],  # noqa: S607
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except subprocess.CalledProcessError:
            ripple_commit = "unknown"
    result = {
        "metric": {
            "name": "ET-D PSD-weighted source-polarization mismatch",
            "definition": "1 - |(hLAL|hripple)| / sqrt((hLAL|hLAL)(hripple|hripple)); both h+ and hx are stacked; one-sided rFFT weighted by the one-sided PSD with standard DC/Nyquist factors; rectangular 32 s segment; linear PSD interpolation",
            "combined": combined_metric["mismatch"],
            "plus": plus_metric["mismatch"],
            "cross": cross_metric["mismatch"],
            "combined_amplitude_ratio_ripple_over_lal": combined_metric["amplitude_ratio"],
            "combined_relative_norm_error": abs(combined_metric["amplitude_ratio"] - 1.0),
            "white_time_domain_mismatch": white_metric["mismatch"],
            "f0_hz": F0,
            "f1_hz_s": F1,
            "duration_s": DURATION,
            "sample_rate_hz": SAMPLE_RATE,
            "psd_file": args.psd.name,
            "psd_sha256": hashlib.sha256(args.psd.read_bytes()).hexdigest(),
        },
        "timing": timings,
        "throughput": throughput,
        "timing_scope": {
            "lal": "CWSimulator detector-strain generation; warm timing excludes simulator construction and ephemeris loading",
            "ripple": "JIT-compiled source-polarization generation; cold includes first compilation and execution; warm includes execution only",
            "outputs": "LAL returns one projected detector strain; Ripple returns h+ and hx",
            "backend": str(device),
            "device_model": getattr(device, "device_kind", str(device)),
            "jax_version": jax.__version__,
            "jaxlib_package_version": version("jaxlib"),
            "ripple_package_version": os.environ.get("RIPPLE_PACKAGE_VERSION", version("rippleGW")),
            "ripple_source_commit": ripple_commit,
            "lalsuite_package_version": version("lalsuite"),
            "numpy_package_version": version("numpy"),
            "python": platform.python_version(),
            "processor": platform.processor() or platform.machine(),
            "platform": platform.platform(),
            "cpu_model": _cpu_model(),
            "cpu_cores": int(os.environ.get("SLURM_CPUS_PER_TASK", os.cpu_count() or 1)),
            "gpu_models": gpu_models,
        },
        "ephemerides": {"earth": Path(earth_path).name, "sun": Path(sun_path).name},
    }
    (args.out / "cw-results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")

    fig, ax = plt.subplots(figsize=(10, 4.8), layout="constrained")
    names = ["plus", "cross", "combined"]
    vals = [plus_metric["mismatch"], cross_metric["mismatch"], combined_metric["mismatch"]]
    x = np.arange(len(names))
    ax.scatter(x, vals, s=90, c=["#0072B2", "#E69F00", "#009E73"], zorder=3)
    ax.set_xticks(x, names)
    ax.set_yscale("log")
    ax.set_ylim(max(min(vals) * 0.2, np.finfo(float).tiny), max(vals) * 5.0)
    ax.set_ylabel("ET-D weighted mismatch")
    ax.set_title("LAL reference vs Ripple source polarizations")
    ax.grid(axis="y", which="both", alpha=0.25)
    for xpos, val in zip(x, vals, strict=True):
        ax.annotate(f"{val:.2e}", (xpos, val), xytext=(0, 5), textcoords="offset points", ha="center", fontsize=9)
    ax.text(
        0.01,
        -0.2,
        "32 s · 256 Hz · f₀ = 100 Hz · ET-D PSD · source polarizations",
        transform=ax.transAxes,
        fontsize=9,
        color="#4b5563",
    )
    fig.savefig(args.out / "cw-etd-mismatch.png", dpi=180, facecolor="white")
    plt.close(fig)

    labels = [
        "LAL warm\nsingle",
        "LAL loop\n(batch / signal)",
        "Ripple warm\nsingle",
        "Ripple loop\n(batch / signal)",
        "Ripple vmap\n(batch / signal)",
    ]
    values = [
        lal_warm_s,
        lal_loop_s / args.batch_size,
        single_warm_s,
        sequential_s / args.batch_size,
        vmap_warm_s / args.batch_size,
    ]
    fig, ax = plt.subplots(figsize=(11, 4.8), layout="constrained")
    colors = ["#666666", "#666666", "#0072B2", "#0072B2", "#009E73"]
    rates = 1.0 / np.asarray(values)
    bars = ax.bar(labels, rates, color=colors, hatch=["///", "\\\\", "///", "\\\\", ""])
    ax.set_ylabel("Signals per second")
    ax.set_ylim(0, max(rates) * 1.18)
    ax.set_title(f"Warm waveform throughput · batch size {args.batch_size}")
    ax.grid(axis="y", which="both", alpha=0.25)
    for bar, rate in zip(bars, rates, strict=True):
        ax.annotate(
            f"{rate:.3g}",
            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 5),
            textcoords="offset points",
            ha="center",
            fontsize=9,
        )
    ax.text(
        0.01,
        -0.23,
        "LAL: detector strain; Ripple: h+, hx. Warm timings exclude setup; ≠ identical output payload.",
        transform=ax.transAxes,
        fontsize=8.5,
        color="#4b5563",
    )
    fig.savefig(args.out / "cw-throughput.png", dpi=180, facecolor="white")
    plt.close(fig)

    cold_labels = ["LAL first\nget_strain", "Ripple first\nJIT single", "Ripple first\nJIT vmap batch"]
    cold_values = [lal_first_s, cold_single_s, cold_vmap_s]
    fig, ax = plt.subplots(figsize=(9, 4.5), layout="constrained")
    cold_ms = np.array(cold_values) * 1e3
    cold_x = np.arange(len(cold_labels))
    ax.scatter(cold_x, cold_ms, s=95, c=["#666666", "#D55E00", "#CC79A7"], zorder=3)
    ax.set_xticks(cold_x, cold_labels)
    ax.set_ylabel("First-call latency (ms; log scale)")
    ax.set_yscale("log")
    ax.set_ylim(0.1, max(300, float(np.max(cold_ms)) * 1.2))
    ax.set_title("First call: LAL generation vs Ripple compilation + generation")
    ax.grid(axis="y", which="both", alpha=0.25)
    for xpos, value in zip(cold_x, cold_ms, strict=True):
        ax.annotate(f"{value:.3g}", (xpos, value), xytext=(0, 5), textcoords="offset points", ha="center", fontsize=9)
    ax.text(
        0.01,
        -0.2,
        f"LAL object prebuilt; vmapped bar is one batch of {args.batch_size}; JAX bars include compile.",
        transform=ax.transAxes,
        fontsize=8.5,
        color="#4b5563",
    )
    fig.savefig(args.out / "cw-cold-start.png", dpi=180, facecolor="white")
    plt.close(fig)

    print(json.dumps(result, indent=2))
    print(f"LAL first generated array size: {np.asarray(lal_cold_output).shape}")
    print(f"Ripple batch output shape: {np.asarray(batch_cold_output['p']).shape}")


if __name__ == "__main__":
    main()
