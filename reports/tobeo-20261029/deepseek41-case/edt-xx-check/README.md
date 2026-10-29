# edt-xx 建议核查：参数不通用，小对照未确认提交内存收益

2026-10-29。针对 [#4605 的 edt-xx 评论](https://github.com/Niko1221/Strata/issues/4605#issuecomment-6497383185)，已做参数解析检查、匹配构建源码核查和有保护的模型实测。**不能把评论中的 `--ple-io direct` 直接用于本案例；也没有证据说明近似开关修复了自动预算提交耗尽。** 本轮没有修改引擎、默认配置、分页文件或发布 GitHub 回复。

## 参数与源码

- 实际专用引擎为 0.1.52 / `a42cc3d7df70`，SHA-256 `e2f9fce53017dd8c2318e3a5ce969b4bd00b64589bdf32355e8d4d691962e610`。传 `--ple-io direct` 退出码 2，报 `unknown option --ple-io`；检查时没有传 pack、没有加载模型。见 [result.json](result.json) 及同目录 stdout/stderr。
- 通用 Qwen 引擎有 PLE 的这项参数。DeepSeek 专用引擎另有 Windows 环境变量 `DS4_EG_DIRECT=1`，针对 Engram-only 文件取消映射并尝试无缓冲读取。它不是同名参数，更不能将 PLE 整表驻留与 DeepSeek 文件映射当作同一种物理内存占用。按匹配构建的[源码](https://github.com/Niko1221/Strata/blob/a42cc3d7df70/src/dsv41/ds4_model.cu#L2590)及 [Engram reader](https://github.com/Niko1221/Strata/blob/a42cc3d7df70/src/dsv41/ds4_engram_io.hpp)确认；reader 在无法打开无缓冲句柄时有回退路径，因此只设变量也不等于验证了所有底层读取。
- 关于系统余量：匹配构建的自动 store [计算代码](https://github.com/Niko1221/Strata/blob/a42cc3d7df70/src/dsv41/ds4_model.cu#L4839)确实减去 **12 GB**；其 `ram_avail()` 在 Windows 返回 [`ullAvailPhys`](https://github.com/Niko1221/Strata/blob/a42cc3d7df70/src/dsv41/ds4_os.hpp#L573)。这是这段预算代码的静态事实，不是整个分配流程已完成根因证明。物理余量与 Windows commit 余量不同，不能由此推断“12 GB 被忽略”，也不能保证私有分配不会触及提交上限。原执行的事件 2004 才是本机提交耗尽的实测证据。

## 本次实测与停止原因

执行前保存 [experiment-plan.md](experiment-plan.md)，控制器为 [run_ab.py](run_ab.py)。原始 `run_case.py` 保持不变。

计划 A1→B1→B2→A2，每臂新进程。两臂都用原 2.25bpw、8K/full、GPU0、vision off、64 GB store、1536 MiB reserve；Engram row cache 显式固定 256 MB，verbose 开启。A 为 `DS4_EG_DIRECT=0`，B 为 1；变量仅作用于本次控制器及子进程。每臂先短预热，再用原案例相同输入测 1K/4K，各生成 64 tokens。保护线保持系统 commit 94% / 可用 RAM 4 GiB；不重试危险的自动 store。

实际到 B1 的 1K 请求即按协议停止：

- A1 完成预热、1K、4K；B1 完成预热、1K。两臂均为 5624 RAM slots、555 GPU experts，预热均返回 READY。相同数量不证明每个专家的实际放置完全相同。
- B1 日志明确记录 Engram 文件 `unmapped, its Engram rows read unbuffered`，对应开关进入了目标路径。未启用 `DS4_EG_CHECK`，本轮没有逐行比对 direct/buffered 读取字节。
- 两次 1K 请求均为 1038 输入 / 64 输出，cached_tokens/cache_n 均为 0，HTTP 完成；输出从小标题的 Records / Dataset 等位置开始不同，**没有通过逐字一致门槛**。这不证明数据损坏，也不能单凭一次对照归因于 direct。温度 0 / seed 0 同样不足以证明不同进程的整个计算必然逐字确定。
- 因此没有继续 B1-4K、B2 或 A2；没有计算等价加速比、确认质量等价或更改原案例结论。

下表均为十进制 GB，不是 GiB；只描述这一对观察，不能作统计结论：

| 指标 | A1：默认路径 | B1：direct |
|---|---:|---:|
| 加载期进程 private 峰值 | 83.345 | 83.127 |
| 预热后空闲系统 commit | 112.339 | 112.539 |
| 1K 请求系统 commit 峰值 | 112.693 | 112.848 |
| 1K 请求进程 private 峰值 | 83.525 | 83.309 |
| 1K 请求 RSS 峰值 | 59.612 | 59.797 |

进程 private 差约 0.22 GB，系统 commit 没有随之明显下降。背景进程、缓存和运行顺序均可能影响这一级别的差异；本轮未控制冷盘、未完成顺序对称重复，也未验证自动预算。**没有观察到可解释原先数十 GB 提交压力的大幅回收；不能宣称该开关普遍无效或已解决本机故障。**

完整记录在 [ab-01/results.json](ab-01/results.json)，提取数据在 [summary.json](summary.json)，各请求另有 response/resources 文件及原生引擎日志。结果中的 `phase=failed` 是预设输出门槛失败，不是引擎崩溃或第二次 OOM。22:09:59 控制器完成恢复，`restore_errors=[]`；随后实时 health 再核查 Qwen 已加载，日常配置 SHA 前后一致。离线重建了三个正式请求的 SSE 内容，检查 cache、采样错误、控制器/协议/冻结 helper 哈希，均与记录相符。

## 结论与后续边界

- [x] 参数适配、匹配版本源码核查、受保护小对照及恢复验收。
- [ ] 完整 ABBA、输出等价与性能收益验证：因 B1 输出身份门槛停止，不能计为完成。
- [ ] 自动 RAM-store 耗尽的修复验证：没有运行，更没有通过。

评论提供了检查“表读取方式”的有用线索，但当前不能据此替换已跑完 30 分钟的 64 GB store 配置，也不需要现在重跑长测。若继续研究 direct，应先用基线重复和读取字节核对区分输出变化，再决定是否另立性能协议；不能事后降低本次门槛拼出通过结果。自动预算问题仍留在 #4605，读取开关与预算修复分开判断。
