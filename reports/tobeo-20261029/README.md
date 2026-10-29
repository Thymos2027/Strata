# tobeo · 2026-10-29

- [DeepSeek V4.1 Windows 单卡案例](deepseek41-case/REPORT.md)：完成模型/专用引擎校验、功能、1K/4K短矩阵及30分钟连续请求；保留自动预算提交内存失败与手动配置边界，问题和脱敏证据已发布。
- [模型目录盘点与迁移](model-directory-audit/MIGRATION.md)：按模型家族整理Qwen/DeepSeek资产，17项同盘移动和110文件SHA-256通过，DeepSeek与日常Qwen新路径实际请求验收完成。
- [Qwen3.6 可复现源码基线](qwen36-repro-baseline/README.md)：固定上游46c152a1/源码引擎0.1.53，独立CUDA构建、17项选定测试、四臂门禁及两次1K/16K输出重复性通过，HtoD约24.9GB/s，原日常服务恢复。正常工况profiling与瓶颈结论仍待执行。

- [Flash-Next IQ3_S CPU布局策略验证](flash-next-affinity/README.md)：完成同一0.1.52引擎的18条功能任务、15次启动/45条受控请求及收尾。measure四次P、一次all；请求成本无稳定方向，未复现达到前瞻条件的稳定错选，不改校准器或默认。P累计CPU时间较少；全部配对与失败记录独立归档。

此前开始、跨日完成的Qwen3.6实验和后续发布记录仍按运行开始日期保存在[10-28目录](../tobeo-20261028/README.md)。
