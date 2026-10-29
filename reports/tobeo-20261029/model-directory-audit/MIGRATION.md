# 模型目录迁移完成

2026-10-29 23:41:51–23:46:42（Asia/Shanghai）。按用户授权执行，17 项同盘移动完成；110 个文件的完整 SHA-256 核验、DeepSeek pack-info/实际请求、日常 Qwen 恢复/实际请求均通过。

原始逐目录盘点是迁移前快照，见 [README.md](README.md)。迁移清单、每步日志、110 项校验与配置指纹在 [migration-01/results.json](migration-01/results.json)，补充独立核查在 [independent-verification.json](migration-01/independent-verification.json)。本轮只做文件布局与运行路径调整，没有修改引擎或量化格式。

## 当前布局

```text
D:\Models\
├─ Qwen\
│  ├─ Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S\
│  │  ├─ 两份 GGUF 及原下载标记
│  │  └─ strata-pack\                 ← 原 packs\iq3_s
│  ├─ Qwen3.8-Flash-Next-shared\
│  │  └─ mtp\                         ← tensors、量化 GGUF、rt 与来源清单
│  ├─ Qwen3.6-35B-A3B-MTP-GGUF\
│  │  ├─ 原有模型文件
│  │  └─ strata-pack\tokenizer\       ← 原 packs\qwen36-ud-q4_k_xl
│  └─ 其他原有 Qwen 模型目录
├─ DeepSeek\
│  ├─ deepseek-v4.1-flash-IST-DAS-2.25bpw\
│  │  └─ maya-ds4\
│  └─ deepseek-v4.1-flash-shared\
└─ Strata\
   ├─ components\                     ← 通用引擎及组件状态，原路径保留
   ├─ engine-dsv41\                   ← DeepSeek 专用引擎，原路径保留
   ├─ archive\2026-10-29-layout\
   │  ├─ deployment-backups\
   │  ├─ optimization-20261021\
   │  ├─ qwen38-download\             ← 原下载脚本、日志、COMPLETE、pycache
   │  └─ download-residue\            ← 原 work 工作区和 components partial
   └─ README.md
```

历史记录和下载残留采用归档保留；本轮没有因此释放对应磁盘空间。下载校验 sidecar 保留其原始内容，内部旧路径属于来源记录，不代表当前运行路径。两个已安装引擎版本及组件状态仍留在原处。

## 运行入口与修改

- `strata-iq3_s.json`：只替换权重、pack、tokenizer 和 MTP 的计划路径；其他参数与备份逐字段比较一致。原 `run-iq3_s.bat` 继续有效，日常地址仍为 `http://127.0.0.1:8080`。
- `strata-qwen36-q4.json`：只替换 tokenizer 路径。Qwen3.6 主模型未移动；本轮没有启动 Qwen3.6 做推理验收。
- 新建工作区根目录 `strata-deepseek41-ist-das-2.25bpw.json`：由成功 execution-03 配置生成，采用新模型路径及独立日志，保留 64 GB store、1536 MiB reserve、8K/full/text。DeepSeek pack 的 `ds4.txt` 仅修改 `model_dir`；共享文件相对层级不变。
- 原运行记录、报告、控制器保持历史状态，特别是冻结的 `run_case.py`。后续使用新配置，不能直接重跑带旧绝对路径的历史脚本。

验收后的最终运行配置将日志放在工作区 `strata-deepseek41-ist-das-2.25bpw.log`，避免后续运行覆盖迁移证据目录的引擎日志；推理设置与已验收配置相同。仅此日志字段的变更及最终配置 SHA 另存 [runtime-config-finalization.json](migration-01/runtime-config-finalization.json)，`results.json` 保留验收时的指纹。

需要使用 DeepSeek 时，应先卸载日常 Qwen，释放单卡，再从仓库运行：

```powershell
.\.venv\Scripts\python.exe -u -m serve.server --engine strata --config .\strata-deepseek41-ist-das-2.25bpw.json --host 127.0.0.1 --port 8081
```

本轮只为验收临时启动 DeepSeek，已卸载并停止其测试服务器，当前 GPU 留给日常 Qwen。

## 验证范围

- 110/110 个移动文件均做完整 SHA-256：七份 DeepSeek 配套/权重使用此前全量校验值，两份 Qwen 权重使用下载记录中的固定哈希，31 份 MTP 原始张量使用 manifest；其他文件使用迁移前新算的哈希。唯一预期变化为 DeepSeek `ds4.txt` 的路径文字，另按修改后的预期字节核对。
- 每个移动文件还核对长度和 Windows 文件标识，确认是同盘移动；17 个旧来源均不再存在、目标均存在。空 `packs` 容器已移除，所有实际文件保留。
- 新路径下 DeepSeek 专用引擎 `--pack-info` 退出 0；真实加载成功，HTTP 问法国首都回答 Paris。原始响应和资源记录在 [deepseek-validation](migration-01/deepseek-validation/results.json)。没有重跑原 30 分钟实验或作性能比较。
- 日常服务用新配置重启；health 显示正确模型与 loaded=true，真实请求回答 Paris。其 native timing 的 draft_n=3、draft_n_accepted=3，确认这次请求实际走过 MTP，而非仅检查路径存在。见 [qwen-response.json](migration-01/qwen-response.json)。这不是 MTP 性能或质量评估。
- 独立比较两份现有运行配置与迁移前备份，确认只出现计划的路径替换；冻结案例控制器哈希仍与前次记录一致。

## 回退材料

迁移前两份配置和原 DeepSeek ds4.txt 在 [config-backup](migration-01/config-backup/strata-iq3_s.json)。逐项来源/目标、原长度、文件标识、预期 SHA 和校验来源均已记录。若需回退，应先卸载并停止使用这些路径的服务，再按 journal 逆序恢复模型及 pack，最后还原配置并重新加载；不要只恢复旧配置而保留新文件位置。归档中的旧下载脚本含历史路径，不应未经修改直接重跑。
