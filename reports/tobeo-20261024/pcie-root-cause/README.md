# TDR 后的主机/GPU 传输异常定位

日期：2026-10-24，北京时间。用户授权按需停止 Strata，以诊断优先。本次卸载日常模型后测试；没有重置显卡、重启机器或改驱动、电源、TDR、BIOS 设置。服务外壳保留，模型当前未加载。

## 已定位的范围

强证据支持：10 月 22 日 Nsight Compute kernel replay 期间发生 TDR，随后同一启动参数的日常引擎首次记录持续低 HtoD；跨进程、模型卸载、服务重启后仍存在。最优先假设是 TDR 后驱动/设备传输状态未恢复。尚未通过驱动或系统复位前后对照证明因果，不能称已经确定物理链路降级或驱动内部缺陷。

## 时间线

| 北京时间 | 本机证据 |
| --- | --- |
| 10-22 13:08:25 会话 | strata-iq3_s.log：engine 0.1.46，HtoD 25.0 GB/s |
| 10-22 13:26:01.397 | System/nvlddmkm 153：Resetting TDR occurred on GPUID:100 |
| 10-22 13:26:04.238 | Reset TDR occurred on GPUID:100 |
| 10-22 13:26:04.757 | Restarting TDR occurred on GPUID:100 |
| 10-22 13:26:06–07 | 旧 Compute 第 04 轮 ncu-internal.log：context state transfer/restore failed、LaunchFailed、return 999 |
| 10-22 13:26:07 会话 | 日常 engine 0.1.46 同参数启动，四次 HtoD 均约 1.7 GB/s |
| 10-24 10:26:40 会话 | 服务重启恢复温度遥测，但 HtoD 仍 1.7 GB/s |

系统最近启动时间为 10-21 09:38:41，本次查询时尚未经历整机重启。TDR 不是通过时间猜测：原始事件 XML 已保存。旧 kernel replay 证据路径为 `reports/tobeo-20261022/qwen36-compute/mtp0-cold-replay-04/r0-l1024/ncu-internal.log`。

## 模型卸载后的新实测

驱动 610.88，CUDA 13.2 编译的新独立程序，无 profiler。设备缓冲区合计 128 MiB、pinned host 64 MiB；每种方向预热后测试。CUDA Event 与主机 wall clock 对照，抽查数据。退出码 0。

| 路径 | 有效传输 GB/s（十进制） | 范围 |
| --- | ---: | --- |
| pinned CPU→GPU | 1.725655 | 64 MiB ×128；wall 1.725581 |
| pinned GPU→CPU | 1.806933 | 64 MiB ×128；wall 1.806859 |
| GPU 显存内复制 | 186.724392 | 64 MiB ×256，按单向 payload 计，不把读写相加 |
| CPU memcpy | 17.241300 | 64 MiB ×128，wall；不能等同于整机 RAM 理论带宽 |
| GPU kernel 读取 mapped host | 1.608412 | 64 MiB ×32，结果抽查通过 |

模型卸载后 nvidia-smi 显存约 1328 MiB，排除本次测试被日常模型挤满显存。CPU memcpy 和 D2D 只用于区分路径，不声称它们达到正常硬件峰值。H2D/D2H/zero-copy 均慢，把范围集中到主机与 GPU 的路径；并非只某一个 Strata kernel 或启动探针异常。

## 链路读数与 Monitor 的限制

- 测试期间 40 次 NVML 采样 current generation 全为 1，宽度 ×8。
- GPU 的 Windows PnP CurrentLinkSpeed/MaxLinkSpeed 均为 5，CurrentLinkWidth=8；上游 Intel PEG10-460D 没有返回 CurrentLinkSpeed/Width 属性，未获得其 PCI 配置空间的实时 Link Status 寄存器。
- nvmlDeviceGetPcieSpeed 返回 32000，但 NVIDIA 文档对其输出描述包含 Max Link speed，不能直接当成物理当前 Gen5 的独立证明；GetPcieLinkMaxSpeed 返回枚举 5。代际 API 返回 current/max/gpu-max=1；记录这些不一致，不任选其一当结论。
- nvmlDeviceGetPcieReplayCounter=0；10-21 至查询时的 WHEA-Logger 查询结果为 0。两者不证明不存在硬件或重训练问题。
- 本次明确复现 Monitor 吞吐可能超过拷贝探针：NVML RX 峰值 5489.831 MB/s，拷贝有效 H2D 仍 1.726 GB/s。该计数与 payload/time 不一致，不能拿峰值证明已恢复，也不能只用负载 Gen1 与吞吐宣布物理链路已确认 Gen1。未定位计数差异来源。
- 当前电源计划为高性能；未显式设置 TdrLevel/TdrDelay/TdrDdiDelay。无修改。

NVIDIA 文档：[PCIe 查询 API](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html)。[Microsoft TDR 机制](https://learn.microsoft.com/en-us/windows-hardware/drivers/display/timeout-detection-and-recovery)说明超时恢复会要求驱动重新初始化并 reset GPU；该机制说明不是本机根因证明。

## 尚缺的决定性对照

在已保存证据后，执行一次明确获准的驱动/设备重置或 Windows 重启，再以同一 exe 运行上述短测试。若无需版本/参数变更即可从约 1.7 恢复到历史约 25 GB/s，会强烈支持 TDR 后持久设备/驱动状态异常；若仍慢，再检查链路协商、驱动版本/BIOS及硬件路径。用户此前处于远程操作场景，系统/设备复位可能断开连接，本轮不自动执行。

## 文件

`transfer_probe.cu` 与 `run_transfer_probe.py` 是可审阅的测试入口。本机运行证据：`transfer-result.json`（含 NVML 时序）、`transfer.log`、`build.log`、`events.xml`、`nvidia-events-all.json`、`pnp-during-probe.json`、`nvml-extra.json`、`nvidia-before.xml`、`whea.json`。重新运行前应另建目录保存结果，避免覆盖本轮证据。
