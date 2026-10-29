Independent validation on an **i7-12700 (8P/4E), RTX 5060 Ti 16 GB, 128 GB DDR4, Windows 11**, official engine **0.1.52**, Flash-Next IQ3_S (2026-10-29).

Five restart rounds of `all` / `p-cores` / `measure`, three synthetic code/English/Chinese inputs, 256 output tokens each: **15 starts, 45 requests**. Actual cache fixed at 3107 slots/6092 MiB; all=11 workers, P=7, plus host. Complete output IDs and offered/accepted draft counts matched across all requests; 18/18 small deterministic tasks passed.

Native prefill+decode **paired all/P time ratios** (median and range; >1 means P faster):

| Input | Five-pair ratio | P faster |
| --- | --- | --- |
| Code, 1025 tokens | 1.0019 (0.9916–1.1431) | 4/5 |
| English, 4097 tokens | 0.9996 (0.9549–1.0461) | 2/5 |
| Chinese, 1025 tokens | 1.0016 (0.9637–1.0932) | 3/5 |

`measure` selected P four times and all once, following the existing 10% P preference. No stable end-to-end selection loss was demonstrated. P used about **29–32% less accumulated process CPU time** (lower in 5/5 pairs per input), which is not an energy measurement.

[Evidence, configuration and sanitized logs](https://github.com/Thymos2027/Strata/blob/d973440a29e6efc8106ea7d8f4ebe6d6cbc6035c/bench/results/2026-10-29-affinity-i7-12700/README.md) · [all 15 paired measurements](https://github.com/Thymos2027/Strata/blob/d973440a29e6efc8106ea7d8f4ebe6d6cbc6035c/bench/results/2026-10-29-affinity-i7-12700/paired-results.csv).

This is a controlled native-protocol study (spec4/min-p0, fixed PCIe fraction, lookup/suffix/adaptation off), not daily defaults, a standard benchmark or broad quality validation. Failed/interrupted timing batches are excluded and documented. HtoD stayed at ~24.85 GB/s. No engine/default change or reopening is requested.
