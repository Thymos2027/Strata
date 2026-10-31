# 同一870诊断二进制：job标记off/on的采集对照

2026-10-31运行前写定。目标是补齐diag off + CUDA/NVTX trace，与同一诊断二进制的diag on trace比较，不修改引擎、stream、等待或算术，不宣称性能优化或无profiler根因。

复用build-job-submit-870aedd9-cuda132-sm120及原870aedd9诊断源码；原Q4/32K/chunk2048/63固定slots/7workers加host/MTP0/packed/GPU0/EAGER/贪心。每条独立进程，同一r1-l1024/64预热；1K/16K实际1025/16385输入，各64输出。两臂只切换STRATA_Q36_JOB_TRACE，Nsight CUDA/NVTX/CPU sampling关闭/context-switch关闭选项相同，客户端request标记相同。

已有19测试/四份完整logits是同一二进制的历史正确性门槛；开跑前重验原126份证据、源码/二进制/模型、数值原文件和参考指纹，不称为新构建、新测试或新dump。每条新请求须与原870参考64-token输出相同，fresh/0草稿/63slots/chunk2048/0换槽、退出0。off trace的原生JT事件必须为0，on trace必须存在，防止只看环境变量而未核对开关实际生效。

顺序预定为两轮16条请求/八trace/八plain：

1. 第1轮1K→16K，每长度off plain、on plain、off trace、on trace。
2. 第2轮16K→1K，每长度on trace、off trace、on plain、off plain。

每轮采集前后HtoD>=15GB/s、漂移<=10%；每轮finally恢复开跑前日常模型与配置，再开始下一轮。排除其他下载/转换/构建/采集。失败即停、保留现场，不自动改配置或外发。

## 共同筛选与指标

selector.py已在旧四份870 on trace上与独立NVTX MoE/CPU-GPU明细逐层交叉验证，共10080层的kernel设备start/API退出/层序完全相同；在看到新off数据前固定筛选。

仅用客户端request界限、engine PID、CUDA kernel名和顺序筛选：1K请求必须有2520个native_gu_kernel，16K必须有2560个；16K前40个为T=1 prefill尾部，取最后2520个作为63次原生decode×40层。该集合须在单stream且关联到唯一engine CUDA launch API。两臂配对的2520层grid/block/shared-memory形状必须逐层相同，任何数量/关联/形状异常停止，不调整筛选追随结果。CUPTI进程ID提取屏蔽VM高位；此前预检遗漏VM掩码的脚本快照保留，修正并通过四trace交叉验证后才开始新采集。

共同指标：有符号API退出→设备kernel启动时间（保留负数和计数）、同stream前一可见GPU操作结束→kernel启动间隙（10us时间戳容差内的负差单独计数，展示间隙截为0）。报告每trace中位数/95分位/范围与逐层CSV；每格独立进程n=2，不能把2520层当2520次独立实验。各层延迟与GPU间隙可重叠，不能求和解释为可回收wall time。

off没有pool边界，因此不计算off的“pool结束后启动”比例。若off trace仍有同量级API→GPU延迟，只能说明密集原生标记不是采集现象出现的必要条件，CUDA profiler影响尚未排除；若显著变化，也只支持工具组合/顺序/环境影响，不能直接推断原版没有问题。n=2仅描述，不设显著性或优化收益结论。保留全部警告与不利波动。

后台完成后封存静态证据，排除background动态状态/日志、README、summary及manifest自身；由用户下次调用时回读报告。当前尚无新对照结果，根因继续未完成。
