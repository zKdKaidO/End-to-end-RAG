# Block 6 Phase 02 — Generation profile and schemas

Implemented immutable server-owned `GenerationProfile`, minimal `AnswerRequest`, `GenerationResult`, `Citation`, nullable `Usage`, status/citation enums, and typed generation errors.

Profile: Ollama / `qwen3.5:9b`, `Qwen/Qwen3.5-9B`, 32,768 operational context limit, 4,096 evidence budget, 512 output reserve, 32-token safety margin, thinking disabled, `legal-rag-v1`, 180s timeout.

Tests cover unsupported provider, invalid model/output/context limits, missing tokenizer identifier, unknown prompt version, and rejection of client model/sampling/prompt controls.

Result: PASS.
