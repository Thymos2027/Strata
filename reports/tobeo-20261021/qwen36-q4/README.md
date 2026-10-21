# Qwen3.6-35B-A3B Q4 本机实验

日期：2026-10-21。设备：i7-12700、RTX 5060 Ti 16GB（16311 MiB）、128GB DDR4-3600、Windows 11 26200。项目源码基线 `9de04cd4`，使用已发布 CUDA 13 引擎组件 0.1.46，没有修改或编译原生代码。

## 文件与启动配置

- 模型：`D:\Models\Qwen\Qwen3.6-35B-A3B-MTP-GGUF\Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`，22,853,663,008 字节。
- ModelScope 下载，SHA-256 与 Strata 固定值一致：`55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1`。下载任务记录为 completed，已完成完整文件校验。
- 从该 GGUF 导出分词器到 `D:\Models\Strata\packs\qwen36-ud-q4_k_xl\tokenizer`，16 项编码/解码往返检查全部通过。
- 基线参数：`--max-context 32768 --prefill auto --mtp 2 --pool-workers 7 --expert-vram 10.0`，单请求、无视觉。`baseline-config.json` 保存完整配置。
- 实际初始化：2048 token prompt chunk；每层 68/256 专家驻留 GPU，约 4.98 GiB；18.75 GiB 专家权重驻留 pinned host memory；7 个池工作线程加主线程，共 8 个 CPU 计算线程。
- `--expert-vram 10.0` 是请求预算，实际可分配缓存受其他缓冲与安全余量限制，不能把它写成实际用了 10 GiB 专家缓存。
- 此独立引擎路径不支持 Flash-Next 的 `--pool-affinity p-cores`，本轮没有测 P/E 核亲和性，也没有把 Flash-Next 的所有参数照搬过来。

## 默认 HTTP 行为的短基准

命令：`python tools/strata_bench.py --config reports/tobeo-20261021/qwen36-q4/baseline-config.json --runs 3 --out reports/tobeo-20261021/qwen36-q4/baseline`。Windows 设置 `PYTHONUTF8=1`；使用基础 Python 配合项目 venv site-packages 启动，避免 venv 重定向启动器带来的测试启动进程识别问题。

这是已有 quick benchmark，不是新协议标准评测，也不是模型准确率榜单。模型加载不计入速度。每个新提示添加标签以避免复用影响 fresh prompt 测试。原始 README 和 JSON 位于 `baseline/`。

| 指标 | 中位数 | 范围 |
| --- | ---: | --- |
| 短对话解码，9 项 | 42.6 tok/s | 36.6–47.7 |
| 短对话 TTFT | 0.23 s | 0.19–0.26 |
| 4K（实际 4019 token）预填充，3 项 | 1964.9 tok/s | 1847.6–1979.7 |
| 4K TTFT | 2.07 s | 2.04–2.20 |
| 16K（实际 16058 token）预填充，3 项 | 1895.6 tok/s | 1829.6–1897.4 |
| 16K TTFT | 8.51 s | 8.49–8.81 |
| Agent 解码 | 38.3 tok/s | 31.8–44.9 |
| Agent 后续回合 TTFT | 4.79 s | 1.93–7.94 |
| Agent 缓存命中 | 0% | 三轮均为 0 |

### MTP 配置不等于 MTP 实际执行

虽然配置包含 `--mtp 2`，默认 HTTP 测试的日志始终为 `drafts accepted 0 of 0`。代码检查显示：服务按 qwen35moe 模型卡补入 `presence_penalty=1.5`；temperature=0 请求没有覆盖该值。而 Qwen3.6 引擎在非零 presence/frequency penalty 或非 1 repetition penalty 下需要 logits，当前路径不启用投机步骤。因此上表是这个实际 API 配置的性能，不能称为 MTP 吞吐结果。

纯贪婪的 MTP 测量需要 temperature=0、presence_penalty=0、frequency_penalty=0、repetition_penalty=1，且以日志/草稿计数确认实际工作。更改采样方式可能改变输出，不能把默认 API 结果与纯贪婪 MTP 结果当作同一输出条件的优化 A/B。

### Agent 缓存观察

