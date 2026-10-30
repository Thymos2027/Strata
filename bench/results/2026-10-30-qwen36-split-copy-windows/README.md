# [Benchmark] Isolated split-stage-copy validation on Windows / RTX 5060 Ti

Measured 2026-10-30, Asia/Shanghai. Independent evidence for [Strata PR3905](https://github.com/Niko1221/Strata/pull/3905); this tests the original author's implementation and proposes no duplicate patch.

I isolated the four copy-path hunks from xyehya's commit `af08278c15e857345dad95805dda7256a559dcfa` onto main `46c152a1310f77cd2f0ce2c7cd213962df14fe83`, adapting only the CLI context. This does **not** test the complete stacked PR3905 or its attention, KV, GDN, side-stream or always-on kernel changes.

Windows 11, RTX 5060 Ti 16GB, i7-12700, 128GB DDR4, driver 610.88, MSVC 19.42 / CUDA 13.2 / sm_120. Model: Qwen3.6-35B-A3B UD-Q4_K_XL, SHA256 `55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1`. Fixed 32K context cap, chunk2048, 63 expert slots with placement frozen, 7 pool workers, MTP0, packed/MMQ, greedy sampling. A and B use the same candidate executable; B adds only `--split-stage-copy`. No STREAM_ALL override.

The baseline, candidate-off and candidate-on each produced 64 full-vocabulary logit rows for both 1025- and 16385-token inputs, using identical forced histories. All six dumps are finite; the three arms are bitwise identical at each length. Four free-generation gates and all 20 formal requests match the baseline 64-token output, with zero slot replacements and no draft/prefix reuse. The CUDA build and 17 selected tests passed; HIP/SYCL were not built.

Five fresh-process pairs per input, alternating AB/BA and input order, with the same separate 1K/64-token warmup in every process. All formal timings are without a profiler. Ratios are paired A/B time, so greater than one favors B:

| Input | Prefill median [range] | Decode median [range] | Prefill + decode median [range] |
| --- | --- | --- | --- |
| 1K | 1.3021 [1.3019, 1.3089] | 1.0008 [0.9688, 1.0272] | 1.0825 [1.0576, 1.1018] |
| 16K | 1.1915 [1.1890, 1.1947] | 1.0282 [0.9477, 1.1767] | 1.1457 [1.1257, 1.1874] |

Prefill and prefill+decode favor B in 5/5 pairs at both lengths. Decode alone is noisy, so I do not attribute a decode improvement to this copy slice. Total here excludes load/warmup and covers only 64 output tokens; it is not an HTTP or standard community benchmark. Pinned-HtoD controls were 24.956 before / 24.881 GB/s after.

A conditional 16K CUDA/NVTX trace for each arm confirms the mechanism: HtoD bytes decrease from 157.13 to 118.46 GB, while about 38.67 GB moves to DtoD on a separate bulk-copy stream. Expert staging bytes are exactly conserved: 157126656000 = 118458768000 + 38667888000. Copy time not overlapping kernels is approximately 1.745 versus 0.594 seconds, with kernel unions of 5.330 versus 5.323 seconds. These profiled windows explain mechanism only and are excluded from the five-pair results. Outputs, placement, actual engine CUDA activity and the three closed client NVTX ranges were checked. Role-specific profiler warnings are retained; CPU sampling was not enabled. These checks do not constitute a byte dump of all staging memory.

The first attempt stopped at the baseline output gate because my auxiliary full-logit entry lacked an adjacent `strata_kq.dll` and used the native prompt fallback. No candidate-on or formal timings came from that attempt. After fixing only the adapter/DLL deployment and requiring actual MMQ activation, I started a new run and retained the failed evidence.

This supports the opt-in copy path on this one fixed Windows/CUDA configuration. It does not establish other slot/chunk settings, dynamic replacement, full quality, long-run behavior, cross-backend compatibility or a default change. Full CPU critical-path attribution remains incomplete because CPU sampling was unavailable.

## Evidence and exact workload

[All 24 free-generation requests and six numeric checks](results.json), [all ten pairs](pairs.csv),
[statistics](statistics.json), [trace analysis](trace-summary.json), [source patch](candidate.patch),
[file/build identities](provenance.json), [recorded commands with path placeholders](commands.json),
[logs](logs), and [the excluded first attempt](failed-attempt.json).

Three synthetic inputs are included as *.prompt.txt and exact *.ids.json: r0-l1024 and
r0-l16384 are measured; r1-l1024 is the common 64-output-token warmup. Input hashes
use SHA256 of compact JSON token arrays. Each request is sent on the native engine protocol:

```text
GEN 64 temperature=0 top_p=1 top_k=20 min_p=0 penalty_present=0 penalty_freq=0 penalty_repeat=1 penalty_last_n=0 seed=0 <comma-separated input IDs>
```

The original baseline's 64 generated IDs (included in the gate rows) supply the first
63 tokens of identical forced history for each full-logit check. Each f32 file is
64 x 248320 float32, 63569920 bytes; hashes are archived in results.json. Full dumps,
NSight reports/SQLite and binary files stay local and are not included here.

The prospective continuation rule was median paired prefill A/B >1.03 and B faster in
at least 4/5 pairs at either length. Both lengths met it; only then were two 16K traces
captured. The three client NVTX windows are request, prefill-to-first-token and
decode-after-first-token; they are client boundaries, not exact GPU step boundaries.
The trace JSON retains all role-specific warnings. No CPU sampling was available.

`python verify.py` checks this archive offline: hashes, input/output IDs, numeric hash
agreement, gate/formal layouts, native log timings, paired ratios and trace byte accounting.
This verifier and evidence exporter were written **after** measurement and were not GPU
rerun tools. Original lab controllers have private toolchain/helper dependencies and are
identified by hashes, not presented as a portable runner. Path placeholders replace only
local roots; source patch and exact token files are unchanged. No additional measurements
were made while preparing this bundle. This is not an approved standard benchmark or a
full PR3905/cross-backend validation. Daily service/config was restored after both stages.
