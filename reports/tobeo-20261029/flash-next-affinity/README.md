# Flash-Next IQ3_S：现有CPU亲和性策略验证

2026-10-29。按[选题复评](../../tobeo-20261028/topic-reassessment/README.md)的P1顺序执行。功能门槛、五轮正式矩阵及收尾复核已完成。未复现达到预先标准的稳定错选；保持日常P核设置，暂不改校准器。P核累计CPU时间较低，但完整请求耗时差异小于观察到的波动。这里只验证受控配置，本轮未对外发布。

## 完成状态

performance-04于北京时间17:21:55开始、17:51:56完成，`passed=true`、无错误及恢复错误。用户要求后台后曾在21/45条交接；现已完成15次启动、45条正式请求及31次环境检查。控制器PID31044已退出。收尾复核确认控制器/助手/协议/workload及引用gate的SHA匹配，17份文件指纹在汇总中无名称覆盖，三臂实际缓存一致，45条完整输出/草稿数量/协议门槛均通过。

原始状态为本机`performance-04/results.json`，日志为`performance-04.console.log`/`performance-04.stderr.log`。独立HtoD前24.846733、后24.853699GB/s，漂移0.0280%。原日常模型恢复后及本次实时`/health`均为loaded=true，原配置SHA未变。下载已按原命令重启（启动PID26760、v5日志）；18:24快照为262.62/273.80GB（约95.92%），六项verified，主体第一分片仍下载，尚非模型完整验收。

```powershell
Get-Content reports/tobeo-20261029/flash-next-affinity/performance-04.console.log -Tail 8
Get-Content reports/tobeo-20261029/flash-next-affinity/performance-04/results.json -Raw | ConvertFrom-Json | Select-Object phase, passed, finished, error, restore_errors
```

## 固定对象与测量范围

- i7-12700（8P/4E）、RTX5060 Ti16GB、128GBDDR4、Windows、驱动610.88。
- 已安装的官方engine0.1.52，exe SHA-256 `dbd0f9b692e9790cd8a25b383a265fab4ccf424a98e6ebc533c6e00dc58628bc`；BUILD记为`f-027-rel/a42cc3d7df70`、CUDA13.0。没有重新构建引擎，也不把本地源码revision当成该二进制身份。
- 现有Qwen3.8-Flash-Next IQ3_S、native pack、PLE、MTP和24576-pair profile。包含exe在内，两份GGUF、pack/Tokenizer/profile及MTP等共17份文件的SHA-256已记录。performance阶段复用准备阶段的全量哈希，并检查文件尺寸/mtime未变；每次启动再核对exe哈希。
- 64K配置上限、INT8 KV/32K resident、prefill1024。`--expert-cache 2400`是预算参数，实际为3107slots/6092MiB，三臂核对相同；启动显存余量门槛>=512MiB，功能门槛观测约2.2GiB。
- 实际spec4/min-p0、lookup-chain0、suffix-draft0；固定pcie-frac0.55、adaptive off、conversation cache0，prompt CPU share和route-tail skip关闭。不是日常默认配置的速度评测，也不称为MTP0。

只改变all/p-cores/measure。worker数保留策略默认：all11、P7，均加主线程；all的worker映射到逻辑CPU2,4,6,8,10,12,14,16,17,18,19，P为2,4,6,8,10,12,14，15次启动的Windows快照均确认对应worker单核mask。主线程0是启动日志声明；快照采于预热后空闲阶段，未确认主线程运行时持续mask，不将日志声明冒充完整采样验证。线程数是策略效果的一部分，不将比较解释成固定worker数下的纯绑核收益。

## 已通过的功能门槛

前瞻协议见[experiment-plan.md](experiment-plan.md)，公开合成输入/IDs见[workloads.json](workloads.json)。三条长请求实际为代码1025、英文4097、中文1025token，各生成256token；三个模式共九条的完整输出、草稿提出/接受数均与all一致，fresh、length结束、无file-tier读取。

每模式另测六条确定性任务，共18/18通过：两个算术JSON、中文literal/JSON、英文literal和可执行absdiff函数（三组输入）。只剥离协议EOS，不改变答案或预期；这不是完整模型质量评测。门槛期间下载运行，相关时长不作为性能结论。

功能阶段measure读数为all11workers/11.23ms、P7workers/8.31ms，选择P；这是一次启动微基准，不是正式请求收益，也不能替代后续五轮选择记录。

## 正式矩阵与环境

五轮新进程顺序预先固定为APM、PMA、MAP、MPA、AMP；三种workload顺序逐轮轮换，每轮三臂相同。15次启动，每次同一96token预热后跑三条正式请求，共45条。每条完整输出和草稿提出/接受数须匹配门槛；记录prefill/decode/二者合计、原生流首token/客户端耗时、CPU累计时间及0.5s RAM/VRAM/分页观测。没有HTTP测量，也不把CPU累计时间当成关键路径。

