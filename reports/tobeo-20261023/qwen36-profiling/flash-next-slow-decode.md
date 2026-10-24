# 日常 Flash-Next decode 变慢核查

日期：2026-10-23，北京时间。只读检查现有服务日志、配置和空闲 GPU 状态；没有新增推理请求、重启服务或修改运行参数。

## 本次请求

证据：仓库根目录本机 `strata-iq3_s.log` 第 1144–1163 行附近；配置为 `strata-iq3_s.json`，engine 0.1.46、IQ3_S、64K、INT8 KV、spec 4、P 核亲和性。

- 21:46 的两次请求分别生成 10 / 177 token，decode 为 21.9 / 26.5 tok/s。后一次输入 61 token，prefill 1409 ms，decode 6686 ms。
- 后一次 drafts accepted 87 of 130，说明 MTP 实际执行，接受率约 66.9%。专家缓存命中率 68.8%，另有 0.3% routed experts 经 PCIe 或其他 GPU 读取。
- 当前引擎启动日志的 HtoD 探针为 1.7 GB/s，初始 pcie_frac 0.05；请求期间自动调整到 0.10，CPU pool 为 88 us/missed expert。
- 历史同一日志记录过 24.9–25.0 GB/s，以及 52.9–61.2 tok/s 的若干较长回答；prompt、输出、缓存命中率不同，这些速度不能作为同 workload A/B 或精确下降比例。
- 请求前有仅余 381 MiB 显存的告警，graph capture 时低至 279 MiB。检查时 nvidia-smi 显存占用 15944 MiB。存在 WDDM 换页风险，尚无证据确认本次发生换页。

## 判断与限制

当前低 HtoD 吞吐是最强的已知环境异常，并实际改变了引擎的任务分配，是速度下降的重要嫌疑。20:17 独立探针也只有 1.732420997 GB/s，详见 [环境报告](README.md) 和 [续做安排](no-reboot-next-steps.md)。本轮没有重新测量当前带宽，不能给出它在本次 decode 中的独立贡献比例。

截图只有 238 token 上下文，不支持把明显变慢归因于长上下文。MTP 没有关闭。较低专家缓存命中率和首次捕获 verify graph 也可能影响这些短请求；未隔离测量。

Monitor 的 Gen5×8 显示不能证明实际传输已恢复；此前 NVML/PnP 已有冲突。此次 nvidia-smi 在空闲 P8 下报告 Gen1，同样不能用空闲读数判定负载时物理链路。

保持当前服务。恢复正常速度的下一步应先排查传输异常并用独立探针确认恢复，再做相同请求对照；显存余量调整应另作对照，不能直接承诺提速。

## 2026-10-24：核对引擎升级时间线

只读复核同一日志，未回滚或新增实测：

- 10 月 21 日 10:29：engine 0.1.43，HtoD 25.0–25.1 GB/s。
- 10 月 21 日 11:28：切换组件目录的 engine 0.1.46，HtoD 25.0 GB/s；本次会话有 512-token 回答 60.6 tok/s。
- 10 月 22 日 13:08：仍是同一路径的 0.1.46，HtoD 25.0 GB/s。
- 10 月 22 日 13:26：仍是同一路径的 0.1.46，HtoD 首次在本日志中降至 1.7 GB/s；前后启动命令一致。

因此不支持“升级到 0.1.46 后立即稳定变慢”的解释；同版本曾运行正常，传输异常发生更晚。未保留各历史时点 exe 哈希，路径/版本相同不能充当逐字节未变的证明。仍不能排除引擎使用或 profiling 触发驱动异常等间接关系，也未做当前环境下 0.1.43/0.1.46 的同请求 A/B。此前独立 CUDA copy 在模型卸载后仍慢，说明吞吐异常不限于当前引擎推理路径。

## 2026-10-24：Dashboard 温度缺失核查

只读查询现有服务，没有新增推理负载或重启：

- `/metrics` 连续两次返回 gpu_temp / gpu_power / gpu_util / gpu_pcie_gen 缺失或 null，但仍有显存数据和 gpu_pcie_gen_max=5。
- `nvidia-smi` 能读取温度（该次 53°C）、功耗 65.48 W、利用率 100%、current PCIe generation=1；这是用户请求运行期间的瞬时读数，不是本轮主动性能测试。
- 用服务实际使用的 `D:\Program Files\Anaconda\python.exe` 启动独立进程，执行仓库 `serve.telemetry._Nvml`，读取成功：48°C、60.33 W、util=100、current/max generation=1。温度/功耗/current generation API 返回码均为 0。独立进程加载 `C:\WINDOWS\SYSTEM32\nvml.dll`。
- 现有服务 PID 14456 模块列表同时有 System32 与 DriverStore 路径的 nvml.dll；未核实具体调用映射或版本，不能仅凭两个模块判断冲突。

监控取值与引擎 CUDA 数据传输是不同路径；温度显示为空本身不能解释 HtoD 下降。新进程读取正常、旧服务返回空，更指向旧进程的 NVML 状态、句柄或已加载代码差异，尚未定位。两者可能有共同驱动事件，但目前缺少时间线和因果证据；未证明高温降频，也未验证重启服务后监控或带宽是否恢复。
