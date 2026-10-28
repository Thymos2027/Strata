I would appreciate help diagnosing a persistent host/GPU transfer slowdown observed after a profiling failure and Windows TDR. The question is about the state **after recovery**, rather than the known possibility that profiling can exceed the watchdog timeout.

Independent pinned H2D copies remained around **1.7 GB/s** in new processes, even with the model unloaded and after restarting the application. After a Windows reboot, the **same standalone executable** measured **24.88 GB/s**, with the same NVIDIA driver version. This is one observed event sequence, not a confirmed Nsight Compute or driver defect and not a deterministic minimal reproducer.

## Environment

- GPU: NVIDIA GeForce RTX 5060 Ti 16 GB, PCIe x8, sm_120.
- CPU/RAM: Intel i7-12700, 128 GB DDR4.
- Windows 11 Pro; current system reports build 26200. I have not independently verified the historical OS build at the original failure.
- NVIDIA driver 610.88 before/after recovery; diagnostic built with CUDA 13.2 and static cudart.
- Nsight Compute CLI 2026.2.1.0, build 38283040; archive package 2026.2.1.5.
- Profiled program: native Strata `strata-q36`, unchanged source revision `83e6b05cd7b97ee194f330f0247faa76deb73f1b`; Qwen3.6-35B-A3B UD-Q4_K_XL, fixed 64/256 experts in VRAM, configured context 32768, MTP 0, 1025-token input / 64-token output cap.
- A separate daily Flash-Next engine (0.1.46) exposed the degraded startup H2D probe. The later standalone tests below do not load either model.

## Observed sequence

All timestamps are UTC+8, 2026:

1. Oct 22, 13:08 session: daily engine startup probe measured 25.0 GB/s H2D.
2. Oct 22, 13:26:01.397, 13:26:04.238 and 13:26:04.757: Windows `nvlddmkm` Event 153 recorded `Resetting TDR`, `Reset TDR`, `Restarting TDR`, GPUID:100.
3. During this collection, ncu warned that device memory was being backed up in system memory. Its internal log included `Failed to launch memcmp kernel`, `Failed to compare memory (999)`, `Failed to optimize backing store`, `Failed to restore` and `Profile end failed (LaunchFailed)`. Context-state transfer/restore failed at 13:26:06; the profiler exited with CUDA return 999 at 13:26:07.
4. The next daily-engine session, starting at 13:26:07, measured about 1.7 GB/s in all four H2D probe bursts. Later model unloads and service restarts did not restore throughput. A service restart did restore previously missing NVML temperature/power readings.
5. Oct 24: with the model unloaded, a new independent CUDA diagnostic still measured the degraded transfer rates below.
6. Oct 28: the user rebooted Windows (boot time 07:50:02). Before restarting Strata, the exact same standalone diagnostic executable measured normal H2D throughput and sampled Gen5 under transfer load.

## Profiling configuration at the failure

The saved command for the actual failed collection selected:

```text
ncu --target-processes all --kernel-name-base function
    --kernel-name k_attn_part --launch-skip 760 --launch-count 1
    --replay-mode kernel --cache-control all --clock-control none
    --section LaunchStats --section SpeedOfLight
    --section MemoryWorkloadAnalysis --section MemoryWorkloadAnalysis_Tables
    --section SchedulerStats --section WarpStateStats --section Occupancy
    --export <output>
    python <capture_request.py> --case r0-l1024 --mtp 0 --cap 64
```

Line breaks are for readability and local paths are replaced. The Python workload harness launched the native child engine and issued a warm-up followed by the measured request. This command alone is **not** a self-contained TDR reproducer. The selected kernel shape was grid (5,16,1), block (256,1,1).

## Independent diagnostic results

Decimal GB/s. Same executable before/after reboot, no model loaded and no profiler. H2D/D2H: 64 MiB, 8 warm-up copies, 128 timed copies. D2D: 256 copies, one-way payload bytes. Mapped-host read: 32 kernel launches reading 64 MiB each. CUDA Events are used except for CPU memcpy. Exit codes were 0 and the built-in data spot checks passed; this is not an exhaustive integrity test.

| Path | Oct 24 degraded | Oct 28 after reboot |
| --- | ---: | ---: |
| Pinned H2D | 1.725655 | 24.881625 |
| Pinned D2H | 1.806933 | 28.369929 |
| GPU mapped-host read | 1.608412 | 16.651046 |
| D2D payload copy | 186.724392 | 190.355314 |
| CPU memcpy | 17.241300 | 17.964073 |

Host wall-clock H2D agreed with CUDA Events: 1.725581 vs 24.831195 GB/s. Executable SHA-256: `712995e1d2d12b0806eb621edc2c653b59b45a106118de7c5bfac577bf4972a8`.

During the degraded diagnostic, 40 NVML samples reported current Gen1 x8, while Windows PnP CurrentLinkSpeed reported code 5. NVML RX also showed peaks above measured payload throughput. After reboot the transfer samples reported Gen5; idle P8 Gen1 still occurs normally. I have **not** independently read PCI configuration-space Link Status registers, so I am not claiming a proven physical Gen1 downgrade.

## Limits and questions

- There is one correlated failure sequence. Before/after standalone tests are four days apart, not an immediate controlled reboot A/B.
- No driver version change was made during our diagnostics. No clock, power-plan, BIOS or TDR settings were changed. The user performed the reboot separately.
- The original TDR was not deliberately triggered again. Driver-version A/B, raw root-port register reads and post-reboot model decode benchmarks were not run.
- Is persistent low transfer throughput after TDR a known recovery-state issue on this configuration? What additional driver/tool diagnostics would distinguish an actual link downgrade from another transfer-path state problem if it happens again?

The Strata troubleshooting report includes the standalone CUDA diagnostic source and build command (expand the source section): https://github.com/Niko1221/Strata/issues/4381 . That source measures the resulting throughput; it does not trigger the original profiling fault.
