# Block 6 Phase 04 — Tokenizer/provider parity

Measured local Qwen chat-template counts against Ollama `prompt_eval_count` with `think=false`.

| Fixture | Local | Provider | Abs delta | Relative delta |
|---|---:|---:|---:|---:|
| Vietnamese | 20 | 20 | 0 | 0% |
| Vietnamese legal | 92 | 92 | 0 | 0% |
| Unicode | 32 | 32 | 0 | 0% |
| Multiple evidence | 95 | 95 | 0 | 0% |
| Long query | 1,373 | 1,373 | 0 | 0% |
| Mixed punctuation | 39 | 39 | 0 | 0% |

Worst absolute/relative delta: **0 / 0%**. Despite exact measured parity, the profile reserves **32 tokens** beyond the output reserve. Provider usage in canonical E2E also matched local count exactly: 1,670 / 1,670.

Result: PASS.
