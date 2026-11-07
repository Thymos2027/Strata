# 研究执行记录与原始清单

本文件保留原总计划第 11 节的逐项记录、当时状态和证据入口。历史条目中的“当前”“下一项”只代表写入时的判断；现状见[研究入口](../README.md)。

## 11. 执行与收尾清单

### 2026-11-07 上游合并与三模型验收

- [x] 合并 upstream/main `146df3c46` 至本地 main。合并提交 `c4d90462`，双亲为 `74f9ed31` 与 `146df3c46`；无冲突，CMake 源码版本为 0.1.58。仅完成源码合并，不代表构建或模型运行通过。
- [x] 使用本机 RTX 5060 Ti 构建合并提交的 CUDA 0.1.58 引擎，并分别验证 Qwen3.8-Flash-Next IQ3_S、Qwen3.6-35B-A3B UD-Q4_K_XL、DeepSeek V4.1-Flash IST-DAS 2.25bpw 能加载且完成短请求。2026-11-07 17:21 完成；证据为 `build-native-baseline/merge-c4d90462/status.json`、`build.log`、两个版本日志和三份短请求响应。三个引擎构建目标退出码为 0，版本均为 0.1.58；三个模型分别生成 6、5、8 token，后台流程结束后清理测试进程。范围仅为本机 CUDA 构建、加载与一次短请求，不代表长上下文、并发、性能或跨后端验收。
- [ ] 下载并校验 Unsloth Qwen3.8-Flash-Next Dynamic v3.1 `UD-IQ3_XXS` 四分片。2026-11-07 已核对魔搭文件大小及 SHA-256 与 `setup.py` 固定清单一致；魔搭直连约 0.12 MiB/s，用户因速度过慢要求暂停。后台 PID 35816 已停止，第一分片 10,946,618 字节已校验，第二分片保留 37,748,736 字节 `.part` 供断点续传；其余分片未下载。状态与日志位于 `D:\Models\Qwen\Qwen3.8-Flash-Next-Unsloth-UD-IQ3_XXS-v31`。文件未全量校验，模型未运行。

2026-10-28 新增独立的[DeepSeek 社区使用案例](../tobeo-20261028/deepseek41-community/README.md)，现已完成并发布；不替代上文 Qwen3.6 优化主线。10-21选题池、10-28接续与复评正文均保留为历史，当前执行排序统一看页首当前入口。

每次任务结束前复核本清单：已实际完成的项目打勾，并记录日期、证据与范围；部分完成保留未勾选并说明进度。后续扩展配置或 workload 时，已有勾选不替代新条件下的验证。

- [x] 归档泰山 DeepSeek V4-Flash 有界速度探针及 V4.1 可行性评估。
  - 2026-11-07：核对 [复核报告](../tobeo-20261105/taishan-dsv4/REVIEW.md)、[原始请求结果](../tobeo-20261105/taishan-dsv4/results.jsonl)、[完成状态](../tobeo-20261105/taishan-dsv4/status.json)及 [V4.1 可行性评估](../tobeo-20261105/taishan-dsv4/V41_FEASIBILITY.md)后归档。实测发生于2026-11-05，范围仅为现有V4服务单请求、两种输入长度各三次；V4.1仅只读评估，没有加载或测速。本次没有重跑请求或修改远端服务。

最近执行更新：2026-10-30。本轮沿用10-29 fetch固定的 `46c152a1`，源码引擎0.1.53；已独立完成下一轮基线的构建、门禁和重复性验收，没有在本轮重查全部 PR/Issue 状态。10-28的 `5e8a4cca` 及讨论审查见[恢复后研究评估](../tobeo-20261028/research-next-steps/README.md)。阶段 A、阶段 B 最小矩阵及阶段 C 的原 Systems 时间线是在旧 revision 上完成的历史证据；另有 1K/16K Compute 三指标、1K CPU IP/PDB 解析，以及上游 #3641 固定旧 head 的 CUDA 构建/三个选定测试/真实 Q4 1K 对照。历史HtoD异常已在10-28整机重启后恢复。`5e8a4cca`基线、#4347/#4335各自的数值/小型任务验收和固定历史五组配对均已完成；Flash-Next三臂及DeepSeek案例也已收尾，详见各项证据。10-30另已完成相关复制方向查重、原作者切片的数值/自由生成门禁、五组配对及机制跟踪；正常工况CPU IP/调度及受控job路径后续已完成；无插桩全系统根因、#4347原自由生成五组配对和完整质量验收仍未完成。按北京时间运行开始日期归档。

