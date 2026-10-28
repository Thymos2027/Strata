# HtoD 恢复后的研究取舍

2026-10-28，北京时间。本轮为资料审查和选题，不含新构建、推理、profiling 或上游发布。

建议继续 Qwen3.6 长上下文主线，先交付当前主线上的独立候选验证，再据正常工况的关键路径决定是否写优化。无需下载新模型。

给首次阅读者：本页是[总计划](../../INFERENCE_RESEARCH_PLAN.md)在环境恢复后的接续安排；10-21 的 `INFERENCE_OPTIMIZATION.md` 是历史选题池。整体只有一条深入研究主线：复现长上下文变慢 → 找关键路径 → 验证已有 GQA 方案 → 有独立空间再做自己的优化。亲和性、缓存和诊断保留为备选，不要求同时开展。用户随后增加的[DeepSeek 社区使用案例](../deepseek41-community/README.md)是独立验证任务，先后台下载，不替换本页的内核研究主线，也不因下载完成而算作研究交付。

## 当前依据

- 本地 `upstream/main` 为 `5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d`，v0.2.7，仓库标示发布 engine 0.1.52。HEAD 包含该上游提交，审查开始时 tracked/untracked 工作区为空。源码版本、发布引擎和日常实际安装引擎必须分开记录。
- [重启后独立探针](../pcie-after-reboot/README.md) H2D=24.882 GB/s；[日常服务恢复](../daily-start-105651/README.md)启动探针约 24.9 GB/s。随后[日常引擎升级](../engine-upgrade/README.md)已切换到 0.1.52 并通过短 API/MTP/缓存/工具调用验收；这仍不代表完成当前源码性能基线。
- `git diff 7ddc17a3 upstream/main -- src/qwen35 include/strata/qwen35`：变化为采样逻辑提取与越界 history token 的 penalty 修复（#3911）；attention 实现没有变化。这是静态审查，不是新版本正确性或性能验证。
- GitHub 当次 API：[PR #3641](https://github.com/Niko1221/Strata/pull/3641) open、非 draft、head `f3f2136f`；[#3678](https://github.com/Niko1221/Strata/pull/3678) open、draft、head `8e7742e8`；base 均仍为 `011c9e6`。两者当前 `mergeable=true`，与 10-23 的快照不同，但不证明本机构建或运行兼容。#3641 返回的讨论列表为空。
- [#3700 后续评论](https://github.com/Niko1221/Strata/issues/3700#issuecomment-6379679338)已扩展到 int8 decode、opt-in Tensor Core attention、fused prompt attention 与 DeltaNet prompt pass，并提出与 #3641/#3678 分工。其 RTX 5080/Sage 数据是作者测量，不能作为本机 Qwen3.6 结果或维护者范围批准。
- [#2464 评论](https://github.com/Niko1221/Strata/issues/2464#issuecomment-6292626483)已有长上下文 MTP 收益变弱的分析；本机可做独立硬件验证，不能称为首次发现。
- [#3295](https://github.com/Niko1221/Strata/pull/3295)仍 open、未合并，处理显式 greedy 请求与模型卡 penalty；不要重复修复。当前本地 `spec` 判定仍含 `E.mtp_d > 0 && !smp.needs_logits() && !adm`，诊断不能只看 temperature。

查重范围：相关 PR 元数据、#3641 讨论列表、#2464/#3700 评论、针对 k_attn_part/GQA/MTP 的公开搜索，以及本地上游差异。未穷尽全部 PR、评论和分支；实现或发布前仍需专项查重。

## 优先顺序与可交付贡献

| 顺序 | 研究问题 | 最小实验 | 对项目的贡献与继续条件 |
| --- | --- | --- | --- |
| 1 | 现有 FP32 GQA 在 Windows/Blackwell hybrid 上是否正确且有端到端收益？ | 当前主线基线与保留作者归属的 #3641 集成候选；1K/16K，先 MTP 0、FP32 KV、固定专家布局；通过门禁后至少五组 AB/BA | 为 #3641/#2464 补独立验证报告。无收益也有价值，须解释 kernel 与端到端差异 |
| 2 | 正常 HtoD 下，attention、CPU 专家和 host 等待各占多少关键路径？ | 当前基线 1K/16K，先无 profiler，再 Systems decode 时间线及 CPU sampling/调度；Compute 分批补访存指标 | 形成最终瓶颈结论，决定后续独立改动范围；不能把 busy-wait 样本当作专家计算 |
| 3 | GQA 是否改变长上下文 MTP 的收益边界？ | 前两项稳定后，将相同 workload 扩为 GQA 0/1 × MTP 0/2；记录 offered/accepted、输出长度/哈希、验证成本 | 给出配置边界和回归 workload；先做测量，不自动调整默认 MTP 策略 |
| 4 | Flash-Next 的启动亲和性微基准是否选中端到端最快布局？ | attention 路线收益不足或完成后，固定实际缓存，比较 measure/all/P 核，覆盖代码、中英文与 prefill | 只有复现错选或稳定收益后才改校准；既有 `--pool-affinity measure` 不是新功能 |
| 5 | MTP 已配置却未执行，能否给出准确原因？ | 先查现有诊断，分别测未加载、greedy、temperature/penalty、其他引擎禁止条件 | 可形成较小的诊断/回归贡献；不能重做 #3295，采样参数诊断须依据引擎实际判定 |

多会话缓存留在后续：显式固定 0/4/8 GiB，测 A→B→A 的复用和保存/恢复成本。CUDA Graph 暂不作为主线：既有固定 64/256 专家配置实际关闭 Graph，不能拿历史组名推导 Graph 开销。

## 第一轮执行范围

1. 固定 `5e8a4cca`，在独立 worktree/输出目录建立 Windows 原生基线；记录工具链、模型和 exe 哈希。先运行适用的采样回归与既有 Q36 门禁，再做 1K/16K、MTP 0/2 的短输出复核。历史输出用于对照，不替代当前基线。
2. 在另一 worktree 将 #3641 集成到同一个当前基线，保留来源和完整合并差异；同时构建该候选。核对 `STRATA_Q36_GQA` 开关、FP32 默认路径、sampling 修复和实际专家布局。候选内部开关 A/B 隔离 GQA 机制，另用未经修改的 main 对照确认集成没有改变默认路径。
3. 先运行独立 attention oracle、真实模型 1K/16K 门禁。输出不同先做数值定位，不继续包装为等价加速。MTP/batch 扩展时增加相应门禁。
4. 通过后做无 profiler 的五组配对：1K/16K、256 输出、交替顺序、固定预热和 fresh-prefix。报告全部结果、配对差值、范围、TTFT、prefill、内存及实际布局。固定 slots 隔离机制后，再单独验证日常动态布局。
5. 先用 Systems 检查候选 kernel 与端到端关键路径；需要解释访存时，再分批采 Compute 的 L1/L2/DRAM、stall/occupancy。延续已跑通的 application replay 和小指标组；历史 kernel replay/TDR 记录见环境报告。冷缓存计数与 warmed 请求分开解释，采集前后留带宽控制。

现有 [run_ab.py](../../tobeo-20261023/qwen36-pr3641/run_ab.py)固定旧 revision、exe 哈希和报告目录，会卸载/恢复日常模型；不能原样当作 v0.2.7 实验。需先改成新日期目录与明确的 base/candidate provenance，再执行。旧 Compute 入口同样要审查日期目录、二进制和权限，不直接恢复全量 section 采集。

第一份对外产物应是有明确范围的 `[Benchmark]` 独立验证报告，准备好证据后再发布到相关讨论。若后续修改共享原生文件，按仓库规则验证受影响后端；缺少 HIP/SYCL 验证如实列为未运行，不把 CUDA 成功当作跨后端完成。

## 本轮完成与未完成

已完成：本地版本与差异审查、相关上游讨论复核、研究优先级与最小实验设计、总计划更新。

未完成：当前源码构建、任何新 GPU 测量、候选集成、完整瓶颈归因、性能 A/B、上游贡献发布。日常服务未切换。

## 日常引擎升级决策评估（2026-10-28）

本节保留升级前的决策依据。随后已按该方案完成升级并保留旧组件，实际结果见[升级与验收报告](../engine-upgrade/README.md)；以下将“未执行”视为当时状态，不覆盖历史决策过程。

实时核对 [latest release](https://github.com/Niko1221/Strata/releases/tag/v0.2.7)仍为 v0.2.7 / engine 0.1.52。本机运行进程实际来自 `D:\Models\Strata\components\engine\0.1.46-windows-x86_64-cuda-cuda13\strata.exe`；配置使用 `component:strata-engine`，因此组件升级后的下一次启动可以解析新引擎，不需手动改成固定 exe 路径。RTX 5060 Ti、驱动 610.88，满足文档 CUDA 13 包要求的 580+。本轮 NVML free 为 418 MiB，是瞬时观测。

升级的主要价值是纳入正式修复并与当前服务器版本靠拢。发布说明列有会话 KV 误复用、checkpoint OOM 退出、短 draft-vocabulary row 越界等修复；各修复有其引擎路径和触发条件，不能据此认定本机旧引擎已触发这些 bug。12GB 卡的 residency-biased routing 默认仅适用于 13 GiB 及以下独显，不适用于本机 16GB；其他硬件的提速不构成本机预期收益。

现有模型、pack、MTP 和 64K 上下文配置先保留。不要同时开启近似 prompt 读取、改变 KV 格式或重新调参，以便发现变化后可以归因。新引擎默认值和归约顺序可能不同，不承诺跨版本 token 完全一致。`STRATA_DEFAULTS=026` 仅回退 0.2.7 相对 0.2.6 的默认行为，不能替代真正回退到 engine 0.1.46。

实施建议：先存旧组件身份/哈希、配置、启动环境及正常 HtoD 下的短控制请求；停止占用 GPU 的日常模型后，用组件 updater 安装匹配的 Windows CUDA 13 包，核验签名/哈希并保留旧版本。官方 updater 有 test-start 和 `strata components rollback`，但轻量 test-start 不是当前 64K 配置的完整验收；须确认使用同一个 `D:\Models\Strata\components` 根与回退记录，不运行会额外改源码或配置的源安装批处理。

切换后验证真实 exe 路径/版本、HtoD、显存布局、短生成、连续多轮请求、工具调用、MTP offered/accepted，以及可承受长度的 fresh prefill 和 A→B→A 缓存恢复。显存余量和重复请求稳定性为重点；异常时保留日志并用实际旧组件回退。研究用源码基线和候选仍各自固定路径/哈希，日常升级不替代研究门禁。
