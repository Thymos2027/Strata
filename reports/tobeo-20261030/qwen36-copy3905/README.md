# PR3905 split-stage-copy：Windows 独立切片验证

2026-10-30，北京时间。接续[正常工况时间线](../qwen36-systems/README.md)，前瞻范围见[experiment-plan.md](experiment-plan.md)。**已有复制方案在本机固定配置下通过数值与自由生成验收，五组无profiler配对中，1K/16K的prefill和prefill+decode合计均5/5变快。** 两条16K机制时间线及离线完整性核对亦通过，见[summary.json](summary.json)。

实现属于xyehya的[PR3905](https://github.com/Niko1221/Strata/pull/3905)，取其独立提交 `af08278c15e857345dad95805dda7256a559dcfa` 的四个复制hunk，并在固定46c152a1上适配CLI，差异为[candidate.patch](candidate.patch)的30增/7删。不引入整套堆叠PR的attention/KV/GDN/side-stream或默认kernel变化。本轮是已有实现的独立Windows验证，不是新优化实现，也不代表整个PR3905已通过验收。

## 固定条件和验收

Windows 11、RTX5060Ti16GB、i7-12700、128GB DDR4，MSVC19.42/CUDA13.2/sm_120、Ninja Release，源码引擎0.1.53。沿用[基线](../../tobeo-20261029/qwen36-repro-baseline/README.md)的Qwen3.6-35B-A3B UD-Q4_K_XL及完整SHA；32K上限、chunk2048、显式63slots后冻结驻留、7workers、MTP0、packed/MMQ、贪婪无penalty。A/B使用同一候选exe，B仅加 `--split-stage-copy`，不设STREAM_ALL。

- 独立CUDA构建、17项选定测试及Ninja无改动检查通过；原基线exe/DLL/库哈希保留。
- 1025/16385-token两输入，原基线/候选off/候选on各64行完整248320词表logits：六份均有限；同输入三臂逐位一致。每份63569920字节，原始f32留在本机。
- 四条原exe自由生成门禁及正式20条请求均输出64token，与原基线参考逐token一致，实际63slots/2048chunk、fresh、0草稿、0换槽、进程退出0。每条均为新进程，先做同一1K/64token预热。
- 正式每长度五对，交替AB/BA及长度顺序，不混入门禁或profiler计时；全部配对见[pairs.csv](pairs.csv)。正式指标来自原生协议，不是HTTP或标准社区benchmark。

## 无profiler结果

下表为五个**配对A/B耗时比**的中位数，>1表示B较快；范围包含全部五对。

| 输入 | prefill比及范围 | decode比及范围 | prefill+decode比及范围 | B较快对数：prefill/decode/合计 |
| --- | --- | --- | --- | --- |
| 1K | 1.3021（1.3019–1.3089） | 1.0008（0.9688–1.0272） | 1.0825（1.0576–1.1018） | 5/3/5 |
| 16K | 1.1915（1.1890–1.1947） | 1.0282（0.9477–1.1767） | 1.1457（1.1257–1.1874） | 5/4/5 |

等价的配对耗时下降中位数：1K/16K prefill约23.2%/16.1%，合计约7.6%/12.7%。单臂prefill时长中位数分别为806.9→619.8ms、7100.7→5948.6ms；它们的商不代替上表配对统计。decode有明显波动，本轮不据此宣称decode算术优化。

两长度均通过预写定的“prefill中位比>1.03且至少4/5同向”继续规则，才触发16K A/B各一份CUDA/NVTX跟踪。跟踪用于检查复制机制，不能加入上述收益。这里的合计只覆盖该64-token请求的prefill与decode，未含加载/预热，也没有推广到其他生成长度。

正式矩阵HtoD前24.955953/后24.880983GB/s；08:19:09恢复原Flash-Next0.1.52，health loaded=true、模型和配置SHA相同、无恢复错误。机制跟踪HtoD前24.899590/后24.885794GB/s，08:24:20再次恢复同一日常模型，loaded=true、配置SHA相同、无恢复错误。

## 16K复制机制观察

客户端prefill-to-first-token窗口内，HtoD为157132622720→118462308696字节（约157.13→118.46GB），DtoD为81920→38667961728字节（新增约38.67GB）。大宗专家staging复制：A的stream14为157126656000字节；B的stream14 HtoD为118458768000、stream15 DtoD为38667888000，二者之和与A完全相同。对应63/256驻留专家的权重改从GPU复制，没有少复制这一部分。

B的主要HtoD在stream14，主要DtoD在独立stream15；小输入/激活复制仍在计算stream13。这里按字节最多且覆盖各类>90%字节的stream识别大宗流，全部stream字节见汇总。HtoD+DtoD全量记录的微小差别来自窗口内辅助小拷贝，不等于专家字节丢失；没有逐字节转储全部staging内容。

两条输出与未跟踪参考一致，实际63slots/2048chunk、0换槽、退出0；CUDA kernel PID只来自目标引擎，三个客户端NVTX范围均存在且闭合，复制记录没有跨越该prefill窗口边界。每条仍有4条角色诊断：控制器Not all NVTX/No CUDA等，以及引擎No NVTX。实际引擎CUDA事件与客户端范围均已核对；没有检测到loss/error、驱动fallback或引擎CUDA警告，不能概括为全部警告为零。CPU sampling未运行，不能把GPU空隙归为CPU专家算术。

两条客户端窗口中，copy未与kernel重叠的并集约1.745→0.594秒，kernel并集约5.330→5.323秒，支持本机prefill改善与传输暴露减少相符；没有把copy与kernel时长直接相加。decode的k_attn_part并集约543/550ms、窗口占24.0%/22.6%，GPU未覆盖约1.244/1.397秒。每臂仅一条trace，不用于比较decode收益或替代CPU归因。

这些trace只用于机制验证，未混入五组性能统计，也没有直接测量stream的硬件优先级。

## 查重、失败记录和证据

查重时3905为open/unmerged；上游当日main为870aedd9，Qwen3.6源码/工具相对固定46c152a1无差异。3841为单缓冲显存取舍，3906为放置/异步换槽，不与本轮组合。原查询、正文、补丁及空评论/review列表在本机 `upstream-snapshot.json`，小型索引见[upstream-summary.json](upstream-summary.json)。这是有范围查重，不保证穷尽所有分支。作者RTX5080/Linux/Sage测量不当成本机数据。

首次 `execution-01` 在基线数值检查即停止：我把辅助入口放在没有相邻 `strata_kq.dll` 的目录，加载器回退到native grouped prompt，输出身份门槛失败，没有进入候选on或性能矩阵。08:00:34恢复日常服务、配置SHA相同。保留原日志、脚本和元数据；随后只把已链接入口及匹配DLL复制到独立arm目录，exe/库/引擎计算源码均未因此改变，增加MMQ实际路径检查。另开execution-02，没有覆盖失败或放宽标准。

公开保留协议、原作者补丁切片、脚本、汇总、全部配对和查重索引。本机另保留build-results、execution-01/02原日志及f32、跟踪报告/SQLite、脚本快照、库/exe和文件级SHA清单；大文件由.gitignore排除。summary内的manifest SHA可用于核对本机原始证据，不表示这些大文件已随Git归档。

复现从仓库根目录执行：

```powershell
python -u reports/tobeo-20261030/qwen36-copy3905/build_slice.py
python -u reports/tobeo-20261030/qwen36-copy3905/run_validation.py
# 只有完成的五组结果达到预设门槛才执行：
python -u reports/tobeo-20261030/qwen36-copy3905/trace_copy.py
python -u reports/tobeo-20261030/qwen36-copy3905/analyze.py
```

脚本拒绝覆盖已有构建/运行证据；重跑应另设目录并同步对应分析入口。候选在独立 `build-native-baseline/src-copy3905-af08278c` 和构建目录，主工作区计算源码、默认策略及日常引擎保留。实验后已按授权发布原PR评论和脱敏证据，见[发布记录](PUBLICATION.md)。

只有一台Windows/CUDA机器、一个Q4模型、63slots/chunk2048和两长度各64输出；没有HIP/SYCL构建、动态换槽、并发、长稳、完整质量或其他布局结论。没有逐字节转储所有staging内存。CPU采样权限仍不足，完整CPU/关键路径归因保持未完成。不改默认、不组合#4335/#4347，也不另提交作者已有实现。

原线程补充已于09:22:50[实际发布](https://github.com/Niko1221/Strata/pull/3905#issuecomment-6512596830)，脱敏证据固定在fork独立commit，详见[发布记录](PUBLICATION.md)与[实际评论](comment-3905.md)；先前英文草稿作为历史保留。复制方向不另写重复实现，也不自动扩展所有布局。完整CPU归因仍待有权限的会话；若继续已有GQA方案的16K验证，应另立范围、重新查重和做数值门禁，不与本次复制改动组合。
