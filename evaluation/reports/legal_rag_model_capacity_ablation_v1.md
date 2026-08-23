# Legal-RAG Model Capacity Ablation V1

Status: **INCONCLUSIVE — LOCAL CAPACITY ABLATION NOT FEASIBLE**

## Integrity

All frozen hashes matched:

- Evaluation V1: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- Evaluation V2: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- Legal-RAG-V2: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`
- Legal-RAG-V3: `35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf`
- E1 strict: `ae7d35a85fdd5db661ed43b198c9dc67c6c6e2513b5a8b3989f83c963bd83da2`

Production remained `qwen3.5:9b` with `legal-rag-v2`.

## Preflight

- GPU: NVIDIA GeForce RTX 5060 Ti, 16,311 MiB VRAM
- RAM: 31.79 GiB
- Disk free before download: C: 50.93 GiB; A: 204.11 GiB
- Ollama: 0.32.15
- Backend: 245 passed, 0 failed, 8 warnings, 93.20 seconds
- Frontend: 11 passed, 0 failed
- Frontend production build: PASS

## Model selection

`qwen3.5:27b` Q4_K_M was the one selected comparison model. Ollama
reports 27.8B parameters and a 17 GB artifact. It is the smallest clearly
material dense same-family increase over the installed 9.7B Q4_K_M baseline.

The 35B option was rejected because it is a 35B-total/3B-active MoE and is a
less clean capacity comparison. The 122B option was rejected as locally
impractical. No unrelated model family was substituted.

## Load feasibility

The normal Ollama runtime was attempted twice with the exact frozen context
limit and generation settings. Both attempts failed during warmup:

`CUDA error: shared object initialization failed` (`0xc0000409`).

Ollama had automatically selected 49/66 layers for GPU placement, with
11,069.09 MiB of model buffers on CUDA, 4,402.20 MiB on CPU, and a 2,048 MiB
KV cache.

An isolated Ollama server on port 11435 used Ollama's supported
`OLLAMA_FLASH_ATTENTION=false` diagnostic path. This did not alter production
and was applied only to test whether the model could execute without the
crashing kernel. The smoke generation succeeded and returned `OK`, but the
observed resource profile was not practical:

| Signal | Observation |
|---|---:|
| Processor placement | 28% CPU / 72% GPU |
| Loaded model size | 25 GB |
| VRAM used/free | 15,785 / 266 MiB |
| Free system RAM | 1.26 GiB |
| Load time | 34.051 s |
| Prompt evaluation | 19 tokens in 7.729 s |
| Generation | 2 tokens in 7.957 s |
| End-to-end smoke | 51.915 s |
| Reported generation throughput | 0.251 tokens/s |

The required experiment needs more than 200 larger-model calls, many with
thousands of input tokens and up to 512 output tokens. Running it at this
placement would take days and would leave negligible memory headroom. This is
the explicit "excessive CPU offload / operationally impractical" stop
condition—not an arbitrary latency gate.

No context size, Block 5 evidence, output limit, sampling setting, thinking
setting, GPU layer count, prompt, or quantization was changed to force a pass.

## Frozen context preparation

All 65 frozen V2 Block 5 packages were reproduced and fingerprinted before
generation. The planned A/B/C/D inputs are byte-identical. Since generation
was stopped at feasibility, these fingerprints establish experiment readiness,
not a completed capacity comparison.

## Quality matrix

| Condition | Status |
|---|---|
| A — 9B + V3 | NOT RUN |
| B — 9B + E1 | NOT RUN |
| C — 27B + V3 | NOT RUN |
| D — 27B + E1 | NOT RUN |

Therefore no targeted, pure-capacity, capacity-by-contract, full-V2,
multi-evidence, synthetic, or safety quality metric is reported. Inferring a
quality effect from a two-token smoke test would be invalid.

## Root-cause decision

**INCONCLUSIVE.** This run does not support or refute model capacity as the
primary grounding bottleneck. The controlled comparison was blocked by local
deployment feasibility before quality measurement.

The missing-evidence cases remain separated from Block 6 capacity:

- `v2_social_effective_transition`: effective-date evidence absent
- `v2_bank_actual_capital_formula`: expected formula source absent
- `v2_social_applicable_groups`: required groups absent

## Next architecture decision

**CONDUCT SECOND CAPACITY ABLATION.** Run the same frozen 2 x 2 design through
a controlled external provider or on hardware with enough VRAM/RAM to execute
Qwen3.5-27B without the observed CPU-offload and memory-pressure failure. Do
not promote a model or redesign Block 6 based on this infeasible local run.

The downloaded 27B artifact remains experimental-only. It was unloaded, the
temporary no-flash server was stopped, and production defaults were untouched.

## Final regression

- Backend: 245 passed, 0 failed, 8 warnings, 93.73 seconds
- Frontend: 11 passed, 0 failed
- Frontend production build: PASS
