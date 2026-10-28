# 模型与选题复评：保留模型，调整研究顺序

2026-10-28，北京时间。本轮执行了 `git fetch upstream main --no-tags`，获取后的 `upstream/main` 仍为 `5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d` / v0.2.7；本地 HEAD 为 `5ebda0f7`，审查开始时工作区为空，研究相关源码与该上游无差异。日常发布引擎已是0.1.52，但当前源码的实验基线尚未重建。本报告是源码与在线讨论审查，没有新性能、正确性或GPU测量。

**建议调整选题，不换模型：Qwen3.6 改为16GB hybrid模式的显存取舍与端到端性能验证，先验证 #4347，再验证 #4335；Flash-Next 的亲和性校准升为下一项独立研究；原 GQA 验证降为后续受限任务。** 不并行开发多套引擎优化。这里的优先级是本机研究判断，不代表维护者已认可范围。

## 为什么改变原来的排序

上一轮查重集中于 attention/KV，覆盖不足以判断全部hybrid性能空间。这轮补看到了直接针对当前主线、16GB显卡和同一真实Q4模型的两个候选；它们缺少Windows验证。其意义是给本机提供更聚焦的独立验证任务，不是可以把作者实现重新提交为自己的方案。

| 新证据 | 在线状态与代码核对 | 对本计划的影响 |
| --- | --- | --- |
| [#4346](https://github.com/Niko1221/Strata/issues/4346) / [PR #4347](https://github.com/Niko1221/Strata/pull/4347) | open、未合并，作者rynwang；head `7be0a3a1`，base `5e8a4cca`。将部分packed Q8副本的显存还给专家槽位；作者在RTX4080 SUPER/WSL2报告收益，未测Windows | 优先在Windows/Blackwell上独立验证。不是本机已确认CPU瓶颈，也不预测本机收益 |
| [#4332](https://github.com/Niko1221/Strata/issues/4332) / [PR #4335](https://github.com/Niko1221/Strata/pull/4335) | open、未合并，作者rynwang；head `bdf0bce2`，base `5e8a4cca`。hybrid允许条件性4096 prompt chunk；作者未测Windows | 第二项，关注TTFT/prefill与专家槽位、decode之间的取舍；与#4347分开测后才考虑组合 |
| [#3641](https://github.com/Niko1221/Strata/pull/3641)、[#3678](https://github.com/Niko1221/Strata/pull/3678)、[#4270](https://github.com/Niko1221/Strata/pull/4270) | 均open、未合并。前两者仍为旧head `f3f2136f` / `8e7742e8`；#4270又提出默认FP16 KV及int8 | KV/GQA方向重叠更大。当前main仍为FP32 KV，不能把PR标题当成已发布能力；先不写独立KV/GQA实现 |
| [#3700新评论](https://github.com/Niko1221/Strata/issues/3700#issuecomment-6379679338) | 作者继续做int8 decode、Tensor Core和fused prompt attention，仍在请求分工 | 原“找一个没覆盖的attention机制”范围不能只排除GQA共享读取，还须覆盖这些工作 |
| [#3522](https://github.com/Niko1221/Strata/pull/3522) | open、未合并，当前base为`5e8a4cca`；处理PCIe/draft-floor确认中的噪声，明确worker/专家tier重启步骤仍用原固定门槛 | Flash-Next校准仍有待验证空间，但不能重复其噪声判定修复 |
| [#4401](https://github.com/Niko1221/Strata/pull/4401) | 已有RTX5060 Ti 16GB、i7-14700、128GB、Linux、engine0.1.52的IQ3_S协议报告 | 单纯“同显卡跑一次tok/s”新增信息较少；本机Windows/12700/DDR4的价值应落在受控亲和性验证、可复现差异或稳定性边界 |
| [#3295](https://github.com/Niko1221/Strata/pull/3295)、[#3773](https://github.com/Niko1221/Strata/pull/3773) | 均open、未合并；后者实现采样MTP并叠在#3678上；另一个同类#3676已closed但未merged | 暂不把MTP诊断作为第一项代码贡献；先区分采样语义、引擎资格判断和实际draft计数 |
| [#4423](https://github.com/Niko1221/Strata/pull/4423)、[#4002](https://github.com/Niko1221/Strata/pull/4002)等缓存工作 | 都有进行中的实现，#4002主要针对多GPU分阶段复制，#4423是batch checkpoint保留且缺GPU端到端验证 | 不另起宽泛缓存重写。本机单卡不能代替多GPU验证；若转入该方向先做特定workload的独立复现 |

复核了#4335/#4347的完整补丁及评论：作者还补充了两者组合、64K/batch压力数据；本轮未见这些讨论中的维护者范围认可。作者机器的加速数字不当作本机数据。可审阅的查询/PR元数据/评论快照见[upstream-snapshot.json](upstream-snapshot.json)。

## 两个模型各自承担什么任务

**Qwen3.6 UD-Q4_K_XL：近期交付一项有边界的独立验证。** 已有本机模型、构建链路、workload和attention历史证据；新候选又恰好涉及16GB hybrid取舍。保留这个模型仍合理，但不再承诺以原创attention内核为最终成果。第一项交付可以是确认候选有效、无收益或发现回归的验证报告。

**Qwen3.8-Flash-Next IQ3_S：下一项更贴近日常使用、也更可能形成独立代码工作的研究。** 固定缓存的历史P核收益支持继续测量，但没有验证现在的`measure`是否会作出有明显端到端损失的选择。当前`tools/calibrate.py`仍主要比较worker数量，没有把all/P核作为独立联合搜索维度；这是静态研究入口，不是已复现bug。先在0.1.52和同日环境下验证，再决定是否向维护者提出小范围校准增强。

`src/program/generate.cpp::measure_pool_affinity`有意在P核耗时不超过all的1.10倍时选P核，注释说明减少等待核心。因此研究目标要区分“愿意少用核心的策略”和“微基准未能预测真实decode损失”，不能把10%内偏向P核直接报成错误。旧[#1912](https://github.com/Niko1221/Strata/pull/1912)虽closed/unmerged，其功能已经存在当前源码；[#3262](https://github.com/Niko1221/Strata/issues/3262)已closed且维护者确认修于0.2.1，不是待修入口。

两模型之间不做只看tok/s的优劣排名。模型规模、量化、引擎路径和实际任务质量不同；没有任务质量评估时，只能分别讨论性能机制。现有文件已够用，不需新增Qwen下载或换量化。

## 新的执行顺序与停止条件

### 1. Qwen3.6：先验证packed副本与专家缓存取舍

先构建未经修改的`5e8a4cca`和独立#4347候选，记录模型/二进制哈希和工具链。完成适用门禁、1K/16K短输出与数值检查；不能把新候选启动成功代替正确性验证。

**关键修正：历史`--expert-slots 64 --expert-vram 10`不能沿用到#4347政策验证。** 补丁保留`slots <= 0 && vram_gib < 0`这一前提，固定slots或显式预算会绕过它。本次应使用自动专家预算，明确相同chunk、最大上下文、worker、缓存、采样、MTP及预热，逐次记录实际槽位。此时槽位变化是研究机制的一部分；不能声称固定布局下的纯kernel加速。

先MTP0，配置上限32K，实际1K/16K，固定一种chunk，至少五组交替配对、256输出预算；同时记录TTFT/prefill/decode、GPU/CPU/等待时间、VRAM和布局。数值差异须分清packed读取路径与CPU/GPU专家执行位置变化，必要时用独立数值参考；不因权重格式没变就承诺整条生成bitwise一致。

正确性失败先定位；收益不超过配对波动则保留负结果并停止推进该政策。确认有收益后仍需短请求、prefill、显存边界和适用MTP路径的检查，不直接改日常默认或提交候选作者已有的同一补丁。

### 2. Qwen3.6：独立验证prompt chunk，再决定是否回到GQA

以同一当前基线比较2048/4096的现有显式设置，并核对#4335规则实际选择；固定第一阶段的packed策略，避免一次改变两项。配置上限和实际prompt长度分开记录。chunk改变GEMM归约与专家可用显存，需检查输出/任务结果，不能只报prefill收益。

两个单因素结果都可信后，才做有限组合确认，不默认搭起大矩阵。若自动布局改善后长上下文attention仍在明显关键路径，再接续#3641的FP32 GQA独立验证；保留旧报告，不重复KV精度、Tensor Core或fused prompt的实现。

### 3. Flash-Next：验证布局选择是否需要端到端确认

第一轮只测现有all/P核/measure，不改校准器；同日、同构建、同实际缓存预算，记录worker和host线程布局，覆盖代码、中文、英文，至少五组交替重启。measure读取的微基准结果、最终选择与实际decode必须关联；另保留prefill负向检查。先区分布局本身与自动缓存联动，之后再测用户配置。

只在复现有实际影响且跨prompt稳定的选择损失后，考虑提出“显式校准时增加布局候选”或“重启候选复核”中的一项，不同时改PCIe/draft噪声规则，也不根据本机单点改普通启动默认。未复现问题就贡献验证结果，不为制造PR而实现新校准流程。

### 暂缓项

- 自写KV/GQA/Tensor Core attention：重叠较多，独立范围和维护者认同尚无。
- route-prior提速：[#4345](https://github.com/Niko1221/Strata/issues/4345)已有16GB实验，且[#4402](https://github.com/Niko1221/Strata/issues/4402)报告长Agent循环退化。本机16GB默认不启用，不为追tok/s主动改变模型路由语义。
- 多GPU、AMD、Metal问题：本机不能提供对应硬件验证；不把issue热度当成适合本机的研究入口。
- DeepSeek：继续作为下载后独立社区使用案例，不升为第三条优化主线。正式性能测试前要暂停大文件下载并记录背景负载，不能混入NVMe/网络竞争。

## 本轮实际交付与边界

2026-10-29 后续执行更新：下列“本轮”指最初选题复评。此后已完成当前源码基线、#4347匹配布局数值对照、48条小型任务回归，以及另立协议的固定历史五组性能配对，见[执行报告](../qwen36-pr4347/README.md)。固定历史16K generation改善未抵消prefill代价，合计五组均更慢；不据此改默认。随后固定packed、独立完成[chunk2048/4096与#4335验证](../qwen36-pr4335/README.md)：相同chunk数值门槛、24条任务及20次计时通过，4096的16K合计五组均更快、1K合计五组均更慢；报告和英文反馈草稿仅保存在本地。两项未组合，原256token自由生成身份失败和未覆盖范围均保留。

已完成：拉取并核对上游main、针对open/closed issue和PR的搜索、相关正文/后续评论、两个新候选补丁、校准源码检查、优先级与总计划更新。

未完成：新源码构建、候选移植、任何新推理或性能实验、维护者范围沟通、发布issue/comment/PR。查询是有范围的复核，未穷尽所有分支和附件。下一步应产出测量，而不是再扩展更多选题。
