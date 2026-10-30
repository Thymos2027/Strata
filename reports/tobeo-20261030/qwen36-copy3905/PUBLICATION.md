# PR3905 独立验证发布记录

2026-10-30，北京时间。用户明确同意发布后，已在[PR3905原讨论发布评论](https://github.com/Niko1221/Strata/pull/3905#issuecomment-6512596830)，09:22:50创建，作者Thymos2027。通过GitHub API及本机同账户CLI回读，正文与[实际发布文本](comment-3905.md)一致；当前只有这一条本账号相关评论，没有另开PR或issue。先前[草稿](upstream-comment-draft.md)保留为授权前历史快照，其“Local draft only”不是当前发布状态。

证据在用户fork的独立分支 `evidence/qwen36-copy3905-20261030`，固定commit `7c0247c72d3e57df40e2dd8b9be415ec90046f98`：[英文报告与证据](https://github.com/Thymos2027/Strata/blob/7c0247c72d3e57df40e2dd8b9be415ec90046f98/bench/results/2026-10-30-qwen36-split-copy-windows/README.md)。仅新增 `bench/results/2026-10-30-qwen36-split-copy-windows/` 下55个文件、482612字节；与父commit的diff逐项检查，仅此目录。全部55文件经连接器逐一回读，内容与本地包一致（保留原始换行）。fork main仍为 `790c64279938a95ead9fd3af719bd74f8ba70eb5`，既有PR未修改。

打包脚本：[prepare_publication.py](prepare_publication.py)；离线校验器：[verify_publication.py](verify_publication.py)。校验通过：文件SHA、三份真实输入、六份数值摘要、24条生成输出/布局/日志、十组配对、trace字节守恒及排除的首次失败。包中有全部配对和波动、源补丁/归属、精确token输入、日志、路径替代后的实际命令、完整logits文件哈希及失败记录。完整f32、Nsight报告/SQLite、exe/DLL仍在本机；未把此紧凑档案称为便携GPU复跑工具或标准benchmark。导出器和离线校验器均在测量后编写。

连接器成功上传fork证据；向上游发评论时返回403 `Resource not accessible by integration`，随后使用本机已登录的同一Thymos2027账号 `gh api` 发布。发布前再次核对线程无重复评论；没有重复提交。一次本地回读比较因PowerShell输出换行转换而误报，随后以实际请求文件及CLI/API回读核对全文一致，没有因此重发或修改评论。

实验范围保持不变：仅原作者af08278c的复制hunk及CLI适配，不代表整套PR3905、HIP/SYCL、动态换槽或完整质量通过。没有新GPU实验、日常配置/引擎变更或默认修改，完整CPU归因仍未完成。原始实验94文件manifest及原始草稿保持不变；发布证据另有55文件回读记录。本机完整发布回执在 `publication-result.json`、`publication-post.stdout.json`、`publication-readback.json`，证据包在 `publication-evidence/`。
