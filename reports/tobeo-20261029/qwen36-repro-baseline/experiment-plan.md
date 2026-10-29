# Qwen3.6 下一轮 profiling 的可复现源码基线

2026-10-29，北京时间，GPU 验收前写定。此次只建立基线，不执行优化 A/B、Nsight 采集或上游发布。

- 本轮 `git fetch upstream main --no-tags` 得到 `46c152a1310f77cd2f0ce2c7cd213962df14fe83`，固定此提交，不在运行中追随远端更新。独立 detached worktree 与独立构建目录，不覆盖旧 `5e8a4cca` 构建。
- 相对旧基线，`src/qwen35`、`tools/qwen35` 没有 Git 差异；共享代码和 CMake 有变化，源码版本为 0.1.53。这些是静态审查，不替代本轮构建和 GPU 验收，也不表示日常发布引擎已升级。
- 使用已有 MSVC 19.42、CUDA 13.2、sm_120、Ninja Release。ggml 固定 `3cf03257f219afbe7334045ff7c6a06ac68c627d`，校验已有源码压缩包并重新解压到独立依赖目录。记录完整配置/编译/测试命令、源码身份、工具链版本、模型与二进制 SHA-256。
- 模型保持已有 Qwen3.6-35B-A3B UD-Q4_K_XL，22,853,663,008 bytes，预期 SHA-256 `55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1`；本轮重算。

## 验收顺序与停止条件

1. 构建 `strata-q36`、`strata_kq`，运行历史 16 项选定 host/布局/采样测试，另加共享 defaults 的 `nv_defaults_test`。不是全量 CTest 或跨后端验证。
2. 保存日常 Flash-Next 配置哈希与 `/health`。GPU 实验仅在本机服务可正常卸载后开始；完成或失败均恢复原先已加载的服务，核对配置哈希和 loaded 状态。清理仅限本控制器子进程。发现其他研究/下载/GPU 任务争用则停止 GPU 验收，保留准备结果。
3. 复用现有 transfer_probe，同日加载前/验收后分别测量；退出 0 且 pinned HtoD 不低于 15 GB/s 才接受本轮环境。该门槛只用于排除历史约 1.7 GB/s 异常，不是硬件峰值要求。
4. 当前源码四臂门禁：8K 上限、chunk512、64 slots、7 workers、冻结专家驻留，旧内核参考 / VERIFY / 默认 Graph 请求 MTP0 / MTP2；每臂 10 个 parity prompt、最多 128 输出。严格检查数量和全部 token 相同，VERIFY 比较数大于 0、mismatch 为 0。hybrid 自动禁用 Graph，不宣称 Graph 执行覆盖。
5. 固定下一轮测量基线：32K 上限、chunk2048、7 workers、MTP0、packed Q8 与 MMQ 开启、GPU0、纯贪婪/无 penalty。自动专家预算后冻结驻留（`STRATA_Q36_FIXED_SLOTS=1`），记录实际槽位、chunk 与换槽，不沿用绕过政策的历史固定 slots 作为自动预算证据。
6. 两次独立进程，各做相同 1K/64-token 预热，再运行既有 1025/16385-token 合成输入，各生成 64 token；要求 fresh、MTPoff、完整输出计数、进程正常退出、两次相同布局下输出逐 token 相同，且冻结驻留无换槽。若不一致，保留失败并诊断，不用旧结果补齐。
7. 完成后重新核对源码清洁、exe/DLL、输入和配置哈希；写本轮独立报告及小型汇总，更新总计划的当前入口与清单。门禁失败先记录，不继续 profiler 或性能矩阵。

本轮短请求耗时用于确认基线可运行，不作为优化收益、统计性能结论或与旧版本的速度对比。chunk4096、动态换槽、完整质量、并发、长稳、HTTP、独立 Graph 和 Nsight 留待后续另立范围；基线通过不等于瓶颈归因完成。
