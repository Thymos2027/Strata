# 这轮推理实验的成果与收获

2026-11-01。范围：本机Windows、i7-12700、RTX5060Ti16GB、128GB DDR4上的Strata推理研究。本文把实际成果、证据与未完成事项分开，供项目总结、GitHub文章及个人作品说明使用。实验依据各自固定revision，不混为一个版本或一份标准benchmark。

## 可以交付的三个成果

### 1. 已有优化的独立验证：结果、机制与适用边界

最明确的正向结果来自xyehya的PR3905原复制切片，测量固定46c152a1、原Qwen3.6 UD-Q4_K_XL、63slots/chunk2048/7workers/MTP0/packed。六份完整词表logits有限且逐位一致，四条生成门槛及20条正式请求输出相同；每输入五对无profiler交替测量。1K/16K的prefill+decode配对A/B耗时比中位数1.0825/1.1457，等价耗时下降约7.6%/12.7%，两长度合计均5/5变快。请求只含64输出，未计加载/预热，不能推广为日常HTTP或长生成加速。

机制也得到核对：16K prefill约38.67GB权重传输由HtoD转到DtoD，staging总字节守恒；320次staging的双buffer、event代际与依赖链通过。贡献在于隔离原作者复制hunk、适配/验证入口、设计并执行独立Windows实验及解释结果；实现归属原作者，不称自研内核或整套PR验收。

