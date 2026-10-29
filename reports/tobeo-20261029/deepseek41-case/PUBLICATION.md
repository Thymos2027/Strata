# DeepSeek Windows提交内存问题：已发布

2026-10-29，经用户授权完成发布。上游仅创建一个聚焦问题的issue，没有创建PR或另发重复评论。

- Issue：[Niko1221/Strata #4605](https://github.com/Niko1221/Strata/issues/4605)，`[Engine] DeepSeek auto RAM-store loading exhausts Windows commit headroom (128 GB RAM)`。
- 作者：Thymos2027；发布后回读为open。
- 公开证据：[英文报告及完整证据](https://github.com/Thymos2027/Strata/blob/72ff3a298043fab23ec430db87380101d058b680/bench/results/2026-10-29-community-rtx5060ti-deepseek41-windows/README.md)。
- 独立分支：`evidence/deepseek41-windows-20261029`；固定commit：`72ff3a298043fab23ec430db87380101d058b680`。
- 范围：仅一个`bench/results/2026-10-29-community-rtx5060ti-deepseek41-windows/`，25文件、5,955,125 bytes；fork main、当前工作树/真实Git索引及既有PR未修改。使用独立Git索引和commit-tree，没有切换分支或将本地其他修改提交进去。

## 发布内容及准确性修正

主问题是专用DeepSeek0.1.52在本机自动store加载时，Windows提交余量不足。公开了原始事件的数值、脱敏日志、三组真实配置，以及独立64GB store案例的功能、性能和连续请求数据。没有把手动保护停止写成第二次OOM，没有编造引擎自行崩溃的退出码，也没有把8K案例当成#4362长上下文UMA扣减问题的复现。

发布前进一步解析此前保存的原始事件XML，得到SystemCommitCharge=145,636,839,424、SystemCommitLimit=145,729,966,080 bytes，余量93,126,656 bytes；DeepSeek进程CommitCharge=118,554,161,152 bytes。只读查询确认分页文件是**初始4096MiB、上限8192MiB**，恢复后分配快照为4096MiB；失败事件的145.730GB上限与后续141.435GB不同。先前“4GB分页文件”的简称只描述了恢复后的快照，不足以代表全程。公开标题移除固定4GB假设，正文/英文报告/本地报告均说明这一区别；原始XML及运行记录未改写。事件只提供一个关键时点，仍不代表完整临界时序或源码根因隔离。

公开包采用每请求独立response文件作为真实输入来源，明确原汇总两处可变messages列表的归档差异。原始源码归档仅做本机路径替换，提供原始和公开SHA；没有把脱敏源码宣称为已重新GPU验收的便携runner。事后离线核验程序已随包提供，核对52个HTTP事件/结果与52条native timing、4384个采样及文件哈希；此前本机原始证据审计189文件的范围与这25文件公开整理包分开记录。

## 查重与渠道

发布前再次检索开放/关闭的DeepSeek commit、auto RAM-store和Windows相关问题，未见同题。引用#1607作为较早Qwen提交内存问题背景，不宣称同一分配路径；该帖维护者允许补充新证据或新建关联issue。参考#4426维护者关闭纯benchmark PR、转向筹备网站收录的说明，因此没有对上游创建成绩PR。

GitHub连接器成功创建用户fork的证据分支；在上游创建issue返回403 Resource not accessible by integration。随后使用已核对同一Thymos2027账户的本机GitHub CLI，以正文文件发布成功，无重复issue。证据首次Git推送失败后重试同一commit成功，没有生成第二个内容提交。

## 发布后验收

- 远端tree限定目录与本地25文件一致，每份Git blob均下载并核对大小及SHA-256，全部通过。
- 通过GitHub连接器和CLI回读#4605，作者/标题/正文一致（仅统一CRLF/LF后比较），固定证据URL正确。
- 远端证据分支head为上述commit，fork main仍为证据commit的父提交；没有创建上游PR。
- 本机记录：`evidence-publication.json`、`remote-evidence-verification.json`、`issue-request.json`、`issue-created.json`、`publication-verification.json`。发布正文为`issue-body.md`。

本次没有新GPU测量、引擎补丁、默认改变或问题已修复的声明；后续维护者回复需再读取，不能把发布视为根因已确认或修复交付完成。
