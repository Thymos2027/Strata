# 固定46c152a1的job级依赖与关键路径诊断

2026-10-30，构建/采集前写定。接续CPU/IP试采；用户要求完成job级关键路径。旧数据缺少job生命周期，因此在独立46c152a1 worktree做最小NVTX诊断构建，原基线源码/exe/DLL及主工作区计算源码保留。只增加观测，不改pool算法、算术、任务数、线程、等待策略或GPU流。不带入PR3905或其他优化。

原Q4/SHA、32K、chunk2048、63slots冻结、7workers、MTP0、packed/MMQ、贪婪无penalty。两个输入1025/16385token、各64输出，每进程同一1K/64预热。诊断仅以STRATA_Q36_JOB_TRACE=1开启，原配置不变。NVTX使用现有Nsight内置header-only SDK，记录头文件和二进制SHA；不下载安装。

## 门槛和采集

1. 新构建CUDA/sm120，17项选定测试、Ninja检查及本地CPU-only NVTX预检。只验证本机CUDA，不请求代码PR审阅，不宣称HIP/SYCL兼容。
2. 诊断off/on两长度各64行完整词表logits，与此前原基线完整f32的SHA、有限性和64输出逐位一致才进入采集；保留原辅助入口和相邻DLL，拒绝回退到非MMQ。四份新dump不作性能依据。
3. 每长度原exe、诊断off、诊断on不挂profiler各一次，然后诊断on各一份CUDA/NVTX trace，CPU sampling/context switch关闭以减少已有15%左右的组合扰动。共八条新进程测量；输出、fresh、0草稿、63slots/2048chunk、0换槽和退出0逐条核对。全部计时保留，n=1的比值只描述构建/标记/采集扰动，不当作优化收益或替换旧五组。
4. 编号连接原生token迭代、forward、GPU-half、CPU MoE、phase epoch及task index/执行线程。这里pool task是专家矩阵的行分片，不能把task数量叫专家数量。每phase核对任务ID0..n-1恰好一次、发布先于执行、job执行范围闭合、执行行数覆盖phase矩阵、同线程串行、GU→量化→DOWN及后续CPU上传/merge依赖。独立核对63个原生decode token迭代、每token40层MoE；实际无CPU缺失专家的层另列，不捏造phase。
5. job执行范围在done计数release之前结束；发布标记在实际epoch发布之前。观察边界、claim/完成原子及唤醒的时间差单列为交接/观测残差，不把它们冒充纯算术、纯调度或精确可回收时长。phase host结束包含wait_done和wait_parked；最长worker分支、最后job结束及join尾部都保留，不能把多线程task耗时相加当wall time。
6. 形成逐phase、逐token账本：每个token wall window用不重叠的主线程阶段归还，另列并发task分支、GPU工作/空隙和CPU产生结果→GPU copy/merge的关联。报告的是这两个固定workload中已观测、带扰动的job/phase依赖闭环；不据此宣称全系统OS内部根因、无扰动原版的精确分摊或优化收益。若观测缺边或门槛失败，保留缺项而不强行勾选。
7. 保存health/配置及进程；GPU阶段前后同一探针HtoD>=15GB/s。正常或失败均清理本控制器子进程并恢复同一日常Flash-Next服务、模型与配置SHA。不覆盖原证据；新结果只在本地，不自动发布。
