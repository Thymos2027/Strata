# edt-xx建议：DeepSeek Engram直接读取小型对照

2026-10-29，执行前写定。评论入口为issue4605的edt-xx评论6497383185。对方建议`--ple-io direct`，该参数实测被专用DeepSeek0.1.52拒绝（exit2，未加载模型）。同一二进制BUILD commit a42cc3d7df70的源码提供Windows `DS4_EG_DIRECT=1`，对只含Engram的文件取消映射并用无缓冲reader；这是相关方向，不是相同参数/完全相同PLE实现。

目标：判断这个相关开关在已能运行的64GB store案例中是否明显降低提交/工作集、是否改变输出及1K/4K成本。不验证“解决自动101GB store耗尽”，也不重做危险的自动预算加载。读源码发现行缓存最高256MiB、Engram按行读取；不能预先把111GB Engram文件视为已经完整复制进RAM。

固定官方0.1.52、原量化、8K、experts6、vision off、DSpark auto、GPU0、store64GB、reserve1536MiB、profile和CPU线程默认。各臂都开启verbose以确认实际路径；各臂固定Engram行缓存256MiB，关闭持久slots/自动pin/前缀复用，避免恢复历史上下文。只改变DS4_EG_DIRECT=0/1，进程局部env，不改系统设置。

顺序A1/B1/B2/A2，每臂独立新进程。同一短预热后，发送原案例performance-0的1038/4110token实际messages，temperature0、thinking off、checkpoint=false、输出预算64。每种输入每臂各一次（每模式两次），检查完整协议、usage、cache_n=0、实际输出/finish一致；GPU专家数和RAM槽位须匹配。若布局/输出不匹配，停止并报告限制，不计算等价加速比。

沿用原0.5秒进程RAM/private、系统commit/limit/分页、整卡VRAM与I/O采样；报告启动与请求采样峰值及空闲稳态，不把file-backed RSS和commit混为一谈。需要同时看到A1→B1及B2→A2两个方向支持，才描述为本组可重复趋势；两次/模式不足以作普遍收益或显著性结论。磁盘缓存不清理，不声称冷盘对照。

保护仍为94%系统commit或可用RAM不足4GiB；异常立即停止当前臂，最后恢复日常Qwen并核对配置SHA。正常退出先通过API unload，保留日志后停止服务器。不改权重/全局配置、不下载文件、不自动向GitHub回帖。完整新结果出来后再决定是否需要更大矩阵。
