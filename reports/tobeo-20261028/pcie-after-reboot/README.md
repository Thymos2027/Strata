# Windows 重启后的 PCIe 传输恢复验证

日期：2026-10-28，北京时间。用户已自行重启 Windows，请求复查。系统报告最近启动时间 07:50:02。本轮没有改驱动、时钟、电源、BIOS 或 Strata 配置；未启动 Strata，初查无 Python/Strata 进程。

## 同一探针对照

直接运行 10 月 24 日生成的 `transfer_probe.exe`，未重新编译。当前 SHA-256：`712995e1d2d12b0806eb621edc2c653b59b45a106118de7c5bfac577bf4972a8`。驱动仍为 610.88。两次均无模型加载、无 profiler，测试大小与次数由同一 exe 固定。前次结果见[根因排查](../../tobeo-20261024/pcie-root-cause/README.md)。

| 路径 | 10-24 重启前 GB/s | 10-28 重启后 GB/s |
| --- | ---: | ---: |
| pinned CPU→GPU | 1.725655 | 24.881625 |
| pinned GPU→CPU | 1.806933 | 28.369929 |
| GPU mapped host read | 1.608412 | 16.651046 |
| 显存内复制（单向 payload） | 186.724392 | 190.355314 |
| CPU memcpy | 17.241300 | 17.964073 |

CUDA Event 与 wall clock 一致：本轮 H2D wall=24.831195 GB/s，D2H wall=28.343567 GB/s。程序退出码 0，内置数据抽查通过。D2D 和 CPU memcpy 不是硬件峰值测试。

## 链路与结论

- 启动前空闲 P8：current Gen1、max Gen5、×8；该空闲 Gen1 不代表异常。
- 本次独立测试期间全部采到的 current generation 为 Gen5（25 ms 请求采样间隔，实际还含 API 调用开销）；重启前 40 次样本全为 Gen1。
- H2D 恢复历史约 25 GB/s 量级。恢复发生在用户整机重启后，驱动版本未变，独立 exe 未变；强烈支持此前为持久驱动/设备传输状态异常，而非单纯 Strata 引擎版本回归。
- 结合 10-22 13:26 TDR 与首次低带宽紧邻的时间线，TDR 后异常恢复不完整仍为首要解释。但本次距前次四天，不是立即交替的受控重启 A/B；没有重新触发 TDR，不能把具体驱动内部机制或物理重训练根因记作已证明。
- 仅确认本轮传输与负载代际恢复，未启动日常模型、未测 decode，也未完成正常环境下的正式性能配对或完整 profiling。后续实验仍需同日基线与正确性门禁。

## 证据与入口

`run_probe.py` 复用旧 exe；运行时证据另存 `transfer-result.json`（含哈希及 NVML 样本）、`transfer.log`、`nvidia-after.xml`、`pnp.json`、`boot-events.json`，未覆盖旧数据。重复运行前请另建输出目录。

## 上游报告价值评估（2026-10-28）

重新检索 Strata issues（含 closed）：`TDR PCIe`、`bandwidth reboot`、`Nsight TDR`。未发现明确覆盖“Compute kernel replay 后独立传输持续低吞吐、重启恢复”的同案；这不是对全部评论、附件和 PR 的穷尽证明。#2137 是 Linux 驱动参数引起的 Gen1/页面显示问题，#485 是旧版短探针低估，均不适合将本次当作同一缺陷追加。

建议作为诊断报告保留并准备提交，优先 NVIDIA Nsight Compute/驱动渠道：Nsight Compute 官方[已知问题](https://docs.nvidia.com/nsight-compute/ReleaseNotes/topics/known-issues.html)已说明 profiling 的额外成本可能导致超时，值得报告的是超时恢复后跨进程传输持续降低，而不是仅报告发生 TDR。实际 CLI 2026.2.1.0 (build 38283040)，archive 2026.2.1.5；原第 04 次采集的确切命令与错误需从该次产物提取，不能用第 01 次 collection-plan 冒充实际第 04 次命令。

Strata 侧可以提交独立的 `[Other]` 排障经验/诊断报告，定位为维护者可参考的已测现象，附 NVIDIA 讨论链接；当前不足以提交“Strata 引擎版本导致链路降级”的 bug 结论。尚缺最小可重复触发案例；无需主动再次制造 TDR 才能报告。明确只有一次已关联的事件序列、恢复前后相隔四天，未证实具体因果。不将建议写成已提交；本轮未发送任何外部消息。
