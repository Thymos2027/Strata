### Area

[Other]

### Your question

Sharing a measured Windows troubleshooting case: after a TDR during Nsight Compute kernel replay of `strata-q36`, independent pinned host-to-device copies stayed around **1.7 GB/s**, including after unloading the model and restarting the daily Strata service. After a Windows reboot, the **same standalone diagnostic executable** measured **24.88 GB/s**. Driver version remained 610.88.

This is a diagnostic observation for users investigating sudden slowdowns, **not a confirmed Strata regression or a request to change engine defaults**. I would welcome guidance on whether this belongs in the troubleshooting documentation. No deterministic minimal trigger is available.

### Environment and versions

- Windows 11 Pro; current system reports build 26200 (historical build at the original failure has not been separately verified).
- RTX 5060 Ti 16 GB, PCIe x8; Intel i7-12700, 128 GB DDR4.
- NVIDIA driver 610.88 before and after recovery; native Windows CUDA 13.2 / sm_120 builds.
- Profiled workload: unchanged Strata revision `83e6b05cd7b97ee194f330f0247faa76deb73f1b`, `strata-q36`, Qwen3.6-35B-A3B UD-Q4_K_XL; fixed 64/256 expert slots, 32K configured context, MTP 0, 1,025-token input / 64-token output cap. This is a historical pinned build, not a test of current main.
- Separate daily service where the low startup probe was visible: engine 0.1.46, Qwen3.8-Flash-Next IQ3_S, 64K, INT8 KV, 32K KV resident, spec 4, P-core affinity, automatic expert cache.
- Nsight Compute CLI 2026.2.1.0, build 38283040; distribution archive version 2026.2.1.5.

### What happened / what was tried

All times below are UTC+8, 2026:

| Time | Observed evidence |
| --- | --- |
| Oct 22, 13:08 session | Daily engine 0.1.46 startup H2D probe: 25.0 GB/s |
| Oct 22, 13:26:01.397–13:26:04.757 | Windows System `nvlddmkm`, Event 153: `Resetting TDR`, `Reset TDR`, `Restarting TDR`, GPUID:100 |
| Oct 22, 13:26:06–07 | Nsight internal log: context-state transfer/restore failure, `LaunchFailed`, CUDA return 999 |
| Oct 22, 13:26:07 session | Same daily engine path/version/arguments: all four startup H2D bursts about 1.7 GB/s |
| Oct 24 | Restarting Strata restored missing GPU temperature/power telemetry, but startup H2D remained 1.7 GB/s |
| Oct 24, model unloaded | New independent CUDA process also measured low H2D/D2H and mapped-host reads |
| Oct 28, after user reboot | Exact same copy-test exe: H2D 24.88 GB/s; sampled current link generation under transfer load was Gen5 |

At failure, `ncu` reported backing up device memory in system memory and suggested application replay. Relevant internal errors included `Failed to launch memcmp kernel`, `Failed to compare memory (999)`, `Failed to optimize backing store`, `Failed to restore`, and `Profile end failed (LaunchFailed)`.

The recorded profiling invocation selected `k_attn_part`, `--launch-skip 760 --launch-count 1 --replay-mode kernel --cache-control all --clock-control none`, with LaunchStats, SpeedOfLight, MemoryWorkloadAnalysis, MemoryWorkloadAnalysis_Tables, SchedulerStats, WarpStateStats and Occupancy. A Python harness launched the native child engine. This documents the observed workload, not a validated minimal TDR reproducer.

### Results: independent diagnostic, no profiler or model loaded

Decimal GB/s; same executable, CUDA Event timing except CPU memcpy. For H2D/D2H, 64 MiB per copy, 8 warm-up copies and 128 timed copies. D2D uses 256 copies, reported as one-way payload bytes; mapped-host read uses 32 kernel launches over 64 MiB. Test exits were 0; built-in spot checks passed, not an exhaustive memory-integrity test.

| Test | Oct 24, degraded | Oct 28, after reboot |
| --- | ---: | ---: |
| Pinned H2D | 1.725655 | 24.881625 |
| Pinned D2H | 1.806933 | 28.369929 |
| GPU mapped-host read | 1.608412 | 16.651046 |
| D2D payload copy | 186.724392 | 190.355314 |
| CPU memcpy | 17.241300 | 17.964073 |

H2D wall-clock results agreed: 1.725581 vs 24.831195 GB/s. Diagnostic exe SHA-256: `712995e1d2d12b0806eb621edc2c653b59b45a106118de7c5bfac577bf4972a8`.

Before reboot, 40 NVML samples during the diagnostic reported current Gen1 x8, while Windows PnP CurrentLinkSpeed reported code 5. After reboot the transfer samples reported Gen5; idle P8 still showed Gen1 normally. **The physical negotiated speed in the degraded state was not independently verified from PCI configuration registers.** NVML RX also produced peaks above the measured copy payload rate, so a Monitor peak alone was not a recovery test.

### Validation and limits

- **Passed:** repeated low-throughput diagnostics with the model unloaded; host wall-clock cross-check; same executable recovered after reboot; under-load generation samples changed from Gen1 to Gen5.
- **Failed:** the original kernel-replay collection (`LaunchFailed` / TDR). No successful metrics are claimed from that collection.
- **Not run:** a deliberate second TDR; immediate controlled reboot A/B; driver-version A/B; raw root-port Link Status reads; post-reboot daily-model decode benchmark.
- The degraded and recovered standalone measurements are four days apart. There is one correlated event sequence, not proof of a specific driver/retraining bug or of Nsight Compute causing persistent link degradation. No driver, clock, power-plan, BIOS or TDR settings were changed during the diagnostic runs.

