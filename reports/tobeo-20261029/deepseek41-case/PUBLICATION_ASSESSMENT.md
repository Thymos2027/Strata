# 社区反馈建议：先报告Windows提交内存边界

后续执行：用户授权后已发布[#4605](https://github.com/Niko1221/Strata/issues/4605)，见[发布记录](PUBLICATION.md)。发布前已将下文拟题中的固定4GB假设修正为初始4GB/上限8GB并补核原始事件系统commit字段；以下保留发布前评估，不是当前未发布状态。

2026-10-29，使用案例完成后的在线查重与投稿评估。仅只读GitHub查询，未发布issue/comment/PR，未上传证据。

## 建议

优先一个聚焦的`[Engine]`问题报告，说明专用DeepSeek0.1.52在本机自动RAM-store加载时出现Windows提交内存不足；引用已有Windows提交内存讨论，并把成功手动配置和精简性能结果作为同一报告的证据。暂不直接开引擎修复PR或纯benchmark PR。

可用标题：`[Engine] DeepSeek auto RAM-store loading exhausts Windows commit headroom (128 GB RAM, 4 GB pagefile)`。

问题请求应是：请维护者确认DeepSeek专用后端的自动store预算是否需要考虑可用commit、加载后的分配余量或更明确的启动告警。不能预先宣布某行源码是已证实根因，也不要求将64GB设置成所有128GB机器的默认值。

## 为什么值得分享

1. 有具体的用户影响和Windows原生证据。自动store101.3GB时出现资源耗尽事件2004，事件记录DeepSeek提交118,554,161,152 bytes，宿主也报告分页文件不足/分配失败，最终显式终止测试树恢复。不是只有静态推测。
2. 有可运行的实际配置边界。80GB store/1536MiB reserve触及自定义94%提交保护；64GB/1536MiB完成九次功能请求、六条性能及30分44秒36条连续请求。无需换量化、改分页文件或重编译。64GB是这次通过的设置，不是最大安全值或全平台解决方案。
3. 补充Windows、单张5060Ti16GB、128GB DDR4、2.25bpw/full的数据：短矩阵decode约7.1–7.2tok/s，首内容约9.7/19.3秒，以及实际存储读取、提交峰值与后段变慢。可以帮助别人评估使用成本。

## 查重与当前投稿信号

- [#1607](https://github.com/Niko1221/Strata/issues/1607)是较早的Qwen通用引擎Windows commit问题，当前closed。维护者[说明0.1.42曾对conversation/checkpoint admission增加commit限制](https://github.com/Niko1221/Strata/issues/1607#issuecomment-6099632342)，并在[关闭说明](https://github.com/Niko1221/Strata/issues/1607#issuecomment-6156153074)允许新证据补原讨论或新建issue链接它。本次是独立DeepSeek引擎的加载/store路径，不能声称复现了相同的Qwen checkpoint故障；建议新建一个范围明确的DeepSeek报告并链接该背景，或先在原帖说明不同后端并请维护者分流。
- [#4362](https://github.com/Niko1221/Strata/pull/4362)当前open/draft，处理离散GPU被当作UMA而在大上下文下扣掉过多RAM store。它的验证是Linux双卡、262K上下文，未测Windows。本次8K没有该>16K context扣减项，问题方向也不同，不能作为该PR的验证或反例，更不应把它作为重复修复入口。
- [#4426](https://github.com/Niko1221/Strata/pull/4426)已有16GB RTX4090 Laptop、Linux、2.25/full/DSpark等更大矩阵。不能把本机案例包装成“首次16GB显卡运行DeepSeek”。本机新增信息在Windows提交预算及具体部署边界。
- 维护者今天在[#4426关闭评论](https://github.com/Niko1221/Strata/pull/4426#issuecomment-6495866736)说明正准备社区benchmark网站，关闭PR但保留数据；同样说明见[#4074评论](https://github.com/Niko1221/Strata/issues/4074#issuecomment-6495687538)。因此虽然本地贡献文档允许results-only PR，当前不建议未沟通就新增一份纯成绩PR。证据可先放用户fork的独立目录或随issue附件提供，再由维护者决定收录方式。

本次检索覆盖开放/关闭的DeepSeek Windows、pagefile、commit limit、RAM store、128GB及5060相关issue/PR，并读取上述正文/评论。没有确认同一DeepSeek自动store加载故障的线程；这不是穷尽所有讨论的保证，实际发布前仍需复查。

## 发布时必须保留的边界

- 首轮没有捕获到引擎自行崩溃的退出码；是系统资源压力后人工终止。不能写成引擎已证实crash、0xC0000409或死锁，也没有完整系统commit临界时序。
- 80GB是控制器主动保护停止，不能写成第二次OOM。64GB同时使用1536MiB reserve；默认到成功并非只改一个变量的因果A/B，不能宣布仅降低store治愈了所有问题。
- 后段英文1K完整耗时中位增加约15.6%，但自由生成输出不同、温度/频率未采集；只作为性能边界，不另开“内存泄漏”“热降频”或“性能回归”issue。
- 两条功能汇总messages有可变列表归档差异，公开包应取独立response文件的实际request并解释，不直接上传整个汇总当作精确输入；原始结果不改写。
- 当前脚本依赖本机路径和历史telemetry模块。公开前需制作英文精简正文、脱敏配置/日志、事件摘要、确切输入和逐次数据，明确原实跑脚本与事后便携整理的验证范围。不要上传模型、pack、422MB引擎包或整份私人目录。

可将完整案例放入fork的`bench/results/2026-10-29-community-rtx5060ti-deepseek41-windows/`作为证据，先不对上游发PR。Issue以自动预算的用户问题为主，附成功配置及完整报告链接；是否独立收录benchmark再听维护者意见。
