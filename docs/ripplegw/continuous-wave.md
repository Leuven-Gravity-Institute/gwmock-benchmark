---
title: Continuous-wave comparison
description: ET-D-weighted LALPulsar vs Ripple source-polarization agreement and throughput results.
---

# Continuous-wave comparison

The accuracy metric compares source `h+` and `hx` polarizations from Ripple
with a LALPulsar barycenter reference on the same sample grid. The LAL
barycenter uses the H1 site location. The ET-D design PSD weights the frequency
bins; this is not a detector-projected ET response or a network result. The
reported mismatch maximizes over one common amplitude and phase, and the
amplitude ratio is retained so normalization cannot conceal a scale error.

Warm throughput records single-signal JIT, a Python loop over the configured
batch, and one `vmap` call. Cold Ripple times include first-call compilation.
LAL generates detector strain, whereas Ripple generates two source
polarizations, so the output payloads differ.

--8<-- "docs/ripplegw/generated/continuous-wave-table.md"

The records and their complete metrics-only provenance are available from the
[continuous-wave data API](../data/v1/ripplegw/continuous-wave.json).

The [benchmark runner](https://github.com/Leuven-Gravity-Institute/gwmock-benchmark/blob/main/scripts/benchmark_ripple_cw.py)
records its exact Ripple source revision and the ET-D PSD checksum; the corresponding [Ripple source
commit](https://github.com/GW-JAX-Team/ripple/commit/85c76f481c4f0504ec1d74e7ffc34d027e88ab6d)
and [Bilby PSD revision](https://github.com/bilby-dev/bilby/tree/0985f75c664786e21cc4f662d4f12fe181b1a536/bilby/gw/detector/noise_curves)
are public.
