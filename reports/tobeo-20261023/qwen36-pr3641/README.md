# PR #3641：Windows / Blackwell 的局部正确性验证

日期：2026-10-23。**已有方案在本机完成 CUDA 构建、三个选定数值/布局测试，以及真实 Q4 模型的 1K 短输出对照。性能实验因同日传输吞吐异常暂缓。** 本轮贡献是复现与硬件验证；attention 实现归属 acrogenesis 的 [PR #3641](https://github.com/Niko1221/Strata/pull/3641)。

## 来源与构建

本轮 API 查重时 PR open、非 draft；固定 head `f3f2136f194bdc42d07961bef0ce66b2811f58cb`，base `011c9e600a93bbc9fd451c563501b5831c32bbca`。另有 draft [#3678](https://github.com/Niko1221/Strata/pull/3678) 和 [#3700 的重叠讨论](https://github.com/Niko1221/Strata/issues/3700#issuecomment-6339718829)。因此使用现有 FP32 GQA 对照开关做验证，避免另起同类实现。

源码在 `build-native-baseline/src-pr3641-f3f2136f/` 的独立 worktree；构建前后 Git tracked 文件均无改动。新构建目录为 `build-native-baseline/build-pr3641-f3f2136f-cuda132-sm120/`。使用 MSVC 2022 / 14.42 toolset、CUDA 13.2、sm_120、Ninja、Release，ggml 继续固定 `3cf03257f219afbe7334045ff7c6a06ac68c627d`。

164/164 步完成所选目标和依赖，生成 `strata-q36.exe`、`strata_kq.dll` 及所选测试。exe SHA-256 为 `af7bb496fac2fb3a94737474e0a58d1870a3bee8af9026749a3406921fd14b6b`，见 [build-summary.json](build-summary.json)。这不是全量 target 或全量 CTest 验证。

## 已实际通过

| 测试 | 结果与范围 |
| --- | --- |
| `model_family_test` | 退出 0，布局/拒绝条件测试通过 |
| `q36_attn_parity` | 退出 0，独立 CPU oracle；F32/F16、不同 GQA 比例、causal tail、row offset、session tables；包含 262,144-cell 合成用例 |
| `q36_f16_parity` | 退出 0，独立矩阵/专家及空分组数值用例通过 |
| 真实 Q4，GQA=0 | 1,025 输入、64 输出，与原阶段 B 前缀逐 token 相同 |
| 真实 Q4，GQA=1 | 相同输入与输出长度，与 GQA=0 及原阶段 B 前缀逐 token 相同 |

大上下文 attention oracle 只比较选定 heads，并不是实际模型 262K 上下文验证。数值误差、逐项输出与实际命令保存在 [validation-summary.json](validation-summary.json)。本轮没有跑全量测试，也没有验证 HIP/SYCL 的本机编译或硬件执行。

真实模型使用已有 Qwen3.6-35B-A3B UD-Q4_K_XL。两臂使用同一个新二进制，只设置 `STRATA_Q36_GQA=0/1`；KV 保持 FP32，未选择 `--f16-weights` 或 `--kv f16`。最大上下文 32768、chunk 512、7 workers、固定 64 专家槽位、MTP 0，采样为阶段 B 相同的纯贪婪协议。每臂先执行同一 64-token warm-up。

两个正式请求均 fresh、生成 64 token、以 length 结束且没有 MTP 草稿。输出 SHA-256 相同：`916be811c6156cb34a324fb194896f9449852fb5ffa25500e5df4d4107152d3e`。详情见 [results.json](results.json)；原始请求/资源与日志保留在本机 `gate-r0-l1024/`。

这说明该固定 head 在本机真实 Q4 短请求上的兼容性，不建立全模型、全 prompt 或长上下文数值等价结论。候选 kernel 的真实 GPU 时间线尚未另采。

## 性能条件与接续入口

同日独立探针确认 HtoD 约 1.73 GB/s，历史引擎探针为约 25 GB/s；NVML 与 PnP 的链路报告也有冲突，见[环境诊断](../qwen36-profiling/README.md)。本轮 gate 的单次时间不作性能结果，不计算加速比。

性能入口的前置检查已实际拒绝当前异常条件，且没有创建 benchmark 目录。16K 实模门禁、至少五组交替 A/B 与候选 GPU 时间线均留待环境恢复后执行。恢复环境并复核同日控制后：

```powershell
# 全部上下文的正确性门禁，保存到新的 gate/，保留已有 gate-r0-l1024/
& 'D:\Program Files\Anaconda\python.exe' 'E:\Coder\LLM\Strata\reports\tobeo-20261023\qwen36-pr3641\run_ab.py' --mode gate

# 需上述完整门禁通过；同一二进制、FP32 KV、五组 AB/BA、每请求 256 输出
& 'D:\Program Files\Anaconda\python.exe' 'E:\Coder\LLM\Strata\reports\tobeo-20261023\qwen36-pr3641\run_ab.py' --mode benchmark --pairs 5
```

以上是待执行步骤。正式测量还要复核每组的链路与资源工况，保留全部单次值，检查短上下文/prefill/启动开销，并与无 profiler 的端到端结果一起解释 kernel 收益。

当前交付为本地验证报告，未向上游发送消息、开 issue 或提交 PR。后续可把完整实测作为 #3641 的补充证据；应继续注明作者、固定 revision、验证范围和缺项。
