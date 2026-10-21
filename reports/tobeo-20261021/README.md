# tobeo · 2026-10-21

设备：i7-12700、RTX 5060 Ti 16GB、128GB DDR4。以下均为当天记录，服务状态和上游进展不代表当前实时状态。

| 主题 | 入口 | 原始记录与脚本 |
| --- | --- | --- |
| 综合部署、优化与贡献 | [REPORT.md](REPORT.md) | 汇总测量、限制和 PR 验证 |
| 推理优化选题 | [INFERENCE_OPTIMIZATION.md](INFERENCE_OPTIMIZATION.md) | 研究假设、源码入口和后续实验方案 |
| Flash-Next IQ3_S | [flash-next/README.md](flash-next/README.md) | P 核、PCIe/MTP 调参、缓存探针和资源采样 |
| Qwen3.6 Q4 | [qwen36-q4/README.md](qwen36-q4/README.md) | 短基准、MTP 三组对照和 HTTP 验证 |
| Qwen3.6 源码基线 | [qwen36-source-baseline/README.md](qwen36-source-baseline/README.md) | WSL 独立构建、工具链准备与正确性门禁 |
| Windows runtime 修复 | [runtime/README.md](runtime/README.md) | PR 描述、基线失败、修复验证与组合测试日志 |
| 模型下载 | [downloads/README.md](downloads/README.md) | 来源测速、下载状态、校验和续传脚本 |
| GitHub 项目热度 | [github/README.md](github/README.md) | 仓库指标与 PR 活动快照 |

整理时仅重排归档、修正复现脚本/配置的路径；原始测量 JSON 与日志保留原内容，可能仍包含当时使用的旧路径。`organization-manifest.json` 保存本次移动映射，仅本机保留。

Qwen3.6 实验后恢复的 Flash-Next 服务，其 stdout/stderr 正在写入 `qwen36-q4/restored-iq3.*.log`，本次保留该位置以避免停服。早期 `final-server.*.log` 是历史快照。
