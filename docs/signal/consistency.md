---
title: Consistency
description:
    Agreement between the gwmock-signal ripple (JAX) backend and the LAL
    baseline across supported approximants.
---

# Consistency

The [ripple](https://github.com/Leuven-Gravity-Institute/gwmock-signal) (JAX)
backend is an alternative implementation of the same waveform models LAL
provides. This page tracks their agreement so the JAX/GPU path can be trusted
against the LAL baseline.

For every approximant, the **frequency-domain overlap** between the ripple and
LAL waveforms is computed across several parameter sets on a shared frequency
grid and `f_ref`. The overlap uses `Re(⟨a,b⟩)` with **no time or phase
maximization** — the implementations must agree exactly, so any residual
discrepancy lowers the overlap rather than being optimized away. Results are
reported as **`log₁₀` overlap loss** (`log₁₀(1 − overlap)`); more negative is
better, and ≈ −15 is machine precision.

The chart plots both the **worst-case** and **median** loss per waveform model,
with models sorted so the **best (most negative worst case) is on the left**.
The `gwmock-signal` version is shown in the tooltip and the table.

`TaylorF2` is omitted here (covered in the gwmock-signal test suite). This is a
numerical property of the waveforms, independent of the hardware that computed
it.

--8<-- "docs/signal/generated/consistency-charts.md"

--8<-- "docs/signal/generated/consistency-table.md"

!!! note "Reproduce / contribute"

    ```bash
    uv run --extra signal gwmock-benchmark signal consistency -o data/signal/consistency
    ```

    Then open a pull request adding the data files. See
    [Contribute a benchmark](../contribute.md).
