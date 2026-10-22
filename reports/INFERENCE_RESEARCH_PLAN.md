# Strata 推理优化与 Profiling 实践计划

制定日期：2026-10-21。用途：指导本机实验、开源贡献和求职作品准备。

设备依据已有记录：i7-12700、RTX 5060 Ti 16GB、128GB DDR4、Windows 11。主线使用现有 Qwen3.6-35B-A3B UD-Q4_K_XL，Flash-Next IQ3_S 用作混合调度研究的另一条路径。本计划不要求重新下载模型。

这是一份待执行计划，不是性能报告。下面的时间是工作安排建议，验收条件是完成标准；没有承诺加速幅度或 PR 合并。上游状态来自 2026-10-21 的调研，实施前需重新核对。

## 1. 目标与取舍

主项目：**定位 Qwen3.6 长上下文 decode 的瓶颈，完成一个有测量依据的 attention 优化。**

小贡献：**围绕 MTP 实际执行状态，补一项有用的诊断、回归验证或 benchmark。** 先检查是否与现有 PR 重叠，再决定具体改动。

主项目应形成完整证据：可复现 workload → 时间线 → 瓶颈假设 → 单一改动 → 正确性验证 → 端到端收益与限制。小贡献用于熟悉构建、测试和审阅流程。不要同时开展多个引擎大改。

| 优先级 | 方向 | 适合展示的能力 | 何时进入 |
| --- | --- | --- | --- |
| P0 | Qwen3.6 长上下文 attention | CUDA、访存、GQA、性能分析、数值验证 | 先完成本机复现和 profiling |
| P1 | MTP 未执行原因诊断 | 推理机制、参数解析、服务可观测性 | 确认与已有 PR 不重叠后 |
| P2 | Flash-Next 端到端亲和性校准 | 混合核调度、自动调优、实验设计 | attention 在本机不占关键路径，或主项目完成后 |
| P3 | 多会话缓存与复制成本 | Serving、状态管理、RAM 与延迟取舍 | 有稳定的交错会话 workload 后 |
| P4 | Flash-Next CUDA Graph 与执行空隙 | CPU/GPU 时间线、执行重叠 | trace 证明空隙确实值得优化后 |

## 2. 已有证据与不能混用的结论

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

2026-10-22 进展：[Nsight Systems 报告](tobeo-20261022/qwen36-profiling/README.md)与[瓶颈观察](tobeo-20261022/qwen36-profiling/bottleneck-notes.md)。已完成原生 1K/16K × MTP 0/2 四组完整进程采集，分析仅筛选预热后 decode；每条输出 64 token，与阶段 B 对应前缀一致。16K 的 k_attn_part 区间占所选窗口约 22.05%/34.45%，支持下一步 Compute 检查；CPU 时间线和访存根因未测，尚未决定最终内核改动。旧工具兼容试采和触发截短试采均独立保留，未混入结论。

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

建议用时：3–5 天，依阶段 C 结果调整。

### 第一版范围

优先选择一个机制：K 读取的协作加载或 tile 布局。先保持 K/V 精度、缓存容量、专家预算和外部行为不变。

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

测试 A→A、A→B→A、A→B→C→A、长会话夹短请求、真实工具调用回合。比较关闭与可容纳快照的缓存预算，测 reused tokens、TTFT、保存/恢复时间、复制字节和 RAM 峰值。

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

每次任务结束前复核本清单：已实际完成的项目打勾，并记录日期、证据与范围；部分完成保留未勾选并说明进度。后续扩展配置或 workload 时，已有勾选不替代新条件下的验证。

最近复核：2026-10-22。阶段 A、阶段 B 最小矩阵及阶段 C 的 Systems 时间线已完成；Compute、CPU 栈、访存根因和优化交付未完成。Graph 覆盖范围已更正，原 Flash-Next 服务已恢复。

- [x] 核对最新上游、相关讨论和工作区改动。
  - 2026-10-22 已核对工作区，重新读取 #2464 及后续评论，并查询包含 k_attn_part 的相关 PR（包括 #3084、#2698）；快照保留在阶段 B 目录。实验继续固定阶段 A revision，未声称运行最新 main；后续实现前仍需重新查重。
- [x] 确认源码基线、工具链、模型哈希和独立构建目录。
  - 2026-10-21 至 2026-10-22 完成，见 [WSL 基线](tobeo-20261021/qwen36-source-baseline/README.md)与 [Windows 原生基线](tobeo-20261022/windows-native-baseline/README.md)。后续主用 Windows 原生构建。
- [x] 跑通适用的基线正确性门禁。
  - Windows 原生：14 项选定测试通过；VERIFY 436,050 次比较、0 mismatch；当前内核验证、默认 Graph 请求、MTP 三组各 10/10 prompt 与参考逐 token 一致。固定 64/256 专家布局会自动关闭 Graph，故独立 Graph 路径仍未验证。范围为 8K 上限和短 prompt，未覆盖全量测试套件。
- [x] 建立固定最大上下文的 1K/4K/8K/16K 实验矩阵。
  - 2026-10-22 完成 24/24 条请求，每格 3 次、均输出 256 token；曲线、中位数、范围及测量边界见[阶段 B 报告](tobeo-20261022/qwen36-context-curve/README.md)。固定配置上限 32768，实际输入为 1025、4096–4097、8193、16385 token。
- [x] 核对真实 MTP 状态、专家布局和前缀复用状态。
  - 2026-10-22 原生短 prompt 基线：MTP 2 接受 567/786 个草稿，每层固定 64/256 专家驻留 GPU，fresh 请求日志 reused=0。新实验矩阵仍须逐次记录这些状态；本项不代表多会话缓存验证完成。
  - 同日阶段 B：24 条请求均 reused=0；MTP 0 全部 offered=0，MTP 2 全部 offered>0；6 次启动均为 64/256 固定专家槽位、slot replacements=0。12 对输出哈希一致，范围限于本轮配置和 workload。
- [x] 采集加载/预热之后的 decode trace。
  - 2026-10-22：Nsight 2026.1.3 四组完整生命周期采集后，按 NVTX 筛选预热后的 decode；图、kernel 明细和诊断见[阶段 C 报告](tobeo-20261022/qwen36-profiling/README.md)。实际 Graph 关闭；未采 CPU sampling/context switch。六项汇总检查通过，未将两批有问题的试采当作正式结果。
- [ ] 写出一个瓶颈结论，再决定最小改动。
  - 已写出[观察与待验证假设](tobeo-20261022/qwen36-profiling/bottleneck-notes.md)，确认长上下文 attention 值得深入；尚缺 Compute 访存计数和未覆盖时间的归因，故本项保留未勾选，不将 GPU 热点当作已确认根因。
- [ ] 按正确性、配对测量和上游范围要求完成交付。
