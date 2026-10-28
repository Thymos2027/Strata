# DeepSeek V4.1 Flash：本机社区使用案例准备

2026-10-28，北京时间。用户要求下载 DeepSeek V4.1 Flash 并测试，形成社区使用案例。本轮已确认资源、选定兼容量化、核对全部源文件大小/哈希并启动后台下载；尚未完成模型下载、安装、加载或推理测试。

## 为什么做

Qwen3.6 主线研究问“慢在哪里，怎样改进”；本任务问“这套硬件运行新模型是否实用”。两者可以分别形成优化验证报告和硬件使用案例。社区案例无需先写新内核，重点是可重建的安装过程、真实资源消耗、速度、任务结果与限制。

## 选择和资源

- DeepSeek-V4.1-Flash-1017，ISTA-DASLab GSQ-RCO **IQ2_XS / 2.25 bpw**。项目文档对有磁盘空间的代码/Agent 使用优先推荐该档位，不下载完整 UD-Q8_K_XL。选定文本测试，暂不下载视觉塔。
- 全部从 ModelScope：ISTA-DASLab 的四个 backbone 分片及 Engram；Unsloth 的 DSpark Q8_0 和约 5.8 MB 元数据分片。不是下载 Unsloth 的整套 508 GB 模型。
- 七个文件合计 **273,803,820,973 bytes**。四个主体分片保存在 `D:\Models\Strata\deepseek-v4.1-flash-IST-DAS-2.25bpw`；共用 Engram、DSpark、元数据保存在 `D:\Models\Strata\deepseek-v4.1-flash-shared`。目录与源码的 shared 查找约定一致，不复制多份 Engram。
- 本机 i7-12700、RTX 5060 Ti 16GB、128GB DDR4；D 盘为 ZHITAI TiPro9000 4TB NVMe，本轮下载前空余约 3.83 TB。RAM 当时空闲约 33 GiB，包含运行中 Qwen 等负载，不能将其当作 DeepSeek 独占可用内存。
- `strata launch --plan` 对 2.25bpw / 8K / 单卡 / full / vision off 返回 `placement.verdict=tight`，估算全 RAM 路径需要约 146.6 GB。128GB 机器需 SSD tier，计划允许该路径；未声称模型完全驻留 RAM 或能与 Qwen 同时推理。测试时须释放日常模型占用，再按日志确认实际预算。

## 来源与完整性

官方 [ISTA-DASLab ModelScope 仓库](https://modelscope.cn/models/ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF)、[Unsloth ModelScope 仓库](https://modelscope.cn/models/unsloth/DeepSeek-V4.1-Flash-1017-GGUF)。本轮 ModelScope API 的大小/SHA-256 与 `setup.py` 的 `DSV41_ISTA_FILES`、`DSV41_FILES` 及允许的新 shard 1 表逐项比对，全部匹配。IQ2_XS 第一分片为更新模板的已接受版本（39,535,788,064 bytes，SHA-256 `d9b949d55e27242b8afc7c2928749b888372d4c39682f9a131670d1c2555155e`）；没有为迁就下载来源而换量化。

本机 `download-manifest.json` 固定每份文件的 ModelScope repo/revision、URL、大小、SHA-256 与目标路径；URL 使用元数据所列 commit revision，不跟随变化的 master。`download_deepseek.py --prepare-only` 只准备清单，正常执行使用该清单，两个下载任务并发，curl 断点续传与自动重试，完成后逐文件计算 SHA-256，再将 `.part` 改成正式文件名并写 `.verified.json`。不覆盖已有不匹配文件。

## 后台任务和查看方式

2026-10-28 后续调整：针对下载慢完成代理/直连、ModelScope入口、8路分段、CDN节点、Hugging Face与独立站点的短测，见[下载链路排查](DOWNLOAD_DIAGNOSTIC.md)。原PID27800已停止且保留部分数据；现PID7728以ModelScope直连、仓库下载器单文件四路分段继续，日志改为 `download-v2.stdout.log` / `download-v2.stderr.log`。状态仍为 `download-status.json`，按已确认32MiB片段计数，不直接按稀疏文件长度计数。本轮没有证明大幅提速；更换接入网络是下一项更有价值的对照。

原启动包装器 PID 27800 已停止；当前包装器 PID 7728，具体子进程 PID 可能变化。脚本位于本机 `reports/tobeo-20261028/research-next-steps/download_deepseek.py`。本轮观察到约 5.8 MB 元数据已下载并核验，其余开始持续收取数据；大文件未完成。未切换或卸载当前日常服务，下载结束不会自动启动 DeepSeek。

```powershell
# phase=complete 且 passed=true 表示七个文件均已通过大小及 SHA-256 校验
Get-Content reports/tobeo-20261028/deepseek41-community/download-status.json
Get-Content reports/tobeo-20261028/deepseek41-community/download.stdout.log -Tail 10
Get-Content reports/tobeo-20261028/deepseek41-community/download.stderr.log -Tail 20
# 当前分段下载任务
Get-Content reports/tobeo-20261028/deepseek41-community/download-v2.stdout.log -Tail 5
Get-Content reports/tobeo-20261028/deepseek41-community/download-v2.stderr.log -Tail 10
```

文件失败的原因还记录在对应 `*.download.log`。网络失败后可重跑同一脚本继续 `.part`；已完成文件会先验证后跳过。不要重新执行 prepare-only 来悄悄改写进行中任务的来源。后台下载可能与日常推理竞争磁盘/网络，本轮不在下载期间做正式性能测量。

## 下载后的最小验证

1. 先重新核对引擎组件是否含 `strata-dsv41`，需要时补齐独立 DeepSeek 引擎；Qwen `strata.exe` 能运行不等于 DeepSeek 后端已就绪。以现有文件运行 launch plan，使用明确的 family/model/model-path 和 8K 上下文，保持本地访问。
2. 安排模型切换，保存并释放当前 Qwen，再准备 pack/tokenizer，记录所有版本、实际启动参数、hot-expert profile 和 RAM/SSD/VRAM 布局。首轮文本-only，Full quality（6 experts）；16GB 默认 Faster 使用5个专家，后续可单独比较并注明行为变化。
3. 冒烟测试中文、英文、可执行小代码题、多轮和工具调用，保存公开可重建 prompt、实际输出、工具参数及正确/错误判断；不只有 tok/s。
4. 用 1K/4K 实际 prompt、固定输出预算、每格至少3次，记录冷/热加载、TTFT、prompt/decode 吞吐、RAM/VRAM 观测峰值和磁盘 I/O；8K 扩展须留出输出空间。DSpark on/off 另做配对，不把接受率直接当作吞吐收益。
5. 写 Windows/Blackwell/NVMe/128GB 的独立使用报告，明确这个量化、文本-only、上下文和重复次数。它是本机案例，不冒充仍为 draft 的 Qwen 标准 benchmark，也不先宣布比 Qwen 更好。实际对外发布前再查重和脱敏，用户未授权本轮发送消息。

当前完成状态：来源/资源审查完成、后台下载已启动；下载完整性最终验收、模型加载、性能/功能验证和社区发布均未完成。
