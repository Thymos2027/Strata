# 阶段 C：Nsight Compute 预检与采集准备

后续进展：北京时间 2026-10-23，application replay 的 1K 最小采集已成功，见[当天结果](../../tobeo-20261023/qwen36-compute/README.md)。以下保留准备与失败排障的历史范围。采集脚本仍在本目录，但后续结果和探针证据按北京时间的运行开始日期另行归档，`timing.json` 记录起止时间。

日期：2026-10-22。接续 [Systems 报告](../qwen36-profiling/README.md)和[瓶颈假设](../qwen36-profiling/bottleneck-notes.md)。**管理员计数权限已通过；第 04 次在 kernel replay 的显存保存/恢复流程报 LaunchFailed，同期驱动记录 TDR。留下的报告无效，尚无可解释的模型硬件计数。** 当前入口改为 application replay、1K、三个硬件指标的最小验证，等待管理员终端实测。引擎未修改，日常模型已恢复。

## 工具与权限的真实结果

使用 [NVIDIA CUDA 13.3.1 官方 manifest](https://developer.download.nvidia.com/compute/cuda/redist/redistrib_13.3.1.json) 的 Windows Nsight Compute archive：

- manifest 包版本 `2026.2.1.5`；实际 CLI 显示 `2026.2.1.0 (build 38283040)`，两者分别记录。
- 438,536,997 bytes；实测 SHA-256 与 manifest 一致：`42749828322bcdec2bd641e910042c562ca6f8d9e2d9623b9368e9a83d0bc94a`。
- 解压在本机忽略的 `build-native-baseline/toolchains/nsight-compute-2026.2.1.5/`，不安装驱动、不修改系统 PATH。
- 复用已验证的分段下载、重试、完整性校验；准备日志为 `prepare.console.log`，路径记录为 `compute-installed.json`，均保留在本机。

独立 `counter_probe.cu` 只分配 256 KiB，启动一个小 kernel、读取结果并释放内存。使用同一 MSVC/CUDA 13.2、sm_120 编译，普通运行输出 `CUDA probe passed: 1.000244`。只保留 Windows System32 的 PATH 时，构建与普通 CUDA 执行也通过；脚本会补入所选 Python 环境的工具路径。

最初在代理非管理员会话用 ncu 请求实际硬件指标 `sm__cycles_elapsed.avg`，结果为退出 1、无 `.ncu-rep`，明确报错：

```text
ERR_NVGPUCTRPERM - The user does not have permission to access NVIDIA GPU Performance Counters on the target device 0.
```

实际状态与原始输出见 [counter-status.json](counter-status.json)。该文件记录探针调用时的二进制哈希；后续编译检查会重建 `counter_probe.exe`，不应把其当前哈希当作旧调用时的哈希。新的探针调用会按 tag 另存 exe 和状态，避免覆盖证据。

`ncu --query-metrics` 与 section 查询成功，但这是指标目录查询，不是成功采集。另用纯指令指标 `sass__inst_executed_per_opcode` 做小探针，该版本/环境同样报权限错误，未取得指令计数。两次调用均显式设置 clock-control=none、cache-control=none，没有以提频或清缓存改变日常配置。

本轮是非管理员会话，本机装有 NVIDIA 控制面板 `8.1.969.0`。限制来自实际驱动错误，不是构建失败。NVIDIA 的[权限说明](https://developer.nvidia.com/ERR_NVGPUCTRPERM)提供两个入口：由管理员允许普通用户使用计数器，或以管理员身份运行 profiler。没有自动修改此设置。

同日用户反馈已在管理员终端重试。已有 `counter-probe-mtp0-cold-replay-01.console.log` 仍记录 ERR_NVGPUCTRPERM；再次执行的截图则是同名证据保护 `Evidence exists`，尚未进入新的权限检查。旧探针未记录进程管理员状态，不能据此判断该次调用是否提权。现已修正默认重试入口；新探针会打印管理员状态，并在自己的 `.status.json` 中记录 `process_is_admin`、Python 路径和 UTC 时间，供后续区分权限问题与重试问题。

随后第 02、03、04 次探针均实测成功：`process_is_admin=true`、退出 0、`permission_denied=false`，生成 `.ncu-rep`。第 02 次时间为 `2026-10-22T03:48:49.516892+00:00`。管理员权限预检已通过，正式模型采集的问题单独排查。

## 第 02 次正式采集超时

第 02 次 `r0-l1024/*.engine.log` 记录加载 6.0 s、专家布局准备 15.1 s、引擎内部 warm-up 11.9 s；客户端的 1025-token、64-token 预热请求耗时 prefill 12.989 s、生成 744.660 s。`capture.log` 只记录 ncu 连接进程，尚无目标 kernel 的 profiling 进度或有效报告。父进程在整个上下文运行 900 s 后超时，清理该进程树；`service-transition.json` 确认原先已加载的 Flash-Next 恢复成功。

可确认的原因是原时间预算不足以容纳这次受 profiler 影响的运行；预热本身就消耗绝大部分预算。尚未定位预热变慢的具体 CUDA 调用或驱动机制，不能将其说成目标 kernel replay 卡死，也不能当作无 profiler 性能退化。NVIDIA 的[开销说明](https://docs.nvidia.com/nsight-compute/ProfilingGuide/index.html#overhead)明确 profiling 会引入额外成本；其具体占比仍需另行诊断。

后续入口默认每个上下文最多 3600 s，包含加载、预热、请求和 profiler 收尾；这只是新的预算，不保证采集一定成功。每 30 s 打印耗时和最新子进程日志；子进程新增加载、预热完成、正式请求每 16 token 的阶段输出。失败保留 `failure.json`，继续清理本次进程树并恢复原服务。这些修改仅影响随后启动的脚本，用户已启动的第 03 次仍使用原 900 s 上限。

## 第 04 次：replay 内存操作失败与 TDR

第 04 次已越过预热（64-token 生成 741.350 s）并开始采集 `k_attn_part`。`capture.log` 先提示 `Backing up device memory in system memory`，随后 `LaunchFailed`。保存到本轮目录的 `r0-l1024/ncu-internal.log` 显示：

```text
Failed to launch memcmp kernel
Failed to compare memory (999)
Failed to optimize backing store
Failed to restore
Profile end failed (LaunchFailed)
```

Windows System 原始事件另存 `driver-events.json`。北京时间 13:26:01–13:26:04，nvlddmkm Event 153 记录 `Resetting TDR`、`Reset TDR`、`Restarting TDR`。可以确认采集失败与驱动超时复位发生在同一时段；尚未进一步确定是工具、驱动还是内存操作的具体限制，不能由此推断 attention 计算错误。

失败的 `attention.ncu-rep` 虽可导入，但唯一 kernel 的 grid/block 均为 `(0, 0, 0)`、耗时及多项硬件计数为 0；已导出到 `failed-report-metrics.csv` 留证，不作为有效测量。第 04 次 `service-transition.json` 与独立 health 均确认 Flash-Next 已恢复加载。

[NVIDIA application replay 说明](https://docs.nvidia.com/nsight-compute/ProfilingGuide/index.html#application-replay)指出，该模式通过重新运行应用获取各 pass，避免工具保存/恢复 kernel 内存；代价是重复加载和预热，并要求确定的执行顺序。因此下一次先用 application replay、strict 匹配，只测 1K、三个指标 `gpu__time_duration.sum`、`dram__bytes_op_read.sum`、`dram__bytes_op_write.sum`。这是采集流程验证，不能回答 L2/stall/occupancy，也不保证比之前更快或一定成功。

每个应用 replay pass 会在 `pass-NNNN/` 独立保存引擎日志和输出验证，避免第二次重跑被同名文件拒绝或覆盖第一份结果。要求所有 pass 的输出均与阶段 B 前缀一致；CSV 跳过单位行，必须只有一个目标 kernel、grid/block 与 Systems 一致，且三个指标有效、耗时大于 0。非零退出会保存 profiler 错误摘要并拒绝接收报告。未改变驱动或 Windows TDR 设置。

## 已定位的模型 kernel

[kernel-selection.json](kernel-selection.json) 由 `select_kernels.py` 从已验证的完整 Systems SQLite 中生成，包含原始报告 SHA-256、NVTX 边界和实际 launch shape。

| 条件 | 1K / MTP 0 | 16K / MTP 0 |
| --- | --- | --- |
| 输入 token | 1025 | 16385 |
| 过滤后的零基调用序号 | 760 | 760 |
| 对应 ncu 参数 | launch-skip=760、launch-count=1 | 同左 |
| grid | (5, 16, 1) | (65, 16, 1) |
| block | (256, 1, 1) | (256, 1, 1) |
| Systems 记录的 registers/thread | 40 | 40 |
| 正式请求开始时的过滤序号 | 650 | 650 |

这两个点均在客户端 decode NVTX 起点 200 ms 之后，且仍位于同一请求的 decode 范围，避免选到 prefill/warm-up。过滤以 function=`k_attn_part` 为准，skip 仅数匹配 kernel；[CLI 规则](https://docs.nvidia.com/nsight-compute/NsightComputeCli/index.html#profile)与本机 `ncu --help` 已核对。每个上下文只选一次调用，是机制诊断，不代表整条生成的平均值。

矩阵继续固定阶段 A exe、32K 配置上限、chunk=512、7 workers、64 专家槽位、MTP 0、原始贪婪协议，以及阶段 B 的输入和 64-token warm-up。正式请求输出 64 token，需要与阶段 B 对应前缀逐 token 一致。实际 NCU 报告的 grid/block、调用数和指标完整性仍须在采集后核对，不能只凭预先计算的 skip 宣称采样正确。

## 当前如何继续

可以由管理员在 NVIDIA 控制面板中，先选择“桌面 → 启用开发者设置”，再进入“开发者 → 管理 GPU 性能计数器”，允许普通用户访问。R610 的官方说明更推荐 NVIDIA App；若已安装，可在 System → Advanced → Developer 中找相应计数器设置。本机本轮检测到的是控制面板。

也可以不改普通用户权限，直接在**管理员 PowerShell**中运行下列脚本：

```powershell
& 'E:\Coder\LLM\Strata\reports\tobeo-20261022\qwen36-compute\collect.ps1'
```

入口使用已验证的 `D:\Program Files\Anaconda\python.exe`。查看完整命令而不改变服务：

```powershell
& 'E:\Coder\LLM\Strata\reports\tobeo-20261022\qwen36-compute\collect.ps1' -DryRun
```

如需明确指定每个上下文的时间预算，可使用 `-CaptureTimeout 3600`（单位秒）。请先等上一轮结束并完成服务恢复，避免并行运行两轮采集。

`run_compute.py` 会先重跑硬件权限探针；通过后才卸载日常模型，采集所选上下文，并在 finally 恢复原先已加载的服务。默认只做 1K 的最小验证；目前尚无成功的模型采集，这些后处理步骤不能算作已通过的 GPU 验证。

当前默认 application replay、三个 smoke 指标、cache-control=all、clock-control=none。通过最小验证后，再考虑 `-Case both -Scope full`：扩展为两个上下文和原先的七个 section（LaunchStats、SpeedOfLight、MemoryWorkloadAnalysis 及 Tables、SchedulerStats、WarpStateStats、Occupancy）。此扩展尚未实测，会增加 replay 成本；full 指标仍需人工核对完整性。清缓存和多次 replay 的结果是隔离诊断，不能直接与阶段 B 的 warmed、无 profiler 吞吐比较。

默认自动选择尚未使用的 `mtp0-application-smoke-NN/` 编号，同时检查目录和同名探针文件。旧 `mtp0-cold-replay-*` 证据保留。每次实际执行先创建目录保留计划，权限预检失败也算一次尝试；dry-run 不创建目录或运行探针。`-ReplayMode kernel` 仅保留用于显式诊断复现，不建议重复已失败的配置。

也可以指定全新的 RunId。显式指定已存在的目录或探针编号时，会在编译和 GPU 操作之前拒绝覆盖：

```powershell
& 'E:\Coder\LLM\Strata\reports\tobeo-20261022\qwen36-compute\collect.ps1' -RunId my-counter-retry-01
```

## 本轮验收范围

**Passed：**工具包大小/SHA-256/CLI 验证；独立 CUDA 探针编译与执行；干净 PATH 构建检查；指标与 section 目录查询；从 Systems 定位两个 matched ordinal；Python 与 PowerShell dry-run。

重试修复验证：默认 PowerShell dry-run 自动跳过已有 01 探针，选择 02；显式复用 01 的采集入口和独立探针均在编译前拒绝执行。临时目录回归检查覆盖仅存在探针日志、仅存在运行目录以及旧日志内容保留；Python AST、PowerShell 解析和 git diff --check 通过。当前代理进程管理员检测为 false，这不代表用户另开的管理员终端状态。未在该代理会话重复硬件采集；健康检查确认日常模型仍加载。

**Passed（后续管理员会话）：**第 02、03、04 次真实硬件计数探针成功，并生成报告。

超时修复验证：Python AST、PowerShell 解析、实际子进程正常退出与短截止时间超时检查通过；PowerShell dry-run 的自定义 4200 s 参数正确传给 Python。尚未验证新预算下的完整 GPU 采集。

用户随后中断第 03 次；检查时已无 ncu/strata-q36 进程，独立 `/health` 确认 Flash-Next loaded=true。旧 `service-transition.json` 记录恢复请求被 KeyboardInterrupt 打断，保留原记录；另存 `post-interrupt-health.json` 记录检查时的真实服务状态。后续脚本在恢复阶段暂时忽略 Ctrl+C，并提示等待健康检查，避免再次打断恢复。

replay 修复验证：本机 ncu 的参数帮助确认 application/grid/strict 参数存在；Python AST、PowerShell 解析和 smoke/full dry-run 通过。回归检查使用真实失败 CSV，确认零尺寸报告被拒绝；使用明确的合成 CSV 检查单位行处理、正确尺寸、零耗时和缺失/NaN 指标；临时目录检查多个 pass 保留不同证据。这些是脚本检查，不是 GPU 采集成功。

**Failed：**早期非管理员硬件计数探针与指令探针均报 ERR_NVGPUCTRPERM；第 02 次正式模型采集超时；第 04 次 kernel replay 失败并伴随 TDR。普通 CUDA 运算成功不能替代计数权限验证。

**未完成：**有效模型 kernel 的 NCU 采集、硬件指标解释；候选 kernel 与优化性能 A/B 尚未执行。研究计划的瓶颈结论/最小改动项仍不打勾。应先完成这些数据，再决定是否做 FP32 K/V 协作读取原型。
