# taishan DeepSeek V4-Flash speed probe: reviewed result

**Model identity:** The local Windows Strata result is **DeepSeek V4.1-Flash-1017**, using the ISTA-DASLab 2.25 bpw GGUF. The taishan result in this report is **DeepSeek V4-Flash**, using its W8A8 NPU weights and MXFP4 CPU experts under SGLang/KTransformers. These are different model generations and different serving stacks. The 15.41 tok/s taishan decode result is **V4 only**; it is not a V4.1 measurement. See [V4.1 feasibility on taishan](V41_FEASIBILITY.md).

Reviewed 2026-11-05, Asia/Shanghai. `status.json` says `completed` (7/7); the local launcher process exited and `stderr.log` is empty. One 32-token warmup was excluded. The six formal requests finished with 256/256 output tokens, `finish_reason=length`, `cached_tokens=0`, and matching tokenizer/API input counts. Every SSE stream ended with `[DONE]`. The serving endpoint still reported the intended `DeepSeek-V4-Flash-W8A8` model afterward; `npu-smi info` showed both cards healthy and the scheduler on one Ascend 910B4-1.

The machine has dual Kunpeng 920 CPUs, 512 GB installed system memory (502 GiB reported), and two 64 GiB Ascend 910B4-1 cards. This service uses one card. Its current SGLang/KTransformers setup has 8K configured context, 512-token prefill chunks, 32 NPU-resident experts per layer, W8A8 NPU weights and MXFP4 CPU experts. See the remote deployment record at `/data/deploy/dsv4-20261104/README.md`. Neither the service nor remote files were modified for this test.

| Actual input / output | Repeats | First content, median (range) | Full response, median (range) | Input / first-content estimate, median (range) | Output after first content, median (range) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 983 / 256 tokens | 3 | 13.718 s (13.703–13.719) | 30.203 s (30.156–30.453) | 71.66 tok/s (71.65–71.74) | 15.47 tok/s (15.22–15.51) |
| 4,099 / 256 tokens | 3 | 56.781 s (56.781–56.938) | 73.328 s (73.313–73.532) | 72.19 tok/s (71.99–72.19) | 15.41 tok/s (15.37–15.42) |

The prefill column is `actual input tokens / time to first nonempty streamed text`. It includes client transport, server queue/tokenization, prefill, and first-token decode, so it is **not isolated engine prefill throughput**. The decode column is `(256 - 1) / (last stream event - first content event)`; it includes SSE transport and is an end-to-end single-request estimate. Both are directly comparable between the two lengths in this run, but the other three models' historical Strata API timings are different measurement boundaries and workloads.

## Four-model speed context

| Model and machine | About 4K input | Decode |
| --- | ---: | ---: |
| Qwen3.8-Flash-Next IQ3_S, Windows RTX 5060 Ti, Strata 0.1.46 | 1,255 tok/s engine prompt timing | 58.9 tok/s, short chat |
| Qwen3.6-35B-A3B UD-Q4_K_XL, same machine, Strata 0.1.46 | 1,965 tok/s engine prompt timing | 42.6 tok/s, short chat |
| DeepSeek V4.1-Flash IST-DAS 2.25 bpw, same machine, Strata DeepSeek 0.1.52 | 213 tok/s API prompt timing | 7.2 tok/s, 4K input |
| DeepSeek V4-Flash W8A8 + MXFP4, taishan Ascend 910B4-1, SGLang/KTransformers | 72.19 tok/s client first-content estimate | 15.41 tok/s client streaming estimate, 4K input |

The rows are historical observations from different models, workloads, engines and timing boundaries. They describe the observed deployment experience; they are not a controlled architecture or quantization comparison. DeepSeek V4-Flash and V4.1-Flash are separate models.

The prompts repeat a synthetic English sentence and ask for an explanation. Greedy sampling with `ignore_eos=true` forced 256 tokens. This is a speed probe, not a quality or quantization-loss evaluation. Three repeats of one prompt per length cannot establish typical natural-task performance or long-run stability. No 8K input, concurrency, second NPU, or alternative expert placement was tested. The 32-token warmup was slower (983-token first content 16.656 s) and is not included above.

Raw timing and API metadata: [results.jsonl](results.jsonl). Client implementation: [bench.py](bench.py). Completion state: [status.json](status.json). Existing Windows comparison sources: [Flash-Next](../../tobeo-20261021/REPORT.md), [Qwen3.6](../../tobeo-20261021/qwen36-q4/README.md), and [DeepSeek V4.1](../../tobeo-20261029/deepseek41-case/REPORT.md).