For a similar slowdown, checking an independent transfer test and the timestamped driver events helped avoid attributing everything to the model or engine version. This report does not recommend disabling TDR or forcing PCIe/clock settings.

Related but different: #485 concerns old startup-probe underestimation (maintainer reported a fix in 0.1.37); #2137 concerns misleading link-generation display and a Linux-specific driver option. Neither establishes the cause here.

NVIDIA Nsight Compute report (published): https://forums.developer.nvidia.com/t/rtx-5060-ti-windows-persistent-low-pcie-transfer-throughput-observed-after-kernel-replay-tdr-restored-after-reboot/387175 . The bounded standalone diagnostic source is included below so the measured paths can be reviewed. It diagnoses throughput; it does not trigger the original fault.


<details>
<summary>Standalone diagnostic source (CUDA 13.2, sm_120; same source used for both measurements)</summary>

Build in a configured MSVC/CUDA terminal: `nvcc -O2 -arch=sm_120 --cudart=static transfer_probe.cu -o transfer_probe.exe`.

```cuda
// Bounded diagnostic. No link, driver or clock settings are changed.
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#define CK(x) do {auto e=(x); if(e!=cudaSuccess){fprintf(stderr,"%s: %s\n",#x,cudaGetErrorString(e));exit(1);}}while(0)
using Clock=std::chrono::steady_clock;
constexpr size_t N=64ull<<20;
__global__ void read_mapped(const unsigned *p, unsigned *out, size_t n){
 unsigned s=0;for(size_t i=blockIdx.x*blockDim.x+threadIdx.x;i<n;i+=gridDim.x*blockDim.x)s+=p[i];
 out[blockIdx.x*blockDim.x+threadIdx.x]=s;
}
void measure(const char *name,void *dst,void *src,cudaMemcpyKind kind,int count){
 for(int i=0;i<8;++i) CK(cudaMemcpy(dst,src,N,kind));
 cudaEvent_t a,b;CK(cudaEventCreate(&a));CK(cudaEventCreate(&b));
 auto t=Clock::now();CK(cudaEventRecord(a));
 for(int i=0;i<count;++i)CK(cudaMemcpyAsync(dst,src,N,kind));
 CK(cudaEventRecord(b));CK(cudaEventSynchronize(b));float ms;CK(cudaEventElapsedTime(&ms,a,b));
 double wall=std::chrono::duration<double>(Clock::now()-t).count();
 printf("{\"test\":\"%s\",\"bytes_per_copy\":%llu,\"count\":%d,\"event_GBps\":%.6f,\"wall_GBps\":%.6f}\n",name,(unsigned long long)N,count,double(N)*count/(ms*1e6),double(N)*count/wall/1e9);fflush(stdout);
 CK(cudaEventDestroy(a));CK(cudaEventDestroy(b));
}
int main(){
 void *h,*d,*d2;CK(cudaMallocHost(&h,N));CK(cudaMalloc(&d,N));CK(cudaMalloc(&d2,N));memset(h,0x5a,N);
 measure("pinned_H2D",d,h,cudaMemcpyHostToDevice,128);
 unsigned v;CK(cudaMemcpy(&v,d,4,cudaMemcpyDeviceToHost));if(v!=0x5a5a5a5a)return 2;
 measure("pinned_D2H",h,d,cudaMemcpyDeviceToHost,128);
 if(*(unsigned*)h!=0x5a5a5a5a)return 3;
 measure("D2D_oneway_bytes",d2,d,cudaMemcpyDeviceToDevice,256);
 CK(cudaMemcpy(&v,d2,4,cudaMemcpyDeviceToHost));if(v!=0x5a5a5a5a)return 4;
 void *h2=malloc(N);if(!h2)return 5;
 auto t=Clock::now();for(int i=0;i<128;++i){memcpy(h2,h,N);*(volatile unsigned*)h2=i;}
 printf("{\"test\":\"CPU_memcpy\",\"GBps\":%.6f}\n",double(N)*128/std::chrono::duration<double>(Clock::now()-t).count()/1e9);
 void *mapped;CK(cudaHostGetDevicePointer(&mapped,h,0));
 read_mapped<<<256,256>>>((unsigned*)mapped,(unsigned*)d2,N/4);CK(cudaGetLastError());CK(cudaDeviceSynchronize());
 cudaEvent_t a,b;CK(cudaEventCreate(&a));CK(cudaEventCreate(&b));CK(cudaEventRecord(a));
 for(int i=0;i<32;++i)read_mapped<<<256,256>>>((unsigned*)mapped,(unsigned*)d2,N/4);
 CK(cudaGetLastError());CK(cudaEventRecord(b));CK(cudaEventSynchronize(b));float ms;CK(cudaEventElapsedTime(&ms,a,b));
 CK(cudaMemcpy(&v,d2,4,cudaMemcpyDeviceToHost));unsigned expected=0;for(size_t i=0;i<N/4;i+=65536)expected+=0x5a5a5a5au;
 if(v!=expected){fprintf(stderr,"mapped verification failed\n");return 6;}
 printf("{\"test\":\"mapped_GPU_read\",\"GBps\":%.6f,\"spot_checks_passed\":true}\n",double(N)*32/(ms*1e6));
 CK(cudaFree(d));CK(cudaFree(d2));CK(cudaFreeHost(h));free(h2);
}
```

</details>
