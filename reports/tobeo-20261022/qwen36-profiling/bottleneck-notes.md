# 瓶颈观察与待验证假设

2026-10-23 后续：已补 [1K/16K 的三个 Compute 指标](../../tobeo-20261023/qwen36-compute/README.md)与[1K CPU IP/环境诊断](../../tobeo-20261023/qwen36-profiling/README.md)。独立传输探针约 1.73 GB/s，低于历史约 25 GB/s；NVML/PnP 报告冲突、原因未定，正常条件的关键路径结论仍待复核。CPU 样本大量落在等待工作循环，不能将 GPU 空隙等同于专家数学计算。已有 [PR #3641](../../tobeo-20261023/qwen36-pr3641/README.md) 提供 FP32 GQA 开关，局部正确性验证通过；本轮优先验证已有方案，未声称自写内核或性能收益。以下保留最初观察。

2026-10-22，RTX 5060 Ti 16GB、Windows 原生固定源码基线、Qwen3.6 UD-Q4_K_XL、64/256 固定专家槽位。实测依据和限制见[正式报告](README.md)，无 profiler 的速度依据仍为[阶段 B](../qwen36-context-curve/README.md)。

已确认的现象：`k_attn_part` 从短上下文的小热点，变成长上下文中累计 GPU 耗时最高的 kernel。MTP 0 的均值从约 78.81 增至 891.43 μs/调用，而 native Q8 matvec 单次均值基本稳定。16K 的 attention 区间并集占所选 decode 窗口约 22.05%（MTP 0）或 34.45%（MTP 2）。这支持将下一项硬件计数分析集中在 attention，而不是同时修改多个算子。

这不是“唯一瓶颈”结论。窗口仍有约 49%–72% 未被 GPU kernel/copy/memset 覆盖；CPU 专家、host 调度、同步、profiler 等原因尚未分离。CUDA EventQuery 调用也很多，但其累计 CPU API 时间与 GPU 活动重叠，不能再加到端到端时间上，不能仅据调用数宣称轮询有 bug。

只在本轮带 profiler 的窗口中，若假设 attention 的全部区间都处于关键路径且可以完全消除，乐观 Amdahl 上界约为 1.28×（16K/MTP 0）和 1.53×（16K/MTP 2）。这些不是优化预测，不应套用到阶段 B 的无 profiler 曲线。

待验证的静态假设：`k_attn_part` 的 FP32 K/V 读取和 query row/head 间重复读取，可能造成长上下文开销增长。现有时间线没有给出 DRAM/L2 流量、sector 利用率或 stall，不能据此称为 HBM bandwidth bound。query row、GQA 复用和线程访问布局的解释均仍属 unconfirmed static analysis。

下一步顺序：

1. 用 Nsight Compute 选取预热后、实际 decode 的代表性 `k_attn_part`，先比较 MTP 0 的 1K/16K，核对 launch shape 和 query row；以本机 CLI help 确认过滤和跳过 warm-up 的参数，避免把 prefill kernel 当成 decode。
2. 检查 DRAM/L2 流量、访问合并、stall、寄存器和 occupancy；区分流量过大、访问效率和调度限制。MTP 2 的多 query row 随后单独分析。
3. 若访存证据支持，再做保持 K/V FP32、专家布局、缓存容量和默认行为不变的协作读取/tile 原型。先做 kernel 数值验证，再做同工具链、无 profiler、交替顺序的端到端 A/B；现有数据不能代替候选验证。
4. 若关键路径证据转向 CPU/host，补 CPU 时间线，重新排序方案；不要仅为了兑现 attention 选题而继续内核改动。

本轮发现的另一个可审阅方向是“请求 Graph”与“实际 Graph”状态的诊断：main-hybrid 会自动关闭 Graph，容易使 benchmark 组名误导覆盖范围。是否已有同类诊断需先查上游，本轮没有据此开 issue、提交 PR 或改动协议。
