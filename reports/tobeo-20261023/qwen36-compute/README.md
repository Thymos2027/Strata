# Qwen3.6：1K / 16K Nsight Compute 最小采集

日期：2026-10-23，北京时间。RTX 5060 Ti 16GB、i7-12700、128GB RAM，驱动 610.88。接续 [10 月 22 日的准备与排障](../../tobeo-20261022/qwen36-compute/README.md)。1K 与 16K 的 application replay 均成功，每个上下文 1 个 pass、正式输出 64 token，与阶段 B 对应前缀逐 token 一致。日常 Flash-Next 已恢复加载。

## 实际结果与范围

固定源码 `83e6b05cd7b97ee194f330f0247faa76deb73f1b`，继续使用阶段 A 的 Windows 原生 exe，SHA-256 为 `7abadfdbac3888b520cb00be77a5f2e70887acc95c8b98ab45316726f78a728b`。工具、模型和其他参数见前日报告。MTP 0、上限 32768、chunk 512、7 workers、64 专家槽位；既有 hybrid 配置实际关闭 Graph。预热输出 64 token，正式请求输出 64 token。

过滤 `k_attn_part`，skip=760、count=1，application replay、strict/grid 匹配、cache-control=all、clock-control=none。只采三个 smoke 指标。

| 检查或指标 | 1K | 16K |
| --- | --- | --- |
| 实际输入 token | 1025 | 16385 |
| 目标 kernel 数量 | 1 | 1 |
| grid / block | (5, 16, 1) / (256, 1, 1) | (65, 16, 1) / (256, 1, 1) |
| kernel GPU 耗时 | 82.144 μs | 874.176 μs |
| DRAM 读字节 | 4,271,104 bytes | 91,881,216 bytes |
| DRAM 写字节 | 0 bytes | 1,098,752 bytes |
| 输入哈希、fresh、MTP、输出长度、输出前缀 | 全部通过 | 全部通过 |
| application pass 数 | 1 | 1 |
| 原服务恢复 | 通过 | 通过 |

每个上下文只测一个选定调用，不是平均值。16K/1K 的耗时比为 10.642、DRAM 读取比为 21.512；尚无重复分布。工具记录的 L2 容量为 33,554,432 bytes。DRAM 写计数为零不代表 kernel 没有写入缓存或其他 GPU 内存层级。仅有三个指标不足以判断带宽饱和或最终访存瓶颈；L2 命中、L1 访问效率、stall、occupancy 均未完成。

随后同日发现主机到 GPU 的传输吞吐异常，见[独立控制与诊断](../qwen36-profiling/README.md)。本页保留有效的隔离 kernel 数据，不将它与旧日无 profiler 测量直接拼成 A/B，也不据此推断正常传输条件的端到端收益。

公开的小型结果见 [summary.json](summary.json)，包含基础单位、两个上下文、验证范围和报告 SHA-256，由 `summarize_contexts.py` 核对后生成。第一份 CSV 的自动缩放单位分别是 us、Mbyte、byte；重新导出 `metrics-base.csv` 得到 82,144 ns 和 4,271,104 byte。16K 及后续脚本显式使用 `--print-units base`，验证记录也保留单位。

## 日期与原始证据

探针记录 UTC `2026-10-22T16:27:21.615342+00:00`，对应北京时间 **2026-10-23 00:27:21**。旧脚本把输出固定到自身目录，因而本轮最初落在 10 月 22 日目录；这属于归档路径问题。

现已复制到本目录的 `mtp0-application-smoke-01/`，逐文件 SHA-256 确认与原记录一致。旧文件保留，嵌入日志、NCU 报告中的原始路径不重写。来源和哈希清单记录在本机 `archive-origin.json`；探针的 exe、状态、日志与报告也一并保留。本地原始记录由 `.gitignore` 排除。

后续运行按 **Asia/Shanghai 的开始日期**写入 `reports/tobeo-YYYYMMDD/qwen36-compute/`，由调用时的日期决定，与脚本放在哪天无关。一轮跨午夜时仍保留完整目录，`timing.json` 记录带时区的起止时间；每日目录独立选择不重名的运行编号。脚本和工具配置继续使用原位置。

## 执行权限与下一步

用户管理员终端的探针实测 `process_is_admin=true`；2026-10-23 检查时代理自身进程的 `IsUserAnAdmin()` 为 false。两者是不同进程，管理员终端的权限不会自动传给已运行的代理。脚本、离线 NCU 报告导出、结果核对和归档由代理直接执行；本机尚未给普通用户开放计数权限，因此新的 GPU 硬件采集仍需有权限的执行进程。

随后以管理员身份重启宿主，代理在 01:10 的直接检测为 true，实际计数探针 `agent-permission-20261023-011026` 退出 0 并生成报告。16K 的 `mtp0-application-smoke-02` 由代理直接完成，不再需要用户复制采集命令。

下一项先恢复并复核环境，然后分批补 1K/16K 的 L2/L1 及活跃 warp 指标，避免立即恢复七个 section。`memory` 分组的七个完整指标名已在本机工具目录中找到；这只是可用性检查，尚未成功采集该分组。恢复后的入口为：

```powershell
& 'E:\Coder\LLM\Strata\reports\tobeo-20261022\qwen36-compute\collect.ps1' -Scope memory -Case both -CaptureTimeout 5400
```

这是待执行命令。`-CacheControl none` 也已准备，用于后续与冷缓存计数分开做对照，尚未运行。当前仅完成两个上下文的三个最小指标；研究计划的最终瓶颈结论和优化交付项继续保留未勾选。
