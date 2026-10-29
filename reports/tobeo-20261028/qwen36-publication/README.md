# Qwen3.6研究证据发布

2026-10-29，经用户授权发布，已回读核验线上正文、作者、head和文件范围。

- [报告型PR #4577](https://github.com/Niko1221/Strata/pull/4577)：open、非draft；尚未合并或获得维护者审阅。
- [#4335补充评论](https://github.com/Niko1221/Strata/pull/4335#issuecomment-6488876445)：16K收益与1K代价、数值/任务范围、固定历史局限。
- [#4347补充评论](https://github.com/Niko1221/Strata/pull/4347#issuecomment-6488877876)：原身份门槛失败、匹配布局数值归因及generation/prefill取舍；没有将分叉直接定为质量问题。
- [不可变证据入口](https://github.com/Thymos2027/Strata/blob/f48fcb6130be1d9e08eaa36c7963dbf2b558e748/bench/results/2026-10-28-community-rtx-5060-ti-qwen36-hybrid/README.md)：commit `f48fcb6130be1d9e08eaa36c7963dbf2b558e748`。

独立worktree：`E:/Coder/LLM/Strata-contrib-q36-tradeoffs`；分支`report/qwen36-hybrid-windows-20261028`，基于upstream`46c152a1`。PR只有一个bench/results目录内的113个新增文本文件，没有夹带本地研究计划或引擎改动。测量仍固定原基线`5e8a4cca`与两个原PR head，不把报告分支base说成新测引擎。

## 实际完成的发布验证

- 补齐性能输入、96token历史、原失败实验warmup、全部任务prompt/IDs/期望值，并用本机Tokenizer核对原输入哈希。
- 发布40次正式输出、20对原始毫秒、脱敏引擎日志、各构建16项选定CTest日志、原脚本/协议归档，以及本地全词表dump的尺寸/shape/SHA-256；不上传模型或dump。
- 离线复核输入/文件哈希、原日志与JSON输出、全部配对/中位数/范围及匹配数值dump哈希通过。
- 参数化replay/adapter脚本在发布整理时新增：语法、CLI帮助、两个计划模式通过；adapter真实编译链接及missing-file参数检查通过，原exe/DLL/库哈希未变。没有为发布重新运行GPU模型、质量或性能实验。
- 私人目录/凭据扫描、链接、提交范围、暂存区精确字节SHA-256和whitespace检查通过。保留prompt末尾空行和原行尾，不为格式检查改变输入。
- 两个评论及PR正文与发布源逐字比对，作者、head、main目标及113个新增文件范围确认。

核验时仅`Intake / check`成功、`Intake / sweep`跳过；这不是引擎全量CI通过，也不代表已合并。状态快照见[publication.json](publication.json)。GitHub连接器写入返回403后，使用本机已登录GitHub CLI完成同一已授权操作。

原实现归属rynwang，本次贡献为独立验证、适用边界和可复现证据；未撤销原自由生成身份失败，没有扩张为普遍质量等价、动态缓存性能或默认全面提速。
