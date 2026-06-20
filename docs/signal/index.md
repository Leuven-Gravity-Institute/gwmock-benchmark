---
title: gwmock-signal
description:
    Benchmarks for the gwmock-signal package — performance and ripple-vs-LAL
    consistency.
---

# gwmock-signal benchmarks

Benchmarks for
[gwmock-signal](https://github.com/Leuven-Gravity-Institute/gwmock-signal):

- **[Performance](performance.md)** — cost of generating a CBC catalogue data
  product across backends (`lal`, `pycbc`, `ripple`), methods (per-event vs the
  batched on-device path), and hardware.
- **[Consistency](consistency.md)** — agreement between the ripple (JAX) backend
  and the LAL baseline, per approximant.

All figures and tables are generated from the committed records under
`data/signal/`. To add your own results, see
[Contribute a benchmark](../contribute.md).
