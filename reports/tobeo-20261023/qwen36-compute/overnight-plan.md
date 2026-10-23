# 2026-10-23 夜间执行记录

用户授权按研究计划继续。代理进程管理员状态与实际 NCU 计数探针均通过；后续采集由代理直接执行。结果以北京时间开始日期归档，保留失败，不并行运行 GPU profiler 或性能实验。

- [x] 核对代理管理员状态并实际采到一个硬件计数。探针 `agent-permission-20261023-011026`，退出 0，有报告。
- [x] 重新查重 open/closed issues/PR，并阅读相关后续评论。只读取，没有发消息、开 issue 或 PR。
- [x] 完成 16K / MTP 0 的三个同口径指标与输出验证。`mtp0-application-smoke-02` 通过，874.176 μs、读 91,881,216 bytes、写 1,098,752 bytes。
- [ ] 用 500 Hz CPU sampling、context switches 和匹配 PDB 补 1K/16K 时间线；区分 CPU 样本与调度事件栈。已取得 1K IP/调度数据及 PDB 源码位置，16K/正常工况归因未完成，见[CPU 报告](../qwen36-profiling/README.md)。
- [ ] 用 application replay 分批采 1K/16K 的 L2 命中、L1 读 sectors/requests 和活跃 warp。指标目录已核对，不能当作采集通过。
- [ ] 形成瓶颈结论，明确时间线占比、冷缓存计数和真实关键路径的区别。
- [x] 已有 PR #3641 的局部验证：固定 head 的 CUDA 构建、三个选定布局/数值测试、真实 Q4 1K/64-token 两臂输出对照通过，见[验证报告](../qwen36-pr3641/README.md)。
- [ ] 16K 实模门禁与至少五组无 profiler 交替配对。因同日传输通路异常暂缓，性能前置检查已拒绝当前状态，没有生成 benchmark 目录。
- [x] 额外环境控制：同日无 profiler prefill 仍慢；两次 pinned copy 与原引擎探针均约 1.73 GB/s，卸载日常模型也未恢复。NVML/PnP 代际报告冲突，原因未定。
- [x] 确认服务恢复，无本轮 profiler/测试进程残留；更新报告、索引和总清单。未重启机器或修改驱动/全局链路、时钟、电源设置。

## 新发现的上游重叠

[PR #3641](https://github.com/Niko1221/Strata/pull/3641) 本轮检查时 open、非 draft，head `f3f2136f194bdc42d07961bef0ce66b2811f58cb`。已读描述和文件 diff，新增 `q36_attn.cuh`，并已有 `STRATA_Q36_GQA` 对照开关。量化模型未选择 `--kv f16` 时，开关可以只替换 FP32 attention；本轮已做上述局部实测，完整长上下文和 GPU 时间线尚未覆盖。源码保存在独立 worktree，未改写其实现或当前主工作区源码。

[PR #3678](https://github.com/Niko1221/Strata/pull/3678) 当前 open、draft，也包含量化 KV 与共享读取。Issue [#3700 后续评论](https://github.com/Niko1221/Strata/issues/3700#issuecomment-6339718829) 明确指出与 #3641 的 grouped attention 重叠。因此本轮优先做已有方案的 Blackwell 硬件验证，不将他人实现包装成自己的优化。API 搜索与详情快照保留本机，状态只代表本次检查时刻。

本轮结果与范围以上述报告为准。传输恢复后先复测相同探针、复核元数据，再重建同日对照并续跑，不能把当前异常工况的 gate 单次时间包装成加速收益。
