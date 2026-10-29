# Qwen3.6：下一轮 profiling 的可复现源码基线

2026-10-29，北京时间。按[总计划当前入口](../../INFERENCE_RESEARCH_PLAN.md)固定下一轮源码与实验配置。协议见[experiment-plan.md](experiment-plan.md)。本目录不包含优化补丁或新瓶颈结论。

**基线验收通过。** 22:47:43完成GPU验收与日常服务恢复，随后离线复核通过。小型结果见[summary.json](summary.json)，完整结果在本机 `validation-01/results.json`。这是下一轮受控profiling的可运行基线，尚无新瓶颈或优化收益结论。

## 本轮实际结果

设备为i7-12700、RTX5060 Ti16GB、128GB RAM、Windows11专业版26200，驱动610.88。

| 验证 | 真实结果 |
| --- | --- |
| 构建与选定测试 | `strata-q36`、`strata_kq`构建成功；17/17选定host/布局/采样测试通过；Ninja复查无工作 |
| 四臂正确性 | 每臂10个parity prompt；VERIFY、默认Graph请求MTP0、MTP2均与本轮旧内核参考逐token相同；各臂实际64 slots、0换槽 |
| 内核验证 | VERIFY436,050次比较、0 mismatch |
| MTP实际执行 | MTP2接受567/786个草稿；输出与参考相同，不是质量/准确率指标 |
| 两次新进程重复性 | 相同1K/64-token预热后，各运行1025/16385输入、64输出；共4条检查请求，两次同长度输出逐token相同，均fresh、MTPoff、length结束 |
| 实际布局 | 两次均chunk2048、每层63/256 GPU专家、packed Q8/MMQ开启、0换槽；未叠加#4335/#4347 |
| 同日HtoD控制 | 同一探针加载前24.894215、验收后24.810577GB/s，变化约0.336%；两次退出0 |
| 恢复与身份 | 原日常Flash-Next0.1.52恢复，`loaded=true`，配置SHA相同、无恢复错误；源码仍清洁，exe/DLL哈希未变 |
| 离线核验 | 原始四臂token、VERIFY/布局/草稿计数、两次输出、输入/脚本/编译配置/二进制与3608份ggml文件哈希复核通过；44份本地证据清单留存 |

参考10条输出长度为128/128/128/128/16/128/85/67/128/23；严格检查10条数量，未仅依赖zip截短比较。1K输出SHA-256为 `0b5a1ea52a88d40495085b558b6674fa7035a8697e8609ccc38b6391ac1e7908`，16K为 `d9fa9d31b1fea2e0ebca46ef3ccb4bb03c7b33d7db49e48b28407f9d2f986a33`，仅作为本轮冻结布局/64token复现参考，不要求其他布局或跨版本逐字相同。

## 固定的源码、依赖与配置

- 本轮fetch固定上游 `46c152a1310f77cd2f0ce2c7cd213962df14fe83`；CMake源码引擎版本为0.1.53，日常发布引擎仍为0.1.52。主工作区HEAD为 `8857fb6c`，二者不混用。相对旧 `5e8a4cca`，Qwen3.6专属源码/门禁没有Git差异，共享代码和构建配置有更新。
- 独立detached worktree：`build-native-baseline/src-main-46c152a1`；构建：`build-native-baseline/build-main-46c152a1-cuda132-sm120`。源码未修改，旧构建与报告保留。
- MSVC19.42.34436、CUDA13.2.51、sm_120、Ninja Release、CMake3.29.5-msvc4；模型为原Qwen3.6-35B-A3B UD-Q4_K_XL，22,853,663,008 bytes，SHA-256 `55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1`，本轮构建准备与GPU执行前各重新计算。
- ggml固定 `3cf03257f219afbe7334045ff7c6a06ac68c627d`，已有源码包SHA-256 `c076d7534afa0e5d0ec2a0d425b11e791c16f3de0d727221aea071cef156a280`。重新解压到独立依赖目录，全部依赖文件哈希保存在本机 `ggml-files.json`。其CMake自动向父目录查Git，日志显示的 `ggml commit: 8857fb6c` 是外层工作区元数据，不是ggml依赖提交；实际依赖身份以上述固定包和逐文件哈希为准。
- 复现基线：32K上限、chunk2048、7workers加调用线程、MTP0、GPU0、packed Q8与MMQ开启、纯贪婪且penalty关闭。专家预算自动初始化，随后冻结驻留；此为受控profiling基线，不代表日常动态换槽配置。

## 执行与复现

脚本都从仓库根目录执行；需要本机已有CUDA/MSVC/Anaconda及固定模型，不下载或改系统设置。

```powershell
python -u reports/tobeo-20261029/qwen36-repro-baseline/build_baseline.py
python -u reports/tobeo-20261029/qwen36-repro-baseline/validate_baseline.py --run-id validation-01
python -u reports/tobeo-20261029/qwen36-repro-baseline/summarize_baseline.py --run-id validation-01
```

构建脚本拒绝覆盖已有基线；构建复现时应在新的工作区运行或为新实验另设目录。GPU验收可使用新的 `validation-NN`，不覆盖已有结果；每次会短暂卸载日常模型，并在finally恢复此前已加载的服务。汇总脚本只核对证据，不发新请求。完整命令、工具链、构建缓存/编译数据库及exe/DLL指纹见本机 `build-results.json`。

本轮准备失败均保留：第一次是中文MSVC版本输出被GBK解码而报错，发生在配置/编译前；修正为保存原始字节，按 `--resume-preparation` 校验已有源码和依赖后继续。第二次构建与17项测试均已通过，但收尾脚本误用独立 `strata-q36` 不支持的 `--version`，返回usage/退出2；不是编译失败或模型加载失败。保留原脚本与 `build-attempt-01/02.json`，用 `--finalize-built` 核对已完成的测试、源码与二进制指纹后，仅修正版本元数据，不重编译、不重跑已通过的测试，也不把错误调用记作通过。

## 验证边界与下一步

本轮仅Windows/CUDA和当前硬件；选定测试不等于全量CTest，hybrid自动禁用Graph，组名中的Graph请求不代表独立Graph执行。没有测HIP/SYCL/Metal、完整质量、并发、长稳、HTTP或chunk4096；没有验证重新编译的二进制逐字节相同。短请求耗时不作优化加速或跨版本性能结论。

下一项是正常HtoD下的1K/16K Systems时间线：chunk2048与显式4096分别记录，保持packed政策一致并核对实际布局，先区分attention、CPU专家、传输与同步的关键路径，再决定是否恢复GQA。冻结驻留用于受控归因；若解释日常动态缓存，应另行确认动态布局，不能直接外推。本轮没有启动profiler、组合候选或修改默认。
