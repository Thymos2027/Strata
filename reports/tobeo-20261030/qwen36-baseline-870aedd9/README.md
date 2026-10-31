# Qwen3.6 870aedd9新基线验收

2026-10-30。独立构建和数值/输出/实际布局门槛于北京时间20:09:49通过，用户返回后再次核对来源、32份静态证据、3608份ggml依赖、适配入口及DLL、参考结果与当前日常服务通过。该基线可供下一阶段迟启动调查；目前没有新的迟启动复现或根因结论。

## 固定配置与来源

精确revision `870aedd9e1ebe1c91f94da93b59af17729f6c5c0`，源码engine0.1.54。独立源码 `build-native-baseline/src-main-870aedd9` 干净，构建目录 `build-native-baseline/build-main-870aedd9-cuda132-sm120`。MSVC19.42、CUDA13.2.51/sm_120、Windows，硬件沿用i7-12700/RTX5060Ti16GB/128GB DDR4。ggml3cf03257从已校验归档重新解包到独立deps目录，3608份文件构建后及收尾复核均一致。

模型保持Qwen3.6-35B-A3B UD-Q4_K_XL，22,853,663,008字节，SHA-256 `55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1`。保持32K/chunk2048/显式63slots后冻结/7workers加host/MTP0/packed-MMQ/GPU0/EAGER/贪心，未组合copy或side-stream等改动。

[运行前协议](experiment-plan.md)、[执行程序](run_pipeline.py)、[最终汇总](summary.json)。完整build-results.json、validation-01/results.json及evidence-manifest.json保留本机，动态background-status.json和stdout/stderr不列入静态manifest。README属于封存后可更新的人类报告，初始32份清单不因文档收尾改变。

## 已通过

- CUDA原生构建及19项选定CTest；原17项外增加auto_cache_test/window_limits_test。Ninja无工作复查通过。配置约24.72秒、编译292.12秒、测试15.00秒。
- 两长度各64行×248320词表float32完整logits，每份63,569,920字节，全部有限且与旧46c基线同一强制历史的SHA逐位相同；不是仅核对top-1。
- 两轮×两长度，四条独立进程请求完整64-token输出与参考相同，fresh/0草稿/0换槽、实际63slots/chunk2048、MMQ生效、退出0。每进程同一1K/64预热，第二轮倒序。
- 新源码、exe/DLL/PDB、适配入口及其相邻匹配DLL、控制脚本/协议/参考结果指纹通过。没有覆盖旧46c源码、构建或实验数据。

## 无profiler基线观察

计时只作本轮参考，不是跨版本配对或优化收益。

| 请求 | 输入token | prefill ms | decode ms |
| --- | ---: | ---: | ---: |
| 1K，第1轮 | 1025 | 836.6 | 1791.2 |
| 16K，第1轮 | 16385 | 7885.7 | 2338.1 |
| 16K，第2轮 | 16385 | 8190.2 | 2442.3 |
| 1K，第2轮 | 1025 | 854.7 | 1767.9 |

16K第二轮prefill/decode较第一轮约高3.86%/4.46%；1K prefill约高2.16%、decode约低1.30%。两轮输出和布局一致，不能因此宣称延迟完全稳定。每条64输出，后续细分decode仍须区分prefill产生的首token和63次原生迭代。

HtoD前24.895941、后24.895785GB/s，漂移约0.00063%，带宽门槛通过。20:09:49恢复原Flash-Next IQ3_S，loaded=true，原配置SHA相同，restore_errors为空；回读时当前服务仍正常。

## 范围与下一步

本轮没有profiler、job插桩或迟启动单因素实验；未验证HIP/SYCL、独立CUDA Graph、MTP2、动态布局、并发及全量质量。旧46c迟启动现象不能直接当作870上的复现。后续先做[新提交复现与观察扰动协议](next-investigation-plan.md)，再根据真实结果收窄驱动/调度调查，不直接改等待策略或宣称WDDM根因。
