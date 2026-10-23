# 本机研究与实验报告

按设备和日期归档。先看结论报告，再进入对应主题查原始数据和复现脚本。

准备开展新实验时，先看[推理优化与 Profiling 实践计划](INFERENCE_RESEARCH_PLAN.md)：以 Qwen3.6 长上下文 attention 为主线，包含环境准备、实验矩阵、验证标准、备用方向和 PR 交付要求。

| 归档 | 内容 |
| --- | --- |
| [tobeo · 2026-10-21](tobeo-20261021/README.md) | RTX 5060 Ti / i7-12700 / 128GB：Flash-Next 优化、Qwen3.6 Q4 实验、Windows runtime 修复与下载记录 |
| [tobeo · 2026-10-22](tobeo-20261022/README.md) | 同一设备：Windows 原生正确性基线、上下文曲线、Nsight Systems 时间线及 Compute 权限预检 |
| [tobeo · 2026-10-23](tobeo-20261023/README.md) | 1K/16K Compute 计数、CPU IP 与传输异常诊断、PR #3641 局部正确性验证；按北京时间归档 |

每次归档以 `README.md` 为入口，按主题建目录；后续日期另建归档，不将新测量覆盖到历史结果。报告和复现脚本可进入 Git，本机配置、原始数据、日志和运行时状态由各目录 `.gitignore` 排除。忽略 Git 不等于删除文件：这些记录仍可在本机查看。

日期按北京时间的运行开始日计算，脚本所在目录不决定结果日期。同一次运行跨午夜时不拆分目录，记录起止时间；Compute 采集入口已自动遵循此规则。
