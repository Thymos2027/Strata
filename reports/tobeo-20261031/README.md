# tobeo · 2026-10-31

- [870aedd9 GPU迟启动复现与观察扰动](qwen36-gpu-submit-870aedd9/README.md)：两轮16请求/四trace及126文件验收通过，新提交采集路径重复观察到迟启动；采集扰动仍显著，未确认无profiler或系统根因，下一项补标记off/on采集对照。

- [job标记off/on采集对照](qwen36-observer-control-870aedd9/README.md)：相同二进制/采集选项，16请求/八trace及106文件验收通过；off仍有同量级提交延迟，排除密集标记为必要条件，CUDA profiler与系统根因仍未区分。

- [总体状态复审](../RESEARCH_STATUS.md)：主线目标、已完成验证/发布、当前观察扰动分支及停止条件。
- [WPR GPU队列工具短探针](qwen36-wpr-queue-probe/README.md)：仅一次小型CUDA探针、独立命名ETW会话与本地解析，不加载大模型矩阵，数据语义须回读审查。
