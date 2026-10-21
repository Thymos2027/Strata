# Qwen3.6 Q4 下载记录

模型位置：`D:\Models\Qwen\Qwen3.6-35B-A3B-MTP-GGUF\Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`。权重仍在模型目录，本目录只存下载证据与脚本。

- [下载状态](qwen36-download-status.json)：已完成；22,853,663,008 字节，SHA-256 与项目固定值一致。
- [ModelScope 短测](modelscope-speed-probe.json)：同一文件的 Range 请求与速度记录，仅代表当时网络条件。
- [下载/续传脚本](download_qwen36.py)：使用固定 ModelScope revision，支持续传、重试与最终 SHA-256 校验；目标文件已存在时只验证。
- `qwen36-curl.log`、`qwen36-download.*.log`：历史下载日志。

脚本搬迁后，新的状态和日志写入本目录。大文件下载按全局偏好：优先 ModelScope，确认稳定后后台运行，不持续监控。
