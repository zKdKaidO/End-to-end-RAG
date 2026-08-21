# Block 6 Phase 03 — Tokenizer bindings

Bound frozen Block 5 to a real Hugging Face `ContextTokenCounter` and implemented a separate chat-template-aware `PromptTokenCounter`. Both reuse one cached `Qwen/Qwen3.5-9B` tokenizer object; no E5, tiktoken, character ratio, word count, or proxy heuristic is used in production.

Real smoke: `ContextTokenCounter.count("Việt Nam") = 2`; the Qwen chat prompt for `Chỉ trả lời đúng một từ: OK` counts 20 tokens including roles, special tokens, disabled-thinking template, and generation prompt.

Block 5 source and Greedy Stop behavior were unchanged.

Result: PASS.
