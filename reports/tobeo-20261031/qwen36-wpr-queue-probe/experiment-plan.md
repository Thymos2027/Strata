# WPR短探针协议：只验证工具，不扩展模型矩阵

2026-10-31，开跑前固定。依据[总体状态](../../RESEARCH_STATUS.md)的停止条件，本轮只进行一次已校验transfer_probe.exe小型CUDA传输/计算探针，原SHA712995e1d2d12b0806eb621edc2c653b59b45a106118de7c5bfac577bf4972a8。不启动Nsight/CUPTI，不加载Qwen实模，不改引擎或系统持久设置。

实际预检系统WPR10.0.26100 CoreSystem，GPU.Light在file模式下每collector为64×1024KB buffer；不沿用memory模式按大RAM配置的数千buffer。tracerpt为系统已有工具。命令以本机help及[Microsoft WPR CLI文档](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpr-command-line-options)为准，profile采用GPU.Light/filemode，临时文件保留本目录temp。

检查管理员、磁盘、已有录制和其他GPU/下载/转换任务；先记录日常health/config、卸载已知日常模型。为本次PID生成唯一WPR instance名，-instancename必须作为最后参数；只操作该实例。启动成功后只运行一次小探针（30秒超时），记录PID、UTC及perf_counter_ns边界、退出码与原输出。录制状态和collector丢失信息在停止前保留，随后-stop合并ETL，finally确保仅本会话停止/取消并恢复原日常服务与配置。探针或停止失败不计通过，不自动重跑。

恢复服务后再用tracerpt转换本次ETL为XML和summary，最多180秒。只读流式统计provider、event ID/task/opcode、payload字段、ProcessID/目标PID候选关联和少量样例。图形内核事件的执行PID可能是系统线程，payload中的context/queue字段必须另行解释；直接PID计数不等于完整归因。丢失事件按原始WPR状态/summary记录，不能因文件可读就默认0。

工具探针通过仅要求：已知探针退出0、命名会话正常结束、ETL非空且tracerpt成功、XML有事件、原服务/配置恢复。是否提供可用的目标PID/context/queue提交语义、时钟和丢失信息，由下次回读审查后单独决定，queue_attribution_ready默认false。如果事件不足，停止大模型扩测并说明唯一缺口，不继续堆同类trace或自动安装整套WPT。

静态manifest排除background动态状态/日志、README、summary及manifest自身。长任务后台运行，告知日志后结束本轮。ETL/XML可能含进程、路径等系统活动，仅本地保存，不自动外发；本轮无模型/内核性能、无原版CUDA kernel级延迟或驱动根因结论。
