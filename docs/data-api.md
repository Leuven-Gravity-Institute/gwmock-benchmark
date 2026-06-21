---
title: Data API
description:
    Stable JSON endpoints for retrieving the committed benchmark records
    programmatically, with a published record schema.
---

# Data API

The benchmark results on this site are also published as **static JSON** at
stable URLs, so you can retrieve the full dataset programmatically instead of
scraping the figures and tables. The files are regenerated from the committed
records on every build, so the API always matches what the pages show.

Everything lives under a versioned base URL:

```text
https://leuven-gravity-institute.github.io/gwmock-benchmark/data/v1/
```

## Endpoints

| Path                                                     | Contents                                                                                                                                                 |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`index.json`](data/v1/index.json)                       | Manifest: API/schema version, build timestamp, total record count, and per-package/per-suite counts with links to every other file. **Start here.**      |
| [`records.json`](data/v1/records.json)                   | Every record across all packages and suites in a single response.                                                                                        |
| `<package>/<suite>.json`                                 | One package + suite, e.g. [`signal/performance.json`](data/v1/signal/performance.json) and [`signal/consistency.json`](data/v1/signal/consistency.json). |
| [`schema/record-v1.json`](data/v1/schema/record-v1.json) | JSON Schema (draft 2020-12) describing a single record.                                                                                                  |

`records.json` and the per-suite files share one envelope:

```json
{
    "api_version": "v1",
    "schema_version": 1,
    "generated": "2026-06-21T00:00:00+00:00",
    "count": 19,
    "records": [
        /* ... */
    ]
}
```

## Record shape

Each entry in `records` is a committed benchmark record — a small, metrics-only
document of `configuration` (run settings), `metrics` (measured numbers), and
`provenance` (code versions + hardware, no hostname). See
[`schema/record-v1.json`](data/v1/schema/record-v1.json) for the authoritative
definition and the [data layout notes](contribute.md) for how records are
produced.

## Examples

Fetch the manifest, then the full dataset:

```bash
curl -s https://leuven-gravity-institute.github.io/gwmock-benchmark/data/v1/index.json
curl -s https://leuven-gravity-institute.github.io/gwmock-benchmark/data/v1/records.json
```

Load every record in Python (standard library only):

```python
import json
import urllib.request

BASE = "https://leuven-gravity-institute.github.io/gwmock-benchmark/data/v1/"

with urllib.request.urlopen(BASE + "records.json") as response:
    payload = json.load(response)

for record in payload["records"]:
    print(record["suite"], record["label"], record["metrics"])
```

## Stability

The `v1` base is **additive** — new records, packages, suites, and fields may
appear, but existing fields keep their meaning. A breaking change to the layout
would be published under a new version (`data/v2/`) so existing consumers keep
working.
