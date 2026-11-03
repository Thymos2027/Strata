# 推理研究总体状态

更新：2026-11-01（归档复核）。当前源码基线870aedd9 / engine0.1.54；原Qwen3.6-35B-A3B UD-Q4_K_XL，本机i7-12700、RTX5060Ti16GB、128GB DDR4、Windows。默认研究配置为32K/chunk2048/63固定槽位/7workers/MTP0/packed。日常Flash-Next服务独立保留。

## 整体要做什么

解释这台16GB显卡机器上Qwen3.6 hybrid推理的端到端瓶颈，用证据选择一个足够小的改动，验证正确性、适用范围及无profiler下的真实收益，最后形成可复现的报告或开源贡献。实践构建、数值验证、profiling和性能实验设计也属于项目成果，但不能以更多trace代替改进证据。

不要求一定原创内核或一定有加速。已有作者方案的独立验证、负结果和明确限制都是合格贡献；它们要标清归属，不能重新包装成原创实现。

2026-11-01成果交付：[阶段成果与收获](RESEARCH_OUTCOMES.md)汇总可审阅结果、已有公开贡献及研究复盘；另有[英文研究文章草稿](tobeo-20261101/research-retrospective/PUBLIC_DRAFT.md)。本轮只读核对线上状态并整理本地材料，未新增采集或对外发布；建议优先作为本人GitHub研究文章，不重复开启同结果上游PR。

## 已经完成了什么

| 工作 | 状态与结果 | 证据 |
| --- | --- | --- |
| #4347/#4335最小验证 | 已收尾。记录显存/布局/长度取舍 | [选题复评及收尾](tobeo-20261028/topic-reassessment/README.md) |
| Qwen3.8-Flash-Next IQ3_S亲和性 | 已收尾并发布到#1912。all/P/measure五轮15启动45请求，未测出稳定提速/错选；P累计CPU时间少约29%–32%，不是能耗结论 | [实验与发布记录](tobeo-20261029/flash-next-affinity/README.md)、[成果独立小节](RESEARCH_OUTCOMES.md#2-qwen38-flash-next亲和性延迟与cpu资源的取舍) |
| DeepSeek Windows单卡使用案例 | 已完成并发布，独立于Qwen主线，不继续扩成第三条优化线 | [发布记录](tobeo-20261029/deepseek41-case/PUBLICATION.md) |
| PR3905原复制切片 | 正确性、五组无profiler配对、字节守恒与event机制通过；本机1K/16K合计A/B耗时比1.0825/1.1457。属于原作者实现的独立验证 | [验证报告](tobeo-20261030/qwen36-copy3905/README.md)、[补充发布](tobeo-20261030/qwen36-pr3905-followup/README.md) |
| 可复现870aedd9基线 | 独立构建、19测试、完整logits、输出与实际63槽位/chunk2048门槛通过，原46c基线保留 | [基线报告](tobeo-20261030/qwen36-baseline-870aedd9/README.md) |
| CPU/job级受控证据 | 区分等待与算术样本；原子完成顺序、任务覆盖、phase/token账本通过。采样比例不当wall time | [CPU报告](tobeo-20261030/qwen36-cpu-mechanism/README.md)、[job报告](tobeo-20261030/qwen36-job-path/README.md) |
| 新提交迟启动复现 | 四份插桩trace重复观察到，尚不是原版无扰动根因 | [复现报告](tobeo-20261031/qwen36-gpu-submit-870aedd9/README.md) |
| job标记off/on采集对照 | 16请求/八trace通过。off仍有566–632us中位提交间隔，排除密集标记为该采集现象的必要条件；仍有CUDA profiler混杂 | [对照报告](tobeo-20261031/qwen36-observer-control-870aedd9/README.md) |

## 当前到底到哪一步

当前这条连续采集分支已按[收尾决定](tobeo-20261101/qwen36-wpr-review/DECISION.md)收敛为有界验证与诊断成果。唯一系统根因仍未知，针对迟启动的新改动及收益验收未完成；不再将追踪所有未知点作为本阶段结束条件。

最近几轮是同一个诊断分支：看到GPU空隙 → 补CPU/job依赖 → 看到早提交晚启动 → 在870复现 → 排查密集job标记。它们不是五项独立优化，也未证明累计GPU间隙可以直接回收。

目前仍分不清：未采CUDA trace时是否有同样现象；工作在CPU/用户态驱动里尚未真正提交，还是已进入系统/设备队列但未执行；其中哪些影响真实请求延迟。已明确的是不能把全部CPU on-CPU称算术，不能把GPU前驱较晚完成称连续繁忙，也不能据这些trace直接选flush/stream/等待修复。

## 当前取舍与后续入口

当前不再新增采集。1K实模ETW/plain对照没有启动，作为未执行备选设计保留，不在默认执行队列。

本阶段的成果由上表各项报告与[收尾决定](tobeo-20261101/qwen36-wpr-review/DECISION.md)共同交付。原版迟启动的系统根因及原创加速保持未知/未完成；已有独立复制验证、负结果和诊断限制可以形成完整作品，无需以无限采集换取唯一解释。

后续只有在明确一个具体改动/假设、实验结果怎样改变实施决定、最小矩阵和停止条件后，才另立实验。否则优先整理现有成果或选择具体候选，不自动恢复ETW、GQA、MTP或Flash-Next矩阵。

## 已采用的停止边界

- 探针只有GPU利用率、没有可关联目标进程的提交语义：停止实模扩测，报告缺什么；不反复生成同类trace。
- 无法建立可靠时钟/PID/context关联：先解决这个单一缺口，不能堆数据得根因。
- 只有观测器下的现象，或没有可测的无profiler收益：不能为凑PR修改默认；可以以负结果/诊断限制收尾，再重新评估attention、MTP或Flash-Next中的独立问题。
- 即使看到系统队列问题，也需一个单因素改动和真实端到端收益证据，不能把相关性直接变成修复。

[系统探针任务](tobeo-20261031/qwen36-wpr-queue-probe/README.md)记录本轮状态；[总计划第11节](INFERENCE_RESEARCH_PLAN.md#11-执行与收尾清单)记录完成项；[历史状态](RESEARCH_STATUS_HISTORY_20261031.md)只作追溯。
