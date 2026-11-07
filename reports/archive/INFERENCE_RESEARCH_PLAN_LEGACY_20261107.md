# 旧版推理研究方案与阶段判断

归档日期：2026-11-07。本页保留当时的完整计划及各阶段取舍，正文中的“当前”“下一步”和优先级均为历史判断。现行主线见[研究计划](../INFERENCE_RESEARCH_PLAN.md)，实际结果见[执行记录](EXECUTION_LOG.md)。

# Strata 推理优化与 Profiling 实践计划

制定日期：2026-10-21。用途：指导本机实验、开源贡献和求职作品准备。

设备依据已有记录：i7-12700、RTX 5060 Ti 16GB、128GB DDR4、Windows 11。主线使用现有 Qwen3.6-35B-A3B UD-Q4_K_XL，Flash-Next IQ3_S 用作混合调度研究的另一条路径。本计划不要求重新下载模型。

这是一份研究计划，不是性能报告。下面的时间是工作安排建议，验收条件是完成标准；没有承诺加速幅度或 PR 合并。2026-10-29实验固定 `46c152a1310f77cd2f0ce2c7cd213962df14fe83`，源码引擎0.1.53；该基线与旧 `5e8a4cca` 的测量继续独立保留。2026-10-30晚间按用户指定已更新项目至upstream `870aedd9e1ebe1c91f94da93b59af17729f6c5c0`（app0.2.8/engine0.1.54），后续已在此提交独立构建并通过本机受控数值/布局门槛（20:09:49），详见相应历史报告；此处的日常服务版本也只代表当时状态。

## 2026-11-01 的研究取舍（历史快照）

**当前阅读入口见[reports/README.md](../README.md)，本节保留 2026-11-01 的判断。** 当前主线仍是Qwen3.6在本机16GB hybrid工况的端到端瓶颈与可验证改进；不是以采集数量或写一个代码PR为完成标准。

- 已有成果：三项最小验证与DeepSeek案例收尾；PR3905原复制切片的独立正确性/五组性能/机制验证及补充已发布；可复现基线、CPU/job级证据和870aedd9数值/布局门槛已完成。
- 成果交付入口：[阶段成果与收获](../RESEARCH_OUTCOMES.md)汇总实测收益、负结果、诊断边界、已有GitHub贡献及复盘；[英文文章草稿](../tobeo-20261101/research-retrospective/PUBLIC_DRAFT.md)仅为本地发布准备，不等于新增材料已外发。
- 当前判断：GPU迟启动在受控trace中重复出现；关闭原生job标记后仍有约566–632us API→GPU启动中位间隔。CUDA profiler仍在所有相关trace中，原版根因和可回收延迟未确认，不据此直接修改等待/stream/flush。
- 2026-11-01取舍收尾：用户指出连续采集缺少结束点，本轮停止自动延伸诊断链，见[收尾决定](../tobeo-20261101/qwen36-wpr-review/DECISION.md)。WPR包级工具门槛已通过，但1K实模ETW/plain对照没有启动，移为未执行备选，不再是默认下一项。现有证据作为有界验证与诊断成果交付；暂不实施flush/stream/等待策略改动，原版根因和新优化收益保留未完成。以后新增实验须先有具体改动/假设、决策指标、最小矩阵和停止条件。
- 后续交付链：足以支撑的瓶颈假设 → 单一最小改动 → 数值/功能门槛 → 同日无profiler配对收益/波动 → 有范围的报告或贡献。当前迟启动方向尚未完成这条优化闭环。

此前逐日记录已移到[状态历史](../archive/RESEARCH_STATUS_HISTORY_20261031.md)，保留原始证据和当时判断。它们不再充当当前“下一项”；实际完成仍按第11节简表、[执行记录](../archive/EXECUTION_LOG.md)与报告核对。

## 1. 目标与取舍

选型解释（2026-10-28 补充）：最初的[选题池](../tobeo-20261021/INFERENCE_OPTIMIZATION.md)优先考虑 Flash-Next 的亲和性和会话缓存，并非未考虑该模型。总计划选择 Qwen3.6 作为深入 CUDA 主线，是因为上游已有明确的长上下文问题与可定位的 attention 路径、现有 Q4 模型和门禁可用；后续本机时间线又支持继续调查。Flash-Next 已获得固定缓存的 P 核收益证据，但校准功能和缓存机制本来就存在，是否需要新改动仍须证明。此为研究问题与实验范围的选择，不是模型能力或用户价值排名。若优先服务日常 Flash-Next 体验，或 Q36 候选无收益/与上游重叠过大，可转向 Flash-Next。

