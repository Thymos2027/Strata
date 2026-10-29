# DeepSeek V4.1 Flash 2.25bpw Windows单卡案例协议

2026-10-29，执行前写定。来源为既定ModelScope固定revision七文件，全部重新计算大小及SHA-256；使用setup.py原样ISTA pack recipe及2.25 hot-expert profile。固定官方DeepSeek 0.1.52 Windows CUDA13包，签名/文件哈希与signed feed核对，sm120。记录当前源码与实际exe的不同身份。

固定RTX5060 Ti16GB、i7-12700、128GB DDR4、NVMe，8K context、vision off、experts 6（Full quality）、DSpark auto、RAM/SSD store自动。不得为跑通换量化或无记录地改参数。先备份日常Qwen配置及health，unload释放资源；finally关闭测试引擎并load恢复日常服务，核对原配置SHA。

先pack-info，再加载与Paris冒烟请求。安装/加载失败即停止矩阵、保留最小复现。正常后检查中文、英文、算术JSON、可执行小函数、多轮；工具调用须先确认模板/API路径再验证，不把原生token生成冒充API工具调用。任务失败保留实际输出；明确格式错误或能力限制，不静默改评分。

性能为HTTP流式Chat Completions自定义案例：约1024/4096实际输入token，各三次，固定256输出预算，记录API实际输入/输出长度及finish、首个内容事件延迟、完整耗时和引擎prefill/decode。输入为公开合成日志，文本及本地tokenizer IDs归档，避免隐私数据；以API usage作为实际chat模板输入token数，轮换长度顺序，明确重复前缀与复用状态。temperature=0，enable_thinking=false，关闭请求checkpoint。仅在功能及加载可用时执行；不是Qwen标准协议，不跨模型排名。

资源每0.5秒采样进程RSS/private、系统可用RAM/commit、整卡VRAM、进程I/O、系统分页和磁盘读取计数；注明采样与计数器范围，页错误不等同于磁盘换页。记录自动store预算、SSD tier、GPU专家及余量。记录首次进程加载和二次进程加载；没有清理OS文件缓存，不称真正冷盘加载。

前三步正常后连续请求至少1800秒；复用同一引擎，交替中英文合成任务与约1K/4K输入，记录每条输出/错误/时长及资源，首尾比较描述漂移，不承诺逐token相同或无统计支持的稳定提升。每条请求有超时及取消；OOM/引擎退出/不可恢复协议错误则停止并恢复日常模型。若功能失败导致停止，报告为边界案例而非全部验收通过。

本轮只写本地案例，不对外发issue、评论或PR。报告区分通过、失败、未运行，不以准备或部分验证勾选完整阶段。

## 首次加载后的独立恢复配置（19:26写定，下一轮之前）

execution-01保留为自动预算失败：Windows事件2004记录DeepSeek提交118,554,161,152 bytes，分页文件4096MiB；RAM store自动101.3GB，显存日志仅余182MiB。服务器曾报告ready，但宿主工具出现分页文件不足/分配失败，未发功能请求；为释放commit显式终止测试树，日常Qwen已恢复且配置SHA相同。原控制器保存于execution-01/controller-original.py，不覆盖失败。

新execution-02是独立的实用配置尝试，显式`--ssd-cache 80`（80十进制GB RAM专家store）及`--reserve-mib 1536`，不改变权重、量化、8K、experts6、DSpark auto。RAM减少约21GB并多留GPU余量，不把它与自动预算的时长比较为提速；是运行配置收敛而非源码/默认修改。先重复加载和功能门槛，再按原六条矩阵与30分钟连续请求流程；仍失败则停止，保留实际证据，不修改系统分页文件。其余判定不变。

## 80GB保护停止后的独立64GB配置（19:32写定，下一轮之前）

execution-02通过九次功能请求，两次新进程加载约20.4/20.1秒，1K/4K首组各256token通过。第三条请求期间，保护器在系统提交132,952,526,848 / 141,434,998,784 bytes（94%阈值）主动终止引擎，停止了余下矩阵；并非已观察到本轮OOM。原始结果不拼接、不撤销停止；控制器及当时协议保存于execution-02。94% commit或可用RAM不足4GiB的保护门槛不放宽。

另立execution-03，以`--ssd-cache 64 --reserve-mib 1536`保留更大commit余量；其余模型/上下文/专家数/DSpark/保护/评分不变。重新从加载、功能门槛开始，完整六条性能请求及至少1800秒连续请求。64GB结果作为独立手动部署案例，不能称默认配置验收；若再触发保护或加载失败则停止并报告边界，不修改系统设置。
