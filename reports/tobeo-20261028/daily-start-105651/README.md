# 日常 IQ3_S 服务启动

2026-10-28 10:56，北京时间。用户拉取上游并重启 Windows 后要求恢复服务。沿用 strata-iq3_s.json 与原启动脚本环境，在后台启动当前工作区服务端（git head 82c08921）和已安装 engine 0.1.46；没有安装新引擎或修改配置。

- 模型 qwen3.8-flash-next-iq3_s，上下文 65536，127.0.0.1:8080，未启用图片或 API key。
- /health 为 ok、loaded=true；实际 API 请求返回 Strata is ready.，6 个输出 token。短请求仅验证可用性，不代表正式性能结果。
- 引擎启动四次 H2D probe 均约 24.9 GB/s；温度遥测约 44°C，传输未再出现之前的 1.7 GB/s。
- 自动缓存 4190 slots；加载后仅剩 445 MiB 显存并有引擎余量告警。本次未调缓存或上下文，不声称已解决显存余量问题。
- 证据：server.stdout.log、server.stderr.log、engine-session.log、smoke-response.json、metrics.json。日常服务保持后台运行。
