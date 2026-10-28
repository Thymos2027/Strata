# PR #4347：基础门禁通过，扩大输出后身份检查未通过

2026-10-28，北京时间。本轮完成当前Windows原生源码基线、已有候选的政策触发验证，以及输出分叉后的数值诊断。**原定五组性能配对在第一组后按预设门槛停止，不发布输出等价的加速结论；尚不能判断模型质量变差或等价。** 日常Flash-Next engine0.1.52和DeepSeek后台下载均已恢复。

实现归属rynwang的[PR #4347](https://github.com/Niko1221/Strata/pull/4347)。本机验证其已有实现，没有改候选源码，没有向上游发送消息或提交重复补丁。范围预先写于[experiment-plan.md](experiment-plan.md)。小型结果见[summary.json](summary.json)，首组原始请求指标见[paired-requests.csv](paired-requests.csv)；CSV中的不同输出时长不是可接受的加速证据。

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

## 环境控制与失败记录

正式测量前暂停DeepSeek下载器的两个Python进程，记录PID与创建时间，并实际确认stopped；等待5秒后独立HtoD=24.847244GB/s、探针退出0。停止测量后恢复两个进程，确认均running。功能和数值诊断时下载继续；不使用这些阶段的时间作性能结果。未修改系统代理、驱动、时钟或日常模型配置。

首次`execution-01`在门禁启动时因Windows反斜杠被POSIX shlex转义，模型未加载；改为正斜杠后以`execution-02`重试，保留失败日志。正式首组身份检查失败后、数值诊断后、packed完整logits对照后，均恢复日常服务，health为ok/loaded=true；最后实际进程仍是组件engine0.1.52。

本机证据：`build-summary.json`、两边`*.build.log`、`execution-01/`（启动准备失败）、`execution-02/`（真实检查和首组请求）、`diagnosis-01/`（生成/教师强制）、`packed-logits-01/`（相同布局完整logits）。大日志、全词表dump、本机路径和原始token默认不进Git；公开summary包含强制token、指标、哈希与范围。

## Not run 与下一步

未完成五组性能配对、正式速度验收；因首组停止，原定测量结束后的带宽控制未执行。没有做16K教师强制logits、质量任务集、长稳、并发、独立Graph、Nsight时间线或HIP/SYCL/Metal验证。没有执行#4335或Flash-Next校准实验。

下一步应先制定允许CPU/GPU布局变化的前瞻数值/任务验收：控制每请求的驻留历史，补16K教师强制与代表性任务，区分布局自身波动和新政策。标准确定并通过后才能重启正式性能配对；不在看到单次更快后放宽门槛。#4347本轮交付为独立验证及适用边界，不算完整优化交付。