该套件三轮共 18 个请求均没有复用 prompt token；后续回合反复读取累计上下文。这里只记录症状，没有定位原因，不宣称缓存实现有 bug。后续应拆解模板、token 前缀、检查点和具体引擎状态，再评估交错会话/持续追加的行为。

## 资源快照

测试期间单点采样，见 `resource-snapshot.json`：全卡显存 15813/16311 MiB，余量约 498 MiB；GPU 利用率 56%、功耗 86W、51°C。该瞬间不能代表全程平均或峰值。

引擎工作集约 42.3 GiB、私有提交约 35.8 GiB，全机可用物理内存约 67.7 GiB。工作集包含映射页等，不等于只有 18.75 GiB 专家副本；工作集与私有提交不是可相加的两项 RAM 消耗。本轮没有完整 CPU/GPU/磁盘时间线。

## MTP 开关对照方法

复现脚本：`compare_mtp.py`。三组交替顺序，每臂全新引擎、64 token 预热；两个固定代码/中文提示，各最多生成 256 token。保持模型、32K 上下文、专家预算、线程数一致；原始引擎协议使用纯贪婪采样，不经过 HTTP 模型卡默认值。计时只比较 decode，不包括预填充或模型加载。

每次启动记录实际专家布局；用生成 token 哈希检查两臂是否相同。短算术与中文输出只作功能检查，不能替代完整质量评测。数据与日志：`mtp-comparison.json`、`mtp-*.log`、`mtp-console.log`。

### 三组结果

| 提示 | MTP 关闭，tok/s | MTP 2，tok/s | 中位数比值变化 | 三组成对变化 |
| --- | --- | --- | ---: | --- |
| 代码 | 43.35 / 43.38 / 40.34 | 63.86 / 64.84 / 63.22 | +47.3% | +47.3% / +49.5% / +56.7% |
| 中文 | 44.50 / 44.10 / 43.85 | 54.26 / 53.78 / 49.08 | +21.9% | +21.9% / +21.9% / +11.9% |

代码中位数 43.35 → 63.86 tok/s，中文 44.10 → 53.78 tok/s。引擎日志确认 MTP 真实工作，例如第一组代码接受 157/198 个草稿，中文 137/236；其余计数保留原始日志，不将接受率当作正确率。

**全部六个输出对的 token 哈希不同。**所以本次不是输出逐字一致的加速证明，也没有证明质量等价。不要把文档中其他设备/固定 slot 配置的 identity 结论转用于这次实验。本次未固定 slot 表和 CPU/GPU 路由的数值路径；尚未定位输出差异原因，不能断言只是舍入误差。

功能检查：`17+25` 回复 `42`，中文回复“我已正常运行，随时准备为您提供帮助。”。原始解码包含 `<|im_end|>`，算术断言在剥离这个结束标记后通过；没有重新生成或替换原始回答。两项仅为基本功能验证。

## 后续使用与边界

本机准备了 `strata-qwen36-q4.json` 和 `run-qwen36-q4.bat`，监听 `127.0.0.1:8081`。这是单请求、32K、纯文本、纯贪婪的实验配置，sampling 显式设置 temperature=0、presence/frequency penalty=0、repetition penalty=1，以允许当前引擎实际使用 MTP；不是模型卡推荐采样下的质量结论。HTTP 验证脚本 `check_api.py` 和结果 `api-verification.json` 另存。

该配置实际 HTTP 验证：健康检查 loaded=true，生成可见中文内容，192 token 达到本次长度上限，API 报告 64.2 tok/s、草稿接受 106/174。该单次请求只验证配置和协议，不加入三组原始协议 A/B 的统计。

16GB 显卡不要同时启动 Flash-Next 和此模型。实验结束后恢复原来的 `127.0.0.1:8080` Flash-Next IQ3_S 服务，Qwen3.6 实验服务停止；之后切换前应先停止当前模型。

本轮没有测试视觉、并发、长于 16K 的实际输入、长时间稳定性、完整代码正确性或模型准确率。下一步优先研究 API 采样与 MTP 的交互、持续会话的重复预填充，再做固定实际布局的线程/缓存实验。没有提交新的上游 issue 或 PR。
