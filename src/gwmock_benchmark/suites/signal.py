# ruff: noqa: PLC0415 - package-specific deps are imported lazily for import-safety
"""gwmock-signal benchmark suite.

Two workloads:

- **performance** — generate a CBC catalogue data product for one
  backend/method/hardware cell, timing a *cold* (incl. JIT/XLA compile) and a *warm*
  (steady-state) run, plus memory and output size.
- **consistency** — the white, time/phase-maximized match between the ripple (JAX)
  backend and the LAL baseline, per approximant.

Import-safe: ``numpy``, ``gwpy``, and ``gwmock_signal`` are imported lazily, so this
module imports without the ``[signal]`` extra installed.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from gwmock_benchmark.harness import grouped_bar, make_record, measure, provenance, single_bar

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


def _white_match(series_a, series_b, sampling_frequency: float, minimum_frequency: float) -> float:
    """White, time/phase-maximized match between two real time series."""
    import numpy as np

    n = 1 << (int(np.ceil(np.log2(max(len(series_a), len(series_b))))) + 1)
    spectrum_a = np.fft.rfft(series_a, n=n)
    spectrum_b = np.fft.rfft(series_b, n=n)
    in_band = np.fft.rfftfreq(n, d=1.0 / sampling_frequency) >= minimum_frequency
    spectrum_a = np.where(in_band, spectrum_a, 0.0)
    spectrum_b = np.where(in_band, spectrum_b, 0.0)
    cross = spectrum_a * np.conj(spectrum_b)
    full = np.zeros(n, dtype=complex)
    full[: len(cross)] = cross
    correlation = np.fft.ifft(full) * n
    norm = np.sqrt(np.sum(np.abs(spectrum_a) ** 2) * np.sum(np.abs(spectrum_b) ** 2))
    return float(np.max(np.abs(correlation)) / norm)


def run_consistency(  # noqa: PLR0913 - each measurement knob is an explicit keyword
    *,
    sampling_frequency: float = 2048.0,
    minimum_frequency: float = 20.0,
    tidal_minimum_frequency: float = 40.0,
    distance: float = 400.0,
    n_cpu_cores: int | None = None,
    n_gpus: int | None = None,
) -> list[dict]:
    """Run the ripple-vs-LAL match for every supported approximant.

    Returns one record per approximant (``suite='consistency'``, ``label`` is the
    approximant), so contributed results stay one-data-point-per-file.
    """
    import numpy as np
    from gwmock_signal.waveform.backends import LALSimulationBackend, RippleBackend

    ripple_backend = RippleBackend()
    lal_backend = LALSimulationBackend()
    tc = 1_126_259_462.4

    prov = provenance(package=PACKAGE, libraries=_LIBRARIES, n_cpu_cores=n_cpu_cores, n_gpus=n_gpus)
    records: list[dict] = []
    for approximant, configs in _FAMILIES.items():
        f_min = tidal_minimum_frequency if approximant in _TIDAL else minimum_frequency
        matches: list[float] = []
        for config in configs:
            common = {
                "tc": tc,
                "sampling_frequency": sampling_frequency,
                "minimum_frequency": f_min,
                "luminosity_distance": distance,
                **config,
            }
            ripple = ripple_backend.generate_td_waveform(approximant, **common)
            lal = lal_backend.generate_td_waveform(approximant, **common)
            for polarization in ("plus", "cross"):
                matches.append(
                    _white_match(ripple[polarization].value, lal[polarization].value, sampling_frequency, f_min)
                )
        records.append(
            make_record(
                package=PACKAGE,
                suite="consistency",
                label=approximant,
                configuration={
                    "minimum_frequency": f_min,
                    "sampling_frequency": sampling_frequency,
                    "distance": distance,
                    "n_matches": len(matches),
                },
                metrics={"min_match": min(matches), "median_match": float(np.median(matches))},
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


def _version_subtitle(records: list[dict]) -> str:
    """Return a 'gwmock-signal <versions>' subtitle for the figures."""
    versions = sorted({r["provenance"].get("package_version") or "?" for r in records})
    return f"{PACKAGE} {', '.join(versions)}"


def _performance_table(records: list[dict]) -> str:
    """Return a Markdown table of the performance records (warm is the headline)."""
    header = (
        "| cell | device | warm ev/s | cold/warm wall (s) | compile (s) | peak mem (GB) | output (GB) |\n"
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |\n"
    )
    rows = []
    for record in records:
        rows.append(
            f"| {record['label']} | {_device(record)} | {_metric(record, 'events_per_second_warm'):.0f} | "
            f"{_metric(record, 'wall_seconds_cold'):.0f} / {_metric(record, 'wall_seconds_warm'):.0f} | "
            f"{_metric(record, 'compile_seconds'):.1f} | {_metric(record, 'peak_rss_bytes') / 1e9:.1f} | "
            f"{_metric(record, 'output_bytes') / 1e9:.2f} |"
        )
    return header + "\n".join(rows) + "\n"


def _consistency_table(records: list[dict]) -> str:
    """Return a Markdown table of ripple-vs-LAL matches per approximant."""
    header = "| Approximant | f_min (Hz) | worst match | median match |\n| --- | ---: | ---: | ---: |\n"
    rows = [
        f"| `{r['label']}` | {r['configuration'].get('minimum_frequency', '')!s} | "
        f"{_metric(r, 'min_match'):.5f} | {_metric(r, 'median_match'):.5f} |"
        for r in records
    ]
    return header + "\n".join(rows) + "\n"


def render(records: list[dict], output_dir: Path) -> list[Path]:
    """Render figures + table snippets for the gwmock-signal records under ``output_dir``.

    Writes SVG figures to ``output_dir/figures`` and Markdown table snippets to
    ``output_dir/generated``. Returns the paths written.
    """
    figures = output_dir / "figures"
    generated = output_dir / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    performance = sorted((r for r in records if r["suite"] == "performance"), key=lambda r: r["label"])
    consistency = sorted((r for r in records if r["suite"] == "consistency"), key=lambda r: r["label"])

    if performance:
        subtitle = _version_subtitle(performance)
        labels = [f"{r['label']}\n{_device(r)}" for r in performance]
        paired = [
            ("events_per_second", "Throughput [events/s]", "performance_throughput.svg"),
            ("wall_seconds", "Wall time [s]", "performance_walltime.svg"),
            ("cpu_core_hours", "CPU core-hours", "performance_cpu_core_hours.svg"),
            ("gpu_hours", "GPU-hours", "performance_gpu_hours.svg"),
        ]
        for stem, ylabel, filename in paired:
            cold = [_metric(r, f"{stem}_cold") for r in performance]
            warm = [_metric(r, f"{stem}_warm") for r in performance]
            if not any(cold) and not any(warm):
                continue  # e.g. no GPU runs -> skip GPU-hours
            written.append(
                grouped_bar(
                    figures / filename,
                    labels=labels,
                    cold=cold,
                    warm=warm,
                    ylabel=ylabel,
                    title=f"{ylabel} - cold vs warm\n{subtitle}",
                )
            )
        singles = [
            ([_metric(r, "compile_seconds") for r in performance], "One-time compile [s]", "performance_compile.svg"),
            (
                [_metric(r, "peak_rss_bytes") / 1e9 for r in performance],
                "Peak memory [GB]",
                "performance_peak_memory.svg",
            ),
            ([_metric(r, "output_bytes") / 1e9 for r in performance], "Output data [GB]", "performance_output.svg"),
        ]
        for values, ylabel, filename in singles:
            if not any(values):
                continue
            written.append(
                single_bar(
                    figures / filename, labels=labels, values=values, ylabel=ylabel, title=f"{ylabel}\n{subtitle}"
                )
            )
        table = generated / "performance-table.md"
        table.write_text(_performance_table(performance))
        written.append(table)

    if consistency:
        subtitle = _version_subtitle(consistency)
        written.append(
            single_bar(
                figures / "consistency_matches.svg",
                labels=[r["label"] for r in consistency],
                values=[_metric(r, "min_match") for r in consistency],
                ylabel="worst-case match",
                title=f"ripple vs LAL - worst-case match\n{subtitle}",
            )
        )
        table = generated / "consistency-table.md"
        table.write_text(_consistency_table(consistency))
        written.append(table)

    return written
