# 16GB显卡、128GB RAM上的DeepSeek V4.1 Flash 2.25bpw

2026-10-29，北京时间。既定Windows单卡使用案例已完成：七文件完整性复验、专用引擎核验、加载与功能检查、1K/4K各三次性能请求、30分44秒连续请求，以及日常Qwen恢复和离线证据审计。

**本机可以使用这个量化，但需要显式限制专家RAM store和预留显存。** 成功配置是64GB RAM store、1536MiB显存保留、8K上下文上限、Full quality（6专家）、文本、单卡。短矩阵decode中位约7.1–7.2 token/s，1K/4K首内容等待中位约9.7/19.3秒。连续请求全部完成，但后段部分请求变慢。自动预算在本机初始4GB、上限8GB分页文件配置下中失败，不能写成“默认安装后即可稳定运行”。

这是一份本机使用案例，不是Qwen标准benchmark、完整质量评测或跨模型排名。发布状态见本目录PUBLICATION.md；原始运行和公开整理的范围分开记录。

## 机器、模型与运行配置

| 项目 | 实际对象 |
| --- | --- |
| 系统 | Windows 11，10.0.26200；Python 3.12.7 |
| CPU / 内存 | i7-12700，12物理核/20逻辑核，128GB DDR4（系统报告137,140,031,488 bytes物理RAM） |
| GPU / 驱动 | RTX5060 Ti，16311MiB，NVIDIA610.88，单卡0 |
| 模型盘 | D盘ZHITAI TiPro9000 4TB NVMe；不是SATA盘或网络盘 |
| Windows提交限制 | 失败事件记录145.730GB；后续约141.435GB。发布前只读查询确认C盘分页文件初始4096MiB、上限8192MiB；恢复后分配快照4096MiB，未修改系统配置 |
| 模型 | DeepSeek-V4.1-Flash-1017，ISTA-DASLab GSQ-RCO IQ2_XS / IST-DAS-2.25bpw，文本 |
| 文件 | 七份共273,803,820,973 bytes，ModelScope固定revision；四主体分片和Engram来自ISTA，DSpark及5.8MB元数据来自Unsloth |
| 引擎 | 官方独立DeepSeek0.1.52，Windows CUDA13.0，sm120；BUILD commit a42cc3d7df70 |
| 源码身份 | 控制器使用的checkout为8857fb6c9a94c947f75e845b7e9abe74b97551c8，不能当作官方exe的build commit |

下载包422,151,870 bytes。包SHA-256、可信签名、逐文件哈希及manifest与signed feed一致；exe SHA-256为`e2f9fce53017dd8c2318e3a5ce969b4bd00b64589bdf32355e8d4d691962e610`。来源和大小/哈希分别见本机[engine.json](engine.json)、[selected-package.json](selected-package.json)、[model-verification.json](model-verification.json)。模型七文件在原下载全部verified后，本轮再次全量计算SHA-256，7/7通过。

使用setup.py原样ISTA pack recipe，四主体分片、Engram、Unsloth元数据和DSpark按明确参数组合，没有skip-tensors或dense override；复制`profile-2.25.bin`。pack-info退出0，六份引用GGUF存在且长度足够，tensor device type齐全。实际准备命令和文件指纹见本机[pack-command.json](pack-command.json)、[pack-files.json](pack-files.json)、[pack-info-result.json](pack-info-result.json)。pack是运行索引，没有再复制274GB权重。

成功运行的核心引擎参数是：

```text
--serve --pack D:\Models\Strata\deepseek-v4.1-flash-IST-DAS-2.25bpw\maya-ds4
--max-context 8192 --eos 1 --vision off
--dspark auto --dspark-conf 0.65 --experts 6 --gpus 0
--ssd-cache 64 --reserve-mib 1536
```

`--ssd-cache 64`是64十进制GB的RAM专家store预算，不是64GB磁盘缓存文件。实际日志为5624个RAM槽位、约51.5GB热点专家预读；555/15360专家在GPU，GPU专家约5.77GB，dense约5.86GB，两次加载的初始显存余量分别1185/1075MiB；CPU lane为12线程，长prompt使用4096-token chunk。DSpark在auto下明确未加载。不能拿本轮数据说明开启DSpark的收益。

## 两次准备失败与独立重跑

