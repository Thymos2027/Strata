# tobeo · 2026-10-24

本日继续定位 RTX 5060 Ti 主机/GPU 传输异常，并在用户授权下重启日常 Strata 服务。报告保留实测范围和未确认项，不把时间相关性写成已证实根因。

- [TDR 后的主机/GPU 传输异常定位](pcie-root-cause/README.md)：整理 TDR 时间线，在模型卸载后独立测量 H2D、D2H、D2D、CPU memcpy 和 mapped-host 读取；传输异常仍存在。
- [日常 Strata 服务重启验证](strata-restart/README.md)：服务与遥测恢复，启动 HtoD 仍约 1.7 GB/s，未恢复历史约 25 GB/s。
- [HtoD 低吞吐的上游检索](strata-restart/github-related-issues.md)：记录相关 issue、可迁移线索及不能直接套用的结论。

编译产物、完整设备/事件 XML、运行日志、运行时指标和可能包含本机标识的文件仅保留在本机，由各目录 `.gitignore` 排除。可公开内容包括报告、复现源码和经过筛选的小型结果。
