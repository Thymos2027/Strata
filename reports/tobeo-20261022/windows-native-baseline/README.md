# Windows 原生源码构建与 Qwen3.6 正确性基线

日期：2026-10-22。设备：Windows 11、i7-12700、RTX 5060 Ti 16GB、128GB DDR4，驱动 610.88。此目录单独保存 Windows 原生结果，[前一天的 WSL 实测](../../tobeo-20261021/qwen36-source-baseline/README.md)保持独立。

## 工具链检测更正

之前 `vswhere -all` 未带 `-products *`，遗漏了独立的 Build Tools。正确查询应包含：

```powershell
& 'C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe' -latest -products '*' -version '[17.0,18.0)' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
```

本机实际已有 VS 2022 Build Tools 17.12.4，位于 `D:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools`，包含 MSVC toolset 14.42.34433（编译器报告 19.42.34436）、CMake 3.29.5-msvc4；Windows SDK 为 10.0.22621.0。不能将前次查询空结果解读为本机未安装 MSVC。

本轮通过 Microsoft 签名验证的 bootstrapper 启动安装，安装器先更新自身，随后提示 Build Tools 已存在并退出 1；没有重新安装 C++ 编译器。后续复用已有工具链。

新增 CUDA 使用官方 13.2.0 Windows redistributables，nvcc 为 13.2.51。六个组件均与 NVIDIA manifest 的 SHA-256 一致，解压到项目忽略的 `build-native-baseline/toolchains/cuda-13.2.0`。没有安装/替换显卡驱动，没有修改系统 PATH。现有 Anaconda 提供 Ninja。

