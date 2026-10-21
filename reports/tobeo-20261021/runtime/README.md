# Windows runtime 修复与验证

相关上游 PR：[PID 就绪检测 #3542](https://github.com/Niko1221/Strata/pull/3542)、[独立默认 DACL 修复 #3428](https://github.com/Niko1221/Strata/pull/3428)。状态以 GitHub 为准；此目录记录 2026-10-21 的验证。

- [PR 描述](runtime-pr-description.md)：包含独立分支失败和叠加 DACL 修复后的结果。
- [真实模型验证](patched-runtime-proof.json)：管理运行时启动、显式检查、中文生成与停止。
- `runtime-baseline-failure.log` / `runtime-fixed-lifecycle.log`：原始生命周期失败与修复后通过。
- `runtime-full-tests.log`：独立 PID 分支 38 通过、2 跳过、1 失败。
- `runtime-baseline-liveness-after-dacl.log`：未修改基线在应用原默认权限后复现 liveness 失败。
- `runtime-with-dacl-full.log`：组合验证分支 39 通过、2 跳过、0 失败；不等于 PID 分支单独全绿。
- 其余 `*.log`：权限、父子 PID、更新器等聚焦检查。
- `patched-runtime/`：当时的测试 profile 和运行时状态，作为本地证据保存，不提交 Git。
- `runtime-pr-followup-body.md`：更新 PR 描述时的历史工作副本，仅本机归档。

本次整理没有更改线上 PR 或测试分支。
