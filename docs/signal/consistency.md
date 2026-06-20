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

For every approximant LAL implements in the time domain, the white,
time/phase-maximized **match** between the ripple and LAL backends is computed
across several parameter sets; the **worst-case** and **median** match per
approximant are recorded. `TaylorF2` is omitted here (LAL provides no
time-domain TaylorF2) and is covered against LAL's frequency-domain TaylorF2 in
the gwmock-signal test suite.

The match is a numerical property of the waveforms, independent of the hardware
that computed it.

--8<-- "docs/signal/generated/consistency-charts.md"

--8<-- "docs/signal/generated/consistency-table.md"

!!! note "Reproduce / contribute"

    ```bash
    uv run --extra signal gwmock-benchmark signal consistency -o data/signal/consistency
    ```

    Then open a pull request adding the data files. See
    [Contribute a benchmark](../contribute.md).