官方依据：[Microsoft 安装参数](https://learn.microsoft.com/en-us/visualstudio/install/use-command-line-parameters-to-install-visual-studio?view=vs-2022)、[NVIDIA CUDA 13.2 Windows 安装说明](https://docs.nvidia.com/cuda/archive/13.2.0/cuda-installation-guide-microsoft-windows/index.html)。

## 源码与配置

- Strata：`83e6b05cd7b97ee194f330f0247faa76deb73f1b`，用 `git archive` 导出独立、未经修改的源码。
- ggml：仓库固定的 llama.cpp commit `3cf03257f219afbe7334045ff7c6a06ac68c627d`，从 GitHub commit archive 准备，实际 archive SHA-256 记录在本机 `source-manifest.json`。
- 编译器：MSVC x64；CUDA architecture：`120`；Release；Ninja；原生专家支持开启；`STRATA_BUILD_TESTS=OFF`、`STRATA_BUILD_CONVERSATION_TESTS=ON`。
- 构建目标：`strata`、`strata-q36` 与脚本列出的 14 个独立 host/conversation 辅助测试。
- 所有编译器和 CUDA 环境只写入构建子进程；不会永久改动日常运行环境。编译器路径传给 CMake 时使用正斜杠，避免反斜杠被 CUDA 编译器识别流程解释成转义。

源码、构建目录和编译数据库都在 `build-native-baseline/` 下，和 WSL 的 ext4 构建完全分开。本轮原生构建与测试脚本不调用 WSL。

Windows Git 导出的文本保留本机 CRLF 行尾。`q36_engine.cu`、`q36_kernels.cuh` 用 `git hash-object --path=...` 规范化后的对象分别为 `b0d7e75cb2712b407987132b4b4e946a67aaf700`、`21617b0bbdd5e1be211c0b2147f732152f5e0acc`，与固定 revision 的 blob 一致；不是通过改动计算源码获得构建成功。

## 复现命令

从项目根目录的 Windows PowerShell 执行：

```powershell
python -u reports/tobeo-20261022/windows-native-baseline/prepare_cuda_windows.py
python -u reports/tobeo-20261022/windows-native-baseline/build_native.py
python -u reports/tobeo-20261022/windows-native-baseline/run_correctness_native.py
```

准备脚本复用前一天的分段续传和 SHA-256 校验代码，构建脚本自动查找现有 VS 2022 并调用 `vcvars64.bat`。构建有 Windows 文件互斥锁，不允许两个 Ninja 同时写同一目录。独立源码快照用于基线，不要将候选补丁放在其中。

正确性脚本使用与 WSL 相同的四臂方法，但参考输出由 **Windows 当前构建的旧内核路径**现场产生，未把 Linux 输出当作标准答案：

| 臂 | 设置 |
| --- | --- |
| 参考 | old kernels、no graph、MTP 0 |
| 内核验证 | current kernels、no graph、VERIFY、MTP 0 |
| Graph | current kernels、graph、MTP 0 |
| MTP | current kernels、graph、MTP 2 |

每臂运行仓库 10 个 parity prompt，各最多 128 token。固定 8K 最大上下文、prefill 512、7 workers、每层 64 expert slots，设置 `STRATA_Q36_FIXED_SLOTS=1`。既检查全部 token，也检查两侧都有 10 个 prompt，以及 VERIFY 实际比较次数和 mismatch 数。

GPU 检查会暂时通过本机 `127.0.0.1:8080` 控制接口卸载当前模型，完成或失败后在 `finally` 中恢复原先已加载的模型。服务进程和日常配置保留。

后续直接调用原生引擎时，用以下入口自动设置 CUDA DLL 搜索目录；引擎参数原样传递，不永久修改 PATH：

```powershell
python reports/tobeo-20261022/windows-native-baseline/run_engine_native.py --version
```

## 当前结果

**Passed：**

- CUDA 六个 Windows 组件的 SHA-256 校验。
- 未修改的源码成功生成 `strata.exe` 和 `strata-q36.exe`；版本 `0.1.46.3`，支持列表 `qwen4exp qwen35moe`。
- 选定的 14 项 host/conversation 测试全部通过，CTest 共约 14.36 s。
- 构建完成后 Ninja dry run 返回 `no work to do`，未发现无改动时仍要求重编译的情况。
- 原生 VERIFY 完成 436,050 次内核比较，0 mismatch。该计数来自本次 Windows 日志，不沿用 WSL 的计数。
- 四组 GPU gate 均正常退出。当前内核、CUDA Graph、MTP 2 三组分别与 Windows 旧内核参考输出 10/10 prompt 完全一致。
- 参考输出长度为 128/128/128/128/16/128/85/67/128/23，共 959 token，另外三组逐 token 相同。
- MTP 2 的 10 条请求实际接受 567/786 个草稿；接受率不是模型质量或正确率。
- 检查包装脚本退出 0，原 Flash-Next IQ3_S 服务已恢复，健康接口 `loaded=true`；日常配置未修改。

| 对照 Windows 旧内核参考 | prompt 数 | token 结果 | 退出码 |
| --- | ---: | --- | ---: |
| current、no graph、VERIFY、MTP 0 | 10 | 10/10 完全相同 | 0 |
| current、graph、MTP 0 | 10 | 10/10 完全相同 | 0 |
| current、graph、MTP 2 | 10 | 10/10 完全相同 | 0 |

Windows 原生基线阶段已完成。后续本机优化可以使用这套源码、编译参数和原生输出作参考；不能将这些单次 gate 的吞吐写成优化收益，也不能据此断言 Linux/Windows 的数值路径、速度或质量等价。

原生二进制位置：

```text
build-native-baseline/build-83e6b05cd7b97ee194f330f0247faa76deb73f1b-cuda132-sm120/strata.exe
build-native-baseline/build-83e6b05cd7b97ee194f330f0247faa76deb73f1b-cuda132-sm120/strata-q36.exe
```

原始本机证据：

- `prepare-cuda.console.log`、`cuda-installed-manifest.json`：下载、校验和工具组件。
- `build-native.log`、`build-driver.console.log`、`build-summary.json`：完整构建命令、结果、二进制哈希。
- `correctness-summary.json`、各臂 `.json`、`.console.log`、`.engine.log`：检查命令、token、内核验证与对照结果。
- `service-transition.json`：模型切换及恢复状态。

本目录只将报告、脚本和忽略规则纳入 Git；原始本机 JSON/日志留在磁盘。若要提交上游报告，应另行脱敏并纳入必要的小型原始证据。

## 已遇到的准备问题与限制

- 初版构建包装脚本没有用完整路径启动 `cl.exe`，Windows 子进程查找失败；改为解析 vcvars 环境、统一环境变量键名并使用完整编译器路径。
- 初次 CUDA 编译器识别的 host compiler 路径含反斜杠，被解释为转义；改为 CMake 参数中的正斜杠路径，随后配置通过。
- 编译和 CTest 已通过后，首次 `strata.exe --version` 返回 `0xC0000135`。CUDA 13.2 Windows 包将运行时 DLL 放在 `bin/x64`；加入子进程 PATH 后，版本和支持列表检查通过。仅重跑相关启动检查，没有为此重复编译或重复全部测试。
- 编译过程有 C4819 等代码页警告和上游警告，原始记录保留，不把警告自动归类为引擎错误。
- **Not run：** 独立 llama.cpp oracle、日常动态布局的跨臂 parity、auto chunk、视觉、并发、长上下文、完整质量、长期稳定性、HIP/SYCL，以及 Flash-Next 在新源码二进制上的真实推理。未开启完整原生测试套件，不能称为全部项目测试通过；恢复的日常 Flash-Next 仍使用原发布引擎。
