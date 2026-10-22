# Qwen3.6：首次有效 Nsight Compute 最小采集

日期：2026-10-23，北京时间。RTX 5060 Ti 16GB、i7-12700、128GB RAM，驱动 610.88。接续 [10 月 22 日的准备与排障](../../tobeo-20261022/qwen36-compute/README.md)。本轮 application replay 成功，1 个 pass，正式请求输出 64 token，与阶段 B 前缀逐 token 一致。日常 Flash-Next 已恢复加载。

## 实际结果与范围

固定源码 `83e6b05cd7b97ee194f330f0247faa76deb73f1b`，继续使用阶段 A 的 Windows 原生 exe，SHA-256 为 `7abadfdbac3888b520cb00be77a5f2e70887acc95c8b98ab45316726f78a728b`。工具、模型和其他参数见前日报告。1K / MTP 0：输入 1025 token、上限 32768、chunk 512、7 workers、64 专家槽位；实际 Graph 关闭。预热输出 64 token，正式请求输出 64 token。

过滤 `k_attn_part`，skip=760、count=1，application replay、strict/grid 匹配、cache-control=all、clock-control=none。只采三个 smoke 指标。

| 检查或指标 | 实际结果 |
| --- | --- |
| 目标 kernel 数量 | 1 |
| grid / block | (5, 16, 1) / (256, 1, 1)，与 Systems 一致 |
| kernel GPU 耗时 | 82.144 μs |
| DRAM 读字节 | 4,271,104 bytes |
| DRAM 写字节 | 0 bytes |
| 输入哈希、fresh、MTP、输出长度、输出前缀 | 全部通过 |
| application pass 数 | 1 |
| 原服务恢复 | 通过 |

这是一个选定调用的计数，不是平均值。DRAM 写计数为零不代表 kernel 没有写入缓存或其他 GPU 内存层级。仅有三个指标不足以判断访存瓶颈；16K、L2、stall、occupancy 均未完成，不能据此宣称优化收益。

公开的小型结果见 [summary.json](summary.json)，包含单位、验证范围和报告 SHA-256。原始 CSV 的自动缩放单位分别是 us、Mbyte、byte；本轮重新导出 `metrics-base.csv`，显式使用 `--print-units base`，得到 82,144 ns 和 4,271,104 byte。后续脚本也显式导出基础单位，并在验证结果中保留单位，避免只读数值产生误解。

## 日期与原始证据

探针记录 UTC `2026-10-22T16:27:21.615342+00:00`，对应北京时间 **2026-10-23 00:27:21**。旧脚本把输出固定到自身目录，因而本轮最初落在 10 月 22 日目录；这属于归档路径问题。

现已复制到本目录的 `mtp0-application-smoke-01/`，逐文件 SHA-256 确认与原记录一致。旧文件保留，嵌入日志、NCU 报告中的原始路径不重写。来源和哈希清单记录在本机 `archive-origin.json`；探针的 exe、状态、日志与报告也一并保留。本地原始记录由 `.gitignore` 排除。

后续运行按 **Asia/Shanghai 的开始日期**写入 `reports/tobeo-YYYYMMDD/qwen36-compute/`，由调用时的日期决定，与脚本放在哪天无关。一轮跨午夜时仍保留完整目录，`timing.json` 记录带时区的起止时间；每日目录独立选择不重名的运行编号。脚本和工具配置继续使用原位置。

## 执行权限与下一步

用户管理员终端的探针实测 `process_is_admin=true`；2026-10-23 检查时代理自身进程的 `IsUserAnAdmin()` 为 false。两者是不同进程，管理员终端的权限不会自动传给已运行的代理。脚本、离线 NCU 报告导出、结果核对和归档由代理直接执行；本机尚未给普通用户开放计数权限，因此新的 GPU 硬件采集仍需有权限的执行进程。

下一项应先做 **16K、相同三个指标**，保持采集口径一致；之后再根据结果扩展 L2/stall/occupancy，逐项验证，避免立即恢复七个 section。入口仍为：

```powershell
& 'E:\Coder\LLM\Strata\reports\tobeo-20261022\qwen36-compute\collect.ps1' -Case r0-l16384
```

这是下一步命令，尚未执行。本轮只完成 1K 最小采集；研究计划的瓶颈结论和优化交付项继续保留未勾选。