主项目（2026-10-29 接续）：**定位 Qwen3.6 在16GB hybrid正常工况的端到端瓶颈，以新源码基线和时间线决定下一项最小改动。** #4347/#4335 的独立验证已完成并保留取舍结论；Flash-Next 现有布局验证没有复现稳定错选，不编写新校准器。选题依据见[模型与选题复评](../tobeo-20261028/topic-reassessment/README.md)。

近期交付：**源码基线、正常工况CUDA/NVTX、已有复制方案验证及原线程发布、CPU IP/调度、逐stage复制依赖，以及受控job级依赖与wall账本均已完成。** 补充材料已发布至原PR3905；无插桩全系统根因和最小改动选择仍待。870aedd9已独立构建并通过基线门槛，新提交受控trace已重复观察到迟启动，off/on采集对照已完成；下一项先验证无CUDA profiler的系统GPU队列观测，再聚焦提交/调度残差；GQA与MTP不自动进入。

2026-10-29阶段收尾：#4347、#4335及Flash-Next现有布局三项最小验证已完成，Qwen3.6已发布#4577，亲和性按用户选择仅补[#1912评论](https://github.com/Niko1221/Strata/pull/1912#issuecomment-6494468322)、不另提PR。DeepSeek 单卡案例亦已完成文件/引擎校验、功能、1K/4K各三次及30分44秒连续请求，并发布问题与脱敏证据。没有稳定亲和性错选证据，不编写校准器；没有新的正常工况 profiling 结论，不直接恢复 GQA。具体进入/停止条件见[复评收尾更新](../tobeo-20261028/topic-reassessment/README.md)。

主项目应形成完整证据：可复现 workload → 时间线 → 瓶颈假设 → 单一改动 → 正确性验证 → 端到端收益与限制。小贡献用于熟悉构建、测试和审阅流程。不要同时开展多个引擎大改。

| 优先级 | 方向 | 适合展示的能力 | 何时进入 |
| --- | --- | --- | --- |
| P0 | Qwen3.6正常工况归因与prefill流式复制取舍 | GPU/传输重叠、CPU/GPU关键路径、布局与延迟归因 | 基线、复制验证/发布、CPU IP与受控job路径已完成；新补充已发布；870aedd9新基线已通过，迟启动已在新提交四trace复现，off/on采集对照已通过，下一项为系统GPU队列探针，随后提交/调度诊断；无插桩全系统根因仍待 |
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

以下更新优先于文中仍保留的 10-23 续跑建议；历史数据和版本不改写。完整依据与实验设计见[恢复后的研究取舍](../tobeo-20261028/research-next-steps/README.md)。

- HtoD 已恢复约 25 GB/s，正常性能测量的环境阻塞解除；每轮仍须同日确认带宽、资源工况和实际引擎。
- 新基线目标改为 `5e8a4cca` / v0.2.7，不再补过时的 v0.2.3.1 基线。`7ddc17a3` 至当前主线的 Q36 改动是 sampling 提取与 history token 越界修复；attention 未变属静态审查，不能代替重新构建与门禁。
- #3641/#3678 当前仍 open，固定 head/base 未更新，但本次 API 均返回 `mergeable=true`；旧“不可直接合并”只保留为历史快照。先集成到当前主线并验证，不再把等待作者 rebase 当作唯一前提。
- #3700 的[新评论](https://github.com/Niko1221/Strata/issues/3700#issuecomment-6379679338)已覆盖 int8 decode、Tensor Core 与 fused prompt attention，暂不另起重叠实现。优先补 #3641 的 Windows/Blackwell、真实 Q4、16K 独立正确性与性能证据。
- 执行顺序：当前源码基线 → 当前主线候选集成与 1K/16K 门禁 → MTP 0 五组无 profiler 配对 → 正常工况关键路径与访存归因 → GQA × MTP 0/2 收益边界。最终瓶颈与独立改动范围仍待测量决定。
- 旧 `run_ab.py` 与 Compute 入口固定历史路径/二进制，先改造 provenance、日期目录和控制参数再运行。本轮仅完成评估，没有切换日常服务、运行 GPU 实验或发布上游消息。

## 2. 已有证据与不能混用的结论

### 历史：2026-10-28 再评估后的执行顺序

本节记录三项验证前的安排及首轮停止状态，已由页首当前执行入口和第11节后续完成记录接替；不再按下列“尚未开展”继续执行。

