# tobeo · 2026-10-28

本日确认 Windows 整机重启后主机/GPU 传输恢复，并将此前 TDR 后持续低吞吐的测量和限制分别提交给 Strata 与 NVIDIA。报告只陈述一次已观察到的事件序列，不将时间相关性写成已证明的驱动或工具缺陷。

- [重启后的 PCIe 传输恢复验证](pcie-after-reboot/README.md)：同一独立 exe 的 H2D 从 1.726 恢复到 24.882 GB/s，负载采样恢复到 Gen5；未运行模型 decode 或正式性能 A/B。
- [上游报告发布状态](upstream-reports/README.md)：记录 Strata #4381、NVIDIA Nsight Compute #387175、双向链接、查重与脱敏范围。
- [日常 IQ3_S 服务恢复](daily-start-105651/README.md)：沿用原配置启动当前服务端与已安装 engine 0.1.46，健康检查和短 API 冒烟通过，启动 H2D 保持约 24.9 GB/s。
- [恢复后的研究取舍](research-next-steps/README.md)：复核 v0.2.7 与相关上游讨论，优先当前主线的 FP32 GQA 独立验证、正常工况关键路径和 MTP 收益边界；本轮未新增 GPU 实验。
- [最新模型与选题复评](topic-reassessment/README.md)：再次fetch与扩大查重后，保留两模型，优先 #4347/#4335 的Qwen3.6 hybrid独立验证，Flash-Next校准升至P1，GQA降为条件性后续；包含查询元数据快照。
- [当前源码基线与 #4347 结果](qwen36-pr4347/README.md)：首组256token身份检查不通过后停止原配对；后续匹配布局数值/48条任务通过，另立协议的固定历史五组配对显示16K generation收益未抵消prefill代价。没有普遍加速结论；服务和下载已恢复。
- [#4335 独立chunk验证](qwen36-pr4335/README.md)：10-28开始、10-29凌晨完成；选定测试、同chunk数值/24条任务及20次计时通过。4096的16K合计五组更快、1K合计五组更慢，槽位63→50；未叠加#4347。包含小型汇总、全部10对数据及未发布的英文反馈草稿。
- [DeepSeek 社区使用案例准备](deepseek41-community/README.md)：已核对 ModelScope 的 2.25bpw 七份文件与硬件资源，后台下载进行中；没有切换日常模型，未完成推理或性能测试。
- [日常引擎升级与验收](engine-upgrade/README.md)：0.1.46 → 0.1.52 的官方包、签名/文件、test-start 和预设 API 验收通过；旧组件保留，长上下文和正式性能 A/B 未运行。

完整 `nvidia-smi` XML、含本机绝对路径的原始结果和运行日志由 `.gitignore` 排除。仓库仅保留报告、复现源码、公开主题快照和明确脱敏的证据包。
