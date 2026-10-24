# Qwen3.6 源码构建与正确性基线

日期：2026-10-21。对应[实践计划](../../INFERENCE_RESEARCH_PLAN.md)的阶段 A。本目录用于基线准备，不是性能优化或模型质量报告。

2026-10-22 阶段 C 覆盖范围更正：固定 64/256 专家槽位使该 revision 进入 main-hybrid，源码在 `q36_engine.cu:2887–2889` 自动关闭主模型和 MTP Graph。历史组名 `graph-mtp0/2` 仅表示未传 `--no-graph`，不代表实际 Graph 路径已被验证。原始 token 对照与 VERIFY 结果保持不变。

## 环境与隔离

主机为 Windows 11、i7-12700、RTX 5060 Ti 16GB、128GB DDR4，驱动 610.88。当轮采用本机已有 WSL Ubuntu 26.04 建立独立 Linux 源码基线。

2026-10-22 更正：之前的 `vswhere` 检测遗漏 `-products *`，漏掉 D 盘已有的 VS 2022 Build Tools/MSVC，不能据此认定本机没有 MSVC。Windows 原生构建另见[次日记录](../../tobeo-20261022/windows-native-baseline/README.md)。本报告中的 WSL 实测结果保持原样；选择 WSL 并非项目不支持 Windows。

WSL 可见约 62 GiB 内存、16 GiB swap，并可访问同一张 GPU。后续测量需要监控 WSL 内存和分页。WSL 结果不能直接与之前 Windows 发布引擎结果做性能 A/B，也不能代替 Windows 原生构建验证。

- Strata revision：`83e6b05cd7b97ee194f330f0247faa76deb73f1b`。
- 通过 `git archive` 导出干净源码，未包含当前工作区的报告改动；未修改引擎源码。
- ggml 来源：仓库固定的 llama.cpp commit `3cf03257f219afbe7334045ff7c6a06ac68c627d`，从 GitHub commit archive 单独准备。
- 构建目录位于 WSL ext4：`~/strata-research/`；模型继续使用 D 盘现有文件，不复制权重。
- 工具：CMake 4.2.3、Ninja 1.13.2、GCC/G++ 14.3.0、Python 3.14.4。
- CUDA 13.2.0 最小工具集放在 `~/strata-research/toolchains/cuda-13.2.0`，各组件按 NVIDIA redistributable manifest 校验 SHA-256。不安装或替换 GPU 驱动。

模型重新计算的 SHA-256：

```text
Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1
```

与 Strata 固定值一致。完整本机路径和环境记录见本机 `environment.json`。

ggml 的 commit archive 不带 `.git`，因此编译日志显示 `ggml commit: unknown`。依赖归属由固定下载 URL 和本机 `ggml-archive.sha256` 记录，不将该日志字段当成 Git revision 已自动识别的证据。

## 复现入口

从 Windows PowerShell 运行下列命令；下载与构建需要联网和足够磁盘空间：

```powershell
wsl -d Ubuntu -- python3 -u /mnt/e/Coder/LLM/Strata/reports/tobeo-20261021/qwen36-source-baseline/prepare_cuda.py
wsl -d Ubuntu -- bash /mnt/e/Coder/LLM/Strata/reports/tobeo-20261021/qwen36-source-baseline/prepare_source.sh
wsl -d Ubuntu -- bash /mnt/e/Coder/LLM/Strata/reports/tobeo-20261021/qwen36-source-baseline/build_baseline.sh
```

WSL 中已安装 CMake、Ninja、GCC/G++ 14 和 Python venv 包。脚本不负责安装这些主机依赖。源码快照脚本只应在专用基线目录使用，它会重新导出固定 revision；不要把候选补丁放在该快照中。

构建日志：`~/strata-research/logs/build-baseline.log`。工具安装清单：CUDA 目录下的 `installed-manifest.json`。下载脚本支持分段续传和重试，SHA-256 不匹配则停止，不继续解压。

`build_baseline.sh` 使用互斥锁拒绝同时构建同一目录，PATH 仅保留 Linux 工具与选定 CUDA，避免继承 Windows 工具搜索路径。

