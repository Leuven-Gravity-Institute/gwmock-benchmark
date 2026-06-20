# ruff: noqa: PLC0415 - matplotlib is imported lazily so this module stays import-safe
"""Generic bar-chart helpers for rendering benchmark figures.

Reusable across package suites. Matplotlib is imported lazily (and forced to the Agg
backend) so this module imports without it installed; it is only needed when actually
rendering, in the docs/aggregate pipeline.
"""

from __future__ import annotations

from pathlib import Path

_COLD = "#7fcdbb"
_WARM = "#2c7fb8"


def _axes(n_bars: int):
    """Create a figure/axes sized for ``n_bars`` and return ``(plt, figure, axes)``."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(figsize=(max(6.0, 1.6 * n_bars), 4.5))
    return plt, figure, axes


def _finish(plt, figure, axes, labels, ylabel: str, title: str, path: Path) -> Path:  # noqa: PLR0913
    """Apply shared styling, save ``figure`` to ``path`` (SVG), and close it."""
    axes.set_xticks(range(len(labels)))
    axes.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    axes.set_ylabel(ylabel)
    axes.set_title(title, fontsize=10)
    axes.grid(axis="y", alpha=0.3)
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path)
    plt.close(figure)
    return path


def single_bar(path: Path, *, labels: list[str], values: list[float], ylabel: str, title: str) -> Path:
    """Render a single-series bar chart to ``path``."""
    plt, figure, axes = _axes(len(labels))
    axes.bar(range(len(labels)), values, color=_WARM)
    return _finish(plt, figure, axes, labels, ylabel, title, path)


def grouped_bar(  # noqa: PLR0913 - one keyword per chart dimension
    path: Path, *, labels: list[str], cold: list[float], warm: list[float], ylabel: str, title: str
) -> Path:
    """Render grouped cold/warm bars to ``path``."""
    plt, figure, axes = _axes(len(labels))
    width = 0.4
    positions = range(len(labels))
    axes.bar([p - width / 2 for p in positions], cold, width, label="cold (incl. compile)", color=_COLD)
    axes.bar([p + width / 2 for p in positions], warm, width, label="warm (steady state)", color=_WARM)
    axes.legend(fontsize=8)
    return _finish(plt, figure, axes, labels, ylabel, title, path)
