# 870aedd9 GPU迟启动复现与观察扰动

2026-10-31。后台于北京时间00:35:57完成并通过验收；用户返回后，126份静态证据及manifest指纹、GPU依赖明细和当前日常服务再次复核通过。**迟启动在新提交的四份插桩trace中重复出现；无profiler时是否同样发生，以及驱动/调度根因，仍未确定。** 本轮没有改默认或对外发布新材料。

## 固定条件和门槛

精确revision `870aedd9e1ebe1c91f94da93b59af17729f6c5c0`，engine0.1.54。Windows11，i7-12700、RTX5060Ti16GB、128GB DDR4，实测驱动610.88。原Qwen3.6-35B-A3B UD-Q4_K_XL，32K/chunk2048/显式63slots后冻结/7workers加host/MTP0/packed-MMQ/GPU0/EAGER/贪心。两个输入实际1025/16385token，各64输出；每条请求独立进程并做统一r1-l1024/64预热。

[执行前协议](completion-plan.md)、[后台流程](run_background.py)、[最终汇总](summary.json)。独立诊断源码在 `build-native-baseline/src-job-submit-870aedd9`，构建在 `build-job-submit-870aedd9-cuda132-sm120`。只移植NVTX token/MoE/pool/phase/job边界及原done原子返回完成序号，不改算术、任务claim、等待、原子内存序或stream策略。原870及46c基线不改。

CUDA13.2/sm_120构建、19项选定测试和Ninja无工作复查通过。四份实际新logits（两长度×诊断off/on，各64×248320 float32）全部有限且与870基线同一强制历史逐位相同；数值入口的MMQ、输出及63slots/chunk2048/零换槽通过。第二轮引用并重验这四份文件和同一诊断二进制，不称作八份新dump。

两轮16条正式观察、四份trace全部输出与新基线64-token参考一致，fresh/0草稿、63slots/chunk2048/0换槽、退出0。第1轮按1K→16K、baseline/off/on/trace；第2轮按16K→1K、trace/on/off/baseline倒序，保留全部数据。CPU sampling/context switch关闭。

## 新提交上的复现结果

按原生token/MoE标记、CUDA API correlation和设备时间核对GPU半边首kernel `native_gu_kernel`。每条trace含63次原生decode迭代、2520层MoE；首个输出由prefill产生，不计作第64次原生迭代。以下每层均核对该launch API已在CPU pool开始前返回。

| 轮次/输入 | 首kernel在pool结束后才启动的层数 | 比例 | API退出到GPU启动中位数，微秒 |
| --- | ---: | ---: | ---: |
| 第1轮1K | 2514 / 2520 | 99.76% | 620.229 |
| 第1轮16K | 2520 / 2520 | 100% | 682.453 |
| 第2轮1K | 2520 / 2520 | 100% | 588.238 |
| 第2轮16K | 2520 / 2520 | 100% | 651.686 |

回读逐层明细额外核对了严格大于pool结束时间，四条均无相等时间戳；没有把相等边界混入“结束后”。时间中位数来自每条trace的2520个相关kernel，不是未插桩引擎的延迟统计。

每条decode含5040 phase/120960行任务，两条16K各另有80个prefill尾部phase/1920任务。合计20320 phase、487680行任务的原子完成序号、唯一性与行覆盖通过，252个token和各phase的wall账本精确闭合。每trace中“最后原子完成发布者不同于最晚任务body结束”的decode phase数分别为83/71/66/68，共288个；最终使用原子完成序号，不使用最晚body代理。

## 采集与标记扰动

下表均为同轮独立进程decode耗时，单位ms；每长度每臂n=2，无性能优化臂。

| 轮次/输入 | 原baseline plain | 诊断off plain | 诊断on plain | 诊断on trace | on/off | trace/on |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 第1轮1K | 1787.2 | 1781.4 | 1805.0 | 2127.1 | 1.0132 | 1.1784 |
| 第1轮16K | 2408.1 | 2259.8 | 2301.3 | 2655.3 | 1.0184 | 1.1538 |
| 第2轮1K | 1719.1 | 1731.9 | 1760.9 | 1947.7 | 1.0167 | 1.1061 |
| 第2轮16K | 2307.8 | 2257.4 | 2294.8 | 2527.0 | 1.0166 | 1.1012 |

