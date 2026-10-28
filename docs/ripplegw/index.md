---
title: Ripple continuous-wave benchmarks
description: ET-D-weighted agreement and throughput measurements for Ripple's continuous-wave source polarizations.
---

# Ripple continuous-wave benchmarks

This page reports a reproducible comparison of Ripple's JAX continuous-wave
source polarizations against a LALPulsar barycenter reference. ET-D is used as
a frequency weighting curve. The mismatch is not a projected ET detector or
network result.

- **[Continuous-wave comparison](continuous-wave.md)** — ET-D-weighted mismatch
  and warm throughput on CPU and GPU hardware.

Records include the hardware and software provenance and omit hostnames. The
LAL timing returns one detector-projected strain, while Ripple returns the
source `h+` and `hx` polarizations; treat their throughput as a useful
implementation comparison, not an identical-output benchmark.
