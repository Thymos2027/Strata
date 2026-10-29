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

2026-10-29 Flash-Next性能实验已结束：[亲和性实验](../../tobeo-20261029/flash-next-affinity/README.md)的performance-04于17:51完成并恢复下载，原命令后台续传启动PID26760，日志为`download-v5.stdout.log`/`download-v5.stderr.log`，旧日志保留。18:24快照为262,621,527,949 / 273,803,820,973 bytes（95.92%），六项verified，主体第一分片继续下载；启动进程存活，尚未完成全文件SHA及推理验收。此前17:09恢复使performance-02整批15条计时隔离；performance-03静默检查失败隔离三条、来源未确认。最终有效矩阵采用停止下载进程、保留原文件/分段清单并测后续传的方式。

2026-10-29 17:09（北京时间）状态核查：17:02:09后确认字节停在249,937,952,653 / 273,803,820,973（91.28%），只剩主体第1分片；其余六项本次任务均为verified。检查发现包装器11260、Python23764及两个curl的线程处于Suspended，并非脚本网络重试正在运行。代理曾于17:09:36恢复这四个进程（返回0）；用户随即说明有试验在跑，因此17:09:59重新挂起下载树，包装器11260、Python23764及当时curl26904/11444均返回0，保留断点。恢复期间新确认两个32MiB片段，随后维持挂起以让试验继续；未检查或修改试验，也未独立确认最初是谁挂起下载。当前日志/状态不增长是预期暂停，试验结束后的下载恢复尚待安排；以下v4后台持续运行描述为此前状态。

2026-10-29 16:27（北京时间）恢复下载：已停止卡住的 v3 树 PID 18392/5012，并保留状态为 `download-status-before-v4-20261029.json`。旧 DSpark `.part.src` 的 ETag 为 `F3048329A5A10134EA05DCB233AEE8B1-400`，本轮 urllib 探测同固定版本得到 `EDCDF47948CBF730995AC43625A06669`；实际 curl 分段又返回旧标识。说明本轮请求得到的 ETag 不一致，不能据此断言权重内容变化；具体 CDN/请求头因素未独立隔离。两文件固定 revision 的 ModelScope API 大小及 SHA-256 均与清单一致，各抽查已确认片段的开头、中间、末尾 64 KiB，六处与服务器逐字节相同。证据为本机 `etag-probes-20261029.json`、`etag-range-probes-20261029.json`、`resume-source-check-20261029.json`；抽查不是完整性验收。

新本地脚本 `../research-next-steps/download_deepseek_fresh.py` 每个32MiB分段从固定 repo URL 重新获取签名地址，不缓存 CDN URL，也不把 ETag 当作跨请求内容相同的依据；逐响应严格检查206、Content-Range、总大小和实收长度，成功写盘并flush后才登记片段。旧 `.part`、片段清单和来源记录保留，不调用会因 ETag 不同而删除断点的路径；两个未完成文件各两条连接、合计四条，失败片段最多等60秒后继续重试，不堵住另一文件。网络单次最长300秒、45秒低速阈值；磁盘/最终SHA错误保留数据并记录失败。已有完整文件随后重新计算SHA-256；所有文件验收通过才设置 `passed=true`。未修改 `setup.py` 或全局网络设置，仍是原 ModelScope 来源、版本与量化。

后台包装器 PID **11260**、Python PID **23764**，日志为 **`download-v4.stdout.log` / `download-v4.stderr.log`**，状态仍为 `download-status.json`。16:26:52至16:27:36短检，确认字节从236,592,329,293增至236,827,210,317（86.50%），新增234,881,024 bytes；DSpark增至3,959,422,976、主体第1分片增至6,576,668,672 bytes。两个文件均有多个成功片段，无新网络错误，随后继续后台运行。语法检查及五项HTTP响应校验案例通过（正确跳转响应接受，错误状态/偏移/长度/总大小拒绝）；自动网络重试及最终全文件验收本轮尚未触发，不把短检吞吐外推成长期速度或预计完成时间。

```powershell
Get-Content reports/tobeo-20261028/deepseek41-community/download-v4.stdout.log -Tail 10
Get-Content reports/tobeo-20261028/deepseek41-community/download-v4.stderr.log -Tail 10
$s = Get-Content reports/tobeo-20261028/deepseek41-community/download-status.json -Raw | ConvertFrom-Json
$s | Select-Object phase, passed, downloaded_bytes, total_bytes, updated
$s.files | Select-Object name, phase, downloaded_bytes, last_progress, last_network_error, error
```

重启机器或任务退出后，可在确认旧进程已退出的情况下重跑 `.venv/Scripts/python.exe -u reports/tobeo-20261028/research-next-steps/download_deepseek_fresh.py --connections 2` 继续已确认片段。不要同时启动v3和v4写入相同文件。以下为更早的历史状态；当前任务以本节开头的v5状态为准。

2026-10-29 16:18（北京时间）只读复核：下载目标仍为 ISTA-DASLab IQ2_XS / 2.25 bpw。状态文件的 `repo` 是每个文件各自的来源，前两项 Unsloth 分别是 5,780,589 bytes 的元数据和 7,976,914,240 bytes 的 DSpark 草稿模型；`setup.py` 的 `IST-DAS-2.25bpw` 配置也引用这两份 shared 文件，不表示换成 Unsloth 主体。当前确认 236,592,329,293 / 273,803,820,973 bytes（86.41%），剩约 37.21 GB。PID 18392/5012 仍在运行，但本轮短检期间确认字节数未增长；v3 stdout 反复出现版本标识不一致及连接停滞提示，DSpark 停在约 3.86/7.98 GB。实际调度为单文件顺序下载（`max_workers=1`），每文件四路连接，因此主体第1分片约 6.44/39.54 GB 暂未继续。主体第2–4分片及 Engram 正式文件和此前的校验标记仍存在；当前 `pending` 是重启后尚未重新校验，不代表文件丢失。本轮未重新计算这些大文件的哈希、未更改下载任务，完整下载和推理验证仍未完成。

2026-10-29 15:18续传更新：此前v2任务在15:03退出，已确认235,954,795,085 / 273,803,820,973 bytes（86.18%），5/7文件校验通过，包括Engram及主体第2–4分片；剩DSpark与主体第1分片，约37.85GB。分段日志的直接退出原因是响应ETag不一致，旧curl回退日志另有低速超时，不能混为同一次失败。重新探测两份未完成文件的Range、大小与ETag均匹配断点记录，保持原ModelScope版本与SHA-256，没有换源或跳过校验。

已保留失败状态为本机`download-status-before-resume-20261029.json`，在原本机调度脚本补充最多4次外层重连重试；完整性失败不盲目重试。新包装器PID18392、实际Python进程PID5012，以四路分段续传；新日志为`download-v3.stdout.log` / `download-v3.stderr.log`，状态文件仍为`download-status.json`。短检确认DSpark从3.22GB继续增长到3.39GB以上，未清空断点；进程运行且无新错误。重启后的状态会逐项重新验证已有文件，暂时显示pending不表示此前通过的文件丢失。本轮未等待全部下载，也未启动DeepSeek。

```powershell
Get-Content reports/tobeo-20261028/deepseek41-community/download-status.json
Get-Content reports/tobeo-20261028/deepseek41-community/download-v3.stdout.log -Tail 5
Get-Content reports/tobeo-20261028/deepseek41-community/download-v3.stderr.log -Tail 10
```

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
