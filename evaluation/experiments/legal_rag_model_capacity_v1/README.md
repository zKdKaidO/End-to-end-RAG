# Legal-RAG Model Capacity Ablation V1

This directory contains an experiment-only, controlled 2 x 2 comparison:

- A: `qwen3.5:9b` + frozen `legal-rag-v3`
- B: `qwen3.5:9b` + frozen E1 strict prompt
- C: `qwen3.5:27b` + frozen `legal-rag-v3`
- D: `qwen3.5:27b` + frozen E1 strict prompt

The experiment reuses byte-identical Block 5 context packages across all
conditions. It does not register a prompt, change a production profile, or
modify Blocks 1-5, parsers, SSE, retrieval, or database schema.

The experimental model is installed only in the local Ollama model store.
Production remains `qwen3.5:9b` with `legal-rag-v2`.

## Frozen inputs

- Evaluation V1 SHA-256: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- Evaluation V2 SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- Legal-RAG-V2 SHA-256: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`
- Legal-RAG-V3 SHA-256: `35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf`
- E1 strict SHA-256: `ae7d35a85fdd5db661ed43b198c9dc67c6c6e2513b5a8b3989f83c963bd83da2`

Generated result files are diagnostic evidence, not production configuration.

## Outcome

The comparison model failed the local operational-feasibility gate. The
default CUDA flash-attention runtime crashed twice; Ollama's supported
experiment-only no-flash path loaded but ran at 0.251 generated tokens/s with
266 MiB VRAM and 1.26 GiB RAM free. The quality matrix was therefore not run,
and the result is **INCONCLUSIVE**.
