# 下一阶段：无CUDA profiler的系统GPU队列观测

2026-10-31，off/on对照收尾后准备。状态：仅文档/只读工具预检，尚未运行ETL采集、安装WPT或更改系统设置。

当前证据：原生job标记off仍有约0.57–0.63ms的CUDA API退出到设备启动中位间隔。全部共同指标来自CUDA profiler，缺少内部提交与系统栈，不能继续用相同观测重复来确认原版根因。

## 已核对的工具与依据

本机 `C:/Windows/System32/wpr.exe` 存在，版本10.0.26100 CoreSystem；实际 `wpr -profiles` 包含GPU，`wpr -status` 返回not recording，管理员为true。标准WPT目录下的wpr.exe与wpa.exe不存在。此前Nsight警告WPT未安装，与“系统已有基础WPR”不矛盾，不将其误写成完全没有WPR。

Microsoft的[内置profile说明](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/built-in-recording-profiles)确认GPU activity记录GPU特定事件；[GPUView说明](https://learn.microsoft.com/en-us/windows-hardware/drivers/display/using-gpuview)介绍从ETL观察图形内核/驱动事件及命令缓冲提交。GPUView随WPT提供。上述是工具能力依据，不证明系统内置GPU profile已包含本任务所需的全部队列事件，也不保证一个GPU包能映射为一个CUDA kernel。

## 执行前要解决的范围

先用短探针确认：WPR GPU profile可启动和正常停止、ETL可读、目标PID/进程生命周期与GPU context/queue可关联、所需提交/执行事件存在、丢失事件和缓冲状态可查。只做探针并评估事件语义，不能把“ETL文件存在”当作根因数据合格。若基础工具不足，先明确缺少的解析或录制能力，再考虑WPT或定制profile，不默认完整工具必须重装。

进入模型采集后，固定870源码/二进制、原Q4及现有布局，关闭原生job标记，完全不启动Nsight/CUPTI采集；保留同日plain参考、统一预热、完整输出/布局和服务恢复门槛。只录请求范围以控制体积，记录PID及可校验的请求边界；边界如何映射到ETL时钟需先验证，不把客户端首token到达时刻等同于engine内部prefill/decode边界。

用系统队列证据区分“CPU尚未提交/队列缺工作”与“已提交而设备未执行”的候选情况，CPU调度/抢占另需真实事件支持。若只能取得GPU利用率而无提交语义，就不足以回答原问题。ETW包级事件不能直接替代CUDA kernel/API关联；没有对应关系时只报告系统层观察，不伪造原版微秒级kernel延迟或最后CPU job边界。

这一阶段使用ETW也存在观察扰动，仍须与plain端到端比较，不称完全无扰动。已有WPR会话必须先检查，不能取消别人的录制；仅停止本任务成功创建的会话。失败即停，finally恢复日常模型/配置；长任务后台运行并保留状态和日志。当前没有确定WDDM、flush、stream或等待策略修复，更未授权自动发布新材料。
