# 下一阶段范围：1K原始模型ETW/plain对照

2026-11-01范围调整：本设计未执行，按[收尾决定](DECISION.md)移为备选，不在默认执行队列；保留正文供追溯。

2026-11-01，工具packet/QPC门槛通过后准备。状态：尚未执行，不是驱动根因或优化收益验证。

## 只回答什么

同一原始未插桩870aedd9基线在不启动Nsight/CUPTI时，系统GPU队列里能否观察到可归属的实际工作，以及请求范围内队列缺工作/包已提交待调度的形态。不会从包级ETW直接复现某个CUDA API→kernel微秒间隔，也不声称已取得原CPU pool边界。

## 最小执行范围

仅现有r0-l1024实际1025输入/64输出，原Q4、32K/chunk2048/显式63slots后冻结/7workers/MTP0/packed/GPU0/EAGER/贪心。使用build-main-870aedd9-cuda132-sm120原始exe/DLL，复核已通过19测试、两份完整logits及相关源码/二进制/模型指纹，不把旧门槛称新测量。

两对独立进程，顺序plain→ETW、ETW→plain，共四条请求、两份ETL；每进程同一1K/64预热。WPR只在load和warmup后启动，GEN前成功开始，DONE后停止；load/warmup不混入请求统计。原生job标记、CUDA profiler与side/copy新开关都关闭，不改源码或执行策略。

记录engine PID和请求发送、首token、DONE的perf_counter_ns；使用与该次ETL header一致的原始QPC频率换算。ETW start/stop开销单列，不混入native DONE的prefill/decode计时。客户端first-token不是engine内部边界，不能借此挑CUDA kernel。进程在录制前已创建context，必须验证Device/Context DCStart rundown及payload归属；不能沿用短探针“进程在录制中创建”的假设。

## 采集/分析门槛

每条完整输出与870参考相同、fresh/0草稿/实际63slots/2048chunk/0换槽/退出0；每轮HtoD控制和原服务/配置恢复通过。WPR需独立命名instance，不能取消别人的录制，失败finally清理本任务会话。使用GPU.Light/file模式，保留buffer与丢失计数，不安装整套WPT或改注册表/时钟。

先核对目标device/context生命周期、QPC请求范围、render/sync包类型和唯一序号链，报告覆盖率、未匹配、边界截断或分片，不把所有packet强配。若目标关联、原时钟或丢失门槛不合格，停止本阶段，不扩展16K、多臂、长稳或优化矩阵。只能取得部分链时只描述合格部分，并明确无法得出的结论。

ETW也有观察扰动，保留同日plain原始计时与两对顺序；n=2不能作稳定收益结论。CPU scheduling事件与GPU包可按QPC比较，但没有栈/符号或语义时，不能把所有CPU on-CPU解释为专家算术。包级“已提交/可见执行”不直接等于用户态CUDA launch返回/硬件kernel入口，更不能推断缺工作必然是某个flush问题。

只有结果能支持可证伪的系统层假设，才决定下一项最小诊断或改动；否则以观察限制收敛。长任务后台、失败即停、每轮恢复服务。新资料不自动对外发布。