标记on/off的观测差为约1.3%–1.8%；trace/on差为约10.1%–17.8%。这些比例包含进程、顺序、环境与采集影响，不能直接当纯标记成本或纯profiler成本。两轮倒序帮助保留顺序变化，未消除所有混杂。原baseline plain没有pool边界；仅凭plain的合计耗时，不能判定未采集路径也存在相同迟启动。

prefill四臂原始ms及比值保留在summary中，未选择性丢弃；本轮没有将其作为新复制收益或跨版本对照。原46c五组无profiler数据保持独立。

## 时间分解的约束

以下是每条trace中63次原生迭代的累计观测量，单位ms。各列有重叠，**不能相加作为串行耗时或可回收延迟**。

| 轮次/输入 | token wall | GPU操作未覆盖 | 关键分支job body | 可见GPU前驱结束到首kernel启动间隙 | 该间隙与pool重叠 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 第1轮1K | 2126.330 | 1500.302 | 904.553 | 1107.474 | 956.008 |
| 第1轮16K | 2654.609 | 1506.325 | 871.005 | 1095.263 | 921.134 |
| 第2轮1K | 1947.118 | 1323.964 | 686.889 | 906.325 | 733.693 |
| 第2轮16K | 2526.253 | 1384.905 | 791.870 | 992.111 | 842.919 |

关键分支body是wall范围，可含抢占/诊断开销；host wait_done与worker执行重叠，不能再次累计。GPU未覆盖不等于CPU专家算术；GPU前驱完成较晚不等于设备一直在忙。原子序号确定最后发布者身份，但发布时刻仅界于body结束和发布后标记之间。额外prefill尾部也检查任务/phase，详细GPU依赖分析仍限decode。

本次还只读检查四份SQLite的 `CUPTI_ACTIVITY_KIND_KERNEL` 表结构，均无queued/submitted/completed列；已有数据无法补出内部驱动提交阶段时间。缺少完整系统栈和设备event完成时间时，不推测WDDM批处理、硬件抢占或某个flush改动必然有效。

## 证据、警告和恢复

- [第1轮详细路径](critical-path-01.json)、[第2轮详细路径](critical-path-02.json)。
- [第1轮phase账本](phase-ledger-01.csv)、[第2轮phase账本](phase-ledger-02.csv)、[第1轮token账本](token-ledger-01.csv)、[第2轮token账本](token-ledger-02.csv)。
- [第1轮图](timeline-01.png)、[第2轮图](timeline-02.png)按固定中间token/层位置选择，不以最快或最慢挑样。
- [诊断补丁](diagnostic-complete.patch)、[诊断头](job_trace.hpp)、[分析程序](analyze.py)、[来源与共享上下文](context.py)。

本机capture-01/capture-02保存原始Nsight/SQLite、每层CPU-GPU依赖、全部行任务、请求/输出和日志。126文件静态manifest指纹保存在summary中，background动态状态/stdout/stderr、README、summary和manifest自身排除；本次文档收尾不改封存清单。控制进程的NVTX/CUDA警告、WPT未安装而未生成merged ETL的警告全部保留；引擎CUDA、NVTX、任务和依赖核对通过，不能据此声称全系统栈已采全。

第1轮HtoD前24.881689/后24.995351GB/s，00:28:30恢复日常服务；第2轮24.885906/24.889249GB/s，00:35:15再次恢复。两轮配置SHA相同、restore_errors为空；最终验收00:35:57通过，回读时当前Flash-Next IQ3_S仍loaded=true、配置未改。未构建HIP/SYCL或验证动态换槽、并发、全量质量，未改默认，也未自动发布本轮材料。

## 下一步

先做[同一诊断二进制的标记off/on采集对照](observer-control-plan.md)，用两个采集臂均可观测的API→kernel启动延迟和GPU空隙比较，补齐本轮缺少的“关闭原生job标记但保留CUDA采集”一格。之后再决定是否需要系统/驱动提交观测。后续该对照已于10:50:59完成，[结果与系统观测下一步](../qwen36-observer-control-870aedd9/README.md)已收尾：关闭密集标记仍有同量级采集延迟，但尚无唯一全系统根因或优化收益。
