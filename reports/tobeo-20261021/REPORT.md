# tobeo：Strata 本机优化与上游贡献记录

日期：2026-10-21。项目：`E:\Coder\LLM\Strata`。本次允许短暂停服和多轮性能测试。

归档目录：项目内 `reports/tobeo-20261021/`。报告、PR 描述和复现脚本可纳入版本管理；本机测量 JSON、日志、配置和运行时状态由本目录 `.gitignore` 排除。已运行服务的 stdout/stderr 仍写入启动时指定的旧位置，本目录保存了迁移时的快照，未为移动日志中断服务。模型权重及引擎组件继续存放于 `D:\Models\Strata`。

## 设备与版本

- i7-12700，8 个 P 核 + 4 个 E 核；128 GB DDR4，4 × 32 GB，配置频率 3600 MT/s。
- RTX 5060 Ti 16 GB（驱动报告 16311 MiB），驱动 610.88；负载下 PCIe 5.0 ×8，探测吞吐约 25 GB/s。
- Windows 11 Pro 26200，Python 3.12.7，项目 `.venv` 使用 Anaconda Python 创建。
- 上游源码基线 `9de04cd4`，Control 0.1.46.3；实际签名 CUDA 13 引擎组件 0.1.46。
- 原版 Qwen3.8-Flash-Next GSQ-RCO IQ3_S，模型位于 `D:\Models\Strata\IQ3_S`，MTP 位于 `D:\Models\Strata\mtp`。

## 已应用的日常配置

仅向本机忽略的 `strata-iq3_s.json` 增加 `--pool-affinity p-cores`，保留 `--expert-cache auto`、PCIe 自动分配、`--spec 4 --spec-min-p 0.5`、64K 上下文、int8 KV、32K 常驻 KV、1024 MiB 显存预留。原配置备份：`original-config.json`。

P 核模式使用 7 个池工作线程，加主机线程，避免 E 核进入同一计算池。当前模型/上下文下自动缓存约 4190 槽、8186 MiB，初始化引擎报告剩余显存约 462 MiB；这些是引擎内部统计，并非系统整体空闲量。不要照搬确认实验的手动缓存参数到日常配置。

启动方式仍为项目内 `run-iq3_s.bat`；服务只监听 `127.0.0.1:8080`。恢复服务后的验证和资源采样另见 `final-verification.json`。

恢复后的单次 512 token 生成，API 报告解码 61.2 tok/s（独立功能与资源检查，不加入上面的 A/B 统计）。该请求启用模型默认思考，512 token 均为 reasoning，达到长度限制；另用关闭思考的简短请求检查可见中文回答，原始响应单独保留。

该次运行的资源观察：

- 模型引擎工作集约 50.1–50.5 GiB；私有提交约 64.7–65.3 GiB。工作集是驻留物理内存，提交量不是实际占用 RAM，两者不能相加。
- 全机可用物理内存约 58 GiB，提交余量约 42 GiB；128 GB RAM 在本次负载下有余量。
- NVIDIA 进程外采样的全卡显存约 15644–15740 MiB / 16311 MiB，余量约 571–667 MiB；服务状态的 GPU 统计存在时间差，数值略有不同。显存明显比系统内存紧张，保留 1024 MiB 预算预留，不进一步扩大缓存。
- GPU 活跃阶段采样利用率 91–99%，功耗逐步升至约 130 W，最高温度 58°C。此短测没有温度过高的证据，也不代表长期满载结论。
- CPU 总利用率在生成期间单点采样 45%，空闲采样 1%；并非完整时间序列，不能用这个数字推断所有核心利用率。绑定 P 核后的 E 核仍可供其他任务使用。
- 本轮没有采集完整磁盘吞吐/延迟时间序列；约 289K rows/s 是引擎初始化 PLE 探测，不是持续磁盘带宽。

## 同日性能比较

先分别冷启动默认配置与 P 核配置，运行项目 `tools/strata_bench.py --long --runs 3`。这是原有 quick/community benchmark，不能替代新质量标准，也没有执行准确率评测。