[实际报告](tobeo-20261030/qwen36-copy3905/README.md)、[已发布原评论](https://github.com/Niko1221/Strata/pull/3905#issuecomment-6512596830)、[已发布补充](https://github.com/Niko1221/Strata/pull/3905#issuecomment-6518999609)。

另一组有用成果是负结果和取舍：#4347释放约1.78GiB并使槽位63→89，仍可能prefill变慢、合计退化；#4335的4096 chunk在16K合计改善、1K合计及decode变慢。说明显存、驻留、上下文和请求长度会改变端到端结论，不能据单个分项替用户改默认。Flash-Next五轮45请求也未复现预定标准下的稳定亲和性错选，因此没有另写校准器。

[#4347报告](tobeo-20261028/qwen36-pr4347/README.md)、[#4335报告](tobeo-20261028/qwen36-pr4335/README.md)、[Flash-Next负结果](tobeo-20261029/flash-next-affinity/README.md)。

### 2. 有边界的性能诊断与观察扰动案例

先完成固定源码、模型/依赖/二进制身份及数值/布局门槛，再从CUDA时间线补CPU样本和job生命周期。CPU样本区分专家算术与epoch等待；job分析使用原done原子返回序号确定最后发布者，而不是仅凭最晚任务body结束。phase/token wall账本能闭合，主线程等待与并行分支不重复计时。

870aedd9上的四份插桩trace重复看到早提交晚启动；随后用同一二进制做job标记off/on的16请求/八trace对照。off原生标记为0，CUDA API退出→GPU启动中位数仍约566–632us，排除密集标记是该采集延迟的必要条件。所有这些trace仍使用CUDA profiler，不能声称未采集版本有相同延迟或认定WDDM缺陷。波动和不利样本保留，没有把GPU空隙当成可回收收益。

WPR工具探针及离线复核又建立原QPC和目标PID→device→context→packet关联：97条唯一完整render链、0未匹配、报告丢失0；绕开XML异常时区显示。它证明工具可用于包级观察，未提供实模ETW结果，也不能把ETW包当CUDA kernel。

这部分适合写“性能诊断的证据层次与观察扰动”，当前交付是可信的现象、排除范围和限制。原版系统根因、新flush/stream/等待改动及无profiler加速均未完成，已停止自动延伸采集链。

[新提交复现](tobeo-20261031/qwen36-gpu-submit-870aedd9/README.md)、[标记对照](tobeo-20261031/qwen36-observer-control-870aedd9/README.md)、[WPR/QPC复核](tobeo-20261101/qwen36-wpr-review/README.md)、[收尾决定](tobeo-20261101/qwen36-wpr-review/DECISION.md)。

### 3. 真实部署与环境边界的案例

DeepSeek V4.1 Flash IST-DAS2.25bpw在Windows/16GB VRAM/128GB RAM上，自动RAM预算触发提交内存压力；显式64GB RAM store后，完成九次功能请求、1K/4K各三次、30分44秒36条连续请求。已把Windows commit问题、失败和成功配置作为#4605发布。

这是部署边界与问题复现成果。不是默认即可稳定使用的承诺，也不是质量排名；后段速度变化、8K/full/原量化等范围保留。[案例](tobeo-20261029/deepseek41-case/REPORT.md)、[发布记录](tobeo-20261029/deepseek41-case/PUBLICATION.md)、[问题#4605](https://github.com/Niko1221/Strata/issues/4605)。

此前还保留了一次重要环境排障：kernel replay/TDR事件后，独立探针HtoD约1.7GB/s，重启后同一探针恢复24.88GB/s。已形成[Strata #4381](https://github.com/Niko1221/Strata/issues/4381)及[NVIDIA论坛报告](https://forums.developer.nvidia.com/t/rtx-5060-ti-windows-persistent-low-pcie-transfer-throughput-observed-after-kernel-replay-tdr-restored-after-reboot/387175)，见[本地发布记录](tobeo-20261028/upstream-reports/README.md)。它为排除环境异常、采集前后测带宽提供真实依据；没有可重复的TDR触发器，也没有确认厂商根因，不能把重启恢复称作引擎优化。

## 实际形成的能力

| 能力 | 已有可审阅证据 |
| --- | --- |
| 构建与来源控制 | 固定commit的独立worktree、CUDA/MSVC构建、依赖/模型/二进制哈希；870基线19项选定测试 |
| 数值验证 | 完整词表logits、固定历史、输出身份、布局与策略改变分开；不把bitwise失败悄悄当质量通过 |
| 性能实验设计 | 统一预热、新进程、交替AB/BA、同日参考、配对统计、失败/波动保留、不同revision分开 |
| CPU/GPU关联分析 | IP/调度、CUDA API与设备事件、NVTX任务、原子完成顺序、fork/join账本、ETW/QPC包级关联 |
| 研究判断 | 正结果、负结果与工具限制都能交付；不根据采样比例或kernel占比直接承诺端到端收益 |
| 开源协作 | 先核对作者和既有实现，在原线程贡献硬件验证，附固定证据，保留验证/原创实现的归属区别 |

## 哪里做得不够、以后怎样改

前半段有前瞻协议、身份门槛和失败保留，避免把不同输出或配置当同一性能对照。后半段把每个未知点继续接成新采集，没有及时写清“结果怎样改变是否实施”的出口，诊断分支扩得过长。

以后在实验前必须写出：具体候选或可证伪假设、支持/否定条件、最小矩阵、预算和停止条件。看到现象先检查它是否影响真实请求，再投入更深工具链；诊断能力升级本身不等于优化项目取得收益。允许以负结果或未决限制收尾，不为凑代码PR修改默认。

## GitHub上怎样交付

当前建议优先把这篇总结和[英文研究文章草稿](tobeo-20261101/research-retrospective/PUBLIC_DRAFT.md)放到自己的研究目录/项目说明中，让读者能沿证据链接复核。标题建议：**《16GB Windows GPU上的混合推理：复制方案验证、端到端取舍与profiling边界》**。

截至2026-11-01本轮GitHub只读回读：

- [#3905](https://github.com/Niko1221/Strata/pull/3905)仍open/unmerged，已有两条本账号验证评论；核心复制及原46c CPU/job证据已公开，不重复发送同一结果。
- [报告PR #4577](https://github.com/Niko1221/Strata/pull/4577)closed/unmerged；[维护者回复](https://github.com/Niko1221/Strata/pull/4577#issuecomment-6495838098)感谢测量，并说明计划在社区benchmark网页发布时纳入这类结果，因此关闭报告PR。不能把它写成代码已合并、网页已上线或正式收录；也不为相同结果再开一份报告PR。
- [DeepSeek #4605](https://github.com/Niko1221/Strata/issues/4605)仍open，已有问题与证据；没有新修复结论时不追加重复评论。

10-31至11-01的870新复现、标记对照及WPR复核尚未作为新增材料外发。若以后发布，先整理精简且脱敏的表、代码和哈希，原始ETL/SQLite/完整logits保留本机；系统ETL可能含其他进程与路径，不应直接公开。

不建议基于当前材料新开“Windows/CUDA驱动bug”issue或“自研优化提速”PR。自己的研究复盘文章与作品总结已有足够内容；上游只追加能改变维护者判断的新证据。

## 一段可用于项目说明的表述

在Windows/RTX5060Ti16GB环境，对Strata混合推理建立固定源码、数值及布局基线，独立验证已有专家权重复制方案。在两种输入长度各五对无profiler测量中，64-token请求合计耗时中位下降约7.6%/12.7%，并核对320步staging字节守恒及事件依赖。进一步以CPU采样、原子完成序号和CPU/GPU时间账本研究执行空隙，识别观察扰动并限定未确认根因；既有实现归原作者，本人贡献为独立验证、实验与分析。

本总结未新增GPU实验或对外发布，也未将所有未完成研究项勾选完成。