performance-04数据阶段停止DeepSeek下载器的Python/curl进程，等待退出并排空5s。保存原启动命令和断点；各臂前后确认下载器未运行、文件尺寸/mtime和分段清单SHA不变。测后按原命令续传并另写v5日志。之前暂停核验的失败另行归档，不用于有效性能比较。

## 正式结果与判断

全部样本见[summary.json](summary.json)，15组配对毫秒见[paired-results.csv](paired-results.csv)。下表为每种模式五次请求的中位耗时；配对比先在同轮求all/P，再取五轮中位数，不能用两个独立中位数相除替代。比值大于1表示P核耗时较少。

| 请求（输入/输出token） | all合计s | P核合计s | measure合计s | 配对all/P中位数（范围） | P核较快 |
| --- | ---: | ---: | ---: | --- | ---: |
| 代码1025/256 | 14.131 | 13.916 | 13.863 | 1.0019（0.9916–1.1431） | 4/5 |
| 英文4097/256 | 23.893 | 23.947 | 23.828 | 0.9996（0.9549–1.0461） | 2/5 |
| 中文1025/256 | 15.914 | 15.888 | 15.792 | 1.0016（0.9637–1.0932） | 3/5 |

| 请求 | all/P/measure的prefill中位s | all/P/measure的decode中位s | decode配对all/P中位数（范围） |
| --- | --- | --- | --- |
| 代码 | 3.012 / 2.948 / 2.965 | 11.049 / 10.873 / 10.920 | 1.0050（0.9899–1.1733） |
| 英文 | 11.582 / 11.746 / 11.645 | 12.351 / 12.243 / 12.183 | 1.0088（0.9988–1.0762） |
| 中文 | 2.958 / 2.941 / 2.933 | 13.024 / 12.877 / 12.844 | 1.0059（0.9530–1.1015） |

合计配对比中位数均在1的约0.2%以内，五对没有全部同方向；手动模式组内合计相对极差约4.9%–12.8%，decode也有明显波动。没有达到“全部同方向且幅度大于观察漂移”的前瞻条件，不删除慢样本、不作显著性推断，不能据此写成稳定提速或校准bug。未持续记录温度/频率，页错误未分类为软/硬错误，因此也未对波动作因果归因。

| 轮次（从0开始） | all微基准ms | P微基准ms | measure实选 |
| --- | ---: | ---: | --- |
| 0 | 9.71 | 10.09 | P核 |
| 1 | 9.70 | 9.01 | P核 |
| 2 | 9.57 | 8.53 | P核 |
| 3 | 9.98 | 8.93 | P核 |
| 4 | 9.27 | 10.27 | all |

第0轮P比all微基准略慢仍选择P，符合既有10%偏好；第4轮超出阈值改选all。最后一轮手动对照中代码/中文all较快、英文P较快，不能称为三类请求一致错选，也不能称为每次选择均最优。micro与完整请求不是同一指标，五次选择也不足以估计通用准确率。

资源方面，进程累计CPU时间中位数为代码all/P=134.44/91.70s、英文166.69/119.27s、中文157.58/107.14s。逐轮P/all的中位数分别为0.6848、0.7114、0.6786（每类5/5较低），即本机本配置累计CPU时间约少29%–32%。它包含worker等线程开销，不能解释为关键路径、能耗或固定工作指令数的改善。0.5s采样未报告错误：请求RSS采样峰值范围77.152–77.157GiB、整卡VRAM采样峰值13.685–14.564GiB、各请求系统可用内存最低值33.097–33.933GiB；采样峰值不是连续峰值，进程页错误8–81319不等同于磁盘换页。

下一步不写引擎补丁、不改默认、不为了找收益重跑同一矩阵。若继续此题，应另立日常默认参数的确认协议，或针对接近10%边界的启动选择研究；这些扩展不由本轮代替。当前可交付的是独立验证报告和反例范围，而不是新优化实现。

## 准备失败与修正（均未计入正式计时）

1. execution-01未指定实际组件根目录，解析不到引擎；尚未释放日常模型。改为进程内指定现有组件根，未改系统配置。
2. execution-02发现native IQ pack要求spec>=2，spec0在加载前退出2；因此不能照搬Qwen3.6的MTP0协议。
3. execution-03显示默认suffix将spec4扩为6，且3600预算重算后达到4289slots、显存余量58MiB。发送请求前停止，降低预算并显式关闭suffix；没有将该启动用于性能比较。
4. execution-04功能门槛全部通过，但暂停状态断言失败，0条正式计时，服务/下载恢复。performance-01再次在该断言处停止，0条计时；诊断复现成功暂停时status仍为running且CPU/I/O不变。performance-02只修正环境核验，引用同一不可变gate及其SHA-256，不重跑门槛或改变输出/性能判定阈值。
5. 含额外线程挂起计数探测的启动命令被自动审查拦截，未执行。正式控制器使用更保守的psutil进程暂停及CPU/I/O核验，不调用该探测。
6. performance-02期间，另一会话于17:09:36–17:09:59恢复后重新暂停下载；本实验核对到Python CPU/I/O增长和原curl退出，停止加载中的后续臂。整批15条计时隔离，不挑选此前轮次作为结果。原控制器、协议和`external-interruption.json`已归档，原下载进程及另一会话新建的两个curl均已恢复，日常模型loaded=true。performance-03保持原条件，增加逐臂计数核验后完整重跑，功能门槛复用不变。
7. performance-03在首臂结束时持续静默比较失败，三条计时全部隔离并自动恢复。该守卫未保存差异字段，不能确认变化来源，未认定为再次外部恢复。performance-04改为停止下载进程并测后续传；原脚本静态检查显示分段fsync后才原子更新清单，可保留已登记数据。新守卫记录文件及进程差异，模型/请求/顺序/性能判定不变。

