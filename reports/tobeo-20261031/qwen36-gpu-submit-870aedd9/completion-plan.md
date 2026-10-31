# 870aedd9迟启动复现与观察扰动：执行前协议

2026-10-31。接续10-30已通过的新基线及下一阶段协议。只调查870aedd9e1ebe1c91f94da93b59af17729f6c5c0，不合入新上游，不改变日常引擎。原Q4/32K/chunk2048/显式63slots后冻结/7workers加host/MTP0/packed-MMQ/GPU0/EAGER/贪心，各输入1025/16385token、64输出、独立进程同一r1-l1024/64预热。

在独立src-job-submit-870aedd9 worktree移植原NVTX job/phase/token边界与done_.fetch_add返回完成序号。原算术、claim、等待、原子内存序和stream策略不变，STRATA_Q36_JOB_TRACE=1显式开启标记。原baseline源码/二进制保持。独立build-job-submit-870aedd9-cuda132-sm120，CUDA13.2/sm_120，相关19测试及Ninja复查。探针先验证原生NVTX可采集，再卸载日常服务。

数值门槛只在第1轮运行：两长度×诊断off/on各64×248320全词表float32，全部有限且与870新基线同一强制历史逐位相同。实际MMQ、63槽位/chunk2048、0换槽及64完整输出均须通过。第2轮引用并重验首轮四份数值文件及同一诊断二进制的指纹，不把复用门槛称作八份新dump。

两轮独立进程观察共16条正式请求、四份trace：

1. 第1轮依次1K、16K；每长度baseline plain → diag off plain → diag on plain → diag on trace。
2. 第2轮依次16K、1K；每长度diag on trace → diag on plain → diag off plain → baseline plain。

每条有统一预热；每轮恢复日常服务后再开始下一轮。CPU sampling/context switch关闭，只采CUDA/NVTX。相邻比较一次改变构建、标记或trace中的一项；每格n=2，保留全部计时、顺序和警告，不选择最快trace，不作为优化收益或原版纯算术分解。

分析每轮每长度的63原生decode迭代：检查全部job完成序号、行覆盖、phase fork/join、token wall闭合、GPU提交API/设备关联，输出GPU半边API退出→pool起止→首kernel启动、上条可见GPU操作结束与CPU重叠。16K prefill尾部也验证任务/phase，完整GPU边仍限decode。按四份新trace各自计数迟启动比例；“两轮观察到”仅表示各自有严格满足早提交晚启动的层，比例和分布必须报告，不推断无profiler状态同样发生。发布者身份来自原子修改顺序，其时刻仅有body结束到标记的界限。

如诊断门槛/输出/布局失败，停止；如未复现，也保留全部结果不强行套旧解释。如复现，下一阶段再选择能区分内部提交、调度与CPU工作重叠的单因素诊断；本轮不改flush、stream、等待策略，不确认WDDM缺陷，不估算可回收延迟。

HtoD每轮前后>=15GB/s且漂移<=10%；finally终止本轮子进程并恢复开跑前服务/模型，核对原配置SHA；恢复失败不能通过。预检排除并行下载/转换/构建/采集。后台失败即停，输出状态、stdout/stderr、按轮原始记录与分析。最终静态manifest排除background动态文件、README、summary及manifest自身，保留原46c/870基线证据。新材料只本地，不自动发布。
