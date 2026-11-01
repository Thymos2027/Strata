# WPR短探针的离线队列语义与时钟复核

2026-11-01取舍更新：[当前采集诊断分支收尾](DECISION.md)，不再自动追加采集。拟议1K实模ETW/plain未启动，保留为备选。下文工具门槛结论保持，原版根因与新优化仍未完成。

2026-11-01。离线程序于09:18:21完成；用户返回后复核新7份与原17份封存文件、97条逐包记录及当前日常服务/配置通过。**原始QPC可与控制程序共轴，目标进程的包级队列链可核对；工具门槛通过，可准备有限实模ETW/plain对照。** 尚未采集该实模对照，也没有模型CUDA kernel级延迟或驱动根因结论。

[自动结果](summary.json)、[逐包账本](packet-ledger.csv)、[复核程序](review.py)。原17文件与本轮7文件manifest保持不变；本次接续判断另存本机acceptance.json。自动summary里的queue_attribution_ready=false/attribution_review_required=true是封存时的保守状态；本报告认可的是有边界的“包级观测工具门槛”，不把它改写为模型归因完成。

## 时钟审查

原XML的SystemTime显示+07:59，控制记录是+08:00。没有凭猜测把偏移改成+08:00，而是用系统tracerpt的-rts只读导出同一ETL。默认/原时钟两份导出均565850条事件，所筛选图形内核事件的类型、PID/TID与payload序列一致。

header PerfFreq为10000000Hz。目标进程25856的DxgKrnl Process Start/Stop原始QPC分别2774838329023/2774853698293，均位于独立控制边界2774838027853至2774853733285内。97条完整packet链的四个原始时间点也全部在该区间，单位换算及先后顺序通过。

因此后续可以直接用原始QPC与Windows perf_counter_ns比较，不需经过可疑日历时区字符串。该结论没有解释导出器为何显示+07:59，也不把UTC壁钟当微秒级证据：控制端UTC/QPC两端调用给出的偏移区间宽约259.8微秒，后续精细归因应使用QPC共轴。

## 目标进程归属与packet关联

按payload的hProcessId建立target PID→两个device的归属，再按hDevice建立14个context生命周期。没有简单把事件header执行PID当作工作归属：DPC/系统线程可能代表其他进程处理完成事件。

每个包的键为context生命周期加SubmitSequence，对应DMA使用ulQueueSubmitSequence；同时核对DMA提交/完成ID相同及原始QPC单调，避免仅按重复使用的handle或全局sequence强配。

| 检查 | 结果 |
| --- | ---: |
| 目标device / context生命周期 | 2 / 14 |
| 目标render QueuePacket Start（ID178） | 97 |
| 唯一对应DmaPacket Start（175）/Stop（176） | 97 / 97 |
| 完整render包链 | 97 |
| 未匹配/不唯一render键 | 0 |
| WPR及导出报告丢失事件 | 0 |

同context的同步packet start ID244/245共30/14条，未混入97条render链。14个context不表示14条CUDA stream；ETW packet也不等于一个CUDA kernel。本轮只确认提交/调度/完成的系统事件关联，不声称每条包覆盖一个专家或一个token。

97条链的Queue Start→DMA Start事件间隔中位60.7微秒、最大88.7375ms；DMA Start→Stop事件间隔中位274.8微秒、最大344.7217ms。全部原值保留，只是这次传输/计算工具探针的描述，不可对照此前模型566–632微秒的CUDA API→kernel指标当收益或根因。这些边界是记录到的系统事件，不是精确shader指令起止。

## 数据与恢复

原短探针用时约1.57秒，ETL101711872字节；导出摘要Total Events Lost=0，WPR状态Dropped=0且两个collector Lost均0。不把“报告为0”扩大为所有可能驱动事件均完整。原命名WPR会话已停止，原服务已在10-31恢复；此次完全离线，没有新的GPU采集或服务切换，回读时Flash-Next IQ3_S仍loaded=true、配置SHA相同。

本机保留原probe.etl/默认XML及本目录原QPC XML、clock-review.json、packet-review.json和两个manifest。ETL含系统活动/进程信息，只留本地；本轮没有安装工具、修改系统配置或自动外发。

下一步仅准备[1K受限实模ETW/plain协议](limited-model-plan.md)：原始未插桩870二进制，关闭Nsight/CUPTI，固定模型/布局，先做两对AB/BA。包级数据不能自动补出CUDA API或CPU job边界；失败或缺失就停止，不扩到16K矩阵。
