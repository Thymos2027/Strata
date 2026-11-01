# WPR GPU队列工具短探针

2026-10-31。主线是瓶颈归因和可验证改进，见[总体状态](../../RESEARCH_STATUS.md)。本轮仅验证系统观测工具链，最多一次小型CUDA探针，不运行大模型矩阵、不做新优化。

[运行前协议](experiment-plan.md)、[后台程序](run_probe.py)。状态background-status.json，stdout/stderr在background.stdout.log/background.stderr.log。summary.json区分“工具探针成功”和“队列归因仍需审查”，不将ETL存在当作根因已知。

系统已有WPR GPU.Light profile和tracerpt；不安装新工具，不修改驱动/时钟/启动或注册表设置。先检查无其他WPR录制、再使用唯一命名会话；只停止/取消本任务创建的会话。finally恢复原日常模型/配置。原始ETL/XML含系统活动，只留本地。

2026-11-01归档复核：后台已于2026-10-31 12:56:25完成短探针及导出，summary显示probe_recording_passed=true、queue_attribution_ready=false。探针退出0，生成101711872字节ETL、解码565850条事件；12:55:40恢复日常服务且无恢复错误。目标PID候选事件的存在不代表队列/提交语义或时钟关联已经验收；下一步仅审查现有数据语义，不据此启动实模矩阵或确认根因。状态与日志以上述本机文件为准。

2026-11-01语义审查接续：已回读原17份证据及WPR停止状态，导出与collector丢失计数均0；已有目标进程Device/Context、QueuePacket/DmaPacket字段。发现XML时间偏移+07:59与控制记录+08:00不同，后续仅在[独立离线目录](../../tobeo-20261101/qwen36-wpr-review/README.md)复核原始QPC和packet关联，原始数据及manifest不改。

2026-11-01后续离线复核已完成：[原QPC及97条packet链核对通过](../../tobeo-20261101/qwen36-wpr-review/README.md)，包级工具门槛成立，默认XML时区不用于精细对齐。原始summary和17文件清单保留；没有重新采集GPU或确定模型根因。
