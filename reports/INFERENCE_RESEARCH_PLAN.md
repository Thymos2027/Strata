# Strata 推理优化与 Profiling 实践计划

制定日期：2026-10-21。用途：指导本机实验、开源贡献和求职作品准备。

设备依据已有记录：i7-12700、RTX 5060 Ti 16GB、128GB DDR4、Windows 11。主线使用现有 Qwen3.6-35B-A3B UD-Q4_K_XL，Flash-Next IQ3_S 用作混合调度研究的另一条路径。本计划不要求重新下载模型。

这是一份研究计划，不是性能报告。下面的时间是工作安排建议，验收条件是完成标准；没有承诺加速幅度或 PR 合并。2026-10-29实验固定 `46c152a1310f77cd2f0ce2c7cd213962df14fe83`，源码引擎0.1.53；该基线与旧 `5e8a4cca` 的测量继续独立保留。2026-10-30晚间按用户指定已更新项目至upstream `870aedd9e1ebe1c91f94da93b59af17729f6c5c0`（app0.2.8/engine0.1.54），下阶段在此新提交上独立构建、重新过门槛。源码更新不等于新引擎已构建/验收；日常服务仍沿用原0.1.52。

## 当前执行入口（2026-10-30，优先于下文历史安排）

2026-10-30晚间最新：[CPU/复制机制/job补充发布及源码更新](tobeo-20261030/qwen36-pr3905-followup/README.md)已完成。18:00:16在[#3905新增跟进评论](https://github.com/Niko1221/Strata/pull/3905#issuecomment-6518999609)，固定证据commit b6a98dd9的9文件线上身份核对、68文件ZIP离线验收通过。随后按指定fetch并合并870aedd9到本地main，合并commit e1691cc8，另建精确870aedd9独立worktree；原46c基线及94/52/161文件旧证据保持。日常服务/配置未变。**近期下一项：先完成870aedd9的独立CUDA构建、数值/输出/布局与无profiler重复性门槛，再调查GPU已提交后的迟启动残差。** 本轮没有构建新引擎或进行新GPU测量，不沿用46c验收作为新提交通过。以下下午/午间段落是阶段历史，发布和源码状态以本段为准。

2026-10-30下午最新：[job级依赖与关键路径报告](tobeo-20261030/qwen36-job-path/README.md)已正式收尾，后台验收及161份静态证据复核通过。保持46c152a1和原配置，两个63迭代路径、10160个phase/243840个行任务的完成序号、覆盖及phase/token账本通过；173个phase的最后发布者不同于最晚body，已按原子序号确定。trace使1K/16K decode较诊断on无profiler约慢22.1%/13.5%，故完成的是受控观测路径，原版无扰动的全系统根因仍未确认。下一项应收窄到已提交GPU分支的迟启动/执行提交残差，先立单因素诊断协议，不直接修改等待策略或恢复GQA。13:32:02已恢复日常服务、配置SHA相同，新材料未外发。以下早间/午间段落保留历史状态；当前完成范围以本段与正式报告为准。

2026-10-30午间最新：[CPU IP/调度与PR3905机制补充](tobeo-20261030/qwen36-cpu-mechanism/README.md)已完成本机受控采集及离线归因，继续固定46c152a1/原Q4/63slots/chunk2048/7workers/MTP0/packed。管理员会话预检取得真实周期样本和调度事件；baseline的1K/16K及原复制切片on/16K各一条无profiler参考与一份CPU/CUDA/NVTX trace，共六条测量全部输出/布局一致。三个decode窗口周期样本9448/12093/11867，引擎image内IP均解析、七worker及提交主线程可定位；基线16K等待循环52.63%、算术/量化20.09%、内核态未解析13.45%（分母含注入线程，不是延迟）。2430个算术样本均在GPU空隙中；原复制trace另核对320次staging逐步字节守恒、event跨代依赖及实际stream优先级0/0/-5。HtoD前24.862111/后24.942329GB/s，12:05:08恢复原日常服务、配置SHA相同。本轮没有改引擎、默认、已发布计时或外发新材料；完整job级关键路径、内核态符号与全栈仍未完成，不能按样本比例改等待策略。采样权限障碍已解除，下文此前“待采样权限”为历史状态。

2026-10-30新进展：[正常工况CUDA/NVTX采集](tobeo-20261030/qwen36-systems/README.md)已完成4条同日无profiler参考与4份trace、输出/布局/范围完整性验收及服务恢复；固定46c152a1，HtoD前24.843725/后24.890607GB/s。16K prefill的HtoD记录在chunk2048/4096下约157.13/78.57GB且大量与kernel重叠；16K decode的k_attn_part约占窗口21%–22%，另有1.36–1.49秒GPU未覆盖。CPU采样权限预检失败，完整CPU/关键路径归因仍未完成，不能将空隙称为CPU专家时间。

2026-10-30早间收尾：[PR3905原复制提交独立切片验证](tobeo-20261030/qwen36-copy3905/README.md)已完成。查重发现xyehya已有实现，仅移植af08278c复制hunk并适配CLI；固定46c152a1、63slots/chunk2048，同一候选exe仅切换 `--split-stage-copy`。17项选定测试、六份完整logits逐位一致、4条自由生成门禁及20条正式请求通过；1K/16K各五对prefill与合计均5/5变快，合计A/B耗时比中位数1.0825/1.1457。两条16K机制trace确认HtoD约157.13→118.46GB，约38.67GB转为独立stream DtoD，专家staging总字节相同。08:24:20恢复原日常服务、配置SHA相同。保留首次数值入口DLL部署失败，未使用其性能数据；不改默认、不另提重复实现；后续已按授权[发布原PR评论与脱敏证据](tobeo-20261030/qwen36-copy3905/PUBLICATION.md)，完整CPU归因仍待采样权限，GQA仍须另立范围。

三项最小验证（#4347、#4335、Flash-Next all/P/measure）和 DeepSeek Windows 单卡使用案例均已收尾；DeepSeek 问题与证据已发布，见[案例发布记录](tobeo-20261029/deepseek41-case/PUBLICATION.md)。这些结果不等于完整质量、跨后端或原创内核优化完成。

2026-10-29已[固定并验收可复现的 Qwen3.6 源码基线](tobeo-20261029/qwen36-repro-baseline/README.md)：新提交独立构建、模型/依赖/二进制指纹、17项选定测试、四臂门禁及两次独立进程1K/16K重复性通过，日常服务已恢复。该次基线阶段没有启动profiling；10-30已另行完成上述CUDA/NVTX部分，chunk2048与显式4096分开记录，packed政策相同、实际槽位63/50。没有组合#4335/#4347或开发新内核。

DeepSeek 仅保留有边界的问题跟进：[Engram direct 小对照](tobeo-20261029/deepseek41-case/edt-xx-check/README.md)未通过输出身份门槛，尚无 commit 回收或自动预算修复结论。若以后继续，先区分默认路径重复性与读取字节问题，不恢复性能矩阵或重跑长测。以下日期段落保留当时安排；当前进度以本节、实际报告及第11节清单的新记录为准。

## 1. 目标与取舍

选型解释（2026-10-28 补充）：最初的[选题池](tobeo-20261021/INFERENCE_OPTIMIZATION.md)优先考虑 Flash-Next 的亲和性和会话缓存，并非未考虑该模型。总计划选择 Qwen3.6 作为深入 CUDA 主线，是因为上游已有明确的长上下文问题与可定位的 attention 路径、现有 Q4 模型和门禁可用；后续本机时间线又支持继续调查。Flash-Next 已获得固定缓存的 P 核收益证据，但校准功能和缓存机制本来就存在，是否需要新改动仍须证明。此为研究问题与实验范围的选择，不是模型能力或用户价值排名。若优先服务日常 Flash-Next 体验，或 Q36 候选无收益/与上游重叠过大，可转向 Flash-Next。

主项目（2026-10-29 接续）：**定位 Qwen3.6 在16GB hybrid正常工况的端到端瓶颈，以新源码基线和时间线决定下一项最小改动。** #4347/#4335 的独立验证已完成并保留取舍结论；Flash-Next 现有布局验证没有复现稳定错选，不编写新校准器。选题依据见[模型与选题复评](tobeo-20261028/topic-reassessment/README.md)。

近期交付：**源码基线、正常工况CUDA/NVTX、已有复制方案验证及原线程发布、CPU IP/调度、逐stage复制依赖，以及受控job级依赖与wall账本均已完成。** 补充材料已发布至原PR3905；无插桩全系统根因和最小改动选择仍待。项目已更新870aedd9，下一项先重建并过基线门槛，再聚焦GPU已提交后的迟启动残差；GQA与MTP不自动进入。

2026-10-29阶段收尾：#4347、#4335及Flash-Next现有布局三项最小验证已完成，Qwen3.6已发布#4577，亲和性按用户选择仅补[#1912评论](https://github.com/Niko1221/Strata/pull/1912#issuecomment-6494468322)、不另提PR。DeepSeek 单卡案例亦已完成文件/引擎校验、功能、1K/4K各三次及30分44秒连续请求，并发布问题与脱敏证据。没有稳定亲和性错选证据，不编写校准器；没有新的正常工况 profiling 结论，不直接恢复 GQA。具体进入/停止条件见[复评收尾更新](tobeo-20261028/topic-reassessment/README.md)。

主项目应形成完整证据：可复现 workload → 时间线 → 瓶颈假设 → 单一改动 → 正确性验证 → 端到端收益与限制。小贡献用于熟悉构建、测试和审阅流程。不要同时开展多个引擎大改。

| 优先级 | 方向 | 适合展示的能力 | 何时进入 |
| --- | --- | --- | --- |
| P0 | Qwen3.6正常工况归因与prefill流式复制取舍 | GPU/传输重叠、CPU/GPU关键路径、布局与延迟归因 | 基线、复制验证/发布、CPU IP与受控job路径已完成；新补充已发布；870aedd9新基线验收后进入GPU迟启动残差单因素诊断；无插桩全系统根因仍待 |
| 已收尾 | #4347/#4335独立验证、Flash-Next现有亲和性验证 | 显存/延迟取舍、混合核调度、实验设计 | 保留已发布结果；没有新问题或证据时不扩展矩阵、改校准器 |
| P2 | Qwen3.6现有FP32 GQA验证 | CUDA、访存、GQA、数值验证 | 布局调整后attention仍有显著关键路径贡献 |
| P3 | MTP状态诊断、多会话缓存 | 服务可观测性、状态管理、延迟/内存取舍 | 先缩小独立范围并确认与现有PR不重叠 |
| P4 | Flash-Next CUDA Graph与执行空隙 | CPU/GPU时间线、执行重叠 | trace证明本机有值得优化的空隙后 |

### 历史：2026-10-23 上游同步后的执行约束

- 当前主线是 `7ddc17a3` / v0.2.3.1。相对本机原 `9de04cd4` 基线，Qwen3.6 的 `q36_engine.cu` 只有一处 CUDA 12.0/12.1 兼容性修复；这没有推翻既有 attention 假设，但旧构建只能作为历史证据。新的性能结论必须先建立当前主线的源码基线。
- [PR #3641](https://github.com/Niko1221/Strata/pull/3641) 仍 open、非 draft，固定 head `f3f2136f`，base `011c9e6`；[PR #3678](https://github.com/Niko1221/Strata/pull/3678) 仍 open、draft，base 同为 `011c9e6`。2026-10-23 GitHub API 对两者均返回当前不可直接合并；[#3700](https://github.com/Niko1221/Strata/issues/3700) 仍 open。旧 head 的验证可以保留为历史兼容性证据，但不能直接作为 v0.2.3.1 的候选性能结论。
- v0.2.3 在未显式设置时会根据模型加载后的空闲 RAM 自动分配 conversation cache；`--conversation-cache-mib 0` 才明确关闭。所有缓存 A/B 必须显式固定 0、4 GiB、8 GiB 等预算，并记录引擎最终日志，不能再把“未传参数”解释为关闭。
- v0.2.3 调整了 Work profile 的 CPU worker、显存余量和内存默认值，并新增 Flash-Next 专用、默认关闭的 DFlash2。跨版本或跨 profile 比较必须显式固定 worker、专家布局、缓存、MTP/drafting、上下文和采样；DFlash2 不是 Qwen3.6 attention 方案。
- 标准 benchmark 协议仍标记为 draft。当前 Qwen3.6 专项 workload 继续称为本机实验，不冒充标准 benchmark。

### 历史：2026-10-28 恢复后的执行入口

以下更新优先于文中仍保留的 10-23 续跑建议；历史数据和版本不改写。完整依据与实验设计见[恢复后的研究取舍](tobeo-20261028/research-next-steps/README.md)。

- HtoD 已恢复约 25 GB/s，正常性能测量的环境阻塞解除；每轮仍须同日确认带宽、资源工况和实际引擎。
- 新基线目标改为 `5e8a4cca` / v0.2.7，不再补过时的 v0.2.3.1 基线。`7ddc17a3` 至当前主线的 Q36 改动是 sampling 提取与 history token 越界修复；attention 未变属静态审查，不能代替重新构建与门禁。
- #3641/#3678 当前仍 open，固定 head/base 未更新，但本次 API 均返回 `mergeable=true`；旧“不可直接合并”只保留为历史快照。先集成到当前主线并验证，不再把等待作者 rebase 当作唯一前提。
- #3700 的[新评论](https://github.com/Niko1221/Strata/issues/3700#issuecomment-6379679338)已覆盖 int8 decode、Tensor Core 与 fused prompt attention，暂不另起重叠实现。优先补 #3641 的 Windows/Blackwell、真实 Q4、16K 独立正确性与性能证据。
- 执行顺序：当前源码基线 → 当前主线候选集成与 1K/16K 门禁 → MTP 0 五组无 profiler 配对 → 正常工况关键路径与访存归因 → GQA × MTP 0/2 收益边界。最终瓶颈与独立改动范围仍待测量决定。
- 旧 `run_ab.py` 与 Compute 入口固定历史路径/二进制，先改造 provenance、日期目录和控制参数再运行。本轮仅完成评估，没有切换日常服务、运行 GPU 实验或发布上游消息。

## 2. 已有证据与不能混用的结论

### 历史：2026-10-28 再评估后的执行顺序

本节记录三项验证前的安排及首轮停止状态，已由页首当前执行入口和第11节后续完成记录接替；不再按下列“尚未开展”继续执行。

执行后更新：[当前源码基线与#4347首轮](tobeo-20261028/qwen36-pr4347/README.md)已完成构建、所选基线门禁和数值诊断；首组256token输出身份检查未通过，因此剩余四组性能配对按预设停止。下一步先明确允许专家布局变化的数值/任务验收，不能继续把该政策当作整条生成bitwise不变的变化；#4335及其他模型实验尚未开展。

在10-28当时，本节优先于同日早先接续建议以及阶段D的旧排序。当时执行`git fetch upstream main --no-tags`，上游仍为`5e8a4cca`；源码没有新变化，扩大查重后发现直接针对hybrid路径的 #4335/#4347，以及校准、MTP和缓存方向的新重叠，见[复评报告与查询快照](tobeo-20261028/topic-reassessment/README.md)。

1. 先建立当前Windows原生源码基线，验证 #4347 的packed副本/专家槽位取舍。补丁要求`slots <= 0 && vram_gib < 0`；历史固定64 slots、显式10GiB专家预算会绕过规则，不能用于该政策验收。采用自动布局，固定其他参数并记录实际槽位。
2. 再单独验证 #4335 的prompt chunk规则及2048/4096取舍，分别检查prefill、TTFT、decode、显存和数值；两项各自可信后才考虑组合。
3. P0形成明确结果后，进入Flash-Next all/P核/measure端到端验证。现有measure有意在10%以内偏向P核，不能把它直接称为选错；若确认选择造成稳定实际损失，再商定一个校准改动。避开 #3522 已处理的PCIe/draft确认噪声。
4. GQA保留为条件性后续，不另写已有KV量化、Tensor Core或fused attention。MTP诊断与宽泛缓存重写暂缓；DeepSeek仍为独立使用案例。

本轮仅做源码/讨论复核和计划调整，未构建、移植、运行新测量或向上游发送消息。阶段A/B/C历史勾选不能代表新候选验证完成。

先阅读现有材料，保留历史记录，不覆盖原始结果：

- [本机综合记录](tobeo-20261021/REPORT.md)。
- [原选题调研](tobeo-20261021/INFERENCE_OPTIMIZATION.md)。
- [Qwen3.6 Q4 实验](tobeo-20261021/qwen36-q4/README.md)。
- [Flash-Next 实验索引](tobeo-20261021/flash-next/README.md)。

现有 Qwen3.6 记录有三点需要带入新实验：

1. 默认 HTTP 条件下，虽然配置 `--mtp 2`，日志仍显示 `drafts accepted 0 of 0`。服务解析出的 penalty 等条件会影响投机路径，不能只看启动参数。
2. 原始协议纯贪婪实验观察到 MTP 吞吐改善，但全部六个输出对的 token 哈希不同。尚未定位原因，不能称为输出一致或质量等价的加速。
3. Agent 基准中后续回合没有复用 prompt token。它是待解释的现象，不能直接宣布缓存实现有 bug。

Flash-Next 已有固定实际缓存后的 P 核收益记录。该记录支持继续研究调度，但不能写成尚未实现的自动校准器带来的收益。

两种模型走不同引擎路径。不要直接照搬 Flash-Next 的亲和性、KV、PCIe 或草稿参数到 Qwen3.6；需要分别核对解析器、日志和实际行为。

## 3. 阶段 A：建立可信的构建与测量环境

完成记录：[WSL 基线（2026-10-21）](tobeo-20261021/qwen36-source-baseline/README.md)、[Windows 原生基线（2026-10-22）](tobeo-20261022/windows-native-baseline/README.md)。后续本机优化以 Windows 原生构建为参考，WSL 结果独立保存。已确认原生源码构建、选定测试及固定布局下四臂一致性；具体范围和未测项以两份报告为准。阶段 C 已更正 Graph 覆盖范围：64/256 专家槽位触发 hybrid 并自动关闭主模型/MTP Graph，不能把历史组名当作真实 Graph 执行证据。

上述两份基线固定的是旧 revision，完成状态只说明当时的构建链路可信。`5e8a4cca` 基线已于10-28完成，见[#4347报告](tobeo-20261028/qwen36-pr4347/README.md)；本轮改为固定 `46c152a1`，独立构建并验收，见[新基线协议](tobeo-20261029/qwen36-repro-baseline/experiment-plan.md)。不要覆盖旧目录，也不要用“Qwen3.6 核心改动很少”替代构建和门禁。

建议用时：1–2 天。环境问题未解决时，不急于修改内核。

### 需要完成

- 记录当前 Git revision、工作区改动、发布引擎版本、驱动、模型文件与 SHA-256。已有报告的版本不能当作新实验版本。
- 在独立分支或 worktree 开展实验，保留当前报告和用户修改；单独设置构建输出目录。
- 检查 CUDA Toolkit、MSVC、CMake、Nsight Systems、Nsight Compute 的实际安装位置。本轮 PATH 未找到部分工具，不代表整机未安装。
- 依据仓库构建说明编译未经修改的源码。确认它能加载现有模型并完成基本生成。
- 区分发布二进制、源码基线二进制和候选二进制。性能 A/B 优先比较同一工具链构建的源码基线与候选。
- 确认 GPU 上没有两个模型争抢显存。开始需要切换模型的实验前，安排服务切换窗口；不要将其他任务负载混入测量。

### 基线正确性

阅读并运行适用的现有门禁，先查看脚本参数，不照猜命令：

- `tools/qwen35/q36_solo_gate.py`、`q36_cmp_gate.py`：solo token 对照。
- `tools/qwen35/q36_batch_gate.py`、`q36_proto_edge.py`：涉及 batch、取消、上下文边界时使用。
- `tools/qwen35/q36_harness.py`：理解引擎协议和已有测试组织方式。
- [Qwen3.6 文档](../docs/QWEN36.md)：已有实现、验证方法及限制。

验收：源码基线可运行；能说明运行的是哪个 exe、哪些参数和哪个模型；相关基线门禁有真实结果。失败项先记录、定位，不能默认为新补丁问题或直接忽略。

## 4. 阶段 B：复现长上下文曲线

完成记录：[Windows 原生上下文曲线（2026-10-22）](tobeo-20261022/qwen36-context-curve/README.md)。固定 32K 配置上限、512 prompt chunk、64 专家槽位，完成 1K/4K/8K/16K × MTP 0/2 × 3 次的 24 条测量；12 对输入及输出 token 哈希一致。已生成 ms/token、协议 TTFT 与配对 MTP 加速比曲线，保存资源样本。7 个 worker 的亲和性一致，其他线程由 OS 调度；单一合成 workload 的结果不能替代阶段 C 的 kernel 归因。24K/32K 输入与并发扩展未做。

建议用时：2–3 天。此阶段不修改计算逻辑。

### 最小实验矩阵

| 维度 | 第一轮范围 | 控制要求 |
| --- | --- | --- |
| 模型 | Qwen3.6 UD-Q4_K_XL | 同一文件与哈希 |
| 实际 prompt 长度 | 约 1K、4K、8K、16K token | 记录实际 token 数；使用公开、可重建的代码和文本 |
| 配置最大上下文 | 固定一个可容纳所有请求的值 | 不随 prompt 长度一起变化 |
| 输出 | 最多 256 token | 记录实际长度、提前结束和失败 |
| MTP | 先 0，再 2 | 采样条件一致，并核对 offered/accepted |
| batch | 第一轮保持单请求 | 后续再扩展并发 |
| 重复 | 每格至少 3 次 | 固定预热方法，保留每次结果 |

显存允许且前面结果稳定后，再增加 24K/32K 输入。扩展长度前核对输入加输出能否容纳，不为凑齐矩阵而触发 OOM。

纯贪婪诊断臂显式设置 temperature=0、presence_penalty=0、frequency_penalty=0、repetition_penalty=1。它是用于隔离机制的实验条件，不替代模型卡推荐采样的质量评测。若直接使用引擎协议，也应保存最终解析的配置。

### 必须采集

- prompt token、reused token、新读取 token、输出 token、输出 token 哈希。
- 引擎 prompt/decode 时间及吞吐；客户端 TTFT、总延迟。
- MTP offered/accepted；实际 prompt chunk、CPU worker 数、专家驻留数量。
- RAM/VRAM 的实际使用与峰值；出现分页、OOM、取消或提前结束时保留记录。
- 构建、配置、workload ID、预热方法、运行顺序和是否挂 profiler。

固定采样规则、CPU 布局、最大上下文、prompt chunk 和实际专家布局；动态专家缓存可能随 workload 改变，需要记录预热和状态重置方法。fresh prompt 测试核对 reused=0，不能把专家缓存预热与前缀复用混为一件事。

验收：得到 decode 每 token 耗时随实际上下文长度变化的图，并能解释测量边界。此时只陈述本机现象，不把 V100 或 L4 的结论直接移植到 5060 Ti。

## 5. 阶段 C：Profiling 与决定是否动内核

2026-10-30新增：[新基线正常工况CUDA/NVTX报告](tobeo-20261030/qwen36-systems/README.md)已完成四格采集和同日输出对照，阶段观察见[一页记录](tobeo-20261030/qwen36-systems/bottleneck-notes.md)。prefill流式复制与decode attention分别调查；CPU采样权限不足，完整CPU/关键路径归因及Compute计数仍待完成，以下旧trace不能替代新条件。

2026-10-22 进展：[Nsight Systems 报告](tobeo-20261022/qwen36-profiling/README.md)与[瓶颈观察](tobeo-20261022/qwen36-profiling/bottleneck-notes.md)。已完成原生 1K/16K × MTP 0/2 四组完整进程采集，分析仅筛选预热后 decode；每条输出 64 token，与阶段 B 对应前缀一致。16K 的 k_attn_part 区间占所选窗口约 22.05%/34.45%，支持下一步 Compute 检查；CPU 时间线和访存根因未测，尚未决定最终内核改动。旧工具兼容试采和触发截短试采均独立保留，未混入结论。

2026-10-23 进展：[Compute 1K/16K 三指标](tobeo-20261023/qwen36-compute/README.md)均通过，代理管理员权限与实际计数探针也已验证。新增[1K CPU IP/调度试采及环境诊断](tobeo-20261023/qwen36-profiling/README.md)：同日无 profiler 的 prefill 也明显慢，独立 HtoD 约 1.73 GB/s，历史引擎探针约 25 GB/s；NVML 与 PnP 链路报告有冲突。环境恢复前暂缓正常条件的性能 A/B，尚缺 L2/L1/stall/occupancy 和完整 CPU 归因。已有上游 [PR #3641 的局部正确性验证](tobeo-20261023/qwen36-pr3641/README.md)通过，未声称自己的优化加速。

建议用时：2–3 天。

### 已知研究入口

[Issue #2464](https://github.com/Niko1221/Strata/issues/2464) 的[后续评论](https://github.com/Niko1221/Strata/issues/2464#issuecomment-6291779543)报告：在其 V100 上，`k_attn_part` 每个生成 token 的累计耗时从 1K 上下文的 1.68 ms 增到 16K 的 8.71 ms。该数字属于报告者，不是本机测量。

本地 `src/qwen35/q36_engine.cu` 的静态线索：

- `k_attn_part` 使用 FP32 K/V；多个 query head 共享 KV head，但按 query row 分别计算。
- QK 点积中，相邻线程处理不同 token 的 K 行，需检验访问合并情况。
- graph 模式按配置上下文的 chunk 数启动，超出实际长度的 block 提前返回，需检验其成本。

以上均为待验证假设，不是已经确认的本机性能缺陷。

### 工具顺序

1. **Nsight Systems**：截取加载和预热后的代表性请求。区分 prefill、decode、CPU 专家工作、拷贝、同步、graph launch 和 GPU 空隙。
2. **Nsight Compute**：只分析 Systems 已确认值得深入的 kernel。优先检查 `k_attn_part` 的访存合并、DRAM/L2 流量、stall、寄存器和 occupancy；不要只追 occupancy。
3. **未挂 profiler 的复测**：正式报告速度收益时使用独立测量。profiling 数据用于解释原因，不能与普通运行直接混作 A/B。

图表至少包括：上下文长度与 ms/token、代表性 decode 时间线、主要 kernel 耗时及调用次数、GPU 空隙与拷贝重叠。重叠活动要按时间区间分析，不能把各流耗时简单相加当作总延迟。

Flash-Next 的 `--stage-timing` 文档明确提示其统计限制，不能把 kernel-count share 当成真实设备耗时占比。

### 继续与转向条件

- 如果 attention 的关键路径贡献随上下文显著增加，进入阶段 D。
- 如果主要耗时是 CPU 专家或同步等待，先转向 Flash-Next 调度或对应 CPU 路径，避免优化低占比 kernel。
- 如果目标 kernel 的占比很小，用 Amdahl 上界估计端到端空间；没有可观收益时停止该方案，保留负结果。

验收：写一页瓶颈结论，附本机 trace、计时与一个最小优化假设。证据不足时继续测量，而不是凭 GPU utilization 决定改动。

## 6. 阶段 D：一个可审阅的 attention 优化

2026-10-29接续：本阶段仍为条件性后续。#4347/#4335 的独立取舍验证已经完成；先固定新源码基线并补正常工况时间线，只有attention仍值得优化，才接续本阶段，保留以下正确性与性能要求。

建议用时：3–5 天，依阶段 C 结果调整。

### 第一版范围

进入前先重新查重并核对候选范围；若仍适合验证 #3641，第一版做其在届时固定基线上的兼容性与 Blackwell 验证，不自行重写同一 GQA 共享读取。只有作者更新后的候选或清晰归属的本地集成通过该基线门禁后，才做性能比较。若最终需要独立实现，优先选择一个未被现有 PR 或 #3700 后续工作覆盖的机制，并先在相关 issue 商定范围；继续保持 K/V 精度、缓存容量、专家预算和外部行为不变。

确认第一项有用后，才考虑 GQA 的 KV tile 复用或其他独立优化。第一版不同时加入 KV 量化、MTP 策略、缓存分配和多会话调度。

新增路径默认关闭，明确适用条件和回退路径。开始较大改动前，在原 issue 讨论范围并取得维护者认同；本计划本身不代表维护者认可。

### 正确性要求

- 建立独立参考输出或复用真实可用的原实现；覆盖不同上下文、非整 tile 长度、因果边界及多 query row。
- 先测 kernel 输出，再测 logits/生成结果。现有 `STRATA_Q36_VERIFY` 不自动覆盖所有新内核，需要核对或扩展验证入口。
- 若改变浮点归约顺序，提前定义误差度量与验收标准，报告最大误差、数值分布及适用时的 teacher-forced logits/KL、top-1 差异。
- 不能用“答案看起来差不多”替代验证，也不能仅凭 token 哈希不同就断定模型质量下降。若原目标是 bitwise identity，出现差异就应定位。
- 涉及 batch/MTP 时增加相应门禁；避免用固定 slots 的诊断结果替代日常动态布局下的正确性结论。

### 性能验证

- 同机、同工具链、同 workload，至少 5 组交替顺序的基线/候选配对。
- 同时报告 kernel 时间和未挂 profiler 的端到端 ms/token、TTFT、吞吐；记录实际输出长度与 MTP 接受情况。
- 检查短上下文、prefill、显存和启动开销是否退化。保留所有配对结果、失败项和范围，不只报告最大收益。
- 当固定专家布局时，测的是该布局下的机制；当允许自动布局时，另测最终用户配置，明确二者的区别。
- “稳定超过现有噪声”是继续投入的标准，3% 可作预筛参考，不能取代配对结果或作为项目统一合并门槛。

验收：单一改动可以解释收益来源；正确性、性能和边界检查有原始证据。失败或无收益也写入实验记录，不能包装成完成的优化。

## 7. 小贡献：MTP 实际执行状态诊断

候选关联：[Issue #3354](https://github.com/Niko1221/Strata/issues/3354)。

先审阅 [PR #3295](https://github.com/Niko1221/Strata/pull/3295)，它已处理 temperature=0 与模型卡 penalty 的交互。不要重新提交相同修复。没有采样参数的请求与显式 temperature=0 的请求也不是同一问题。

可以讨论的最小切口：MTP 已加载，但最终解析出的 sampling 不允许 drafting 时，在已有诊断位置显示原因。诊断应依据引擎实际判定，避免只在 Python 侧猜测；控制日志频率，不向每个 token 打印。

第一版只处理明确的一类原因，记录 configured/enabled/offered/accepted 的区别。验证至少覆盖：

- 纯贪婪且无 penalties，MTP 实际提供草稿。
- temperature 或 penalty 导致不走投机路径，原因与实际一致。
- MTP 没有加载时，不误报为采样禁用。
- 诊断关闭时的既有输出和协议保持一致。

采样、batch 或上下文剩余空间导致的其他情况，只有在准备扩展范围时再加入。若上游已实现同类诊断，转为独立验证或 benchmark 贡献。

## 8. 备用路线

### Flash-Next：端到端亲和性校准

阅读 `tools/calibrate.py`、`strata_control/calibration.py` 和引擎 `measure_pool_affinity()`。已有 `--pool-affinity measure`，不能把布局选择当作新功能。

要回答：启动专家微基准选出的布局，是否也是实际 decode 更快的布局？显式校准流程是否需要比较布局，或为 worker 候选增加交替确认？两项分开做。

先固定实际专家缓存与其他参数，比较 all/P 核及实际线程放置，再验证自动配置的用户收益。包含代码、中文、英文及 prefill 负向检查。只有复现错选或稳定收益，才实现自动选择改动。

[#3262](https://github.com/Niko1221/Strata/issues/3262) 仍显示 open，但评论确认 LP-E 分类在 0.2.1 修复并通过真实设备验证，不作为当前待修问题。

### 多会话缓存：先做收益与成本实验

测试 A→A、A→B→A、A→B→C→A、长会话夹短请求、真实工具调用回合。比较显式关闭（`--conversation-cache-mib 0`）与可容纳快照的显式缓存预算，另设“未传参数”的 v0.2.3 自动预算观察臂；测 reused tokens、TTFT、保存/恢复时间、复制字节和 RAM 峰值。

[#3493](https://github.com/Niko1221/Strata/issues/3493) 作者已反馈启用现有缓存解决不命中问题。另有 [#3584](https://github.com/Niko1221/Strata/pull/3584)、[#3565](https://github.com/Niko1221/Strata/pull/3565)、[#3517](https://github.com/Niko1221/Strata/pull/3517) 在做相关工作。先定位模板/token 前缀、状态、停车预算和复制成本，再决定是否有独立修复空间。

### CUDA Graph：先证明本机有同类空隙

参考 [#3497](https://github.com/Niko1221/Strata/issues/3497) 的 Turing 双卡 profiling 方法。其 graph launch 耗时不能直接推广到单张 Blackwell。只有本机时间线确认 host launch 或其他同步处于关键路径，才研究减少节点、kernel fusion 或提交方式。

## 9. 上游查重与 PR 规则

依据 [CONTRIBUTING.md](../CONTRIBUTING.md)、[AGENTS.md](../AGENTS.md) 和[社区测量指南](../docs/COMMUNITY_BENCHMARKS.md)：

- 每次开始实现及提交前，重新搜索 open/closed issue 与 PR，并阅读后续评论。关闭不等于拒绝或合并。
- Qwen3.6 KV 相关旧方案包括 [#2698](https://github.com/Niko1221/Strata/pull/2698)、[#3084](https://github.com/Niko1221/Strata/pull/3084)、[#2742](https://github.com/Niko1221/Strata/pull/2742)。若考虑相同方案，先回原讨论确认范围，保留来源与归属。
- 大功能、重构和默认行为变更先取得维护者范围认同。一个 PR 解决一个问题，新增功能 opt-in。
- 修改原生代码时，构建所有受影响后端，区分编译和真实硬件执行。缺少验证时保持 draft，列明缺项并寻求针对性验证。
- 标题带 `[Engine]`、`[Benchmark]` 等区域前缀；正文先写问题和结果，再写方法、验证与限制。
- Passed、Failed、Not run 分开。未执行的建议命令不是通过证据。静态猜测明确标注为 unconfirmed static analysis。
- 结果报告与引擎改动分别提交。标准 benchmark 协议的 draft 状态以最新文档为准，不把本计划实验自动称为标准结果。

## 10. 产物、归档与求职表达

新实验按实际日期新建目录，例如 `reports/tobeo-YYYYMMDD/qwen36-attention/`，不要覆盖 2026-10-21 的数据。建议组织：

```text
README.md                 # 问题、环境、复现方法、结果与限制
experiment-plan.md        # 假设、控制变量、判定标准
scripts/                  # 可公开的 workload 与采集/分析脚本
results/                  # 每次运行记录、汇总表和图
traces/                   # 本机 profiler 文件及导出数据
validation.md             # 正确性、构建、性能检查的真实结果
upstream-notes.md         # 查重、相关讨论、拟提交范围
```

按目录忽略大型 trace、运行时配置和本机数据，保持报告与可复现脚本可进入 Git。公开 PR 所需的小型原始结果要另行脱敏并明确纳入，不能因本地 `.gitignore` 而漏交证据。不要提交模型、凭据或私人 prompt。

建议两三周节奏：第一周完成构建、基线和 profiling；第二周完成一个候选及正确性验证；第三周完成配对测量、上游沟通和 PR 整理。若 profiling 结果不支持 attention 优化，就按转向条件调整，不为赶时间保留无依据方案。

最终作品应能回答：

1. 为什么选这个真实 workload？
2. 如何确定瓶颈，以及排除哪些混杂？
3. 每处代码为什么这样改？
4. 正确性如何验证，哪些情况仍未覆盖？
5. 算子收益与端到端收益为什么不同？
6. 适用硬件、上下文和内存配置的边界是什么？

简历写法模板，只有完成并实测后才能填数：

> 在 RTX 5060 Ti 16GB 的 Qwen3.6 混合推理路径中，使用 Nsight 定位〈具体瓶颈〉，实现〈具体改动〉；在〈上下文和 workload〉上，经〈配对方法〉测得〈端到端指标〉改善〈实测值〉，完成〈正确性与边界验证〉，贡献〈PR 链接及真实状态〉。

不能把别人的 profile、已有开关收益或计划中的改动写成自己的成果。没有合并也可以展示经过验证的研究，明确 PR 状态即可。

## 11. 执行与收尾清单

2026-10-28 新增独立的[DeepSeek 社区使用案例](tobeo-20261028/deepseek41-community/README.md)，现已完成并发布；不替代上文 Qwen3.6 优化主线。10-21选题池、10-28接续与复评正文均保留为历史，当前执行排序统一看页首当前入口。

每次任务结束前复核本清单：已实际完成的项目打勾，并记录日期、证据与范围；部分完成保留未勾选并说明进度。后续扩展配置或 workload 时，已有勾选不替代新条件下的验证。

最近执行更新：2026-10-30。本轮沿用10-29 fetch固定的 `46c152a1`，源码引擎0.1.53；已独立完成下一轮基线的构建、门禁和重复性验收，没有在本轮重查全部 PR/Issue 状态。10-28的 `5e8a4cca` 及讨论审查见[恢复后研究评估](tobeo-20261028/research-next-steps/README.md)。阶段 A、阶段 B 最小矩阵及阶段 C 的原 Systems 时间线是在旧 revision 上完成的历史证据；另有 1K/16K Compute 三指标、1K CPU IP/PDB 解析，以及上游 #3641 固定旧 head 的 CUDA 构建/三个选定测试/真实 Q4 1K 对照。历史HtoD异常已在10-28整机重启后恢复。`5e8a4cca`基线、#4347/#4335各自的数值/小型任务验收和固定历史五组配对均已完成；Flash-Next三臂及DeepSeek案例也已收尾，详见各项证据。10-30另已完成相关复制方向查重、原作者切片的数值/自由生成门禁、五组配对及机制跟踪；正常工况CPU IP/调度及受控job路径后续已完成；无插桩全系统根因、#4347原自由生成五组配对和完整质量验收仍未完成。按北京时间运行开始日期归档。

- [x] 核对最新上游、相关讨论和工作区改动。
  - 2026-10-30 晚间本地归档：发布补充与源码更新记录提交为 `8e0dce58`，计划和导航单独提交。只读核对9个上传文件的SHA/Git blob身份、两份评论回执、ZIP68文件与离线账本通过；194处链接按本地或导出目录语义核对通过，Python语法及暂存空白检查通过。本次未重复发布、推送、构建新引擎或重跑GPU实验，新基线验收仍未完成。
  - 2026-10-30 下午本地归档：CPU采样/复制机制与job依赖诊断分别提交为 `b1327a2d`、`03ab5f41`。只读重算两目录共213份证据SHA及清单指纹通过，Python语法、JSON格式、196处本地链接和两份诊断补丁格式检查通过；补丁空白上下文原样保留。phase/token账本分别为10160/126行；本次未重跑实验、改写封存清单或推送远端，未把原版无扰动根因标记完成。
  - 2026-10-30 本地归档：CUDA/NVTX时间线与复制切片验证分别提交为 `a442cbe2`、`a5ed4122`，导航、分支盘点与本计划另行归档。Python语法、JSON格式和发布证据包离线一致性校验通过；仅提交现有报告、脚本与小型数据，未重跑GPU实验、推送远端或执行分支清理。
  - 2026-10-30 Git 清理盘点：完成六条本地分支、远端引用、三个具名贡献/验证工作树及 #3542/#3428/#4577 实时状态核对；两条备份分支的 9/11 个补丁分别全部已有 main 等价提交。证据及清理边界见[分支盘点](tobeo-20261030/git-branch-audit.md)。本次未删除分支/工作树、未同步 main、未新增运行验证；公开证据分支保留。
  - 2026-10-29 本轮：fetch固定 `46c152a1`，核对相对 `5e8a4cca` 的源码差异和现有工作区改动；只更新版本与执行入口，没有重查在线讨论或改变此前发布结论。总计划中的“近期下一项”和旧“最新”段落已更新/标为历史，原始结果保留。新基线证据见[协议](tobeo-20261029/qwen36-repro-baseline/experiment-plan.md)。
  - 2026-10-29 文档导航补充：复核两份接续文档的先后关系，将[research-next-steps](tobeo-20261028/research-next-steps/README.md)正文标识为早先GQA方案，将[topic-reassessment](tobeo-20261028/topic-reassessment/README.md)明确为近期#4347/#4335的执行依据，并同步已发布结果。本次只修正文档定位与历史状态标识，没有新增上游复评、模型测量或阶段完成声明。
  - 2026-10-28 本轮再次fetch确认`upstream/main=5e8a4cca`，核对open/closed issue/PR、#4335/#4347补丁与后续评论、#3522校准范围、#3773及缓存重叠，并检查自动预算guard与measure的10% P核偏好。完成[模型与选题复评](tobeo-20261028/topic-reassessment/README.md)：保留两模型，优先Q36 hybrid独立验证，Flash-Next校准升至P1，GQA降为条件性后续。仅审查与设计，未新增GPU结果。
  - 2026-10-28 后续补充 Qwen3.6/Flash-Next 选题关系；完成 [DeepSeek 下载慢排查](tobeo-20261028/deepseek41-community/DOWNLOAD_DIAGNOSTIC.md)，核对运营商 USB 网卡出口，比较代理/直连、入口、分段、CDN 和备用源，改用四路直连后台续传。仅证实低外网吞吐及当前对照，未确认运营商限速、未完成模型下载或推理测试。
  - 2026-10-28 本轮梳理历史选题池、总计划和恢复后接续方案的关系；完成 DeepSeek 2.25bpw 资源与来源审查，七份 ModelScope 文件大小/哈希均匹配仓库接受版本，后台下载已启动，首份元数据 SHA-256 通过。见[下载与案例安排](tobeo-20261028/deepseek41-community/README.md)；未将下载准备计作模型或研究验证完成。
  - 2026-10-28 后续完成[日常引擎升级评估](tobeo-20261028/research-next-steps/README.md#日常引擎升级决策评估2026-10-28)：实时发布为 engine 0.1.52，运行进程仍为 0.1.46，驱动 610.88 与 CUDA 13 要求相符；建议保留旧组件后验证切换，重点检查显存余量、多轮、MTP 与缓存。仅只读核查与决策记录，未升级或新增推理测量。
  - 2026-10-28 本轮：复核 `5e8a4cca` / v0.2.7、Q36 sampling/attention 差异、#3641/#3678/#3295 元数据与 #2464/#3700 后续评论；更新[研究优先级与接续实验](tobeo-20261028/research-next-steps/README.md)。确认 #3700 已扩展重叠方案，#3641/#3678 API 当前可合并；未把静态审查记作构建、性能或交付完成。
  - 2026-10-28 用户完成 [NVIDIA Nsight Compute #387175](https://forums.developer.nvidia.com/t/rtx-5060-ti-windows-persistent-low-pcie-transfer-throughput-observed-after-kernel-replay-tdr-restored-after-reboot/387175) 发布；已通过公开主题 JSON 核验分类、正文、测量表和限制，并更新 [Strata #4381](https://github.com/Niko1221/Strata/issues/4381) 正文完成互链。核验时论坛尚无回复；报告发布完成不代表根因已被厂商确认或完整优化交付完成。
  - 2026-10-28 同日早先完成针对性 issues/PRs/论坛查重与脱敏，发布 [Strata 排障报告 #4381](https://github.com/Niko1221/Strata/issues/4381)，并准备 NVIDIA Nsight Compute 正文、证据包和预填页面；随后由用户登录发布并完成互链，最终状态以上一项和[发布状态](tobeo-20261028/upstream-reports/README.md)为准。未把报告发布或本机环境恢复当成完整优化交付。
  - 2026-10-23 同步后复核 `upstream/main` `7ddc17a3`（v0.2.3.1）：Qwen3.6 核心仅见 CUDA 12.0/12.1 编译兼容修复；v0.2.3 改变 conversation cache 自动预算及 Work profile 默认值。GitHub 实时状态确认 #3641/#3678/#3700 均未关闭或合并，前两者仍基于 `011c9e6` 且 API 返回当前不可直接合并；#3542 已更新到当前 base。审查结果已写入本计划和各执行入口，没有向外发送消息或修改上游。
  - 2026-10-23 通过 API 重新搜索 open/closed，阅读 #2464/#3700 后续评论，确认 #3641 已有 FP32 GQA 对照开关，#3678 也有重叠工作；固定 #3641 head f3f2136f 做已有方案验证，不另起重复实现。没有向外发送消息或提交 PR。
  - 2026-10-22 已核对工作区，重新读取 #2464 及后续评论，并查询包含 k_attn_part 的相关 PR（包括 #3084、#2698）；快照保留在阶段 B 目录。实验继续固定阶段 A revision，未声称运行最新 main；后续实现前仍需重新查重。
- [x] 确认源码基线、工具链、模型哈希和独立构建目录。
  - 2026-10-21 至 2026-10-22 完成，见 [WSL 基线](tobeo-20261021/qwen36-source-baseline/README.md)与 [Windows 原生基线](tobeo-20261022/windows-native-baseline/README.md)。后续主用 Windows 原生构建。
- [x] 建立同步后 `5e8a4cca` / v0.2.7 的 Windows 原生源码基线。
  - 2026-10-28 本轮完成：MSVC19.42/CUDA13.2/sm_120，独立当前main与#4347原始候选构建，两边各16项选定host/布局/采样测试通过；main四臂固定布局门禁10/10逐token一致，VERIFY436,050次比较、0 mismatch。自动布局下main/候选保留/候选释放的1K/16K、64token门禁也通过；见[执行报告](tobeo-20261028/qwen36-pr4347/README.md)。仅此配置范围，非全量测试、独立Graph或质量验证。扩大到256token后身份不成立，正式配对在第一组停止，五组未完成。
- [x] 固定下一轮 profiling 的 `46c152a1` Qwen3.6 可复现源码基线。
  - 2026-10-29 22:47验收完成、随后离线复核通过：[报告与复现入口](tobeo-20261029/qwen36-repro-baseline/README.md)、[小型汇总](tobeo-20261029/qwen36-repro-baseline/summary.json)。固定源码0.1.53、MSVC19.42/CUDA13.2/sm_120、原Q4模型SHA及3608份ggml文件；独立构建与17项选定测试、Ninja无改动复查通过。四臂各10条逐token一致，VERIFY436,050次/0 mismatch，MTP2实际接受567/786草稿。32K/chunk2048/7workers/MTP0/packed、自动63slots后冻结驻留，两次新进程的1025/16385输入各64输出分别一致、fresh且0换槽；HtoD前24.894215/后24.810577GB/s。44份本地证据离线核对，源码/exe/DLL/日常配置SHA未变，原Flash-Next0.1.52恢复loaded=true、无恢复错误。保留版本采集的两次脚本失败及修正；仅本机Windows/CUDA受控基线，不代表全量测试、独立Graph、动态换槽/质量、逐字节重编译一致或正常工况profiling完成。
- [ ] 在新基线上补正常 HtoD 工况的 Qwen3.6 关键路径时间线。
  - 2026-10-30下午：原配置chunk2048的受控job依赖及wall账本已完成，见下方已完成子项；完整原版无扰动根因、系统全栈和扩展配置尚未完成，因此总项保留未勾选。午间“无job边界”和早间“采样权限不足”仅描述当时状态。
  - 2026-10-30午间部分完成：[CPU/IP与调度补充](tobeo-20261030/qwen36-cpu-mechanism/README.md)解除采样权限障碍，已区分算术/worker等待/CUDA查询并对齐GPU窗口；引擎image IP均解析。仍无逐层job边界、完整栈和内核态符号，组合采集有10%–16% decode扰动，不把本项或最终关键路径勾选完成。
  - 2026-10-30 部分完成：新正常工况CUDA/NVTX四格与同日无profiler请求均通过，见下方完成子项；CPU sampling环境预检为No admin/Fail，未采集CPU IP或调度，仍不能区分专家算术、事件轮询及pool等待，本项继续保留未勾选。
  - 2026-10-29 历史安排：基线通过后另立采集范围；1K/16K、MTP0起步，chunk2048和显式4096分开，保持packed政策一致并记录布局。与历史异常工况trace、无profiler计时分开，不把本轮基线门禁当作阶段C完成。
  - 2026-10-28 目标更新为当前上游，完成静态差异和实验范围审查；尚未构建或运行新门禁，保留未勾选。旧 v0.2.3.1 目标由本项替代。
  - 2026-10-23 已完成代码差异与发布说明审查，但尚未重新构建或运行门禁。新基线须显式固定 worker、专家布局、conversation cache、MTP/drafting、上下文和采样；历史 `9de04cd4` 数据保留，不与新结果拼接。
- [x] 跑通适用的基线正确性门禁。
  - Windows 原生：14 项选定测试通过；VERIFY 436,050 次比较、0 mismatch；当前内核验证、默认 Graph 请求、MTP 三组各 10/10 prompt 与参考逐 token 一致。固定 64/256 专家布局会自动关闭 Graph，故独立 Graph 路径仍未验证。范围为 8K 上限和短 prompt，未覆盖全量测试套件。
- [x] 完成新基线正常工况的CUDA/NVTX采集、同日输出对照与阶段观察。
  - 2026-10-30：[报告](tobeo-20261030/qwen36-systems/README.md)、[汇总](tobeo-20261030/qwen36-systems/summary.json)、[阶段数据](tobeo-20261030/qwen36-systems/phase-results.csv)、[观察与最小假设](tobeo-20261030/qwen36-systems/bottleneck-notes.md)。原46c152a1/exe/DLL/Q4模型SHA，32K/MTP0/7workers/packed、chunk2048/4096实际63/50slots后冻结，1K/16K各64输出；4条同日无profiler请求与4份trace同chunk输出一致、全部fresh/0草稿/0换槽、进程退出0。4份SQLite范围/PID及完整性六项检查通过，54份本地证据留存；CPU sampling未运行。HtoD前24.843725/后24.890607GB/s，00:19:18恢复原Flash-Next0.1.52、loaded=true、配置SHA相同且无恢复错误。每格n=1，4096/1K trace decode慢20.6%完整保留；不代表候选A/B、完整关键路径、质量、动态缓存或新优化收益。
- [x] 发布CPU/复制机制/job级路径补充到PR3905原线程。
  - 2026-10-30 18:00:16：[发布记录](tobeo-20261030/qwen36-pr3905-followup/README.md)、[新增评论](https://github.com/Niko1221/Strata/pull/3905#issuecomment-6518999609)。fork独立证据分支固定b6a98dd9，仅新增9文件/1130419字节，线上blob身份与本地一致；ZIP68文件，离线核对文件哈希、10160 phase/243840任务和126 token账本。完整正文回读、同账号及线程查重通过，无重复评论。原五组计时/评论及94/52/161份旧证据未改；新测量仍是46c，不宣称新上游通过。连接器上游评论403后用现有Git凭据确认同一账号并发布；未改变PR代码、fork main或默认。
- [x] 根因调查前将项目源码更新至指定upstream870aedd9。
  - 2026-10-30：[更新记录](tobeo-20261030/qwen36-pr3905-followup/README.md)。fetch精确870aedd9e1ebe1c91f94da93b59af17729f6c5c0，本地main保留研究提交并合并为e1691cc8，无冲突；更新前bc6098b9由backup/pre-upstream-870aedd9-20261030保留。独立src-main-870aedd9精确固定且干净，除AGENTS/报告外项目文件与上游一致。原46c基线/worktree/证据及日常配置保留；源码版本0.1.54，不代表新构建或GPU验收完成。
- [ ] 在870aedd9建立并验收根因调查使用的新基线。
  - 2026-10-30准备完成：精确源码worktree已建立，尚未CUDA构建、数值/输出/实际布局门槛或无profiler重复性验证。完成这些前不直接移植job插桩或声称旧迟启动现象在新提交复现；仍以原Q4/chunk2048/63slots/7workers/MTP0/packed为目标配置。
- [x] 完成固定46c152a1的独立job诊断构建、数值门槛和两轮采集。
  - 2026-10-30：[阶段入口](tobeo-20261030/qwen36-job-path/README.md)。原配置/计算保持，独立NVTX诊断及完成原子序号补充构建均通过CUDA、17项选定测试和Ninja；两轮各四份完整logits与原参考逐位相同、八条测量输出/布局通过，原基线与首轮保留。第二轮于13:32:02恢复日常服务、配置SHA相同，无恢复错误。已分析两个63迭代路径和实际最后完成发布，不代表原版无扰动的唯一全系统根因；新增材料未外发。
- [x] 完成job级路径的最终文件/账本验收及正式报告收尾。
  - 2026-10-30：[正式报告](tobeo-20261030/qwen36-job-path/README.md)、[验收汇总](tobeo-20261030/qwen36-job-path/summary.json)、[phase账本](tobeo-20261030/qwen36-job-path/phase-ledger.csv)、[token账本](tobeo-20261030/qwen36-job-path/token-ledger.csv)。13:39:26后台验收/静态封存通过，用户返回后再次核对161份文件及manifest指纹。两个63迭代路径、共10160个phase/243840个行任务覆盖和原子完成序号通过，phase/token账本精确闭合；106/67个decode phase最后发布者不同于最晚body，已修正首轮代理。四份完整logits、八条输出/布局、17项选定测试及来源/模型/旧证据一致性通过。完成受控观测job路径，未确认无插桩全系统根因；trace/on decode扰动22.1%/13.5%，不将任务wall称纯算术，不重复累计host等待。GPU半边2514/2516层在CPU pool结束后才启动，先调查执行/提交残差；未验证优化收益、全栈、HIP/SYCL或全量质量。原基线与首轮保留、日常服务13:32:02恢复且配置不变、新材料未外发。
- [x] 完成正常HtoD下固定46c152a1的CPU周期IP/调度试采与复制event机制补充。
  - 2026-10-30午间：[报告](tobeo-20261030/qwen36-cpu-mechanism/README.md)、[CPU数据](tobeo-20261030/qwen36-cpu-mechanism/cpu-summary.json)、[复制依赖数据](tobeo-20261030/qwen36-cpu-mechanism/mechanism-summary.json)、[320步明细](tobeo-20261030/qwen36-cpu-mechanism/mechanism-stages.csv)。CPU-only预检1851周期样本/13899调度事件；三格各一条同日参考与CPU trace，六测量均匹配旧64token参考、63slots/2048chunk/fresh/0草稿/0换槽/退出0；decode样本9448/12093/11867，固定PDB解析引擎image 0未解析，七worker及CUDA提交线程已定位。基线16K worker等待52.63%、算术20.09%，2430算术样本均在GPU空隙；分母含注入线程，内核态13.45%未解析，不等于wall time或瓶颈份额。三格组合trace/plain decode为1.165/1.152/1.104，全部保留；WPT未安装，merged ETL未生成，但SQLite CPU/调度可用。原复制trace320步均核对字节守恒和双buffer record/wait关联，DtoD流实际priority=-5，设备event timestamp=0故不声称GPU wait时长。HtoD24.862111→24.942329GB/s，12:05:08原Flash-Next恢复、配置SHA相同，无恢复错误。未重建引擎、扩展推理配置、改默认、更新原五组计时或自动外发。完整因果关键路径、全栈和内核态符号仍未完成。
- [x] 完成已有PR3905复制切片在本机固定布局的独立验证。
  - 2026-10-30：[报告](tobeo-20261030/qwen36-copy3905/README.md)、[汇总](tobeo-20261030/qwen36-copy3905/summary.json)、[全部配对](tobeo-20261030/qwen36-copy3905/pairs.csv)、[查重索引](tobeo-20261030/qwen36-copy3905/upstream-summary.json)。归属xyehya/af08278c，仅复制hunk+CLI适配，不是整套PR验收。固定46c152a1/Q4/Windows5060Ti、63slots/chunk2048/7workers/MTP0/packed；独立CUDA构建、17项选定测试、原基线/候选off/on两长度各64行完整词表logits有限且逐位一致；4条自由生成门禁及20条正式新进程请求全部匹配参考、fresh/0草稿/0换槽/退出0。每长度五对交替AB/BA，1K/16K prefill配对比中位数1.3021/1.1915、合计1.0825/1.1457，均5/5变快；decode波动保留。达预设规则后两条16K trace核对输出/范围/PID/复制字节及独立DtoD流，staging总字节相同，不混入收益。矩阵HtoD前24.955953/后24.880983、跟踪前24.899590/后24.885794GB/s；08:24:20再次恢复原Flash-Next0.1.52、loaded=true、配置SHA相同，无恢复错误。首轮入口DLL部署失败在门禁停止、另开execution-02，无旧计时混用。未运行HIP/SYCL、动态换槽、并发、长稳或全量质量；不改默认；本实验阶段未外发，后续实际发布见下一项。完整CPU归因及总瓶颈项仍未勾选。
- [x] 将PR3905独立复制验证发布到原讨论，并归档可访问的脱敏证据。
  - 2026-10-30 09:22:50：[原评论](https://github.com/Niko1221/Strata/pull/3905#issuecomment-6512596830)、[发布记录](tobeo-20261030/qwen36-copy3905/PUBLICATION.md)。用户授权后发布，作者Thymos2027、全文回读与本地实际文本一致，无重复评论。fork独立分支固定commit `7c0247c72d3e57df40e2dd8b9be415ec90046f98`，55文件仅证据目录，逐文件线上内容一致；离线核对三输入、六数值摘要、24输出/日志、十配对及trace字节守恒。原始94文件实验manifest未改。连接器fork写入成功、上游评论403后用同账户gh完成，未新开PR/issue、修改fork main或既有PR，也未新增GPU测量/默认变更。完整CPU归因、HIP/SYCL及全量质量范围不因此计完成。
- [x] 建立固定最大上下文的 1K/4K/8K/16K 实验矩阵。
  - 2026-10-22 完成 24/24 条请求，每格 3 次、均输出 256 token；曲线、中位数、范围及测量边界见[阶段 B 报告](tobeo-20261022/qwen36-context-curve/README.md)。固定配置上限 32768，实际输入为 1025、4096–4097、8193、16385 token。
- [x] 核对真实 MTP 状态、专家布局和前缀复用状态。
  - 2026-10-22 原生短 prompt 基线：MTP 2 接受 567/786 个草稿，每层固定 64/256 专家驻留 GPU，fresh 请求日志 reused=0。新实验矩阵仍须逐次记录这些状态；本项不代表多会话缓存验证完成。
  - 同日阶段 B：24 条请求均 reused=0；MTP 0 全部 offered=0，MTP 2 全部 offered>0；6 次启动均为 64/256 固定专家槽位、slot replacements=0。12 对输出哈希一致，范围限于本轮配置和 workload。
- [x] 采集加载/预热之后的 decode trace。
  - 2026-10-22：Nsight 2026.1.3 四组完整生命周期采集后，按 NVTX 筛选预热后的 decode；图、kernel 明细和诊断见[阶段 C 报告](tobeo-20261022/qwen36-profiling/README.md)。实际 Graph 关闭；未采 CPU sampling/context switch。六项汇总检查通过，未将两批有问题的试采当作正式结果。
- [x] 跑通 Compute 的 1K / MTP 0 最小硬件计数采集。
  - 2026-10-23 首次 1K 完成：application replay 1 个 pass，三个指标有效、尺寸匹配，64-token 输出验证与服务恢复通过，见[最小采集报告](tobeo-20261023/qwen36-compute/README.md)。后续 16K 见下一项；完整硬件指标仍未覆盖。
- [x] 补齐 16K / MTP 0 的相同三个 Compute 指标。
  - 2026-10-23，代理直接运行；874.176 μs、DRAM 读 91,881,216 bytes、写 1,098,752 bytes，shape、64-token 前缀和服务恢复均通过，见[两上下文汇总](tobeo-20261023/qwen36-compute/summary.json)。每个上下文只测一个调用，不代表 L2/stall/occupancy 已完成。
- [x] 检查同日环境漂移，独立核对主机到 GPU 的传输通路。
  - 2026-10-29：已发布并按当前 Bug report 模板修正上游 [issue #4381](https://github.com/Niko1221/Strata/issues/4381)，保留 TDR 后约 1.7 GB/s、重启后同一探针 24.88 GB/s 的实测、时间线和未确认根因限制；Intake 自动检查通过，`needs-format` 标签已移除。仅为历史单次相关事件序列和排障参考，没有可重复 TDR 触发器，也未声称当前 0.2.7/engine 0.1.52 存在回归。
  - 2026-10-28 后续：日常 engine 0.1.46 → 0.1.52 已完成，官方包 SHA-256、签名/文件、组件 test-start 及短回答、代码、中文、A→B→A、工具调用验收通过；配置未变、旧组件保留，HtoD 约 24.9 GB/s。见[升级与验收](tobeo-20261028/engine-upgrade/README.md)。未运行长上下文、正式性能 A/B 或当前源码基线，不扩大全局完成范围。
  - 2026-10-28 上游拉取与用户重启后，恢复[日常 IQ3_S 服务](tobeo-20261028/daily-start-105651/README.md)：当前服务端配合已安装 engine 0.1.46，health loaded=true、短 API 回答通过，启动 H2D=24.9 GB/s、温度遥测可用。未升级引擎，显存余量告警仍在；未将 6-token 冒烟请求作为正式性能测量。
  - 2026-10-28 [报告价值评估](tobeo-20261028/pcie-after-reboot/README.md)：重新检索 TDR/PCIe/reboot/Nsight 的 issues，建议优先向 NVIDIA 报告恢复后的持续低吞吐，Strata 侧作排障参考；未找到确认同案，未声称穷尽查重，未发布 issue/comment。后续实际提交前仍需完成 PR/评论范围的针对性查重及脱敏。
  - 2026-10-28 用户整机重启后，用 10-24 同一 exe 复测：H2D=24.882、D2H=28.370、mapped read=16.651 GB/s，退出码 0、数据抽查通过，负载期间采到的代际均为 Gen5，驱动仍为 610.88。见[重启后恢复验证](tobeo-20261028/pcie-after-reboot/README.md)。确认本轮传输恢复，强支持此前持久驱动/设备状态异常；未启动日常模型或测 decode，不代表阶段 C 归因或正式性能 A/B 已完成。
  - 2026-10-24 [进一步定位](tobeo-20261024/pcie-root-cause/README.md)：核对原始事件，13:26:01–04 TDR 紧接 13:26:07 首次慢探针；卸载模型后独立 H2D=1.726、D2H=1.807、mapped read=1.608 GB/s，D2D=186.7、CPU memcpy=17.24 GB/s，抽查通过。复现 NVML RX 峰值高于有效 payload 带宽。优先怀疑 TDR 后持久驱动/设备传输状态；物理代际仍有报告冲突，未执行系统/设备复位，不将相关性记作根因已证实或环境已恢复。
  - 2026-10-24 完成 HtoD 症状的[上游 issues 检索](tobeo-20261024/strata-restart/github-related-issues.md)，核查 #485/#2137/#2453 正文及评论；找到探针低估、Gen1 限速与同卡 decode 降速的相关报告，但未确认完全同因案例。未发布消息或执行新测量，不代表本机环境恢复。
  - 2026-10-24 经用户授权重启日常 Strata：模型已加载，温度/功耗/利用率遥测恢复；启动 HtoD 仍为 1.7 GB/s，传输异常未恢复。见[重启验证](tobeo-20261024/strata-restart/README.md)。未改配置或系统设置，未新增 decode 测试，不将遥测恢复记作性能恢复。
  - 2026-10-24 补查 Dashboard 遥测：旧服务 `/metrics` 温度/功耗等为空，而新进程用相同 `_Nvml` 读取成功，温度约 48°C；见[遥测核查](tobeo-20261023/qwen36-profiling/flash-next-slow-decode.md)。未重启或新增传输测量，不能确认与 HtoD 异常同源，环境恢复仍未完成。
  - 2026-10-24 只读复核[引擎升级时间线](tobeo-20261023/qwen36-profiling/flash-next-slow-decode.md)：0.1.46 在 10 月 21 日升级后带宽正常，10 月 22 日 13:08 仍为 25.0 GB/s，13:26 同路径/版本/启动参数首次记录 1.7 GB/s。未做版本回滚 A/B，未确认异常触发原因，不新增阶段完成项。
  - 2026-10-23 补查日常 Flash-Next 的 21:46 请求日志：177-token decode 为 26.5 tok/s，MTP 接受 87/130，当前启动探针 1.7 GB/s，且有显存余量告警。见[日常服务慢速核查](tobeo-20261023/qwen36-profiling/flash-next-slow-decode.md)。本轮仅核查已有日志，没有新增带宽/推理测量，也未确认换页或完成环境恢复。
  - 2026-10-23 20:17 再测为 1.732420997 GB/s，512 次 64-MiB pinned copy、抽查通过；负载时 NVML/PnP 冲突仍在，环境尚未恢复。证据为本机 `tobeo-20261023/qwen36-profiling/pcie-diagnostic-03/result.json`，范围与[无重启续做安排](tobeo-20261023/qwen36-profiling/no-reboot-next-steps.md)已记录。用户仅能远程操作，暂不安排重启或驱动维护；日常服务仍已加载。
  - 2026-10-23，无 profiler 控制 1K prefill 为 23,045.2 ms；两次 64-MiB copy 约 1.732/1.734 GB/s，卸载日常模型后仍慢；复现冻结引擎原始 256-MiB/四 burst 探针为 1.735 GB/s。NVML 负载报告 Gen1×8，PnP 速度编码仍为 5，底层原因未确定，见[环境诊断](tobeo-20261023/qwen36-profiling/README.md)。这完成的是异常识别，不是正常测量环境恢复。
- [x] 对已有 FP32 GQA 方案完成本机局部构建与正确性验证。
  - 2026-10-23，#3641 固定源码未修改，MSVC/CUDA 13.2/sm_120 构建与三个选定布局/数值测试通过；真实 Q4 的 1K/64-token、FP32 KV、GQA=0/1 输出一致，见[验证报告](tobeo-20261023/qwen36-pr3641/README.md)。只验证作者既有实现，16K 实模、五组配对和 HIP/SYCL 本机验证尚未完成。
- [ ] 写出一个瓶颈结论，再决定最小改动。
  - 2026-10-30下午：[job级报告](tobeo-20261030/qwen36-job-path/README.md)已形成受控依赖与时间分解。GPU半边早提交但多数在CPU pool结束后启动；可见空隙与CPU范围重叠，不能归为纯专家计算或GPU连续繁忙。下一项收窄到执行/提交残差的单因素诊断，仍无无插桩根因或候选收益证据；本总项继续未完成。
  - 2026-10-30午间后续：正常工况已获得CPU算术/等待的直接样本与调度证据，基线16K已识别算术样本均落在GPU空隙；同时大多数worker样本是在等待循环。可以排除“全部on-CPU均是有效专家计算”的解读，但尚无精确job级关键路径分解、独立优先级消融或等待策略收益证据，因此仍不勾选本总项、不据采样比例写优化。
  - 2026-10-30早间后续：[复制切片独立验证](tobeo-20261030/qwen36-copy3905/README.md)已将prefill假设收窄为可验证结果：同布局下约38.67GB专家权重从host转为独立stream DtoD，字节守恒，1K/16K合计配对比1.0825/1.1457且均5/5改善。但已有作者实现，不是新原创优化；decode CPU/IP/调度归因仍缺失，因此本总项保持未完成。
  - 2026-10-30：[一页阶段观察](tobeo-20261030/qwen36-systems/bottleneck-notes.md)已形成。16K prefill HtoD约157.13→78.57GB，copy/kernel重叠4723→3096ms，不能相加当串行成本；decode k_attn_part约556–559ms/21%–22%，仍有1.36–1.49秒GPU未覆盖。匹配源码的整层/分段复制门槛是下一项静态线索，未测两路径取舍；CPU采样权限不足，完整归因及最小改动选择不计完成。
  - 2026-10-29：#4335独立对照中，4096使GPU槽位63→50，16K prefill的2048/4096配对比中位数1.3029、合计1.1788（均快5/5）；generation为0.9791（慢5/5）。1K合计0.9779（慢5/5）。已确认本组分项与长度取舍，但没有将槽位和chunk交叉隔离、没有正常工况关键路径时间线，不把这些时长直接当作最终瓶颈归因。见[独立报告](tobeo-20261028/qwen36-pr4335/README.md)。
  - 2026-10-28 固定历史五组配对补充：#4347释放副本后，16K generation的A/B耗时比中位数1.0395（5/5变快），但prefill为0.9591、合计0.9834（5/5变慢）；1K合计方向混合。说明本组GPU专家增加未抵消prefill代价，未定位其具体原因，不把分项收益当作正常工况关键路径结论。见[配对报告](tobeo-20261028/qwen36-pr4347/README.md)。
  - 2026-10-28 后续：在1K/16K各97行全词表强制历史中，候选与主线匹配63/89槽位后分别逐位一致；布局变化自身top-1为96/97、95/97。将归因收窄为本组专家布局变化可复现的数值差异，未定位具体算子或正常工况关键路径；见[后续验收](tobeo-20261028/qwen36-pr4347/validation-next-summary.json)。本项仍未完成。
  - 2026-10-28：#4347实测释放1.78GiB、槽位63→89。固定相同63槽位时packed开关的97行完整logits逐位一致；改变为63/89槽位的1K教师强制对照top-1为96/97一致、mean KL0.001171。支持继续归因专家驻留与CPU/GPU执行差异，但没有新时间线/访存计数，不将数值诊断当作最终关键路径结论。
  - 2026-10-23 夜间：1K CPU IP 采到 10,870 个周期样本，本地 PDB 显示大量等待循环 IP，不能把 on-CPU 全算作专家数学计算；只有一个受环境异常影响会话中的短请求，不能建立正常 Gen5 的关键路径结论。16K CPU、L2/L1/stall/occupancy 与缓存状态对照待继续。
  - 继续使用[观察与待验证假设](tobeo-20261022/qwen36-profiling/bottleneck-notes.md)界定范围，不将 GPU 热点当作唯一瓶颈。权限、重复编号、超时、kernel replay/TDR 的历史排障见[原记录](tobeo-20261022/qwen36-compute/README.md)，不以早期失败覆盖后续成功，也不以三个计数代替最终归因。
- [x] 完成#4347冻结布局的1K/16K匹配主线数值对照与小型任务回归。
  - 2026-10-28：[前瞻协议](tobeo-20261028/qwen36-pr4347/validation-next-plan.md)先于结果写定。两上下文各97行×248,320项，A=C、B=D全部逐位一致且有限；四臂各12/12任务通过，共48/48，覆盖JSON算术、中文、小函数执行与1K/16K检索。新增文件参数入口只链接既有库，原exe/库哈希不变且原入口数值复核通过；原始GEN终止token评分误判已修正，保留原输出和原评分。见[报告](tobeo-20261028/qwen36-pr4347/README.md)与[小型证据](tobeo-20261028/qwen36-pr4347/validation-next-summary.json)。仅Windows/CUDA、冻结驻留和确定性小样本，未验证动态换槽、普遍质量等价或速度；下载持续，日常服务恢复loaded=true。
- [ ] 按正确性、配对测量和上游范围要求完成交付。
  - 2026-10-29 P1受控验证完成：[Flash-Next报告](tobeo-20261029/flash-next-affinity/README.md)的performance-04于17:51完成15次启动/45条请求，功能18/18、输出/草稿数量及31次环境检查通过；收尾回读完成。measure四轮选P、一轮选all；代码/英文/中文合计配对all/P中位数1.0019/0.9996/1.0016、P较快4/2/3对，均未达稳定方向与幅度标准，不写校准补丁或变更日常默认。P累计CPU时间较低不代表能耗/关键路径改善。此前15+3条环境失败计时隔离；下载v5续传、日常loaded=true、配置SHA未变。仅当前单机受控配置，完整质量、日常默认扩展及跨后端交付继续未完成。
  - 2026-10-29 下载状态复核：DeepSeek七份已确认235.95/273.80GB（86.18%）、5份此前校验通过，v2因分段ETag不一致退出；重新探测与断点标识相同后，以v3日志和最多4次外层重试恢复四路续传，短检确认实际新增数据。见[下载续传记录](tobeo-20261028/deepseek41-community/README.md)。仅恢复下载，不将其计作完整下载、模型可运行或社区案例完成。
  - 2026-10-29 发布进展：经授权已在#4335/#4347原PR补充独立反馈，并提交[报告PR #4577](https://github.com/Niko1221/Strata/pull/4577)。仅一个bench/results目录，含公开输入、40次正式运行/20对数据、失败记录及原/新增脚本各自验证范围。线上回读、作者、head与113文件范围核验通过，Intake check成功、sweep跳过；未合并，未将发表当作完整优化/质量/跨后端交付完成。见[发布记录](tobeo-20261028/qwen36-publication/README.md)。
  - 2026-10-29 较早快照（发布前，后续见上方发布记录）：#4335原head独立构建、数值/24条任务、20次正式运行及环境收尾均完成；Windows/Blackwell长输入收益与短输入代价已写入[报告和本地英文反馈草稿](tobeo-20261028/qwen36-pr4335/README.md)。未发布，未改默认；完整质量、动态换槽、更多上下文/batch/MTP及跨后端仍未验证。原自由生成身份失败不撤销，完整交付继续未勾选。
  - 2026-10-28 历史快照：已另立协议完成固定历史五组配对（下项），结果为generation/prefill取舍，未证明完整请求加速；原自由生成身份失败、动态换槽、完整质量和跨后端范围仍保留。下一项独立验证chunk2048/4096及#4335，不同时改packed策略；未对外发布或变更日常默认。
  - 2026-10-28 后续：已补16K教师强制与48条小型任务回归，数值/任务门槛通过；原256token身份失败不撤销，不重新使用旧性能数据。下一步另立固定强制历史、固定工作量的五组配对协议，区分受控布局成本与自由生成性能；本轮未运行新性能配对、未完成交付或对外发布。
  - 2026-10-28 本轮执行完成并按门槛停止：当前源码基线通过，#4347在Windows/Blackwell实际触发；1K/16K的256token首组分别于第76/19输出token分叉，因此未运行剩余四组、不计算等价加速比。完成固定布局生成及97行全词表的两类教师强制诊断，报告与小型数据见[首轮结果](tobeo-20261028/qwen36-pr4347/README.md)。未做完整质量验收、16K教师强制、跨后端或#4335；日常0.1.52服务和下载均恢复。整体交付继续保留未勾选。
  - 2026-10-28 再评估后：当前源码基线与 #4347/#4335 独立验证均未执行；历史GQA局部门禁不替代新候选门禁。以[新顺序](tobeo-20261028/topic-reassessment/README.md)推进，未完成项继续保留未勾选。
  - 2026-10-28：传输状态已恢复，当前主线基线、#3641 当前主线集成候选、16K 实模门禁、至少五组交替配对和最终贡献范围仍待完成。旧续跑脚本须先更新版本与归档入口；新结果产出前不填加速比，不把旧 base 的候选结果当作当前发布结果，也不把已有上游实现记作自写优化。
- [x] 在原亲和性讨论补充实测结论和公开证据，并收尾本轮三项选题。
  - 2026-10-29：[#1912评论](https://github.com/Niko1221/Strata/pull/1912#issuecomment-6494468322)已发布，作者/全文回读一致；22份脱敏证据在fork固定commit `d973440a`逐文件回读通过，离线核对45请求/15日志/15组配对通过。未新建PR、issue或重开讨论，fork main与#4577未改。连接器403后使用本机同账户gh发布。见[发布记录](tobeo-20261029/flash-next-affinity/README.md)；[选题文档](tobeo-20261028/topic-reassessment/README.md)已写明三项最小验证收尾及下一步DeepSeek社区案例/正常工况profiling条件，未将未执行扩展标完成。
- [x] 评估Flash-Next亲和性成果的公开贡献定位。
  - 2026-10-29：[发布评估](tobeo-20261029/flash-next-affinity/README.md)已检索相关开放/关闭issue和PR，复核#1912、#3522、#4401及既有#4577，阅读贡献/社区测量规则。建议以独立受控报告补原讨论，必要时另提结果型Benchmark PR；不报稳定错选bug、不把累计CPU时间称为省电。仅完成评估，英文脱敏独立证据包及新成果发布尚未执行。
- [x] 完成Flash-Next IQ3_S现有CPU布局受控五轮性能对照及收尾复核。
  - 2026-10-29：[正式报告](tobeo-20261029/flash-next-affinity/README.md)、[45条小型汇总](tobeo-20261029/flash-next-affinity/summary.json)、[全部15组配对](tobeo-20261029/flash-next-affinity/paired-results.csv)。官方0.1.52，实际3107slots/6092MiB，三种合成输入各256token输出，15次独立启动、每臂96token预热、五轮预定顺序；45条完整输出/草稿数量一致，31次下载停止/断点未变检查通过。HtoD24.846733→24.853699GB/s、漂移0.0280%；恢复日常loaded=true、配置SHA未变，下载原命令v5后台续传。未复现稳定错选，不改校准器或默认；仅Windows/CUDA当前硬件受控参数，不代表日常默认、并发、完整质量或其他CPU/后端结论。
- [x] 完成Flash-Next IQ3_S现有CPU布局三臂的受控功能门槛。
  - 2026-10-29：[报告及后台交接](tobeo-20261029/flash-next-affinity/README.md)、[前瞻协议](tobeo-20261029/flash-next-affinity/experiment-plan.md)、[公开输入](tobeo-20261029/flash-next-affinity/workloads.json)。官方0.1.52、实际3107slots/6092MiB、spec4/min-p0/lookup0/suffix0下，all/P/measure各三条256token输出及草稿数量一致，另六任务各模式全过（18/18）。功能阶段下载运行，时长不作性能证据；后台五轮矩阵、正式性能结论、完整质量及日常默认配置收益均未完成。
- [x] 完成#4347冻结驻留、固定历史的五组交替性能配对。
  - 2026-10-28：[前瞻协议](tobeo-20261028/qwen36-pr4347/fixed-history-plan.md)先于计时写定；两输入各五对，共20次独立进程，96token强制历史、97次argmax、无完整logits写盘，每次与对应臂既有验收输出相同、槽位63/89、0换槽。1K合计A/B中位数0.9949（B快2/5），16K为0.9834（B快0/5）；16K generation为1.0395（B快5/5），prefill代价抵消该收益。见[小型汇总](tobeo-20261028/qwen36-pr4347/fixed-history-summary.json)与[10对原始毫秒](tobeo-20261028/qwen36-pr4347/fixed-history-pairs.csv)。HtoD前24.860822/后24.835640GB/s，漂移0.1013%；下载恢复、日常服务loaded=true、配置哈希未变。仅固定历史Windows/CUDA成本对照，不代表原自由生成协议、质量等价或普遍加速验收完成。
- [x] 核对DeepSeek下载失败并恢复已固定版本的断点续传。
  - 2026-10-29 19:02原七文件下载完成，本次重新全量计算SHA-256及核对大小7/7通过；8K/full/文本/单卡只读plan和原样ISTA pack recipe准备完成。signed feed选定sm120专用0.1.52包，原安装器0 bytes后切curl续传；19:11包91.76/422.15MB持续增长，尚未安装或加载。证据见[案例准备记录](tobeo-20261029/deepseek41-case/README.md)。目录整理按先完成案例后迁移的顺序，未执行搬迁。
- [x] 核查 #4605 评论参数适配并归档有界实验结果。
  - 2026-10-29 后验核查 edt-xx 评论：实际专用引擎拒绝 `--ple-io direct`；匹配构建另有 `DS4_EG_DIRECT`。受保护 64GB store 小对照已执行，B1 日志进入 Engram direct 路径，但 1K 输出身份门槛失败，按预案停止；未见明显系统 commit 回收，未确认自动预算修复。Qwen 恢复及配置 SHA 通过；见[参数与实测边界](tobeo-20261029/deepseek41-case/edt-xx-check/README.md)。
- [ ] 完成 DeepSeek Engram direct 的完整 ABBA 与输出等价验证。
  - 2026-10-29：本次计划在 B1-1K 后因输出身份门槛停止；剩余 B1-4K/B2/A2 未运行，没有等价性能或自动预算修复结论。后续须先区分基线重复性与读取字节问题，再另立协议；本项不影响此前已完成的原配置使用案例。
- [x] 核对目录整理中 Qwen3.8 IQ3_S 的归属与运行引用。
  - 2026-10-29 扩展为整个 `D:\Models\Strata` 的只读盘点：11 个子目录及根目录散文件已记录用途、逻辑大小和处置建议，证据见[逐目录报告与 inventory](tobeo-20261029/model-directory-audit/README.md)。确认 `mtp/rt` 是日常 Qwen3.8 的直接运行依赖；原始 tensors、量化 GGUF、两个模型的 packs 和下载残留分开识别。本次未搬迁、未删除，未全量重算哈希或完成全部路径依赖审计。
  - 2026-10-29：确认 `D:\Models\Strata\IQ3_S` 含两份 Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S 权重及完成标记，`strata-iq3_s.json` 第 7、9 行引用其旧绝对路径；`D:\Models\Qwen` 已有其他 Qwen 家族模型。本次仅盘点与确定建议目标，没有迁移或修改运行配置。
- [x] 完成模型与 Strata 配套目录的独立迁移及验收。
  - 2026-10-29 23:46完成：Qwen3.8 IQ3_S、MTP、按模型拆分的 packs 及 DeepSeek 主权重/共享文件已归入家族目录；引擎原位保留，历史与残留归档。17 项移动、110/110 完整 SHA-256、长度/文件标识、配置仅计划路径替换检查通过；DeepSeek 新路径 pack-info/实际加载/Paris 请求通过，日常 Qwen 恢复/Paris 请求通过且 draft_n=3，冻结控制器未变。证据及回退材料见[迁移报告](tobeo-20261029/model-directory-audit/MIGRATION.md)。未重跑长期性能实验，Qwen3.6 仅验证 tokenizer 文件迁移及引用，没有新增该模型推理验收。
  - 建议目标为 `D:\Models\Qwen\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S`，与 DeepSeek 家族整理一并规划。迁移前盘点 MTP、pack 与其他实际路径依赖；卸载日常模型后再搬迁，修正运行引用、校验并恢复服务。历史测量证据保留原路径，另记迁移映射。
- [x] 完成DeepSeek V4.1 Flash IST-DAS 2.25bpw Windows单卡使用案例。
  - 2026-10-29后续经授权发布[#4605](https://github.com/Niko1221/Strata/issues/4605)：聚焦专用DeepSeek自动store的Windows commit余量，引用#1607并保留手动保护/失败边界。原始事件补核145.637/145.730GB系统commit，分页文件澄清为初始4GB/最大8GB。用户fork独立证据分支commit72ff3a29，25文件/5.96MB；52次HTTP、52条native timing、4384采样离线核验及25文件线上字节哈希、issue作者/正文回读通过。未创建PR、未修改fork main/默认或引擎源码，未确认根因/修复；见[发布记录](tobeo-20261029/deepseek41-case/PUBLICATION.md)。
  - 2026-10-29社区反馈评估：在线检索并读取#1607/#4362/#4426等相关正文/评论，确认维护者今日关闭benchmark PR并说明筹备网站收录。建议聚焦DeepSeek专用后端Windows commit余量的新issue并引用旧讨论，完整手动配置案例作证据；不冒充#4362复现、不直接开修复或纯跑分PR。未发布/上传，公开包脱敏与整理未完成，见[投稿评估](tobeo-20261029/deepseek41-case/PUBLICATION_ASSESSMENT.md)。
  - 2026-10-29 20:10完成、20:12后验收：原七文件全量SHA、专用0.1.52签名/哈希与pack-info通过；保留自动预算提交耗尽、80GB store触及94%保护两批失败。独立64GB store/1536MiB显存保留、8K/full文本配置完成九次功能请求、1K/4K各三次256输出及1844.141秒/36条连续请求，无请求错误；20:10:30恢复Qwen、20:12实时health和配置SHA相同。52次HTTP/189份证据离线核验通过并注明两条功能汇总messages引用差异；报告/数据/曲线见[最终案例](tobeo-20261029/deepseek41-case/REPORT.md)。短矩阵decode中位7.1/7.2tok/s，后段英文1K变慢保留；仅本机手动配置短期案例，不代表默认、8K实输入、完整质量、跨后端或对外发布完成。
  - 2026-10-29 19:40：execution-01自动预算遇Windows提交耗尽；execution-02的80GB store完成局部功能/性能后触及94%保护，均保留失败及Qwen恢复证据。execution-03改为独立64GB store、1536MiB显存保留，原量化/8K/full不变；九次功能请求及1K/4K各三次256输出通过，19:38:57起进行至少30分钟连续请求。按用户要求停止前台监看，后台PID26304继续并自动尝试恢复日常Qwen；完整连续运行、最终恢复、离线核验和最终报告尚待完成，保留未勾选。见[运行交接](tobeo-20261029/deepseek41-case/README.md)。
  - 2026-10-29 19:20：422,151,870-byte专用0.1.52 CUDA13/sm120包下载及SHA/可信签名/逐文件/manifest对signed feed核验通过，独立安装完成。pack-info退出0，六个引用文件存在且长度足够、tensor device type齐全；见[案例记录](tobeo-20261029/deepseek41-case/README.md)。尚未GPU加载、功能/性能或连续请求，保留未勾选。
  - 2026-10-29：七文件重新全量校验、只读plan、pack准备完成；专用引擎下载中。尚缺引擎签名/文件最终验收、pack-info、8K full加载/功能、1K/4K各三次及约30分钟连续请求，不能以准备步骤代替案例完成。协议与证据入口见[案例目录](tobeo-20261029/deepseek41-case/README.md)。
  - 2026-10-29 17:09：核查v4停滞实际为下载树线程Suspended，17:02时已249.94/273.80GB（91.28%）、六项verified；短暂恢复后用户说明有试验在跑，已重新挂起同一下载树，保留断点。未检查或修改试验，未确认最初挂起者；见[状态记录](tobeo-20261028/deepseek41-community/README.md)。本轮只完成状态确认及恢复暂停，完整下载与推理未完成。
  - 2026-10-29 16:27：排查确认同一固定ModelScope版本在本轮请求中返回不同ETag，旧下载器重复拒绝分段；两文件固定revision的大小/SHA元数据一致，六处64KiB本地/远端抽查相同。停止v3后启用本地fresh-range脚本，保留断点、每段重新获取地址、两文件各两路独立续传，最终仍须全文件SHA。语法和五项HTTP响应校验案例通过，约45秒新增234,881,024 bytes，两文件均增长且无新错误；后台PID11260/23764、`download-v4.*.log`，见[恢复记录](tobeo-20261028/deepseek41-community/README.md)。本次完成排查及实际恢复，网络自动重试/完整下载/推理尚未验收，整体交付保留未勾选。
  - 2026-10-29 16:18只读复核：目标仍为ISTA-DASLab IQ2_XS/2.25bpw，Unsloth两项是安装配置引用的元数据与DSpark配套文件；确认236.59/273.80GB（86.41%），进程仍在但短检无增长，DSpark反复出现版本标识不一致及连接停滞提示。核对单文件顺序调度及已有正式文件/校验标记，未重新计算大文件哈希或更改任务；见[下载记录](tobeo-20261028/deepseek41-community/README.md)。本次仅完成来源与状态解释，不新增完整下载或推理完成项。
  - 2026-10-29：确认进程退出、留存失败状态、区分分段ETag错误与旧回退超时；当前两文件的Range/大小/ETag与断点相符，未改变版本或校验。脚本语法检查及实际续传增长通过，新增外层重试耗尽分支本轮未触发；保留37.85GB左右未完成部分继续后台运行。证据入口为[下载记录](tobeo-20261028/deepseek41-community/README.md)及本机`download-v3.*.log`。完整模型下载与推理测试仍未完成。
- [x] 发布DeepSeek Windows提交内存问题及脱敏使用案例证据。
  - 2026-10-29：已在 [#4605 跟进评论](https://github.com/Niko1221/Strata/issues/4605#issuecomment-6499143642)澄清本次未设置 `--ple-io ram`、DSpark 未加载、101.3GB 来自专用 DeepSeek RAM store，并请求对方补充模型、版本、系统及有效 PLE 设置；未把普通用户的 Signal 15 案例当作同根因或维护者结论。
  - 2026-10-29：上游issue#4605与用户fork固定commit证据均已发布并回读核验；仅问题报告及独立证据目录，不是修复PR或纯成绩PR。真实运行与事后脱敏/校验范围分开记录，证据及限制见[发布记录](tobeo-20261029/deepseek41-case/PUBLICATION.md)。
- [x] 发布两项独立验证反馈与报告型PR。
  - 2026-10-30：作者跟进询问#4347的16K prefill分项与`ne/3`阈值后，已发布[定向回复](https://github.com/Niko1221/Strata/pull/4347#issuecomment-6514456594)。回复补充原固定历史五对的prefill中位数7161.8/7478.3ms、配对比0.9591及5/5方向，并明确这是旧head、chunk2048、冻结驻留下同一请求的阶段计时，不是新跑的prefill-only workload，也未在rebase后复测；现有63→89槽位证据不足以主张调整阈值。评论以`@rynwang`和上下文说明指向所答问题，已通过GitHub API回读核验。本次未新增GPU测量、代码或默认变更。
  - 2026-10-29：[#4335评论](https://github.com/Niko1221/Strata/pull/4335#issuecomment-6488876445)、[#4347评论](https://github.com/Niko1221/Strata/pull/4347#issuecomment-6488877876)、[报告PR #4577](https://github.com/Niko1221/Strata/pull/4577)均已发布并回读核验。证据包完成脱敏、精确输入归档、离线统计/原日志核对、Git字节哈希、链接与范围检查；原实现归属不变。Intake check成功、sweep跳过；未声称全量CI、维护者认可或合并。范围见[发布记录](tobeo-20261028/qwen36-publication/README.md)。
- [x] 完成#4335独立chunk数值/任务验收与固定历史五组配对。
  - 2026-10-29完成，10-28开始并按开始日期归档。原head `bdf0bce2` 独立Windows/CUDA构建及16项选定测试通过；1K/16K各五臂，主线/PR同chunk的97行全词表logits逐位相同，自动实选4096；2048/4096各12条任务通过。未叠加#4347，槽位63→50；20次正式请求均与对应chunk数值验收argmax一致、0换槽。16K合计约10.48→8.90s，配对比中位数1.1788（4096快5/5）；1K约3.33→3.40s、0.9779（快0/5）。HtoD前24.833714/后24.855839GB/s、漂移0.0891%；下载恢复、日常服务loaded=true、配置哈希不变。见[报告](tobeo-20261028/qwen36-pr4335/README.md)、[小型汇总](tobeo-20261028/qwen36-pr4335/summary.json)和[全部10对毫秒](tobeo-20261028/qwen36-pr4335/pairs.csv)。仅冻结驻留、32K上限、96token固定历史及小样本任务，不代表普遍质量、动态缓存或默认策略全面验收。