## 正确性方案

编译成功后，可从 Windows 使用以下包装脚本：它通过 `127.0.0.1:8080` 的现有控制接口卸载当前模型，检查后在 `finally` 中恢复原先已加载的模型，不停止 Python API 服务。

```powershell
python reports/tobeo-20261021/qwen36-source-baseline/run_with_service.py
```

手动确保显卡空闲后，也可直接运行：

```powershell
wsl -d Ubuntu -- python3 -u /mnt/e/Coder/LLM/Strata/reports/tobeo-20261021/qwen36-source-baseline/run_correctness.py
```

脚本使用源码快照中的 `q36_solo_gate.py` 和 `q36_cmp_gate.py`，10 个仓库 parity prompt，每项最多生成 128 token。固定 8K 最大上下文、prefill 512、7 workers、每层 64 expert slots，并设置 `STRATA_Q36_FIXED_SLOTS=1`。

四组初始化实际记录：64/256 专家每层驻留 GPU，共约 4.69 GiB；18.75 GiB 专家在 pinned host memory，7 workers 加 host 共 8 个 CPU 计算线程。`--expert-vram 10.0` 是参数预算，不是实际专家驻留量。日志确认本构建默认使用 K-quant MMQ prompt 路径；因此不将本次基线描述为旧版 FP16 prompt 路径。

依次比较：

| 臂 | 目的 |
| --- | --- |
| old kernels / no graph / MTP 0 | 同一源码中的旧 kernel 参考路径 |
| current kernels / no graph / VERIFY / MTP 0 | 逐项内核比较及输出对照 |
| current kernels / 默认 Graph 请求 / MTP 0 | hybrid 自动关闭 Graph，默认请求的输出对照 |
| current kernels / 默认 Graph 请求 / MTP 2 | hybrid 自动关闭 Graph，固定专家布局下的 MTP 输出对照 |

不仅检查退出码和生成 token，还要求 VERIFY 真正完成正数次比较且 mismatch=0。检查两份结果都包含 10 个 prompt，避免比较器的 `zip` 截断漏检。

这是同一源码的实现路径对照，没有独立 llama.cpp oracle。固定 slots 是诊断条件，不能代表日常动态专家路由；prefill 512 的结果也不自动适用于 auto chunk。视觉、并发、完整质量、长上下文、性能和其他后端需另行验证。

## 当前验证记录

**Passed：**

- 模型 SHA-256 重新校验。
- CUDA 13.2.0 / sm_120 的 `strata`、`strata-q36` 源码构建成功；`strata --version` 为 `0.1.46.3`，`strata --families` 输出 `qwen4exp qwen35moe`。本机完整日志为 `build-baseline.log`。
- CUDA 构建目录中的 3 项选定 conversation 测试全部通过，耗时约 0.12 s。没有将它们等同于全部 CUDA 内核测试。
- `STRATA_Q36_VERIFY=1 --no-graph --mtp 0` 完成 442,935 次内核比较，0 mismatches。覆盖本次仓库 gate 的 10 个短 prompt；VERIFY 只覆盖现有实现中已接入的检查，不是全部算子的独立 oracle。
- 独立 host 构建下，全部 14 项已注册测试通过，耗时约 5.36 s。包含 conversation cache/file/memory、split failure、session reclaim、message boundary、draft KV plan、coupled draft、spec probability、bf16 bits 和 batch 辅助测试。原始输出保存在本机 `host-ctest.log`。
- 四组 solo gate 全部正常退出。参考路径的 10 个输出分别为 128/128/128/128/16/128/100/67/128/23 token，共 974 token；另外三组每个 token 均与参考一致，三次比较分别为 10/10 prompt identical。
- MTP 2 的 10 条请求合计接受 569/810 个草稿，验证的并非仅有配置开关。其余三组 MTP 0 的请求草稿计数为 0。接受率不是回答正确率。
- 测试包装脚本退出码 0；原 `127.0.0.1:8080` Flash-Next IQ3_S 已恢复，健康接口 `loaded=true`，WSL 测试引擎已退出。没有修改日常服务配置。

