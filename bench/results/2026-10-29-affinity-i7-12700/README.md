# Flash-Next IQ3_S CPU-affinity validation on Windows

Measured 2026-10-29, 17:21-17:51 Asia/Shanghai. Independent evidence for
[Strata #1912](https://github.com/Niko1221/Strata/pull/1912), not a proposed patch or a standard-protocol submission.

i7-12700 (8P/4E), RTX 5060 Ti 16 GB, 128 GB DDR4, Windows 11, driver 610.88.
Official engine 0.1.52, BUILD f-027-rel/a42cc3d7df70, CUDA 13.0;
exe SHA-256 dbd0f9b692e9790cd8a25b383a265fab4ccf424a98e6ebc533c6e00dc58628bc.
Existing Qwen3.8-Flash-Next GSQ-RCO IQ3_S native pack, PLE, MTP and expert profile.
Exact files/hashes: [summary.json](summary.json). Model revision was not recorded.

## Method

Five restart rounds, all/P/measure each round: APM, PMA, MAP, MPA, AMP.
Three synthetic inputs (code 1025, English 4097, Chinese 1025 tokens), each with
256 generated tokens. Input order rotates by round and is identical within a round.
Each of 15 new processes receives the same 96-output-token warm-up, excluded from timing.
All 45 requests match the gate's complete output IDs and offered/accepted draft counts.
Three modes also pass six deterministic tasks each (18/18); this is not broad quality evaluation.
The gate ran with downloads active; gate times are not performance evidence.

Controlled settings: actual cache 3107 slots/6092 MiB (budget argument 2400),
64K context cap, INT8 KV/32K resident, prefill 1024, spec4/min-p0,
lookup/suffix off, fixed PCIe fraction .55, adaptation/conversation cache off,
prompt CPU share and route-tail skipping off. Greedy, neutral penalties.
[config.json](config.json) records the arguments/environment; [workloads.json](workloads.json) contains exact inputs/IDs.
Worker defaults are part of the policy: all 11, P 7, plus host.
Post-warm-up Windows snapshots confirmed the expected worker single-core masks;
host core 0 was logged, not continuously verified during generation.

The downloader was stopped for the entire formal matrix. All 31 before/after-arm
and final checks found no downloader and unchanged files/checkpoints.
Pinned HtoD: 24.846733 before, 24.853699 GB/s after (0.0280% drift).

## Results

Primary metric: native prefill + decode milliseconds, not HTTP TTFT.
Ratios are computed within each round before taking their median. Greater than 1 means P is faster.

| Input | Median all/P ratio (range, five pairs) | P faster |
| --- | --- | --- |
| Code | 1.0019 (0.9916-1.1431) | 4/5 |
| English | 0.9996 (0.9549-1.0461) | 2/5 |
| Chinese | 1.0016 (0.9637-1.0932) | 3/5 |

All samples: [paired-results.csv](paired-results.csv), [per-request JSON](summary.json),
[15 sanitized engine logs](logs). No slow sample was removed.
Observed within-manual-mode relative ranges in total cost are about 4.9-12.8%.
The prospective condition (same direction in all five pairs, exceeding observed
within-mode variation) was not met. No stable selection loss was demonstrated.

Measure selected P four times, all once. Microbenchmark all/P milliseconds:
9.71/10.09, 9.70/9.01, 9.57/8.53, 9.98/8.93, 9.27/10.27.
These decisions follow the existing 10% P preference. The final round's manual
all was faster on code/Chinese and P faster on English; neither mode won every input.

Paired P/all process CPU-time medians: .6848/.7114/.6786 for code/English/Chinese
(P lower in 5/5 each), about 29-32% less accumulated CPU time. This is not energy
measurement, a critical-path attribution, or a fixed-worker-count comparison.

## Failed attempts and limits

Preparation failed on component-root resolution, unsupported native spec0,
insufficient VRAM at a larger cache, and a Windows pause-status assertion.
No formal timing from those attempts is included. A thread-count diagnostic launch
was blocked by automatic review and was not used by the formal controller.
An earlier matrix's 15 requests were excluded in full after another session resumed
downloads at 17:09:36-17:09:59. Another three-request matrix failed a sustained
quiet comparison; the differing fields were not saved, so its cause is unresolved.
Both remain excluded; only performance-04 is represented here.

One hardware configuration, controlled policies, three synthetic requests, five rounds.
Not daily defaults, a standardized benchmark, API/concurrency, other contexts/CPUs/backends,
broad quality equivalence, a new optimization, or evidence to change a default.
No continuous temperature/clock capture or soft/hard page-fault classification.
Daily service and original config were restored, and downloads restarted afterward.

This compact bundle was prepared after measurement for a discussion comment.
Local controller/helper/plan hashes are retained in the JSON as provenance, but their
private lab dependencies and full resource samples are not a portable replay package.
The offline verifier was added after measurement and does not validate a GPU rerun.
