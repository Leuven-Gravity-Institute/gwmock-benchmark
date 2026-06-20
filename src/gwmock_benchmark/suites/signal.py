# ruff: noqa: PLC0415 - package-specific deps are imported lazily for import-safety
"""gwmock-signal benchmark suite.

Two workloads:

- **performance** — generate a CBC catalogue data product for one
  backend/method/hardware cell, timing a *cold* (incl. JIT/XLA compile) and a *warm*
  (steady-state) run, plus memory and output size.
- **consistency** — the frequency-domain overlap (no time/phase maximization)
  between the ripple (JAX) backend and the LAL baseline, per approximant.

Import-safe: ``numpy``, ``gwpy``, and ``gwmock_signal`` are imported lazily, so this
module imports without the ``[signal]`` extra installed.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from gwmock_benchmark.harness import close, make_record, measure, provenance

PACKAGE = "gwmock-signal"
_LIBRARIES = ("ripplegw", "jax", "jaxlib", "lalsuite", "pycbc", "numpy", "gwpy")
_BYTES_PER_SAMPLE = 8  # float64 strain
_DEFAULT_START = 1_126_259_462.0
_DEFAULT_DETECTORS = ("H1", "L1", "V1")

_INTRINSIC_KEYS = (
    "detector_frame_mass_1",
    "detector_frame_mass_2",
    "luminosity_distance",
    "spin_1z",
    "spin_2z",
    "inclination",
    "coa_phase",
)

# --- consistency: approximant families and per-family parameter sets ----------
# TaylorF2 is omitted: LAL provides no time-domain TaylorF2.
_ALIGNED = ("IMRPhenomD", "IMRPhenomHM", "IMRPhenomXAS", "IMRPhenomXHM")
_TIDAL = ("IMRPhenomD_NRTidalv2", "IMRPhenomXAS_NRTidalv3")
_PRECESSING = ("IMRPhenomPv2", "IMRPhenomXP", "IMRPhenomXPHM")

_ALIGNED_CONFIGS = [
    {"detector_frame_mass_1": 40.0, "detector_frame_mass_2": 31.0, "spin_1z": 0.5, "spin_2z": -0.2, "inclination": 0.9},
    {"detector_frame_mass_1": 36.0, "detector_frame_mass_2": 29.0, "spin_1z": 0.0, "spin_2z": 0.0, "inclination": 0.4},
    {"detector_frame_mass_1": 60.0, "detector_frame_mass_2": 55.0, "spin_1z": -0.3, "spin_2z": 0.2, "inclination": 1.2},
]
_TIDAL_CONFIGS = [
    {
        "detector_frame_mass_1": 1.6,
        "detector_frame_mass_2": 1.4,
        "spin_1z": 0.02,
        "spin_2z": -0.01,
        "inclination": 0.6,
        "lambda_1": 400.0,
        "lambda_2": 500.0,
    },
    {
        "detector_frame_mass_1": 2.0,
        "detector_frame_mass_2": 1.5,
        "spin_1z": 0.0,
        "spin_2z": 0.0,
        "inclination": 0.3,
        "lambda_1": 300.0,
        "lambda_2": 600.0,
    },
]
_PRECESSING_CONFIGS = [
    {
        "detector_frame_mass_1": 40.0,
        "detector_frame_mass_2": 30.0,
        "spin_1x": 0.3,
        "spin_1y": 0.1,
        "spin_1z": 0.2,
        "spin_2x": -0.1,
        "spin_2y": 0.2,
        "spin_2z": 0.1,
        "inclination": 0.6,
    },
    {
        "detector_frame_mass_1": 50.0,
        "detector_frame_mass_2": 35.0,
        "spin_1x": -0.2,
        "spin_1y": 0.3,
        "spin_1z": 0.1,
        "spin_2x": 0.2,
        "spin_2y": -0.1,
        "spin_2z": 0.0,
        "inclination": 1.0,
    },
]
_FAMILIES: dict[str, list[dict]] = {
    approximant: configs
    for names, configs in (
        (_ALIGNED, _ALIGNED_CONFIGS),
        (_TIDAL, _TIDAL_CONFIGS),
        (_PRECESSING, _PRECESSING_CONFIGS),
    )
    for approximant in names
}


def build_catalogue(n_events: int, *, seed: int = 0, gps_start: float = _DEFAULT_START, span: float = 8192.0) -> dict:
    """Return a synthetic struct-of-arrays catalogue of ``n_events`` aligned-spin BBHs."""
    import numpy as np

    rng = np.random.default_rng(seed)
    return {
        "detector_frame_mass_1": rng.uniform(25.0, 50.0, n_events),
        "detector_frame_mass_2": rng.uniform(20.0, 45.0, n_events),
        "luminosity_distance": rng.uniform(200.0, 1500.0, n_events),
        "spin_1z": rng.uniform(-0.5, 0.5, n_events),
        "spin_2z": rng.uniform(-0.5, 0.5, n_events),
        "inclination": rng.uniform(0.0, np.pi, n_events),
        "coa_phase": rng.uniform(0.0, 2.0 * np.pi, n_events),
        "right_ascension": rng.uniform(0.0, 2.0 * np.pi, n_events),
        "declination": rng.uniform(-0.5 * np.pi, 0.5 * np.pi, n_events),
        "polarization_angle": rng.uniform(0.0, np.pi, n_events),
        "coa_time": gps_start + rng.uniform(0.0, span, n_events),
    }


def _waveform_backend(name: str):
    """Return a fresh waveform backend for ``name`` ('lal', 'pycbc', or 'ripple')."""
    from gwmock_signal.waveform.backends import LALSimulationBackend, PyCBCBackend, RippleBackend

    return {"lal": LALSimulationBackend, "pycbc": PyCBCBackend, "ripple": RippleBackend}[name]()


def _segment_start_times(start_time: float, end_time: float, segment_duration: float):
    """Return contiguous segment start times tiling ``[start_time, end_time)``."""
    import numpy as np

    n_segments = int(np.ceil((end_time - start_time) / segment_duration))
    return start_time + np.arange(n_segments) * segment_duration


def _per_event_catalogue(backend, approximant, detector_names, catalogue, *, run):
    """Build the segmented data product one event at a time (the per-event CPU path)."""
    import numpy as np
    from gwmock_signal.injection import inject_strains_sequential
    from gwmock_signal.multichannel.stack import DetectorStrainStack
    from gwmock_signal.projection.network import project_polarizations_to_network
    from gwpy.timeseries import TimeSeries

    sampling_frequency = run["sampling_frequency"]
    segment_duration = run["segment_duration"]
    starts = _segment_start_times(run["start_time"], run["end_time"], segment_duration)
    n_segment_samples = round(segment_duration * sampling_frequency)
    n_events = len(catalogue["coa_time"])

    channels = [
        {
            name: TimeSeries(np.zeros(n_segment_samples), t0=float(start), sample_rate=sampling_frequency)
            for name in detector_names
        }
        for start in starts
    ]
    for i in range(n_events):
        polarizations = backend.generate_td_waveform(
            approximant,
            tc=float(catalogue["coa_time"][i]),
            sampling_frequency=sampling_frequency,
            minimum_frequency=run["minimum_frequency"],
            **{key: float(catalogue[key][i]) for key in _INTRINSIC_KEYS},
        )
        projected = project_polarizations_to_network(
            {"plus": polarizations["plus"], "cross": polarizations["cross"]},
            detector_names,
            right_ascension=float(catalogue["right_ascension"][i]),
            declination=float(catalogue["declination"][i]),
            polarization_angle=float(catalogue["polarization_angle"][i]),
            earth_rotation=False,
        )
        for name in detector_names:
            signal = projected[name]
            signal_start, signal_end = signal.t0.value, signal.t0.value + signal.duration.value
            for k, start in enumerate(starts):
                if signal_start < start + segment_duration and signal_end > start:
                    channels[k][name] = inject_strains_sequential(channels[k][name], [signal])
    return [DetectorStrainStack.from_mapping(detector_names, channel) for channel in channels]


def _batched_catalogue(approximant, detector_names, catalogue, *, run, chunk_size, n_chirp_mass_bins):  # noqa: PLR0913
    """Build the segmented data product with the on-device batched path."""
    from gwmock_signal.jax_batch import simulate_cbc_catalogue

    return simulate_cbc_catalogue(
        approximant,
        detector_names,
        parameters=catalogue,
        chunk_size=chunk_size,
        n_chirp_mass_bins=n_chirp_mass_bins,
        **run,
    )


def _output_bytes(segments, *, write_dir: Path | None) -> int:
    """Return the data-product size: on-disk bytes if ``write_dir`` is set, else in-memory."""
    if write_dir is None:
        return sum(stack.data.size * _BYTES_PER_SAMPLE for stack in segments)
    total = 0
    for index, stack in enumerate(segments):
        path = write_dir / f"segment_{index:06d}.hdf5"
        stack.write(path, format="hdf5")
        total += path.stat().st_size
    return total


def run_performance(  # noqa: PLR0913
    *,
    backend: str,
    method: str,
    approximant: str = "IMRPhenomD",
    detectors: tuple[str, ...] = _DEFAULT_DETECTORS,
    n_events: int = 200,
    sampling_frequency: float = 4096.0,
    minimum_frequency: float = 20.0,
    segment_duration: float = 64.0,
    start_time: float = _DEFAULT_START,
    end_time: float = _DEFAULT_START + 8192.0,
    chunk_size: int | None = None,
    n_chirp_mass_bins: int = 1,
    n_cpu_cores: int | None = None,
    n_gpus: int | None = None,
    label: str | None = None,
    write_data: bool = False,
    max_product_gb: float = 8.0,
) -> dict:
    """Run one performance cell (cold + warm) and return its benchmark record.

    Raises:
        ValueError: if ``method='batched'`` with a non-ripple backend, or if the
            in-memory data product would exceed ``max_product_gb``.
    """
    import numpy as np

    if method == "batched" and backend != "ripple":
        raise ValueError("the batched method is only available for the ripple backend")

    detectors = tuple(detectors)
    # The span is tiled with fixed-duration segments and the whole product is held in
    # memory; refuse absurd spans up front instead of OOMing the node mid-run.
    n_segments = int(np.ceil((end_time - start_time) / segment_duration))
    n_segment_samples = round(segment_duration * sampling_frequency)
    product_gb = n_segments * len(detectors) * n_segment_samples * _BYTES_PER_SAMPLE / 1e9
    if product_gb > max_product_gb:
        raise ValueError(
            f"data product is ~{product_gb:.1f} GB ({n_segments} segments x {len(detectors)} detectors), "
            f"over max_product_gb={max_product_gb}. Shorten the span (end_time) or raise the cap."
        )

    catalogue = build_catalogue(n_events, gps_start=start_time)
    catalogue["coa_time"] = np.clip(catalogue["coa_time"], start_time, end_time)
    run = {
        "sampling_frequency": sampling_frequency,
        "minimum_frequency": minimum_frequency,
        "segment_duration": segment_duration,
        "start_time": start_time,
        "end_time": end_time,
    }

    def workload():
        if method == "batched":
            return _batched_catalogue(
                approximant,
                list(detectors),
                catalogue,
                run=run,
                chunk_size=chunk_size,
                n_chirp_mass_bins=n_chirp_mass_bins,
            )
        return _per_event_catalogue(_waveform_backend(backend), approximant, list(detectors), catalogue, run=run)

    def run_once(write_dir):
        with measure() as usage:
            segments = workload()
            usage.output_bytes = _output_bytes(segments, write_dir=write_dir)
        return usage

    with tempfile.TemporaryDirectory() as tmp:
        write_dir = Path(tmp) if write_data else None
        # Cold pays one-time JIT/XLA compile; warm is the steady state that a
        # catalogue-scale run amortizes to. Record both.
        cold = run_once(write_dir)
        warm = run_once(write_dir)

    prov = provenance(package=PACKAGE, libraries=_LIBRARIES, n_cpu_cores=n_cpu_cores, n_gpus=n_gpus)

    def _per_second(wall: float) -> float | None:
        return n_events / wall if wall else None

    def _core_hours(wall: float, units: int) -> float:
        return wall / 3600.0 * units

    metrics = {
        "wall_seconds_cold": cold.wall_seconds,
        "wall_seconds_warm": warm.wall_seconds,
        "compile_seconds": max(cold.wall_seconds - warm.wall_seconds, 0.0),
        "events_per_second_cold": _per_second(cold.wall_seconds),
        "events_per_second_warm": _per_second(warm.wall_seconds),
        "cpu_core_hours_cold": _core_hours(cold.wall_seconds, prov["n_cpu_cores"]),
        "cpu_core_hours_warm": _core_hours(warm.wall_seconds, prov["n_cpu_cores"]),
        "gpu_hours_cold": _core_hours(cold.wall_seconds, prov["n_gpus"]),
        "gpu_hours_warm": _core_hours(warm.wall_seconds, prov["n_gpus"]),
        "peak_rss_bytes": max(cold.peak_rss_bytes, warm.peak_rss_bytes),
        "average_rss_bytes": warm.average_rss_bytes,
        "gpu_peak_bytes": max(cold.gpu_peak_bytes or 0, warm.gpu_peak_bytes or 0),
        "output_bytes": cold.output_bytes,
    }
    return make_record(
        package=PACKAGE,
        suite="performance",
        label=label or f"{backend}-{method}",
        configuration={
            "backend": backend,
            "method": method,
            "approximant": approximant,
            "detectors": list(detectors),
            "n_events": n_events,
            "chunk_size": chunk_size,
            "n_chirp_mass_bins": n_chirp_mass_bins,
            **run,
        },
        metrics=metrics,
        provenance=prov,
    )


def _overlap_loss(spectrum_a, spectrum_b, in_band) -> float:
    """Return 1 - overlap of two complex FD series — NO time/phase maximization.

    Uses ``Re(<a,b>)`` (no phase maximization) on a shared frequency grid with a shared
    coalescence reference (no time maximization), so any residual phase or time
    discrepancy lowers the overlap rather than being optimized away. Evaluated via the
    numerically stable identity ``(A·B - C²) / (sqrt(A·B)·(sqrt(A·B) + C))`` so
    near-unity overlaps keep precision. PSD-weighting is flat (white).
    """
    import numpy as np

    a = np.where(in_band, np.asarray(spectrum_a), 0.0)
    b = np.where(in_band, np.asarray(spectrum_b), 0.0)
    aa = float(np.sum(np.abs(a) ** 2))
    bb = float(np.sum(np.abs(b) ** 2))
    ab = float(np.real(np.sum(a * np.conj(b))))
    denom = np.sqrt(aa * bb)
    if denom == 0.0:
        return 1.0
    return max((aa * bb - ab**2) / (denom * (denom + ab)), 0.0)


def _lal_fd_polarizations(approximant: str, params: dict, *, delta_f, f_min, f_max, f_ref):  # noqa: PLR0913
    """Return LAL frequency-domain (hp, hc) arrays on the grid 0..f_max (step delta_f)."""
    import lal
    import lalsimulation
    import numpy as np

    lal_params = lal.CreateDict()
    lalsimulation.SimInspiralWaveformParamsInsertTidalLambda1(lal_params, float(params.get("lambda_1", 0.0)))
    lalsimulation.SimInspiralWaveformParamsInsertTidalLambda2(lal_params, float(params.get("lambda_2", 0.0)))
    hp, hc = lalsimulation.SimInspiralChooseFDWaveform(
        float(params["detector_frame_mass_1"]) * lal.MSUN_SI,
        float(params["detector_frame_mass_2"]) * lal.MSUN_SI,
        float(params.get("spin_1x", 0.0)),
        float(params.get("spin_1y", 0.0)),
        float(params.get("spin_1z", 0.0)),
        float(params.get("spin_2x", 0.0)),
        float(params.get("spin_2y", 0.0)),
        float(params.get("spin_2z", 0.0)),
        float(params["luminosity_distance"]) * lal.PC_SI * 1e6,
        float(params.get("inclination", 0.0)),
        float(params.get("coa_phase", 0.0)),
        0.0,
        0.0,
        0.0,
        delta_f,
        f_min,
        f_max,
        f_ref,
        lal_params,
        lalsimulation.GetApproximantFromString(approximant),
    )
    return np.asarray(hp.data.data), np.asarray(hc.data.data)


def run_consistency(  # noqa: PLR0913 - each measurement knob is an explicit keyword
    *,
    sampling_frequency: float = 2048.0,
    minimum_frequency: float = 20.0,
    tidal_minimum_frequency: float = 40.0,
    distance: float = 400.0,
    n_cpu_cores: int | None = None,
    n_gpus: int | None = None,
) -> list[dict]:
    """Measure the ripple-vs-LAL frequency-domain overlap for every supported approximant.

    Overlap is computed in the FREQUENCY DOMAIN with NO time/phase maximization: both
    backends share the same frequency grid, ``f_ref``, and coalescence reference, so a
    real-part overlap loss (see :func:`_overlap_loss`) exposes any genuine disagreement.
    This mirrors ripple's own LAL cross-validation and avoids the FD->TD conditioning
    differences between the two backends. Returns one record per approximant.
    """
    import numpy as np
    from gwmock_signal.waveform.backends import RippleBackend

    ripple_backend = RippleBackend()

    prov = provenance(package=PACKAGE, libraries=_LIBRARIES, n_cpu_cores=n_cpu_cores, n_gpus=n_gpus)
    records: list[dict] = []
    for approximant, configs in _FAMILIES.items():
        f_min = tidal_minimum_frequency if approximant in _TIDAL else minimum_frequency
        overlaps: list[float] = []
        for config in configs:
            params = {"luminosity_distance": distance, "coa_phase": 0.0, **config}
            fd = ripple_backend.generate_fd_polarizations(
                approximant, sampling_frequency=sampling_frequency, minimum_frequency=f_min, **params
            )
            freqs = np.asarray(fd.frequencies)
            delta_f = float(freqs[1] - freqs[0])
            lal_hp, lal_hc = _lal_fd_polarizations(
                approximant, params, delta_f=delta_f, f_min=f_min, f_max=float(freqs[-1]), f_ref=f_min
            )
            n = min(len(freqs), len(lal_hp))
            in_band = freqs[:n] >= f_min
            in_band[-2:] = False  # LAL zeros a variable number of Nyquist bins; drop the last two for both
            for ripple_pol, lal_pol in ((np.asarray(fd.plus)[:n], lal_hp[:n]), (np.asarray(fd.cross)[:n], lal_hc[:n])):
                overlaps.append(1.0 - _overlap_loss(ripple_pol, lal_pol, in_band))
        records.append(
            make_record(
                package=PACKAGE,
                suite="consistency",
                label=approximant,
                configuration={
                    "minimum_frequency": f_min,
                    "sampling_frequency": sampling_frequency,
                    "distance": distance,
                    "n_overlaps": len(overlaps),
                },
                metrics={"min_overlap": min(overlaps), "median_overlap": float(np.median(overlaps))},
                provenance=prov,
            )
        )
    return records


# --- rendering: figures + table snippets from committed records ----------------


def _device(record: dict) -> str:
    """Return the hardware label for a record: its GPU if a GPU run, else its CPU."""
    prov = record["provenance"]
    gpus = prov.get("gpu_models") or []
    return gpus[0] if prov.get("n_gpus") and gpus else (prov.get("cpu_model") or "unknown")


def _metric(record: dict, key: str) -> float:
    """Return a metric as a float, treating missing/None as 0."""
    return float(record["metrics"].get(key) or 0.0)


def _signal_version(record: dict) -> str:
    """Return the gwmock-signal version this record was produced with."""
    prov = record["provenance"]
    return prov.get("package_version") or (prov.get("library_versions") or {}).get(PACKAGE) or "—"


def _approximant(record: dict) -> str:
    """Return the waveform model a record exercises (consistency labels are the model)."""
    return record["configuration"].get("approximant") or record["label"]


def _short_device(name: str) -> str:
    """Shorten a CPU/GPU model for compact chart x-axis labels."""
    import re

    name = name.replace("(R)", "").replace("(TM)", "")
    name = re.sub(r"\s*\d+-Core Processor", "", name)
    name = re.sub(r"\s*CPU @.*", "", name)
    name = re.sub(r"\bProcessor\b", "", name)
    return re.sub(r"\s+", " ", name).strip()


def _html_table(headers: list[str], rows: list[list]) -> str:
    """Return an HTML table (class ``benchmark-table``) enhanced client-side to sort/filter."""
    import html

    head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body = "\n".join("<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<table class="benchmark-table">\n<thead><tr>{head}</tr></thead>\n<tbody>\n{body}\n</tbody>\n</table>\n'


def _performance_table(records: list[dict]) -> str:
    """Return an HTML table of the performance records (warm is the headline)."""
    headers = [
        "cell",
        "model",
        "device",
        "gwmock-signal",
        "warm ev/s",
        "cold wall (s)",
        "warm wall (s)",
        "compile (s)",
        "peak mem (GB)",
        "output (GB)",
    ]
    rows = [
        [
            record["label"],
            _approximant(record),
            _device(record),
            _signal_version(record),
            f"{_metric(record, 'events_per_second_warm'):.0f}",
            f"{_metric(record, 'wall_seconds_cold'):.0f}",
            f"{_metric(record, 'wall_seconds_warm'):.0f}",
            f"{_metric(record, 'compile_seconds'):.1f}",
            f"{_metric(record, 'peak_rss_bytes') / 1e9:.1f}",
            f"{_metric(record, 'output_bytes') / 1e9:.2f}",
        ]
        for record in records
    ]
    return _html_table(headers, rows)


def _log_overlap_loss(overlap: float) -> float:
    """Return log10(1 - overlap); lower (more negative) is closer to identical."""
    import math

    return math.log10(max(1.0 - overlap, 1e-16))


def _consistency_table(records: list[dict]) -> str:
    """Return an HTML table of ripple-vs-LAL overlap (no maximization) per approximant."""
    headers = ["Approximant", "gwmock-signal", "f_min (Hz)", "worst overlap", "worst log₁₀ loss", "median log₁₀ loss"]
    rows = [
        [
            record["label"],
            _signal_version(record),
            record["configuration"].get("minimum_frequency", ""),
            f"{_metric(record, 'min_overlap'):.6f}",
            f"{_log_overlap_loss(_metric(record, 'min_overlap')):.2f}",
            f"{_log_overlap_loss(_metric(record, 'median_overlap')):.2f}",
        ]
        for record in records
    ]
    return _html_table(headers, rows)


def _performance_chart_rows(records: list[dict]) -> list[dict]:
    """Return chart-ready rows for the performance records (one per cell)."""
    return [
        {
            "approximant": _approximant(record),
            "cell": f"{record['label']} · {_short_device(_device(record))}",
            "label": record["label"],
            "device": _device(record),
            "version": _signal_version(record),
            "throughput_cold": _metric(record, "events_per_second_cold"),
            "throughput_warm": _metric(record, "events_per_second_warm"),
            "wall_cold": _metric(record, "wall_seconds_cold"),
            "wall_warm": _metric(record, "wall_seconds_warm"),
            "compile": _metric(record, "compile_seconds"),
            "peak_gb": _metric(record, "peak_rss_bytes") / 1e9,
            "output_gb": _metric(record, "output_bytes") / 1e9,
        }
        for record in records
    ]


def _consistency_chart_rows(records: list[dict]) -> list[dict]:
    """Return chart-ready rows for the consistency records (one per approximant)."""
    return [
        {
            "approximant": record["label"],
            "label": record["label"],
            "device": _device(record),
            "version": _signal_version(record),
            "worst_overlap": _metric(record, "min_overlap"),
            "worst_log_loss": _log_overlap_loss(_metric(record, "min_overlap")),
            "median_log_loss": _log_overlap_loss(_metric(record, "median_overlap")),
        }
        for record in records
    ]


def _charts_snippet(group: str, suite: str, rows: list[dict]) -> str:
    """Return an HTML snippet: inline JSON data + a container the chart JS renders into."""
    import json

    payload = json.dumps(rows, separators=(",", ":"))
    return (
        f'<script type="application/json" class="benchmark-chart-data" data-group="{group}">{payload}</script>\n'
        f'<div class="benchmark-charts" data-group="{group}" data-suite="{suite}"></div>\n'
    )


def render(records: list[dict], output_dir: Path) -> list[Path]:
    """Render chart + table snippets for the gwmock-signal records under ``output_dir``.

    Writes Markdown snippets to ``output_dir/generated``: per suite, an interactive
    table and an inline-data block that the client-side Vega-Lite charts render from.
    Returns the paths written.
    """
    generated = output_dir / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    performance = sorted((r for r in records if r["suite"] == "performance"), key=lambda r: r["label"])
    consistency = sorted((r for r in records if r["suite"] == "consistency"), key=lambda r: r["label"])

    def _write(name: str, content: str) -> None:
        path = generated / name
        path.write_text(content)
        written.append(path)

    if performance:
        _write(
            "performance-charts.md",
            _charts_snippet("signal-performance", "performance", _performance_chart_rows(performance)),
        )
        _write("performance-table.md", _performance_table(performance))

    if consistency:
        _write(
            "consistency-charts.md",
            _charts_snippet("signal-consistency", "consistency", _consistency_chart_rows(consistency)),
        )
        _write("consistency-table.md", _consistency_table(consistency))

    return written


# --- contribution validation: derived metrics must agree with the primitives -----


def _check_performance(record: dict) -> list[str]:
    """Return performance-record inconsistencies (empty means OK).

    Recomputes throughput, core-hours, the compile gap, and the data-product size
    from the configuration + raw wall times, so a hand-edited metric stops agreeing.
    """
    import math

    config = record["configuration"]
    metrics = record["metrics"]
    prov = record["provenance"]
    problems: list[str] = []

    n_events = config.get("n_events")
    if not isinstance(n_events, int) or n_events <= 0:
        return [f"configuration.n_events must be a positive integer, got {n_events!r}"]
    n_cpu = prov.get("n_cpu_cores") or 0
    n_gpu = prov.get("n_gpus") or 0

    for phase in ("cold", "warm"):
        wall = metrics.get(f"wall_seconds_{phase}")
        if not isinstance(wall, (int, float)) or wall <= 0:
            problems.append(f"metrics.wall_seconds_{phase} must be positive, got {wall!r}")
            continue
        checks = {
            f"events_per_second_{phase}": n_events / wall,
            f"cpu_core_hours_{phase}": wall / 3600.0 * n_cpu,
            f"gpu_hours_{phase}": wall / 3600.0 * n_gpu,
        }
        for key, expected in checks.items():
            value = metrics.get(key)
            if value is not None and not close(value, expected):
                problems.append(f"metrics.{key}={value!r} disagrees with derived {expected:.6g}")

    cold, warm = metrics.get("wall_seconds_cold"), metrics.get("wall_seconds_warm")
    compile_seconds = metrics.get("compile_seconds")
    if all(isinstance(v, (int, float)) for v in (cold, warm, compile_seconds)):
        expected = max(cold - warm, 0.0)
        if not close(compile_seconds, expected, abs_tol=1e-6):
            problems.append(
                f"metrics.compile_seconds={compile_seconds!r} disagrees with max(cold-warm,0)={expected:.6g}"
            )

    # Output size: the raw data product is n_segments x detectors x samples x 8 bytes.
    # The on-disk (HDF5) path adds container overhead, so allow [raw, 2x raw].
    detectors = config.get("detectors") or []
    span = (config.get("end_time", 0.0) - config.get("start_time", 0.0)) or 0.0
    segment_duration = config.get("segment_duration") or 0.0
    sampling_frequency = config.get("sampling_frequency") or 0.0
    output_bytes = metrics.get("output_bytes")
    if span > 0 and segment_duration > 0 and sampling_frequency > 0 and detectors and output_bytes is not None:
        n_segments = math.ceil(span / segment_duration)
        n_segment_samples = round(segment_duration * sampling_frequency)
        raw = n_segments * len(detectors) * n_segment_samples * _BYTES_PER_SAMPLE
        if not (raw * 0.999 <= output_bytes <= raw * 2.0):
            problems.append(
                f"metrics.output_bytes={output_bytes!r} outside [{raw}, {2 * raw}] for the configured product"
            )
    return problems


def _check_consistency(record: dict) -> list[str]:
    """Return consistency-record inconsistencies (empty means OK)."""
    metrics = record["metrics"]
    problems: list[str] = []
    worst, median = metrics.get("min_overlap"), metrics.get("median_overlap")
    for name, value in (("min_overlap", worst), ("median_overlap", median)):
        if not isinstance(value, (int, float)) or not (0.0 < value <= 1.0 + 1e-9):
            problems.append(f"metrics.{name} must be in (0, 1], got {value!r}")
    if isinstance(worst, (int, float)) and isinstance(median, (int, float)) and worst > median + 1e-9:
        problems.append(f"metrics.min_overlap={worst!r} exceeds median_overlap={median!r} (worst cannot beat median)")
    n_overlaps = record["configuration"].get("n_overlaps")
    if not isinstance(n_overlaps, int) or n_overlaps < 1:
        problems.append(f"configuration.n_overlaps must be a positive integer, got {n_overlaps!r}")
    return problems


def check_contribution(record: dict) -> list[str]:
    """Return a list of internal-consistency problems for a gwmock-signal record.

    Dispatches on ``suite``; an empty list means every derived metric agrees with the
    primitives it was computed from. Used by ``gwmock-benchmark validate`` in CI.
    """
    suite = record.get("suite")
    if suite == "performance":
        return _check_performance(record)
    if suite == "consistency":
        return _check_consistency(record)
    return [f"unknown gwmock-signal suite {suite!r}"]


def reproduce_consistency(records: list[dict], *, tolerance: float = 0.5) -> list[str]:
    """Re-run the consistency suite and return committed records that fail to reproduce.

    The ripple-vs-LAL overlap is deterministic and hardware-independent, so re-running
    it against the same (locked) toolchain reproduces a genuine record to machine
    precision. This takes consistency out of the trust model: a fabricated overlap
    cannot survive an independent recomputation. Compared on ``log10(1 - overlap)``
    with an absolute ``tolerance`` that absorbs cross-platform float noise (measured
    reproduction error is ~0) while still catching the orders-of-magnitude gap a
    fabricated value would show. Requires the ``[signal]`` extra. Empty means OK.
    """
    import math

    consistency = [record for record in records if record.get("suite") == "consistency"]
    if not consistency:
        return []

    sampling = {r["configuration"].get("sampling_frequency") for r in consistency}
    distance = {r["configuration"].get("distance") for r in consistency}
    if len(sampling) != 1 or len(distance) != 1:
        return [f"consistency records mix sampling_frequency/distance ({sampling}, {distance}); verify separately"]
    minimum_frequency = next(
        (r["configuration"]["minimum_frequency"] for r in consistency if r["label"] not in _TIDAL), 20.0
    )
    tidal_minimum_frequency = next(
        (r["configuration"]["minimum_frequency"] for r in consistency if r["label"] in _TIDAL), 40.0
    )

    fresh = {
        record["label"]: record
        for record in run_consistency(
            sampling_frequency=sampling.pop(),
            minimum_frequency=minimum_frequency,
            tidal_minimum_frequency=tidal_minimum_frequency,
            distance=distance.pop(),
        )
    }

    def log_loss(overlap: float) -> float:
        return math.log10(max(1.0 - overlap, 1e-16))

    problems: list[str] = []
    for record in consistency:
        label = record["label"]
        if label not in fresh:
            problems.append(f"{label}: not produced by the re-run (unknown approximant?)")
            continue
        for key in ("min_overlap", "median_overlap"):
            stored, recomputed = record["metrics"].get(key), fresh[label]["metrics"].get(key)
            if stored is None or recomputed is None:
                problems.append(f"{label}: missing {key}")
                continue
            delta = abs(log_loss(stored) - log_loss(recomputed))
            if delta > tolerance:
                problems.append(
                    f"{label}: {key} stored loss {log_loss(stored):.3f} but reproduced "
                    f"{log_loss(recomputed):.3f} (Δ={delta:.3f} > {tolerance})"
                )
    return problems
