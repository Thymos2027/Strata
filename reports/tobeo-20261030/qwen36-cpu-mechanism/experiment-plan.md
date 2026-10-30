# 正常传输下CPU归因与PR3905机制补充

2026-10-30，采集前写定。用户要求继续CPU归因与复制机制证据，保持46c152a1和原配置；提升当前会话权限后，实际IsUserAnAdmin=True、Nsight Sampling Environment=OK。本轮不构建或修改引擎、不更新源码，不改默认，也不自动向上游发布新材料。

沿用原Q4及SHA、CUDA13.2/sm120二进制。32K上限、chunk2048、显式63slots后冻结驻留、7workers、MTP0、packed/MMQ、贪婪无penalty；每个新进程同一r1-l1024/64输出预热。正式输入r0-l1024/r0-l16384，均64输出。baseline使用46c152a1原exe；on仅使用此前已经数值验收的af08278c复制切片exe及--split-stage-copy。on不代表完整PR3905。记录exe/DLL/PDB与源码/工具身份。

1. 先做CPU-only的Nsight预检：500Hz、process-tree IP、process-tree context switches、backtrace=none、resolve-symbols=false，检查探针自己的周期样本和调度事件真实存在。管理员标志不能代替实际样本验收。预检前不卸载日常模型。
2. 三格为baseline/1K、baseline/16K、on/16K。每格各一条同日无profiler请求及一份CPU/CUDA/NVTX trace；两者输出均须与原64token参考完全相同。保持相同标记与模块基址采集，核对fresh、MTP0、slots63、chunk2048、0换槽与退出0。所有计时留存，profiler/plain比只用于观察采集扰动，不作为新的性能配对或替换已发布五组数据。
3. 只在原decode客户端NVTX窗口内，按目标引擎PID筛选周期leaf IP和调度事件。用实际模块加载地址及匹配本地PDB离线解析，区别CPU专家算术、pool自旋、主线程组织/等待和CUDA模块；未解析样本另列。按线程计算on-CPU与GPU空隙的交集；累计CPU时间、on-CPU重叠和leaf比例都不是关键路径耗时，不能简单相加或直接称为可回收时间。保留完整CPU关键路径与等待因果的未证实部分。
4. 使用此前off/on的原始16K SQLite补复制机制，不改变原始报告：核对目标PID/范围、stream优先级元数据、逐次大宗copy、event record/wait关联及双缓冲依赖；验证HtoD+DtoD专家字节逐stage守恒。CUDA event设备完成时间若为0则明确未采得，不捏造设备时间或staging逐字节内容。不加第三个复制臂，不能独立分离分段策略、独立stream与优先级各自的收益。
5. 无其他下载/编译/采集冲突才卸载原日常模型。同一transfer_probe前后HtoD>=15GB/s，正常或失败均恢复同一Flash-Next服务并核对health、模型和配置SHA。任一输出/布局/样本完整性门槛失败，停止后续格；原始失败留存。新目录拒绝覆盖。

仅本机受控观察，不是全量质量、HIP/SYCL、动态换槽、完整调用栈、标准benchmark或新默认验收。Nsight Windows CLI的管理员要求见[NVIDIA User Guide](https://docs.nvidia.com/nsight-systems/UserGuide/index.html)；本轮复核的是已有安装工具，不下载安装或修改系统权限设置。