- [x] 汇总阶段成果、个人收获与GitHub发布取舍。
  - 2026-11-02：补全[成果总结](../RESEARCH_OUTCOMES.md)和[英文草稿](../tobeo-20261101/research-retrospective/PUBLIC_DRAFT.md)的Qwen3.8-Flash-Next亲和性独立小节；不再仅一句负结果。核对15次启动/45请求、三个配对中位数与P累计CPU时间少约29%–32%的范围，并只读回读已发布[#1912评论](https://github.com/Niko1221/Strata/pull/1912#issuecomment-6494468322)，补齐固定22文件证据链接；总体状态单列此项。仅文档更正与已发布记录核对，未新采集、重跑GPU或新增外发，未扩大为省电、通用提速或原创优化。
  - 2026-11-01：[中文成果总结](../RESEARCH_OUTCOMES.md)、[英文研究文章草稿](../tobeo-20261101/research-retrospective/PUBLIC_DRAFT.md)及[交付说明](../tobeo-20261101/research-retrospective/README.md)已完成。只读回读#3905两条既有评论、#4577关闭/未合并与维护者说明、DeepSeek#4605开放状态；区分原作者实现的独立验证、工具/负结果和未确认根因。未启动新实验或新增对外发布，870/WPR若外发仍需单独精简脱敏证据索引；根因与原创加速项目保持未完成。
- [x] 复审整体任务状态、当前诊断分支和停止条件。
  - 2026-10-31：[总体状态](../RESEARCH_STATUS.md)汇总已完成成果、当前瓶颈归因边界及剩余优化闭环；页首现在只有一个当前队列，旧阶段记录完整保存在[状态历史](RESEARCH_STATUS_HISTORY_20261031.md)。确认下一项为有界系统观测探针，未把已有采集/工具存在当作原创改动、性能收益或总任务完成。
- [x] 回读WPR探针的录制状态、丢失计数与系统事件可见性。
  - 2026-11-01：17份原始证据哈希通过；WPR会话StrataQueueProbe11980已停止，导出摘要Total Events Lost=0、录制状态Dropped=0及两个collector Events Lost=0。实有目标PID25856的Device/Context、QueuePacket和DmaPacket字段；发现XML显示偏移+07:59，不能直接与控制+08:00边界比较。证据入口见[复核任务](../tobeo-20261101/qwen36-wpr-review/README.md)。仅确认数据可见/未报告丢失，不等于队列语义、QPC或模型根因完成。
- [x] 收敛当前采集诊断分支并明确后续实验进入条件。
  - 2026-11-01：[收尾决定](../tobeo-20261101/qwen36-wpr-review/DECISION.md)。未启动拟议实模对照，原始证据和备选协议保留；现有验证/诊断成果交付，不声称根因或新优化完成。后续实验须有具体候选/假设、能改变取舍的指标及预算/停止条件，防止以每个未知点继续接一轮采集。
- [x] 完成既有WPR ETL的原始QPC及目标context/提交序号关联复核。
  - 2026-11-01 09:18:21：[复核报告](../tobeo-20261101/qwen36-wpr-review/README.md)、[自动汇总](../tobeo-20261101/qwen36-wpr-review/summary.json)、[97条包账本](../tobeo-20261101/qwen36-wpr-review/packet-ledger.csv)。7份新及17份原证据指纹、原始/默认事件序列、10MHz QPC控制边界、目标2device/14context和97条唯一完整render链通过，0未匹配、丢失0；所有包时间点均在探针边界内。使用原QPC绕开+07:59显示异常，未猜测修复时区。只认可包级工具门槛，自动summary仍保留queue_attribution_ready=false；后续受限实模方案已准备但未跑。无新GPU采集、模型切换、安装、默认改动或外发。
- [ ] 完成1K原始870基线的无CUDA profiler实模ETW/plain受限对照。（未启动，移为备选，不在本轮执行队列。）
  - 2026-11-01：[下一阶段范围](../tobeo-20261101/qwen36-wpr-review/limited-model-plan.md)已准备，只做两对AB/BA、四请求/两ETL，先验证进程已存在时的rundown、请求QPC及包关联；未执行，不计根因或收益完成。
- [x] 完成一次WPR短探针采集与导出，并核对封存文件。
  - 2026-10-31采集完成，2026-11-01只读核对17份证据及manifest指纹通过，见[短探针报告](../tobeo-20261031/qwen36-wpr-queue-probe/README.md)。probe退出0，ETL101711872字节、解码565850条事件、恢复无错误；仅工具采集成功，不表示目标队列语义、时钟关联、丢失事件审查或根因完成。
- [x] 核对最新上游、相关讨论和工作区改动。
  - 2026-11-03 本地归档：核对262K验收与资源ABBA的完成状态和生产/恢复health记录，ABBA顺序及汇总轮次与原始记录一致；93项资源中位数/差值重算、Python语法/JSON格式及202处本地链接检查通过。证据见[262K验收](../tobeo-20261103/flashnext-262k/README.md)、[资源对照](../tobeo-20261103/context-resource-ab/README.md)。本次仅归档报告/脚本及亲和性成果补充，不重跑实验或推送，动态PID、原始响应/配置/采样日志留在本机；不扩大长文质量或性能结论。
  - 2026-11-02 本地归档：将[11-01版本审查](UPSTREAM_V029_REVIEW_20261101.md)及对应清单记录合并为一次文档提交；162处本地链接及空白检查通过。本轮未重新刷新上游或执行构建/模型测试，未升级源码、日常服务或推送远端。
  - 2026-11-01 v0.2.9审查：刷新upstream及标签，回读正式发布说明，并核对v0.2.8→v0.2.9的169个提交/283文件差异和Qwen3.6预热修复，见[版本审查](UPSTREAM_V029_REVIEW_20261101.md)。区分Linux/Strix Halo提速与本机Windows/CUDA适用范围；未合并、安装、构建、复测或恢复诊断队列，不把发布方测量当本机收益。
  - 2026-11-01 本轮本地归档：只读复核原WPR17份及离线审查7份证据SHA、两份清单指纹通过；97条packet链的唯一键、原始QPC顺序及10MHz时间换算通过，Python语法/JSON格式、201处本地链接和暂存空白检查通过。证据入口见[WPR审查](../tobeo-20261101/qwen36-wpr-review/README.md)与[成果总结](../RESEARCH_OUTCOMES.md)。仅归档既有结果与收尾决定，未重跑采集、执行实模备选、推送或新增发布；原版根因与新优化收益保持未完成。
  - 2026-11-01 本地归档复核：870aedd9基线32份、GPU提交诊断126份、标记off/on对照106份、WPR短探针17份，共281份本机证据SHA及四份清单指纹通过；58个新增候选文件的Python语法/JSON格式及215处本地链接检查通过。证据入口见[10-30基线](../tobeo-20261030/qwen36-baseline-870aedd9/README.md)与[10-31报告导航](../tobeo-20261031/README.md)。仅归档和修正WPR文字状态，没有重跑实验、改写封存数据或推送；原版根因及队列语义未计完成。
  - 2026-10-30 晚间本地归档：发布补充与源码更新记录提交为 `8e0dce58`，计划和导航单独提交。只读核对9个上传文件的SHA/Git blob身份、两份评论回执、ZIP68文件与离线账本通过；194处链接按本地或导出目录语义核对通过，Python语法及暂存空白检查通过。本次未重复发布、推送、构建新引擎或重跑GPU实验，新基线验收仍未完成。
  - 2026-10-30 下午本地归档：CPU采样/复制机制与job依赖诊断分别提交为 `b1327a2d`、`03ab5f41`。只读重算两目录共213份证据SHA及清单指纹通过，Python语法、JSON格式、196处本地链接和两份诊断补丁格式检查通过；补丁空白上下文原样保留。phase/token账本分别为10160/126行；本次未重跑实验、改写封存清单或推送远端，未把原版无扰动根因标记完成。
  - 2026-10-30 本地归档：CUDA/NVTX时间线与复制切片验证分别提交为 `a442cbe2`、`a5ed4122`，导航、分支盘点与本计划另行归档。Python语法、JSON格式和发布证据包离线一致性校验通过；仅提交现有报告、脚本与小型数据，未重跑GPU实验、推送远端或执行分支清理。
  - 2026-10-30 Git 清理盘点：完成六条本地分支、远端引用、三个具名贡献/验证工作树及 #3542/#3428/#4577 实时状态核对；两条备份分支的 9/11 个补丁分别全部已有 main 等价提交。证据及清理边界见[分支盘点](../tobeo-20261030/git-branch-audit.md)。本次未删除分支/工作树、未同步 main、未新增运行验证；公开证据分支保留。
  - 2026-10-29 本轮：fetch固定 `46c152a1`，核对相对 `5e8a4cca` 的源码差异和现有工作区改动；只更新版本与执行入口，没有重查在线讨论或改变此前发布结论。总计划中的“近期下一项”和旧“最新”段落已更新/标为历史，原始结果保留。新基线证据见[协议](../tobeo-20261029/qwen36-repro-baseline/experiment-plan.md)。
  - 2026-10-29 文档导航补充：复核两份接续文档的先后关系，将[research-next-steps](../tobeo-20261028/research-next-steps/README.md)正文标识为早先GQA方案，将[topic-reassessment](../tobeo-20261028/topic-reassessment/README.md)明确为近期#4347/#4335的执行依据，并同步已发布结果。本次只修正文档定位与历史状态标识，没有新增上游复评、模型测量或阶段完成声明。
  - 2026-10-28 本轮再次fetch确认`upstream/main=5e8a4cca`，核对open/closed issue/PR、#4335/#4347补丁与后续评论、#3522校准范围、#3773及缓存重叠，并检查自动预算guard与measure的10% P核偏好。完成[模型与选题复评](../tobeo-20261028/topic-reassessment/README.md)：保留两模型，优先Q36 hybrid独立验证，Flash-Next校准升至P1，GQA降为条件性后续。仅审查与设计，未新增GPU结果。
  - 2026-10-28 后续补充 Qwen3.6/Flash-Next 选题关系；完成 [DeepSeek 下载慢排查](../tobeo-20261028/deepseek41-community/DOWNLOAD_DIAGNOSTIC.md)，核对运营商 USB 网卡出口，比较代理/直连、入口、分段、CDN 和备用源，改用四路直连后台续传。仅证实低外网吞吐及当前对照，未确认运营商限速、未完成模型下载或推理测试。
  - 2026-10-28 本轮梳理历史选题池、总计划和恢复后接续方案的关系；完成 DeepSeek 2.25bpw 资源与来源审查，七份 ModelScope 文件大小/哈希均匹配仓库接受版本，后台下载已启动，首份元数据 SHA-256 通过。见[下载与案例安排](../tobeo-20261028/deepseek41-community/README.md)；未将下载准备计作模型或研究验证完成。
  - 2026-10-28 后续完成[日常引擎升级评估](../tobeo-20261028/research-next-steps/README.md#日常引擎升级决策评估2026-10-28)：实时发布为 engine 0.1.52，运行进程仍为 0.1.46，驱动 610.88 与 CUDA 13 要求相符；建议保留旧组件后验证切换，重点检查显存余量、多轮、MTP 与缓存。仅只读核查与决策记录，未升级或新增推理测量。
  - 2026-10-28 本轮：复核 `5e8a4cca` / v0.2.7、Q36 sampling/attention 差异、#3641/#3678/#3295 元数据与 #2464/#3700 后续评论；更新[研究优先级与接续实验](../tobeo-20261028/research-next-steps/README.md)。确认 #3700 已扩展重叠方案，#3641/#3678 API 当前可合并；未把静态审查记作构建、性能或交付完成。
  - 2026-10-28 用户完成 [NVIDIA Nsight Compute #387175](https://forums.developer.nvidia.com/t/rtx-5060-ti-windows-persistent-low-pcie-transfer-throughput-observed-after-kernel-replay-tdr-restored-after-reboot/387175) 发布；已通过公开主题 JSON 核验分类、正文、测量表和限制，并更新 [Strata #4381](https://github.com/Niko1221/Strata/issues/4381) 正文完成互链。核验时论坛尚无回复；报告发布完成不代表根因已被厂商确认或完整优化交付完成。
  - 2026-10-28 同日早先完成针对性 issues/PRs/论坛查重与脱敏，发布 [Strata 排障报告 #4381](https://github.com/Niko1221/Strata/issues/4381)，并准备 NVIDIA Nsight Compute 正文、证据包和预填页面；随后由用户登录发布并完成互链，最终状态以上一项和[发布状态](../tobeo-20261028/upstream-reports/README.md)为准。未把报告发布或本机环境恢复当成完整优化交付。
  - 2026-10-23 同步后复核 `upstream/main` `7ddc17a3`（v0.2.3.1）：Qwen3.6 核心仅见 CUDA 12.0/12.1 编译兼容修复；v0.2.3 改变 conversation cache 自动预算及 Work profile 默认值。GitHub 实时状态确认 #3641/#3678/#3700 均未关闭或合并，前两者仍基于 `011c9e6` 且 API 返回当前不可直接合并；#3542 已更新到当前 base。审查结果已写入本计划和各执行入口，没有向外发送消息或修改上游。
  - 2026-10-23 通过 API 重新搜索 open/closed，阅读 #2464/#3700 后续评论，确认 #3641 已有 FP32 GQA 对照开关，#3678 也有重叠工作；固定 #3641 head f3f2136f 做已有方案验证，不另起重复实现。没有向外发送消息或提交 PR。
  - 2026-10-22 已核对工作区，重新读取 #2464 及后续评论，并查询包含 k_attn_part 的相关 PR（包括 #3084、#2698）；快照保留在阶段 B 目录。实验继续固定阶段 A revision，未声称运行最新 main；后续实现前仍需重新查重。
- [x] 确认源码基线、工具链、模型哈希和独立构建目录。
  - 2026-10-21 至 2026-10-22 完成，见 [WSL 基线](../tobeo-20261021/qwen36-source-baseline/README.md)与 [Windows 原生基线](../tobeo-20261022/windows-native-baseline/README.md)。后续主用 Windows 原生构建。
- [x] 建立同步后 `5e8a4cca` / v0.2.7 的 Windows 原生源码基线。
  - 2026-10-28 本轮完成：MSVC19.42/CUDA13.2/sm_120，独立当前main与#4347原始候选构建，两边各16项选定host/布局/采样测试通过；main四臂固定布局门禁10/10逐token一致，VERIFY436,050次比较、0 mismatch。自动布局下main/候选保留/候选释放的1K/16K、64token门禁也通过；见[执行报告](../tobeo-20261028/qwen36-pr4347/README.md)。仅此配置范围，非全量测试、独立Graph或质量验证。扩大到256token后身份不成立，正式配对在第一组停止，五组未完成。
- [x] 固定下一轮 profiling 的 `46c152a1` Qwen3.6 可复现源码基线。
  - 2026-10-29 22:47验收完成、随后离线复核通过：[报告与复现入口](../tobeo-20261029/qwen36-repro-baseline/README.md)、[小型汇总](../tobeo-20261029/qwen36-repro-baseline/summary.json)。固定源码0.1.53、MSVC19.42/CUDA13.2/sm_120、原Q4模型SHA及3608份ggml文件；独立构建与17项选定测试、Ninja无改动复查通过。四臂各10条逐token一致，VERIFY436,050次/0 mismatch，MTP2实际接受567/786草稿。32K/chunk2048/7workers/MTP0/packed、自动63slots后冻结驻留，两次新进程的1025/16385输入各64输出分别一致、fresh且0换槽；HtoD前24.894215/后24.810577GB/s。44份本地证据离线核对，源码/exe/DLL/日常配置SHA未变，原Flash-Next0.1.52恢复loaded=true、无恢复错误。保留版本采集的两次脚本失败及修正；仅本机Windows/CUDA受控基线，不代表全量测试、独立Graph、动态换槽/质量、逐字节重编译一致或正常工况profiling完成。
- [ ] 在新基线上补正常 HtoD 工况的 Qwen3.6 关键路径时间线。
  - 2026-10-30下午：原配置chunk2048的受控job依赖及wall账本已完成，见下方已完成子项；完整原版无扰动根因、系统全栈和扩展配置尚未完成，因此总项保留未勾选。午间“无job边界”和早间“采样权限不足”仅描述当时状态。
  - 2026-10-30午间部分完成：[CPU/IP与调度补充](../tobeo-20261030/qwen36-cpu-mechanism/README.md)解除采样权限障碍，已区分算术/worker等待/CUDA查询并对齐GPU窗口；引擎image IP均解析。仍无逐层job边界、完整栈和内核态符号，组合采集有10%–16% decode扰动，不把本项或最终关键路径勾选完成。
  - 2026-10-30 部分完成：新正常工况CUDA/NVTX四格与同日无profiler请求均通过，见下方完成子项；CPU sampling环境预检为No admin/Fail，未采集CPU IP或调度，仍不能区分专家算术、事件轮询及pool等待，本项继续保留未勾选。
  - 2026-10-29 历史安排：基线通过后另立采集范围；1K/16K、MTP0起步，chunk2048和显式4096分开，保持packed政策一致并记录布局。与历史异常工况trace、无profiler计时分开，不把本轮基线门禁当作阶段C完成。
  - 2026-10-28 目标更新为当前上游，完成静态差异和实验范围审查；尚未构建或运行新门禁，保留未勾选。旧 v0.2.3.1 目标由本项替代。
  - 2026-10-23 已完成代码差异与发布说明审查，但尚未重新构建或运行门禁。新基线须显式固定 worker、专家布局、conversation cache、MTP/drafting、上下文和采样；历史 `9de04cd4` 数据保留，不与新结果拼接。
- [x] 跑通适用的基线正确性门禁。
  - Windows 原生：14 项选定测试通过；VERIFY 436,050 次比较、0 mismatch；当前内核验证、默认 Graph 请求、MTP 三组各 10/10 prompt 与参考逐 token 一致。固定 64/256 专家布局会自动关闭 Graph，故独立 Graph 路径仍未验证。范围为 8K 上限和短 prompt，未覆盖全量测试套件。
- [x] 完成新基线正常工况的CUDA/NVTX采集、同日输出对照与阶段观察。
  - 2026-10-30：[报告](../tobeo-20261030/qwen36-systems/README.md)、[汇总](../tobeo-20261030/qwen36-systems/summary.json)、[阶段数据](../tobeo-20261030/qwen36-systems/phase-results.csv)、[观察与最小假设](../tobeo-20261030/qwen36-systems/bottleneck-notes.md)。原46c152a1/exe/DLL/Q4模型SHA，32K/MTP0/7workers/packed、chunk2048/4096实际63/50slots后冻结，1K/16K各64输出；4条同日无profiler请求与4份trace同chunk输出一致、全部fresh/0草稿/0换槽、进程退出0。4份SQLite范围/PID及完整性六项检查通过，54份本地证据留存；CPU sampling未运行。HtoD前24.843725/后24.890607GB/s，00:19:18恢复原Flash-Next0.1.52、loaded=true、配置SHA相同且无恢复错误。每格n=1，4096/1K trace decode慢20.6%完整保留；不代表候选A/B、完整关键路径、质量、动态缓存或新优化收益。
- [x] 发布CPU/复制机制/job级路径补充到PR3905原线程。
  - 2026-10-30 18:00:16：[发布记录](../tobeo-20261030/qwen36-pr3905-followup/README.md)、[新增评论](https://github.com/Niko1221/Strata/pull/3905#issuecomment-6518999609)。fork独立证据分支固定b6a98dd9，仅新增9文件/1130419字节，线上blob身份与本地一致；ZIP68文件，离线核对文件哈希、10160 phase/243840任务和126 token账本。完整正文回读、同账号及线程查重通过，无重复评论。原五组计时/评论及94/52/161份旧证据未改；新测量仍是46c，不宣称新上游通过。连接器上游评论403后用现有Git凭据确认同一账号并发布；未改变PR代码、fork main或默认。
- [x] 根因调查前将项目源码更新至指定upstream870aedd9。
  - 2026-10-30：[更新记录](../tobeo-20261030/qwen36-pr3905-followup/README.md)。fetch精确870aedd9e1ebe1c91f94da93b59af17729f6c5c0，本地main保留研究提交并合并为e1691cc8，无冲突；更新前bc6098b9由backup/pre-upstream-870aedd9-20261030保留。独立src-main-870aedd9精确固定且干净，除AGENTS/报告外项目文件与上游一致。原46c基线/worktree/证据及日常配置保留；源码版本0.1.54，不代表新构建或GPU验收完成。
- [x] 在870aedd9建立并验收根因调查使用的新基线。
  - 2026-10-30 20:09:49：[报告](../tobeo-20261030/qwen36-baseline-870aedd9/README.md)、[汇总](../tobeo-20261030/qwen36-baseline-870aedd9/summary.json)。独立CUDA13.2/sm_120构建及19项选定测试/Ninja通过；两长度各64×248320完整logits有限且与旧参考逐位一致，四条独立进程输出和实际63slots/chunk2048/fresh/0草稿/0换槽通过，MTP0/packed保持。用户返回后复核32份静态文件、3608份依赖、适配入口/匹配DLL、源码和当前服务通过。HtoD24.895941→24.895785GB/s，20:09:49原Flash-Next恢复、配置SHA相同、无恢复错误。16K两次计时约4%波动，不宣称延迟稳定或跨版本收益；未验证新迟启动、Graph、MTP2、HIP/SYCL或全量质量。
- [x] 完成870aedd9迟启动的两轮受控复现、观察扰动记录及证据验收。
  - 2026-10-31 00:35:57：[正式报告](../tobeo-20261031/qwen36-gpu-submit-870aedd9/README.md)、[汇总](../tobeo-20261031/qwen36-gpu-submit-870aedd9/summary.json)。独立NVTX/原子完成序号诊断CUDA构建、19测试/Ninja、四份完整logits与870参考逐位一致、16请求/四trace全部输出/布局通过。两轮反序，1K晚启动2514/2520与2520/2520层、16K均2520/2520层；逐层API返回早于pool、GPU启动严格晚于pool结束，无相等边界。20320 phase/487680任务、252 token账本闭合，288个decode phase最后原子发布者不同于最晚body。回读126文件manifest及当前服务/配置通过。trace/on额外10.1%–17.8%，每格n=2，不能当纯profiler成本或无插桩根因；缺内部queued/submitted时间和系统栈。HtoD均约24.88–25.00GB/s，00:28:30和00:35:15恢复原服务，无恢复错误。原基线/旧证据不改，未新外发、改默认或宣称优化收益。
- [x] 完成同一870诊断二进制的job标记off/on采集对照与收尾验收。
  - 2026-10-31 10:50:59：[报告](../tobeo-20261031/qwen36-observer-control-870aedd9/README.md)、[汇总](../tobeo-20261031/qwen36-observer-control-870aedd9/summary.json)。沿用同一exe/DLL与原配置，旧19测试/四份logits只重验指纹、没有新构建或dump；16新请求/八trace/八plain全部输出/实际布局通过。共同选择先匹配旧四trace独立标记10080层，新八trace20160层的API关联和off/on grid/block/shared-memory逐层一致；off JT为0，on有真实事件。off API→启动中位数565.894–631.838us、可见间隙335.151–385.727us，故密集标记不是此类采集延迟的必要条件；不能推断off晚于pool结束或原版驱动根因。n=2，第1轮16K off较慢及plain漂移保留；trace/plain约1.078–1.336，不当纯采集成本或优化收益。106文件manifest及当前服务/配置回读通过，10:42:41/10:50:46两轮恢复，无恢复错误；HtoD均约24.76–24.90GB/s。原证据/默认不改、未外发。
- [ ] 在870aedd9复现GPU已提交后的迟启动，并隔离观察扰动、收窄根因。
  - 2026-11-01范围收尾：现有受控复现/标记消融及WPR工具证据已形成，但原版根因未知。按[取舍决定](../tobeo-20261101/qwen36-wpr-review/DECISION.md)停止自动追加采集，不为勾选本项无期限追踪；留空表示根因未完成，不是默认还要跑的任务队列。
  - 2026-10-31总体复审：主线仍为“证据支持的瓶颈 → 最小改动 → 正确性 → 无profiler配对收益 → 有界贡献”，已将页首累积状态移入历史、建立[总体状态](../RESEARCH_STATUS.md)。下一项仅一次[WPR GPU队列工具短探针](../tobeo-20261031/qwen36-wpr-queue-probe/README.md)，不加载实模、不跑新矩阵；ETL/PID/提交语义和丢失信息合格后才继续，否则报告单一缺口。任务准备不计根因完成。
  - 2026-10-31部分完成：off/on采集对照及106文件验收已完成，密集标记不是采集延迟出现的必要条件；但CUDA profiler与系统提交/调度仍未区分，根因总项继续未勾选。下一项[系统GPU队列探针范围](../tobeo-20261031/qwen36-observer-control-870aedd9/next-system-trace-plan.md)已准备，只读确认WPR GPU profile/管理员/无活动录制，不等于合格ETL或实模数据；尚未新录制或安装WPT。
  - 2026-10-31部分完成：上述新提交受控复现与账本已完成，但观察扰动尚未充分隔离、根因仍未知，本总项保留未勾选。下一项[off/on标记采集对照](../tobeo-20261031/qwen36-gpu-submit-870aedd9/observer-control-plan.md)尚未执行；原baseline plain无pool边界，不能由合计时间反推无profiler迟启动。补共同CUDA API/设备指标后再选择系统/驱动单因素观测，不直接改flush/stream/等待策略。
- [x] 完成固定46c152a1的独立job诊断构建、数值门槛和两轮采集。
  - 2026-10-30：[阶段入口](../tobeo-20261030/qwen36-job-path/README.md)。原配置/计算保持，独立NVTX诊断及完成原子序号补充构建均通过CUDA、17项选定测试和Ninja；两轮各四份完整logits与原参考逐位相同、八条测量输出/布局通过，原基线与首轮保留。第二轮于13:32:02恢复日常服务、配置SHA相同，无恢复错误。已分析两个63迭代路径和实际最后完成发布，不代表原版无扰动的唯一全系统根因；新增材料未外发。
- [x] 完成job级路径的最终文件/账本验收及正式报告收尾。
  - 2026-10-30：[正式报告](../tobeo-20261030/qwen36-job-path/README.md)、[验收汇总](../tobeo-20261030/qwen36-job-path/summary.json)、[phase账本](../tobeo-20261030/qwen36-job-path/phase-ledger.csv)、[token账本](../tobeo-20261030/qwen36-job-path/token-ledger.csv)。13:39:26后台验收/静态封存通过，用户返回后再次核对161份文件及manifest指纹。两个63迭代路径、共10160个phase/243840个行任务覆盖和原子完成序号通过，phase/token账本精确闭合；106/67个decode phase最后发布者不同于最晚body，已修正首轮代理。四份完整logits、八条输出/布局、17项选定测试及来源/模型/旧证据一致性通过。完成受控观测job路径，未确认无插桩全系统根因；trace/on decode扰动22.1%/13.5%，不将任务wall称纯算术，不重复累计host等待。GPU半边2514/2516层在CPU pool结束后才启动，先调查执行/提交残差；未验证优化收益、全栈、HIP/SYCL或全量质量。原基线与首轮保留、日常服务13:32:02恢复且配置不变、新材料未外发。
- [x] 完成正常HtoD下固定46c152a1的CPU周期IP/调度试采与复制event机制补充。
  - 2026-10-30午间：[报告](../tobeo-20261030/qwen36-cpu-mechanism/README.md)、[CPU数据](../tobeo-20261030/qwen36-cpu-mechanism/cpu-summary.json)、[复制依赖数据](../tobeo-20261030/qwen36-cpu-mechanism/mechanism-summary.json)、[320步明细](../tobeo-20261030/qwen36-cpu-mechanism/mechanism-stages.csv)。CPU-only预检1851周期样本/13899调度事件；三格各一条同日参考与CPU trace，六测量均匹配旧64token参考、63slots/2048chunk/fresh/0草稿/0换槽/退出0；decode样本9448/12093/11867，固定PDB解析引擎image 0未解析，七worker及CUDA提交线程已定位。基线16K worker等待52.63%、算术20.09%，2430算术样本均在GPU空隙；分母含注入线程，内核态13.45%未解析，不等于wall time或瓶颈份额。三格组合trace/plain decode为1.165/1.152/1.104，全部保留；WPT未安装，merged ETL未生成，但SQLite CPU/调度可用。原复制trace320步均核对字节守恒和双buffer record/wait关联，DtoD流实际priority=-5，设备event timestamp=0故不声称GPU wait时长。HtoD24.862111→24.942329GB/s，12:05:08原Flash-Next恢复、配置SHA相同，无恢复错误。未重建引擎、扩展推理配置、改默认、更新原五组计时或自动外发。完整因果关键路径、全栈和内核态符号仍未完成。
- [x] 完成已有PR3905复制切片在本机固定布局的独立验证。
  - 2026-10-30：[报告](../tobeo-20261030/qwen36-copy3905/README.md)、[汇总](../tobeo-20261030/qwen36-copy3905/summary.json)、[全部配对](../tobeo-20261030/qwen36-copy3905/pairs.csv)、[查重索引](../tobeo-20261030/qwen36-copy3905/upstream-summary.json)。归属xyehya/af08278c，仅复制hunk+CLI适配，不是整套PR验收。固定46c152a1/Q4/Windows5060Ti、63slots/chunk2048/7workers/MTP0/packed；独立CUDA构建、17项选定测试、原基线/候选off/on两长度各64行完整词表logits有限且逐位一致；4条自由生成门禁及20条正式新进程请求全部匹配参考、fresh/0草稿/0换槽/退出0。每长度五对交替AB/BA，1K/16K prefill配对比中位数1.3021/1.1915、合计1.0825/1.1457，均5/5变快；decode波动保留。达预设规则后两条16K trace核对输出/范围/PID/复制字节及独立DtoD流，staging总字节相同，不混入收益。矩阵HtoD前24.955953/后24.880983、跟踪前24.899590/后24.885794GB/s；08:24:20再次恢复原Flash-Next0.1.52、loaded=true、配置SHA相同，无恢复错误。首轮入口DLL部署失败在门禁停止、另开execution-02，无旧计时混用。未运行HIP/SYCL、动态换槽、并发、长稳或全量质量；不改默认；本实验阶段未外发，后续实际发布见下一项。完整CPU归因及总瓶颈项仍未勾选。
- [x] 将PR3905独立复制验证发布到原讨论，并归档可访问的脱敏证据。
  - 2026-10-30 09:22:50：[原评论](https://github.com/Niko1221/Strata/pull/3905#issuecomment-6512596830)、[发布记录](../tobeo-20261030/qwen36-copy3905/PUBLICATION.md)。用户授权后发布，作者Thymos2027、全文回读与本地实际文本一致，无重复评论。fork独立分支固定commit `7c0247c72d3e57df40e2dd8b9be415ec90046f98`，55文件仅证据目录，逐文件线上内容一致；离线核对三输入、六数值摘要、24输出/日志、十配对及trace字节守恒。原始94文件实验manifest未改。连接器fork写入成功、上游评论403后用同账户gh完成，未新开PR/issue、修改fork main或既有PR，也未新增GPU测量/默认变更。完整CPU归因、HIP/SYCL及全量质量范围不因此计完成。
- [x] 建立固定最大上下文的 1K/4K/8K/16K 实验矩阵。
  - 2026-10-22 完成 24/24 条请求，每格 3 次、均输出 256 token；曲线、中位数、范围及测量边界见[阶段 B 报告](../tobeo-20261022/qwen36-context-curve/README.md)。固定配置上限 32768，实际输入为 1025、4096–4097、8193、16385 token。
- [x] 核对真实 MTP 状态、专家布局和前缀复用状态。
  - 2026-10-22 原生短 prompt 基线：MTP 2 接受 567/786 个草稿，每层固定 64/256 专家驻留 GPU，fresh 请求日志 reused=0。新实验矩阵仍须逐次记录这些状态；本项不代表多会话缓存验证完成。
  - 同日阶段 B：24 条请求均 reused=0；MTP 0 全部 offered=0，MTP 2 全部 offered>0；6 次启动均为 64/256 固定专家槽位、slot replacements=0。12 对输出哈希一致，范围限于本轮配置和 workload。
- [x] 采集加载/预热之后的 decode trace。
  - 2026-10-22：Nsight 2026.1.3 四组完整生命周期采集后，按 NVTX 筛选预热后的 decode；图、kernel 明细和诊断见[阶段 C 报告](../tobeo-20261022/qwen36-profiling/README.md)。实际 Graph 关闭；未采 CPU sampling/context switch。六项汇总检查通过，未将两批有问题的试采当作正式结果。
- [x] 跑通 Compute 的 1K / MTP 0 最小硬件计数采集。
  - 2026-10-23 首次 1K 完成：application replay 1 个 pass，三个指标有效、尺寸匹配，64-token 输出验证与服务恢复通过，见[最小采集报告](../tobeo-20261023/qwen36-compute/README.md)。后续 16K 见下一项；完整硬件指标仍未覆盖。
- [x] 补齐 16K / MTP 0 的相同三个 Compute 指标。
  - 2026-10-23，代理直接运行；874.176 μs、DRAM 读 91,881,216 bytes、写 1,098,752 bytes，shape、64-token 前缀和服务恢复均通过，见[两上下文汇总](../tobeo-20261023/qwen36-compute/summary.json)。每个上下文只测一个调用，不代表 L2/stall/occupancy 已完成。
- [x] 检查同日环境漂移，独立核对主机到 GPU 的传输通路。
  - 2026-10-29：已发布并按当前 Bug report 模板修正上游 [issue #4381](https://github.com/Niko1221/Strata/issues/4381)，保留 TDR 后约 1.7 GB/s、重启后同一探针 24.88 GB/s 的实测、时间线和未确认根因限制；Intake 自动检查通过，`needs-format` 标签已移除。仅为历史单次相关事件序列和排障参考，没有可重复 TDR 触发器，也未声称当前 0.2.7/engine 0.1.52 存在回归。
  - 2026-10-28 后续：日常 engine 0.1.46 → 0.1.52 已完成，官方包 SHA-256、签名/文件、组件 test-start 及短回答、代码、中文、A→B→A、工具调用验收通过；配置未变、旧组件保留，HtoD 约 24.9 GB/s。见[升级与验收](../tobeo-20261028/engine-upgrade/README.md)。未运行长上下文、正式性能 A/B 或当前源码基线，不扩大全局完成范围。
  - 2026-10-28 上游拉取与用户重启后，恢复[日常 IQ3_S 服务](../tobeo-20261028/daily-start-105651/README.md)：当前服务端配合已安装 engine 0.1.46，health loaded=true、短 API 回答通过，启动 H2D=24.9 GB/s、温度遥测可用。未升级引擎，显存余量告警仍在；未将 6-token 冒烟请求作为正式性能测量。
  - 2026-10-28 [报告价值评估](../tobeo-20261028/pcie-after-reboot/README.md)：重新检索 TDR/PCIe/reboot/Nsight 的 issues，建议优先向 NVIDIA 报告恢复后的持续低吞吐，Strata 侧作排障参考；未找到确认同案，未声称穷尽查重，未发布 issue/comment。后续实际提交前仍需完成 PR/评论范围的针对性查重及脱敏。
  - 2026-10-28 用户整机重启后，用 10-24 同一 exe 复测：H2D=24.882、D2H=28.370、mapped read=16.651 GB/s，退出码 0、数据抽查通过，负载期间采到的代际均为 Gen5，驱动仍为 610.88。见[重启后恢复验证](../tobeo-20261028/pcie-after-reboot/README.md)。确认本轮传输恢复，强支持此前持久驱动/设备状态异常；未启动日常模型或测 decode，不代表阶段 C 归因或正式性能 A/B 已完成。
  - 2026-10-24 [进一步定位](../tobeo-20261024/pcie-root-cause/README.md)：核对原始事件，13:26:01–04 TDR 紧接 13:26:07 首次慢探针；卸载模型后独立 H2D=1.726、D2H=1.807、mapped read=1.608 GB/s，D2D=186.7、CPU memcpy=17.24 GB/s，抽查通过。复现 NVML RX 峰值高于有效 payload 带宽。优先怀疑 TDR 后持久驱动/设备传输状态；物理代际仍有报告冲突，未执行系统/设备复位，不将相关性记作根因已证实或环境已恢复。
  - 2026-10-24 完成 HtoD 症状的[上游 issues 检索](../tobeo-20261024/strata-restart/github-related-issues.md)，核查 #485/#2137/#2453 正文及评论；找到探针低估、Gen1 限速与同卡 decode 降速的相关报告，但未确认完全同因案例。未发布消息或执行新测量，不代表本机环境恢复。
  - 2026-10-24 经用户授权重启日常 Strata：模型已加载，温度/功耗/利用率遥测恢复；启动 HtoD 仍为 1.7 GB/s，传输异常未恢复。见[重启验证](../tobeo-20261024/strata-restart/README.md)。未改配置或系统设置，未新增 decode 测试，不将遥测恢复记作性能恢复。
  - 2026-10-24 补查 Dashboard 遥测：旧服务 `/metrics` 温度/功耗等为空，而新进程用相同 `_Nvml` 读取成功，温度约 48°C；见[遥测核查](../tobeo-20261023/qwen36-profiling/flash-next-slow-decode.md)。未重启或新增传输测量，不能确认与 HtoD 异常同源，环境恢复仍未完成。
  - 2026-10-24 只读复核[引擎升级时间线](../tobeo-20261023/qwen36-profiling/flash-next-slow-decode.md)：0.1.46 在 10 月 21 日升级后带宽正常，10 月 22 日 13:08 仍为 25.0 GB/s，13:26 同路径/版本/启动参数首次记录 1.7 GB/s。未做版本回滚 A/B，未确认异常触发原因，不新增阶段完成项。
  - 2026-10-23 补查日常 Flash-Next 的 21:46 请求日志：177-token decode 为 26.5 tok/s，MTP 接受 87/130，当前启动探针 1.7 GB/s，且有显存余量告警。见[日常服务慢速核查](../tobeo-20261023/qwen36-profiling/flash-next-slow-decode.md)。本轮仅核查已有日志，没有新增带宽/推理测量，也未确认换页或完成环境恢复。
  - 2026-10-23 20:17 再测为 1.732420997 GB/s，512 次 64-MiB pinned copy、抽查通过；负载时 NVML/PnP 冲突仍在，环境尚未恢复。证据为本机 `tobeo-20261023/qwen36-profiling/pcie-diagnostic-03/result.json`，范围与[无重启续做安排](../tobeo-20261023/qwen36-profiling/no-reboot-next-steps.md)已记录。用户仅能远程操作，暂不安排重启或驱动维护；日常服务仍已加载。
  - 2026-10-23，无 profiler 控制 1K prefill 为 23,045.2 ms；两次 64-MiB copy 约 1.732/1.734 GB/s，卸载日常模型后仍慢；复现冻结引擎原始 256-MiB/四 burst 探针为 1.735 GB/s。NVML 负载报告 Gen1×8，PnP 速度编码仍为 5，底层原因未确定，见[环境诊断](../tobeo-20261023/qwen36-profiling/README.md)。这完成的是异常识别，不是正常测量环境恢复。
- [x] 对已有 FP32 GQA 方案完成本机局部构建与正确性验证。
  - 2026-10-23，#3641 固定源码未修改，MSVC/CUDA 13.2/sm_120 构建与三个选定布局/数值测试通过；真实 Q4 的 1K/64-token、FP32 KV、GQA=0/1 输出一致，见[验证报告](../tobeo-20261023/qwen36-pr3641/README.md)。只验证作者既有实现，16K 实模、五组配对和 HIP/SYCL 本机验证尚未完成。
- [ ] 写出一个瓶颈结论，再决定最小改动。
  - 2026-10-30下午：[job级报告](../tobeo-20261030/qwen36-job-path/README.md)已形成受控依赖与时间分解。GPU半边早提交但多数在CPU pool结束后启动；可见空隙与CPU范围重叠，不能归为纯专家计算或GPU连续繁忙。下一项收窄到执行/提交残差的单因素诊断，仍无无插桩根因或候选收益证据；本总项继续未完成。
  - 2026-10-30午间后续：正常工况已获得CPU算术/等待的直接样本与调度证据，基线16K已识别算术样本均落在GPU空隙；同时大多数worker样本是在等待循环。可以排除“全部on-CPU均是有效专家计算”的解读，但尚无精确job级关键路径分解、独立优先级消融或等待策略收益证据，因此仍不勾选本总项、不据采样比例写优化。
  - 2026-10-30早间后续：[复制切片独立验证](../tobeo-20261030/qwen36-copy3905/README.md)已将prefill假设收窄为可验证结果：同布局下约38.67GB专家权重从host转为独立stream DtoD，字节守恒，1K/16K合计配对比1.0825/1.1457且均5/5改善。但已有作者实现，不是新原创优化；decode CPU/IP/调度归因仍缺失，因此本总项保持未完成。
  - 2026-10-30：[一页阶段观察](../tobeo-20261030/qwen36-systems/bottleneck-notes.md)已形成。16K prefill HtoD约157.13→78.57GB，copy/kernel重叠4723→3096ms，不能相加当串行成本；decode k_attn_part约556–559ms/21%–22%，仍有1.36–1.49秒GPU未覆盖。匹配源码的整层/分段复制门槛是下一项静态线索，未测两路径取舍；CPU采样权限不足，完整归因及最小改动选择不计完成。
  - 2026-10-29：#4335独立对照中，4096使GPU槽位63→50，16K prefill的2048/4096配对比中位数1.3029、合计1.1788（均快5/5）；generation为0.9791（慢5/5）。1K合计0.9779（慢5/5）。已确认本组分项与长度取舍，但没有将槽位和chunk交叉隔离、没有正常工况关键路径时间线，不把这些时长直接当作最终瓶颈归因。见[独立报告](../tobeo-20261028/qwen36-pr4335/README.md)。
  - 2026-10-28 固定历史五组配对补充：#4347释放副本后，16K generation的A/B耗时比中位数1.0395（5/5变快），但prefill为0.9591、合计0.9834（5/5变慢）；1K合计方向混合。说明本组GPU专家增加未抵消prefill代价，未定位其具体原因，不把分项收益当作正常工况关键路径结论。见[配对报告](../tobeo-20261028/qwen36-pr4347/README.md)。
  - 2026-10-28 后续：在1K/16K各97行全词表强制历史中，候选与主线匹配63/89槽位后分别逐位一致；布局变化自身top-1为96/97、95/97。将归因收窄为本组专家布局变化可复现的数值差异，未定位具体算子或正常工况关键路径；见[后续验收](../tobeo-20261028/qwen36-pr4347/validation-next-summary.json)。本项仍未完成。
  - 2026-10-28：#4347实测释放1.78GiB、槽位63→89。固定相同63槽位时packed开关的97行完整logits逐位一致；改变为63/89槽位的1K教师强制对照top-1为96/97一致、mean KL0.001171。支持继续归因专家驻留与CPU/GPU执行差异，但没有新时间线/访存计数，不将数值诊断当作最终关键路径结论。
  - 2026-10-23 夜间：1K CPU IP 采到 10,870 个周期样本，本地 PDB 显示大量等待循环 IP，不能把 on-CPU 全算作专家数学计算；只有一个受环境异常影响会话中的短请求，不能建立正常 Gen5 的关键路径结论。16K CPU、L2/L1/stall/occupancy 与缓存状态对照待继续。
  - 继续使用[观察与待验证假设](../tobeo-20261022/qwen36-profiling/bottleneck-notes.md)界定范围，不将 GPU 热点当作唯一瓶颈。权限、重复编号、超时、kernel replay/TDR 的历史排障见[原记录](../tobeo-20261022/qwen36-compute/README.md)，不以早期失败覆盖后续成功，也不以三个计数代替最终归因。
- [x] 完成#4347冻结布局的1K/16K匹配主线数值对照与小型任务回归。
  - 2026-10-28：[前瞻协议](../tobeo-20261028/qwen36-pr4347/validation-next-plan.md)先于结果写定。两上下文各97行×248,320项，A=C、B=D全部逐位一致且有限；四臂各12/12任务通过，共48/48，覆盖JSON算术、中文、小函数执行与1K/16K检索。新增文件参数入口只链接既有库，原exe/库哈希不变且原入口数值复核通过；原始GEN终止token评分误判已修正，保留原输出和原评分。见[报告](../tobeo-20261028/qwen36-pr4347/README.md)与[小型证据](../tobeo-20261028/qwen36-pr4347/validation-next-summary.json)。仅Windows/CUDA、冻结驻留和确定性小样本，未验证动态换槽、普遍质量等价或速度；下载持续，日常服务恢复loaded=true。
- [ ] 按正确性、配对测量和上游范围要求完成交付。
  - 2026-10-29 P1受控验证完成：[Flash-Next报告](../tobeo-20261029/flash-next-affinity/README.md)的performance-04于17:51完成15次启动/45条请求，功能18/18、输出/草稿数量及31次环境检查通过；收尾回读完成。measure四轮选P、一轮选all；代码/英文/中文合计配对all/P中位数1.0019/0.9996/1.0016、P较快4/2/3对，均未达稳定方向与幅度标准，不写校准补丁或变更日常默认。P累计CPU时间较低不代表能耗/关键路径改善。此前15+3条环境失败计时隔离；下载v5续传、日常loaded=true、配置SHA未变。仅当前单机受控配置，完整质量、日常默认扩展及跨后端交付继续未完成。
  - 2026-10-29 下载状态复核：DeepSeek七份已确认235.95/273.80GB（86.18%）、5份此前校验通过，v2因分段ETag不一致退出；重新探测与断点标识相同后，以v3日志和最多4次外层重试恢复四路续传，短检确认实际新增数据。见[下载续传记录](../tobeo-20261028/deepseek41-community/README.md)。仅恢复下载，不将其计作完整下载、模型可运行或社区案例完成。
  - 2026-10-29 发布进展：经授权已在#4335/#4347原PR补充独立反馈，并提交[报告PR #4577](https://github.com/Niko1221/Strata/pull/4577)。仅一个bench/results目录，含公开输入、40次正式运行/20对数据、失败记录及原/新增脚本各自验证范围。线上回读、作者、head与113文件范围核验通过，Intake check成功、sweep跳过；未合并，未将发表当作完整优化/质量/跨后端交付完成。见[发布记录](../tobeo-20261028/qwen36-publication/README.md)。
  - 2026-10-29 较早快照（发布前，后续见上方发布记录）：#4335原head独立构建、数值/24条任务、20次正式运行及环境收尾均完成；Windows/Blackwell长输入收益与短输入代价已写入[报告和本地英文反馈草稿](../tobeo-20261028/qwen36-pr4335/README.md)。未发布，未改默认；完整质量、动态换槽、更多上下文/batch/MTP及跨后端仍未验证。原自由生成身份失败不撤销，完整交付继续未勾选。
  - 2026-10-28 历史快照：已另立协议完成固定历史五组配对（下项），结果为generation/prefill取舍，未证明完整请求加速；原自由生成身份失败、动态换槽、完整质量和跨后端范围仍保留。下一项独立验证chunk2048/4096及#4335，不同时改packed策略；未对外发布或变更日常默认。
  - 2026-10-28 后续：已补16K教师强制与48条小型任务回归，数值/任务门槛通过；原256token身份失败不撤销，不重新使用旧性能数据。下一步另立固定强制历史、固定工作量的五组配对协议，区分受控布局成本与自由生成性能；本轮未运行新性能配对、未完成交付或对外发布。
  - 2026-10-28 本轮执行完成并按门槛停止：当前源码基线通过，#4347在Windows/Blackwell实际触发；1K/16K的256token首组分别于第76/19输出token分叉，因此未运行剩余四组、不计算等价加速比。完成固定布局生成及97行全词表的两类教师强制诊断，报告与小型数据见[首轮结果](../tobeo-20261028/qwen36-pr4347/README.md)。未做完整质量验收、16K教师强制、跨后端或#4335；日常0.1.52服务和下载均恢复。整体交付继续保留未勾选。
  - 2026-10-28 再评估后：当前源码基线与 #4347/#4335 独立验证均未执行；历史GQA局部门禁不替代新候选门禁。以[新顺序](../tobeo-20261028/topic-reassessment/README.md)推进，未完成项继续保留未勾选。
  - 2026-10-28：传输状态已恢复，当前主线基线、#3641 当前主线集成候选、16K 实模门禁、至少五组交替配对和最终贡献范围仍待完成。旧续跑脚本须先更新版本与归档入口；新结果产出前不填加速比，不把旧 base 的候选结果当作当前发布结果，也不把已有上游实现记作自写优化。
- [x] 在原亲和性讨论补充实测结论和公开证据，并收尾本轮三项选题。
  - 2026-10-29：[#1912评论](https://github.com/Niko1221/Strata/pull/1912#issuecomment-6494468322)已发布，作者/全文回读一致；22份脱敏证据在fork固定commit `d973440a`逐文件回读通过，离线核对45请求/15日志/15组配对通过。未新建PR、issue或重开讨论，fork main与#4577未改。连接器403后使用本机同账户gh发布。见[发布记录](../tobeo-20261029/flash-next-affinity/README.md)；[选题文档](../tobeo-20261028/topic-reassessment/README.md)已写明三项最小验证收尾及下一步DeepSeek社区案例/正常工况profiling条件，未将未执行扩展标完成。
- [x] 评估Flash-Next亲和性成果的公开贡献定位。
  - 2026-10-29：[发布评估](../tobeo-20261029/flash-next-affinity/README.md)已检索相关开放/关闭issue和PR，复核#1912、#3522、#4401及既有#4577，阅读贡献/社区测量规则。建议以独立受控报告补原讨论，必要时另提结果型Benchmark PR；不报稳定错选bug、不把累计CPU时间称为省电。仅完成评估，英文脱敏独立证据包及新成果发布尚未执行。
- [x] 完成Flash-Next IQ3_S现有CPU布局受控五轮性能对照及收尾复核。
  - 2026-10-29：[正式报告](../tobeo-20261029/flash-next-affinity/README.md)、[45条小型汇总](../tobeo-20261029/flash-next-affinity/summary.json)、[全部15组配对](../tobeo-20261029/flash-next-affinity/paired-results.csv)。官方0.1.52，实际3107slots/6092MiB，三种合成输入各256token输出，15次独立启动、每臂96token预热、五轮预定顺序；45条完整输出/草稿数量一致，31次下载停止/断点未变检查通过。HtoD24.846733→24.853699GB/s、漂移0.0280%；恢复日常loaded=true、配置SHA未变，下载原命令v5后台续传。未复现稳定错选，不改校准器或默认；仅Windows/CUDA当前硬件受控参数，不代表日常默认、并发、完整质量或其他CPU/后端结论。
- [x] 完成Flash-Next IQ3_S现有CPU布局三臂的受控功能门槛。
  - 2026-10-29：[报告及后台交接](../tobeo-20261029/flash-next-affinity/README.md)、[前瞻协议](../tobeo-20261029/flash-next-affinity/experiment-plan.md)、[公开输入](../tobeo-20261029/flash-next-affinity/workloads.json)。官方0.1.52、实际3107slots/6092MiB、spec4/min-p0/lookup0/suffix0下，all/P/measure各三条256token输出及草稿数量一致，另六任务各模式全过（18/18）。功能阶段下载运行，时长不作性能证据；后台五轮矩阵、正式性能结论、完整质量及日常默认配置收益均未完成。
- [x] 完成#4347冻结驻留、固定历史的五组交替性能配对。
  - 2026-10-28：[前瞻协议](../tobeo-20261028/qwen36-pr4347/fixed-history-plan.md)先于计时写定；两输入各五对，共20次独立进程，96token强制历史、97次argmax、无完整logits写盘，每次与对应臂既有验收输出相同、槽位63/89、0换槽。1K合计A/B中位数0.9949（B快2/5），16K为0.9834（B快0/5）；16K generation为1.0395（B快5/5），prefill代价抵消该收益。见[小型汇总](../tobeo-20261028/qwen36-pr4347/fixed-history-summary.json)与[10对原始毫秒](../tobeo-20261028/qwen36-pr4347/fixed-history-pairs.csv)。HtoD前24.860822/后24.835640GB/s，漂移0.1013%；下载恢复、日常服务loaded=true、配置哈希未变。仅固定历史Windows/CUDA成本对照，不代表原自由生成协议、质量等价或普遍加速验收完成。
- [x] 核对DeepSeek下载失败并恢复已固定版本的断点续传。
  - 2026-10-29 19:02原七文件下载完成，本次重新全量计算SHA-256及核对大小7/7通过；8K/full/文本/单卡只读plan和原样ISTA pack recipe准备完成。signed feed选定sm120专用0.1.52包，原安装器0 bytes后切curl续传；19:11包91.76/422.15MB持续增长，尚未安装或加载。证据见[案例准备记录](../tobeo-20261029/deepseek41-case/README.md)。目录整理按先完成案例后迁移的顺序，未执行搬迁。
- [x] 核查 #4605 评论参数适配并归档有界实验结果。
  - 2026-10-29 后验核查 edt-xx 评论：实际专用引擎拒绝 `--ple-io direct`；匹配构建另有 `DS4_EG_DIRECT`。受保护 64GB store 小对照已执行，B1 日志进入 Engram direct 路径，但 1K 输出身份门槛失败，按预案停止；未见明显系统 commit 回收，未确认自动预算修复。Qwen 恢复及配置 SHA 通过；见[参数与实测边界](../tobeo-20261029/deepseek41-case/edt-xx-check/README.md)。
- [ ] 完成 DeepSeek Engram direct 的完整 ABBA 与输出等价验证。
  - 2026-10-29：本次计划在 B1-1K 后因输出身份门槛停止；剩余 B1-4K/B2/A2 未运行，没有等价性能或自动预算修复结论。后续须先区分基线重复性与读取字节问题，再另立协议；本项不影响此前已完成的原配置使用案例。
- [x] 核对目录整理中 Qwen3.8 IQ3_S 的归属与运行引用。
  - 2026-10-29 扩展为整个 `D:\Models\Strata` 的只读盘点：11 个子目录及根目录散文件已记录用途、逻辑大小和处置建议，证据见[逐目录报告与 inventory](../tobeo-20261029/model-directory-audit/README.md)。确认 `mtp/rt` 是日常 Qwen3.8 的直接运行依赖；原始 tensors、量化 GGUF、两个模型的 packs 和下载残留分开识别。本次未搬迁、未删除，未全量重算哈希或完成全部路径依赖审计。
  - 2026-10-29：确认 `D:\Models\Strata\IQ3_S` 含两份 Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S 权重及完成标记，`strata-iq3_s.json` 第 7、9 行引用其旧绝对路径；`D:\Models\Qwen` 已有其他 Qwen 家族模型。本次仅盘点与确定建议目标，没有迁移或修改运行配置。
- [x] 完成模型与 Strata 配套目录的独立迁移及验收。
  - 2026-10-29 23:46完成：Qwen3.8 IQ3_S、MTP、按模型拆分的 packs 及 DeepSeek 主权重/共享文件已归入家族目录；引擎原位保留，历史与残留归档。17 项移动、110/110 完整 SHA-256、长度/文件标识、配置仅计划路径替换检查通过；DeepSeek 新路径 pack-info/实际加载/Paris 请求通过，日常 Qwen 恢复/Paris 请求通过且 draft_n=3，冻结控制器未变。证据及回退材料见[迁移报告](../tobeo-20261029/model-directory-audit/MIGRATION.md)。未重跑长期性能实验，Qwen3.6 仅验证 tokenizer 文件迁移及引用，没有新增该模型推理验收。
  - 建议目标为 `D:\Models\Qwen\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S`，与 DeepSeek 家族整理一并规划。迁移前盘点 MTP、pack 与其他实际路径依赖；卸载日常模型后再搬迁，修正运行引用、校验并恢复服务。历史测量证据保留原路径，另记迁移映射。
- [x] 完成DeepSeek V4.1 Flash IST-DAS 2.25bpw Windows单卡使用案例。
  - 2026-10-29后续经授权发布[#4605](https://github.com/Niko1221/Strata/issues/4605)：聚焦专用DeepSeek自动store的Windows commit余量，引用#1607并保留手动保护/失败边界。原始事件补核145.637/145.730GB系统commit，分页文件澄清为初始4GB/最大8GB。用户fork独立证据分支commit72ff3a29，25文件/5.96MB；52次HTTP、52条native timing、4384采样离线核验及25文件线上字节哈希、issue作者/正文回读通过。未创建PR、未修改fork main/默认或引擎源码，未确认根因/修复；见[发布记录](../tobeo-20261029/deepseek41-case/PUBLICATION.md)。
  - 2026-10-29社区反馈评估：在线检索并读取#1607/#4362/#4426等相关正文/评论，确认维护者今日关闭benchmark PR并说明筹备网站收录。建议聚焦DeepSeek专用后端Windows commit余量的新issue并引用旧讨论，完整手动配置案例作证据；不冒充#4362复现、不直接开修复或纯跑分PR。未发布/上传，公开包脱敏与整理未完成，见[投稿评估](../tobeo-20261029/deepseek41-case/PUBLICATION_ASSESSMENT.md)。
  - 2026-10-29 20:10完成、20:12后验收：原七文件全量SHA、专用0.1.52签名/哈希与pack-info通过；保留自动预算提交耗尽、80GB store触及94%保护两批失败。独立64GB store/1536MiB显存保留、8K/full文本配置完成九次功能请求、1K/4K各三次256输出及1844.141秒/36条连续请求，无请求错误；20:10:30恢复Qwen、20:12实时health和配置SHA相同。52次HTTP/189份证据离线核验通过并注明两条功能汇总messages引用差异；报告/数据/曲线见[最终案例](../tobeo-20261029/deepseek41-case/REPORT.md)。短矩阵decode中位7.1/7.2tok/s，后段英文1K变慢保留；仅本机手动配置短期案例，不代表默认、8K实输入、完整质量、跨后端或对外发布完成。
  - 2026-10-29 19:40：execution-01自动预算遇Windows提交耗尽；execution-02的80GB store完成局部功能/性能后触及94%保护，均保留失败及Qwen恢复证据。execution-03改为独立64GB store、1536MiB显存保留，原量化/8K/full不变；九次功能请求及1K/4K各三次256输出通过，19:38:57起进行至少30分钟连续请求。按用户要求停止前台监看，后台PID26304继续并自动尝试恢复日常Qwen；完整连续运行、最终恢复、离线核验和最终报告尚待完成，保留未勾选。见[运行交接](../tobeo-20261029/deepseek41-case/README.md)。
  - 2026-10-29 19:20：422,151,870-byte专用0.1.52 CUDA13/sm120包下载及SHA/可信签名/逐文件/manifest对signed feed核验通过，独立安装完成。pack-info退出0，六个引用文件存在且长度足够、tensor device type齐全；见[案例记录](../tobeo-20261029/deepseek41-case/README.md)。尚未GPU加载、功能/性能或连续请求，保留未勾选。
  - 2026-10-29：七文件重新全量校验、只读plan、pack准备完成；专用引擎下载中。尚缺引擎签名/文件最终验收、pack-info、8K full加载/功能、1K/4K各三次及约30分钟连续请求，不能以准备步骤代替案例完成。协议与证据入口见[案例目录](../tobeo-20261029/deepseek41-case/README.md)。
  - 2026-10-29 17:09：核查v4停滞实际为下载树线程Suspended，17:02时已249.94/273.80GB（91.28%）、六项verified；短暂恢复后用户说明有试验在跑，已重新挂起同一下载树，保留断点。未检查或修改试验，未确认最初挂起者；见[状态记录](../tobeo-20261028/deepseek41-community/README.md)。本轮只完成状态确认及恢复暂停，完整下载与推理未完成。
  - 2026-10-29 16:27：排查确认同一固定ModelScope版本在本轮请求中返回不同ETag，旧下载器重复拒绝分段；两文件固定revision的大小/SHA元数据一致，六处64KiB本地/远端抽查相同。停止v3后启用本地fresh-range脚本，保留断点、每段重新获取地址、两文件各两路独立续传，最终仍须全文件SHA。语法和五项HTTP响应校验案例通过，约45秒新增234,881,024 bytes，两文件均增长且无新错误；后台PID11260/23764、`download-v4.*.log`，见[恢复记录](../tobeo-20261028/deepseek41-community/README.md)。本次完成排查及实际恢复，网络自动重试/完整下载/推理尚未验收，整体交付保留未勾选。
  - 2026-10-29 16:18只读复核：目标仍为ISTA-DASLab IQ2_XS/2.25bpw，Unsloth两项是安装配置引用的元数据与DSpark配套文件；确认236.59/273.80GB（86.41%），进程仍在但短检无增长，DSpark反复出现版本标识不一致及连接停滞提示。核对单文件顺序调度及已有正式文件/校验标记，未重新计算大文件哈希或更改任务；见[下载记录](../tobeo-20261028/deepseek41-community/README.md)。本次仅完成来源与状态解释，不新增完整下载或推理完成项。
  - 2026-10-29：确认进程退出、留存失败状态、区分分段ETag错误与旧回退超时；当前两文件的Range/大小/ETag与断点相符，未改变版本或校验。脚本语法检查及实际续传增长通过，新增外层重试耗尽分支本轮未触发；保留37.85GB左右未完成部分继续后台运行。证据入口为[下载记录](../tobeo-20261028/deepseek41-community/README.md)及本机`download-v3.*.log`。完整模型下载与推理测试仍未完成。
- [x] 发布DeepSeek Windows提交内存问题及脱敏使用案例证据。
  - 2026-10-29：已在 [#4605 跟进评论](https://github.com/Niko1221/Strata/issues/4605#issuecomment-6499143642)澄清本次未设置 `--ple-io ram`、DSpark 未加载、101.3GB 来自专用 DeepSeek RAM store，并请求对方补充模型、版本、系统及有效 PLE 设置；未把普通用户的 Signal 15 案例当作同根因或维护者结论。
  - 2026-10-29：上游issue#4605与用户fork固定commit证据均已发布并回读核验；仅问题报告及独立证据目录，不是修复PR或纯成绩PR。真实运行与事后脱敏/校验范围分开记录，证据及限制见[发布记录](../tobeo-20261029/deepseek41-case/PUBLICATION.md)。
- [x] 发布两项独立验证反馈与报告型PR。
  - 2026-10-30：作者跟进询问#4347的16K prefill分项与`ne/3`阈值后，已发布[定向回复](https://github.com/Niko1221/Strata/pull/4347#issuecomment-6514456594)。回复补充原固定历史五对的prefill中位数7161.8/7478.3ms、配对比0.9591及5/5方向，并明确这是旧head、chunk2048、冻结驻留下同一请求的阶段计时，不是新跑的prefill-only workload，也未在rebase后复测；现有63→89槽位证据不足以主张调整阈值。评论以`@rynwang`和上下文说明指向所答问题，已通过GitHub API回读核验。本次未新增GPU测量、代码或默认变更。
  - 2026-10-29：[#4335评论](https://github.com/Niko1221/Strata/pull/4335#issuecomment-6488876445)、[#4347评论](https://github.com/Niko1221/Strata/pull/4347#issuecomment-6488877876)、[报告PR #4577](https://github.com/Niko1221/Strata/pull/4577)均已发布并回读核验。证据包完成脱敏、精确输入归档、离线统计/原日志核对、Git字节哈希、链接与范围检查；原实现归属不变。Intake check成功、sweep跳过；未声称全量CI、维护者认可或合并。范围见[发布记录](../tobeo-20261028/qwen36-publication/README.md)。
- [x] 完成#4335独立chunk数值/任务验收与固定历史五组配对。
  - 2026-10-29完成，10-28开始并按开始日期归档。原head `bdf0bce2` 独立Windows/CUDA构建及16项选定测试通过；1K/16K各五臂，主线/PR同chunk的97行全词表logits逐位相同，自动实选4096；2048/4096各12条任务通过。未叠加#4347，槽位63→50；20次正式请求均与对应chunk数值验收argmax一致、0换槽。16K合计约10.48→8.90s，配对比中位数1.1788（4096快5/5）；1K约3.33→3.40s、0.9779（快0/5）。HtoD前24.833714/后24.855839GB/s、漂移0.0891%；下载恢复、日常服务loaded=true、配置哈希不变。见[报告](../tobeo-20261028/qwen36-pr4335/README.md)、[小型汇总](../tobeo-20261028/qwen36-pr4335/summary.json)和[全部10对毫秒](../tobeo-20261028/qwen36-pr4335/pairs.csv)。仅冻结驻留、32K上限、96token固定历史及小样本任务，不代表普遍质量、动态缓存或默认策略全面验收。

## 本机日常服务262K验收（2026-11-03）

- [x] 完成 Flash-Next IQ3_S 本机原生262K上下文有界验收及日常服务切换（2026-11-03 16:43通过；证据入口：[报告](../tobeo-20261103/flashnext-262k/README.md)。仅在启动、近上限检索、续聊和8080验收通过后标记完成；失败恢复64K。）

262K验收完成记录（2026-11-03T16:43:14.746048+08:00）：见[tobeo-20261103/flashnext-262k/README.md](../tobeo-20261103/flashnext-262k/README.md)，仅启动、261584token检索、续聊缓存及8080短请求范围。

- [x] 核对262K日常服务空闲时的RAM/VRAM构成（2026-11-03）。证据：[内存账本](../tobeo-20261103/flashnext-262k/MEMORY.md)、实际启动日志、metrics、Windows GPU进程计数器及进程内存采样。范围为近似账本和统计口径核对，未进行卸载差分或逐分配器审计。

- [x] 完成64K与262K上下文重启资源ABBA对照并恢复262K服务（2026-11-03四轮完成并复核，17:56恢复262K；[证据入口](../tobeo-20261103/context-resource-ab/README.md)。四轮独立重启、无模型基线/加载后/相同短请求后资源采样；私有提交增量约2.52GiB，整机RAM增量约2.48GiB；未逐分配器归因，未测试长输入或性能。）

- [ ] 完成Flash-Next IQ3_S本机1/2/4槽并发性能矩阵及恢复验收。
  - 2026-11-03结果复核：1/2槽完整、4槽局部，38成功波/87成功请求，另4请求在4槽首轮四并发时因提交余量保护中断，35未尝试。完整矩阵保持未完成，按资源停止条件收尾，不自动重试。[复核报告](../tobeo-20261103/flashnext-concurrency/REVIEW.md)与review.json核对数据、失败、缓存/MTP及原配置SHA；22:29恢复、23:29实时262K健康通过。2槽在本合成任务下总吞吐较1槽低约18%–34%，未外推自然任务或隔离MTP/驻留因果。
  - 2026-11-03：用户已批准1/2/4服务端槽位 × 1/2/4客户端并发 × 1K/8K输入 × 三轮（126正式请求）。已编写独立后台流程、原始数据与资源采样、失败即停及262K日常服务恢复步骤，并通过Python语法检查；[协议与执行入口](../tobeo-20261103/flashnext-concurrency/README.md)、进度status.json。矩阵结果、实际槽位/缓存/MTP行为核对、最终性能结论及恢复人工验收尚待，保持未勾选，不把后台启动记为完成。

- [x] 完成Flash-Next IQ3_S本机1/2槽有界并发对照、4槽资源停止及恢复复核（2026-11-03）。证据：[复核报告](../tobeo-20261103/flashnext-concurrency/REVIEW.md)、review.py与review.json。范围为当前0.1.52/262K配置、1032/8202输入、256输出及三轮进程内重复；完整4槽矩阵、自然任务与独立因果归因未完成。
  - 2026-11-04：按同日相邻实验目录惯例补充目录级.gitignore，原始JSON/JSONL、日志和PID留本地，不纳入Git候选；报告与脚本保留。证据及克隆后核验限制见该目录README；此为版本管理整理，无新增测量，不改变实验完成范围。

## 多请求合并prefill探索（2026-11-04）

- [x] 核对现有Flash-Next接口是否提供独立请求packed prefill直接测试入口（2026-11-04静态审查）。Prefill绑定单SessionState，现有HTTP并发矩阵未合并独立请求的输入；证据：[接口与实验范围](../tobeo-20261104/packed-prefill-probe/README.md)。仅静态审查，无新端到端收益证据。
- [x] 完成真实量化权重上分次/合并GEMM的正确性和性能可行性实验（2026-11-04 15:50复核）。证据：[首轮报告](../tobeo-20261104/packed-prefill-probe/REVIEW.md)、review.py/review.json、逐工况CHECK/PAIR日志。真实第0层四矩阵、合成激活、24项数值门槛、48工况/240配对通过，配对比中位范围1.219–3.711；含重复反量化和可选权重上传成本，未隔离纯GEMM贡献、未调用生产grouped MoE路径。执行前日常服务已关闭，保持关闭；此为算子可行性，不是完整prefill或端到端收益。
- [ ] 实现并验证真正独立会话的合并prefill，测量完整阶段时间、状态保存恢复及端到端收益。现有0.1.52多槽实验及本轮算子探针均不能代替此项；尚未实现分段QSA/GDN/PLE状态隔离。

- [x] 梳理本session并发研究并保存至Obsidian日常开发记录（2026-11-07）。笔记：`C:\Users\tobeo\Documents\obsidian\lfppbVault\技术\日常开发记录\2026-11-07.md`的“Strata 并发研究复盘”主题，日常记录README已更新索引。按11月3日多槽服务与11月4日算子探针报告核对，区分整波计时/合并prefill、实测/因果假设及版本/资源边界；保留完整实现未完成和后续理解清单。本次仅文档归档，无新增GPU测试、服务改动或上游发布。
