# Hybrid inference on a 16GB Windows GPU: copy validation, tradeoffs, and profiling limits

Draft prepared 2026-11-01; not newly posted. Measurements were made on an i7-12700, RTX 5060 Ti 16GB, 128GB DDR4 and Windows11. This is a research retrospective with bounded hardware evidence, not a standard benchmark or a new engine implementation.

## A measurable result from an existing copy implementation

I independently isolated the original author's copy-only change from Strata PR3905 onto baseline `46c152a1`. The model was Qwen3.6-35B-A3B UD-Q4_K_XL, with a 32K maximum context, chunk 2048, 63 frozen expert slots, 7 workers, MTP0, packed/MMQ and greedy sampling. The same candidate executable was tested with the copy flag off/on; the full PR’s other attention/KV/GDN and expert-compute side-stream changes were not evaluated.

Six complete 64-row full-vocabulary logit dumps were finite and bitwise identical at each input length. Generated outputs and layouts also passed. Five alternating fresh-process pairs per input, without a profiler and with identical separate warmup, gave:

| Actual prompt tokens | Median paired A/B prefill time | Median paired A/B prefill+decode time | Pairs favoring B for total |
| --- | ---: | ---: | ---: |
| 1025 | 1.3021 | 1.0825 | 5/5 |
| 16385 | 1.1915 | 1.1457 | 5/5 |

The total-time reductions are approximately 7.6%/12.7%. These totals cover 64 output tokens and exclude model loading/warmup; they do not establish HTTP latency, long-generation benefit or a default change. Decode-only results varied. The implementation belongs to xyehya; my contribution is the isolated Windows validation and analysis.

Two 16K mechanism traces conserved expert staging bytes while moving about 38.67GB from host-to-device traffic to a separate device-to-device stream. Further checks covered all 320 stages and their double-buffer/event generations. Stream priority metadata was observed, but priority benefit was not isolated from the copy/stream change.

Public evidence: [original report and individual pairs](https://github.com/Thymos2027/Strata/blob/7c0247c72d3e57df40e2dd8b9be415ec90046f98/bench/results/2026-10-30-qwen36-split-copy-windows/README.md), [dependency/CPU/job follow-up](https://github.com/Thymos2027/Strata/blob/b6a98dd96fee80f7e3166770c7b85a209d763573/bench/results/2026-10-30-qwen36-cpu-copy-job-followup/README.md), [upstream discussion](https://github.com/Niko1221/Strata/pull/3905#issuecomment-6518999609).

## Useful negative results

Separate tests of packed-copy memory policy and larger prompt chunks showed why a component-level win does not automatically improve the complete request. More resident experts can improve generation while hurting prefill; chunk 4096 helped the long-input total on this machine but hurt short-input totals and generation. Matching layouts also mattered when interpreting numerical differences.

A separate Flash-Next all/P-core/automatic-policy comparison completed 45 requests across 15 launches. It did not reproduce a stable selection error under its predefined criteria, so I did not implement a replacement calibrator. Lower accumulated CPU time was not treated as proof of lower energy use.

The [Qwen tradeoff report](https://github.com/Niko1221/Strata/pull/4577) was closed without merging; the maintainer [explained](https://github.com/Niko1221/Strata/pull/4577#issuecomment-6495838098) that community benchmark results were planned for a website. This is a publication history, not a claim that the site has launched or that an engine patch was accepted.

## What the profiling branch established

CPU leaf-IP samples separated worker epoch-wait loops from arithmetic. Task instrumentation then exposed phase fork/join structure and the return order of the existing completion atomic. The actual final completion publisher sometimes differed from the latest task-body end, so body timestamps alone were an insufficient proxy. Parallel waits and GPU/copy durations were not added as serial elapsed time.

On a separately accepted `870aedd9` baseline, instrumented traces repeatedly showed a GPU-half kernel starting after the CPU pool had finished, even though its launch API had returned earlier. A same-binary job-marking off/on comparison subsequently completed 16 requests and eight traces. With native markers off, median launch-API-exit to kernel-start intervals still ranged about 566–632 microseconds. Dense native markers were therefore not necessary for that observed delay under CUDA profiling.

Every such trace still used a CUDA profiler. I did not establish the same timing in an unprofiled model or diagnose a WDDM defect. Reported overhead and process/order variation remained substantial, including a slower off trace that was retained.

A short non-model WPR probe and offline review validated raw QPC against controller bounds and linked 97 unique target render-packet chains with no unmatched render keys and zero reported lost events. These are system packet events, not CUDA kernel boundaries. A model ETW comparison was designed but not run. This newer870/WPR addendum remains locally archived; it is not part of the already-published 46c evidence package.

## Deployment evidence also matters

A separate DeepSeek V4.1 Flash 2.25bpw Windows case reproduced commit-headroom pressure under automatic RAM-store budgeting. An explicit 64GB store permitted bounded functional/performance checks and a 30-minute continuous-request case, with limitations retained. The [focused issue and evidence](https://github.com/Niko1221/Strata/issues/4605) are public. This is a deployment-boundary report, not a universal default or quality claim.

A separate historical transfer problem was also documented: roughly 1.7GB/s after a kernel-replay/TDR event sequence, and 24.88GB/s with the same probe after reboot. The [Strata report](https://github.com/Niko1221/Strata/issues/4381) and [NVIDIA forum report](https://forums.developer.nvidia.com/t/rtx-5060-ti-windows-persistent-low-pcie-transfer-throughput-observed-after-kernel-replay-tdr-restored-after-reboot/387175) preserve that sequence. There is no repeatable TDR trigger or confirmed vendor root cause. This motivated before/after environment controls; reboot recovery is not an engine speedup.

## Where I stopped and what I learned

The validation/performance reports are deliverables even though the original system root cause remains unresolved. Extending every unknown into another collection round made the later branch too broad. I stopped automatic collection and did not turn an observation into a speculative flush, stream or waiting-policy patch.

A new experiment should state one concrete change or falsifiable hypothesis, how a positive or negative result changes the implementation decision, and its smallest matrix/budget/stop rules. Correctness identities, actual placement, paired unprofiled measurements, failures and attribution limits belong in the result. The goal is a reviewable decision, not an ever-growing trace archive.

Before publishing the newer addendum, its small result tables and analysis need a separate sanitized evidence index. Raw system ETL, large profiler databases, binaries and complete float32 dumps remain local; they may contain unrelated system information. No new driver bug, original kernel speedup, cross-backend support or complete-quality result is claimed here.