| 批次 | 结果 | 如何处理 |
| --- | --- | --- |
| execution-01，自动RAM预算 | store自动101.3GB，GPU日志余182MiB。Windows事件2004记录系统提交145,636,839,424 / 145,729,966,080 bytes、DeepSeek提交118,554,161,152 bytes；宿主出现分页文件不足和内存分配失败。服务曾报告ready，但未发功能请求 | 为释放提交内存显式终止测试树，手动恢复Qwen并核对原配置SHA；保留原控制器、事件XML和日志，不计加载验收通过 |
| execution-02，80GB store / 1536MiB reserve | 九次功能请求通过，首组1K/4K各256输出完成；后续请求中系统提交132.953/141.435GB，触发预先设置的94%保护 | 主动终止引擎并恢复Qwen；不是这一批已经发生OOM。后续采样因进程退出报NoSuchProcess，结合memory-guard记录解释，保留全部局部数据 |
| execution-03，64GB store / 1536MiB reserve | 独立重新加载、功能、六条性能和至少1800秒连续请求，完整通过 | 仅采用这一批作为成功案例；没有把前两批局部样本拼进性能矩阵 |

保护条件始终为系统提交超过94%或可用RAM不足4GiB，后续未放宽。恢复配置在每轮之前写入[协议](experiment-plan.md)。原始失败位于本机`execution-01/`、`execution-02/`，各自的旧控制器/协议保留；没有修改系统分页文件、驱动或引擎源码。

## 加载、功能与性能

成功批次两次新进程加载分别18.203秒和17.844秒。没有清理OS文件缓存，且此前已读过模型，因此不能称冷盘加载时间。

九次HTTP功能请求检查了：Paris常识回答、英文literal、中文literal、算术JSON、生成absdiff函数并执行四组输入、多轮标记、真实OpenAI Chat Completions工具调用及回填。全部预设判定通过。例如生成代码四组测试通过；工具返回`add({"a":17,"b":25})`，回填42后回复42；多轮正确找回`ORBIT-472`。这只支持这些小任务，不代表普遍代码/Agent质量。

性能使用公开合成记录，完整输入和本地tokenizer IDs在`execution-03/workloads.json`；实际发送messages以各`*.response.json`为准。temperature0、关闭thinking、请求checkpoint=false，三轮长度顺序为1K/4K、4K/1K、1K/4K。下面每格三次，均256输出、finish=length、cache_n=0。

| 实际输入token | 首内容事件秒：中位（范围） | 完整HTTP秒：中位（范围） | prompt tok/s：中位（范围） | decode tok/s：中位（范围） |
| --- | --- | --- | --- | --- |
| 1038 | 9.697（9.569–11.602） | 46.677（44.887–47.558） | 107.3（89.5–108.5） | 7.1（6.9–7.3） |
| 4110 | 19.332（19.286–19.649） | 54.850（54.776–55.108） | 212.9（209.3–213.3） | 7.2（7.2–7.3） |

首内容事件是HTTP客户端第一次收到可见content的延迟，不是GPU内部第一token计时。吞吐来自该请求引擎时钟的API timings，完整耗时来自客户端。8K是配置上限，本轮实际长输入约4.1K，没有验证8K输入、并发或视觉。

## 30分钟连续请求与速度变化

19:38:57开始，20:09:42完成最后一条，共1844.141秒（30分44秒）、36条请求；四组各九条，全部256输出、finish=length、cache_n=0，无协议/请求错误，无保护停止。

| 指令组 / 实际输入token | 完整HTTP秒中位（范围） | decode tok/s中位（范围） | 末三条/首三条完整耗时中位比 | 末三条/首三条decode速度中位比 |
| --- | --- | --- | --- | --- |
| 中文指令 / 1048 | 46.366（43.198–49.952） | 7.1（6.6–7.6） | 0.979 | 1.029 |
| 中文指令 / 4120 | 52.865（51.398–56.265） | 7.5（7.2–7.9） | 1.063 | 0.960 |
| 英文指令 / 1033 | 48.511（43.586–60.216） | 6.6（5.2–7.6） | 1.156 | 0.849 |
| 英文指令 / 4105 | 54.825（53.504–60.130） | 7.2（6.4–7.4） | 1.080 | 0.932 |

