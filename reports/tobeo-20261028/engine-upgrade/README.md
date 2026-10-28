# 日常引擎 0.1.46 → 0.1.52：升级与预设验收通过

2026-10-28，北京时间。用户授权按评估执行引擎升级。官方包下载、SHA-256、签名与逐文件校验、组件 test-start、切换及预设 API 验收均已通过；日常服务当前实际运行 engine 0.1.52。旧 0.1.46 组件仍保留，配置哈希未变。

官方签名 feed sequence 115，内置信任 key `5d1bc23abbeffd0d`；选中 Windows x86-64 CUDA 13 engine 0.1.52，支持 sm_120，最低驱动 580.65，本机 610.88。包 620,430,878 bytes，解包声明 945,294,304 bytes，SHA-256 `bfa68c6b2e92f9c273caaf937d9ae164918e6de4cca2dc1f1d79d32470f0915a`。

升级前保存了旧 exe 哈希、配置副本和哈希、原启动环境中的 Strata 参数、health 和一条短控制请求；旧控制请求的 MTP 接受 6/6（仅该请求）。原 updater 曾停留 0% 且 partial 为 0 bytes，终止该下载后恢复旧服务。首次编排在服务切换前因缺少 tzdata 退出，已改为 UTC+8 固定时区后重试；这些准备失败保留为真实过程，不包装成成功。

随后从同一 GitHub 正式版固定资产完成 curl 断点续传；文件 SHA-256 与 feed 的 `bfa68c6b...0915a` 一致。官方组件安装器解包后核对签名和每个文件，以现有模型 test-start 并回答一个 token，再切换到 0.1.52。旧版与新版组件目录同时保留。

## 实际验收结果

- 新 exe：0.1.52 Windows x86-64 CUDA 13，SHA-256 `dbd0f9b692e9790cd8a25b383a265fab4ccf424a98e6ebc533c6e00dc58628bc`；服务日志确认实际从该路径启动，配置哈希与升级前一致。
- `/health` 为 ok、loaded=true；启动 HtoD 四次约 24.9 GB/s，日志报告 engine 0.1.52，验收结束时遥测为 Gen5 ×8。
- 短回答、Python 代码、中文解释均返回预期形态；工具请求返回声明的 `get_weather` 调用。
- A→B→A 中返回 A 的标记 `ORBIT-472`，API 报告复用 18/51 prompt token；conversation cache 为 5632 MiB，本轮记录一次 restore。该短序列验证状态隔离和一次真实复用，不代表长会话缓存性能。
- 七个验收请求合计 MTP offered/accepted=78/57；各请求均完成。它只证明这些短请求上 drafting 工作，不是稳定性或质量评测。
- 新布局为 4002 个 expert slots、约 7819 MiB；验收末尾 `vram_free_mib=634`。显存余量仍需长请求观察，不能由短验收判定已无风险。

本机完整运行证据位于 `engine-upgrade-final/result.json` 与安装日志，由日期目录规则排除，不作为公开提交材料。报告只摘录可审阅结论。升级没有更新 Control、源码或模型权重。

## 未覆盖范围

没有运行长上下文、并发、视觉、正式质量集、升级前后同 workload 性能 A/B 或持续压力测试。短请求速率不能用于宣称 0.1.52 比 0.1.46 更快。研究用 v0.2.7 源码基线仍需独立构建；日常组件升级不替代 Qwen3.6 门禁和 profiling。

## 引擎如何进入推理

`strata-iq3_s.json` 保存 `exe: component:strata-engine`。服务端启动时，`serve/server.py::with_component_engine` 通过 `strata_control/engine_component.py::expand/resolve` 在 `D:\Models\Strata\components` 选兼容包、核对文件哈希，并把包自带运行库目录放到加载路径。

Python 服务端随后启动独立的 `strata.exe --serve ...`，通过 stdin/stdout 管道发送引擎协议并读取 token；引擎加载 GGUF、专家 pack 和 MTP 权重，执行 CPU/GPU 计算与缓存管理。服务端负责 HTTP API、请求参数和返回流。组件解析在服务端启动时完成，所以本轮需要重启服务端，不能只换磁盘文件后宣称正在使用新版。

升级更换计算程序及其运行库，不重新训练或替换模型权重，不需要安装系统 CUDA Toolkit。本机源码构建和历史实验 exe 继续独立保存。推理启动路径不自动联网下载引擎；下载由本轮授权的更新/安装步骤负责。