| 指标 | 默认混合核池 | P 核池 | 变化 |
| --- | ---: | ---: | ---: |
| 短对话解码中位数，9 样本 | 53.9 tok/s | 58.9 tok/s | +9.3% |
| 4K 预填充 | 1252.0 tok/s | 1255.3 tok/s | +0.3% |
| 16K 预填充 | 1622.4 tok/s | 1630.0 tok/s | +0.5% |
| 32K 预填充 | 1623.4 tok/s | 1620.4 tok/s | −0.2% |
| Agent 解码 | 59.4 tok/s | 66.7 tok/s | +12.3% |
| Agent 回合 TTFT | 3.00 s | 2.96 s | −1.2% |

两轮 failures 均为空。自动缓存分别分配 4088 和 4190 槽，因此这组收益不能全部归因于 CPU 亲和性。完整结果位于 `baseline/`、`pcores/`。

为控制缓存差异，又进行了三组交替顺序的全新引擎比较。两臂均传入 `--expert-cache 4000`：该参数按字节预算解析，在此 pack 上实际均为 **4302 槽 / 8406 MiB**，不是 4000 槽。每次 96 token 预热，再执行三个固定提示，各最多生成 256 token，贪婪采样，不使用会话检查点。计时不含加载。

| 提示 | 默认解码中位数 | P 核解码中位数 | 中位数比值变化 |
| --- | ---: | ---: | ---: |
| Python LRU 代码 | 59.42 tok/s | 63.69 tok/s | +7.2% |
| 英文故事 | 44.18 tok/s | 49.59 tok/s | +12.2% |
| 中文硬件文章 | 48.28 tok/s | 52.12 tok/s | +8.0% |

九个成对比较的吞吐增益均为正。代码输出三对逐 token 一致；故事仅一对一致，中文三对均不同。本次没有证明质量等价或输出逐字一致。固定缓存时引擎报告剩余显存仅约 242 MiB，因此生产保留自动缓存。原始 token、哈希、计时和引擎信息见 `affinity-confirmation.json`，脚本 `confirm_affinity.py`。

## 未采纳的调参

在 P 核模式下，两个固定提示、每项三轮，扫描 PCIe 比例 auto / 0 / 0.3 / 0.55 / 1.0 和 MTP 最低概率 0.3 / 0.5 / 0.7。每次生成 128 token，使用两个提示吞吐的几何平均数；这是有限提示的参数筛选。

PCIe 0.3 初筛略快，随后以 256 token、三组交替顺序比较自动分配，收益分别 +2.45%、+0.88%、−3.56%，未通过预设的三对均改善且中位数超过 3% 的采用门槛。全部交给 GPU（1.0）初筛明显更慢。MTP 阈值没有稳定优于原来的 0.5。因此两项均保留原配置。数据：`pcie-mtp-tuning.json`；脚本：`tune_pcie_mtp.py`。

## 上游问题与贡献

已创建独立分支、提交并推送，草稿 PR：

https://github.com/Niko1221/Strata/pull/3542

标题：`[TUI] recognise interpreter readiness behind Windows venv launchers`。

本机 `.venv\Scripts\python.exe` 是启动器，实际服务 Python 是其直接子进程。管理运行时原先要求 ready 文件 PID 严格等于启动器 PID，导致服务已运行但 readiness 失败。补丁通过 Windows Toolhelp 核验直接父子关系，同时保留存活检查、每次启动的 attestation 和 generation 检查；停止操作仍管理原启动进程/Job。独立工作树 `E:\Coder\LLM\Strata-contrib-venv-ready`，提交 `41e534b32c5b5db2b7496dd0e3199054e19baf72`。日常主工作树没有套用此源码补丁。

验证证据：

- 原版生命周期测试启动失败；补丁后的同一测试通过 start / verify / restart / stop。
- 4 个 Windows 进程关系测试通过，包含实际 venv 启动器场景和 snapshot 失败时拒绝匹配。
- 更新器聚焦集成测试通过。
- 实际 IQ3_S 在修复后的管理运行时启动、显式验证、中文生成、停止通过；启动器 PID 与服务 PID 确实不同，ready 和启动凭据均有效。见 `patched-runtime-proof.json`。
- runtime 全套 41 项：38 通过、2 平台跳过、1 失败。失败是终止后 `_pid_exists` 仍为真；在未修改基线先调用 `adopt_user_defaults()` 后可复现，同上游 #3428 涉及的默认 DACL 问题相关，未在本 PR 扩大修复。
- 未执行 Linux/macOS 平台测试；未触及 C++/CUDA/HIP/SYCL，无原生后端构建。PR 保持草稿，以上限制已写入描述。

