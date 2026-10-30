# PR3905 split-stage-copy 独立切片验证

2026-10-30，正式加载前写定。接续[Systems观察](../qwen36-systems/bottleneck-notes.md)，不把作者实现另作原创提交。本机主工作区、固定基线和日常配置保留。

## 查重与范围修正

本轮已重新fetch，上游main为870aedd9，Qwen3.6源码/工具相对46c152a1无差异。GitHub插件搜索覆盖open/closed的stream_kick、STRATA_Q36_STREAM_ALL、q36 stream、Qwen3.6 prefill与hybrid copy；发现xyehya的open/unmerged PR3905直接覆盖此方向，评论与review列表为空。3841是closed/unmerged单缓冲方案，3906是专家放置/异步换槽，不与本轮组合。查询是有范围查重，不保证穷尽全部附件和分支。

因此不写新的门槛/分段复制实现。取PR3905的原作者独立提交 `af08278c15e857345dad95805dda7256a559dcfa`：在固定46c152a1独立worktree中原样应用该提交的四个复制实现hunk，只适配此前堆叠系列中不存在的CLI声明/解析/赋值上下文。保留原 `--split-stage-copy` 名称与语义，不引入其他提交的KV、GQA、fused prompt、GDN、side-stream、量化散射或默认kernel变化，也不复制包含这些功能的整段文档。原补丁与适配diff均留存。

## 固定条件

原Qwen3.6 UD-Q4_K_XL及SHA，MSVC19.42/CUDA13.2/sm_120、Ninja Release；固定32K上限、chunk2048、7workers、MTP0、GPU0、packed Q8/MMQ、显式63 expert slots并冻结驻留、贪婪无penalty。这里固定slots用于隔离复制方式，不能用于#4347自动预算政策验收。

A为同一候选二进制不传flag（原整层host复制），B仅加 `--split-stage-copy`（1/8门槛、resident D2D独立stream、其余host分段复制）。不设STREAM_ALL，不扩大到4096或其他布局。1K/16K沿用公开1025/16385-token输入，64输出。各运行新进程，同一1K/64-token预热；强制历史数值检查另行记录，不与自由生成时间混用。

## 顺序与门槛

1. 独立构建候选、17项选定测试；基线不重建，核对原exe/DLL及库哈希。只在本机CUDA执行；HIP/SYCL未构建，不请求上游代码审阅。
2. 两输入在原基线、候选off、候选on分别生成64行完整词表logits，固定相同63-token历史；要求全部有限、输出/全logits逐位一致。辅助文件入口只把文件参数转换为原CLI，不修改模型计算；记录独立入口/库哈希。检查原exe的off/on自由生成各64输出与同长度参考一致，实际63slots/2048chunk、0换槽。
3. 门禁通过后才做五组交替AB/BA无profiler配对，两输入各五对，共20个新进程、各64输出；记录所有prefill/decode/client耗时、输出、布局及CPU时间。正式指标是原生协议prefill、decode与二者合计，不冒充HTTP或标准benchmark。至少4/5对同向且prefill配对比中位数>1.03才视为本机值得继续的信号；3%仅为本次停止/继续规则，不是通用合并门槛。负结果不剔除、不继续凑样本。
4. 若数值/自由生成身份失败立即停止性能矩阵。若五对未达门槛，保留负结果，不做新trace。达到门槛后，只补16K的A/B各一份CUDA/NVTX trace，核对输出、HtoD/D2D字节和stream变化；trace只解释机制，不填入无profiler收益。按实际边界说明复制字节量核对不等于逐字节转储所有staging内存。
5. GPU执行前保存health、进程清单及本轮日常配置SHA，卸载日常模型；同一transfer_probe测前/测后退出0且HtoD>=15GB/s。出现其他任务争用或带宽异常即停止。正常/失败均清理本控制器子进程、恢复原日常Flash-Next并复核loaded/模型/配置SHA。

## 边界

这是已有实现的Windows/5060Ti/真实Q4独立验证。没有新默认、跨后端、动态换槽、并发、长稳或完整质量结论；即使有收益也不提交作者已有补丁。先产出可复核本机结果，再决定是否需要补原线程，当前没有向外发送消息的授权。
