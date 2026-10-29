# Flash-Next IQ3_S：现有CPU布局策略的端到端验证

2026-10-29，在新实验结果产生前写定。不改引擎、校准器或日常配置。问题是0.1.52的启动微基准选择是否与本机受控真实请求一致；不是预设measure有bug或承诺新增提速。

环境处置补充（performance-03启动前）：performance-02计时窗口中，另一会话于17:09:36–17:09:59短暂恢复下载。计数证据确认Python CPU/I/O增长、原curl退出；整批15条计时隔离，不纳入分析，不挑选其中早先轮次。保存原控制器、协议和中断证据；功能门槛不受影响。performance-03保持全部模型、参数、输入、顺序和判定阈值，只增加每臂前后及测后HtoD完成后的下载身份/CPU/I/O计数核对；任一增长即停止并隔离该批。

performance-04前补充：performance-03首臂后三条计时因持续静默判据失败而全部隔离；当时仅存比较布尔值、未保存差异字段，不能确定变化来源，未认定为又一次外部恢复。改为终止原下载Python/curl树，等待退出和5s排空；原下载脚本经静态检查为分段数据fsync之后才原子登记done，未登记段可重新获取。保存原启动命令、文件尺寸/mtime及分段清单SHA。每臂前后及末次HtoD后确认没有同类下载器、下载文件/断点状态未变，失败记录具体进程/文件状态并停止。测后按原命令后台续传，保留原日志并另写v5日志；不改变模型、输入、参数、顺序或性能判定阈值。

## 固定条件

使用已安装并核验的0.1.52 Windows CUDA引擎、现有IQ3_S GGUF/native pack及expert-profile。记录exe、权重、pack元数据、Tokenizer、profile和日常配置SHA-256。保留64K配置上限、INT8 KV/32K resident。固定`--expert-cache 2400`预算参数（不是宣称2400实际slots），固定prefill1024、reserve1024MiB，核对实际GPU slots/字节跨模式一致。每次要求实际vram_free>=512MiB，若slots漂移即停止。准备阶段execution-03发现3600预算被异构slot格式重算后实际为4289 slots、只余58MiB，且默认suffix把spec扩为6；未发送请求即停止。在新有效门槛和计时前，改用2400预算并显式关闭suffix；不把这些准备启动纳入性能矩阵。

准备阶段发现native IQ pack明确要求spec>=2；spec0在加载前退出2，未产生有效门槛或性能数据，原记录保留在execution-02。正式协议在新有效数据前修订：保留MTP路径，固定spec4、spec-min-p0、lookup-chain0及suffix-draft0；逐条要求drafts_offered>0，并核对三臂提出/接受数均与all参考相同，不将本实验称为MTP0。固定pcie-frac0.55，禁用adaptive专家换入、conversation cache，避免自动PCIe策略和缓存联动掩盖CPU布局。`STRATA_PREFILL_CPU_SHARE=0`和`STRATA_ROUTE_TAIL_SKIP=0`在三臂一致，隔离prompt CPU share和近似route-tail策略。这不是日常默认配置的速度评测。采样greedy且penalties关闭。

只改变`--pool-affinity all/p-cores/measure`。不传pool-workers，由各策略自行确定；预计all11、P7加各自主线程，以日志和Windows线程mask为准。worker数变化属于策略作用，不将结果称为固定线程数下的纯绑核收益。measure的10% P核偏好是已知设计，不凭微基准中P略慢直接判bug。

## 门槛与任务

1. 先保持下载运行，卸载日常模型，在每臂新进程中核对version、slots、KV、prefill、spec、worker/host实际布局和measure输出。每次同一96token预热，不用于计时结论。
2. 三条公开合成请求：代码约1K、英文约4K、中文约1K，保存实际文本/IDs/哈希。均要求详细长回答、预算256tokens。三臂所有生成token及草稿提出/接受数须与all参考完全一致，必须fresh、输出256且length结束、MTP实际执行、无file-tier读取。任何身份/协议差异先停止定位，不能带着不同输出宣布速度收益。
3. 另做六条确定性任务：两个算术JSON、中文literal/JSON、英文literal、可执行absdiff函数（三个输入）。各模式六条全过，共18条；代码用既有受限AST/子进程超时判题，剥离末尾协议EOS。小样本不代表完整质量等价。

## 正式性能矩阵

门槛全过后才停止当前DeepSeek下载器，执行上文performance-04的终止/断点核验及恢复方案。此前暂停尝试及其诊断全部保留，不纳入有效计时。前后独立HtoD均退出0且>=15GB/s，漂移<=15%，不满足就标记环境门槛失败。

五轮，每轮all/p-cores/measure各新启动一次，共15次启动、45条正式请求。顺序预先固定：APM、PMA、MAP、MPA、AMP。三条请求顺序逐轮旋转，轮内三模式相同；每次同一96token预热。每条须与对应gate的256token输出及草稿提出/接受数完全一致、fresh/length256/无file-tier，实际slots/预算一致。轮间与轮内全部样本保留，不挑快样本。

逐启动记录measure的all/P微基准ms、选择、实际worker/host及Windows线程mask；逐请求记录引擎prefill/decode及其合计、客户端首token/总时间、输出哈希、CPU累计时间、线程CPU时间及0.5s间隔RAM/VRAM/分页观测。采样峰值不冒充连续峰值；CPU累计时间不冒充关键路径。客户端首token按原生token流定义，不代表HTTP答案首字。

各workload分别报告五个paired all/P耗时比中位数/范围，measure/all、measure/P也报告；主指标prefill+decode，decode分项及资源代价分开。将每轮measure的微基准选择和该轮手动布局对照关联。只有五对同方向且收益幅度大于本组观察到的同模式漂移，才作为后续“稳定错选”候选；本轮不做显著性推断或自动改配置。未达到条件则报告混合/未复现，不制造补丁。

## 收尾与边界

finally关闭本轮引擎、恢复下载进程树及原已加载的日常模型，核对原配置SHA-256和health。不向上游发布本轮结果。日常spec-min-p0.5、lookup/adaptive深度、自动缓存预算、自动PCIe、近似route-tail及prompt CPU share、其他缓存大小/上下文、自由并发和跨硬件均不在本轮覆盖范围；有明确证据后另立协议扩展。未改引擎源码，不重复#3522的PCIe/draft确认逻辑。

准备收尾补充：execution-04三臂9条长请求身份/草稿数量和18条任务均通过；随后暂停状态断言失败，在任何正式计时前退出且服务/下载恢复。performance-01也在进程状态断言处退出，0条计时。performance-02引用不可变gate及哈希，只修正暂停核验，不改变输入、参数或结果判定阈值。线程计数探测版本的启动命令被自动审查拦截，未执行；后续控制器仅使用已有psutil进程暂停/恢复与CPU/I/O核验。
