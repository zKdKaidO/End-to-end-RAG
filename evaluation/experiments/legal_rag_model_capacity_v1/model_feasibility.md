# Model feasibility

## Preflight

- GPU: NVIDIA GeForce RTX 5060 Ti, 16,311 MiB VRAM
- Initial free VRAM: 15,049 MiB
- System RAM: 31.79 GiB total, 21.60 GiB initially free
- Disk free: C: 50.93 GiB; A: 204.11 GiB
- Ollama: 0.32.15
- Initially installed models: `qwen3.5:9b` only
- Backend: 245 passed, 0 failed
- Frontend: 11 passed, 0 failed
- Frontend production build: PASS

## Same-family candidates

| Candidate | Architecture/capacity | Ollama quantization | Download | Feasibility assessment |
|---|---:|---|---:|---|
| `qwen3.5:27b` | dense, 27.8B | Q4_K_M | 17 GB | Selected; smallest clearly material same-family increase, fits disk and combined VRAM/RAM, with expected partial CPU placement |
| `qwen3.5:35b` | MoE, 35B total / 3B active | Q4_K_M | 24 GB | Rejected; less clean capacity isolation because active capacity is below the dense 9B baseline, larger download/runtime footprint |
| `qwen3.5:122b` | MoE, 122B total / 10B active | Q4_K_M | 81 GB | Rejected; exceeds C: free disk and is impractical for 32 GiB RAM |

## Selection

`qwen3.5:27b` is selected as the one comparison model. Ollama publishes it
as a 27.8B Q4_K_M model with a 17 GB artifact and a 256K context window. The
upstream Qwen model card describes a dense 27B language model. This is a 2.9x
parameter increase over the installed 9.7B baseline while keeping the same
Qwen3.5 family and Ollama provider path.

Full GPU residency is not expected because the quantized weights alone exceed
available VRAM. Partial CPU placement is therefore an explicit quantization and
placement confound. Actual processor split, memory, and throughput are measured
after loading; the experiment stops if that placement is operationally
impractical.

No prompt, context, generation setting, tokenizer setting, or production model
default is changed to make the model fit.

## Observed result

The normal Ollama 0.32.15 runtime failed twice during CUDA flash-attention
warmup with `shared object initialization failed` (`0xc0000409`). An isolated
experiment-only server with Ollama's supported flash-attention toggle disabled
did load and returned `OK`, while preserving the 32,768 context setting and
all generation settings.

Observed placement was 28% CPU / 72% GPU. The loaded process used 15,785 MiB
VRAM, left 266 MiB VRAM and 1.26 GiB system RAM free, and generated two tokens
in 7.957 seconds (0.251 tokens/s reported by the API calculation). This is not
operationally feasible for the required 200+ larger-model calls.

Decision: **LOCAL CAPACITY ABLATION NOT FEASIBLE**. The matrix was not run,
and no grounding-quality conclusion is drawn.
