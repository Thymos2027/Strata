# DeepSeek V4.1 Flash IST-DAS 2.25bpw Windows单卡使用案例

2026-10-29 目录整理已完成：权重及共享配套迁入 `D:\Models\DeepSeek`，新运行配置为工作区根目录 `strata-deepseek41-ist-das-2.25bpw.json`，pack-info/实际加载与短回答通过。历史报告和冻结控制器保留原路径，后续运行请使用新配置；见[迁移、验收和回退记录](../model-directory-audit/MIGRATION.md)。

2026-10-29 评论建议后验：[edt-xx 参数适配与小对照](edt-xx-check/README.md)。专用引擎不支持 `--ple-io direct`；近似 `DS4_EG_DIRECT` 已进入目标路径，但小对照未见明显系统 commit 回收，且输出身份门槛失败，按协议停止完整 ABBA。未确认自动预算修复；日常 Qwen 已恢复，原案例结果不变。

2026-10-29，按[选题复评](../../tobeo-20261028/topic-reassessment/README.md)完成。**最终报告见[REPORT.md](REPORT.md)**，数据见[summary.json](summary.json)、[requests.csv](requests.csv)，图见[case-results.png](case-results.png)。

已按用户授权发布[Windows提交内存问题 #4605](https://github.com/Niko1221/Strata/issues/4605)，完整脱敏证据在用户fork独立分支，未创建上游PR。发布前从原始XML补核系统commit临界值，并将“4GB分页文件”澄清为初始4GB/上限8GB；见[发布及线上核验](PUBLICATION.md)。

成功配置为原2.25bpw、Windows/RTX5060 Ti16GB/128GB RAM、8K上限、Full quality、文本，显式64GB RAM store及1536MiB显存保留。九次功能请求、1K/4K各三次256输出、30分44秒36条连续请求完成；20:10:30自动恢复Qwen，20:12实时health和原配置SHA复核通过。

1K/4K短矩阵decode中位7.1/7.2tok/s，首内容事件9.697/19.332秒，完整HTTP46.677/54.850秒。自动预算在本机失败，80GB store触及提交保护；64GB配置后段仍有速度变化，不能声称默认即可稳定运行或长期无漂移。52次HTTP原始事件及189份证据离线核验完成；两处功能汇总messages的可变列表引用问题已注明，实际输入以独立response文件为准。以下为运行交接和准备阶段的历史快照，不代表当前仍在运行。

## 运行中交接（2026-10-29 19:40）

- execution-01：自动RAM store101.3GB导致Windows提交压力，事件2004记录DeepSeek提交118.55GB，本机分页文件4GB。服务器曾报告ready但未发功能请求，宿主出现分配失败后显式终止测试树，Qwen手动恢复，配置SHA未变。原始日志、事件及原控制器保留，不计成功加载验收。
- execution-02：`--ssd-cache 80 --reserve-mib 1536`通过九次功能请求及首组1K/4K各256输出；后续请求期间触及94%提交保护线（132.95/141.43GB）而停止，非本轮已确认OOM。Qwen自动恢复、配置SHA未变；局部性能不拼接到新一轮。
- execution-03：`--ssd-cache 64 --reserve-mib 1536`，仍为原2.25bpw、8K、experts6、vision off、GPU0、DSpark auto。DSpark实际未加载；自动profile、12 CPU线程、555 GPU专家、两次加载的初始GPU余量经日志复核为1185/1075MiB。保护线仍为系统提交94%或可用RAM不足4GiB，不改系统分页文件。
- 九次HTTP功能请求覆盖Paris、中英文、JSON、可执行absdiff四组输入、多轮及真正的API工具调用/回填，全部门槛通过。两次新进程加载18.203/17.844秒，未清理OS缓存，非冷盘测量。
- 正式性能6/6完成，各1038/4110输入、256输出、cache_n=0。1K首内容事件中位9.697秒、完整46.677秒、prompt107.3tok/s、decode7.1tok/s；4K对应19.332秒、54.850秒、212.9/7.2tok/s。每格三次，完整范围与原始输出在本机results/response文件；只是自定义使用案例，不代表模型质量排名。
- 连续请求开始于19:38:57，至少运行30分钟并完成最后一条请求后退出；随后自动停止测试服务器并调用日常8080的`/load`恢复原Qwen，核对health及配置SHA。后台包装器PID26304；确切子进程可能变化。此次不持续轮询，用户稍后唤回再核验与整理最终报告。

```powershell
Get-Content reports/tobeo-20261029/deepseek41-case/execution-03.stdout.log -Tail 5
Get-Content reports/tobeo-20261029/deepseek41-case/execution-03.stderr.log -Tail 10
Get-Content reports/tobeo-20261029/deepseek41-case/execution-03/results.json -Raw | ConvertFrom-Json | Select-Object phase, passed, finished, error, restore_errors, health_after
```

最终须同时核对`finished`非空、`passed=true`、`restore_errors=[]`及`health_after.loaded=true`。尚未完成30分钟或恢复时，不能依据phase暂为complete就宣布全部收尾。下一次先确认进程/结果；完成后运行`analyze_case.py`、`verify_evidence.py`，并用本机Anaconda Python运行`plot_case.py`导出图（venv无matplotlib，尚未执行绘图）。离线脚本已准备，完整最终验收未运行。后续章节保留准备阶段的历史记录。

## 已完成的准备

- 原下载任务19:02:42完成，七份273,803,820,973 bytes全部verified。本轮再次逐文件计算SHA-256及核对大小，7/7通过；证据为本机`model-verification.json`与`prepare_model.stdout.log`。
- 只读Terminal plan显式指定deepseek41、IST-DAS-2.25bpw、已有模型目录、8K、full、vision off、GPU0、本机访问/8081。返回tight：全RAM估计146.6GB，本机128GB需自动RAM/SSD分层；`placement.engine_has_dsv41=false`，不能把通用引擎usable当成专用引擎已安装。
- 用当前setup.py原样`dsv41_pack_cmd`生成`D:\Models\Strata\deepseek-v4.1-flash-IST-DAS-2.25bpw\maya-ds4`，复制`profile-2.25.bin`。未使用skip-tensors或dense override，没有复制274GB权重。实际命令及生成文件指纹保存在本机`pack-command.json`、`pack-files.json`。pack尚未通过专用引擎pack-info/加载验收。
- 执行前协议见[experiment-plan.md](experiment-plan.md)。当前源码HEAD为`8857fb6c9a94c947f75e845b7e9abe74b97551c8`，不将它当作待安装官方引擎的build身份。

## 专用引擎下载

19:20验收：下载包于19:19:19写完，422,151,870 bytes；包SHA与signed feed一致，官方安装器的可信签名/逐文件核验通过，manifest SHA与signed feed一致，已安装到`D:\Models\Strata\engine-dsv41\0.1.52-windows-x86_64-cuda-cuda13`。exe SHA-256为`e2f9fce53017dd8c2318e3a5ce969b4bd00b64589bdf32355e8d4d691962e610`，BUILD为0.1.52、a42cc3d7df70、CUDA13.0、sm86/89/120。记录为本机`engine.json`及安装stdout。随后执行专用引擎`--pack-info`退出0：六份引用文件全部存在且长度足够，所有tensor均有device type；原始输出与命令见`pack-info.log`、`pack-info-result.json`。这是离线结构检查，不代表GPU加载、文本输出或性能验收通过。原下载进程均已退出。

signed feed核验后选中0.1.52 Windows x86-64 CUDA13包，含sm86/sm89/sm120/compute120；大小422,151,870 bytes，SHA-256 `f1a3ae88f770b0ef2a3adb9fc7a7166af79069532210bf0f9c7970845cb75865`，build ID `a42cc3d7df70+dsv41+cuda13.0`。选择记录为本机`selected-package.json`。

原安装器下载partial保持0 bytes，停止其PID31012树后改用curl断点、网络重试与低速超时；原stdout/stderr保留。当前包装器PID29404、Python32380、curl10672；脚本`install_engine_fallback.py`下载后核对包大小/SHA，再调用官方`install_package`检查可信签名及逐文件哈希，另对比signed feed公布的manifest SHA；成功写`engine.json`。没有安装驱动或系统工具。

19:10:44至19:11:17短检，包由86,159,360增至91,762,688 bytes（21.74%），下载线程未见Suspended，没有新错误。近期速度约0.1MB/s且有波动，未确认稳定速度或预计完成时间；继续后台下载，不持续轮询。

```powershell
Get-Content reports/tobeo-20261029/deepseek41-case/install_engine_fallback.stderr.log -Tail 5
Get-Content reports/tobeo-20261029/deepseek41-case/install_engine_fallback.stdout.log -Tail 10
Get-Item reports/tobeo-20261029/deepseek41-case/strata-dsv41-0.1.52-windows-x86_64-cuda-cuda13.tar.gz | Select-Object Length, LastWriteTime
```

目录整理按用户接受的顺序：先完成案例，再单独将权重按模型家族分类、核对所有配置/pack路径后迁移。本轮保持原路径。下一步须先确认`engine.json`和pack-info通过，再保存日常服务恢复步骤并释放Qwen进行DeepSeek加载；加载失败按协议停止，不继续测量。