输出对照：

| 对照旧内核参考路径 | prompt 数 | token 一致性 | 退出码 |
| --- | ---: | --- | ---: |
| 当前内核，no graph，VERIFY，MTP 0 | 10 | 10/10 完全相同 | 0 |
| 当前内核，默认 Graph 请求（hybrid 关闭），MTP 0 | 10 | 10/10 完全相同 | 0 |
| 当前内核，默认 Graph 请求（hybrid 关闭），MTP 2 | 10 | 10/10 完全相同 | 0 |

本机 `correctness-summary.json` 记录二进制/提示文件 SHA-256、完整命令、环境覆盖、退出码、VERIFY 和严格比较结论；各臂 `.json` 保留完整 token。`service-transition.json` 保存服务切换前后状态，`.console.log` 与 `.engine.log` 保留原始输出。

这支持将该构建用作后续同环境 A/B 的参考。不能据此解释之前 Windows 动态布局下 MTP 输出不同的全部原因，因为系统、chunk 和布局等条件不同；也不能把四次 gate 中偶然观察到的吞吐差异作为优化收益。

**Failed / 已定位的准备问题：**

- 初次 host CTest 运行只编译了 3 个目标，另外 11 项显示 Not Run。随后补齐全部目标，14/14 通过；这不是已复现的引擎测试失败。
- CUDA 13.0.2 配置在编译器识别阶段失败：系统 `mathcalls.h` 的 `rsqrt/rsqrtf` noexcept 声明与 CUDA CRT 头文件冲突。失败发生在编译 Strata 之前，完整日志保留为 `~/strata-research/logs/configure-cuda130-failure.log`。改用独立的 CUDA 13.2.0 工具集继续，未修改系统头文件或项目源码。
- 下载时出现 TLS/partial transfer 中断，已通过分段续传、重试及最终 SHA-256 校验处理。
- CUDA 13.2 初次配置缺少 redistributable `lib/` 到 nvcc 所需 `lib64/` 的目录映射，补充工具集内的符号链接后通过编译器识别。日志为 `configure-cuda132-layout-failure.log`。
- 构建重试曾重复启动同一目录的 Ninja，中止重复进程后出现缺失对象文件。已加入互斥锁并重新构建；该操作失败不作为源码缺陷。日志为 `build-interrupted-failure.log`。

**Not run / 边界：** Windows 原生源码构建、HIP/SYCL、独立 llama.cpp oracle、日常动态专家布局的跨臂 parity、auto chunk、视觉、并发、长上下文、完整质量与长期稳定性。未安装或运行 Nsight，尚无 profiler trace 或正式速度 A/B。完整原生测试套件没有启用，不能把本次选定检查称为全量 CTest 通过。

后续状态（2026-10-23）：这里原定的阶段 B 已完成，见[Windows 原生上下文曲线](../../tobeo-20261022/qwen36-context-curve/README.md)；阶段 C 也已有 Systems 与部分 Compute 证据。本文固定的旧 revision 仍是历史构建证据，不是同步后 `7ddc17a3` / v0.2.3.1 的当前基线。新的执行入口见[总计划](../../INFERENCE_RESEARCH_PLAN.md)。

原下一步为：按计划阶段 B，使用同一源码与工具链准备固定最大上下文的 1K/4K/8K/16K 曲线；输入与输出需容纳于新配置，记录实际布局。不要直接拿本次 8K 上限配置发送 16K 输入。该项现已按上述范围完成；当前仍没有自己的 attention 内核改动。

本目录 `.gitignore` 仅允许报告、脚本和忽略规则进入 Git。本机 JSON、日志保留在磁盘；如要提交上游，需要将必要的小型原始证据脱敏后另行纳入报告 PR。

参考：[贡献要求](../../../CONTRIBUTING.md)、[Qwen3.6 验证说明](../../../docs/QWEN36.md)、[NVIDIA CUDA 13.2 Linux 安装说明](https://docs.nvidia.com/cuda/archive/13.2.0/cuda-installation-guide-linux/index.html)。
