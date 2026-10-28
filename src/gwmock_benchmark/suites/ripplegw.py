"""Continuous-wave measurements of Ripple's source-polarization generator."""

from __future__ import annotations

from pathlib import Path

_SUITE = "continuous-wave"


def check_contribution(record: dict) -> list[str]:
    """Check CW mismatch and throughput metrics against their recorded primitives."""
    if record.get("suite") != _SUITE:
        return [f"unknown ripplegw suite {record.get('suite')!r}"]

    config = record.get("configuration", {})
    metrics = record.get("metrics", {})
    problems: list[str] = []
    batch = config.get("batch_size")
    if not isinstance(batch, int) or batch < 1:
        problems.append(f"configuration.batch_size must be a positive integer, got {batch!r}")

    mismatch = metrics.get("etd_weighted_mismatch")
    if not isinstance(mismatch, (int, float)) or not 0.0 <= mismatch <= 1.0:
        problems.append(f"metrics.etd_weighted_mismatch must be in [0, 1], got {mismatch!r}")
    ratio = metrics.get("etd_weighted_amplitude_ratio")
    if not isinstance(ratio, (int, float)) or ratio <= 0.0:
        problems.append(f"metrics.etd_weighted_amplitude_ratio must be positive, got {ratio!r}")

    pairs = (
        ("ripple_warm_single_seconds", "ripple_warm_single_signals_per_second", 1.0),
        ("ripple_warm_vmap_seconds_per_signal", "ripple_warm_vmap_signals_per_second", 1.0),
        ("lal_warm_seconds_per_signal", "lal_warm_signals_per_second", 1.0),
        ("lal_warm_loop_seconds_per_signal", "lal_warm_loop_signals_per_second", 1.0),
    )
    for latency_key, throughput_key, numerator in pairs:
        latency, throughput = metrics.get(latency_key), metrics.get(throughput_key)
        if not isinstance(latency, (int, float)) or latency <= 0:
            problems.append(f"metrics.{latency_key} must be positive, got {latency!r}")
        elif not isinstance(throughput, (int, float)) or abs(throughput - numerator / latency) > max(
            1e-8, 1e-6 * numerator / latency
        ):
            problems.append(f"metrics.{throughput_key} disagrees with {latency_key}")

    loop_latency, loop_rate = metrics.get("ripple_warm_loop_seconds_per_signal"), metrics.get(
        "ripple_warm_loop_signals_per_second"
    )
    if not isinstance(loop_latency, (int, float)) or loop_latency <= 0:
        problems.append(f"metrics.ripple_warm_loop_seconds_per_signal must be positive, got {loop_latency!r}")
    elif not isinstance(batch, int) or not isinstance(loop_rate, (int, float)) or abs(
        loop_rate - 1.0 / loop_latency
    ) > max(1e-8, 1e-6 / loop_latency):
        problems.append("metrics.ripple_warm_loop_signals_per_second disagrees with loop latency")
    return problems


def render(records: list[dict], output_dir: Path) -> list[Path]:
    """Write a compact generated CW benchmark table for the docs site."""
    rows = sorted((r for r in records if r.get("suite") == _SUITE), key=lambda r: r["label"])
    if not rows:
        return []
    target = output_dir / "generated" / "continuous-wave-table.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "| Run | Device | ET-D mismatch | Ripple single (signals/s) | Ripple vmap (signals/s) | LAL single (signals/s) | LAL loop (signals/s) |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for record in rows:
        metrics = record["metrics"]
        devices = record["provenance"].get("gpu_models") or []
        device = devices[0] if devices else record["provenance"].get("cpu_model", "unknown")
        lines.append(
            f"| {record['label']} | {device} | {metrics['etd_weighted_mismatch']:.3e} | "
            f"{metrics['ripple_warm_single_signals_per_second']:.3g} | "
            f"{metrics['ripple_warm_vmap_signals_per_second']:.3g} | "
            f"{metrics['lal_warm_signals_per_second']:.3g} | "
            f"{metrics['lal_warm_loop_signals_per_second']:.3g} |"
        )
    target.write_text("\n".join(lines) + "\n")
    return [target]