后段英文1K的三条中位完整耗时增加约15.6%，decode速度降低约15.1%。因此结论是“本轮连续请求没有中断”，不能写成“30分钟速度完全稳定”。每条有不同编号和自由生成输出，未记录温度/频率或隔离后台负载；这些小组趋势不足以归因于热降频、SSD温度、缓存或泄漏，也不作显著性推断。中文/英文指令标签不是对长输出语言质量的评分。

![性能点和连续运行资源曲线](case-results.png)

可导出[SVG图](case-results.svg)。点保留实际样本；内存曲线为连续请求期间的0.5秒采样。

## RAM、提交内存与SSD读取

成功批次功能/性能/连续请求的0.5秒采样峰值为：引擎RSS63.990GiB、private82.561GiB、整卡VRAM15.143GiB，系统提交110.389GiB（118.529GB）；系统可用物理RAM最低42.602GiB。提交上限约131.721GiB（141.435GB），本轮没有再次触及94%保护。采样没有报告错误，采样峰值不代表连续真实峰值；RSS/private/显存不是可简单相加的独立物理内存池。

系统全部磁盘的读字节计数，在三次1K请求中位增加约73.10GB（69.99–92.07GB），4K约81.56GB（80.56–82.43GB）。连续阶段系统总读量约2.766TB，进程I/O读取计数约2.764TB。系统计数包括其他进程/磁盘，进程I/O也不是SSD物理读的精确归属；两者说明本轮有大量存储读取，不能当纯RAM推理。页错误和Memory Pages Input/Page Reads计数包含映射文件等行为，不能直接解释成分页文件换页量。

本机NVMe能够支持本轮约7 token/s的交互，但长输入首内容需约19秒、256token回答约55秒。这可作为接受该等待成本的本地文本/小型工具调用使用案例；尚不足以替代真实项目Agent任务、长时稳定性或不同磁盘机器的验收。

## 收尾、证据与复现

控制器20:10:30收尾，`passed=true`、`restore_errors=[]`；Qwen原服务health loaded=true。20:12再次读取8080健康状态确认已加载，原`strata-iq3_s.json` SHA-256仍为`e00594522318be8b5f528ae614bbbc11117db9634f4e751ef942f5efa1002efc`。测试控制器和DeepSeek进程已退出，模型目录未迁移。

原始成功结果是本机`execution-03/results.json`，各`*.response.json`保留实际请求、完整输出和原始流式事件，各`*.resources.json`保留资源样本。精简统计见[summary.json](summary.json)及[requests.csv](requests.csv)。控制器、协议SHA、六条矩阵、连续时长、资源采样和恢复检查均通过。事后离线审计核对52次HTTP请求（9功能、1预热、6性能、36连续）及189份证据指纹，见本机[evidence-verification.json](evidence-verification.json)。

归档限制：汇总JSON的`gate-multiturn-a`、`gate-tools`两条messages引用了之后追加的可变列表，因此显示3/4条消息；独立response文件保存的实际请求均只有一条消息。审计显式记录两处差异并核对汇总前缀、原始request/result及后续对话，未改写原始记录。复现输入以独立response的`request.messages`为准，不能直接使用这两条汇总messages。此问题不改变实际发出的请求、输出或性能记录。

执行入口是[run_case.py](run_case.py)，事后统计/审计/绘图分别为[analyze_case.py](analyze_case.py)、[verify_evidence.py](verify_evidence.py)、[plot_case.py](plot_case.py)。完整环境和私有路径材料保留在本机，未宣称已打成便携复现包。重跑相同案例可在本源码/模型/日常8080服务环境中使用新的输出目录：

```powershell
.venv/Scripts/python.exe -u reports/tobeo-20261029/deepseek41-case/run_case.py --run execution-04 --ssd-cache 64 --reserve-mib 1536
```

该入口会先备份并卸载日常Qwen，运行完整测试后恢复；本轮实际使用的是execution-03。事后分析脚本当前固定读取execution-03，复测须显式调整其输入，不要误读旧结果。没有修改默认配置或引擎源码，没有运行跨后端、8K实际输入、并发、视觉、DSpark强制开启或整夜测试，后续仅发布问题issue #4605及独立证据分支，未提交引擎修复PR；发布范围见[PUBLICATION.md](PUBLICATION.md)。
