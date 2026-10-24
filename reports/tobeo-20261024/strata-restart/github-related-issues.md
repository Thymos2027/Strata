# HtoD 低吞吐的上游检索

2026-10-24，通过 GitHub 连接器检索 open/closed issues：`1.7 GB/s`、`Gen1`、`PCIe slow`、`1.7 probe`、`5060 bandwidth`、`TDR`、`HtoD`。读取 #485、#2137、#2453 正文与全部返回评论。未发布 issue 或评论，未改运行配置。

未找到可确认与本机“Windows RTX 5060 Ti、约 25 降至 1.7 GB/s、服务重启仍慢”完全同因的报告；关键词检索不保证穷尽评论及附件。

- [#485：PCIe probe can read ~3x low](https://github.com/Niko1221/Strata/issues/485)。RTX A3000 Laptop、engine 0.1.34：同机不同启动 18.5 / 6.9 / 5.8 GB/s，低探针值降低 pcie_frac。维护者[评论](https://github.com/Niko1221/Strata/issues/485#issuecomment-5960251984)称 0.1.37 改为四次 256-MiB burst 取最快，并平滑分配比例；状态 closed/completed。本机 0.1.46 已记录四次均 1.7，且此前长时间独立 probe 和卸载模型后仍低，不符合仅一次启动探针被扰动的简单解释。
- [#2137：Monitor 混淆 capability 与 current generation](https://github.com/Niko1221/Strata/issues/2137)。GTX 1080 Ti/Linux 在持续负载下 Gen1×16，峰值约 3191 MB/s，页面却显示 Gen3。作者[更正](https://github.com/Niko1221/Strata/issues/2137#issuecomment-6128241799)指出遗留 Linux 驱动参数阻止重训练；不能迁移为本机 Windows 根因或修复步骤。最后维护者评论为 tracker reset，closed/not_planned 不代表已修复；另有 #3158 渲染修复提案，未在本轮核实其合并状态。
- [#2453：Windows RTX 5060 Ti 升级后 decode 降速](https://github.com/Niko1221/Strata/issues/2453)。69 降至 55–58 tok/s，但作者明确负载时仍是 Gen5×8；后续旧 server/config 搭配新 engine 的聊天观察恢复到 66.7–69.6 tok/s。不是已证实的 HtoD 低吞吐同案。最后因 tracker reset 关闭，不能称已确定 engine regression 或已修复。
- [#3681：SYCL host memory fragmentation](https://github.com/Niko1221/Strata/issues/3681)。检索正文显示 Arc Pro B70 同版本同链路的 pinned H→D 因宿主内存状态从 27.5 变为 11.0 / 17.6 GB/s，decode 随之变化。仅作不同后端的排查线索；本轮未读其评论，不能据此诊断 CUDA/Windows。

本机结论保持：确有重复测得的有效 HtoD 低吞吐，根因尚未确定；不能将上游案例的不同平台根因套用到本机。
