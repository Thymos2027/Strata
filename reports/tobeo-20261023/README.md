# tobeo · 2026-10-23

本轮完成 1K/16K 的 Compute 三指标采集，以及已有 GQA 方案的局部 CUDA/真实模型正确性验证。随后发现同日 HtoD 只有约 1.73 GB/s，历史引擎探针约 25 GB/s；性能 A/B 留待环境恢复，不宣称加速收益。日常模型已恢复加载。

| 主题 | 入口 | 内容 |
| --- | --- | --- |
| 阶段 C：Compute 最小采集 | [qwen36-compute/README.md](qwen36-compute/README.md) | 1K/16K × MTP 0，各一个 attention 调用、三个指标，输出与基线一致 |
| CPU IP 与环境诊断 | [qwen36-profiling/README.md](qwen36-profiling/README.md) | 1K CPU 采样、离线 PDB 解析、同日无 profiler 控制、独立 HtoD 吞吐异常与 NVML/PnP 冲突 |
| 既有 GQA 方案验证 | [qwen36-pr3641/README.md](qwen36-pr3641/README.md) | PR #3641 的 Windows/Blackwell 构建、三个选定测试与真实 Q4 1K/64-token 对照通过；性能未测 |

日期统一按北京时间。新运行按开始日期归档，跨午夜不拆分同一次运行；运行记录包含开始和结束时间。此前的固定脚本目录归档问题已修正。
