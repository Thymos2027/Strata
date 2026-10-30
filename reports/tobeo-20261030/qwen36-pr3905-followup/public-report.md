# [Benchmark] CPU, staging dependency and job-path follow-up for PR3905

Measured 2026-10-30, Asia/Shanghai. This supplements the [original isolated copy-slice report](https://github.com/Thymos2027/Strata/blob/7c0247c72d3e57df40e2dd8b9be415ec90046f98/bench/results/2026-10-30-qwen36-split-copy-windows/README.md) and [PR3905 comment](https://github.com/Niko1221/Strata/pull/3905#issuecomment-6512596830). The original five-pair unprofiled timings are unchanged. No duplicate engine patch or default change is proposed. This is archived evidence, not a standard benchmark or a portable GPU rerun package.

## Fixed setup and separate experiments

Windows 11, RTX 5060 Ti 16GB, i7-12700, 128GB DDR4, driver610.88, CUDA13.2/sm_120. Original baseline `46c152a1310f77cd2f0ce2c7cd213962df14fe83`; original author's copy-only slice `af08278c15e857345dad95805dda7256a559dcfa`. Qwen3.6-35B-A3B UD-Q4_K_XL, model SHA256 `55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1`. Fixed32K context, chunk2048,63 frozen slots,7 pool workers plus host, MTP0,packed/MMQ,greedy. Inputs1025/16385 tokens,64 outputs, same separate 1K/64 warmup per fresh process.

Three sources of evidence must be kept separate: (1) offline checks of the original copy-off/on prefill traces; (2) elevated CPU traces on the original baseline1K/16K and isolated copy-on16K; (3) separately built NVTX-only job diagnostics of the baseline, with split-stage-copy off. None validates the full stacked PR, side-stream flag, dynamic replacement, HIP/SYCL or full model quality.

## Original staging traces: additional dependency checks

[Mechanism summary](mechanism-summary.json) and [all320 stages](mechanism-stages.csv).

Every stage conserves bytes: off HtoD equals on HtoD+DtoD, with exactly63/256 moved viaDtoD and193/256 viaHtoD. Both buffer generations alternate160 times. EventId **and eventSyncId**, plus runtime correlation, connect prior reader→both copy streams→DtoD join on host-copy stream→ev_copy→compute. All320 chains passed the checks. Relevant recorded API return values are zero.

Stream metadata gives compute13/HtoD14/DtoD15 priorities0/0/-5; -5 was stored asuint32 4294967291. DtoD union208.49ms overlaps HtoD193.96ms and kernels9.11ms. This confirms stream assignment and overlap, not independent priority benefit or hardware preemption. Device event completion timestamps are zero: no measured device-wait duration or byte dump of staging contents is claimed.

## CPU leaf IP and scheduling

[CPU results](cpu-summary.json). Admin preflight obtained real samples and scheduling events before GPU work. Three500Hz leaf-IP/context-switch/CUDA/NVTX traces and three same-day plain references passed complete output and fixed-layout checks. Periodic engine-process samples were9448/12093/11867; engine-image IPs resolved against the matching local PDB, while kernel addresses remain unresolved. No full stacks were collected.

Baseline16K:52.63% of all engine-process periodic samples were worker epoch-wait loops,20.09% identified arithmetic/quantization,13.45% unresolved kernel addresses. The denominator includes injected profiler threads. All2430 arithmetic samples were at GPU-uncovered instants; sample proportions are not elapsed critical-path shares. Combined capture/plain decode ratios1.165/1.152/1.104 include all capture and ordering effects, not isolated CPU-sampling cost or copy-on speedup.

## Completion-order refinement of the baseline job path

[Job results](critical-path.json) and [126 token ledgers](token-ledger.csv). The archive includes all10160 phase ledgers, the final instrumentation patch/header, prewritten protocols, analysis programs, build/test identities, output IDs and retained logs/warnings.

Each of two independent diagnostic builds passed CUDA build,17 selected tests and Ninja no-work verification; each round passed four finite full-vocabulary logit dumps bitwise against the original reference and eight request output/layout checks. A first analysis used latest task-body end as a proxy. The final separate diagnostic observes the return ordinal of the existing release-order done.fetch_add, without adding a shared counter or changing claim/wait/math. Per-phase ordinals1..24 and task row coverage were checked against raw traces. The actual last publisher differs from latest-body-end task in106/67 decode phases; the final analysis uses ordinal24. Identity is exact from atomic modification order; publication time is bounded by body-end and post-release marker.

Two63-iteration decode windows contain10080 phases/241920 row tasks;16K prefill-tail adds80 phases/1920 tasks. Total10160 phases/243840 tasks. All phase fork/join and126 token wall ledgers close exactly. A pool task is a row partition of an ordered expert array, not a whole expert. Detailed CPU-result-upload/GPU-merge edge analysis covers decode; extra prefill-tail GPU edges were not fully analyzed. Legacy JSON field observed_last_body_who_counts actually counts final-ordinal publishers in this second-round analysis.

Observed decode token-wall totals:2111.583/2572.904ms. Critical-branch task-body ranges total872.866/845.246ms, but include preemption/instrumentation; host wait_done244.722/229.973ms overlaps running branches and must not be added again. Job traces have no CPU sampling/context switches. Trace/on-unprofiled decode ratios1.2206/1.1347 are substantial perturbation, n=1 per cell, not optimization gains or uninstrumented attribution.

GPU-half launch API returns before CPU pool starts, yet the first native_gu kernel starts after pool end in2514/2516 of2520 layers per window. The visible prior-GPU-end→kernel-start gaps total1092.506/1042.910ms, overlapping CPU pool by940.304/894.174ms. These overlapping diagnostics cannot be added to the wall ledger. Later GPU-predecessor completion does not mean continuous GPU work. Internal driver submission, kernel stacks and a unique uninstrumented system root cause are unresolved; no WDDM defect, flush benefit or recoverable latency is claimed.

## Evidence, verification and exclusions

Download [evidence.zip](evidence.zip), extract, then run `python verify_archive.py <extracted-directory>`. Its included file manifest verifies sanitized artifacts and repeats phase/token ledger checks. It does not reanalyze absent raw traces. The ZIP includes exact synthetic inputs, original raw-file manifest fingerprints, sanitized actual commands, request/output records, analysis source, instrumentation patch/header, phase/token CSVs, figures and engine/profiler/test logs. Top-level readable files duplicate selected archive artifacts. [Archive file hashes](archive-file-sha256.json).

Raw Nsight reports/SQLite, individual task exports, full float32 dumps and binaries remain local. Text paths are replaced with placeholders after measurement; hashes of raw and sanitized artifacts are separate. Historical summary publication flags retain their measurement-time state. Two job-builder preparation failures stopped before build/GPU capture and are retained locally; the first proxy round remains local as a snapshot, not final completion-order data. Original copy adapter deployment failure remains documented in the first report. No failed timing is silently replaced.

Profiler warnings are retained: control-process CUDA/NVTX warnings and missing Windows Performance Toolkit/merged ETL. Engine CPU/CUDA events and expected task ranges were checked; no full-system-stack claim follows. No new performance A/B, GPU experiment or service change was done for publication. Original binaries/source and earlier immutable evidence remain intact; daily service was restored after CPU capture at12:05:08 and after final job capture at13:32:02, with unchanged config.
