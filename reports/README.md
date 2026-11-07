# 本机研究与实验报告

更新：2026-11-07。主题：资源受限硬件上的高性能 AI 推理与 Strata 社区贡献。主要设备：Windows 11、i7-12700、RTX 5060 Ti 16GB、128GB DDR4。

## 现在从哪里看

1. [研究总体状态](RESEARCH_STATUS.md)：已完成的成果、目前尚未证明的结论及后续实验的进入条件。
2. [研究方法与验收要求](INFERENCE_RESEARCH_PLAN.md)：当前主线、下一轮实验门槛与收尾清单；旧版阶段方案已归档。
3. [执行记录与原始清单](archive/EXECUTION_LOG.md)：逐次勾选、失败、未完成项及证据链接。历史条目的“下一步”不自动成为当前任务。
4. [阶段成果与收获](RESEARCH_OUTCOMES.md)：可对外复核的结果、负结果、贡献归属和限制。

截至 2026-11-07：源码已合并上游 0.2.12，CUDA 0.1.58 的三个引擎目标及三类模型短请求在本机通过，见[状态文件](../build-native-baseline/merge-c4d90462/status.json)。这不是长上下文或性能验收。Unsloth `UD-IQ3_XXS` 下载按用户要求暂停。Qwen3.6 迟启动诊断已按[收尾决定](tobeo-20261101/qwen36-wpr-review/DECISION.md)停止自动延伸，原版根因及新加速仍未确认。

## 归档

- [旧版研究方案与阶段判断](archive/INFERENCE_RESEARCH_PLAN_LEGACY_20261107.md)
- [状态历史（截至 2026-10-31）](archive/RESEARCH_STATUS_HISTORY_20261031.md)
- [v0.2.9 上游审查（2026-11-01）](archive/UPSTREAM_V029_REVIEW_20261101.md)
- 按日期保存的原始报告和脚本在同级 `tobeo-YYYYMMDD/` 目录。报告中的“当前”“下一步”只表示记录当时的状态；具体结果以该目录的证据为准。

新实验按北京时间的运行开始日建目录，保留原始结果与失败项。大型 trace、运行时配置和本机日志由各目录的 `.gitignore` 管理；忽略 Git 不表示删除本机文件。
