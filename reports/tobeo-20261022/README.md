# tobeo · 2026-10-22

| 主题 | 入口 | 内容 |
| --- | --- | --- |
| Windows 原生源码基线 | [windows-native-baseline/README.md](windows-native-baseline/README.md) | MSVC/CUDA 工具链、原生构建与 Qwen3.6 正确性验证 |
| 阶段 B：上下文曲线 | [qwen36-context-curve/README.md](qwen36-context-curve/README.md) | 1K/4K/8K/16K × MTP 0/2 × 3 次，24 条测量、曲线与资源记录 |
| 阶段 C：Nsight Systems | [qwen36-profiling/README.md](qwen36-profiling/README.md) | 四组有效进程采集、decode 时间线与 kernel 统计；更正 hybrid 下的 Graph 覆盖范围 |

前一天的 WSL 结果保留在 [2026-10-21 归档](../tobeo-20261021/README.md)，不同平台的测量单独记录。
