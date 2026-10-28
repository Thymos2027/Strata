# tobeo · 2026-10-28

本日确认 Windows 整机重启后主机/GPU 传输恢复，并将此前 TDR 后持续低吞吐的测量和限制分别提交给 Strata 与 NVIDIA。报告只陈述一次已观察到的事件序列，不将时间相关性写成已证明的驱动或工具缺陷。

- [重启后的 PCIe 传输恢复验证](pcie-after-reboot/README.md)：同一独立 exe 的 H2D 从 1.726 恢复到 24.882 GB/s，负载采样恢复到 Gen5；未运行模型 decode 或正式性能 A/B。
- [上游报告发布状态](upstream-reports/README.md)：记录 Strata #4381、NVIDIA Nsight Compute #387175、双向链接、查重与脱敏范围。
- [日常 IQ3_S 服务恢复](daily-start-105651/README.md)：沿用原配置启动当前服务端与已安装 engine 0.1.46，健康检查和短 API 冒烟通过，启动 H2D 保持约 24.9 GB/s。

完整 `nvidia-smi` XML、含本机绝对路径的原始结果和运行日志由 `.gitignore` 排除。仓库仅保留报告、复现源码、公开主题快照和明确脱敏的证据包。
