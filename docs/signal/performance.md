---
title: Performance
description:
    gwmock-signal CBC catalogue generation cost across backends, methods, and
    hardware (wall time, core-hours, memory, output size).
---

# Performance

Cost of generating a CBC catalogue data product with
[gwmock-signal](https://github.com/Leuven-Gravity-Institute/gwmock-signal),
across **backends** (`lal`, `pycbc`, `ripple`), **methods** (per-event vs the
batched on-device path), and **hardware**.

Each run produces the catalogue **twice** — a **cold** run that pays one-time
JIT/XLA compilation and a **warm** steady-state run — and records both wall
times, the `compile_seconds` difference, throughput, core-hours, peak memory,
and output size. The **warm** numbers are the headline: at catalogue scale the
one-time compile amortizes away, so steady state is what a year-long run
actually sees. The cold bars are kept beside it because a GPU's compile is
larger than a CPU's, which can mask the device's advantage at small event
counts.

--8<-- "docs/signal/generated/performance-table.md"

![Throughput, cold vs warm](figures/performance_throughput.svg)

![Wall time, cold vs warm](figures/performance_walltime.svg)

![One-time compile](figures/performance_compile.svg)

??? note "More metrics (core-hours, memory, output size)"

    ![CPU core-hours](figures/performance_cpu_core_hours.svg)

    ![GPU-hours](figures/performance_gpu_hours.svg)

    ![Peak memory](figures/performance_peak_memory.svg)

    ![Output data](figures/performance_output.svg)

!!! note "Reproduce / contribute"

    ```bash
    uv run --extra signal gwmock-benchmark signal performance \
        --backend ripple --method batched --n-events 5000 \
        -o data/signal/performance/ripple_batched_<your-gpu>.json
    ```

    Then open a pull request adding the data file — figures and tables regenerate
    automatically. See [Contributing](../contributing.md).
