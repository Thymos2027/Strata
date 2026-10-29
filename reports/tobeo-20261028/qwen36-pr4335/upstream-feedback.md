# Local draft: Windows/Blackwell validation of #4335

Historical draft, superseded by the [published comment](https://github.com/Niko1221/Strata/pull/4335#issuecomment-6488876445) and [report PR #4577](https://github.com/Niko1221/Strata/pull/4577). Recorded on 28–29 October 2026. This tests rynwang's existing implementation, without #4347 or engine source edits.

On this Windows/RTX 5060 Ti 16 GB system, the new auto rule selected 4096 at context32768. With a fixed 96-token history, 4096 improved the 16K prompt request total in all five pairs, but made the 1K request total slower in all five pairs. Generation was slower at both lengths, alongside fewer resident GPU experts (63 → 50).

Environment: i7-12700, 128 GB DDR4, driver610.88, MSVC19.42, CUDA13.2, sm120; Qwen3.6-35B-A3B-UD-Q4_K_XL, SHA-256 `55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1`. Main `5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d`; original PR head `bdf0bce2e5520680524efd3a5cf79db984c3902c`.

Same PR binary, explicit2048/4096, context32768, pool-workers7, MTP0, FP32 KV, packed enabled, automatic initial expert placement, then `STRATA_Q36_FIXED_SLOTS=1` to freeze residency. Each input/arm/repetition started a new process, with only the built-in warmup. Five alternating pairs per input; all samples retained. Synthetic prompts actually contain1025/16385 tokens. Both arms consume the identical96 forced token IDs and evaluate97 argmax positions; this is controlled work, not free generation or a community benchmark protocol run.

| Input | Stage | 2048 median ms | 4096 median ms | Median paired2048/4096 ratio | 4096 faster pairs |
| --- | --- | ---: | ---: | ---: | ---: |
| 1025 | prefill | 809.1 | 808.5 | 1.0004 | 5/5 |
| 1025 | generation | 2519.2 | 2594.6 | 0.9705 | 0/5 |
| 1025 | sum | 3327.8 | 3403.1 | 0.9779 | 0/5 |
| 16385 | prefill | 7165.2 | 5502.7 | 1.3029 | 5/5 |
| 16385 | generation | 3319.7 | 3393.0 | 0.9791 | 0/5 |
| 16385 | sum | 10478.0 | 8898.4 | 1.1788 | 5/5 |

Native timings exclude load/warmup/HTTP. Generation includes final printing of output IDs; no full logits are written during performance runs. This is97 argmax evaluations and96 actual decode forwards, so I do not report it as standard decode throughput. All20 performance requests matched the corresponding chunk's prior numerical-check argmax outputs; no expert slot replacements occurred. HtoD24.833714 before and24.855839 GB/s after, with model downloading suspended throughout timing.

Passed: native CUDA build;16 selected host/layout/sampling tests; full-logit comparisons for both prompts at97 positions ×248320 values. Main and PR are bitwise equal at the same explicit chunk; PR auto is bitwise equal to main explicit4096. Cross-chunk logits differ (top1:94/97 at1K,93/97 at16K);24 small deterministic task checks passed (12 per chunk: arithmetic JSON, Chinese formatting, executed pure Python functions, short/long retrieval).

Not tested: broad quality equivalence, dynamic replacement histories, API/concurrency, longer outputs, other configured contexts, other VRAM sizes, batch guards, MTP, HIP/SYCL/Metal, or request-level clock/temperature traces. The observed generation cost has not been isolated from other effects of changing chunk. These data support a long-input benefit and a short-input tradeoff on this one configuration, rather than a universally faster default.

Local reproducible evidence: [plan](experiment-plan.md), [report](README.md), [summary](summary.json), [all10 pairs](pairs.csv), [build driver](build_candidate.py), [execution driver](run_validation.py). The execution driver depends on the preceding locally archived baseline/input fixtures; a public submission must include or make those artifacts accessible. These local links are not yet public attachments.
