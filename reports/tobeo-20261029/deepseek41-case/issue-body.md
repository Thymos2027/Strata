### Area

[Engine]

### Desktop app, Terminal or source?

Source Python server with the official prebuilt dedicated DeepSeek engine. No local native-engine build or patch.

### What happened

On Windows with 128GB RAM, loading IST-DAS2.25bpw with automatic RAM-store sizing left effectively no system commit headroom. The store selected 101.3GB; Windows logged event 2004 and the host began failing allocations. The server had printed ready, but no functional request was sent. I explicitly terminated the test tree to recover the machine; **I did not capture a spontaneous engine-crash exit code**.

The original event at 2026-10-29 19:23:30 local time (11:23:30 UTC) recorded:

| Field | Bytes |
| --- | ---: |
| SystemCommitCharge | 145,636,839,424 |
| SystemCommitLimit | 145,729,966,080 |
| strata-dsv41.exe CommitCharge | 118,554,161,152 |

That event had only 93,126,656 bytes of available commit. A postflight read-only query shows pagefile **initial 4096MiB / maximum 8192MiB**, system-managed=false; after recovery its allocated-size snapshot was4096MiB. Later runs had a 141.435GB commit limit, whereas this failure event had 145.730GB. I am not assuming the pagefile stayed fixed at 4GB throughout. No OS/pagefile/driver settings were changed.

Could the dedicated DeepSeek auto-store budget or preflight check account for available Windows commit and subsequent allocation headroom, in addition to available physical RAM, or give a targeted diagnostic before reaching this state? This is a report of the observed boundary, not a proposed universal 64GB default or a confirmed failing source line.

### Smallest steps or command that reproduce it

These are the conditions of the one locally observed automatic-budget attempt, not a claim that every 128GB system fails:

1. Prepare the official ISTA-DAS IQ2_XS /2.25bpw pack and shipped 2.25 expert profile; all seven source files were size/SHA-256 verified.
2. Unload the normal Qwen model first. Start the source HTTP server with the dedicated release engine,8K context, six experts, text-only, GPU0, DSpark auto, and no explicit store budget/reserve. The native invocation recorded by the server was:

```text
strata-dsv41.exe --serve --pack <PACK_DIR> --max-context 8192 --eos 1
  --vision off --dspark auto --dspark-conf 0.65 --experts 6 --gpus 0
```

3. Observe startup allocation, Windows event 2004 and host allocation failures. The recorded store target was 101.3GB and the startup GPU free-memory line was 182MiB. I did not independently rerun the command in a native-only harness, and did not repeat the automatic-budget attempt after the resource-exhaustion event.

### Reproduction status

Observed locally once with the recorded automatic budget and event. No source-level root cause established. The process tree was deliberately terminated for recovery; no claim of 0xC0000409, deadlock, or a measured pagefile-size A/B.

### Strata version

- Dedicated native engine: official`0.1.52-windows-x86_64-cuda-cuda13`, BUILD commit`a42cc3d7df70`, CUDA13.0, sm86/89/120.
- Exe SHA-256:`e2f9fce53017dd8c2318e3a5ce969b4bd00b64589bdf32355e8d4d691962e610`.
- Source server checkout:`8857fb6c9a94c947f75e845b7e9abe74b97551c8` (not the native engine build commit).
- Signed feed, archive hash, package signature, per-file hashes and pack-info checked successfully.

### Graphics card, memory and system

RTX5060 Ti16GB (16311MiB), driver 610.88; i7-12700,128GB DDR4; Windows11 10.0.26200; NVMe model storage. Desktop/IDE/browser remained open; the normal Qwen model was unloaded before each DeepSeek attempt.

### Model, settings and independent workaround attempts

DeepSeek-V4.1-Flash-1017, ISTA-DASLab GSQ-RCO IQ2_XS / IST-DAS-2.25bpw;8K cap, Full quality (`--experts 6`), vision off, DSpark auto (actually not loaded). Plain setup.py ISTA pack recipe and shipped profile, no dense overrides.

| Attempt | Settings / outcome |
| --- | --- |
| Automatic |101.3GB store, default GPU reserve; Windows resource exhaustion before functional requests; manually terminated |
|80GB store |`--ssd-cache 80 --reserve-mib 1536`; functional checks and first1K/4K pair completed, then our controller actively stopped at 94% commit (132.953/141.435GB). **This is not a second observed OOM.** |
|64GB store |`--ssd-cache 64 --reserve-mib 1536`; new functional gates,1K/4K each three times, and 36 requests over 1844.141s all completed; daily Qwen restored |

The64GB successful-run sampled system commit peak was 118.529GB. Its short-matrix decode medians were 7.1/7.2tok/s; first-content medians 9.7/19.3s. Some late continuous requests slowed down. Default-to-success changed both store and reserve; this is not a single-variable causal comparison or an optimal-budget claim.

### Logs and complete evidence

```text
ds4: RAM store: 113.3 GB of RAM free after the GPU's weights: store sized 101.3 GB, not 106.4
ds4: RAM store: up to 8899 slots of 11.4 MB (101.3 GB), policy 0, 8 reader threads, unbuffered reads
...
fatal   : Memory allocation failure
```

A host command helper also reported:`Failed to load advapi32.dll: The paging file is too small for this operation to complete.`

Fixed-commit evidence: [English report and configuration](https://github.com/Thymos2027/Strata/blob/72ff3a298043fab23ec430db87380101d058b680/bench/results/2026-10-29-community-rtx5060ti-deepseek41-windows/README.md), [event 2004 fields](https://github.com/Thymos2027/Strata/blob/72ff3a298043fab23ec430db87380101d058b680/bench/results/2026-10-29-community-rtx5060ti-deepseek41-windows/failure-event-2004.json), [automatic native log](https://github.com/Thymos2027/Strata/blob/72ff3a298043fab23ec430db87380101d058b680/bench/results/2026-10-29-community-rtx5060ti-deepseek41-windows/logs/automatic-engine.log), [all recorded args](https://github.com/Thymos2027/Strata/blob/72ff3a298043fab23ec430db87380101d058b680/bench/results/2026-10-29-community-rtx5060ti-deepseek41-windows/configurations.json), [HTTP requests and events](https://github.com/Thymos2027/Strata/blob/72ff3a298043fab23ec430db87380101d058b680/bench/results/2026-10-29-community-rtx5060ti-deepseek41-windows/http-requests.jsonl). The evidence directory also contains per-request statistics,0.5s resource samples, source archives, failures, drift and an offline validator.

Passed: file/package integrity and pack-info; the independent64GB configuration's functional requests, six timing requests and 30m44s continuous run; restoration and offline HTTP/native-log consistency checks.

Failed/stopped: automatic attempt had the event and allocation failures;80GB attempt was guard-stopped. Neither is pooled into successful timings.

Not run: pagefile-size A/B, fixed-clock/thermal tests, source fix, actual8K input, concurrency, vision, forced DSpark, other OS/backends or overnight testing. Native log/preload GB values are engine estimates. The report documents two mutable-list aggregate-input artifacts; published actual inputs come from the independently saved per-request files. Preparation and analysis were assisted by Codex; the measurements and Windows event are locally recorded.

### Related discussion

[#1607](https://github.com/Niko1221/Strata/issues/1607) concerns earlier Qwen conversation/checkpoint commit admission; this report concerns the separate DeepSeek loading/store path and does not claim the same failing allocation. Its closure note allows a linked new issue with current evidence. [#4362](https://github.com/Niko1221/Strata/pull/4362) addresses a different, greater-than-16K UMA context deduction; this 8K run is not a validation or counterexample of that PR.
