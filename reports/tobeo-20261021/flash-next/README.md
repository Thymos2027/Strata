# Flash-Next IQ3_S 实验资料

结论与限制见[综合报告](../REPORT.md)，后续选题见[研究方案](../INFERENCE_OPTIMIZATION.md)。

| 内容 | 文件或目录 |
| --- | --- |
| 原始配置及基线状态 | [original-config.json](original-config.json)、[status-before.json](status-before.json) |
| 默认布局 / P 核短基准 | [baseline/](baseline/)、[pcores/](pcores/) |
| 固定实际缓存的亲和性对照 | [affinity-confirmation.json](affinity-confirmation.json)、[confirm_affinity.py](confirm_affinity.py) |
| PCIe 和 MTP 参数筛选/确认 | [pcie-mtp-tuning.json](pcie-mtp-tuning.json)、[tune_pcie_mtp.py](tune_pcie_mtp.py) |
| 前缀复用功能探针 | [prefix-reuse-probe.json](prefix-reuse-probe.json)、[probe_prefix_reuse.py](probe_prefix_reuse.py) |
| 服务验证与资源快照 | [final-verification.json](final-verification.json)、[verify_final.py](verify_final.py) |

运行会启动引擎的脚本前应先释放显卡上的模型，避免争用显存。不要将吞吐实验直接视为质量等价证明。本目录 JSON、日志、配置及 benchmark 子目录仅保留在本机。