已查重的相关线程：

- #3428：Windows 子进程默认权限修复，仍需与其协同，避免混在本 PR。
- #3459：5060 Ti GUI `startup_wait_expired` 报告，未证实根因相同，不宣称本 PR 能解决。
- #3235 等：benchmark 读 UTF-8 文件时在 GBK 系统失败。本机也复现，以 `PYTHONUTF8=1` 绕过；已有多份修复，没有重复开 PR。
- #1200：同型号 GPU 历史测量；#2274：12700K/7900 XTX 亲和性结果。平台和配置不同，均没有直接作为本机性能承诺。

## 后续有价值但尚未验证的方向

- 大页分配当前报 1314（缺少权限）。启用需要系统权限变更和重新登录，本次没有修改；没有端到端收益数据，不能宣称更快。
- 128 GB 内存可能容纳额外 PLE RAM 表，但本轮未测 `--ple-io ram`。当前 SSD 探测约 289K rows/s，不能仅凭剩余内存推断加载到 RAM 会改善吞吐。
- 没有测试其他量化、长上下文 OOM 边界、并发压力或回答准确率；本次结果限定于此模型、引擎和固定提示。

恢复原配置可复制 `original-config.json` 覆盖本机 `strata-iq3_s.json` 后重启。测量中的日志、JSON 和脚本均保留在本目录，未提交模型、本机绝对路径配置或运行日志到上游。

## 追查 runtime 权限失败（同日补充）

再次查询，上游 [PR #3428](https://github.com/Niko1221/Strata/pull/3428) 仍为 open、未合并。为验证它是否能解决本机剩余失败，新建独立工作树 `E:\Coder\LLM\Strata-verify-dacl`，在本 PR 的 `41e534b3` 上 cherry-pick #3428 的 `14b1d8f0`，组合验证提交为 `44b16b88`。没有把他人的修复混入 #3542，也没有修改日常运行代码、系统 ACL 或管理员权限。

原因：`adopt_user_defaults()` 修改当前进程令牌的默认 DACL，之后创建的子进程也使用它。原来的 `FA` 是文件权限掩码，缺少查询进程需要的权限；退出后再按 PID 查询时可能遇到 access denied，而存活检查为避免误判受保护进程，将其保守视为仍存在。#3428 将这一处默认权限改为 `GA`，让 Windows 按目标对象映射权限；不是给 Everyone 开权限，也不是让用户永久以管理员运行。

验证命令均使用项目 `.venv\Scripts\python.exe`，cwd 为组合验证工作树，`PYTHONUTF8=1`：

- 显式调用 `private_files.adopt_user_defaults()` 后，仅执行原失败的 `test_liveness_check_does_not_end_the_process_it_asks_about`：1 项通过，见 `runtime-with-dacl-liveness.log`。
- `python -m unittest discover -s tests/terminal -p test_private_files.py -v`：14 项中 13 通过、1 平台跳过，见 `private-files-with-dacl.log`。
- `python -m unittest discover -s tests/terminal -p test_winproc_parent.py -v`：4 项通过，见 `parent-pid-with-dacl.log`。
- 显式调用 `private_files.adopt_user_defaults()` 后运行完整 `test_runtime.py`：41 项中 **39 通过、2 平台跳过、0 失败**，242.332 秒，见 `runtime-with-dacl-full.log`。

这些组合结果不等于 #3542 当前独立分支已全绿。正式审查前应在最终提交上重跑相关检查，不能把组合提交的结果冒充单独提交的结果。查询 #3542 当前提交的三个 Actions 工作流均为 `action_required`，尚无成功运行的证据；需由上游处理工作流状态。修复通过不代表维护者承诺合并。
