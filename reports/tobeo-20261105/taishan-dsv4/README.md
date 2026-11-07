# taishan DeepSeek V4-Flash speed probe

Started 2026-11-05 (Asia/Shanghai) after the user authorized requests to the existing remote service. The client runs locally; it does not change remote files, settings, or processes.

- Endpoint: `http://192.168.137.11:18080`, checked for the `DeepSeek-V4-Flash-W8A8` model before requests.
- Workload: one short warmup, then three requests each at about 1K and 4K input tokens, alternating order; 256 output tokens, greedy sampling, EOS ignored.
- The local `/tokenize` endpoint supplies the actual prompt count. The benchmark uses streaming `/generate` responses and records first content time, full response time, output count, and cache count.
- `prefill_est_tok_s = input_tokens / time_to_first_content`. This includes HTTP and the first decode token. `decode_est_tok_s = (output_tokens - 1) / (end_time - first_content_time)`. These are client-side estimates, not isolated engine timers.
- The test leaves the existing 8K context, 512-token prefill chunk, 32 NPU experts per layer, and single-request server settings intact. Do not compare directly with the Windows Strata engine results as a controlled engine A/B.

The reviewed completion state is in [status.json](status.json), and the raw per-request measurements are in [results.jsonl](results.jsonl). The process ID and execution logs remain local run artifacts.

The run completed and was reviewed on 2026-11-05. See [REVIEW.md](REVIEW.md) for the validated measurements and limits.