## 证据和限制

### 已在原讨论发布（2026-10-29）

按用户选择，仅发布[#1912评论](https://github.com/Niko1221/Strata/pull/1912#issuecomment-6494468322)，不另提报告PR、不重开原讨论。作者Thymos2027，正文与[本地评论](comment-1912.md)逐字回读一致，原PR仍closed/unmerged。GitHub连接器对上游写评论返回403，随后使用本机已登录同一账户的GitHub CLI发布成功；无重复评论。

证据链接放在用户fork的独立`evidence/flash-next-affinity-20261029`分支，固定commit `d973440a29e6efc8106ea7d8f4ebe6d6cbc6035c`：[英文摘要、数据和日志](https://github.com/Thymos2027/Strata/blob/d973440a29e6efc8106ea7d8f4ebe6d6cbc6035c/bench/results/2026-10-29-affinity-i7-12700/README.md)。共22文件、615605 bytes，仅该证据目录；未更新fork main或既有Qwen3.6 PR。全部22文件线上回读内容与本地包一致，事后添加的离线校验器通过文件哈希、45条输出身份、15份日志及15组主指标配对核对。未运行新的GPU实验，不将此紧凑证据包称为便携GPU复现工具。

导出脚本：[prepare_comment_evidence.py](prepare_comment_evidence.py)；本机完整发布材料为`performance-04/comment-evidence/`与`comment-request.json`。初次脱敏扫描把https网址误判为Windows盘符，在上传前修正盘符匹配边界后全部通过；不涉及实验阈值或数据改动。

### 较早的发布评估（2026-10-29，后续采用上文评论方案）

检索了上游开放/关闭的亲和性与校准讨论。[原measure提案#1912](https://github.com/Niko1221/Strata/pull/1912)已关闭且未合并，正文已有另一Windows混合核CPU的选择波动与10% P核偏好说明；本轮不能把该行为称为新发现或新功能。[#3522](https://github.com/Niko1221/Strata/pull/3522)针对PCIe/draft-floor确认噪声，本实验不是该PR的验证。已有[5060 Ti/i7-14700 Linux报告#4401](https://github.com/Niko1221/Strata/pull/4401)，但配置/CPU/OS/协议不同，不能直接跨报告算加速。

本轮值得分享的新增信息是Windows/i7-12700/DDR4/0.1.52下，实际固定缓存、15次独立启动/45条输出一致请求的all/P/measure对照：合计配对比中位数接近1、无稳定错选，P累计CPU时间每类5/5较低，启动选择并非五次相同。属于非标准受控社区报告，不能冠以标准协议合格结果、通用提速、低功耗或bug修复。

优先在#1912原讨论补充精简独立证据；若希望长期收录，可另开仅增加`bench/results/<date>-community-.../`的`[Benchmark]`报告PR并引用原讨论。依据[贡献规则](../../../CONTRIBUTING.md)和[社区测量指南](../../../docs/COMMUNITY_BENCHMARKS.md)，结果型PR可以直接提交。当前本机报告尚非完整发布包：需制作英文摘要、脱敏配置/启动与失败日志、保留确切输入/全部配对和来源，并解决脚本对本机历史报告目录的依赖；原实跑脚本与事后便携入口须区分验证范围。不能把本段评估记为已完成打包或已发布。

此前Qwen3.6报告[PR#4577](https://github.com/Niko1221/Strata/pull/4577)评估时实时回读仍open、未合并；Flash-Next是独立问题，不追加到该PR。评估时尚未发布，后续用户只选择原讨论评论，实际发布见上文。

原始完整证据：本机`execution-01..04/`、`performance-01..04/`及对应console/stderr日志；有效正式矩阵仅采用performance-04。运行脚本是[run_experiment.py](run_experiment.py)，续跑正式矩阵是[run_performance.py](run_performance.py)，收尾汇总为[analyze.py](analyze.py)。本机路径、完整资源样本与配置默认不进Git。

本轮只验证当前单机受控配置。没有日常MTP阈值0.5、lookup/suffix默认、自动PCIe/缓存、prompt CPU share、route-tail策略、其他上下文/预算、并发、其他CPU或后端的性能结论。measure的10% P核偏好是已知设计；只有真实请求方向、波动和资源代价一起支持时，才考虑后续最小改动。
