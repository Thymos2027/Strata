# PR #4347：输出身份不成立，匹配专家布局的数值对照通过

2026-10-28，北京时间。已完成当前Windows原生源码基线、已有候选的政策触发、数值归因和小型任务回归。**原自由生成五组配对在第一组后按身份门槛停止；后续另立协议的五组固定历史配对已完成：16K的generation更快，但prefill变慢，二者合计五组均变慢。** 不能据此宣布普遍加速或完整质量等价。日常Flash-Next engine0.1.52和DeepSeek后台下载均已恢复。

实现归属rynwang的[PR #4347](https://github.com/Niko1221/Strata/pull/4347)。本机验证其已有实现，没有改候选源码，10-29已在原PR补充[独立反馈](https://github.com/Niko1221/Strata/pull/4347#issuecomment-6488877876)，并提交[报告PR #4577](https://github.com/Niko1221/Strata/pull/4577)，没有提交重复实现。范围预先写于[experiment-plan.md](experiment-plan.md)。小型结果见[summary.json](summary.json)，首组原始请求指标见[paired-requests.csv](paired-requests.csv)；CSV中的不同输出时长不是可接受的加速证据。

## 源码与配置

- 基线`5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d`，候选`7be0a3a17aeea0a7c0bf7bc63ae56c70e53311d4`；候选父提交就是基线。独立worktree和构建目录，构建后tracked源码无变化。
- MSVC19.42、CUDA13.2、sm_120、Ninja Release；两边同工具链、同固定ggml。RTX5060 Ti16GB、i7-12700、128GBDDR4、Windows、驱动610.88。
- 真实Qwen3.6 UD-Q4_K_XL：22,853,663,008 bytes，本轮重算SHA-256为`55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1`。
- 政策对照：32K配置上限、chunk2048、7workers加调用线程、MTP0、纯贪婪且penalties关闭、FP32 KV，自动专家预算。未混入#4335，不传固定slots或显式expert-vram来绕过政策。
- 性能测量使用同一候选exe，`STRATA_Q36_KEEP_PACKED=1`与未设置对照。每臂新进程，预热后1K/16K合成ledger输入，先64token门禁，再256token测量。计时来自引擎协议，不是HTTP，未挂profiler。

## Passed：实际完成

1. 两边均构建strata-q36、strata_kq，各16项选定host/布局/采样测试通过；不是全量CTest或跨后端验证。
2. 当前main的固定64槽位、8K上限四臂门禁通过。VERIFY436,050次比较、0 mismatch；当前内核VERIFY、默认Graph请求、MTP2均与旧内核参考10/10 prompt逐token一致。hybrid实际关闭Graph，不能记作独立Graph执行覆盖。
3. 自动预算的main、候选保留、候选释放三臂，在1K/16K各64token的短输出上逐token一致。fresh/count/MTP0检查通过。
4. 候选实际释放1.78GiB packed副本，GPU专家每层**63→89**（4.61→6.52GiB）。这证明政策在本机触发，不证明CPU是唯一瓶颈。
5. 另行固定相同63槽位并关闭再平衡后，主线packed开关在1K/16K各256token生成上完全一致。
6. 同一main二进制、相同63槽位、相同1K prompt和96个强制token历史：packed开关的97行完整logits逐位相同，每行248,320项，共24,087,040个float32值，最大误差0；97/97个top-1一致且全部有限。

## Failed：预设完整输出身份验收

第一组256token A/B的两种输入均不一致，因此停止剩余四组。引擎未崩溃，请求均fresh、MTP0、生成256token并以length结束。

| 实际输入 | 首个不同输出位置（从1起） | 64token门禁与256token实验的区别 |
| --- | ---: | --- |
| 1K（1025 tokens） | 76 | 短检查没有覆盖到该位置 |
| 16K（16385 tokens） | 19 | 此前的1K请求在两个阶段分别生成64/256token，动态专家驻留历史不同；不能简单解释成只在64token之后分叉 |

这不自动说明候选质量下降，也不等于packed数据转换有错误。它说明在本机动态hybrid配置中，不能把“释放副本、增加GPU专家”当作整条生成始终bitwise相同的变化。一次不一致请求也不足以证明新的普遍缺陷。

## 教师强制数值诊断

使用同一个候选exe，自动初始化63/89槽位后固定驻留，不允许换槽；同一1K prompt、相同96个强制token，逐位置比较97行全词表logits。两次退出0，均写出96,348,160 bytes；日志确认0次slot replacements。

| 指标 | 保留63槽位 vs 释放后89槽位 |
| --- | ---: |
| 有限值检查 | 通过 |
| top-1一致 | 96/97 |
| mean KL（keep ‖ drop） | 0.0011710852 |
| max KL | 0.0183991885 |
| 最大logit绝对误差 | 1.8908615 |
| logit RMS误差 | 0.0969343 |
| top-1不同的位置（从1起） | 76 |

该位置与自由生成首个分叉位置一致，但教师强制时冻结了缓存，替代token也不同，**不是动态轨迹的完整复现**。KL不能直接换算成任务质量；没有预设并通过完整质量验收，因此不据此恢复原性能加速结论。

相同63槽位的packed开关给出完全相同的完整logits，而63/89槽位给出上述差异；这支持将下一项归因集中于专家驻留及CPU/GPU执行路径，而非本组中lossless packed读取本身。与[Qwen3.6文档](../../../docs/QWEN36.md)已有的CPU/GPU不同舍入说明相符；本轮没有逐算子确定哪一处差异贡献最大。

## 后续：匹配主线布局的前瞻数值验收

2026-10-28继续执行，规则先写于[validation-next-plan.md](validation-next-plan.md)。小型数据见[validation-next-summary.json](validation-next-summary.json)，原身份门槛失败及其停止决定保持不变。

四臂均冻结驻留：A为候选保留packed、自动63槽位，B为候选默认释放、自动89槽位；C/D为未改源码的主线、关闭packed、分别显式设置63/89槽位。固定同一prompt、96个强制token历史，以及32K上限、chunk2048、7workers、MTP0。主线控制臂用于复现布局，并不用于测试自动预算政策。

| 实际输入 | A=C完整logits | B=D完整logits | A/B top-1一致 | mean KL（A ‖ B） | max KL |
| --- | --- | --- | ---: | ---: | ---: |
| 1025 tokens | 逐位一致 | 逐位一致 | 96/97 | 0.0011710852 | 0.0183991885 |
| 16385 tokens | 逐位一致 | 逐位一致 | 95/97 | 0.0044496711 | 0.2294845658 |

每组97行、每行248,320项，全部有限；相同布局的最大误差为0。A/B与C/D的全部数值指标也相同。在这两条强制历史和冻结驻留配置下，候选差异完全由主线可复现的专家布局变化解释，未发现额外的候选数值偏差；这不定位具体舍入算子，也不证明任意动态缓存轨迹或全模型质量等价。

Windows命令行长度不足以传16K token列表，因此新增[文件参数入口](file_entry.cpp)，只把文件内容转成原有`--tokens`/`--force`参数，并链接原有静态库。两边原exe及所有记录的库SHA-256均保持不变，入口与已归档原main的1K/97行logits逐位一致。数值实验使用该入口，任务实验使用原exe。入口首次链接因缺少CUDA库搜索路径失败，补齐`/LIBPATH`后通过；未修改上游引擎实现。

原始日志和dump在本机`validation-next/`。任务评分曾遗漏终止token：原生GEN先发送token248046，再报告stop；Tokenizer将其解码为`<|im_end|>`。评分修正仅移除这个末尾协议标记，原始输出、原评分和重评分分别保留于`results.json`与`results-rescored.json`，没有修改模型答案或放宽任务标准。

四臂各12/12任务通过，共48/48：四个JSON算术、两个中文格式、四个纯Python函数（分别执行三个输入）、两个短/长检索。所有请求fresh/reused=0；每臂原exe新进程且固定相应布局。这是公开确定性小样本回归，不是标准质量基准或普遍质量等价证明。本阶段下载未暂停，所有时长不用于性能结论；结束后日常Flash-Next服务恢复，health为ok/loaded=true。

复现入口：先运行`build_file_entry.py`，再运行`validate_next.py`，归档完成后运行`rescore_tasks.py`和`summarize_validation.py`。脚本依赖本目录已构建的固定两版本及此前归档输入/原始对照；已有`run-01`会拒绝覆盖，重复实验应使用新目录并保留旧证据。重评分仅重读已生成答案，不再请求模型。

## 固定历史五组配对：generation收益没有抵消prefill代价

运行前写定[fixed-history-plan.md](fixed-history-plan.md)，没有重启旧256token自由生成协议。使用同一个候选文件入口，A保留packed、B默认释放；自动预算分别为63/89槽位，初始化后冻结驻留。每个输入/臂/重复均新进程，沿用上述两条prompt和96token强制历史，只有内建预热，不写logits文件。五组交替AB/BA，共20次运行；全部退出0、97个argmax与该臂先前数值验收记录一致、0次换槽，B均实际触发释放。没有要求A/B彼此输出相同。

原生CLI报告97个generated，实际为prefill后的首个argmax加96次单token推进。下表保留其generation计时口径，包括最终打印97个ID的成本；合计为prefill+generation，不含加载、预热和HTTP，不能当作标准decode吞吐或自由生成用户速度。

| 输入 | 阶段 | A耗时中位数 ms | B耗时中位数 ms | 配对A/B比中位数（范围） | B更快的配对 |
| --- | --- | ---: | ---: | --- | ---: |
| 1025 tokens | prefill | 808.5 | 839.5 | 0.9626（0.9594–0.9767） | 0/5 |
| 1025 tokens | generation | 2519.9 | 2518.2 | 1.0050（0.9990–1.0458） | 3/5 |
| 1025 tokens | 合计 | 3328.4 | 3360.5 | 0.9949（0.9892–1.0252） | 2/5 |
| 16385 tokens | prefill | 7161.8 | 7478.3 | 0.9591（0.9556–0.9602） | 0/5 |
| 16385 tokens | generation | 3322.9 | 3187.1 | 1.0395（1.0270–1.0642） | 5/5 |
| 16385 tokens | 合计 | 10484.7 | 10644.3 | 0.9834（0.9795–0.9906） | 0/5 |

比值大于1表示B快。配对比中位数按每对比值计算，不是两列耗时中位数相除。全部10对原始毫秒见[fixed-history-pairs.csv](fixed-history-pairs.csv)，20次门禁、哈希和完整汇总见[fixed-history-summary.json](fixed-history-summary.json)。未剔除早期较慢的1K generation样本，未做显著性推断。

结论限于本组配置：释放1.78GiB、增加GPU专家确实伴随16K generation的同向改善，但两种长度的prefill均同向变慢；本组96token历史不足以使16K合计受益，1K合计方向混合。这是布局政策的取舍证据，不支持以此推荐全面更快的默认行为，也不能外推长输出必然获益。具体prefill代价来自哪里仍需独立定位。

正式计时期间两个DeepSeek下载进程均暂停。HtoD测前24.860822、测后24.835640GB/s，漂移0.1013%，均退出0并通过预设环境门槛。finally确认下载恢复，日常服务health为ok/loaded=true，配置前后SHA-256一致。没有采集本轮逐请求温度/频率时间线或CPU等待分解。

复现为`benchmark_fixed_history.py`后运行`analyze_fixed_history.py`；依赖上轮已验收二进制、输入及argmax记录。原始证据在本机`fixed-history-01/`，已有目录拒绝覆盖。前瞻协议、执行脚本和验证摘要哈希在新汇总中固定。

## 环境控制与失败记录

正式测量前暂停DeepSeek下载器的两个Python进程，记录PID与创建时间，并实际确认stopped；等待5秒后独立HtoD=24.847244GB/s、探针退出0。停止测量后恢复两个进程，确认均running。功能和数值诊断时下载继续；不使用这些阶段的时间作性能结果。未修改系统代理、驱动、时钟或日常模型配置。

首次`execution-01`在门禁启动时因Windows反斜杠被POSIX shlex转义，模型未加载；改为正斜杠后以`execution-02`重试，保留失败日志。正式首组身份检查失败后、数值诊断后、packed完整logits对照后，均恢复日常服务，health为ok/loaded=true；最后实际进程仍是组件engine0.1.52。

本机证据：`build-summary.json`、两边`*.build.log`、`execution-01/`（启动准备失败）、`execution-02/`（真实检查和首组请求）、`diagnosis-01/`（生成/教师强制）、`packed-logits-01/`（相同布局完整logits）。大日志、全词表dump、本机路径和原始token默认不进Git；公开summary包含强制token、指标、哈希与范围。

## Not run 与下一步

原自由生成五组配对仍未完成，旧协议结束后的带宽控制也未执行；没有将新的固定历史结果填回旧协议。后续已完成16K教师强制logits、小型任务集、固定历史五组配对及其前后带宽控制。仍没有完整质量评估、动态换槽性能、长稳、并发、独立Graph、Nsight时间线或HIP/SYCL/Metal验证。没有执行Flash-Next校准实验。

后续已按既定顺序独立完成[prompt chunk与#4335验证](../qwen36-pr4335/README.md)，于10月29日凌晨收尾：固定packed策略，2048/4096的数值/任务门槛和五组配对通过，4096的16K合计更快而1K合计更慢；没有叠加两项改动。本报告不把#4347的局部generation收益推广为默认推荐，也不为追求正结果继续扩张矩阵。#4347已形成独立验证及取舍报告，完整质量、跨后端和上游沟通仍未完成。
