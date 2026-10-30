# 正常工况 Qwen3.6 Systems 采集协议

2026-10-30，北京时间，模型加载与新测量前写定。接续[已验收源码基线](../../tobeo-20261029/qwen36-repro-baseline/README.md)，不修改计算源码、不换模型、不追随上游新提交。

## 范围

- 固定 `46c152a1310f77cd2f0ce2c7cd213962df14fe83`、原exe/DLL与Q4模型SHA，MSVC19.42/CUDA13.2/sm_120。重新核对身份和模型完整SHA；日常配置使用本轮实际文件与哈希，不要求与模型目录整理前的旧配置相同。
- Nsight Systems2026.1.3.425，使用已有工具、记录CLI/包身份。同日 `status --environment` 实测本会话Administrator privileges=No、Sampling Environment=Fail；profile帮助也说明CPU sampling需要管理员。本轮使用CUDA/NVTX、sample=none、cpuctxsw=none，不修改系统权限或用旧异常工况CPU样本代替新证据。
- 32K配置上限、7workers加调用线程、MTP0、GPU0、packed Q8/MMQ开启、纯贪婪且penalty关闭；自动预算后冻结驻留。分别运行显式chunk2048、4096，记录实际槽位，不叠加#4335/#4347。两种chunk可能改变槽位与数值，属于两种完整配置，不能称为隔离chunk的纯内核对照。
- 沿用1025/16385-token公开合成输入，每次64输出。每个输入/配置均新进程、相同独立1K/64-token预热。先做无profiler参考，再采集同配置trace：共4个无profiler请求、4份正式trace，每格n=1。不是性能收益统计或五组A/B。
- chunk2048的输出还须与已验收基线64-token参考相同；chunk4096建立自己的同日参考，不要求跨chunk输出相同。每次必须fresh、无MTP草稿、64输出且length结束；trace与对应无profiler输出完全一致，chunk/slots匹配、冻结后0换槽。

## 进入与停止条件

1. 不占用GPU的NVTX预检生成报告并导出SQLite，确认完整范围；同时保留采样权限检查。预检通过不代表模型GPU采集已通过。
2. 保存当前health、日常配置SHA和进程清单；只有日常服务可正常卸载且没有其他研究/下载任务争用，才开始GPU测量。加载前与所有采集后用同一个transfer_probe，HtoD低于15GB/s或退出非0则停止接受正常工况结论。阈值仅排除历史约1.7GB/s异常。
3. 依次采集chunk2048的1K/16K，再独立采集4096的1K/16K；每格先无profiler、后有profiler。保存全部原始请求、日志、命令和失败；输出/身份/布局失败即停止，不用历史结果补齐。profiler耗时超过同日参考3倍时停止扩大采集，先保存诊断并复查带宽，不将其当作模型回归。
4. 每份trace导出SQLite，验证闭合的request、prefill-to-first-token、decode-after-first-token范围与实际引擎PID的GPU记录；检查驱动兼容、引擎CUDA警告、明确丢事件/overflow/error。保留全部诊断，控制器无CUDA或引擎无NVTX等角色相关提示单独解释，不能写“全部警告为零”。
5. 正常结束或失败均终止本控制器的实验子进程并恢复原日常模型；核对health.loaded、模型、配置SHA、源码/二进制身份。恢复完成后再做离线分析，避免分析时间占用日常GPU。

## 分析与交付

按两个客户端观察窗口分别裁剪GPU kernel/copy/memset及CUDA runtime API，计算区间并集、重叠与未覆盖时间；报告主要kernel、attention、HtoD bytes、同步API及其与GPU活动的交集。NVTX由控制器标记，首token接收边界不等于精确引擎step边界。

CUDA API和GPU空隙可缩小问题，但没有CPU采样、调度或CPU专家内部标记时，不能把空隙直接命名为专家计算/自旋等待、把API调用累计耗时当作可回收时间，或宣布完整关键路径归因。attention占比仅用于“假定全部串行且完全消除”的理想收益空间估算，不承诺GQA收益。若证据不足，保留完整CPU归因为未完成。

交付新日期的报告、JSON/CSV、代表性GPU/API时间线和一页有边界的瓶颈观察；原始nsys/SQLite/完整日志仅本机留存。总计划只勾选本轮实际完成的采集子项，完整profiling/质量/动态缓存/Compute/内核优化不自动完成。
