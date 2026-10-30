# Git 分支清理盘点

日期：2026-10-30（北京时间）。本次只盘点，未删除分支或工作树，未同步 main。

执行 `git fetch --all --prune --no-tags` 后，main 与 origin/main 同为 `790c6427`；upstream/main 为 `870aedd9`。main 相对 upstream/main 有 21 个独有提交、缺少 197 个提交，不适合直接重置。主工作区已有研究计划修改及未跟踪的 10-30 报告，需保留。

| 分支 | 建议 | 依据与范围 |
| --- | --- | --- |
| backup/pre-upstream-sync-20261023 | 可删除本地分支 | `git cherry main <branch>` 的 9 项全部为 `-`，补丁均已有等价提交；无工作树占用 |
| backup/pre-upstream-sync-20261028 | 可删除本地分支 | 同一检查的 11 项全部为 `-`；无工作树占用 |
| fix/windows-venv-ready-pid | 退出开发用途；可清理本地工作树和分支 | [PR #3542](https://github.com/Niko1221/Strata/pull/3542) 已关闭、未合并；远端同名分支仍保留原提交。上游另有 `72d0bf66` 修复 Windows venv 就绪问题，仅静态审查，未验证替代实现的运行等价性 |
| verify/venv-ready-with-dacl | 建议先用 tag 归档，再清理工作树和分支 | 组合验证提交 `44b16b88` 仅本地有引用；[PR #3428](https://github.com/Niko1221/Strata/pull/3428) 已关闭、未合并，上游 `e2e99ae5` 已独立采用相同 GA 权限修复。历史验证证据保留，不等于当前上游重新测试通过 |
| report/qwen36-hybrid-windows-20261028 | 可清理本地工作树和分支，保留远端 | [PR #4577](https://github.com/Niko1221/Strata/pull/4577) 已关闭、未合并；113 文件的发布包尚未纳入 main，origin 同名分支保留 `f48fcb61`，仍承担公开证据归档用途 |

三个具名贡献/验证工作树均经 `git status --porcelain=v1` 检查，输出为空。清理其分支前需先移除对应工作树；本轮没有执行移除。仅删除分支通常不会显著释放磁盘空间。

保留 main，以及 origin 下的三条 evidence 分支：deepseek41-windows-20261029、flash-next-affinity-20261029、qwen36-copy3905-20261030。这些分支承担已发布或已准备材料的证据引用，不能仅因无活动 PR 判断为无用。

另有六个 detached HEAD 构建工作树（两个 main、PR3641、PR4335、PR4347、copy3905）。它们不是分支；本次未检查其未跟踪产物、运行进程及构建依赖，不列为已确认可删除项。

验证范围：Git 提交/补丁关系、远端引用、三个具名工作树状态，以及 GitHub PR 元数据实时回读。没有运行测试、GPU 实验、删除操作或远端写入。fetch 自动清除了远端已删除的 `upstream/pr4335` 本地跟踪引用。
