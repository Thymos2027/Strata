# tobeo · 2026-10-30

- [Git 分支清理盘点](git-branch-audit.md)：区分可删除备份、本地验证工作树及应保留的远端证据分支；仅盘点，未执行删除。

- [PR3905复制方案独立切片验证](qwen36-copy3905/README.md)：已有split-stage-copy的原作者独立复制提交通过数值门禁和五组配对，1K/16K合计耗时均5/5改善；两条机制trace及离线核对通过，详见该目录汇总；[原PR评论与证据已发布](qwen36-copy3905/PUBLICATION.md)，不改默认、不提交重复实现。

- [Qwen3.6 正常工况 Systems 采集](qwen36-systems/README.md)：接续46c152a1基线，分别检查chunk2048/4096、1K/16K的CUDA/NVTX时间线与同日无profiler输出；本轮CPU采样权限不足，完整关键路径归因另行记录。

- [正常工况CPU IP/调度与复制依赖补充](qwen36-cpu-mechanism/README.md)：固定46c152a1与原配置，三份CPU trace及同日参考通过；补齐等待/算术样本、320步双缓冲依赖和stream优先级，完整job级因果仍未完成，新材料未发布。

- [Qwen3.6 job级依赖与关键路径](qwen36-job-path/README.md)：两轮独立诊断及最终验收通过，10160个phase/243840个行任务的完成序号和wall账本核对；受控路径完成，GPU迟启动残差与原版全系统根因仍待。新材料未发布。
