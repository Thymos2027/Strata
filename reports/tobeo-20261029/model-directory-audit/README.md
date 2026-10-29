# D:\Models\Strata 目录盘点

**后续状态：2026-10-29 已按用户授权完成整理，当前布局和验收见 [MIGRATION.md](MIGRATION.md)。下文及 inventory.json 是迁移前快照。**

2026-10-29。只读查看目录、文件大小、下载脚本、MTP 清单、pack 和实际运行配置。没有迁移、删除或修改模型及运行配置。[inventory.json](inventory.json) 保存本次逐文件清单。大小均为十进制 GB、逻辑文件长度，不等于实际占用空间；没有重新计算大文件哈希，也没有完成所有历史脚本的依赖审计。

目前这里混放模型资产、引擎、转换产物和历史记录。建议模型资产按家族归到 `D:\Models\Qwen` / `D:\Models\DeepSeek`，Strata 下保留引擎和组件管理数据。

| 现有目录 | 大小 GB | 实际用途与依据 | 建议 |
|---|---:|---|---|
| `IQ3_S` | 83.618 | Qwen3.8 Flash-Next IQ3_S 两份权重及 `.done` 标记；日常配置 `strata-iq3_s.json` 的 native/ple-gguf 正在引用 | 迁至 `Qwen\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S` |
| `mtp` | 6.928 | Qwen3.8 的 MTP 草稿层，日常 `--spec 4 --mtp ...\mtp\rt` 使用它；不是 DeepSeek 文件或通用缓存 | 整体归入 `Qwen\Qwen3.8-Flash-Next-shared\mtp`，先保留来源、量化产物和运行文件 |
| `packs` | 1.558 | `iq3_s` 含 dense.bin、专家索引、转换记录及 tokenizer；`qwen36-ud-q4_k_xl` 当前只有 tokenizer，Qwen3.6 配置仍引用它 | 按各自模型拆分，建议放对应模型目录的 `strata-pack` 子目录 |
| `deepseek-v4.1-flash-IST-DAS-2.25bpw` | 155.235 | 四份 IQ2_XS 主权重、下载校验记录及已生成的 `maya-ds4` pack | 原目录名整体移入 `DeepSeek`，修正 pack 的绝对引用 |
| `deepseek-v4.1-flash-shared` | 118.578 | Engram 表约 110.60 GB、DSpark 约 7.98 GB、约 5.8 MB 的配套元数据 GGUF及校验记录；该小 GGUF 不是完整 Q8 模型 | 与主权重目录一起移入 `DeepSeek`，保留两者相对层级 |
| `components` | 1.900 | 通用 Strata 引擎 0.1.52、旧 0.1.46、DLL，以及 `.updates` 状态/下载残留；启动 bat 通过 STRATA_COMPONENTS_DIR 指向这里 | 保留原路径和组件内部结构；旧引擎作回退。更新残留单独核实后处理 |
| `engine-dsv41` | 0.626 | 已验收的 DeepSeek 专用 0.1.52 引擎、DLL、BUILD/组件信息 | 暂保留，避免与模型迁移同时改变引擎路径 |
| `engine-dsv41.work` | 0.133 | 原专用引擎下载工作区，含 133,169,152-byte 未完成包；正式引擎已另行安装验收 | 候选下载残留；确认无使用者后归档或清理 |
| `deployment-backups` | <0.001 | 10-21 升级前配置、启动脚本、引擎身份、日志及升级后状态 | 保留为历史备份，可统一放 Strata 的 archive 子目录 |
| `optimization-20261021` | <0.001 | 两份历史 server stdout/stderr 日志 | 归档到同一历史区 |
| `__pycache__` | <0.001 | 两个下载脚本产生的 Python 字节码 | 可重建缓存，列为清理候选 |

## mtp 为什么不能直接当缓存删掉

三层文件的关系可以从本机清单与 `tools/mtp_pack.py`、`tools/mtp_rt.py` 对应确认：

1. `tensors/`：31 个原始 checkpoint 张量，约 5.214 GB；manifest 记录来源分片、字节范围、哈希。它们是转换来源，不是当前配置直接指定的运行目录。
2. `mtp-q2_0.gguf`：约 0.889 GB 的量化中间产物，旁边有转换报告。
3. `rt/`：约 0.824 GB 的引擎运行文件，包括 dense.bin、experts.bin、dense.txt、draft_vocab.bin。**当前日常配置直接引用这一层。**

所以它属于 Qwen3.8 模型配套资产。建议放 Qwen3.8 的 shared 目录，而非让 `mtp` 继续以不带模型名称的方式悬在 Strata 根目录。原始张量和 GGUF 可以在迁移验收后再讨论归档，当前不建议删除。

## 根目录散文件

- `COMPLETE.json`：2026-10-12 Qwen3.8 两份权重的大小/SHA-256及 MTP 验证完成记录，属于下载来源证据，不是所有 Strata 数据的总清单。随 Qwen3.8 下载记录归档。
- `download_all.py`、`download_iq3s.py`：当时下载 Qwen3.8 主权重与 MTP 的脚本，含旧路径；适合归档，不应在迁移后未经修订直接重跑。
- `download.log`、`download.err.log`：上述历史下载日志，随脚本归档。
- DeepSeek 目录中的 `.verified.json` 是校验来源记录；`.part.src`、`.part.chunks` 是续传旁文件，不能只凭后缀判定当前失败下载，也不应与正式权重混同。暂保留，迁移验收后再评估清理。

## 执行时的边界

已确认的运行引用包括 `strata-iq3_s.json` 中的两个 GGUF、pack、tokenizer、MTP 路径，`strata-qwen36-q4.json` 的 tokenizer，以及 DeepSeek `maya-ds4/ds4.txt` 中的 model_dir。两份启动 bat 另指向现有 components；这些引擎引用可保持原位。专家 profile 当前在源码工作区 data 目录，本轮不纳入模型搬迁。

推荐顺序是：保存配置与迁移映射 → 卸载正在使用的 Qwen → 在同一 D 盘内移动模型和配套资产 → 修正有效运行引用 → 核对文件、pack 并做短加载/推理 → 恢复日常服务 → 最后处理下载残留和历史归档。历史测试证据不改写旧路径，另记迁移关系。全量引用搜索、目标路径验证、文件完整性和运行验收仍属于迁移任务，不把本次盘点当作迁移完成。