执行后更新：[当前源码基线与#4347首轮](../tobeo-20261028/qwen36-pr4347/README.md)已完成构建、所选基线门禁和数值诊断；首组256token输出身份检查未通过，因此剩余四组性能配对按预设停止。下一步先明确允许专家布局变化的数值/任务验收，不能继续把该政策当作整条生成bitwise不变的变化；#4335及其他模型实验尚未开展。

在10-28当时，本节优先于同日早先接续建议以及阶段D的旧排序。当时执行`git fetch upstream main --no-tags`，上游仍为`5e8a4cca`；源码没有新变化，扩大查重后发现直接针对hybrid路径的 #4335/#4347，以及校准、MTP和缓存方向的新重叠，见[复评报告与查询快照](../tobeo-20261028/topic-reassessment/README.md)。

1. 先建立当前Windows原生源码基线，验证 #4347 的packed副本/专家槽位取舍。补丁要求`slots <= 0 && vram_gib < 0`；历史固定64 slots、显式10GiB专家预算会绕过规则，不能用于该政策验收。采用自动布局，固定其他参数并记录实际槽位。
2. 再单独验证 #4335 的prompt chunk规则及2048/4096取舍，分别检查prefill、TTFT、decode、显存和数值；两项各自可信后才考虑组合。
3. P0形成明确结果后，进入Flash-Next all/P核/measure端到端验证。现有measure有意在10%以内偏向P核，不能把它直接称为选错；若确认选择造成稳定实际损失，再商定一个校准改动。避开 #3522 已处理的PCIe/draft确认噪声。
4. GQA保留为条件性后续，不另写已有KV量化、Tensor Core或fused attention。MTP诊断与宽泛缓存重写暂缓；DeepSeek仍为独立使用案例。

本轮仅做源码/讨论复核和计划调整，未构建、移植、运行新测量或向上游发送消息。阶段A/B/C历史勾选不能代表新候选验证完成。

先阅读现有材料，保留历史记录，不覆盖原始结果：

- [本机综合记录](../tobeo-20261021/REPORT.md)。
- [原选题调研](../tobeo-20261021/INFERENCE_OPTIMIZATION.md)。
- [Qwen3.6 Q4 实验](../tobeo-20261021/qwen36-q4/README.md)。
- [Flash-Next 实验索引](../tobeo-20261021/flash-next/README.md)。

现有 Qwen3.6 记录有三点需要带入新实验：

1. 默认 HTTP 条件下，虽然配置 `--mtp 2`，日志仍显示 `drafts accepted 0 of 0`。服务解析出的 penalty 等条件会影响投机路径，不能只看启动参数。
2. 原始协议纯贪婪实验观察到 MTP 吞吐改善，但全部六个输出对的 token 哈希不同。尚未定位原因，不能称为输出一致或质量等价的加速。
3. Agent 基准中后续回合没有复用 prompt token。它是待解释的现象，不能直接宣布缓存实现有 bug。

Flash-Next 已有固定实际缓存后的 P 核收益记录。该记录支持继续研究调度，但不能写成尚未实现的自动校准器带来的收益。

两种模型走不同引擎路径。不要直接照搬 Flash-Next 的亲和性、KV、PCIe 或草稿参数到 Qwen3.6；需要分别核对解析器、日志和实际行为。

## 3. 阶段 A：建立可信的构建与测量环境

完成记录：[WSL 基线（2026-10-21）](../tobeo-20261021/qwen36-source-baseline/README.md)、[Windows 原生基线（2026-10-22）](../tobeo-20261022/windows-native-baseline/README.md)。后续本机优化以 Windows 原生构建为参考，WSL 结果独立保存。已确认原生源码构建、选定测试及固定布局下四臂一致性；具体范围和未测项以两份报告为准。阶段 C 已更正 Graph 覆盖范围：64/256 专家槽位触发 hybrid 并自动关闭主模型/MTP Graph，不能把历史组名当作真实 Graph 执行证据。

上述两份基线固定的是旧 revision，完成状态只说明当时的构建链路可信。`5e8a4cca` 基线已于10-28完成，见[#4347报告](../tobeo-20261028/qwen36-pr4347/README.md)；本轮改为固定 `46c152a1`，独立构建并验收，见[新基线协议](../tobeo-20261029/qwen36-repro-baseline/experiment-plan.md)。不要覆盖旧目录，也不要用“Qwen3.6 核心改动很少”替代构建和门禁。

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
- [Qwen3.6 文档](../../docs/QWEN36.md)：已有实现、验证方法及限制。

验收：源码基线可运行；能说明运行的是哪个 exe、哪些参数和哪个模型；相关基线门禁有真实结果。失败项先记录、定位，不能默认为新补丁问题或直接忽略。

## 4. 阶段 B：复现长上下文曲线

完成记录：[Windows 原生上下文曲线（2026-10-22）](../tobeo-20261022/qwen36-context-curve/README.md)。固定 32K 配置上限、512 prompt chunk、64 专家槽位，完成 1K/4K/8K/16K × MTP 0/2 × 3 次的 24 条测量；12 对输入及输出 token 哈希一致。已生成 ms/token、协议 TTFT 与配对 MTP 加速比曲线，保存资源样本。7 个 worker 的亲和性一致，其他线程由 OS 调度；单一合成 workload 的结果不能替代阶段 C 的 kernel 归因。24K/32K 输入与并发扩展未做。

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

2026-10-30新增：[新基线正常工况CUDA/NVTX报告](../tobeo-20261030/qwen36-systems/README.md)已完成四格采集和同日输出对照，阶段观察见[一页记录](../tobeo-20261030/qwen36-systems/bottleneck-notes.md)。prefill流式复制与decode attention分别调查；CPU采样权限不足，完整CPU/关键路径归因及Compute计数仍待完成，以下旧trace不能替代新条件。

2026-10-22 进展：[Nsight Systems 报告](../tobeo-20261022/qwen36-profiling/README.md)与[瓶颈观察](../tobeo-20261022/qwen36-profiling/bottleneck-notes.md)。已完成原生 1K/16K × MTP 0/2 四组完整进程采集，分析仅筛选预热后 decode；每条输出 64 token，与阶段 B 对应前缀一致。16K 的 k_attn_part 区间占所选窗口约 22.05%/34.45%，支持下一步 Compute 检查；CPU 时间线和访存根因未测，尚未决定最终内核改动。旧工具兼容试采和触发截短试采均独立保留，未混入结论。

2026-10-23 进展：[Compute 1K/16K 三指标](../tobeo-20261023/qwen36-compute/README.md)均通过，代理管理员权限与实际计数探针也已验证。新增[1K CPU IP/调度试采及环境诊断](../tobeo-20261023/qwen36-profiling/README.md)：同日无 profiler 的 prefill 也明显慢，独立 HtoD 约 1.73 GB/s，历史引擎探针约 25 GB/s；NVML 与 PnP 链路报告有冲突。环境恢复前暂缓正常条件的性能 A/B，尚缺 L2/L1/stall/occupancy 和完整 CPU 归因。已有上游 [PR #3641 的局部正确性验证](../tobeo-20261023/qwen36-pr3641/README.md)通过，未声称自己的优化加速。

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

依据 [CONTRIBUTING.md](../../CONTRIBUTING.md)、[AGENTS.md](../../AGENTS.md) 和[社区测量指南](../../docs/COMMUNITY_BENCHMARKS.md)：

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

这里仅保留最近完成项和明确暂停项。此前所有勾选、未勾选条目及逐次证据见[执行记录与原始清单](../archive/EXECUTION_LOG.md)；旧的 `[ ]` 不能自动视为当前待办。每次完成本仓库任务前核对本节，以真实结果标记完成日期、证据和验证范围。

- [x] 2026-11-07：合并上游 `146df3c46`，本地提交 `c4d90462`；随后在 RTX 5060 Ti 上完成 CUDA 0.1.58 的三个引擎目标构建和 Qwen3.8、Qwen3.6、DeepSeek V4.1 各一次短请求。证据：[构建与模型验证状态](../../build-native-baseline/merge-c4d90462/status.json)。仅覆盖本机加载与短请求；长上下文、并发、性能和其他后端未验证。
- [ ] Unsloth Qwen3.8-Flash-Next Dynamic v3.1 `UD-IQ3_XXS` 四分片下载与校验。2026-11-07 因 ModelScope 直连速度过慢按用户要求暂停；部分文件保留在 `D:\Models\Qwen\Qwen3.8-Flash-Next-Unsloth-UD-IQ3_XXS-v31`。未完成全量下载、校验或模型运行；不自动恢复。详情见[原始清单](../archive/EXECUTION_LOG.md)。
- [x] 2026-11-07：整理 `reports` 根目录的阅读入口、计划、当前状态与历史流水账。证据：[索引](../README.md)、[执行记录](../archive/EXECUTION_LOG.md)和本次文档差异。仅重组文档与链接，未新增 GPU 实验、上游发布或模型下载。
