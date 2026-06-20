---
title: Contribute a benchmark
description:
    How to run a gwmock benchmark on your hardware and contribute the results
    via a pull request.
---

# Contribute a benchmark

**Benchmarks from more hardware make these pages better — your contribution is
welcome.** You run a benchmark on your machine or cluster and open a pull
request that adds a small JSON results file. The figures and tables on the site
are **generated automatically** from those files, so you never touch the docs or
commit an image.

## 1. Install

Install gwmock-benchmark with the extra for the package you want to benchmark
(e.g. `signal` for [gwmock-signal](signal/index.md)):

```bash
uv pip install "gwmock-benchmark[signal]"
```

## 2. Run a benchmark

Each run writes one metrics-only JSON record. Locally:

```bash
# Performance: one backend/method cell (cold + warm)
gwmock-benchmark signal performance --backend ripple --method batched --n-events 5000 \
    -o data/signal/performance/ripple_batched_<your-gpu>.json

# Consistency: ripple vs LAL, one record per approximant
gwmock-benchmark signal consistency -o data/signal/consistency
```

Keep the **settings comparable** to the existing records (same `--n-events`,
approximant, etc.) so your numbers line up on the charts; vary only the
hardware.

### On a cluster

Generate a submission script for your scheduler and submit it:

```bash
gwmock-benchmark submit slurm \
    --command "gwmock-benchmark signal performance --backend ripple --method batched \
               --n-events 5000 -o data/signal/performance/ripple_batched_<your-gpu>.json" \
    --cpus 8 --gpus 1 --memory-gb 32 --time 04:00:00 \
    --account <your-account> --partition <your-partition> -o run.slurm
# then: sbatch run.slurm    (or: condor_submit for `submit htcondor`)
```

## 3. Add the data file

- Put records under **`data/<package>/<suite>/<name>.json`** (the CLI already
  does).
- **Name files by hardware, never by cluster** — e.g.
  `ripple_batched_nvidia-a30.json`, not `ripple_batched_mycluster.json`.
- Records are **metrics-only** (no raw arrays/logs) and capped at **16 KB**. The
  provenance records your CPU/GPU model and library versions — **not** the
  hostname.
- **Do not commit figures or tables.** They live under `docs/<package>/figures`
  and `docs/<package>/generated`, are git-ignored, and are regenerated on
  deploy.

## 4. Check it builds (optional but encouraged)

```bash
gwmock-benchmark validate --data-dir data   # the same check CI runs (see below)
uv run pytest tests/test_data.py            # schema, size, no hostname + internal consistency
uv run --group docs gwmock-benchmark aggregate   # render figures + tables
uv run --group docs zensical serve          # preview the site locally
```

## 5. Open a pull request

Commit your new `data/...json` file(s) and open a PR. CI runs
`gwmock-benchmark validate` on every record; once merged, the next docs deploy
regenerates the figures and tables with your hardware included.

!!! info "What validation checks (and what it can't)"

    The records you submit are produced on your own hardware, so this is a
    **trust-based** contribution model. CI does **not** re-run your benchmark; it
    checks that each record is well-formed, has complete provenance, and that its
    **derived metrics still agree with the primitives** they were computed from —
    e.g. `events_per_second == n_events / wall_seconds`, `compile == cold − warm`,
    and the output size matches the configured data product. That catches
    accidental errors and hand-edited numbers, but cannot detect a fully
    self-consistent fabricated record. Please submit numbers from real runs.

Thanks for contributing!
