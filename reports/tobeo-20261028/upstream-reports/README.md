# 排障经验报告发布状态

日期：2026-10-28。用户明确授权向 NVIDIA Nsight Compute 和 Strata GitHub 分别提交诊断报告。

## Strata：已发布

- [Issue #4381](https://github.com/Niko1221/Strata/issues/4381)
- 标题：`[Other] Windows RTX 5060 Ti: persistent low PCIe throughput observed after profiling TDR, restored after reboot`
- 发布账号：Thymos2027；通过本机已登录 GitHub CLI 发布，并用 `gh issue view` 确认 OPEN、作者与标题。
- GitHub 连接器首次创建返回 403 Resource not accessible by integration，未创建 issue；随后 CLI 创建成功，没有重复提交。
- 正文对应 `strata-issue.md`，附独立 CUDA 诊断源码与编译命令。未上传原始系统 XML、主机名、用户名、本机绝对路径、模型文件或可执行文件。
- 报告没有归因于已确认的 Strata 回归，也没有称 TDR 可稳定复现；已区分 passed、failed、not run 和四天时间间隔的限制。

## NVIDIA：已由用户发布，互链已完成

- [NVIDIA Nsight Compute 主题 #387175](https://forums.developer.nvidia.com/t/rtx-5060-ti-windows-persistent-low-pcie-transfer-throughput-observed-after-kernel-replay-tdr-restored-after-reboot/387175)。
- 2026-10-28 通过公开主题 JSON 核验：分类 ID 114（Nsight Compute），标题与正文完整，含测量表、命令、限制及 Strata #4381 链接；当时 posts_count=1，尚无回复。
- 已更新 Strata #4381 正文中的 NVIDIA 发布状态与真实链接，并重新读取确认，完成双向引用。
- 以下保留发布准备过程；其“待发布”叙述是历史过程，不是当前状态。

- NVIDIA [官方反馈说明](https://developer.nvidia.com/tools-overview/nsight-compute/get-started)指定使用 Developer Forums；目标分类 [Nsight Compute](https://forums.developer.nvidia.com/c/developer-tools/nsight-compute/114)。
- 当前工具没有 NVIDIA 论坛已认证发布能力；按 plugin-management 技能检索也未发现匹配论坛发布集成。
- 准备完毕：`nvidia-title.txt`、`nvidia-post.md`（含 Strata #4381 链接）、`nvidia-evidence-sanitized.zip`（正文、标题、抽取的两轮测试及 NVML 样本、独立 .cu 源码）。
- `nvidia-submit.html` 提供预填论坛链接和复制正文按钮，已通过 Start-Process 请求默认浏览器打开。打开本地页面不等于论坛已登录或报告已发布，也未验证论坛是否完整保留预填正文。
- 原先缺少的论坛发布步骤已由用户完成，主题 URL 已核验并补到 Strata issue。

## 查重与审阅

提交前重新查询 Strata issues / PRs 的 Nsight、TDR、PCIe 与带宽组合，以及 NVIDIA 论坛搜索；未找到确认同案，未声称穷尽所有评论和附件。参考 #485、#2137 的差异已在报告中说明。已读取 CONTRIBUTING.md 与 Question 模板，使用 [Other] 标题和匹配正文结构。原第 04 次采集的 plan.json 用于提取该次真实命令，未用第 01 次计划冒充。
