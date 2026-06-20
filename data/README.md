# Benchmark results

Committed benchmark records, one JSON file per data point. The docs site is
built from these files; contributors add results by opening a pull request that
drops new files here — **no figures, no edits to the docs.**

## Layout

```text
data/<package>/<suite>/<name>.json
```

- `<package>` — the benchmarked package, e.g. `signal` (gwmock-signal).
- `<suite>` — `performance` or `consistency`.
- `<name>` — a descriptive, **cluster-free** name. Performance records are named
  by backend, method, and hardware (e.g. `ripple_batched_nvidia-a30.json`);
  consistency records by approximant (e.g. `IMRPhenomD.json`).

## Record schema

Each file is a single object produced by `gwmock_benchmark.harness.make_record`:

| key              | meaning                                                               |
| ---------------- | --------------------------------------------------------------------- |
| `schema_version` | record schema version (currently `1`)                                 |
| `package`        | benchmarked package distribution name                                 |
| `suite`          | `performance` or `consistency`                                        |
| `label`          | human-readable label used in figures/tables                           |
| `configuration`  | run settings (scalars or flat lists only)                             |
| `metrics`        | measured numbers (values are numbers or `null`)                       |
| `provenance`     | versions + hardware (CPU/GPU model, core/GPU counts); **no hostname** |

**Records are metrics-only.** Raw arrays, time series, and logs are rejected,
and a hard **16 KB per-file cap** is enforced. The `tests/test_data.py` check
validates every file in CI, so a malformed or oversized contribution fails the
build.

## Generating records

Run a benchmark with the CLI, which writes a record in this schema:

```bash
uv run --extra signal gwmock-benchmark signal performance \
    --backend ripple --method batched --n-events 5000 \
    -o data/signal/performance/ripple_batched_<your-gpu>.json
```

See the [Contributing](../CONTRIBUTING.md) guide for the full workflow.
