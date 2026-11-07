# Can taishan run DeepSeek V4.1-Flash?

Reviewed 2026-11-05. This is a read-only feasibility assessment, not a V4.1 load or speed test.

## Model identity

| Deployment | Model | Weights and runtime |
| --- | --- | --- |
| Local Windows Strata | DeepSeek V4.1-Flash-1017 | ISTA-DASLab IQ2_XS, 2.25 bpw GGUF; Strata DeepSeek engine |
| taishan today | DeepSeek V4-Flash | W8A8 NPU weights plus MXFP4 CPU experts; SGLang/KTransformers |

These are different models. DeepSeek's [V4-Flash model card](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash) reports about 284B total / 13B active parameters. The [V4.1-Flash model card](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash) and [vLLM Ascend V4.1 guide](https://docs.vllm.ai/projects/ascend/en/latest/tutorials/models/DeepSeek-V4.1-Flash.html) describe a 40-layer CED model, 552B backbone plus approximately 196B Engram parameters, and 8B / 16B active parameters in prefill / decode. The taishan V4 timing in [REVIEW.md](REVIEW.md) cannot be attributed to V4.1.

## What the machine and software can do today

Read-only inspection on taishan found two Ascend 910B4-1 NPUs with 64 GiB each, 502 GiB system RAM reported by Linux, approximately 349 GiB available while the V4 service was running, and about 60 TiB free on `/data`. One NPU serves V4 and the other was idle. `/data/llm` contained V4 and V4-W8A8 weights, but no V4.1 weights in the inspected model and deployment paths. The installed SGLang/KTransformers model code found in `/data/deploy/dsv4-20261104` has V4 support, with no V4.1 implementation identified in that checkout. The current V4 service cannot accept a V4.1 weight directory as a drop-in replacement.

Strata's [documented V4.1 backends](../../../docs/AI_REFERENCE.md) do not include Ascend. Its [CMake configuration](../../../CMakeLists.txt) places the V4.1 serving path behind CUDA/HIP. Therefore the existing Strata build cannot use taishan's 910B NPUs for V4.1.

There is an Ascend route in [vLLM Ascend's V4.1 deployment guide](https://docs.vllm.ai/projects/ascend/en/latest/tutorials/models/DeepSeek-V4.1-Flash.html), but its documented W8A8 configurations require either one A3 server with eight 128 GB NPUs or two A2 servers with eight 64 GB NPUs each. No two-NPU configuration is documented there. Taishan's two 64 GiB cards are below those validated configurations, so this is not an established plug-and-play route on this machine.

## Plausible experiment, not yet validated

The [ISTA-DASLab V4.1-Flash-1017 GGUF](https://modelscope.cn/models/ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF) offers an IQ2_XXS 2.00 bpw pack. Its [file list and llama.cpp instructions](https://huggingface.co/ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF) report 138.24 GB of backbone weights plus a 110.60 GB shared Engram file. The Engram table can remain memory-mapped and be read sparsely. Given taishan's free RAM and disk, a recent llama.cpp build with CPU-only inference is a plausible **functional trial** at a short context. The model publisher says upstream llama.cpp b11870 or newer supports V4.1, but this exact ARM64 Kunpeng system has not been tested here. Correctness, startup memory, prefill, and decode speed remain unknown. Its current V4 speed must not be used to predict them.

The [llama.cpp CANN backend support table](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/CANN.md) lists DeepSeek models as unsupported and does not list these IQ2 quantization types for 910B. Therefore a two-card 910B GGUF acceleration path is not established by that documentation. A CPU-only trial would need separate model files and an updated runtime; it has not been started, and the running V4 service was left intact.
