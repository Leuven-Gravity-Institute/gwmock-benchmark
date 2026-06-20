# gwmock-benchmark

[![Python CI](https://github.com/Leuven-Gravity-Institute/gwmock-benchmark/actions/workflows/ci.yml/badge.svg)](https://github.com/Leuven-Gravity-Institute/gwmock-benchmark/actions/workflows/ci.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/Leuven-Gravity-Institute/gwmock-benchmark/main.svg)](https://results.pre-commit.ci/latest/github/Leuven-Gravity-Institute/gwmock-benchmark/main)
[![Documentation](https://github.com/Leuven-Gravity-Institute/gwmock-benchmark/actions/workflows/documentation.yml/badge.svg)](https://leuven-gravity-institute.github.io/gwmock-benchmark/)
[![codecov](https://codecov.io/gh/Leuven-Gravity-Institute/gwmock-benchmark/graph/badge.svg?token=24BQ7UOGOY)](https://codecov.io/gh/Leuven-Gravity-Institute/gwmock-benchmark)
[![PyPI Version](https://img.shields.io/pypi/v/gwmock-benchmark)](https://pypi.org/project/gwmock-benchmark/)
[![Python Versions](https://img.shields.io/pypi/pyversions/gwmock-benchmark)](https://pypi.org/project/gwmock-benchmark/)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![SPEC 0 — Minimum Supported Dependencies](https://img.shields.io/badge/SPEC-0-green?labelColor=%23004811&color=%235CA038)](https://scientific-python.org/specs/spec-0000/)
[![DOI](https://zenodo.org/badge/1275019674.svg)](https://doi.org/10.5281/zenodo.20777458)

Shared benchmarking for the **gwmock** packages: one harness, the committed
results, and the rendered report site — in one place.

**📊 Results: <https://leuven-gravity-institute.github.io/gwmock-benchmark/>**

It exists so that every gwmock package is benchmarked the same way, so anyone
can contribute results from their own hardware with a single pull request, and
so the package repositories stay free of benchmark tooling, data, and figures.

## How it works

1. You run a benchmark with the CLI; it writes one **metrics-only JSON record**.
2. You open a pull request adding that file under `data/<package>/<suite>/`.
3. CI validates it; on merge, the docs pipeline regenerates the figures and
   tables from the data — **contributors never commit images or edit the docs.**

Records are tiny (~1–2 KB), carry full provenance (CPU/GPU model, library
versions — no hostnames), and are capped at 16 KB so the dataset stays light in
the repository.

## Benchmarked packages

| Package                                                                    | Suites                   | Extra                      |
| -------------------------------------------------------------------------- | ------------------------ | -------------------------- |
| [gwmock-signal](https://github.com/Leuven-Gravity-Institute/gwmock-signal) | performance, consistency | `gwmock-benchmark[signal]` |

More packages (`gwmock-pop`, `gwmock-noise`, `gwmock`) plug in as suites under
`src/gwmock_benchmark/suites/`.

## Install

```bash
uv pip install "gwmock-benchmark[signal]"   # extra per package you want to benchmark
```

Linux and macOS (the harness uses Unix facilities and the suites pull HPC
packages such as lalsuite); Python 3.12–3.14.

## CLI

```bash
# Run a benchmark (writes a record)
gwmock-benchmark signal performance --backend ripple --method batched --n-events 5000 -o out.json
gwmock-benchmark signal consistency -o data/signal/consistency

# Generate a cluster submission script for any command
gwmock-benchmark submit slurm --command "gwmock-benchmark signal performance ..." \
    --cpus 8 --gpus 1 --time 04:00:00 -o run.slurm

# Render the committed dataset into the docs (run by the docs pipeline)
gwmock-benchmark aggregate --data-dir data --docs-dir docs
```

## Contributing results

Benchmarks from more hardware make the reports better. See the
**[Contribute a benchmark](https://leuven-gravity-institute.github.io/gwmock-benchmark/contribute/)**
guide for the full workflow (run locally or on a cluster → add a data file →
open a PR).

## Development

```bash
git clone git@github.com:Leuven-Gravity-Institute/gwmock-benchmark.git
cd gwmock-benchmark
uv venv --python 3.12 && source .venv/bin/activate
uv sync --group dev --group docs
uv run prek install
uv run pytest
```

Build the site locally (renders figures from `data/` first):

```bash
uv run --group docs gwmock-benchmark aggregate
uv run --group docs zensical serve
```

## License

**GPL-3.0-or-later** — see [LICENSE](LICENSE).
