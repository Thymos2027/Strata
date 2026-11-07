# v0.2.9 更新审查

2026-11-01，只读刷新上游引用并核对[正式发布说明](https://github.com/Niko1221/Strata/releases/tag/v0.2.9)及本地Git差异。未合并、安装、构建或运行模型。

- 正式发布于北京时间2026-10-31 16:02:32。应用0.2.9，Control和引擎包0.1.55。
- v0.2.8标签为870aedd9；v0.2.9标签为c62d5e3a。两标签间169个提交，283文件变更。标签注释说明通用引擎/SYCL包构建来源为99866a47，不能将所有发布资产笼统当成c62d5e3a编译。
- 主要平台收益来自Linux NVIDIA并发和Qwen3.8 GDN、Linux gfx12 GDN、Windows Strix Halo prompt以及Intel Arc。它们不是本机Windows/RTX5060Ti/Qwen3.6实测收益。
- Qwen3.6专属文件的差异为预热token数受context限制，并在后续短prompt/decode探针前reset，修复小context的KV越界；没有据此声称正常32K工况提速或原迟启动现象修复。
- Windows相关修复包括非UTF-8/GBK子进程输出、layer-major prefill无mapped blob时回退读取源；发布说明明确后一条仅编译、未在Windows运行。
- 服务层修复代码块中的伪工具调用、历史工具识别、DONE后断开误报取消；聊天长输出减少重复渲染。
- DeepSeek新增Unsloth UD-IQ1_S/M选项，默认模型集不变；支持ISTA重新发布的四分片及六分片布局。Windows上的Unsloth一比特集及CUDA13 DeepSeek包没有发布方端到端模型验证。
- 发布说明仍列出DeepSeek temperature=0的专家缓存相关输出不重复，以及Strix Halo UD-Q4_K_XL首请求可能停顿等限制；这些不是本机问题的确认或复现。

本次仅发布说明及源码静态审查，没有新的测试或性能结论。已有870aedd9基线和报告继续按原revision归档；不自动重启已经收尾的诊断分支。
