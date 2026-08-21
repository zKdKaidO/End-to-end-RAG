# Block 6 Phase 06 — Final prompt budget guard

Every provider path counts final structured messages first and enforces:

`prompt_tokens + max_output_tokens + safety_margin <= model_context_limit`

Tests cover normal prompts, the exact hard boundary, one token over, long user input, and invalid profile configuration. Overflow raises HTTP 400 / `QUERY_TOO_LONG`; fake-client instrumentation proves provider calls remain 0. A live 1,255-token E5-over-limit query was also rejected without truncation and before generation.

Result: PASS.
