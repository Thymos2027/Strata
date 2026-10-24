# 日常 Strata 服务重启验证

日期：2026-10-24，北京时间，启动日志时间 10:26:40。用户确认无请求并授权重启。停止原服务与引擎后，以原有 run-iq3_s.bat 对应的 Python 命令、环境变量和 strata-iq3_s.json 在后台启动，未改配置、驱动或系统设置。

## 结果

- `/health`：status=ok、loaded=true，模型 qwen3.8-flash-next-iq3_s，上下文上限 65536，监听 127.0.0.1:8080。
- 重启前 `/metrics` 温度、功耗等为空；重启后 gpu_temp=40°C、gpu_power=11.103 W、gpu_util=1，遥测恢复。
- engine 仍为 0.1.46；启动 HtoD 探针四次均约 1.7 GB/s，pcie_frac=0.05。未恢复历史约 25 GB/s。
- 自动专家缓存此次为 4105 slots，前次 4190；配置相同但实际自动分配不同。加载后日志报告显存余量 611 MiB。
- 服务后台运行，launcher PID 24400、Python server PID 19236、engine PID 30548；PID 仅代表本次启动。

重启恢复遥测，但未恢复传输吞吐。两项异常不能作为同一问题处理，尚不能确定是否有共同触发事件。未新增聊天请求，未测重启后 decode 速度，不声称性能恢复。

## 本机证据

同目录 metrics-before.json、metrics-after.json、health-after.json、engine-startup.log、server.stdout.log、server.stderr.log。完整引擎日志继续追加在仓库根目录 strata-iq3_s.log。运行时文件只作本机证据，不作为公开提交材料。
